"""
Модуль хранения пользовательских настроек и данных системы автоматических сводок.

Содержит классы для работы с:
- Пользовательскими предпочтениями и настройками
- Базой данных ассистентов Telegram
- Моделями данных для системы автоматических сводок
"""

from .user_settings import UserSettings
from .database import Database
from .models import Assistant, ExecutionHistory, ChatMetadata

__all__ = [
    "UserSettings",
    "Database",
    "Assistant",
    "ExecutionHistory",
    "ChatMetadata"
]
