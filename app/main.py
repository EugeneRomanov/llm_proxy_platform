import time, httpx, logging
from fastapi import FastAPI, Request, HTTPException, Response, Header
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.mlflow_tracing import setup_mlflow, trace_llm_call, log_mlflow_metrics
from app.models import SessionLocal, init_db, Provider
from app.balancer import SmartBalancer
from app.telemetry import setup_telemetry
from app.guardrails import check_content
from app.agent_registry import router as agent_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

balancer = SmartBalancer()

http_client = httpx.AsyncClient(
    timeout=60.0,
    limits=httpx.Limits(max_connections=500, max_keepalive_connections=100)
)

def sync_data():
    """Синхронизация памяти с БД + Аварийный Fallback"""
    db = SessionLocal()
    try:
        db_providers = db.query(Provider).all()
        if db_providers:
            data =[{"name": p.name, "url": p.url, "latency": p.latency_ema or 0.0} for p in db_providers]
            balancer.set_providers(data)
            logger.info("BALANCER: Loaded from DB")
        else:
            raise ValueError("DB is empty")
    except Exception as e:
        logger.warning(f"DB unavailable ({e}). Using Fallback Mocks!")
        balancer.set_providers([
            {"name": "mock1", "url": "http://mock-llm-1:8001/v1/chat/completions", "latency": 0.0},
            {"name": "mock2", "url": "http://mock-llm-2:8001/v1/chat/completions", "latency": 0.0}
        ])
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sync_data()
    setup_mlflow()  
    yield
    await http_client.aclose()

app = FastAPI(lifespan=lifespan)
setup_telemetry(app)

# Подключаем роутер для агентов
app.include_router(agent_router)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "llm-proxy"}

@app.post("/registry/providers")
async def register_provider(name: str, url: str):
    db = SessionLocal()
    try:
        p = db.query(Provider).filter(Provider.name == name).first()
        if p: p.url = url
        else:
            p = Provider(name=name, url=url, is_active=True)
            db.add(p)
        db.commit()
        sync_data()
        return {"status": "registered"}
    finally:
        db.close()

@app.post("/v1/chat/completions")
async def proxy_llm(request: Request, x_agent_token: str = Header(None)):
    from app.telemetry import TTFT, TOKEN_COUNT, COST
    
    if x_agent_token != "super-secret-token":
        raise HTTPException(status_code=401)
    
    body = await request.json()
    if not check_content(body["messages"][-1]["content"]):
        return {"error": "Guardrails blocked"}

    provider = balancer.get_best_provider()
    if not provider:
        sync_data()
        provider = balancer.get_best_provider()
        if not provider:
            raise HTTPException(status_code=503, detail="No providers available")

    start_time = time.time()
    provider_url = provider["url"]
    provider_name = provider.get("name", "unknown")
    timeout = provider.get("timeout_seconds", 60)
    request_success = False
    
    input_text = body["messages"][-1]["content"]
    input_tokens_est = len(input_text.split())
    output_tokens_est = 0
    total_cost = 0.0
    ttft_value = 0.0

    # Начинаем MLFlow трейсинг
    with trace_llm_call(provider_name, body.get("model", "unknown"), input_text) as trace:
        
        async def stream_generator():
            nonlocal request_success, output_tokens_est, total_cost, ttft_value
            ttft_recorded = False
            try:
                async with http_client.stream("POST", provider_url, json=body, timeout=timeout) as resp:
                    if resp.status_code >= 500:
                        balancer.report_error(provider_url)
                        yield b"data: {'error': 'provider_error'}\n\n"
                        return
                    
                    async for chunk in resp.aiter_bytes():
                        if not ttft_recorded and chunk:
                            ttft_value = time.time() - start_time
                            balancer.update_latency(provider_url, ttft_value)
                            TTFT.labels(provider=provider_name).observe(ttft_value)
                            ttft_recorded = True
                        
                        chunk_str = chunk.decode('utf-8', errors='ignore')
                        if 'data:' in chunk_str and '[DONE]' not in chunk_str:
                            output_tokens_est += 1
                        
                        yield chunk
                    
                    request_success = True
                    
                    price_input = provider.get("price_per_1k_input_tokens", 0.0)
                    price_output = provider.get("price_per_1k_output_tokens", 0.0)
                    total_cost = (input_tokens_est / 1000 * price_input) + (output_tokens_est / 1000 * price_output)
                    
                    TOKEN_COUNT.labels(provider=provider_name, type='input').inc(input_tokens_est)
                    TOKEN_COUNT.labels(provider=provider_name, type='output').inc(output_tokens_est)
                    COST.labels(provider=provider_name).inc(total_cost)
                    
                    # Логируем в MLFlow
                    log_mlflow_metrics(ttft_value, input_tokens_est, output_tokens_est, total_cost)
                    
                    logger.info(f"Provider {provider_name}: input_tokens={input_tokens_est}, output_tokens={output_tokens_est}, cost=${total_cost:.6f}")
                    
            except Exception as e:
                logger.error(f"Stream Error for {provider_url}: {e}")
                balancer.report_error(provider_url)
                yield b"data: {'error': 'overload'}\n\n"

        response = StreamingResponse(stream_generator(), media_type="text/event-stream")
        async def finalize():
            if request_success:
                balancer.report_success(provider_url)
        response.background = finalize
        return response

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)