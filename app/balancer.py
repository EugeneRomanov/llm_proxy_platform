import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class SmartBalancer:
    def __init__(self):
        self.providers = []
        self.error_threshold = 3
        self.block_duration = 30

    def set_providers(self, providers_list: List[Dict]):
        self.providers = providers_list
        logger.info(f"Balancer: loaded {len(providers_list)} providers")
        for p in self.providers:
            logger.info(f"  {p.get('name')}: {p.get('url')}")

    def _is_blocked(self, provider: Dict) -> bool:
        blocked_until = provider.get("blocked_until", 0)
        if blocked_until > time.time():
            return True
        if blocked_until != 0 and blocked_until <= time.time():
            provider["consecutive_errors"] = 0
            provider["blocked_until"] = 0
            logger.info(f"Provider {provider.get('name')} unblocked")
        return False

    def get_best_provider(self) -> Optional[Dict]:
        if not self.providers:
            return None
        available = [
            p for p in self.providers
            if p.get("is_active", True) and not self._is_blocked(p)
        ]
        if not available:
            logger.warning("No available providers!")
            return None
        best = min(available, key=lambda x: x.get("latency", float('inf')))
        logger.info(f"Selected provider: {best.get('name')} ({best.get('url')})")
        return best

    def update_latency(self, url: str, new_latency: float):
        for p in self.providers:
            if p["url"] == url:
                alpha = 0.3
                old_latency = p.get("latency", new_latency)
                p["latency"] = (alpha * new_latency) + (1 - alpha) * old_latency
                break

    def report_error(self, url: str):
        logger.info(f"Reporting error for URL: {url}")
        for p in self.providers:
            if p["url"] == url:
                errors = p.get("consecutive_errors", 0) + 1
                p["consecutive_errors"] = errors
                p["last_error_time"] = int(time.time())
                logger.warning(f"Provider {p.get('name')} error count: {errors}")
                if errors >= self.error_threshold:
                    p["blocked_until"] = int(time.time() + self.block_duration)
                    logger.warning(f"Provider {p.get('name')} BLOCKED for {self.block_duration}s")
                break
        else:
            logger.warning(f"No provider found with URL {url}")

    def report_success(self, url: str):
        for p in self.providers:
            if p["url"] == url:
                if p.get("consecutive_errors", 0) > 0:
                    p["consecutive_errors"] = 0
                    logger.info(f"Provider {p.get('name')} errors reset")
                break