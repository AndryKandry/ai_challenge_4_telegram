"""
Оркестратор для координации работы subagents.

Управляет жизненным циклом агентов, маршрутизирует задачи
и объединяет результаты от нескольких агентов.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Оркестратор для управления и координации работы агентов.

    Предоставляет функциональность для:
    - Регистрации и управления агентами
    - Управления Tool Manager
    - Маршрутизации задач к соответствующим агентам
    - Параллельного выполнения задач несколькими агентами
    - Обработки ошибок и fallback логики
    - Динамического переключения инструментов

    Attributes:
        agents (Dict[str, BaseAgent]): Словарь зарегистрированных агентов
        tool_manager: Менеджер инструментов
    """

    def __init__(self, tool_manager: Optional[Any] = None):
        """
        Инициализация оркестратора.

        Args:
            tool_manager: Менеджер инструментов (опционально)
        """
        self.agents: Dict[str, BaseAgent] = {}
        self.tool_manager = tool_manager
        logger.info(
            f"AgentOrchestrator инициализирован "
            f"(tool_manager={'да' if tool_manager else 'нет'})"
        )

    def register_agent(self, agent: BaseAgent) -> None:
        """
        Регистрация агента в оркестраторе.

        Args:
            agent: Экземпляр агента для регистрации

        Raises:
            ValueError: Если агент с таким именем уже зарегистрирован
        """
        if agent.name in self.agents:
            raise ValueError(f"Агент '{agent.name}' уже зарегистрирован")

        self.agents[agent.name] = agent
        logger.info(f"Агент '{agent.name}' зарегистрирован в оркестраторе")

    def unregister_agent(self, agent_name: str) -> bool:
        """
        Удаление агента из оркестратора.

        Args:
            agent_name: Имя агента для удаления

        Returns:
            True если агент был удален, False если агент не найден
        """
        if agent_name in self.agents:
            del self.agents[agent_name]
            logger.info(f"Агент '{agent_name}' удален из оркестратора")
            return True

        logger.warning(f"Попытка удалить несуществующий агент '{agent_name}'")
        return False

    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Получение агента по имени.

        Args:
            agent_name: Имя агента

        Returns:
            Экземпляр агента или None если не найден
        """
        return self.agents.get(agent_name)

    def list_agents(self) -> List[str]:
        """
        Получение списка имен всех зарегистрированных агентов.

        Returns:
            Список имен агентов
        """
        return list(self.agents.keys())

    def list_enabled_agents(self) -> List[str]:
        """
        Получение списка имен всех активных агентов.

        Returns:
            Список имен активных агентов
        """
        return [name for name, agent in self.agents.items() if agent.is_enabled()]

    async def execute_task(
        self,
        agent_name: str,
        task_data: Dict[str, Any]
    ) -> Any:
        """
        Выполнение задачи указанным агентом.

        Args:
            agent_name: Имя агента для выполнения задачи
            task_data: Данные задачи для выполнения

        Returns:
            Результат выполнения задачи

        Raises:
            ValueError: Если агент не найден или неактивен
            Exception: Ошибки при выполнении задачи агентом
        """
        agent = self.get_agent(agent_name)

        if agent is None:
            raise ValueError(f"Агент '{agent_name}' не найден")

        if not agent.is_enabled():
            raise ValueError(f"Агент '{agent_name}' неактивен")

        # Валидация входных данных
        if not await agent.validate_input(task_data):
            raise ValueError(f"Невалидные данные для агента '{agent_name}'")

        logger.info(f"Выполнение задачи агентом '{agent_name}': {task_data.get('action')}")

        try:
            result = await agent.execute(task_data)
            logger.info(f"Агент '{agent_name}' успешно выполнил задачу")
            return result
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи агентом '{agent_name}': {e}")
            # Попытка обработать ошибку агентом
            error_result = await agent.handle_error(e, task_data)
            if error_result is not None:
                return error_result
            raise

    async def coordinate_agents(
        self,
        agents_tasks: List[Tuple[str, Dict[str, Any]]]
    ) -> List[Any]:
        """
        Координация выполнения задач несколькими агентами параллельно.

        Выполняет задачи для нескольких агентов одновременно и возвращает
        результаты в том же порядке, что и входные задачи.

        Args:
            agents_tasks: Список кортежей (имя_агента, данные_задачи)

        Returns:
            Список результатов выполнения задач. Если задача завершилась
            с ошибкой, в списке будет None на соответствующей позиции.

        Example:
            >>> tasks = [
            ...     ("documentation_rag", {"action": "search", "params": {"query": "API"}}),
            ...     ("github_mcp", {"action": "get_status", "params": {}})
            ... ]
            >>> results = await orchestrator.coordinate_agents(tasks)
        """
        logger.info(f"Координация выполнения {len(agents_tasks)} задач")

        # Создаем корутины для всех задач
        coroutines = []
        for agent_name, task_data in agents_tasks:
            coroutine = self._execute_task_safe(agent_name, task_data)
            coroutines.append(coroutine)

        # Выполняем все задачи параллельно
        results = await asyncio.gather(*coroutines)

        logger.info(f"Координация завершена: {len(results)} результатов")
        return results

    async def _execute_task_safe(
        self,
        agent_name: str,
        task_data: Dict[str, Any]
    ) -> Any:
        """
        Безопасное выполнение задачи с обработкой ошибок.

        Используется внутри coordinate_agents для предотвращения
        прерывания выполнения других задач при ошибке.

        Args:
            agent_name: Имя агента
            task_data: Данные задачи

        Returns:
            Результат выполнения задачи или None при ошибке
        """
        try:
            return await self.execute_task(agent_name, task_data)
        except Exception as e:
            logger.error(
                f"Ошибка при безопасном выполнении задачи агентом '{agent_name}': {e}",
                exc_info=True
            )
            return None

    async def execute_with_fallback(
        self,
        primary_agent: str,
        fallback_agent: str,
        task_data: Dict[str, Any]
    ) -> Any:
        """
        Выполнение задачи с fallback на другой агент при ошибке.

        Сначала пытается выполнить задачу основным агентом.
        Если основной агент терпит неудачу, выполняет задачу fallback агентом.

        Args:
            primary_agent: Имя основного агента
            fallback_agent: Имя резервного агента
            task_data: Данные задачи

        Returns:
            Результат выполнения задачи

        Raises:
            Exception: Если оба агента завершились с ошибкой
        """
        try:
            logger.info(f"Попытка выполнить задачу основным агентом '{primary_agent}'")
            return await self.execute_task(primary_agent, task_data)
        except Exception as primary_error:
            logger.warning(
                f"Основной агент '{primary_agent}' завершился с ошибкой, "
                f"переключение на резервный '{fallback_agent}'"
            )
            try:
                return await self.execute_task(fallback_agent, task_data)
            except Exception as fallback_error:
                logger.error(
                    f"Оба агента завершились с ошибкой. "
                    f"Primary: {primary_error}, Fallback: {fallback_error}"
                )
                raise

    async def switch_tool(
        self,
        agent_name: str,
        old_tool: str,
        new_tool_name: str
    ) -> None:
        """
        Динамическое переключение инструмента для агента.

        Args:
            agent_name: Имя агента (не используется, переключение глобальное)
            old_tool: Имя старого инструмента
            new_tool_name: Имя нового инструмента

        Raises:
            RuntimeError: Если Tool Manager не настроен
            ValueError: Если инструменты не найдены
        """
        if not self.tool_manager:
            raise RuntimeError("Tool Manager не настроен в оркестраторе")

        # Получаем новый инструмент
        new_tool = self.tool_manager.get_tool(new_tool_name)
        if not new_tool:
            raise ValueError(f"Новый инструмент '{new_tool_name}' не найден")

        # Заменяем инструмент
        self.tool_manager.replace_tool(old_tool, new_tool)

        logger.info(
            f"Инструмент '{old_tool}' заменен на '{new_tool_name}' "
            f"в оркестраторе"
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья всех агентов и инструментов.

        Returns:
            Словарь со статусом агентов и инструментов:
                - agents: {имя_агента: доступность_инструментов}
                - tools: {имя_инструмента: доступность} (если есть Tool Manager)
        """
        result = {"agents": {}, "tools": {}}

        # Проверка агентов
        for name, agent in self.agents.items():
            try:
                agent_healthy = await agent.check_tools_availability()
                result["agents"][name] = agent_healthy
            except Exception as e:
                logger.error(
                    f"Ошибка при проверке здоровья агента '{name}': {e}"
                )
                result["agents"][name] = False

        # Проверка инструментов
        if self.tool_manager:
            try:
                result["tools"] = await self.tool_manager.health_check_all()
            except Exception as e:
                logger.error(f"Ошибка при проверке здоровья инструментов: {e}")
                result["tools"] = {}

        return result

    def __repr__(self) -> str:
        """Строковое представление оркестратора."""
        agent_count = len(self.agents)
        enabled_count = len(self.list_enabled_agents())
        has_tools = "with tools" if self.tool_manager else "no tools"
        return f"<AgentOrchestrator(agents={agent_count}, enabled={enabled_count}, {has_tools})>"
