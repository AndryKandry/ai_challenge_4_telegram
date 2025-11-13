# Архитектура управления контекстом

## Обзор

Система управления контекстом отвечает за хранение, обработку и компрессию истории диалогов пользователей с ботом. Архитектура спроектирована для эффективного использования токенов при сохранении качества ответов.

## Компоненты системы

### 1. DialogHistory

**Расположение**: [dialog_compressor.py:18](../../dialog_compressor.py#L18)

**Назначение**: Хранение истории диалога для каждого пользователя.

**Структура данных**:
```python
class DialogHistory:
    def __init__(self):
        self.messages: List[Dict[str, str]] = []  # История сообщений
        self.system_prompt: Optional[str] = None  # Системный промпт
        self.compressed_context: Optional[str] = None  # Сжатый контекст
```

**Формат сообщения**:
```python
{
    "role": "user" | "assistant",
    "text": "содержимое сообщения"
}
```

**Методы**:
- `add_message(role, text)` - Добавить сообщение в историю
- `set_system_prompt(prompt)` - Установить системный промпт
- `set_compressed_context(context)` - Установить сжатый контекст
- `get_message_count()` - Получить количество сообщений
- `get_last_n_messages(n)` - Получить последние N сообщений
- `get_messages_to_compress(keep_last_n)` - Получить сообщения для компрессии
- `clear_compressed_messages(keep_last_n)` - Удалить сжатые сообщения

### 2. DialogCompressor

**Расположение**: [dialog_compressor.py:86](../../dialog_compressor.py#L86)

**Назначение**: Выполнение компрессии истории диалога.

**Зависимости**:
- `YandexGPTClient` - Для создания резюме через LLM
- `TokenCounter` - Для подсчёта токенов
- `Config` - Настройки компрессии

**Основные методы**:
- `should_compress(history)` - Проверка необходимости компрессии
- `compress_history(history, keep_last_n)` - Основной метод компрессии
- `create_summary(history_text)` - Создание резюме через Yandex GPT
- `extract_key_facts(summary)` - Извлечение ключевых фактов
- `get_compression_stats_message(stats)` - Форматирование статистики

### 3. TelegramBot (интеграция)

**Расположение**: [bot.py:141](../../bot.py#L141)

**Интеграция компрессии**:
```python
class TelegramBot:
    def __init__(self, ...):
        # Система компрессии диалога
        self.dialog_compressor = DialogCompressor(yandex_api_key, self.token_counter)
        self.user_histories: dict[int, DialogHistory] = {}
```

**Хранилище историй**:
- Ключ: `user_id` (int) - ID пользователя в Telegram
- Значение: `DialogHistory` - История диалога пользователя

## Поток данных

### 1. Получение сообщения от пользователя

```
┌─────────────┐
│ Пользователь│
│ отправляет  │
│ сообщение   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ handle_message()    │
│ - Получить/создать  │
│   DialogHistory     │
│ - Проверить нужна   │
│   ли компрессия     │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Автокомпрессия?     │◄─── should_compress()
└──────┬──────────────┘
       │ Да
       ▼
┌─────────────────────┐
│ compress_history()  │
│ (keep_last_n=10)    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Отправить запрос    │
│ к Yandex GPT        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Сохранить сообщения │
│ в DialogHistory     │
│ - user message      │
│ - assistant response│
└─────────────────────┘
```

### 2. Ручная компрессия `/compact`

```
┌─────────────┐
│ Пользователь│
│ отправляет  │
│ /compact    │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ compact_command()   │
│ - Получить историю  │
│ - Проверить         │
│   минимум 2 msg     │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ compress_history()  │
│ (keep_last_n=0)     │ ◄─── ВСЕ сообщения
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Создать резюме      │
│ через Yandex GPT    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Заменить историю    │
│ на резюме           │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Показать статистику │
│ пользователю        │
└─────────────────────┘
```

## Структура хранения в памяти

### Словарь историй пользователей

```python
self.user_histories = {
    123456789: DialogHistory(  # user_id_1
        messages=[
            {"role": "user", "text": "Привет!"},
            {"role": "assistant", "text": "Здравствуйте! Чем могу помочь?"},
            # ... ещё 48 сообщений
        ],
        system_prompt="Ты — помощник в Telegram...",
        compressed_context=None
    ),
    987654321: DialogHistory(  # user_id_2
        messages=[
            {"role": "user", "text": "Как дела?"},
            {"role": "assistant", "text": "Отлично, спасибо!"},
        ],
        system_prompt="Ты — помощник в Telegram...",
        compressed_context=None
    ),
}
```

### После компрессии (автоматической)

```python
DialogHistory(
    messages=[
        # Последние 10 сообщений сохранены
        {"role": "user", "text": "..."},
        {"role": "assistant", "text": "..."},
        # ... ещё 8 сообщений
    ],
    system_prompt="Ты — помощник в Telegram...",
    compressed_context="""[COMPRESSED CONTEXT]
Резюме предыдущего диалога:
- Пользователь: разработчик Python
- Задача: создание Telegram-бота
- Выполнено: базовая структура, команды
- В работе: интеграция с Yandex GPT
- Ключевые решения: использовать python-telegram-bot
- Важный контекст: асинхронная архитектура
[/COMPRESSED CONTEXT]"""
)
```

### После `/compact` (ручной компрессии)

```python
DialogHistory(
    messages=[],  # Все сообщения удалены!
    system_prompt="Ты — помощник в Telegram...",
    compressed_context="""[COMPRESSED CONTEXT]
Резюме предыдущего диалога:
- Пользователь: разработчик Python
- Задача: создание Telegram-бота с Yandex GPT
- Выполнено: полная реализация бота, все команды, интеграция с API
- В работе: нет
- Ключевые решения: асинхронная архитектура, обработка ошибок
- Важный контекст: бот готов к деплойменту
[/COMPRESSED CONTEXT]"""
)
```

## Алгоритм компрессии

### 1. Проверка необходимости (should_compress)

```python
def should_compress(history: DialogHistory) -> Tuple[bool, str]:
    """
    Проверяет два условия:
    1. Количество сообщений >= COMPRESSION_MAX_MESSAGES (50)
    2. Использование токенов >= COMPRESSION_MAX_TOKENS_PERCENT (85%)
    """

    # Проверка 1: Количество сообщений
    if history.get_message_count() >= 50:
        return (True, "Message count exceeded")

    # Проверка 2: Процент токенов
    total_tokens = calculate_total_tokens(history)
    token_limit = get_model_token_limit("yandexgpt-lite")  # 8192
    token_percentage = (total_tokens / token_limit) * 100

    if token_percentage >= 85:
        return (True, f"Token usage at {token_percentage:.1f}%")

    return (False, "Within limits")
```

### 2. Подготовка к компрессии

```python
# Получить сообщения для компрессии
messages_to_compress = history.get_messages_to_compress(keep_last_n)

# Для /compact: keep_last_n = 0 → все сообщения
# Для автокомпрессии: keep_last_n = 10 → все кроме последних 10

# Подсчёт токенов ДО компрессии
tokens_before = sum(
    token_counter.count_tokens(msg["text"])
    for msg in messages_to_compress
)
```

### 3. Создание резюме

```python
# Форматирование истории для LLM
history_text = """
[Сообщение 1 - Пользователь]
Привет, помоги создать бота

[Сообщение 2 - Ассистент]
Конечно! Вот что нужно сделать...

...
"""

# Отправка в Yandex GPT
payload = {
    "modelUri": "gpt://.../yandexgpt-lite",
    "completionOptions": {
        "temperature": 0.3,  # Низкая для стабильности
        "maxTokens": 2000,
    },
    "messages": [
        {
            "role": "system",
            "text": "Ты — эксперт по анализу и сжатию информации..."
        },
        {
            "role": "user",
            "text": compression_prompt  # Из prompts/compression_summary.txt
        }
    ]
}

summary = await send_to_yandex_gpt(payload)
```

### 4. Обновление истории

```python
# Создание сжатого контекста
compressed_context = f"""[COMPRESSED CONTEXT]
Резюме предыдущего диалога:
{summary}
[/COMPRESSED CONTEXT]"""

# Обновление истории
history.set_compressed_context(compressed_context)
history.clear_compressed_messages(keep_last_n)

# Подсчёт токенов ПОСЛЕ компрессии
tokens_after = token_counter.count_tokens(summary)
savings = ((tokens_before - tokens_after) / tokens_before) * 100
```

## Взаимодействие с Yandex GPT

### Запрос на создание резюме

```http
POST https://llm.api.cloud.yandex.net/foundationModels/v1/completion
Authorization: Bearer {YANDEX_API_KEY}
Content-Type: application/json

{
    "modelUri": "gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
    "completionOptions": {
        "stream": false,
        "temperature": 0.3,
        "maxTokens": 2000
    },
    "messages": [
        {
            "role": "system",
            "text": "Ты — эксперт по анализу и сжатию информации..."
        },
        {
            "role": "user",
            "text": "Проанализируй следующую историю диалога..."
        }
    ]
}
```

### Ответ от Yandex GPT

```json
{
    "result": {
        "alternatives": [
            {
                "message": {
                    "role": "assistant",
                    "text": "- Пользователь: разработчик Python\n- Задача: создание Telegram-бота\n..."
                },
                "status": "ALTERNATIVE_STATUS_FINAL"
            }
        ],
        "usage": {
            "inputTextTokens": "1234",
            "completionTokens": "256",
            "totalTokens": "1490"
        }
    }
}
```

## Обработка ошибок

### 1. Ошибки сети

```python
try:
    response = await client.post(...)
except httpx.TimeoutException:
    logger.error("Timeout while creating summary")
    return None
except httpx.HTTPStatusError as e:
    logger.error(f"HTTP error: {e.response.status_code}")
    return None
```

**Поведение**: Компрессия не выполняется, история остаётся без изменений.

### 2. Неожиданная структура ответа

```python
if "result" in data and "alternatives" in data["result"]:
    summary = data["result"]["alternatives"][0]["message"]["text"]
else:
    logger.error(f"Unexpected response structure: {data}")
    return None
```

**Поведение**: Логирование ошибки, возврат None, история не изменяется.

### 3. Пустая история

```python
if history.get_message_count() < 2:
    return "История слишком короткая для компрессии"
```

**Поведение**: Пользователь получает информационное сообщение.

## Производительность

### Временные характеристики

| Операция | Среднее время | Примечание |
|----------|---------------|------------|
| `should_compress()` | < 1 мс | Проверка в памяти |
| `add_message()` | < 1 мс | Добавление в список |
| `create_summary()` | 2-5 сек | Запрос к Yandex GPT |
| `compress_history()` | 2-5 сек | Включая создание резюме |

### Использование памяти

- **DialogHistory**: ~1-5 КБ на пользователя (зависит от длины сообщений)
- **После компрессии**: ~0.5-2 КБ (резюме + последние N сообщений)
- **Словарь всех историй**: зависит от количества активных пользователей

### Оптимизации

1. **Ленивая инициализация**: История создаётся только при первом сообщении
2. **Подсчёт токенов**: Кэшируется в TokenCounter для повторных запросов
3. **Низкая температура**: 0.3 для стабильных и быстрых ответов от LLM

## Ограничения текущей реализации

### 1. Хранение в памяти

**Проблема**: Истории хранятся в памяти процесса, теряются при перезапуске.

**Решение (будущее)**:
- Сохранение в SQLite/Redis
- Периодическая сериализация на диск
- Миграция на базу данных для продакшена

### 2. Отсутствие персистентности

**Проблема**: При перезапуске бота все истории удаляются.

**Решение (будущее)**:
- Автоматическое сохранение при изменении
- Восстановление при старте бота
- Механизм миграции старых данных

### 3. Однопоточность

**Проблема**: Компрессия блокирует обработку других запросов пользователя.

**Решение (будущее)**:
- Асинхронная очередь компрессий
- Background workers для обработки
- Приоритизация запросов

### 4. Отсутствие версионирования

**Проблема**: Невозможно откатить компрессию или посмотреть оригинальные сообщения.

**Решение (будущее)**:
- Хранение истории версий
- Механизм отката
- Архивирование старых диалогов

## Диаграммы

### Диаграмма классов

```
┌─────────────────────┐
│   TelegramBot       │
├─────────────────────┤
│ + user_histories    │◄───┐
│ + dialog_compressor │    │
├─────────────────────┤    │
│ + handle_message()  │    │ 1
│ + compact_command() │    │
└─────────┬───────────┘    │
          │                │
          │ uses           │
          ▼                │
┌─────────────────────┐    │ *
│ DialogCompressor    │    │
├─────────────────────┤    │
│ + token_counter     │    │
│ + gpt_client        │    │
├─────────────────────┤    │
│ + should_compress() │    │
│ + compress_history()│    │
│ + create_summary()  │    │
└─────────┬───────────┘    │
          │                │
          │ manages        │
          ▼                │
┌─────────────────────┐    │
│   DialogHistory     │────┘
├─────────────────────┤
│ + messages          │
│ + system_prompt     │
│ + compressed_context│
├─────────────────────┤
│ + add_message()     │
│ + get_message_count│
│ + clear_messages()  │
└─────────────────────┘
```

### Диаграмма состояний истории

```
┌─────────────┐
│  Пустая     │
│  история    │
└──────┬──────┘
       │ add_message()
       ▼
┌─────────────┐
│  Активная   │
│  история    │◄────┐
│  (< 50 msg) │     │
└──────┬──────┘     │
       │            │
       │ 50 msg     │ add_message()
       │ or 85%     │
       ▼            │
┌─────────────┐     │
│ Триггер     │     │
│ компрессии  │     │
└──────┬──────┘     │
       │            │
       ▼            │
┌─────────────┐     │
│ Сжатая      │     │
│ история     │─────┘
│ (резюме +   │
│  10 msg)    │
└─────────────┘
       │
       │ /compact
       ▼
┌─────────────┐
│ Полностью   │
│ сжатая      │
│ (только     │
│  резюме)    │
└─────────────┘
```

## См. также

- [Механизм компрессии](../features/dialog_compression.md)
- [API модуля компрессии](../api/compression_module.md)
- [Конфигурация](../../config.py)
- [Основной код бота](../../bot.py)
