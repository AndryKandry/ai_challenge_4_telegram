"""
MCP Tools - инструменты для работы с MCP серверами.

Предоставляет инструменты для:
- Работы с GitHub через MCP (status, branch, diff, log)
- Работы с файловой системой через MCP (чтение файлов, навигация)
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool, ToolType, ToolFailureError

logger = logging.getLogger(__name__)


class MCPTool(BaseTool):
    """
    Универсальный инструмент для работы с MCP серверами.
    
    Позволяет вызывать любые инструменты из MCP сервера
    через универсальный интерфейс.
    """

    def __init__(self, name: str, mcp_client, tool_info: Dict[str, Any]):
        """
        Инициализация MCPTool.
        
        Args:
            name: Имя инструмента
            mcp_client: Экземпляр MCP клиента
            tool_info: Информация об инструменте от MCP сервера
        """
        super().__init__(
            name=name,
            tool_type=ToolType.MCP,
            description=tool_info.get('description', 'MCP Tool')
        )
        self.mcp_client = mcp_client
        self.tool_info = tool_info
        self.tool_name = tool_info.get('name', name)
        
        logger.info(f"MCPTool инициализирован: {self.tool_name}")

    async def execute(self, **params) -> Any:
        """
        Выполнить инструмент MCP сервера.
        
        Args:
            **params: Параметры для передачи в инструмент
            
        Returns:
            Результат выполнения инструмента
            
        Raises:
            ToolFailureError: При ошибке выполнения
        """
        logger.info(f"Выполнение MCP инструмента: {self.tool_name}")
        
        if not self.mcp_client.is_connected():
            try:
                await self.mcp_client.connect()
            except Exception as e:
                raise ToolFailureError(f"Не удалось подключиться к MCP серверу: {e}")
        
        try:
            # Вызываем инструмент через MCP клиент
            result = await self.mcp_client.session.call_tool(
                self.tool_name, 
                arguments=params
            )
            
            logger.info(f"MCP инструмент {self.tool_name} выполнен успешно")
            return result.content if hasattr(result, 'content') else result
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении MCP инструмента '{self.tool_name}': {e}")
            raise ToolFailureError(f"Ошибка MCP инструмента: {e}")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров."""
        # Базовая валидация - MCP инструменты сами валидируют параметры
        return True

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": self.tool_info.get('inputSchema', {}),
            "mcp_tool_name": self.tool_name
        }


