# Документация: LLM Провайдеры

Этот документ описывает архитектуру системы провайдеров LLM в телеграм-боте.

## Обзор

Бот использует модульную архитектуру для поддержки множественных LLM провайдеров. Каждый провайдер реализует унифицированный интерфейс `LLMProvider`, что позволяет легко добавлять новые модели без изменения основного кода бота.

## Архитектура

```
providers/
├── __init__.py
├── base.py                 # Абстрактный интерфейс LLMProvider
├── openai_provider.py      # Провайдер для OpenAI GPT
├── yandex_provider.py      # Провайдер для Yandex GPT
└── deepseek_provider.py    # Провайдер для DeepSeek
```

## Базовый интерфейс: `LLMProvider`

### Местоположение
`providers/base.py`

### Описание
Абстрактный класс, определяющий общий интерфейс для всех LLM провайдеров.

### Методы

#### `__init__(api_key: str, timeout: int = 30)`
Инициализация провайдера.

**Параметры:**
- `api_key` (str): API ключ для доступа к сервису
- `timeout` (int): Таймаут запроса в секундах (по умолчанию 30)

#### `async generate_response(...) -> Optional[str]`
Генерация ответа от LLM.

**Параметры:**
- `user_message` (str): Сообщение от пользователя
- `system_prompt` (str): Системный промпт для управления поведением модели
- `conversation_history` (Optional[List[Dict]]): История диалога

**Формат `conversation_history`:**
```python
[
    {"message_text": "привет", "message_type": "user"},
    {"message_text": "здравствуйте", "message_type": "assistant"},
    ...
]
```

**Возвращает:**
- `str`: Текстовый ответ от LLM
- `None`: В случае ошибки

#### `get_provider_name() -> str`
Возвращает имя провайдера.

**Возвращает:**
- `str`: "openai", "yandex" или "deepseek"

---

## OpenAI Provider

### Местоположение
`providers/openai_provider.py`

### Описание
Провайдер для работы с OpenAI GPT API. Использует официальную библиотеку `openai`.

### Инициализация

```python
from providers import OpenAIProvider

provider = OpenAIProvider(
    api_key="sk-...",
    model="gpt-3.5-turbo",    # или gpt-4, gpt-4-turbo
    timeout=30,
    temperature=0.9,
    max_tokens=2000
)
```

### Параметры

- `api_key` (str): API ключ OpenAI
- `model` (str): Название модели (по умолчанию "gpt-3.5-turbo")
- `timeout` (int): Таймаут запроса
- `temperature` (float): Температура генерации (0.0-2.0)
- `max_tokens` (int): Максимум токенов в ответе

### Обработка ошибок

Провайдер обрабатывает следующие типы ошибок:
- `RateLimitError`: Превышен лимит запросов
- `APIConnectionError`: Проблемы с соединением
- `APIStatusError`: HTTP ошибки
- `OpenAIError`: Общие ошибки API

При любой ошибке возвращается `None`, и ошибка логируется.

---

## Yandex GPT Provider

### Местоположение
`providers/yandex_provider.py`

### Описание
Провайдер для работы с Yandex GPT API. Использует `httpx` для асинхронных запросов.

### Инициализация

```python
from providers import YandexGPTProvider

provider = YandexGPTProvider(
    api_key="...",
    folder_id="b1g...",          # ID каталога Yandex Cloud
    model="yandexgpt-lite",       # или yandexgpt
    timeout=30,
    temperature=0.9,
    max_tokens=2000
)
```

### Параметры

- `api_key` (str): API ключ Yandex Cloud
- `folder_id` (Optional[str]): ID каталога (если None, берётся из env)
- `model` (str): Название модели (по умолчанию "yandexgpt-lite")
- `timeout` (int): Таймаут запроса
- `temperature` (float): Температура генерации (0.0-1.0)
- `max_tokens` (int): Максимум токенов в ответе

### Особенности

- Использует специфичный формат сообщений Yandex API (поле "text" вместо "content")
- Требует modelUri в формате `gpt://{folder_id}/{model}`

---

## DeepSeek Provider

### Местоположение
`providers/deepseek_provider.py`

### Описание
Провайдер для работы с DeepSeek API. DeepSeek использует OpenAI-совместимый API.

### Инициализация

```python
from providers import DeepSeekProvider

provider = DeepSeekProvider(
    api_key="sk-...",
    model="deepseek-chat",       # или deepseek-coder
    timeout=30,
    temperature=0.9,
    max_tokens=2000
)
```

### Параметры

