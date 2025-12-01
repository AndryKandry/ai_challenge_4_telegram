"""
GitHubMCPAgent - агент для работы с git-репозиторием через MCP Tools.

Новая версия, использующая систему Tools для работы с GitHub.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class GitHubMCPAgent(BaseAgent):
    """
    Агент для работы с git-репозиторием через MCP Tools.

    Поддерживаемые действия:
    - get_current_branch: получить текущую ветку
    - get_modified_files: получить список измененных файлов
    - get_repo_status: получить полный статус репозитория
    - get_file_diff: получить diff для файла
    - get_recent_commits: получить последние коммиты
    """

    def __init__(
        self,
        tool_manager,
        repo_path: str = ".",
        name: str = "github_mcp",
        enabled: bool = True
    ):
        """
        Инициализация GitHubMCPAgent.

        Args:
            tool_manager: Менеджер инструментов
            repo_path: Путь к git-репозиторию
            name: Имя агента
            enabled: Флаг активности
        """
        super().__init__(name, tool_manager, enabled)
        self.repo_path = Path(repo_path).resolve()

        # Определяем необходимые инструменты
        self.required_tools = ["github_mcp"]

        # Определяем альтернативные инструменты
        # В случае отказа github_mcp можно использовать git CLI
        self.preferred_tools = {
            "git_operations": ["github_mcp"]
        }

        # Проверяем, что это git-репозиторий
        if not (self.repo_path / ".git").exists():
            logger.warning(f"Директория {repo_path} не является git-репозиторием")

        logger.info(f"GitHubMCPAgent инициализирован для репозитория: {self.repo_path}")

    async def execute(self, task: Dict[str, Any]) -> Any:
        """
        Выполнение задачи агентом.

        Args:
            task: Словарь с параметрами:
                - action: название действия
                - params: параметры для действия

        Returns:
            Результат выполнения задачи

        Raises:
            ValueError: Если действие не поддерживается
        """
        action = task.get("action")
        params = task.get("params", {})

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

        Raises:
            Exception: При ошибке получения статуса
        """
        logger.info("Получение полного статуса репозитория")
        try:
            result = await self.call_tool("github_mcp", action="status", detailed=True)
            logger.info(f"Статус репозитория: {result}")
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

        return True
