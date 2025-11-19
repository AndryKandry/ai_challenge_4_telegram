"""
Модели данных для системы автоматических сводок.

Использует dataclasses для определения структур данных.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Assistant:
    """
    Модель ассистента для мониторинга Telegram чата.

    Attributes:
        id: Уникальный ID в базе данных (auto-increment)
        assistant_id: UUID для внешней идентификации
        user_id: Telegram user_id владельца ассистента
        chat_id: ID чата для мониторинга
        chat_name: Название чата
        interval_type: Тип интервала ('minute', 'hour', 'day', 'custom')
        interval_value: Значение интервала в минутах
        custom_prompt: Пользовательский промпт для LLM (опционально)
        status: Статус ассистента ('active', 'stopped', 'error')
        scheduler_job_id: ID задачи в APScheduler (опционально)
        created_at: Время создания
        updated_at: Время последнего обновления
        last_run_at: Время последнего запуска (опционально)
        next_run_at: Время следующего запуска (опционально)
    """

    id: Optional[int]
    assistant_id: str
    user_id: int
    chat_id: str
    chat_name: str
    interval_type: str  # 'minute', 'hour', 'day', 'custom'
    interval_value: int
    custom_prompt: Optional[str]
    status: str  # 'active', 'stopped', 'error'
    scheduler_job_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None

    def __post_init__(self):
        """Валидация данных после инициализации."""
        if self.interval_type not in ['minute', 'hour', 'day', 'custom']:
            raise ValueError(f"Недопустимый тип интервала: {self.interval_type}")

        if self.interval_value < 1:
            raise ValueError(f"Значение интервала должно быть >= 1, получено: {self.interval_value}")

        if self.status not in ['active', 'stopped', 'error']:
            raise ValueError(f"Недопустимый статус: {self.status}")


@dataclass
class ExecutionHistory:
    """
    Модель истории выполнения задач ассистента.

    Attributes:
        id: Уникальный ID записи
        assistant_id: ID ассистента
        started_at: Время начала выполнения
        completed_at: Время завершения выполнения (опционально)
        status: Статус выполнения ('success', 'error', 'no_messages')
        messages_count: Количество обработанных сообщений
        summary_sent: Была ли отправлена сводка
        error_message: Текст ошибки (если есть)
    """

    id: Optional[int]
    assistant_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str  # 'success', 'error', 'no_messages'
    messages_count: int = 0
    summary_sent: bool = False
    error_message: Optional[str] = None

    def __post_init__(self):
        """Валидация данных после инициализации."""
        if self.status not in ['success', 'error', 'no_messages']:
            raise ValueError(f"Недопустимый статус: {self.status}")

        if self.messages_count < 0:
            raise ValueError(f"Количество сообщений не может быть отрицательным: {self.messages_count}")


@dataclass
class ChatMetadata:
    """
    Модель метаданных Telegram чата.

    Attributes:
        chat_id: ID чата (первичный ключ)
        chat_type: Тип чата ('private', 'group', 'supergroup', 'channel')
        title: Название чата
        username: Username чата (если есть)
        member_count: Количество участников (опционально)
        last_checked: Время последней проверки
        access_valid: Валиден ли доступ к чату
    """

    chat_id: str
    chat_type: Optional[str]  # 'private', 'group', 'supergroup', 'channel'
    title: Optional[str]
    username: Optional[str]
    member_count: Optional[int]
    last_checked: Optional[datetime]
    access_valid: bool = True

    def __post_init__(self):
        """Валидация данных после инициализации."""
        if self.chat_type and self.chat_type not in ['private', 'group', 'supergroup', 'channel']:
            raise ValueError(f"Недопустимый тип чата: {self.chat_type}")

        if self.member_count is not None and self.member_count < 0:
            raise ValueError(f"Количество участников не может быть отрицательным: {self.member_count}")
