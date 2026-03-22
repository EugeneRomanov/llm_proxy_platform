from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram
import time

REQUEST_COUNT = Counter('request_count', 'Total HTTP requests', ['method', 'endpoint'])
LATENCY = Histogram('request_latency_seconds', 'HTTP request latency', ['endpoint'])

# Новые метрики для Level 2
TTFT = Histogram('llm_ttft_seconds', 'Time to first token', ['provider'])
TOKEN_COUNT = Counter('llm_tokens_total', 'Total tokens processed', ['provider', 'type'])
COST = Counter('llm_cost_total', 'Total cost in USD', ['provider'])

def setup_telemetry(app):
    FastAPIInstrumentor.instrument_app(app)
    
    @app.middleware("http")
    async def monitor_requests(request, call_next):
        start_time = time.time()
        endpoint = request.url.path
        REQUEST_COUNT.labels(method=request.method, endpoint=endpoint).inc()
        response = await call_next(request)
        process_time = time.time() - start_time
        LATENCY.labels(endpoint=endpoint).observe(process_time)
        return response