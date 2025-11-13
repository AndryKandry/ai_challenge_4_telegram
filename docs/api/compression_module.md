# API модуля компрессии

## Обзор

Модуль компрессии предоставляет два основных класса для управления историей диалога и её сжатия:

- **DialogHistory** - Хранение и управление историей сообщений
- **DialogCompressor** - Выполнение компрессии истории

## DialogHistory

### Описание

Класс для хранения истории диалога пользователя, включая сообщения, системный промпт и сжатый контекст.

### Конструктор

```python
def __init__(self) -> None
```

Создаёт пустую историю диалога.

**Пример:**
```python
history = DialogHistory()
```

### Атрибуты

#### messages

```python
messages: List[Dict[str, str]]
```

Список сообщений в истории. Каждое сообщение имеет структуру:

```python
{
    "role": "user" | "assistant",
    "text": str
}
```

#### system_prompt

```python
system_prompt: Optional[str]
```

Системный промпт для данной истории. Устанавливается автоматически при первом сообщении.

#### compressed_context

```python
compressed_context: Optional[str]
```

Сжатый контекст (резюме предыдущих сообщений). Создаётся при компрессии.

### Методы

#### add_message

```python
def add_message(self, role: str, text: str) -> None
```

Добавить сообщение в историю.

**Параметры:**
- `role` (str): Роль отправителя - `"user"` или `"assistant"`
- `text` (str): Текст сообщения

**Пример:**
```python
history.add_message("user", "Привет, как дела?")
history.add_message("assistant", "Здравствуйте! Отлично, спасибо!")
```

#### set_system_prompt

```python
def set_system_prompt(self, prompt: str) -> None
```

Установить системный промпт для истории.

**Параметры:**
- `prompt` (str): Текст системного промпта

**Пример:**
```python
history.set_system_prompt("Ты — помощник в Telegram. Отвечай на русском языке.")
```

#### set_compressed_context

```python
def set_compressed_context(self, context: str) -> None
```

Установить сжатый контекст (резюме).

**Параметры:**
- `context` (str): Сжатый контекст

**Пример:**
```python
compressed = """[COMPRESSED CONTEXT]
Резюме предыдущего диалога:
- Пользователь: разработчик
- Задача: создание бота
[/COMPRESSED CONTEXT]"""

history.set_compressed_context(compressed)
```

#### get_message_count

```python
def get_message_count(self) -> int
```

Получить количество сообщений в истории.

**Возвращает:**
- `int`: Количество сообщений

**Пример:**
```python
count = history.get_message_count()
print(f"В истории {count} сообщений")
```

#### get_last_n_messages

```python
def get_last_n_messages(self, n: int) -> List[Dict[str, str]]
```

Получить последние N сообщений из истории.

**Параметры:**
- `n` (int): Количество последних сообщений

**Возвращает:**
- `List[Dict[str, str]]`: Список последних N сообщений

**Пример:**
```python
last_10 = history.get_last_n_messages(10)
for msg in last_10:
    print(f"{msg['role']}: {msg['text'][:50]}...")
```

#### get_messages_to_compress

```python
def get_messages_to_compress(self, keep_last_n: int) -> List[Dict[str, str]]
```

Получить сообщения, которые будут сжаты (все кроме последних N).

**Параметры:**
- `keep_last_n` (int): Количество последних сообщений для сохранения

**Возвращает:**
- `List[Dict[str, str]]`: Сообщения для компрессии

**Пример:**
```python
# Получить все сообщения кроме последних 10
to_compress = history.get_messages_to_compress(10)
```

#### clear_compressed_messages

```python
def clear_compressed_messages(self, keep_last_n: int) -> None
```

Удалить сжатые сообщения из истории, сохранив последние N.

**Параметры:**
- `keep_last_n` (int): Количество последних сообщений для сохранения

**Пример:**
```python
# Удалить все сообщения кроме последних 10
history.clear_compressed_messages(10)
```

---

## DialogCompressor

### Описание

Класс для выполнения компрессии истории диалога с использованием Yandex GPT.

### Конструктор

