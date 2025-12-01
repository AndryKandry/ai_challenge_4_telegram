"""
GitAgent - агент для работы с git-репозиторием через MCP Tools.

Агент использует систему Tools для получения информации о состоянии
репозитория, коммитах, изменениях и работы с GitHub API.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class GitAgent(BaseAgent):
    """
    Агент для работы с git-репозиторием через MCP Tools.

    Поддерживаемые действия:
    - get_current_branch: получить текущую ветку
    - get_modified_files: получить список измененных файлов
    - get_repo_status: получить полный статус репозитория
    - get_file_diff: получить diff для файла
    - get_recent_commits: получить последние коммиты
    - search_commits: поиск по истории коммитов
    - get_stats: получить статистику изменений
    - get_pull_requests: получить список PR (через GitHub API)
    """

    def __init__(
        self,
        tool_manager,
        repo_path: str = ".",
        name: str = "git_agent",
        enabled: bool = True,
        max_commits_limit: int = 100,
        max_files_limit: int = 500,
        cache_timeout: int = 300
    ):
        """
        Инициализация GitAgent.

        Args:
            tool_manager: Менеджер инструментов
            repo_path: Путь к git-репозиторию
            name: Имя агента
            enabled: Флаг активности
            max_commits_limit: Максимальное количество коммитов для получения (по умолчанию 100)
            max_files_limit: Максимальное количество файлов для обработки (по умолчанию 500)
            cache_timeout: Время жизни кеша в секундах (по умолчанию 300)
        """
        super().__init__(name, tool_manager, enabled)
        self.repo_path = Path(repo_path).resolve()

        # Лимиты для оптимизации работы с большими репозиториями
        self.max_commits_limit = max_commits_limit
        self.max_files_limit = max_files_limit
        self.cache_timeout = cache_timeout

        # Кеш для результатов (простой in-memory кеш)
        self._cache = {}
        self._cache_timestamps = {}

        # Определяем необходимые инструменты
        self.required_tools = []

        # Определяем альтернативные инструменты
        self.preferred_tools = {
            "git_operations": ["github_mcp", "github_get_user_repositories", "github_get_user_info", "github_get_repository_commits"]
        }

        # Регистрируем GitHubMCPTool если доступен
        if hasattr(tool_manager, 'tools') and 'github_mcp' not in tool_manager.tools:
            try:
                from tools import GitHubMCPTool
                github_tool = GitHubMCPTool(repo_path)
                tool_manager.register_tool(github_tool)
                logger.info("GitHubMCPTool зарегистрирован в ToolManager")
            except Exception as e:
                logger.warning(f"Не удалось зарегистрировать GitHubMCPTool: {e}")

        # Проверяем, что это git-репозиторий
        if not (self.repo_path / ".git").exists():
            logger.warning(f"Директория {repo_path} не является git-репозиторием")
        else:
            logger.info(f"GitAgent инициализирован для репозитория: {self.repo_path}")
            logger.info(f"Лимиты: commits={max_commits_limit}, files={max_files_limit}, cache={cache_timeout}s")

    async def execute(self, task: Dict[str, Any]) -> Any:
        """
        Выполнение задачи агентом.

        Args:
            task: Словарь с параметрами:
                - action: название действия
                - params: параметры для действия
                - context: дополнительный контекст (опционально)

        Returns:
            Результат выполнения задачи

        Raises:
            ValueError: Если действие не поддерживается
        """
        action = task.get("action")
        params = task.get("params", {})
        context = task.get("context", {})

        logger.info(f"GitAgent выполняет действие: {action}")

        if action == "get_current_branch":
            return await self.get_current_branch()
        elif action == "get_modified_files":
            return await self.get_modified_files()
        elif action == "get_repo_status":
            return await self.get_repo_status()
        elif action == "get_file_diff":
            return await self.get_file_diff(
                filepath=params.get("filepath", "")
            )
        elif action == "get_recent_commits":
            return await self.get_recent_commits(
                limit=params.get("limit", 10)
            )
        elif action == "search_commits":
            return await self.search_commits(
                query=params.get("query", ""),
                limit=params.get("limit", 20)
            )
        elif action == "get_stats":
            return await self.get_repository_stats()
        elif action == "get_pull_requests":
            return await self.get_pull_requests(
                state=params.get("state", "open"),
                limit=params.get("limit", 10)
            )
        else:
            raise ValueError(f"Неизвестное действие: {action}")

    async def get_current_branch(self) -> str:
        """
        Получить имя текущей ветки.

        Returns:
            Имя текущей ветки

        Raises:
            Exception: При ошибке получения ветки
        """
        logger.info("Получение текущей ветки")
        try:
            result = await self.call_tool("github_mcp", action="branch")
            logger.info(f"Текущая ветка: {result}")
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении текущей ветки: {e}")
            raise

    async def get_modified_files(self) -> List[str]:
        """
        Получить список измененных файлов (не закоммиченных).

        Returns:
            Список путей к измененным файлам

        Raises:
            Exception: При ошибке получения файлов
        """
        logger.info("Получение списка измененных файлов")
        try:
            status = await self.call_tool("github_mcp", action="status", detailed=False)
            modified_files = status.get("modified_files", [])
            logger.info(f"Найдено измененных файлов: {len(modified_files)}")
            return modified_files
        except Exception as e:
            logger.error(f"Ошибка при получении измененных файлов: {e}")
            raise

    async def get_repo_status(self) -> Dict[str, Any]:
        """
        Получить полный статус репозитория.

        Returns:
            Словарь с информацией о статусе:
                - branch: текущая ветка
                - modified_files: измененные файлы
                - staged_files: файлы в staging
                - untracked_files: неотслеживаемые файлы
                - ahead: количество коммитов впереди origin
                - behind: количество коммитов позади origin

        Raises:
            Exception: При ошибке получения статуса
        """
        logger.info("Получение полного статуса репозитория")
        try:
            result = await self.call_tool("github_mcp", action="status", detailed=True)
            logger.info(f"Статус репозитория получен")
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении статуса репозитория: {e}")
            raise

    async def get_file_diff(self, filepath: str) -> str:
        """
        Получить diff для указанного файла.

        Args:
            filepath: Путь к файлу относительно корня репозитория

        Returns:
            Diff файла в виде строки

        Raises:
            ValueError: Если файл не указан
            Exception: При ошибке получения diff
        """
        if not filepath:
            raise ValueError("Не указан путь к файлу")

        logger.info(f"Получение diff для файла: {filepath}")
        try:
            diff = await self.call_tool("github_mcp", action="diff", path=filepath)
            logger.info(f"Получен diff для файла {filepath}")
            return diff
        except Exception as e:
            logger.error(f"Ошибка при получении diff для файла {filepath}: {e}")
            raise

    async def get_recent_commits(self, limit: int = 10) -> List[Dict[str, str]]:
        """
        Получить список последних коммитов.

        Args:
            limit: Количество коммитов для получения

        Returns:
            Список словарей с информацией о коммитах:
                - hash: хеш коммита (короткий)
                - author: автор коммита
                - date: дата коммита
                - message: сообщение коммита

        Raises:
            Exception: При ошибке получения коммитов
        """
        logger.info(f"Получение последних {limit} коммитов")
        try:
            commits = await self.call_tool("github_mcp", action="log", limit=limit)
            logger.info(f"Получено коммитов: {len(commits)}")
            return commits
        except Exception as e:
            logger.error(f"Ошибка при получении коммитов: {e}")
            raise

    async def search_commits(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Поиск по истории коммитов.

        Args:
            query: Поисковый запрос (по сообщению коммита)
            limit: Максимальное количество результатов

        Returns:
            Список коммитов, соответствующих запросу

        Raises:
            Exception: При ошибке поиска
        """
        if not query:
            logger.warning("Пустой запрос для поиска коммитов")
            return []

        logger.info(f"Поиск коммитов по запросу: '{query}'")
        try:
            commits = await self.call_tool(
                "github_mcp",
                action="search_commits",
                query=query,
                limit=limit
            )
            logger.info(f"Найдено коммитов: {len(commits)}")
            return commits
        except Exception as e:
            logger.error(f"Ошибка при поиске коммитов: {e}")
            # Fallback: получаем все коммиты и фильтруем локально
            try:
                all_commits = await self.get_recent_commits(limit=100)
                filtered = [
                    c for c in all_commits
                    if query.lower() in c.get("message", "").lower()
                ]
                return filtered[:limit]
            except Exception:
                return []

    async def get_repository_stats(self) -> Dict[str, Any]:
        """
        Получить статистику изменений в репозитории.

        Returns:
            Словарь со статистикой:
                - total_commits: общее количество коммитов
                - total_contributors: количество контрибьюторов
                - files_changed: количество измененных файлов
                - insertions: количество добавленных строк
                - deletions: количество удаленных строк

        Raises:
            Exception: При ошибке получения статистики
        """
        logger.info("Получение статистики репозитория")
        try:
            stats = await self.call_tool("github_mcp", action="stats")
            logger.info(f"Статистика получена")
            return stats
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            # Возвращаем базовую статистику
            try:
                commits = await self.get_recent_commits(limit=1000)
                return {
                    "total_commits": len(commits),
                    "recent_commits_count": len(commits),
                    "error": str(e)
                }
            except Exception:
                return {"error": str(e)}

    async def get_pull_requests(
        self,
        state: str = "open",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Получить список Pull Requests из GitHub.

        Args:
            state: Состояние PR ("open", "closed", "all")
            limit: Максимальное количество результатов

        Returns:
            Список словарей с информацией о PR:
                - number: номер PR
                - title: заголовок
                - author: автор
                - state: состояние (open/closed)
                - created_at: дата создания
                - url: ссылка на PR

        Raises:
            Exception: При ошибке получения PR
        """
        logger.info(f"Получение PR (state={state}, limit={limit})")
        try:
            prs = await self.call_tool(
                "github_mcp",
                action="pull_requests",
                state=state,
                limit=limit
            )
            logger.info(f"Получено PR: {len(prs)}")
            return prs
        except Exception as e:
            logger.error(f"Ошибка при получении PR: {e}")
            raise

    async def format_status_report(self, include_commits: bool = True) -> str:
        """
        Форматирование отчета о состоянии репозитория.

        Args:
            include_commits: Включать ли информацию о последних коммитах

        Returns:
            Отформатированная строка с отчетом
        """
        try:
            status = await self.get_repo_status()
            report_parts = []

            report_parts.append("# Статус Git-репозитория\n")
            report_parts.append(f"**Текущая ветка:** {status.get('branch', 'unknown')}\n")

            # Информация о файлах
            modified = status.get('modified_files', [])
            staged = status.get('staged_files', [])
            untracked = status.get('untracked_files', [])

            if modified:
                report_parts.append(f"\n**Измененные файлы ({len(modified)}):**")
                for file in modified[:10]:  # Показываем первые 10
                    report_parts.append(f"- {file}")
                if len(modified) > 10:
                    report_parts.append(f"... и еще {len(modified) - 10} файлов")

            if staged:
                report_parts.append(f"\n**Файлы в staging ({len(staged)}):**")
                for file in staged[:10]:
                    report_parts.append(f"- {file}")

            if untracked:
                report_parts.append(f"\n**Неотслеживаемые файлы ({len(untracked)}):**")
                for file in untracked[:5]:
                    report_parts.append(f"- {file}")
                if len(untracked) > 5:
                    report_parts.append(f"... и еще {len(untracked) - 5} файлов")

            # Информация о коммитах
            if include_commits:
                try:
                    commits = await self.get_recent_commits(limit=5)
                    if commits:
                        report_parts.append("\n**Последние коммиты:**")
                        for commit in commits:
                            report_parts.append(
                                f"- {commit.get('hash', 'unknown')[:7]} "
                                f"{commit.get('message', 'No message')} "
                                f"({commit.get('author', 'Unknown')})"
                            )
                except Exception as e:
                    logger.warning(f"Не удалось получить коммиты: {e}")

            return "\n".join(report_parts)

        except Exception as e:
            logger.error(f"Ошибка при формировании отчета: {e}")
            return f"Ошибка при получении статуса репозитория: {e}"

    async def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Валидация входных данных для агента.

        Args:
            data: Словарь с входными данными

        Returns:
            True если данные валидны, False в противном случае
        """
        # Базовая валидация от родительского класса
        if not await super().validate_input(data):
            return False

        action = data.get("action")
        params = data.get("params", {})

        # Валидация в зависимости от действия
        if action == "get_file_diff":
            if not params.get("filepath"):
                logger.error("Отсутствует обязательный параметр 'filepath' для действия 'get_file_diff'")
                return False

        elif action == "search_commits":
            if not params.get("query"):
                logger.error("Отсутствует обязательный параметр 'query' для действия 'search_commits'")
                return False

        return True
