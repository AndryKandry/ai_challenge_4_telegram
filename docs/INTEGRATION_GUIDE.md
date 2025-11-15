# Руководство по интеграции системы памяти

## Введение

Это руководство поможет интегрировать систему долговременной памяти в ваш Telegram-бот с Yandex GPT.

---

## Быстрый старт

### Шаг 1: Установка зависимостей

Система памяти использует только стандартную библиотеку Python - дополнительных зависимостей не требуется.

### Шаг 2: Добавление файлов

1. Скопируйте директорию `database/` в корень вашего проекта
2. Убедитесь, что структура выглядит так:

```
your_project/
├── database/
│   ├── __init__.py
│   ├── memory_manager.py
│   └── schema.sql
└── bot.py
```

### Шаг 3: Импорт и инициализация

В вашем основном файле бота:

```python
from database import MemoryManager

class TelegramBot:
    def __init__(self, telegram_token: str, yandex_api_key: str):
        # ... ваш существующий код ...

        # Добавьте менеджер памяти
        self.memory = MemoryManager("agent_memory.db")
        self.memory.create_tables()
        logger.info("Система памяти инициализирована")
```

### Шаг 4: Сохранение сообщений

В обработчике сообщений:

```python
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # 1. Получить или создать сессию
    session_id = self.memory.get_active_session(user_id, chat_id)
    if not session_id:
        session_id = self.memory.create_session(user_id, chat_id)

    # 2. Сохранить сообщение пользователя
    self.memory.save_message(user_id, chat_id, user_message, "user", session_id)

    # 3. Получить ответ от GPT
    response = await self.gpt_client.send_message(user_message, system_prompt)

    # 4. Сохранить ответ ассистента
    self.memory.save_message(user_id, chat_id, response, "assistant", session_id)

    # 5. Отправить ответ пользователю
    await update.message.reply_text(response)
```

---

## Расширенная интеграция

### Использование истории диалога

Загрузите историю для передачи контекста в GPT:

```python
# Получить последние 5 сообщений
history = self.memory.get_conversation_history(user_id, chat_id, limit=5)

# Сформировать контекст для GPT
context_messages = []
for msg in history:
    role = "user" if msg["message_type"] == "user" else "assistant"
    context_messages.append({
        "role": role,
        "text": msg["message_text"]
    })

# Добавить новое сообщение
context_messages.append({"role": "user", "text": user_message})

# Отправить в GPT с контекстом
response = await self.gpt_client.send_message_with_history(context_messages)
```

### Логирование действий

Отслеживайте производительность и ошибки:

```python
import time

start_time = time.time()

try:
    response = await self.gpt_client.send_message(user_message)
    execution_time = int((time.time() - start_time) * 1000)

    self.memory.save_action(
        user_id=user_id,
        chat_id=chat_id,
        action_type="gpt_request",
        description="Успешный запрос к Yandex GPT",
        input_data={"message_length": len(user_message)},
        output_data={"response_length": len(response)},
        execution_time=execution_time
    )
except Exception as e:
    execution_time = int((time.time() - start_time) * 1000)

    self.memory.save_action(
        user_id=user_id,
        chat_id=chat_id,
        action_type="gpt_request_error",
        description=f"Ошибка: {str(e)}",
        execution_time=execution_time
    )
    raise
```

### Сохранение извлечённых данных

Извлекайте и сохраняйте информацию о пользователе:

```python
# Пример извлечения имени из сообщения
import re

message = "Меня зовут Иван"
name_match = re.search(r"зовут\s+(\w+)", message, re.IGNORECASE)

if name_match:
    name = name_match.group(1)
    self.memory.save_knowledge(
        user_id=user_id,
        entity_type="name",
        key="first_name",
        value=name,
        confidence=0.9,
        source_message_id=message_id
    )
```

---

## Добавление команд управления памятью

### Команда /memory_stats

```python
async def memory_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = self.memory.get_statistics(user_id=user_id)

    message = (
        f"📊 Статистика памяти:\n\n"
        f"💬 Сообщений: {stats.get('messages_count', 0)}\n"
        f"🧠 Фактов: {stats.get('knowledge_count', 0)}\n"
    )

    await update.message.reply_text(message)

# Регистрация команды
self.application.add_handler(CommandHandler("memory_stats", self.memory_stats_command))
```

### Команда /clear_memory

```python
async def clear_memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Проверка подтверждения
    if context.args and context.args[0].lower() == 'confirm':
        success = self.memory.clear_user_history(user_id, chat_id)

        if success:
            message = "✅ История успешно очищена!"
        else:
            message = "❌ Ошибка при очистке истории"
    else:
        message = (
            "⚠️ Для подтверждения используйте:\n"
            "/clear_memory confirm"
        )

    await update.message.reply_text(message)

# Регистрация команды
self.application.add_handler(CommandHandler("clear_memory", self.clear_memory_command))
```

### Команда /export_memory

