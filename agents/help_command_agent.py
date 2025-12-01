"""
HelpCommandAgent - координатор для обработки команды /help.

Агент анализирует вопросы пользователя и маршрутизирует их к соответствующим
subagents (DocsAgent, GitAgent) для получения информации.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .base_agent import BaseAgent
from .orchestrator import AgentOrchestrator
from src.integrations.mcp_link_generator import MCPLinkGenerator

logger = logging.getLogger(__name__)


class HelpCommandAgent(BaseAgent):
    """
    Координатор для обработки команды /help.

    Анализирует вопросы пользователя и направляет их к соответствующим
    агентам (DocsAgent для документации, GitAgent для информации о репозитории).

    Может координировать работу нескольких агентов параллельно для комплексных
    вопросов.

    Поддерживаемые типы вопросов:
    - Вопросы о документации проекта
    - Вопросы о коде и примерах
    - Вопросы о состоянии репозитория
    - Комбинированные вопросы
    """

    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        name: str = "help_command_agent",
        enabled: bool = True
    ):
        """
        Инициализация HelpCommandAgent.

        Args:
            orchestrator: Оркестратор для управления subagents
            name: Имя агента
            enabled: Флаг активности
        """
        # Передаем None как tool_manager, так как этот агент работает через orchestrator
        super().__init__(name, tool_manager=None, enabled=enabled)
        self.orchestrator = orchestrator

        # Ключевые слова для определения типа вопроса
        self.docs_keywords = [
            "документация", "documentation", "как использовать", "how to",
            "пример", "example", "api", "функция", "function", "метод", "method",
            "класс", "class", "модуль", "module"
        ]

        self.git_keywords = [
            "репозиторий", "repository", "коммит", "commit", "ветка", "branch",
            "изменения", "измененные", "changes", "diff", "статус", "status", "git",
            "pull request", "pr", "текущую ветку", "текущая ветка", "последние коммиты"
        ]

        logger.info("HelpCommandAgent инициализирован с оркестратором")

    async def execute(self, task: Dict[str, Any]) -> Any:
        """
        Выполнение задачи координатором.

        Args:
            task: Словарь с параметрами:
                - action: "answer_question", "search", "status"
                - params: параметры (обычно содержит "query" - вопрос пользователя)
                - context: дополнительный контекст (опционально)

        Returns:
            Ответ на вопрос пользователя

        Raises:
            ValueError: Если действие не поддерживается
        """
        action = task.get("action", "answer_question")
        params = task.get("params", {})
        context = task.get("context", {})

        logger.info(f"HelpCommandAgent выполняет действие: {action}")

        if action == "answer_question":
            query = params.get("query", "")
            return await self.answer_question(query, context)

        elif action == "search":
            query = params.get("query", "")
            search_type = params.get("type", "auto")  # auto, docs, git
            return await self.search(query, search_type)

        elif action == "status":
            return await self.get_system_status()

        else:
            raise ValueError(f"Неизвестное действие: {action}")

    async def answer_question(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ответ на вопрос пользователя с использованием subagents.

        Args:
            query: Вопрос пользователя
            context: Дополнительный контекст

        Returns:
            Словарь с ответом:
                - answer: текст ответа
                - sources: источники информации
                - agents_used: список использованных агентов
        """
        if not query:
            return {
                "answer": "Пожалуйста, задайте вопрос.",
                "sources": [],
                "agents_used": []
            }

        logger.info(f"Обработка вопроса: '{query}'")

        # Анализируем вопрос и определяем нужные агенты
        required_agents = self._analyze_question(query)
        logger.info(f"Требуются агенты: {required_agents}")

        if not required_agents:
            # Не удалось определить тип вопроса, используем оба агента
            required_agents = ["docs_agent"]

        # Формируем задачи для агентов
        tasks = []
        for agent_name in required_agents:
            if agent_name == "docs_agent":
                task = {
                    "action": "search",
                    "params": {
                        "query": query,
                        "top_k": 5,
                        "min_similarity": 0.5
                    }
                }
                tasks.append(("docs_agent", task))

            elif agent_name == "git_agent":
                # Определяем конкретное действие для git_agent
                git_action = self._determine_git_action(query)
                task = {
                    "action": git_action,
                    "params": self._extract_git_params(query, git_action)
                }
                tasks.append(("git_agent", task))

        # Выполняем задачи параллельно через оркестратор
        results = await self.orchestrator.coordinate_agents(tasks)

        # Объединяем и форматируем результаты
        answer = await self._format_combined_answer(query, results, required_agents)

        return answer

    async def search(
        self,
        query: str,
        search_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Поиск информации по запросу.

        Args:
            query: Поисковый запрос
            search_type: Тип поиска ("auto", "docs", "git")

        Returns:
            Словарь с результатами поиска
        """
        if search_type == "auto":
            # Автоматическое определение типа
            return await self.answer_question(query)

        elif search_type == "docs":
            # Поиск только по документации
            task = {
                "action": "search",
                "params": {"query": query, "top_k": 5}
            }
            result = await self.orchestrator.execute_task("docs_agent", task)
            return {
                "answer": await self._format_docs_result(result),
                "sources": result if isinstance(result, list) else [],
                "agents_used": ["docs_agent"]
            }

        elif search_type == "git":
            # Поиск только по репозиторию
            task = {
                "action": "get_repo_status",
                "params": {}
            }
            result = await self.orchestrator.execute_task("git_agent", task)
            return {
                "answer": await self._format_git_result(result),
                "sources": [],
                "agents_used": ["git_agent"]
            }

        else:
            raise ValueError(f"Неизвестный тип поиска: {search_type}")

    async def get_system_status(self) -> Dict[str, Any]:
        """
        Получение статуса всей системы subagents.

        Returns:
            Словарь со статусом агентов и инструментов
        """
        logger.info("Получение статуса системы")

        # Получаем health check от оркестратора
        health_status = await self.orchestrator.health_check()

        return {
            "healthy": health_status.get("healthy", False),
            "agents": health_status.get("agents", {}),
            "tools": health_status.get("tools", {}),
        }

    def _analyze_question(self, query: str) -> List[str]:
        """
        Анализ вопроса для определения нужных агентов.

        Args:
            query: Вопрос пользователя

        Returns:
            Список имен агентов, которые нужны для ответа
        """
        query_lower = query.lower()
        agents_needed = []

        # Проверяем наличие ключевых слов для документации
        if any(keyword in query_lower for keyword in self.docs_keywords):
            agents_needed.append("docs_agent")

        # Проверяем наличие ключевых слов для git
        if any(keyword in query_lower for keyword in self.git_keywords):
            agents_needed.append("git_agent")

        # Если не нашли явных указаний, используем эвристику
        if not agents_needed:
            # По умолчанию - документация
            agents_needed.append("docs_agent")

        return agents_needed

    def _determine_git_action(self, query: str) -> str:
        """
        Определение конкретного действия для GitAgent на основе вопроса.

        Args:
            query: Вопрос пользователя

        Returns:
            Название действия для GitAgent
        """
        query_lower = query.lower()

        if "ветка" in query_lower or "branch" in query_lower:
            return "get_current_branch"
        elif "изменен" in query_lower or "modified" in query_lower or "diff" in query_lower:
            return "get_modified_files"
        elif "коммит" in query_lower or "commit" in query_lower:
            if "поиск" in query_lower or "search" in query_lower:
                return "search_commits"
            else:
                return "get_recent_commits"
        elif "pr" in query_lower or "pull request" in query_lower:
            return "get_pull_requests"
        elif "статистика" in query_lower or "stats" in query_lower:
            return "get_stats"
        else:
            # По умолчанию - статус репозитория
            return "get_repo_status"

    def _extract_git_params(self, query: str, action: str) -> Dict[str, Any]:
        """
        Извлечение параметров для GitAgent из вопроса.

        Args:
            query: Вопрос пользователя
            action: Действие для GitAgent

        Returns:
            Словарь с параметрами
        """
        params = {}

        # Извлекаем числа для limit
        numbers = re.findall(r'\d+', query)
        if numbers:
            limit = int(numbers[0])
            params["limit"] = min(limit, 50)  # Ограничиваем максимум 50

        # Для search_commits извлекаем поисковый запрос
        if action == "search_commits":
            # Пытаемся извлечь запрос после ключевых слов
            patterns = [
                r'поиск[^\w]*(["\']?)([^"\']+)\1',
                r'search[^\w]*(["\']?)([^"\']+)\1',
                r'найти[^\w]*(["\']?)([^"\']+)\1',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params["query"] = match.group(2).strip()
                    break

        # Для get_pull_requests определяем state
        if action == "get_pull_requests":
            if "закрыт" in query.lower() or "closed" in query.lower():
                params["state"] = "closed"
            elif "все" in query.lower() or "all" in query.lower():
                params["state"] = "all"
            else:
                params["state"] = "open"

        return params

    async def _format_combined_answer(
        self,
        query: str,
        results: List[Any],
        agents_used: List[str]
    ) -> Dict[str, Any]:
        """
        Форматирование объединенного ответа от нескольких агентов.

        Args:
            query: Исходный вопрос
            results: Результаты от агентов
            agents_used: Список использованных агентов

        Returns:
            Отформатированный ответ
        """
        answer_parts = []
        all_sources = []

        for agent_name, result in zip(agents_used, results):
            if result is None:
                continue

            if agent_name == "docs_agent":
                formatted = await self._format_docs_result(result)
                if formatted:
                    answer_parts.append(formatted)
                    if isinstance(result, list):
                        all_sources.extend(result)

            elif agent_name == "git_agent":
                formatted = await self._format_git_result(result)
                if formatted:
                    answer_parts.append(formatted)

        # Объединяем ответы
        if not answer_parts:
            final_answer = "К сожалению, не удалось найти информацию по вашему вопросу."
        else:
            final_answer = "\n\n---\n\n".join(answer_parts)

        return {
            "answer": final_answer,
            "sources": all_sources,
            "agents_used": agents_used
        }

    async def _format_docs_result(self, result: Any) -> str:
        """
        Форматирование результата от DocsAgent.

        Args:
            result: Результат от DocsAgent (обычно список DocumentChunk)

        Returns:
            Отформатированная строка
        """
        if not result:
            return ""

        if isinstance(result, list) and len(result) > 0:
            parts = ["📚 **Результаты поиска по документации:**\n"]
            
            # Инициализируем генератор ссылок
            link_generator = MCPLinkGenerator()

            for i, chunk in enumerate(result[:3], 1):  # Показываем первые 3
                if hasattr(chunk, 'content'):
                    content = chunk.content
                    score = chunk.score
                    source_file = chunk.metadata.get('source_file', 'unknown')
                    line_number = chunk.metadata.get('line_number', None)
                    if not source_file:
                        source = chunk.metadata.get('source', 'unknown')
                    else:
                        # Извлекаем только имя файла из пути
                        source = os.path.basename(source_file)
                else:
                    content = chunk.get('text', '')
                    score = chunk.get('similarity_score', 0.0)
                    source_file = chunk.get('source_file', 'unknown')
                    line_number = chunk.get('metadata', {}).get('line_number', None)
                    if not source_file:
                        source = chunk.get('metadata', {}).get('source', 'unknown')
                    else:
                        source = os.path.basename(source_file)

                # Создаем кликабельную ссылку если возможно
                if source_file != 'unknown':
                    try:
                        # Если путь относительный, делаем его абсолютным
                        if not source_file.startswith('/'):
                            abs_source_file = '/' + source_file
                        else:
                            abs_source_file = source_file
                        
                        clickable_source = link_generator.create_file_link(abs_source_file, line_number)
                        parts.append(f"\n**{i}. {clickable_source}** (релевантность: {score:.2f})")
                    except Exception:
                        # Если не удалось создать ссылку, используем обычное имя файла
                        parts.append(f"\n**{i}. {source}** (релевантность: {score:.2f})")
                else:
                    parts.append(f"\n**{i}. {source}** (релевантность: {score:.2f})")
                
                parts.append(f"{content[:500]}...")  # Первые 500 символов

            return "\n".join(parts)

        return str(result)

    async def _format_git_result(self, result: Any) -> str:
        """
        Форматирование результата от GitAgent.

        Args:
            result: Результат от GitAgent

        Returns:
            Отформатированная строка
        """
        if not result:
            return ""

        if isinstance(result, dict):
            # Форматируем статус репозитория
            if "branch" in result:
                parts = ["🔧 **Статус репозитория:**\n"]
                parts.append(f"**Ветка:** {result.get('branch', 'unknown')}")

                modified = result.get('modified_files', [])
                if modified:
                    parts.append(f"\n**Измененные файлы:** {len(modified)}")

                return "\n".join(parts)

            # Форматируем статистику
            elif "total_commits" in result:
                return f"📊 **Статистика:** {result.get('total_commits', 0)} коммитов"

        elif isinstance(result, list):
            # Форматируем список измененных файлов или коммитов
            if len(result) > 0:
                # Проверяем, это файлы или коммиты по первому элементу
                if isinstance(result[0], str):
                    # Это список файлов
                    parts = ["📁 **Измененные файлы:**\n"]
                    # Фильтруем пустые значения и сортируем
                    valid_files = [f for f in result if f and f.strip()]
                    for file_path in sorted(valid_files):
                        # Извлекаем только имя файла
                        file_name = file_path.split('/')[-1]
                        if file_name and file_name.strip():
                            parts.append(f"- `{file_name}`")
                    return "\n".join(parts)
                elif isinstance(result[0], dict):
                    # Это список коммитов
                    parts = ["📝 **Последние коммиты:**\n"]
                    for commit in result[:5]:  # Первые 5
                        hash_short = commit.get('hash', 'unknown')[:7]
                        message = commit.get('message', 'No message')
                        parts.append(f"- {hash_short}: {message}")
                    return "\n".join(parts)

        elif isinstance(result, str):
            return f"ℹ️ {result}"

        return str(result)

    async def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Валидация входных данных.

        Args:
            data: Словарь с входными данными

        Returns:
            True если данные валидны, False в противном случае
        """
        # Базовая валидация от родительского класса
        if not await super().validate_input(data):
            return False

        action = data.get("action", "answer_question")
        params = data.get("params", {})

        # Для answer_question и search требуется query
        if action in ["answer_question", "search"]:
            if not params.get("query"):
                logger.error(f"Отсутствует обязательный параметр 'query' для действия '{action}'")
                return False

        return True
