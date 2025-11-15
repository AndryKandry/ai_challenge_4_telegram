# Схема базы данных системы памяти

## Обзор

Система долговременной памяти использует SQLite базу данных для хранения:
- Истории диалогов
- Промежуточных результатов работы агента
- Логов действий агента
- Базы знаний о пользователях
- Метаданных сессий

База данных создается автоматически при первом запуске бота и хранится в файле `agent_memory.db`.

---

## Таблицы

### 1. conversations

**Назначение:** Хранение истории сообщений между пользователями и ассистентом.

**Структура:**

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `id` | INTEGER | Уникальный идентификатор сообщения | PRIMARY KEY, AUTOINCREMENT |
| `user_id` | INTEGER | ID пользователя Telegram | NOT NULL |
| `chat_id` | INTEGER | ID чата Telegram | NOT NULL |
| `message_text` | TEXT | Текст сообщения | NOT NULL |
| `message_type` | TEXT | Тип сообщения | NOT NULL, CHECK('user' или 'assistant') |
| `timestamp` | DATETIME | Временная метка | DEFAULT CURRENT_TIMESTAMP |
| `session_id` | TEXT | ID сессии | FOREIGN KEY → sessions(session_id) |

**Индексы:**
- `idx_conversations_user_chat` - по (user_id, chat_id, timestamp DESC) для быстрого получения истории
- `idx_conversations_session` - по session_id для запросов по сессиям

**Примеры использования:**

```sql
-- Получить последние 10 сообщений пользователя
SELECT * FROM conversations
WHERE user_id = 12345 AND chat_id = 67890
ORDER BY timestamp DESC
LIMIT 10;

-- Получить все сообщения в рамках сессии
SELECT * FROM conversations
WHERE session_id = 'uuid-here'
ORDER BY timestamp ASC;
```

---

### 2. intermediate_results

**Назначение:** Хранение промежуточных результатов и вычислений агента.

**Структура:**

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `id` | INTEGER | Уникальный идентификатор результата | PRIMARY KEY, AUTOINCREMENT |
| `user_id` | INTEGER | ID пользователя Telegram | NOT NULL |
| `chat_id` | INTEGER | ID чата Telegram | NOT NULL |
| `task_name` | TEXT | Название задачи | NOT NULL |
| `result_data` | TEXT | Данные результата (JSON) | NOT NULL |
| `status` | TEXT | Статус выполнения | DEFAULT 'pending', CHECK('pending', 'completed', 'failed') |
| `created_at` | DATETIME | Дата создания | DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | Дата обновления | DEFAULT CURRENT_TIMESTAMP |

**Индексы:**
- `idx_intermediate_user_chat_task` - по (user_id, chat_id, task_name)
- `idx_intermediate_status` - по (status, updated_at DESC)

**Триггеры:**
- `update_intermediate_timestamp` - автоматически обновляет `updated_at` при изменении записи

**Примеры использования:**

```sql
-- Сохранить промежуточный результат
INSERT INTO intermediate_results (user_id, chat_id, task_name, result_data, status)
VALUES (12345, 67890, 'parsing_task', '{"parsed": true}', 'completed');

-- Получить все незавершенные задачи
SELECT * FROM intermediate_results
WHERE status = 'pending'
ORDER BY created_at ASC;
```

---

### 3. agent_actions

**Назначение:** Логирование всех действий агента для отладки и аналитики.

**Структура:**

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `id` | INTEGER | Уникальный идентификатор действия | PRIMARY KEY, AUTOINCREMENT |
| `user_id` | INTEGER | ID пользователя Telegram | NOT NULL |
| `chat_id` | INTEGER | ID чата Telegram | NOT NULL |
| `action_type` | TEXT | Тип действия (например, 'api_call', 'parsing') | NOT NULL |
| `action_description` | TEXT | Описание действия | NULL |
| `input_data` | TEXT | Входные данные (JSON) | NULL |
| `output_data` | TEXT | Выходные данные (JSON) | NULL |
| `timestamp` | DATETIME | Временная метка | DEFAULT CURRENT_TIMESTAMP |
| `execution_time_ms` | INTEGER | Время выполнения в миллисекундах | NULL |

**Индексы:**
- `idx_actions_user_chat_time` - по (user_id, chat_id, timestamp DESC)
- `idx_actions_type` - по (action_type, timestamp DESC)

**Примеры использования:**

