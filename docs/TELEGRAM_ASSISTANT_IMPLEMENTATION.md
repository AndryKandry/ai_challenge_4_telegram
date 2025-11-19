# Система автоматических сводок из Telegram чатов

## Обзор

Реализована система автоматического мониторинга Telegram чатов с периодической генерацией аналитических сводок через DeepSeek LLM.

## Архитектура

```
┌─────────────┐
│ Telegram Bot │ ← Команды пользователя
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Scheduler Manager │ ← Управление задачами
└─────┬────────────┘
      │
      ├──→ APScheduler (планирование)
      ├──→ Storage (БД SQLite)
      └──→ Tasks (выполнение)
             │
             ▼
       ┌────────────┐
       │ DeepSeek LLM│
       └─────┬──────┘
             │
             ▼ (MCP call)
       ┌──────────────────────┐
       │ telegram_assistant MCP│
       └─────┬────────────────┘
             │
             ▼
       ┌──────────────┐
       │ Telegram API  │ (Pyrogram)
       └──────────────┘
```

## Компоненты

### 1. Storage Layer (`storage/`)

**Файлы:**
- `models.py` - Dataclasses для Assistant, ExecutionHistory, ChatMetadata
- `database.py` - CRUD операции с SQLite
- `migrations/001_initial_schema.sql` - Схема БД

**Таблицы:**
- `assistants` - конфигурации ассистентов
- `execution_history` - история выполнения задач
- `chat_metadata` - метаданные чатов

### 2. MCP Server (`mcp_server/telegram_assistant.py`)

**Инструменты для LLM:**
- `get_chat_messages(chat_id, from_date, to_date, limit)` - получение сообщений из чата
- `get_chat_info(chat_id)` - информация о чате
- `validate_chat_access(chat_id)` - проверка доступа

**Технологии:**
- FastMCP для создания MCP сервера
- Pyrogram для работы с Telegram API
- SSE транспорт (порт 8002)

### 3. Scheduler (`scheduler/`)

**Файлы:**
- `config.py` - конфигурация APScheduler
- `manager.py` - SchedulerManager (управление ассистентами)
- `tasks.py` - execute_task() (логика выполнения)

**Возможности:**
- Создание/остановка ассистентов
- Планирование задач (minute/hour/day/custom)
- Восстановление после перезапуска
- Персистентность в SQLite

## Команды бота (Планируются)

```
/telegram_assistant <chat_name> - Создать ассистента
/stop_assistant <chat_name>     - Остановить ассистента
/stop_all_assistants            - Остановить все
/list_assistants                - Список ассистентов
```

## Настройка

### Переменные окружения

Добавьте в `.env`:

```bash
# Telegram API (обязательно для MCP и ассистентов)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# DeepSeek (используется как LLM)
DEEPSEEK_API_KEY=your_deepseek_key

# Database paths
DATABASE_URL=data/assistants.db
SCHEDULER_DB_URL=data/scheduler_jobs.db

# Scheduler settings
SCHEDULER_TIMEZONE=UTC
MAX_ASSISTANTS_PER_USER=10
MIN_INTERVAL_MINUTES=1
```

### Установка зависимостей

```bash
pip install -r requirements.txt
```

**Новые зависимости:**
- `apscheduler==3.10.4` - планирование задач
- `pyrogram==2.0.106` - Telegram User Bot API
- `tgcrypto==1.2.5` - шифрование для Pyrogram
- `tenacity==8.2.3` - retry логика
- `aiosqlite==0.19.0` - асинхронная работа с SQLite

### Получение Telegram API credentials

1. Перейдите на https://my.telegram.org/apps
2. Создайте приложение
3. Скопируйте `api_id` и `api_hash`
4. Добавьте в `.env`

## Использование

### Пример: Создание ассистента

```python
from scheduler import SchedulerManager
from storage import Database
from providers import DeepSeekProvider

# Инициализация
db = Database("data/assistants.db")
db.create_tables()

deepseek = DeepSeekProvider(api_key, mcp_client)
manager = SchedulerManager(db, deepseek, bot_instance)

# Запуск планировщика
manager.start()

# Создание ассистента
success, message, assistant = await manager.create_assistant(
    user_id=123456,
    chat_id="@work_updates",
    chat_name="work_updates",
    interval_type="hour",
    interval_value=1,
    custom_prompt="Выдели главные новости"
)

# Восстановление после перезапуска
await manager.restore_assistants()
```

### Пример: Запуск MCP сервера

```bash
# SSE транспорт (по умолчанию, порт 8002)
python mcp_server/telegram_assistant.py

# STDIO транспорт
python mcp_server/telegram_assistant.py --stdio
```

## Процесс работы

1. **Создание ассистента:**
   - Пользователь → `/telegram_assistant work_chat`
   - Бот → интерактивная настройка (интервал, время, промпт)
   - SchedulerManager → создание записи в БД
   - APScheduler → добавление задачи

2. **Выполнение задачи (по расписанию):**
   - APScheduler → вызов `execute_task(assistant_id)`
   - `execute_task()` → формирование промпта для LLM
   - DeepSeek → получение промпта
   - DeepSeek → вызов MCP tool `get_chat_messages`
   - MCP Server → запрос к Telegram API (Pyrogram)
   - Telegram API → возврат сообщений
   - DeepSeek → анализ сообщений, генерация сводки
   - `execute_task()` → отправка сводки пользователю
   - Database → сохранение в execution_history

3. **Остановка ассистента:**
   - Пользователь → `/stop_assistant work_chat`
   - SchedulerManager → удаление задачи из APScheduler
   - Database → обновление статуса на 'stopped'

## Ограничения

- Максимум 10 активных ассистентов на пользователя
- Минимальный интервал: 1 минута
- Максимум 1000 сообщений за один сбор
- История хранится 30 дней (настраивается)

## Обработка ошибок

- **Telegram API недоступен** → Retry с экспоненциальной задержкой
- **Нет доступа к чату** → Ассистент останавливается, уведомление пользователю
- **LLM timeout** → Повторная попытка (до 2 раз)
- **Дублирование задач** → APScheduler предотвращает (max_instances=1)

## Статус реализации

✅ **Готово:**
- Storage Layer (models, database, migrations)
- MCP Server telegram_assistant
- Scheduler Manager (config, manager, tasks)
- Requirements обновлены
- .env.example обновлён

⏳ **В разработке:**
- Интеграция команд бота
- Интерактивная настройка параметров
- Тестирование

📝 **Планируется:**
- Веб-интерфейс управления
- Экспорт сводок
- Расширенная аналитика

## Следующие шаги

1. Добавить команды бота в `bot.py`
2. Создать обработчики команд с FSM (Finite State Machine)
3. Интегрировать SchedulerManager при запуске бота
4. Настроить MCP клиент для DeepSeek провайдера
5. Протестировать полный цикл работы
6. Написать тесты

## Поддержка

Для вопросов и багов создавайте issues в репозитории проекта.

---

**Дата создания:** 19.11.2025
**Версия:** 1.0
**LLM:** DeepSeek (используется как основной провайдер)