- `api_key` (str): API ключ DeepSeek
- `model` (str): Название модели (по умолчанию "deepseek-chat")
- `timeout` (int): Таймаут запроса
- `temperature` (float): Температура генерации (0.0-2.0)
- `max_tokens` (int): Максимум токенов в ответе

### Особенности

- Использует кастомный `base_url`: `https://api.deepseek.com`
- API полностью совместим с OpenAI
- Поддерживает все те же типы ошибок что и OpenAI

---

## Добавление нового провайдера

Чтобы добавить поддержку нового LLM провайдера:

### 1. Создайте новый файл провайдера

Создайте файл `providers/your_provider.py`:

```python
"""
Провайдер для работы с YourLLM API.
"""

import logging
from typing import Optional, List, Dict

from .base import LLMProvider

logger = logging.getLogger(__name__)


class YourLLMProvider(LLMProvider):
    """
    Провайдер для работы с YourLLM API.
    """

    def __init__(self, api_key: str, timeout: int = 30):
        super().__init__(api_key, timeout)
        # Инициализация клиента
        logger.info("YourLLM Provider инициализирован")

    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """Генерация ответа от YourLLM."""
        try:
            # Реализуйте логику запроса к API
            # ...
            return response_text
        except Exception as e:
            logger.error(f"Ошибка YourLLM API: {e}")
            return None

    def get_provider_name(self) -> str:
        """Получение имени провайдера."""
        return "yourllm"
```

### 2. Зарегистрируйте провайдер

Обновите `providers/__init__.py`:

```python
from .your_provider import YourLLMProvider

__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "YandexGPTProvider",
    "DeepSeekProvider",
    "YourLLMProvider",  # Добавьте сюда
]
```

### 3. Обновите хранилище настроек

В `storage/user_settings.py`, обновите валидацию:

```python
if provider not in ["openai", "yandex", "deepseek", "yourllm"]:
    logger.error(f"Недопустимый провайдер: {provider}")
    return False
```

### 4. Добавьте поддержку в bot.py

1. Импортируйте провайдер:
```python
from providers import OpenAIProvider, YandexGPTProvider, DeepSeekProvider, YourLLMProvider
```

2. Инициализируйте в `__init__`:
```python
self.yourllm_provider = None
if yourllm_api_key:
    self.yourllm_provider = YourLLMProvider(yourllm_api_key)
```

3. Добавьте команду переключения:
```python
async def yourllm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... реализация
```

4. Обновите `handle_message`:
```python
elif selected_provider == "yourllm" and self.yourllm_provider:
    provider = self.yourllm_provider
```

### 5. Обновите переменные окружения

Добавьте в `.env.example`:
```env
YOURLLM_API_KEY=your_api_key_here
```

---

## Логирование

Все провайдеры используют стандартный модуль `logging` Python.

### Уровни логирования:

- `INFO`: Успешные операции (инициализация, получение ответа)
- `WARNING`: Предупреждения (недоступность провайдера)
- `ERROR`: Ошибки API
- `DEBUG`: Детальная информация (длина ответа, контекст)

### Пример логов:

```
2025-11-18 12:34:56 - providers.openai_provider - INFO - OpenAI Provider инициализирован с моделью gpt-3.5-turbo
2025-11-18 12:35:01 - providers.openai_provider - INFO - Отправка запроса в OpenAI API (модель: gpt-3.5-turbo)
2025-11-18 12:35:03 - providers.openai_provider - INFO - Получен ответ от OpenAI API
```

---

## Тестирование провайдеров

Для тестирования нового провайдера:

1. **Unit тесты**: Создайте тесты в `tests/test_your_provider.py`
2. **Интеграционные тесты**: Протестируйте через команды бота
3. **Проверьте обработку ошибок**: Отключите API и убедитесь в корректном fallback

---

## Производительность

### Сравнение провайдеров (примерное время ответа):

- **OpenAI GPT-3.5**: 1-3 секунды
- **Yandex GPT Lite**: 2-5 секунд
- **DeepSeek**: 1-4 секунды

*Время зависит от длины промпта, контекста и загрузки API.*

---

## Безопасность

1. **API ключи**: Никогда не коммитьте ключи в репозиторий
2. **Логирование**: API ключи не логируются
3. **Таймауты**: Все провайдеры имеют таймауты для предотвращения зависания
4. **Обработка ошибок**: Все ошибки перехватываются и логируются

---

## Дополнительные ресурсы

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Yandex GPT API Documentation](https://cloud.yandex.ru/docs/yandexgpt/)
- [DeepSeek API Documentation](https://platform.deepseek.com/api-docs/)