class GitHubMCPTool(BaseTool):
    """
    Инструмент для работы с GitHub через MCP или прямые git команды.

    Поддерживает операции:
    - branch: получение текущей ветки
    - status: статус репозитория
    - diff: diff файла
    - log: история коммитов
    """

    def __init__(self, repo_path: str = "."):
        """
        Инициализация GitHubMCPTool.

        Args:
            repo_path: Путь к git-репозиторию
        """
        super().__init__(
            name="github_mcp",
            tool_type=ToolType.MCP,
            description="Interact with GitHub repository via MCP or git commands"
        )
        self.repo_path = Path(repo_path).resolve()

        # Проверяем, что это git-репозиторий
        if not (self.repo_path / ".git").exists():
            logger.warning(f"Директория {repo_path} не является git-репозиторием")
            self.set_available(False)

        logger.info(f"GitHubMCPTool инициализирован для: {self.repo_path}")

    async def execute(
        self,
        action: str,
        **params
    ) -> Any:
        """
        Выполнить git операцию.

        Args:
            action: Тип операции (branch, status, diff, log)
            **params: Параметры для операции:
                - path: путь к файлу (для diff)
                - limit: количество коммитов (для log)
                - detailed: детальный вывод (для status)

        Returns:
            Результат выполнения операции

        Raises:
            ToolFailureError: При ошибке выполнения операции
            ValueError: При неизвестном действии
        """
        logger.info(f"Выполнение GitHub MCP операции: {action}")

        try:
            if action == "branch":
                return await self._get_current_branch()
            elif action == "status":
                detailed = params.get("detailed", False)
                return await self._get_status(detailed)
            elif action == "diff":
                path = params.get("path")
                return await self._get_diff(path)
            elif action == "log":
                limit = params.get("limit", 10)
                return await self._get_log(limit)
            else:
                raise ValueError(f"Неизвестное действие: {action}")

        except Exception as e:
            logger.error(f"Ошибка при выполнении GitHub MCP операции '{action}': {e}")
            raise ToolFailureError(f"Ошибка git операции: {e}")

    async def _run_git_command(self, args: List[str]) -> str:
        """
        Выполнить git команду.

        Args:
            args: Аргументы команды (без 'git')

        Returns:
            Вывод команды

        Raises:
            ToolFailureError: При ошибке выполнения
        """
        cmd = ["git"] + args

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise ToolFailureError(
                    f"Git команда завершилась с ошибкой: {error_msg}"
                )

            return stdout.decode().strip()

        except FileNotFoundError:
            raise ToolFailureError("Git не установлен или недоступен")
        except Exception as e:
            raise ToolFailureError(f"Ошибка выполнения git команды: {e}")

    async def _get_current_branch(self) -> str:
        """Получить текущую ветку."""
        return await self._run_git_command(["branch", "--show-current"])

    async def _get_status(self, detailed: bool = False) -> Dict[str, Any]:
        """
        Получить статус репозитория.

        Args:
            detailed: Детальный вывод с информацией о файлах

        Returns:
            Словарь со статусом
        """
        if detailed:
            # Детальный статус
            status_output = await self._run_git_command(
                ["status", "--porcelain", "--branch"]
            )

            branch = await self._get_current_branch()
            modified_files = []
            staged_files = []
            untracked_files = []

            for line in status_output.split("\n"):
                if not line or line.startswith("##"):
                    continue

                status_code = line[:2]
                filepath = line[3:]

                if status_code[0] != " " and status_code[0] != "?":
                    staged_files.append(filepath)

                if status_code[1] != " " and status_code[1] != "?":
                    modified_files.append(filepath)

                if status_code == "??":
                    untracked_files.append(filepath)

            return {
                "branch": branch,
                "modified_files": modified_files,
                "staged_files": staged_files,
                "untracked_files": untracked_files
            }
        else:
            # Простой статус
            status_output = await self._run_git_command(["status", "--porcelain"])
            modified_files = []

            for line in status_output.split("\n"):
                if line:
                    filepath = line[3:]
                    modified_files.append(filepath)

            return {"modified_files": modified_files}

    async def _get_diff(self, path: Optional[str] = None) -> str:
        """
        Получить diff.

        Args:
            path: Путь к файлу (опционально)

        Returns:
            Diff в виде строки
        """
        if path:
            return await self._run_git_command(["diff", path])
        else:
            return await self._run_git_command(["diff"])

    async def _get_log(self, limit: int = 10) -> List[Dict[str, str]]:
        """
        Получить историю коммитов.

        Args:
            limit: Количество коммитов

        Returns:
            Список коммитов
        """
        log_format = "--pretty=format:%h|%an|%ar|%s"
        log_output = await self._run_git_command(["log", f"-{limit}", log_format])

        commits = []
        for line in log_output.split("\n"):
            if line:
                parts = line.split("|", maxsplit=3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3]
                    })

        return commits

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров."""
        if "action" not in params:
            logger.error("Отсутствует обязательный параметр 'action'")
            return False

        action = params["action"]
        if action not in ["branch", "status", "diff", "log"]:
            logger.error(f"Неизвестное действие: {action}")
            return False

        return True

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {
                "action": {
                    "type": "string",
                    "description": "Git операция",
                    "enum": ["branch", "status", "diff", "log"]
                },
                "path": {
                    "type": "string",
                    "description": "Путь к файлу (для diff)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Количество коммитов (для log)",
                    "default": 10
                },
                "detailed": {
                    "type": "boolean",
                    "description": "Детальный вывод (для status)",
                    "default": False
                }
            },
            "required": ["action"]
        }


class FileSystemMCPTool(BaseTool):
    """
    Инструмент для работы с файловой системой через MCP.

    Поддерживает операции:
    - read_file: чтение файла
    - list_directory: список файлов в директории
    - get_file_info: информация о файле
    """

    def __init__(self, allowed_paths: Optional[List[str]] = None):
        """
        Инициализация FileSystemMCPTool.

        Args:
            allowed_paths: Список разрешенных путей (для безопасности)
        """
        super().__init__(
            name="filesystem_mcp",
            tool_type=ToolType.MCP,
            description="Interact with filesystem via MCP"
        )
        self.allowed_paths = [Path(p).resolve() for p in (allowed_paths or ["."])]
        logger.info(f"FileSystemMCPTool инициализирован: {self.allowed_paths}")

    async def execute(
        self,
        action: str,
        **params
    ) -> Any:
        """
        Выполнить операцию с файловой системой.

        Args:
            action: Тип операции (read_file, list_directory, get_file_info)
            **params: Параметры для операции:
                - path: путь к файлу/директории

        Returns:
            Результат выполнения операции

        Raises:
            ToolFailureError: При ошибке выполнения операции
            ValueError: При неизвестном действии
        """
        logger.info(f"Выполнение FileSystem MCP операции: {action}")

        try:
            if action == "read_file":
                path = params.get("path")
                return await self._read_file(path)
            elif action == "list_directory":
                path = params.get("path", ".")
                return await self._list_directory(path)
            elif action == "get_file_info":
                path = params.get("path")
                return await self._get_file_info(path)
            else:
                raise ValueError(f"Неизвестное действие: {action}")

        except Exception as e:
            logger.error(f"Ошибка при выполнении FileSystem MCP операции '{action}': {e}")
            raise ToolFailureError(f"Ошибка файловой операции: {e}")

    def _check_path_allowed(self, path: str) -> Path:
        """
        Проверить, разрешен ли доступ к пути.

        Args:
            path: Путь для проверки

        Returns:
            Абсолютный путь

        Raises:
            ToolFailureError: Если путь не разрешен
        """
        target_path = Path(path).resolve()

        # Проверяем, что путь находится в одной из разрешенных директорий
        allowed = any(
            str(target_path).startswith(str(allowed))
            for allowed in self.allowed_paths
        )

        if not allowed:
            raise ToolFailureError(f"Доступ к пути запрещен: {path}")

        return target_path

    async def _read_file(self, path: str) -> str:
        """
        Прочитать файл.

        Args:
            path: Путь к файлу

        Returns:
            Содержимое файла

        Raises:
            ToolFailureError: При ошибке чтения
        """
        if not path:
            raise ValueError("Не указан путь к файлу")

        file_path = self._check_path_allowed(path)

        if not file_path.exists():
            raise ToolFailureError(f"Файл не найден: {path}")

        if not file_path.is_file():
            raise ToolFailureError(f"Путь не является файлом: {path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise ToolFailureError(f"Ошибка чтения файла: {e}")

    async def _list_directory(self, path: str) -> List[Dict[str, Any]]:
        """
        Получить список файлов в директории.

        Args:
            path: Путь к директории

        Returns:
            Список файлов с информацией
        """
        dir_path = self._check_path_allowed(path)

        if not dir_path.exists():
            raise ToolFailureError(f"Директория не найдена: {path}")

        if not dir_path.is_dir():
            raise ToolFailureError(f"Путь не является директорией: {path}")

        try:
            items = []
            for item in dir_path.iterdir():
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "is_file": item.is_file(),
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None
                })
            return items
        except Exception as e:
            raise ToolFailureError(f"Ошибка чтения директории: {e}")

    async def _get_file_info(self, path: str) -> Dict[str, Any]:
        """
        Получить информацию о файле.

        Args:
            path: Путь к файлу

        Returns:
            Словарь с информацией о файле
        """
        file_path = self._check_path_allowed(path)

        if not file_path.exists():
            raise ToolFailureError(f"Путь не найден: {path}")

        try:
            stat = file_path.stat()
            return {
                "name": file_path.name,
                "path": str(file_path),
                "is_file": file_path.is_file(),
                "is_dir": file_path.is_dir(),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime
            }
        except Exception as e:
            raise ToolFailureError(f"Ошибка получения информации о файле: {e}")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров."""
        if "action" not in params:
            logger.error("Отсутствует обязательный параметр 'action'")
            return False

        action = params["action"]
        if action not in ["read_file", "list_directory", "get_file_info"]:
            logger.error(f"Неизвестное действие: {action}")
            return False

        if action in ["read_file", "get_file_info"] and "path" not in params:
            logger.error(f"Отсутствует обязательный параметр 'path' для действия '{action}'")
            return False

        return True

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {
                "action": {
                    "type": "string",
                    "description": "Файловая операция",
                    "enum": ["read_file", "list_directory", "get_file_info"]
                },
                "path": {
                    "type": "string",
                    "description": "Путь к файлу/директории"
                }
            },
            "required": ["action"]
        }