```python
def __init__(
    self,
    yandex_api_key: str,
    token_counter: TokenCounter,
    config: Optional[Dict] = None
) -> None
```

Создаёт экземпляр компрессора диалога.

**Параметры:**
- `yandex_api_key` (str): API ключ Yandex Cloud
- `token_counter` (TokenCounter): Экземпляр счётчика токенов
- `config` (Optional[Dict]): Конфигурация компрессии. Если None, загружается из config.py

**Пример:**
```python
from token_counter import TokenCounter

token_counter = TokenCounter(yandex_api_key)
compressor = DialogCompressor(yandex_api_key, token_counter)
```

**С кастомной конфигурацией:**
```python
custom_config = {
    "enabled": True,
    "auto_compress": True,
    "max_messages": 30,  # Компрессия при 30 сообщениях
    "max_tokens_percent": 0.80,  # 80% от лимита
    "keep_recent_messages": 5,  # Сохранять 5 последних
    "compression_ratio_target": 0.15,  # 15% от исходного
}

compressor = DialogCompressor(yandex_api_key, token_counter, custom_config)
```

### Методы

#### should_compress

```python
def should_compress(self, history: DialogHistory) -> Tuple[bool, str]
```

Проверить, нужна ли компрессия истории.

**Параметры:**
- `history` (DialogHistory): История диалога для проверки

**Возвращает:**
- `Tuple[bool, str]`:
  - `bool`: True если нужна компрессия
  - `str`: Причина (например, "Message count exceeded: 50 messages")

**Пример:**
```python
should_compress, reason = compressor.should_compress(history)

if should_compress:
    print(f"Компрессия нужна: {reason}")
else:
    print(f"Компрессия не нужна: {reason}")
```

**Условия срабатывания:**
1. Количество сообщений >= `config["max_messages"]` (по умолчанию 50)
2. Использование токенов >= `config["max_tokens_percent"]` (по умолчанию 85%)

#### compress_history

```python
async def compress_history(
    self,
    history: DialogHistory,
    keep_last_n: Optional[int] = None
) -> Tuple[bool, str, Dict[str, int]]
```

Выполнить компрессию истории диалога.

**Параметры:**
- `history` (DialogHistory): История для сжатия
- `keep_last_n` (Optional[int]): Количество последних сообщений для сохранения. Если None, используется значение из конфига

**Возвращает:**
- `Tuple[bool, str, Dict[str, int]]`:
  - `bool`: True если компрессия успешна
  - `str`: Сжатый контекст (при успехе) или сообщение об ошибке
  - `Dict[str, int]`: Статистика компрессии

**Статистика:**
```python
{
    "tokens_before": int,        # Токенов до компрессии
    "tokens_after": int,          # Токенов после компрессии
    "savings": int,               # Процент экономии
    "messages_compressed": int,   # Сжато сообщений
    "messages_kept": int,         # Сохранено сообщений
}
```

**Пример (автокомпрессия):**
```python
# Сжать все кроме последних 10 (из конфига)
success, result, stats = await compressor.compress_history(history)

if success:
    print(f"Компрессия успешна!")
    print(f"Экономия: {stats['savings']}%")
    print(f"Токенов было: {stats['tokens_before']}")
    print(f"Токенов стало: {stats['tokens_after']}")
else:
    print(f"Ошибка: {result}")
```

**Пример (ручная компрессия `/compact`):**
```python
# Сжать ВСЕ сообщения
success, result, stats = await compressor.compress_history(history, keep_last_n=0)

if success:
    print(f"Все сообщения сжаты в резюме")
```

#### create_summary

```python
async def create_summary(self, history_text: str) -> Optional[str]
```

Создать резюме истории через Yandex GPT.

**Параметры:**
- `history_text` (str): Форматированная история для сжатия

**Возвращает:**
- `Optional[str]`: Резюме или None при ошибке

**Пример:**
```python
formatted_history = """
[Сообщение 1 - Пользователь]
Привет, как создать бота?

[Сообщение 2 - Ассистент]
Здравствуйте! Для создания бота...
"""

summary = await compressor.create_summary(formatted_history)

if summary:
    print(f"Резюме: {summary}")
else:
    print("Не удалось создать резюме")
```

