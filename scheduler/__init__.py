"""
Scheduler Manager для системы автоматических сводок из Telegram чатов.

Компоненты:
- config.py: Конфигурация APScheduler
- manager.py: Менеджер планировщиков
- tasks.py: Логика выполнения задач
"""

from .manager import SchedulerManager
from .config import get_scheduler_config

__all__ = ['SchedulerManager', 'get_scheduler_config']
