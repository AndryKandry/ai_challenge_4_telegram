-- Миграция 001: Начальная схема базы данных для системы автоматических сводок
-- Создание таблиц: assistants, execution_history, chat_metadata

-- Таблица ассистентов
CREATE TABLE IF NOT EXISTS assistants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id TEXT UNIQUE NOT NULL,      -- UUID для идентификации
    user_id INTEGER NOT NULL,               -- Telegram user_id владельца
    chat_id TEXT NOT NULL,                  -- ID чата для мониторинга
    chat_name TEXT NOT NULL,                -- Название чата
    interval_type TEXT NOT NULL CHECK(interval_type IN ('minute', 'hour', 'day', 'custom')),
    interval_value INTEGER NOT NULL CHECK(interval_value >= 1),  -- Значение интервала в минутах
    custom_prompt TEXT,                     -- Пользовательский промпт
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'stopped', 'error')),
    scheduler_job_id TEXT,                  -- ID задачи в APScheduler
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    UNIQUE(user_id, chat_id)                -- Один ассистент на пару (user, chat)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_assistants_user_id ON assistants(user_id);
CREATE INDEX IF NOT EXISTS idx_assistants_status ON assistants(status);
CREATE INDEX IF NOT EXISTS idx_assistants_assistant_id ON assistants(assistant_id);

-- Таблица истории выполнений
CREATE TABLE IF NOT EXISTS execution_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('success', 'error', 'no_messages')),
    messages_count INTEGER DEFAULT 0 CHECK(messages_count >= 0),
    summary_sent BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    FOREIGN KEY (assistant_id) REFERENCES assistants(assistant_id) ON DELETE CASCADE
);

-- Индексы для истории
CREATE INDEX IF NOT EXISTS idx_execution_history_assistant_id ON execution_history(assistant_id);
CREATE INDEX IF NOT EXISTS idx_execution_history_started_at ON execution_history(started_at);

-- Таблица метаданных чатов
CREATE TABLE IF NOT EXISTS chat_metadata (
    chat_id TEXT PRIMARY KEY,
    chat_type TEXT CHECK(chat_type IN ('private', 'group', 'supergroup', 'channel')),
    title TEXT,
    username TEXT,
    member_count INTEGER CHECK(member_count >= 0 OR member_count IS NULL),
    last_checked TIMESTAMP,
    access_valid BOOLEAN DEFAULT TRUE
);

-- Индекс для метаданных
CREATE INDEX IF NOT EXISTS idx_chat_metadata_last_checked ON chat_metadata(last_checked);

-- Триггер для автоматического обновления updated_at при изменении записи
CREATE TRIGGER IF NOT EXISTS update_assistants_timestamp
AFTER UPDATE ON assistants
BEGIN
    UPDATE assistants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