**Примечание**: Обычно этот метод не вызывается напрямую, используется внутри `compress_history()`.

#### extract_key_facts

```python
def extract_key_facts(self, summary: str) -> Dict[str, str]
```

Извлечь ключевые факты из резюме.

**Параметры:**
- `summary` (str): Текст резюме

**Возвращает:**
- `Dict[str, str]`: Словарь с ключевыми фактами

**Структура результата:**
```python
{
    "user": str,         # Описание пользователя
    "task": str,         # Основная задача
    "completed": str,    # Выполненное
    "in_progress": str,  # В работе
    "decisions": str,    # Ключевые решения
    "context": str,      # Важный контекст
}
```

**Пример:**
```python
summary = """
- Пользователь: разработчик Python
- Задача: создание Telegram-бота
- Выполнено: базовая структура
- В работе: интеграция с API
- Ключевые решения: асинхронность
- Важный контекст: деплоймент на Heroku
"""

facts = compressor.extract_key_facts(summary)

print(f"Пользователь: {facts['user']}")
print(f"Задача: {facts['task']}")
```

#### get_compression_stats_message

```python
def get_compression_stats_message(self, stats: Dict[str, int]) -> str
```

Форматировать сообщение со статистикой компрессии для пользователя.

**Параметры:**
- `stats` (Dict[str, int]): Статистика компрессии

**Возвращает:**
- `str`: Форматированное сообщение

**Пример:**
```python
stats = {
    "tokens_before": 12450,
    "tokens_after": 2890,
    "savings": 77,
    "messages_compressed": 45,
    "messages_kept": 0,
}

message = compressor.get_compression_stats_message(stats)
print(message)
```

**Результат:**
```
🗜️ Компрессия истории завершена

📊 Статистика:
├─ Сжато сообщений: 45
├─ Сохранено последних: 0
├─ Токенов до: 12,450
├─ Токенов после: 2,890
└─ Экономия: 77%

✅ История диалога оптимизирована для экономии токенов!
```

---

## Полные примеры использования

### Пример 1: Базовая работа с историей

```python
from dialog_compressor import DialogHistory, DialogCompressor
from token_counter import TokenCounter

# Создание истории
history = DialogHistory()
history.set_system_prompt("Ты — помощник в Telegram")

# Добавление сообщений
history.add_message("user", "Привет!")
history.add_message("assistant", "Здравствуйте! Чем могу помочь?")
history.add_message("user", "Расскажи про Python")
history.add_message("assistant", "Python - это высокоуровневый язык...")

# Проверка количества
print(f"Сообщений в истории: {history.get_message_count()}")

# Получение последних 2
last_two = history.get_last_n_messages(2)
for msg in last_two:
    print(f"{msg['role']}: {msg['text']}")
```

### Пример 2: Автоматическая компрессия

```python
import asyncio
from dialog_compressor import DialogHistory, DialogCompressor
from token_counter import TokenCounter

async def auto_compress_example():
    # Инициализация
    api_key = "your_yandex_api_key"
    token_counter = TokenCounter(api_key)
    compressor = DialogCompressor(api_key, token_counter)

    # Создание истории с множеством сообщений
    history = DialogHistory()
    history.set_system_prompt("Ты — помощник")

    # Добавим 60 сообщений
    for i in range(60):
        history.add_message("user", f"Вопрос номер {i}")
        history.add_message("assistant", f"Ответ на вопрос {i}")

    # Проверка необходимости компрессии
    should_compress, reason = compressor.should_compress(history)
    print(f"Нужна компрессия: {should_compress}")
    print(f"Причина: {reason}")

    if should_compress:
        # Автокомпрессия (сохраняем последние 10)
        success, result, stats = await compressor.compress_history(history)

        if success:
            print("\n✅ Автокомпрессия выполнена!")
            print(f"Экономия: {stats['savings']}%")
            print(f"Сообщений осталось: {history.get_message_count()}")
        else:
            print(f"\n❌ Ошибка: {result}")

# Запуск
asyncio.run(auto_compress_example())
```

