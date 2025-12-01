"""
Базовые классы для системы Tools.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Типы инструментов в системе."""
    RAG = "rag"
    MCP = "mcp"
    SYSTEM = "system"
    HTTP = "http"


class ToolFailureError(Exception):
    """Исключение при отказе инструмента."""
    pass


class BaseTool(ABC):
    """
    Базовый класс для всех инструментов в системе.

    Attributes:
        name (str): Уникальное имя инструмента
        tool_type (ToolType): Тип инструмента
        description (str): Описание функциональности
        is_available (bool): Флаг доступности
    """

    def __init__(self, name: str, tool_type: ToolType, description: str):
        self.name = name
        self.tool_type = tool_type
        self.description = description
        self.is_available = True
        logger.info(f"Инструмент '{name}' ({tool_type.value}) инициализирован")

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Выполнить операцию с инструментом."""
        pass

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров перед выполнением."""
        return True

    async def health_check(self) -> bool:
        """Проверка доступности инструмента."""
        return self.is_available

    def get_schema(self) -> Dict[str, Any]:
        """Получить JSON-схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {},
            "required": []
        }

    def set_available(self, available: bool) -> None:
        """Установить флаг доступности инструмента."""
        self.is_available = available
        status = "доступен" if available else "недоступен"
        logger.info(f"Инструмент '{self.name}' теперь {status}")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', type={self.tool_type.value})>"
