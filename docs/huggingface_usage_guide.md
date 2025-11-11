# Руководство по использованию HuggingFace LLM в проекте

## Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Установка и настройка](#установка-и-настройка)
3. [Примеры использования](#примеры-использования)
4. [API Reference](#api-reference)
5. [Интеграция с Telegram ботом](#интеграция-с-telegram-ботом)
6. [Обработка ошибок](#обработка-ошибок)
7. [Best Practices](#best-practices)
8. [FAQ](#faq)

## Быстрый старт

Минимальный пример использования HuggingFace LLM:

```python
from huggingface_client import HuggingFaceClient

# Инициализация клиента
client = HuggingFaceClient()

# Генерация ответа
metrics = client.generate_response(
    model_key="qwen",
    prompt="Привет! Как дела?"
)

print(metrics.response)
```

## Установка и настройка

### 1. Установка зависимостей

```bash
# Убедитесь, что виртуальное окружение активировано
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows

# Установите зависимости
pip install -r requirements.txt
```

### 2. Получение API ключа

1. Зарегистрируйтесь на [HuggingFace](https://huggingface.co/)
2. Перейдите в [Settings → Access Tokens](https://huggingface.co/settings/tokens)
3. Создайте новый токен с правами:
   - ✅ Read access to contents of all repos you can access
   - ✅ Make calls to Inference Providers (**обязательно!**)
4. Скопируйте токен

### 3. Настройка переменных окружения

Создайте или обновите файл `.env`:

```bash
# HuggingFace API Configuration
HF_API_KEY=hf_ваш_токен_здесь
```

### 4. Проверка установки

```bash
python huggingface_client.py
```

Если все настроено правильно, вы увидите результаты тестирования трех моделей.

## Примеры использования

### Базовая генерация текста

```python
from huggingface_client import HuggingFaceClient

client = HuggingFaceClient()

# Генерация с дефолтными параметрами
metrics = client.generate_response(
    model_key="qwen",
    prompt="Напиши короткое стихотворение про осень"
)

print(f"Ответ: {metrics.response}")
print(f"Время: {metrics.execution_time:.2f}с")
print(f"Токены: {metrics.total_tokens}")
```

### Настройка параметров генерации

```python
# Более креативная генерация (temperature выше)
metrics = client.generate_response(
    model_key="llama",
    prompt="Придумай необычное название для кофейни",
    max_tokens=100,
    temperature=1.0  # Более креативно
)

# Более детерминированная генерация (temperature ниже)
metrics = client.generate_response(
    model_key="phi",
    prompt="Что такое Python?",
    max_tokens=300,
    temperature=0.3  # Более стабильно
)
```

### Тестирование всех моделей

```python
from huggingface_client import HuggingFaceClient

client = HuggingFaceClient()

# Единый промпт для всех моделей
prompt = "Объясни, что такое машинное обучение, простыми словами"

# Запуск тестирования
results = client.test_all_models(
    prompt=prompt,
    max_tokens=400,
    temperature=0.7
)

# Вывод таблицы
print(client.format_metrics_table(results))

# Детальный вывод
for metrics in results:
    print(f"\n{'='*60}")
    print(f"Модель: {metrics.model_name}")
    print(f"Время: {metrics.execution_time:.2f}с")
    print(f"Ответ: {metrics.response}")
```

### Сравнение моделей

```python
from huggingface_client import HuggingFaceClient

def compare_models(prompt: str):
    """Сравнить качество ответов от разных моделей"""
    client = HuggingFaceClient()

    results = client.test_all_models(prompt)

    # Сортировка по времени выполнения
    results_by_speed = sorted(results, key=lambda x: x.execution_time)
    print(f"Самая быстрая: {results_by_speed[0].model_name}")

    # Сортировка по количеству токенов
    results_by_tokens = sorted(results, key=lambda x: x.output_tokens, reverse=True)
    print(f"Самая детальная: {results_by_tokens[0].model_name}")

    return results

# Использование
results = compare_models("Что такое квантовая физика?")
```

### Использование с явным токеном

```python
from huggingface_client import HuggingFaceClient

# Передача токена явно (без .env)
client = HuggingFaceClient(api_token="hf_ваш_токен")

metrics = client.generate_response(
    model_key="qwen",
    prompt="Привет!"
)
```

## API Reference

### HuggingFaceClient

#### `__init__(api_token: Optional[str] = None)`

Инициализация клиента.

**Параметры:**
- `api_token` (str, optional): HuggingFace API токен. Если не указан, берется из переменной окружения `HF_API_KEY`.

**Raises:**
- `ValueError`: Если токен не найден ни в параметрах, ни в переменных окружения.

---

#### `generate_response(model_key: str, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> ModelMetrics`

Генерация ответа от конкретной модели.

**Параметры:**
- `model_key` (str): Ключ модели ('qwen', 'llama', 'phi')
- `prompt` (str): Текст запроса
- `max_tokens` (int): Максимальное количество токенов в ответе (default: 500)
- `temperature` (float): Температура генерации 0.0-2.0 (default: 0.7)

**Returns:**
- `ModelMetrics`: Объект с результатами и метриками

**Raises:**
- `ValueError`: Если указан несуществующий model_key
- `Exception`: При ошибках API

---

#### `test_all_models(prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> List[ModelMetrics]`

Тестирование всех доступных моделей.

**Параметры:**
- `prompt` (str): Единый текст запроса для всех моделей
- `max_tokens` (int): Максимальное количество токенов (default: 500)
- `temperature` (float): Температура генерации (default: 0.7)

**Returns:**
- `List[ModelMetrics]`: Список результатов для каждой модели

---

#### `format_metrics_table(metrics_list: List[ModelMetrics]) -> str` (static)

Форматирование результатов в Markdown таблицу.

**Параметры:**
- `metrics_list` (List[ModelMetrics]): Список метрик

**Returns:**
- `str`: Таблица в формате Markdown

---

#### `get_model_info() -> Dict[str, Any]` (static)

Получение информации о доступных моделях.

**Returns:**
- `Dict[str, Any]`: Словарь с информацией о моделях

### ModelMetrics

Dataclass с метриками выполнения запроса.

**Атрибуты:**
- `model_name` (str): Название модели
- `model_url` (str): URL модели на HuggingFace
- `prompt` (str): Исходный запрос
- `response` (str): Ответ модели
- `execution_time` (float): Время выполнения в секундах
- `input_tokens` (int): Количество входных токенов
- `output_tokens` (int): Количество выходных токенов
- `total_tokens` (int): Общее количество токенов
- `cost` (str): Стоимость запроса
- `quality_notes` (str): Заметки о качестве (опционально)

## Интеграция с Telegram ботом

### Добавление HuggingFace в Telegram бота

```python
# В файле bot.py

from huggingface_client import HuggingFaceClient

class TelegramBot:
    def __init__(self):
        # ... существующий код ...

        # Инициализация HuggingFace клиента
        try:
            self.hf_client = HuggingFaceClient()
            logger.info("HuggingFace клиент инициализирован")
        except Exception as e:
            logger.warning(f"HuggingFace недоступен: {e}")
            self.hf_client = None

    async def handle_message_huggingface(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        model_key: str = "qwen"
    ):
        """Обработка сообщения через HuggingFace"""
        if not self.hf_client:
            await update.message.reply_text(
                "HuggingFace API недоступен. Проверьте настройки."
            )
            return

        user_message = update.message.text

        try:
            # Генерация ответа
            metrics = self.hf_client.generate_response(
                model_key=model_key,
                prompt=user_message,
                max_tokens=500,
                temperature=0.7
            )

            # Отправка ответа
            response_text = (
                f"{metrics.response}\n\n"
                f"_Модель: {metrics.model_name.split('/')[-1]}_\n"
                f"_Время: {metrics.execution_time:.2f}с_"
            )

            await update.message.reply_text(
                response_text,
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Ошибка HuggingFace: {str(e)}")
            await update.message.reply_text(
                "Произошла ошибка при обработке запроса."
            )
```

### Команды для переключения моделей

```python
async def cmd_use_qwen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить на модель Qwen"""
    context.user_data['hf_model'] = 'qwen'
    await update.message.reply_text("Используется модель: Qwen 2.5 7B")

async def cmd_use_llama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить на модель Llama"""
    context.user_data['hf_model'] = 'llama'
    await update.message.reply_text("Используется модель: Llama 3.2 3B")

async def cmd_use_phi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить на модель Phi"""
    context.user_data['hf_model'] = 'phi'
    await update.message.reply_text("Используется модель: Phi-3 mini")

# Регистрация команд
app.add_handler(CommandHandler("qwen", cmd_use_qwen))
app.add_handler(CommandHandler("llama", cmd_use_llama))
app.add_handler(CommandHandler("phi", cmd_use_phi))
```

## Обработка ошибок

### Основные типы ошибок

```python
from huggingface_client import HuggingFaceClient

client = HuggingFaceClient()

try:
    metrics = client.generate_response(
        model_key="qwen",
        prompt="Тестовый запрос"
    )
except ValueError as e:
    # Неверный model_key или отсутствует токен
    print(f"Ошибка конфигурации: {e}")
except ConnectionError as e:
    # Проблемы с сетью
    print(f"Ошибка подключения: {e}")
except Exception as e:
    # Другие ошибки (rate limiting, timeout, и т.д.)
    print(f"Ошибка API: {e}")
```

### Rate Limiting

```python
import time
from huggingface_client import HuggingFaceClient

client = HuggingFaceClient()

def generate_with_retry(model_key: str, prompt: str, max_retries: int = 3):
    """Генерация с повторными попытками при rate limiting"""
    for attempt in range(max_retries):
        try:
            return client.generate_response(
                model_key=model_key,
                prompt=prompt
            )
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                # Rate limit exceeded
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limit. Ожидание {wait_time}с...")
                time.sleep(wait_time)
            else:
                raise

    raise Exception("Превышено количество попыток")

# Использование
metrics = generate_with_retry("qwen", "Привет!")
```

## Best Practices

### 1. Управление токенами

```python
# Плохо: хардкод токена
client = HuggingFaceClient(api_token="hf_xxxxxxxxxxxxx")

# Хорошо: использование переменных окружения
client = HuggingFaceClient()  # Читает из .env
```

### 2. Выбор модели

```python
# Для быстрых ответов
client.generate_response("llama", prompt, max_tokens=200)

# Для качественных развернутых ответов
client.generate_response("qwen", prompt, max_tokens=800)

# Для компактных ответов
client.generate_response("phi", prompt, max_tokens=150)
```

### 3. Оптимизация параметров

```python
# Фактические ответы (детерминированность)
metrics = client.generate_response(
    model_key="qwen",
    prompt="Столица Франции?",
    temperature=0.1,
    max_tokens=50
)

# Креативная генерация (высокая вариативность)
metrics = client.generate_response(
    model_key="qwen",
    prompt="Придумай слоган для стартапа",
    temperature=1.2,
    max_tokens=100
)
```

### 4. Логирование

```python
import logging

# Настройка детального логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("huggingface.log"),
        logging.StreamHandler()
    ]
)

client = HuggingFaceClient()
# Все запросы будут залогированы
```

### 5. Кэширование результатов

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_generate(model_key: str, prompt: str) -> str:
    """Кэширование результатов для частых запросов"""
    client = HuggingFaceClient()
    metrics = client.generate_response(model_key, prompt)
    return metrics.response

# Использование
response1 = cached_generate("qwen", "Что такое Python?")
response2 = cached_generate("qwen", "Что такое Python?")  # Из кэша
```

## FAQ

### Как получить бесплатный доступ к HuggingFace API?

Зарегистрируйтесь на [huggingface.co](https://huggingface.co/) и создайте токен в настройках. Бесплатный tier включает достаточно запросов для тестирования и небольших проектов.

### Какие лимиты у бесплатного tier?

- 30 запросов/минута
- 60,000 токенов/минута
- 900 запросов/час
- 1,000,000 токенов/час
- 14,400 запросов/день

### Какую модель выбрать?

- **Qwen 2.5 7B**: Для сложных задач, требующих качественных ответов
- **Llama 3.2 3B**: Универсальный выбор, баланс скорости и качества
- **Phi-3 mini**: Для быстрых простых запросов

### Можно ли использовать другие модели?

Да! Добавьте информацию о модели в словарь `AVAILABLE_MODELS` в файле [huggingface_client.py:48](../huggingface_client.py#L48).

### Как точно подсчитать токены?

Текущая реализация использует приблизительную формулу (4 символа = 1 токен). Для точного подсчета можно использовать библиотеку `tiktoken` или API модели.

### Почему модель возвращает ошибку?

Проверьте:
1. Правильность HF_API_KEY в .env
2. Права токена (должен быть "Make calls to Inference Providers")
3. Не превышены ли лимиты запросов
4. Доступность Inference Provider для модели

### Можно ли использовать в production?

Да, но рекомендуется:
- Использовать PRO аккаунт с увеличенными лимитами
- Реализовать retry логику
- Добавить мониторинг и алерты
- Использовать кэширование

## Дополнительные ресурсы

- [Документация HuggingFace Inference Client](https://huggingface.co/docs/huggingface_hub/package_reference/inference_client)
- [Документация по интеграции](huggingface_integration.md)
- [Результаты тестирования](llm_comparison_results.md)
- [HuggingFace Community](https://huggingface.co/spaces)
