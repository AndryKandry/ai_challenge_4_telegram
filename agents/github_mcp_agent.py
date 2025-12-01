"""
GitHubMCPAgent - агент для работы с git-репозиторием.

Предоставляет функциональность для:
- Получения информации о текущей ветке
- Просмотра измененных файлов (git status)
- Получения diff для файлов
- Просмотра истории коммитов
- Интеграции с существующим MCP сервером GitHub
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class GitCommandError(Exception):
    """Исключение при ошибках выполнения git команд."""
    pass


class GitHubMCPAgent(BaseAgent):
    """
    Агент для работы с git-репозиторием через команды git.

    Поддерживаемые действия:
    - get_current_branch: получить текущую ветку
    - get_modified_files: получить список измененных файлов
    - get_repo_status: получить полный статус репозитория
    - get_file_diff: получить diff для файла
    - get_recent_commits: получить последние коммиты
    """

    def __init__(
        self,
        repo_path: str = ".",
        name: str = "github_mcp",
        enabled: bool = True
    ):
        """
        Инициализация GitHubMCPAgent.

        Args:
            repo_path: Путь к git-репозиторию
            name: Имя агента
            enabled: Флаг активности
        """
        super().__init__(name, enabled)
        self.repo_path = Path(repo_path).resolve()

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

    async def _run_git_command(
        self,
        args: List[str],
        check: bool = True
    ) -> str:
        """
        Выполнение git команды асинхронно.

        Args:
            args: Аргументы команды (без 'git')
            check: Проверять код возврата

        Returns:
            Вывод команды (stdout)

        Raises:
            GitCommandError: При ошибке выполнения команды
        """
        cmd = ["git"] + args

        try:
            # Выполняем команду асинхронно
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if check and process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise GitCommandError(
                    f"Git команда завершилась с ошибкой (код {process.returncode}): {error_msg}"
                )

            return stdout.decode().strip()

        except FileNotFoundError:
            raise GitCommandError("Git не установлен или недоступен в PATH")
        except Exception as e:
            raise GitCommandError(f"Ошибка при выполнении git команды: {e}")

    async def get_current_branch(self) -> str:
        """
        Получить имя текущей ветки.

        Returns:
            Имя текущей ветки

        Raises:
            GitCommandError: При ошибке получения ветки
        """
        logger.info("Получение текущей ветки")
        try:
            branch = await self._run_git_command(["branch", "--show-current"])
            logger.info(f"Текущая ветка: {branch}")
            return branch
        except GitCommandError as e:
            logger.error(f"Ошибка при получении текущей ветки: {e}")
            raise

    async def get_modified_files(self) -> List[str]:
        """
        Получить список измененных файлов (не закоммиченных).

        Returns:
            Список путей к измененным файлам

        Raises:
            GitCommandError: При ошибке получения файлов
        """
        logger.info("Получение списка измененных файлов")
        try:
            # Получаем измененные и неотслеживаемые файлы
            status_output = await self._run_git_command(
                ["status", "--porcelain"]
            )

            if not status_output:
                logger.info("Нет измененных файлов")
                return []

            # Парсим вывод git status --porcelain
            modified_files = []
            for line in status_output.split("\n"):
                if line:
                    # Формат: XY filename (XY - коды статуса)
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        status_code = parts[0]
                        filepath = parts[1]
                        modified_files.append(filepath)

            logger.info(f"Найдено измененных файлов: {len(modified_files)}")
            return modified_files

        except GitCommandError as e:
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
                - ahead: количество коммитов впереди
                - behind: количество коммитов позади

        Raises:
            GitCommandError: При ошибке получения статуса
        """
        logger.info("Получение полного статуса репозитория")

        try:
            # Получаем текущую ветку
            branch = await self.get_current_branch()

            # Получаем полный статус
            status_output = await self._run_git_command(
                ["status", "--porcelain", "--branch"]
            )

            modified_files = []
            staged_files = []
            untracked_files = []
            ahead = 0
            behind = 0

            for line in status_output.split("\n"):
                if not line:
                    continue

                # Обработка информации о ветке
                if line.startswith("##"):
                    # Формат: ## branch...origin/branch [ahead N, behind M]
                    if "[ahead" in line:
                        ahead_part = line.split("[ahead")[1].split("]")[0]
                        if "," in ahead_part:
                            ahead = int(ahead_part.split(",")[0].strip())
                        else:
                            ahead = int(ahead_part.strip())

                    if "behind" in line:
                        behind_part = line.split("behind")[1].split("]")[0]
                        behind = int(behind_part.strip().rstrip(","))

                    continue

                # Обработка файлов
                status_code = line[:2]
                filepath = line[3:]

                # M - modified, A - added, D - deleted, R - renamed, etc.
                if status_code[0] != " " and status_code[0] != "?":
                    staged_files.append(filepath)

                if status_code[1] != " " and status_code[1] != "?":
                    modified_files.append(filepath)

                if status_code == "??":
                    untracked_files.append(filepath)

            result = {
                "branch": branch,
                "modified_files": modified_files,
                "staged_files": staged_files,
                "untracked_files": untracked_files,
                "ahead": ahead,
                "behind": behind
            }

            logger.info(f"Статус репозитория: {result}")
            return result

        except GitCommandError as e:
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
            GitCommandError: При ошибке получения diff
            ValueError: Если файл не указан
        """
        if not filepath:
            raise ValueError("Не указан путь к файлу")

        logger.info(f"Получение diff для файла: {filepath}")

        try:
            diff = await self._run_git_command(
                ["diff", filepath],
                check=False  # Не генерировать ошибку, если diff пустой
            )

            if not diff:
                logger.info(f"Нет изменений в файле: {filepath}")
                return f"Нет изменений в файле {filepath}"

            logger.info(f"Получен diff для файла {filepath} ({len(diff)} символов)")
            return diff

        except GitCommandError as e:
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
            GitCommandError: При ошибке получения коммитов
        """
        logger.info(f"Получение последних {limit} коммитов")

        try:
            # Формат: hash|author|date|message
            log_format = "--pretty=format:%h|%an|%ar|%s"
            log_output = await self._run_git_command(
                ["log", f"-{limit}", log_format]
            )

            if not log_output:
                logger.info("История коммитов пуста")
                return []

            commits = []
            for line in log_output.split("\n"):
                if line:
                    parts = line.split("|", maxsplit=3)
                    if len(parts) == 4:
                        commit = {
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3]
                        }
                        commits.append(commit)

            logger.info(f"Получено коммитов: {len(commits)}")
            return commits

        except GitCommandError as e:
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
