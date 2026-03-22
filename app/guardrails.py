import re

# Список запрещенных паттернов
DANGEROUS_PATTERNS = [
    r"ignore previous instructions",
    r"system prompt injection",
    r"sk-[a-zA-Z0-9]{48}", # Поиск API-ключей OpenAI
    r"DROP TABLE",         # Попытки SQL-инъекций
]

def check_content(text: str) -> bool:
    """Возвращает True, если текст безопасен, и False, если найдены нарушения"""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    return True