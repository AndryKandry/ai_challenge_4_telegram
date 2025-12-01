"""
Модуль планировщика фоновых задач.

Предоставляет систему для выполнения периодических задач в фоне:
- Переиндексация документов
- Обновление git-статистики
- Кеширование результатов
- Очистка временных данных
"""

from .base_task import BaseTask, TaskStatus, TaskPriority
from .task_scheduler import TaskScheduler

__all__ = [
    "BaseTask",
    "TaskStatus",
    "TaskPriority",
    "TaskScheduler",
]
