import mlflow
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Настройка MLFlow
MLFLOW_TRACKING_URI = "http://mlflow:5000"

def setup_mlflow():
    """Настройка MLFlow для трейсинга"""
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        logger.info(f"MLFlow configured with URI: {MLFLOW_TRACKING_URI}")
    except Exception as e:
        logger.warning(f"MLFlow setup failed: {e}")

@contextmanager
def trace_llm_call(provider_name: str, model: str, input_text: str):
    """Контекстный менеджер для трейсинга LLM вызовов"""
    run_name = f"llm_call_{provider_name}"
    try:
        with mlflow.start_run(run_name=run_name) as run:
            # Логируем параметры
            mlflow.log_param("provider", provider_name)
            mlflow.log_param("model", model)
            mlflow.log_param("input_text", input_text[:500])  # ограничиваем длину
            
            logger.info(f"MLFlow run started: {run.info.run_id}")
            yield run
            
    except Exception as e:
        logger.warning(f"MLFlow tracing failed: {e}")
        yield None  # Продолжаем работу даже если MLFlow не доступен

def log_mlflow_metrics(ttft: float, input_tokens: int, output_tokens: int, cost: float):
    """Логирование метрик в MLFlow"""
    try:
        mlflow.log_metric("ttft_seconds", ttft)
        mlflow.log_metric("input_tokens", input_tokens)
        mlflow.log_metric("output_tokens", output_tokens)
        mlflow.log_metric("total_tokens", input_tokens + output_tokens)
        mlflow.log_metric("cost_usd", cost)
        logger.info("MLFlow metrics logged")
    except Exception as e:
        logger.warning(f"Failed to log MLFlow metrics: {e}")