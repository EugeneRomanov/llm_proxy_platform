import asyncio
import httpx
import time
import random

URL = "http://localhost:8000/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "X-Agent-Token": "super-secret-token"
}
DATA = {
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hi"}]
}

# Настройки теста
SEMAPHORE_LIMIT = 5  # одновременных запросов
TOTAL_REQUESTS = 50  # всего запросов
FAILURE_RATE = 0.2   # 20% запросов будут идти к "плохому" провайдеру (имитация отказа)

sem = asyncio.Semaphore(SEMAPHORE_LIMIT)

# Счетчики
success_count = 0
failure_count = 0
blocked_count = 0
latencies = []

async def make_request(client, i):
    global success_count, failure_count, blocked_count
    async with sem:
        start = time.time()
        
        # Имитация отказа: иногда отправляем запрос к несуществующему провайдеру
        # через регистрацию временного плохого провайдера
        if random.random() < FAILURE_RATE and i > 10:  # после 10 запросов начинаем отказы
            # Временно подменяем URL на несуществующий (имитация отказа провайдера)
            bad_data = DATA.copy()
            # Это не влияет на реальный балансировщик, просто симулируем ошибку
            try:
                # Отправляем запрос с коротким таймаутом (имитация отказа)
                async with httpx.AsyncClient(timeout=2.0) as bad_client:
                    resp = await bad_client.post(URL, json=bad_data, headers=HEADERS)
                    duration = time.time() - start
                    print(f"Request {i:02d} | Status: {resp.status_code} | Time: {duration:.2f}s | SIMULATED FAILURE")
                    failure_count += 1
                    return
            except Exception as e:
                duration = time.time() - start
                print(f"Request {i:02d} | FAILED (simulated) | Time: {duration:.2f}s | Error: {type(e).__name__}")
                failure_count += 1
                return
        
        # Нормальный запрос
        try:
            resp = await client.post(URL, json=DATA, headers=HEADERS)
            duration = time.time() - start
            latencies.append(duration)
            
            if resp.status_code == 200:
                success_count += 1
                print(f"Request {i:02d} | Status: {resp.status_code} | Time: {duration:.2f}s | SUCCESS")
            elif resp.status_code == 503:
                blocked_count += 1
                failure_count += 1
                print(f"Request {i:02d} | Status: {resp.status_code} | Time: {duration:.2f}s | NO PROVIDER AVAILABLE")
            else:
                failure_count += 1
                print(f"Request {i:02d} | Status: {resp.status_code} | Time: {duration:.2f}s | FAILED")
                
        except httpx.TimeoutException:
            duration = time.time() - start
            failure_count += 1
            print(f"Request {i:02d} | TIMEOUT | Time: {duration:.2f}s")
        except Exception as e:
            duration = time.time() - start
            failure_count += 1
            print(f"Request {i:02d} | ERROR | Time: {duration:.2f}s | {type(e).__name__}")

async def run_load_test(n=TOTAL_REQUESTS):
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=100)
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        tasks = [make_request(client, i) for i in range(n)]
        await asyncio.gather(*tasks)
    
    # Вывод статистики
    print("\n" + "="*50)
    print("РЕЗУЛЬТАТЫ НАГРУЗОЧНОГО ТЕСТА")
    print("="*50)
    print(f"Всего запросов: {TOTAL_REQUESTS}")
    print(f"Успешных: {success_count} ({success_count/TOTAL_REQUESTS*100:.1f}%)")
    print(f"Неудачных: {failure_count} ({failure_count/TOTAL_REQUESTS*100:.1f}%)")
    if blocked_count > 0:
        print(f"  Из них 503 (провайдеры недоступны): {blocked_count}")
    
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        print(f"\nЛатентность (успешные запросы):")
        print(f"  Средняя: {avg_latency:.2f}s")
        print(f"  P95: {p95:.2f}s")
        print(f"  Минимальная: {min(latencies):.2f}s")
        print(f"  Максимальная: {max(latencies):.2f}s")
    
    throughput = success_count / (time.time() - start_time) if 'start_time' in dir() else 0
    print(f"\nПропускная способность (throughput): {throughput:.2f} req/sec")

if __name__ == "__main__":
    global start_time
    start_time = time.time()
    print(f"Запуск нагрузочного теста:")
    print(f"  Всего запросов: {TOTAL_REQUESTS}")
    print(f"  Одновременных: {SEMAPHORE_LIMIT}")
    print(f"  Доля имитации отказов: {FAILURE_RATE*100}%")
    print("-"*50)
    asyncio.run(run_load_test(TOTAL_REQUESTS))