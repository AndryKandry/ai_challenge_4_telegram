-- SQL схема базы данных для системы памяти агента
-- Версия: 1.0
-- Описание: Схема для хранения истории диалогов, промежуточных результатов,
--           действий агента, базы знаний и метаданных сессий

-- ============================================================================
-- ТАБЛИЦА: conversations
-- Назначение: Хранение истории сообщений между пользователями и ассистентом
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    message_text TEXT NOT NULL,
    message_type TEXT CHECK(message_type IN ('user', 'assistant')) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE SET NULL
);

-- Индекс для быстрого получения истории диалогов по пользователю и чату
CREATE INDEX IF NOT EXISTS idx_conversations_user_chat
ON conversations(user_id, chat_id, timestamp DESC);

-- Индекс для запросов по сессиям
CREATE INDEX IF NOT EXISTS idx_conversations_session
ON conversations(session_id);

-- ============================================================================
-- ТАБЛИЦА: intermediate_results
-- Назначение: Хранение промежуточных результатов и вычислений агента
-- ============================================================================
CREATE TABLE IF NOT EXISTS intermediate_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    result_data TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending', 'completed', 'failed')) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для получения результатов по пользователю, чату и задаче
CREATE INDEX IF NOT EXISTS idx_intermediate_user_chat_task
ON intermediate_results(user_id, chat_id, task_name);

-- Индекс для запросов по статусу
CREATE INDEX IF NOT EXISTS idx_intermediate_status
ON intermediate_results(status, updated_at DESC);

-- ============================================================================
-- ТАБЛИЦА: agent_actions
-- Назначение: Логирование всех действий агента для отладки и аналитики
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    action_description TEXT,
    input_data TEXT,
    output_data TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER
);

-- Индекс для получения истории действий
CREATE INDEX IF NOT EXISTS idx_actions_user_chat_time
ON agent_actions(user_id, chat_id, timestamp DESC);

-- Индекс для аналитики по типам действий
CREATE INDEX IF NOT EXISTS idx_actions_type
ON agent_actions(action_type, timestamp DESC);

-- ============================================================================
-- ТАБЛИЦА: knowledge_base
-- Назначение: Хранение извлечённых сущностей, фактов и предпочтений пользователя
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    entity_value TEXT NOT NULL,
    confidence_score REAL DEFAULT 1.0,
    source_message_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, entity_type, entity_key) ON CONFLICT REPLACE
);

-- Индекс для получения знаний по пользователю и типу сущности
CREATE INDEX IF NOT EXISTS idx_knowledge_user_type
ON knowledge_base(user_id, entity_type);

-- Индекс для отслеживания источника
CREATE INDEX IF NOT EXISTS idx_knowledge_source
ON knowledge_base(source_message_id);

-- ============================================================================
-- ТАБЛИЦА: sessions
-- Назначение: Отслеживание пользовательских сессий для управления контекстом
-- ============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    status TEXT CHECK(status IN ('active', 'inactive')) DEFAULT 'active'
);

-- Индекс для поиска активных сессий
CREATE INDEX IF NOT EXISTS idx_sessions_user_chat_status
ON sessions(user_id, chat_id, status);

-- Индекс для очистки старых сессий по дате
CREATE INDEX IF NOT EXISTS idx_sessions_ended
ON sessions(ended_at);

-- ============================================================================
-- ТРИГГЕРЫ
-- Назначение: Автоматическое обновление временных меток и поддержка целостности данных
-- ============================================================================

-- Триггер: Обновление updated_at при изменении intermediate_results
CREATE TRIGGER IF NOT EXISTS update_intermediate_timestamp
AFTER UPDATE ON intermediate_results
FOR EACH ROW
BEGIN
    UPDATE intermediate_results
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- Триггер: Обновление updated_at при изменении knowledge_base
CREATE TRIGGER IF NOT EXISTS update_knowledge_timestamp
AFTER UPDATE ON knowledge_base
FOR EACH ROW
BEGIN
    UPDATE knowledge_base
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- ============================================================================
-- ПРЕДСТАВЛЕНИЯ (Views) - для удобного доступа к данным
-- ============================================================================

-- Представление: Последние сообщения с форматированными метками времени
CREATE VIEW IF NOT EXISTS recent_conversations AS
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

-- Представление: Активные сессии
CREATE VIEW IF NOT EXISTS active_sessions AS
SELECT
    session_id,
    user_id,
    chat_id,
    datetime(started_at) as started,
    status
FROM sessions
WHERE status = 'active';
