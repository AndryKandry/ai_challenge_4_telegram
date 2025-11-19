"""
Конфигурация APScheduler для системы автоматических сводок.
"""

import logging
import os
from typing import Dict, Any

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

logger = logging.getLogger(__name__)


def get_scheduler_config() -> Dict[str, Any]:
    """
    Получение конфигурации для APScheduler.

    Returns:
        Словарь с настройками для AsyncIOScheduler
    """
    # Путь к базе данных для JobStore
    scheduler_db_url = os.getenv("SCHEDULER_DB_URL", "data/scheduler_jobs.db")

    # Создаём SQLite URL для SQLAlchemy
    if not scheduler_db_url.startswith("sqlite://"):
        scheduler_db_url = f"sqlite:///{scheduler_db_url}"

    # Job stores - где хранятся задачи
    jobstores = {
        'default': SQLAlchemyJobStore(url=scheduler_db_url)
    }

    # Executors - как выполняются задачи
    executors = {
        'default': AsyncIOExecutor()
    }

    # Настройки по умолчанию для задач
    job_defaults = {
        'coalesce': True,          # Объединять пропущенные запуски в один
        'max_instances': 1,        # Одна задача одновременно (предотвращает дублирование)
        'misfire_grace_time': 300  # 5 минут на "опоздание" перед тем, как пропустить запуск
    }

    # Timezone
    timezone = os.getenv("SCHEDULER_TIMEZONE", "UTC")

    config = {
        'jobstores': jobstores,
        'executors': executors,
        'job_defaults': job_defaults,
        'timezone': timezone
    }

    logger.info(f"Конфигурация APScheduler создана: JobStore={scheduler_db_url}, Timezone={timezone}")

    return config