```sql
-- Сохранить действие агента
INSERT INTO agent_actions (user_id, chat_id, action_type, action_description, execution_time_ms)
VALUES (12345, 67890, 'gpt_request', 'Запрос к Yandex GPT API', 1500);

-- Получить статистику по типам действий
SELECT action_type, COUNT(*) as count, AVG(execution_time_ms) as avg_time
FROM agent_actions
GROUP BY action_type;
```

---

### 4. knowledge_base

**Назначение:** Хранение извлечённых сущностей, фактов и предпочтений пользователя.

**Структура:**

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `id` | INTEGER | Уникальный идентификатор факта | PRIMARY KEY, AUTOINCREMENT |
| `user_id` | INTEGER | ID пользователя Telegram | NOT NULL |
| `entity_type` | TEXT | Тип сущности (например, 'preference', 'fact', 'name') | NOT NULL |
| `entity_key` | TEXT | Ключ сущности | NOT NULL |
| `entity_value` | TEXT | Значение сущности | NOT NULL |
| `confidence_score` | REAL | Уверенность в факте (0.0 - 1.0) | DEFAULT 1.0 |
| `source_message_id` | INTEGER | ID исходного сообщения | NULL |
| `created_at` | DATETIME | Дата создания | DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | Дата обновления | DEFAULT CURRENT_TIMESTAMP |

**Уникальные ограничения:**
- UNIQUE(user_id, entity_type, entity_key) ON CONFLICT REPLACE - автоматическое обновление при конфликте

**Индексы:**
- `idx_knowledge_user_type` - по (user_id, entity_type)
- `idx_knowledge_source` - по source_message_id

**Триггеры:**
- `update_knowledge_timestamp` - автоматически обновляет `updated_at` при изменении записи

**Примеры использования:**

```sql
-- Сохранить предпочтение пользователя
INSERT INTO knowledge_base (user_id, entity_type, entity_key, entity_value, confidence_score)
VALUES (12345, 'preference', 'favorite_color', 'blue', 0.95);

-- Получить все факты о пользователе
SELECT * FROM knowledge_base
WHERE user_id = 12345
ORDER BY updated_at DESC;
```

---

### 5. sessions

**Назначение:** Отслеживание пользовательских сессий для управления контекстом.

**Структура:**

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `session_id` | TEXT | Уникальный идентификатор сессии (UUID) | PRIMARY KEY |
| `user_id` | INTEGER | ID пользователя Telegram | NOT NULL |
| `chat_id` | INTEGER | ID чата Telegram | NOT NULL |
| `started_at` | DATETIME | Время начала сессии | DEFAULT CURRENT_TIMESTAMP |
| `ended_at` | DATETIME | Время завершения сессии | NULL |
| `status` | TEXT | Статус сессии | DEFAULT 'active', CHECK('active', 'inactive') |

**Индексы:**
- `idx_sessions_user_chat_status` - по (user_id, chat_id, status)
- `idx_sessions_ended` - по ended_at для очистки старых сессий

**Примеры использования:**

```sql
-- Создать новую сессию
INSERT INTO sessions (session_id, user_id, chat_id, status)
VALUES ('uuid-generated', 12345, 67890, 'active');

-- Получить активную сессию пользователя
SELECT session_id FROM sessions
WHERE user_id = 12345 AND chat_id = 67890 AND status = 'active'
ORDER BY started_at DESC
LIMIT 1;

-- Завершить сессию
UPDATE sessions
SET status = 'inactive', ended_at = CURRENT_TIMESTAMP
WHERE session_id = 'uuid-here';
```

---

## Представления (Views)

### recent_conversations

**Назначение:** Удобный доступ к последним 100 сообщениям с форматированными метками времени.

```sql
CREATE VIEW recent_conversations AS
SELECT
    id,
    user_id,
    chat_id,
    message_text,
    message_type,
    datetime(timestamp) as formatted_timestamp,
    session_id
FROM conversations
ORDER BY timestamp DESC
LIMIT 100;
```

### active_sessions

**Назначение:** Быстрый доступ к активным сессиям.

```sql
CREATE VIEW active_sessions AS
SELECT
    session_id,
    user_id,
    chat_id,
    datetime(started_at) as started,
    status
FROM sessions
WHERE status = 'active';
```

---

## ER-диаграмма