```python
async def export_memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Определить формат
    export_format = 'json'
    if context.args and context.args[0].lower() in ['json', 'text', 'csv']:
        export_format = context.args[0].lower()

    # Экспортировать
    data = self.memory.export_conversation_history(user_id, chat_id, format=export_format)

    if not data:
        await update.message.reply_text("📭 История пуста")
        return

    # Если данные большие - отправить как файл
    if len(data) > 4000:
        from io import BytesIO
        file = BytesIO(data.encode('utf-8'))
        file.name = f"history.{export_format}"

        await update.message.reply_document(
            document=file,
            filename=file.name,
            caption=f"📄 Экспорт истории ({export_format.upper()})"
        )
    else:
        await update.message.reply_text(data)

# Регистрация команды
self.application.add_handler(CommandHandler("export_memory", self.export_memory_command))
```

---

## Автоматическая очистка данных

Добавьте периодическую очистку старых данных:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def setup_cleanup():
    scheduler = AsyncIOScheduler()

    def cleanup_job():
        deleted = memory.cleanup_old_data(days=30)
        logger.info(f"Очищено записей: {sum(deleted.values())}")

    # Запускать каждые 24 часа
    scheduler.add_job(cleanup_job, 'interval', hours=24)
    scheduler.start()

# В main()
memory = MemoryManager()
memory.create_tables()
setup_cleanup()
```

---

## Best Practices

### 1. Обработка ошибок

Всегда оборачивайте вызовы в try-except:

```python
try:
    self.memory.save_message(user_id, chat_id, message, "user")
except Exception as e:
    logger.error(f"Ошибка сохранения сообщения: {e}")
    # Бот продолжает работать, даже если сохранение не удалось
```

### 2. Ограничение размера контекста

Не загружайте слишком много сообщений в контекст:

```python
# Хорошо: ограничение до 10 сообщений
history = memory.get_conversation_history(user_id, chat_id, limit=10)

# Плохо: загрузка всей истории
history = memory.get_conversation_history(user_id, chat_id, limit=10000)
```

### 3. Использование сессий

Создавайте новую сессию при смене темы:

```python
if "/new_topic" in user_message:
    # Завершить текущую сессию
    active_session = memory.get_active_session(user_id, chat_id)
    if active_session:
        memory.end_session(active_session)

    # Создать новую
    new_session = memory.create_session(user_id, chat_id)
```

### 4. Мониторинг производительности

Логируйте время выполнения операций:

```python
import time

start = time.time()
history = memory.get_conversation_history(user_id, chat_id)
duration = (time.time() - start) * 1000

if duration > 100:  # Больше 100ms
    logger.warning(f"Медленная загрузка истории: {duration:.2f}ms")
```

---

## Тестирование интеграции

Создайте тесты для проверки интеграции:

```python
import unittest

class TestBotMemoryIntegration(unittest.TestCase):
    def setUp(self):
        self.memory = MemoryManager("test.db")
        self.memory.create_tables()

    def tearDown(self):
        os.remove("test.db")

    def test_conversation_flow(self):
        # Создать сессию
        session_id = self.memory.create_session(123, 456)

        # Сохранить диалог
        self.memory.save_message(123, 456, "Привет", "user", session_id)
        self.memory.save_message(123, 456, "Здравствуйте!", "assistant", session_id)

        # Проверить историю
        history = self.memory.get_conversation_history(123, 456)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["message_type"], "user")
        self.assertEqual(history[1]["message_type"], "assistant")
```

---

## Миграция с существующей системы

Если у вас уже есть система хранения диалогов:

```python
def migrate_old_conversations(old_db_path, new_memory):
    """Миграция из старой БД в новую систему памяти."""
    import sqlite3

    old_conn = sqlite3.connect(old_db_path)
    cursor = old_conn.execute("SELECT * FROM old_messages")

    for row in cursor:
        new_memory.save_message(
            user_id=row['user_id'],
            chat_id=row['chat_id'],
            message=row['text'],
            message_type=row['role']
        )

    old_conn.close()
    print("Миграция завершена")
```

---

## Troubleshooting

### Проблема: "Database is locked"

**Решение:** MemoryManager уже использует блокировки. Убедитесь, что не создаете несколько экземпляров.

```python
# Хорошо: один экземпляр
memory = MemoryManager()

# Плохо: несколько экземпляров
memory1 = MemoryManager()
memory2 = MemoryManager()  # Может вызвать блокировки
```

### Проблема: База данных быстро растёт

**Решение:** Настройте автоматическую очистку:

```python
# Очищать данные старше 7 дней
memory.cleanup_old_data(days=7)
```

### Проблема: Медленные запросы

**Решение:** Проверьте индексы:

```python
import sqlite3
conn = sqlite3.connect("agent_memory.db")
cursor = conn.execute("SELECT * FROM sqlite_master WHERE type='index'")
print([row[1] for row in cursor])  # Должно показать все индексы
```

---

## См. также

- [MEMORY_MANAGER_API.md](MEMORY_MANAGER_API.md) - Полная документация API
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Схема базы данных
- [MEMORY_ARCHITECTURE.md](MEMORY_ARCHITECTURE.md) - Архитектура системы
