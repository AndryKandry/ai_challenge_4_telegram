"""
Базовый класс для всех агентов в системе subagents.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Базовый класс для всех агентов в системе.

    Каждый агент должен наследоваться от этого класса и реализовывать
    метод execute() для выполнения своей специализированной задачи.

    Attributes:
        name (str): Уникальное имя агента для идентификации
        enabled (bool): Флаг активности агента
        tool_manager: Менеджер инструментов (опционально)
        required_tools (List[str]): Список обязательных инструментов
        preferred_tools (Dict[str, List[str]]): Предпочитаемые инструменты с альтернативами
    """

    def __init__(
        self,
        name: str,
        tool_manager: Optional[Any] = None,
        enabled: bool = True
    ):
        """
        Инициализация базового агента.

        Args:
            name: Уникальное имя агента
            tool_manager: Менеджер инструментов (опционально для обратной совместимости)
            enabled: Флаг активности агента (по умолчанию True)
        """
        self.name = name
        self.enabled = enabled
        self.tool_manager = tool_manager
        self.required_tools: List[str] = []
        self.preferred_tools: Dict[str, List[str]] = {}
        logger.info(f"Агент '{name}' инициализирован (enabled={enabled}, tool_manager={'да' if tool_manager else 'нет'})")

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Any:
        """
        Основной метод выполнения задачи агентом.

        Каждый агент должен реализовать этот метод для выполнения
        своей специализированной логики.

        Args:
            task: Словарь с параметрами задачи. Должен содержать ключи:
                - action (str): Действие, которое нужно выполнить
                - params (dict): Параметры для выполнения действия
                - context (dict, optional): Дополнительный контекст

        Returns:
            Результат выполнения задачи (тип зависит от реализации)

        Raises:
            NotImplementedError: Если метод не реализован в подклассе
            ValueError: Если task имеет неверный формат
        """
        pass

    async def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Валидация входных данных для агента.

        Базовая реализация проверяет наличие обязательных полей.
        Подклассы могут переопределить этот метод для более строгой валидации.

        Args:
            data: Словарь с входными данными

        Returns:
            True если данные валидны, False в противном случае
        """
        # Проверка наличия обязательных полей
        required_fields = ["action"]

        for field in required_fields:
            if field not in data:
                logger.error(f"Агент '{self.name}': отсутствует обязательное поле '{field}'")
                return False

        return True

    def is_enabled(self) -> bool:
        """
        Проверка, активен ли агент.

        Returns:
            True если агент активен, False в противном случае
        """
        return self.enabled

    def enable(self) -> None:
        """Активировать агента."""
        self.enabled = True
        logger.info(f"Агент '{self.name}' активирован")

    def disable(self) -> None:
        """Деактивировать агента."""
        self.enabled = False
        logger.info(f"Агент '{self.name}' деактивирован")

    async def handle_error(self, error: Exception, task: Dict[str, Any]) -> Optional[Any]:
        """
        Обработка ошибок при выполнении задачи.

        Базовая реализация логирует ошибку. Подклассы могут переопределить
        для более сложной обработки (retry, fallback и т.д.).

        Args:
            error: Исключение, которое произошло
            task: Задача, при выполнении которой произошла ошибка

        Returns:
            Результат обработки ошибки или None
        """
        logger.error(
            f"Агент '{self.name}': ошибка при выполнении задачи: {error}",
            exc_info=True
        )
        return None

    async def call_tool(self, tool_name: str, **params) -> Any:
        """
        Вызов инструмента через менеджер.

        Args:
            tool_name: Имя инструмента для вызова
            **params: Параметры для инструмента

        Returns:
            Результат выполнения инструмента

        Raises:
            RuntimeError: Если Tool Manager не настроен
            Exception: Ошибки при выполнении инструмента
        """
        if not self.tool_manager:
            raise RuntimeError(
                f"Агент '{self.name}' не имеет Tool Manager. "
                "Невозможно вызвать инструмент."
            )

        try:
            logger.debug(f"Агент '{self.name}' вызывает инструмент '{tool_name}'")
            return await self.tool_manager.execute_tool(tool_name, **params)
        except Exception as e:
            # Попытка найти альтернативный инструмент
            logger.warning(
                f"Агент '{self.name}': инструмент '{tool_name}' завершился с ошибкой: {e}"
            )
            return await self._handle_tool_failure(tool_name, e, params)

    async def _handle_tool_failure(
        self,
        tool_name: str,
        error: Exception,
        params: Dict[str, Any]
    ) -> Any:
        """
        Обработка отказа инструмента с автоматической заменой.

        Ищет альтернативные инструменты в preferred_tools и пытается
        выполнить задачу с их помощью.

        Args:
            tool_name: Имя инструмента, который отказал
            error: Исключение, которое произошло
            params: Параметры, с которыми был вызван инструмент

        Returns:
            Результат выполнения альтернативного инструмента

        Raises:
            Exception: Если все альтернативы не сработали
        """
        # Поиск альтернативных инструментов
        alternative_tools = self._find_alternative_tools(tool_name)

        if not alternative_tools:
            logger.error(
                f"Агент '{self.name}': нет альтернативных инструментов для '{tool_name}'"
            )
            raise error

        # Попытка использовать альтернативные инструменты
        for alt_tool in alternative_tools:
            try:
                logger.info(
                    f"Агент '{self.name}': попытка использовать альтернативу '{alt_tool}'"
                )
                return await self.tool_manager.execute_tool(alt_tool, **params)
            except Exception as alt_error:
                logger.warning(
                    f"Агент '{self.name}': альтернатива '{alt_tool}' также не сработала: {alt_error}"
                )
                continue

        # Все альтернативы не сработали
        logger.error(
            f"Агент '{self.name}': все альтернативные инструменты не сработали"
        )
        raise error

    def _find_alternative_tools(self, failed_tool: str) -> List[str]:
        """
        Найти альтернативные инструменты.

        Ищет альтернативы в preferred_tools словаре.

        Args:
            failed_tool: Имя инструмента, который отказал

        Returns:
            Список имен альтернативных инструментов
        """
        # Ищем в preferred_tools
        for category, tools in self.preferred_tools.items():
            if failed_tool in tools:
                # Возвращаем все остальные инструменты из этой категории
                return [t for t in tools if t != failed_tool]

        return []

    async def check_tools_availability(self) -> bool:
        """
        Проверить доступность необходимых инструментов.

        Returns:
            True если все обязательные инструменты доступны, False иначе
        """
        if not self.tool_manager:
            # Если нет Tool Manager, считаем что инструменты не нужны
            return True

        for tool_name in self.required_tools:
            tool = self.tool_manager.get_tool(tool_name)
            if not tool:
                logger.error(
                    f"Агент '{self.name}': обязательный инструмент '{tool_name}' не найден"
                )
                return False

            if not await tool.health_check():
                logger.error(
                    f"Агент '{self.name}': обязательный инструмент '{tool_name}' недоступен"
                )
                return False

        return True

    def get_available_tools(self) -> List[str]:
        """
        Получить список доступных инструментов для агента.

        Returns:
            Список имен доступных инструментов
        """
        if not self.tool_manager:
            return []

        return self.tool_manager.get_available_tools()

    def __repr__(self) -> str:
        """Строковое представление агента."""
        has_tools = "with tools" if self.tool_manager else "no tools"
        return f"<{self.__class__.__name__}(name='{self.name}', enabled={self.enabled}, {has_tools})>"
