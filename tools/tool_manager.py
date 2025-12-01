"""
Tool Manager - менеджер для управления инструментами.
"""

import logging
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool, ToolType, ToolFailureError

logger = logging.getLogger(__name__)


class ToolManager:
    """
    Менеджер инструментов для централизованного управления.

    Функционал:
    - Регистрация и управление доступными инструментами
    - Динамическая замена инструментов "на лету"
    - Проверка доступности инструментов
    - Маршрутизация вызовов к нужным инструментам

    Attributes:
        tools (Dict[str, BaseTool]): Словарь зарегистрированных инструментов
        tool_aliases (Dict[str, str]): Словарь псевдонимов инструментов
    """

    def __init__(self):
        """Инициализация менеджера инструментов."""
        self.tools: Dict[str, BaseTool] = {}
        self.tool_aliases: Dict[str, str] = {}
        logger.info("ToolManager инициализирован")

    def register_tool(self, tool: BaseTool, aliases: Optional[List[str]] = None) -> None:
        """
        Регистрация нового инструмента.

        Args:
            tool: Экземпляр инструмента для регистрации
            aliases: Список псевдонимов для инструмента

        Raises:
            ValueError: Если инструмент с таким именем уже зарегистрирован
        """
        if tool.name in self.tools:
            raise ValueError(f"Инструмент '{tool.name}' уже зарегистрирован")

        self.tools[tool.name] = tool
        logger.info(f"Инструмент '{tool.name}' зарегистрирован")

        # Регистрация псевдонимов
        if aliases:
            for alias in aliases:
                self.tool_aliases[alias] = tool.name
                logger.info(f"Псевдоним '{alias}' -> '{tool.name}' зарегистрирован")

    def unregister_tool(self, tool_name: str) -> bool:
        """
        Удаление инструмента.

        Args:
            tool_name: Имя инструмента для удаления

        Returns:
            True если инструмент был удален, False если не найден
        """
        if tool_name in self.tools:
            del self.tools[tool_name]

            # Удалить все псевдонимы
            aliases_to_remove = [
                alias for alias, name in self.tool_aliases.items()
                if name == tool_name
            ]
            for alias in aliases_to_remove:
                del self.tool_aliases[alias]

            logger.info(f"Инструмент '{tool_name}' удален")
            return True

        logger.warning(f"Попытка удалить несуществующий инструмент '{tool_name}'")
        return False

    def replace_tool(self, old_tool_name: str, new_tool: BaseTool) -> None:
        """
        Динамическая замена инструмента на лету.

        Args:
            old_tool_name: Имя инструмента для замены
            new_tool: Новый инструмент

        Raises:
            ValueError: Если старый инструмент не найден
        """
        if old_tool_name not in self.tools:
            raise ValueError(f"Инструмент '{old_tool_name}' не найден")

        # Сохраняем псевдонимы старого инструмента
        old_aliases = [
            alias for alias, name in self.tool_aliases.items()
            if name == old_tool_name
        ]

        # Удаляем старый инструмент
        del self.tools[old_tool_name]

        # Регистрируем новый инструмент
        self.tools[new_tool.name] = new_tool

        # Переназначаем псевдонимы
        for alias in old_aliases:
            self.tool_aliases[alias] = new_tool.name

        logger.info(f"Инструмент '{old_tool_name}' заменен на '{new_tool.name}'")

    async def execute_tool(self, tool_name: str, **params) -> Any:
        """
        Выполнение инструмента по имени.

        Args:
            tool_name: Имя инструмента (или псевдоним)
            **params: Параметры для выполнения

        Returns:
            Результат выполнения инструмента

        Raises:
            ValueError: Если инструмент не найден
            ToolFailureError: При ошибке выполнения инструмента
        """
        # Разрешаем псевдонимы
        actual_name = self.tool_aliases.get(tool_name, tool_name)

        if actual_name not in self.tools:
            raise ValueError(f"Инструмент '{tool_name}' не найден")

        tool = self.tools[actual_name]

        # Проверка доступности
        if not await tool.health_check():
            raise ToolFailureError(f"Инструмент '{actual_name}' недоступен")

        # Валидация параметров
        if not await tool.validate_params(params):
            raise ValueError(f"Некорректные параметры для инструмента '{actual_name}'")

        logger.info(f"Выполнение инструмента '{actual_name}'")

        try:
            result = await tool.execute(**params)
            logger.info(f"Инструмент '{actual_name}' успешно выполнен")
            return result
        except Exception as e:
            logger.error(f"Ошибка при выполнении инструмента '{actual_name}': {e}")
            # Попытка обработать ошибку
            error_result = await tool.on_failure(e, params)
            if error_result is not None:
                return error_result
            raise ToolFailureError(f"Инструмент '{actual_name}' завершился с ошибкой: {e}")

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Получить инструмент по имени.

        Args:
            tool_name: Имя инструмента (или псевдоним)

        Returns:
            Экземпляр инструмента или None
        """
        actual_name = self.tool_aliases.get(tool_name, tool_name)
        return self.tools.get(actual_name)

    def get_available_tools(self, tool_type: Optional[ToolType] = None) -> List[str]:
        """
        Получить список доступных инструментов.

        Args:
            tool_type: Фильтр по типу инструмента (опционально)

        Returns:
            Список имен доступных инструментов
        """
        tools = self.tools.values()

        if tool_type:
            tools = [t for t in tools if t.tool_type == tool_type]

        return [t.name for t in tools if t.is_available]

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Проверить доступность всех инструментов.

        Returns:
            Словарь {имя_инструмента: доступность}
        """
        results = {}
        for name, tool in self.tools.items():
            try:
                results[name] = await tool.health_check()
            except Exception as e:
                logger.error(f"Ошибка при проверке здоровья инструмента '{name}': {e}")
                results[name] = False

        return results

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Получить схему параметров инструмента.

        Args:
            tool_name: Имя инструмента

        Returns:
            Словарь со схемой или None если не найден
        """
        tool = self.get_tool(tool_name)
        return tool.get_schema() if tool else None

    def list_tools(self) -> List[str]:
        """Получить список всех зарегистрированных инструментов."""
        return list(self.tools.keys())

    def __repr__(self) -> str:
        """Строковое представление менеджера."""
        tool_count = len(self.tools)
        available_count = len(self.get_available_tools())
        return f"<ToolManager(tools={tool_count}, available={available_count})>"