```
┌─────────────────────┐
│   conversations     │
├─────────────────────┤
│ id (PK)             │
│ user_id             │
│ chat_id             │
│ message_text        │
│ message_type        │
│ timestamp           │
│ session_id (FK)     │────────┐
└─────────────────────┘        │
                               │
┌─────────────────────┐        │
│ intermediate_results│        │
├─────────────────────┤        │
│ id (PK)             │        │
│ user_id             │        │
│ chat_id             │        │
│ task_name           │        │
│ result_data         │        │
│ status              │        │
│ created_at          │        │
│ updated_at          │        │
└─────────────────────┘        │
                               │
┌─────────────────────┐        │
│   agent_actions     │        │
├─────────────────────┤        │
│ id (PK)             │        │
│ user_id             │        │
│ chat_id             │        │
│ action_type         │        │
│ action_description  │        │
│ input_data          │        │
│ output_data         │        │
│ timestamp           │        │
│ execution_time_ms   │        │
└─────────────────────┘        │
                               │
┌─────────────────────┐        │
│   knowledge_base    │        │
├─────────────────────┤        │
│ id (PK)             │        │
│ user_id             │        │
│ entity_type         │        │
│ entity_key          │        │
│ entity_value        │        │
│ confidence_score    │        │
│ source_message_id   │        │
│ created_at          │        │
│ updated_at          │        │
└─────────────────────┘        │
                               │
┌─────────────────────┐        │
│      sessions       │        │
├─────────────────────┤        │
│ session_id (PK)     │◄───────┘
│ user_id             │
│ chat_id             │
│ started_at          │
│ ended_at            │
│ status              │
└─────────────────────┘
```

---

## Политики очистки данных

Для поддержания размера базы данных в разумных пределах рекомендуется периодически очищать старые данные:

```sql
-- Удаление сообщений старше 30 дней
DELETE FROM conversations
WHERE timestamp < datetime('now', '-30 days');

-- Удаление завершенных промежуточных результатов старше 7 дней
DELETE FROM intermediate_results
WHERE status IN ('completed', 'failed')
  AND updated_at < datetime('now', '-7 days');

-- Удаление логов действий старше 30 дней
DELETE FROM agent_actions
WHERE timestamp < datetime('now', '-30 days');

-- Удаление неактивных сессий старше 7 дней
DELETE FROM sessions
WHERE status = 'inactive'
  AND ended_at < datetime('now', '-7 days');
```

Метод `cleanup_old_data(days)` в `MemoryManager` автоматизирует эту задачу.

---

## Оптимизация производительности

### Рекомендации:

1. **Регулярное выполнение VACUUM** для дефрагментации базы:
   ```sql
   VACUUM;
   ```

2. **Анализ статистики** для оптимизации запросов:
   ```sql
   ANALYZE;
   ```

3. **Мониторинг размера базы**:
   ```sql
   SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();
   ```

4. **Использование транзакций** для пакетных операций (уже реализовано в MemoryManager)

---

## Миграции (будущие расширения)

При необходимости изменения схемы БД следует:

1. Создать скрипт миграции в `database/migrations/`
2. Добавить версионирование схемы (таблица `schema_version`)
3. Реализовать откат миграций для безопасности

Пример структуры миграции:

```sql
-- database/migrations/001_add_user_preferences.sql
ALTER TABLE knowledge_base ADD COLUMN priority INTEGER DEFAULT 0;

-- Обновление версии
INSERT INTO schema_version (version, applied_at)
VALUES (1, CURRENT_TIMESTAMP);
```

---

## Резервное копирование

Рекомендуется регулярно создавать резервные копии базы данных:

```bash
# Простое копирование файла
cp agent_memory.db agent_memory_backup_$(date +%Y%m%d).db

# Экспорт в SQL
sqlite3 agent_memory.db .dump > agent_memory_backup.sql

# Восстановление из SQL
sqlite3 new_agent_memory.db < agent_memory_backup.sql
```

---

## Безопасность

1. **Параметризованные запросы**: Все запросы в MemoryManager используют параметризацию для защиты от SQL-инъекций
2. **Шифрование**: Для хранения чувствительных данных рекомендуется использовать SQLCipher (расширение SQLite с шифрованием)
3. **Права доступа**: Убедитесь, что файл БД доступен только процессу бота

---

## См. также

- [MEMORY_MANAGER_API.md](MEMORY_MANAGER_API.md) - Документация API MemoryManager
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Руководство по интеграции
- [MEMORY_ARCHITECTURE.md](MEMORY_ARCHITECTURE.md) - Архитектура системы памяти
