"""
Глобальный контекст для планировщика.

Хранит ссылки на объекты, которые не могут быть сериализованы через pickle,
но необходимы для выполнения задач планировщика.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SchedulerContext:
    """
    Глобальный контекст для хранения объектов, необходимых для выполнения задач.

    Используется как синглтон для избежания проблем с pickle при сохранении
    задач APScheduler в SQLite jobstore.
    """

    _instance: Optional['SchedulerContext'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.database = None
            cls._instance.llm_provider = None
            cls._instance.telegram_bot = None
            logger.info("SchedulerContext создан")
        return cls._instance

    def initialize(self, database, llm_provider, telegram_bot):
        """
        Инициализация контекста.

        Args:
            database: Экземпляр Database
            llm_provider: Провайдер LLM (DeepSeek)
            telegram_bot: Экземпляр Telegram бота
        """
        self.database = database
        self.llm_provider = llm_provider
        self.telegram_bot = telegram_bot
        logger.info("SchedulerContext инициализирован")

    @classmethod
    def get_instance(cls) -> 'SchedulerContext':
        """Получить экземпляр контекста."""
        if cls._instance is None:
            cls._instance = SchedulerContext()
        return cls._instance


def get_context() -> SchedulerContext:
    """Удобная функция для получения контекста."""
    return SchedulerContext.get_instance()