### Пример 3: Ручная компрессия `/compact`

```python
import asyncio
from dialog_compressor import DialogHistory, DialogCompressor
from token_counter import TokenCounter

async def manual_compress_example():
    # Инициализация
    api_key = "your_yandex_api_key"
    token_counter = TokenCounter(api_key)
    compressor = DialogCompressor(api_key, token_counter)

    # Создание истории
    history = DialogHistory()
    history.set_system_prompt("Ты — помощник")

    # Добавляем 20 сообщений
    for i in range(20):
        history.add_message("user", f"Сообщение {i}")
        history.add_message("assistant", f"Ответ {i}")

    print(f"Сообщений до компрессии: {history.get_message_count()}")

    # Ручная компрессия ВСЕХ сообщений
    success, result, stats = await compressor.compress_history(
        history,
        keep_last_n=0  # Сжать ВСЕ!
    )

    if success:
        print("\n✅ Ручная компрессия выполнена!")
        print(f"Сообщений после: {history.get_message_count()}")
        print(f"Есть резюме: {history.compressed_context is not None}")

        # Показать статистику
        message = compressor.get_compression_stats_message(stats)
        print("\n" + message)
    else:
        print(f"\n❌ Ошибка: {result}")

# Запуск
asyncio.run(manual_compress_example())
```

### Пример 4: Кастомная конфигурация

```python
from dialog_compressor import DialogCompressor
from token_counter import TokenCounter

# Агрессивная компрессия (для экономии токенов)
aggressive_config = {
    "enabled": True,
    "auto_compress": True,
    "max_messages": 20,  # Компрессия при 20 сообщениях
    "max_tokens_percent": 0.60,  # 60% от лимита
    "keep_recent_messages": 3,  # Сохранять только 3 последних
    "compression_ratio_target": 0.10,  # Цель: 10% от исходного
}

api_key = "your_api_key"
token_counter = TokenCounter(api_key)

compressor = DialogCompressor(
    api_key,
    token_counter,
    config=aggressive_config
)

# Теперь компрессия будет срабатывать чаще
```

---

## Обработка ошибок

### Проверка перед компрессией

```python
# Проверить минимальное количество сообщений
if history.get_message_count() < 2:
    print("Недостаточно сообщений для компрессии")
    return

# Проверить необходимость компрессии
should_compress, reason = compressor.should_compress(history)
if not should_compress:
    print(f"Компрессия не требуется: {reason}")
    return
```

### Обработка ошибок компрессии

```python
try:
    success, result, stats = await compressor.compress_history(history)

    if success:
        # Обработка успешной компрессии
        print(f"✅ Успех: {stats['savings']}% экономии")
    else:
        # Обработка неудачной компрессии
        print(f"❌ Компрессия не удалась: {result}")

except Exception as e:
    # Обработка непредвиденных ошибок
    print(f"⚠️ Непредвиденная ошибка: {e}")
    # История остаётся без изменений
```

---

## Константы и конфигурация

### Значения по умолчанию

```python
# Из config.py
COMPRESSION_ENABLED = True
COMPRESSION_AUTO_COMPRESS = True
COMPRESSION_MAX_MESSAGES = 50
COMPRESSION_MAX_TOKENS_PERCENT = 0.85  # 85%
COMPRESSION_KEEP_RECENT_MESSAGES = 10
COMPRESSION_RATIO_TARGET = 0.2  # 20%
COMPRESSION_PROMPT_PATH = "prompts/compression_summary.txt"
```

### Настройки Yandex GPT для компрессии

```python
# Внутри create_summary()
TEMPERATURE = 0.3  # Низкая для стабильности
MAX_TOKENS = 2000  # Для резюме
TIMEOUT = 30  # секунд
```

---

## См. также

- [Механизм компрессии](../features/dialog_compression.md)
- [Архитектура управления контекстом](../architecture/context_management.md)
- [Конфигурация системы](../../config.py)
- [Исходный код модуля](../../dialog_compressor.py)
