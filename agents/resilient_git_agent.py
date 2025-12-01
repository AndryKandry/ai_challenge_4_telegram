"""
ResilientGitAgent - улучшенный GitAgent с множественными fallback механизмами.

Обеспечивает отказоустойчивость при недоступности различных инструментов
и предоставляет базовую функциональность даже при полной недоступности git.
"""

import logging
import subprocess
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import asyncio
from datetime import datetime

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResilientGitAgent(BaseAgent):
    """
    Улучшенный GitAgent с множественными fallback механизмами.

    Цепочка fallback для git операций:
    1. github_mcp (MCP tool) - предпочтительный
    2. git_cli (встроенные git команды) - средний приоритет  
    3. subprocess_git (прямой вызов git) - низкий приоритет
    4. basic_response (базовая информация) - последний fallback
    """

    def __init__(
        self,
        tool_manager,
        repo_path: str = ".",
        name: str = "resilient_git_agent",
        enabled: bool = True,
        max_commits_limit: int = 100,
        max_files_limit: int = 500,
        cache_timeout: int = 300,
        enable_fallback: bool = True
    ):
        """
        Инициализация ResilientGitAgent.

        Args:
            tool_manager: Менеджер инструментов
            repo_path: Путь к git-репозиторию
            name: Имя агента
            enabled: Флаг активности
            max_commits_limit: Максимальное количество коммитов
            max_files_limit: Максимальное количество файлов
            cache_timeout: Время жизни кеша в секундах
            enable_fallback: Включить ли fallback механизмы
        """
        super().__init__(name, tool_manager, enabled)
        self.repo_path = Path(repo_path).resolve()
        self.max_commits_limit = max_commits_limit
        self.max_files_limit = max_files_limit
        self.cache_timeout = cache_timeout
        self.enable_fallback = enable_fallback

        # Цепочка fallback инструментов
        self.fallback_chain = {
            "github_mcp": {
                "priority": 1,
                "fallback": "git_cli",
                "description": "MCP GitHub tool"
            },
            "git_cli": {
                "priority": 2, 
                "fallback": "subprocess_git",
                "description": "Built-in git commands"
            },
            "subprocess_git": {
                "priority": 3,
                "fallback": "basic_response",
                "description": "Direct subprocess git calls"
            },
            "basic_response": {
                "priority": 4,
                "fallback": None,
                "description": "Basic cached/error response"
            }
        }

        # Кеш для результатов
        self._cache = {}
        self._cache_timestamps = {}

        # Статистика использования fallback
        self.fallback_stats = {
            "github_mcp_success": 0,
            "github_mcp_failed": 0,
            "git_cli_success": 0,
            "git_cli_failed": 0,
            "subprocess_git_success": 0,
            "subprocess_git_failed": 0,
            "basic_response_used": 0
        }

        # Проверяем, что это git-репозиторий
        self._validate_repository()

        logger.info(f"ResilientGitAgent инициализирован для: {self.repo_path}")
        logger.info(f"Fallback enabled: {enable_fallback}, Cache timeout: {cache_timeout}s")

    def _validate_repository(self) -> None:
        """Проверяет, что директория является git репозиторием."""
        if not (self.repo_path / ".git").exists():
            logger.warning(f"Директория {self.repo_path} не является git-репозиторием")
            self.is_git_repo = False
        else:
            self.is_git_repo = True
            logger.info(f"Git репозиторий подтвержден: {self.repo_path}")

    async def execute(self, task: Dict[str, Any]) -> Any:
        """
        Выполнение задачи с fallback механизмами.

        Args:
            task: Словарь с параметрами задачи

        Returns:
            Результат выполнения с информацией о использованном методе
        """
        action = task.get("action")
        params = task.get("params", {})
        context = task.get("context", {})

        logger.info(f"ResilientGitAgent выполняет действие: {action}")

        try:
            if action == "get_current_branch":
                return await self._execute_with_fallback(
                    action, params, self._get_current_branch_fallbacks
                )
            elif action == "get_modified_files":
                return await self._execute_with_fallback(
                    action, params, self._get_modified_files_fallbacks
                )
            elif action == "get_repo_status":
                return await self._execute_with_fallback(
                    action, params, self._get_repo_status_fallbacks
                )
            elif action == "get_recent_commits":
                return await self._execute_with_fallback(
                    action, params, self._get_recent_commits_fallbacks
                )
            elif action == "search_commits":
                return await self._execute_with_fallback(
                    action, params, self._search_commits_fallbacks
                )
            elif action == "get_stats":
                return await self._execute_with_fallback(
                    action, params, self._get_stats_fallbacks
                )
            else:
                raise ValueError(f"Неизвестное действие: {action}")

        except Exception as e:
            logger.error(f"Критическая ошибка при выполнении {action}: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_used": "none",
                "data": None
            }

    async def _execute_with_fallback(
        self,
        action: str,
        params: Dict[str, Any],
        fallback_handlers: Dict[str, callable]
    ) -> Dict[str, Any]:
        """
        Выполняет действие с цепочкой fallback.

        Args:
            action: Название действия
            params: Параметры действия
            fallback_handlers: Обработчики для каждого уровня fallback

        Returns:
            Результат выполнения с метаданными
        """
        if not self.enable_fallback:
            # Без fallback пробуем только основной метод
            return await self._try_single_method("github_mcp", action, params, fallback_handlers)

        current_tool = "github_mcp"
        attempts = []
        
        while current_tool:
            try:
                # Проверяем кеш сначала
                cache_key = self._get_cache_key(action, params, current_tool)
                if cached_result := self._get_from_cache(cache_key):
                    logger.info(f"Использован кеш для {action} через {current_tool}")
                    self._update_stats(current_tool, success=True)
                    return {
                        "success": True,
                        "data": cached_result,
                        "method": current_tool,
                        "from_cache": True,
                        "attempts": attempts
                    }

                # Пробуем выполнить через текущий инструмент
                result = await fallback_handlers[current_tool](params)
                
                if result is not None:
                    # Кешируем успешный результат
                    self._cache_result(cache_key, result)
                    self._update_stats(current_tool, success=True)
                    
                    return {
                        "success": True,
                        "data": result,
                        "method": current_tool,
                        "from_cache": False,
                        "attempts": attempts
                    }

            except Exception as e:
                attempts.append({
                    "method": current_tool,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                logger.warning(f"Метод {current_tool} завершился с ошибкой: {e}")
                self._update_stats(current_tool, success=False)

            # Переходим к следующему уровню fallback
            current_tool = self.fallback_chain[current_tool]["fallback"]

        # Все методы завершились ошибкой
        logger.error(f"Все fallback методы для {action} завершились ошибкой")
        self.fallback_stats["basic_response_used"] += 1

        return {
            "success": False,
            "error": "Все методы недоступны",
            "method": "none",
            "from_cache": False,
            "attempts": attempts,
            "data": self._get_basic_response(action, params)
        }

    async def _get_current_branch_fallbacks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback методы для получения текущей ветки."""
        handlers = {
            "github_mcp": lambda p: self._call_github_mcp("branch"),
            "git_cli": lambda p: self._call_git_cli("branch"),
            "subprocess_git": lambda p: self._call_subprocess_git(["branch", "--show-current"]),
            "basic_response": lambda p: self._get_cached_branch()
        }

        return await self._try_handlers(handlers, params)

    async def _get_modified_files_fallbacks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback методы для получения измененных файлов."""
        handlers = {
            "github_mcp": lambda p: self._call_github_mcp("status", detailed=False),
            "git_cli": lambda p: self._call_git_cli("status", detailed=False),
            "subprocess_git": lambda p: self._call_subprocess_git(["status", "--porcelain"]),
            "basic_response": lambda p: self._get_cached_modified_files()
        }

        return await self._try_handlers(handlers, params)

    async def _get_repo_status_fallbacks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback методы для получения статуса репозитория."""
        handlers = {
            "github_mcp": lambda p: self._call_github_mcp("status", detailed=True),
            "git_cli": lambda p: self._call_git_cli("status", detailed=True),
            "subprocess_git": lambda p: self._call_subprocess_git(["status", "--branch", "--porcelain=v2"]),
            "basic_response": lambda p: self._get_cached_repo_status()
        }

        return await self._try_handlers(handlers, params)

    async def _get_recent_commits_fallbacks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback методы для получения последних коммитов."""
        limit = params.get("limit", 10)
        
        handlers = {
            "github_mcp": lambda p: self._call_github_mcp("log", limit=limit),
            "git_cli": lambda p: self._call_git_cli("log", limit=limit),
            "subprocess_git": lambda p: self._call_subprocess_git([
                "log", f"-{limit}", "--pretty=format:%H|%an|%ar|%s"
            ]),
            "basic_response": lambda p: self._get_cached_commits(limit)
        }

        return await self._try_handlers(handlers, params)

    async def _search_commits_fallbacks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback методы для поиска коммитов."""
        query = params.get("query", "")
        limit = params.get("limit", 20)
        
        handlers = {
            "github_mcp": lambda p: self._call_github_mcp("search_commits", query=query, limit=limit),
            "git_cli": lambda p: self._call_git_cli("search_commits", query=query, limit=limit),
            "subprocess_git": lambda p: self._call_subprocess_git([
                "log", f"--grep={query}", f"-{limit}", "--pretty=format:%H|%an|%ar|%s"
            ]),
            "basic_response": lambda p: self._search_cached_commits(query, limit)
        }

        return await self._try_handlers(handlers, params)

    async def _get_stats_fallbacks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback методы для получения статистики."""
        handlers = {
            "github_mcp": lambda p: self._call_github_mcp("stats"),
            "git_cli": lambda p: self._call_git_cli("stats"),
            "subprocess_git": lambda p: self._call_subprocess_git(["log", "--stat", "--oneline", "-10"]),
            "basic_response": lambda p: self._get_cached_stats()
        }

        return await self._try_handlers(handlers, params)

    async def _try_handlers(self, handlers: Dict[str, callable], params: Dict[str, Any]) -> Any:
        """Пробует выполнить обработчики и возвращает результат или None."""
        for method, handler in handlers.items():
            try:
                result = await asyncio.to_thread(handler, params)
                if result is not None:
                    return result
            except Exception as e:
                logger.debug(f"Handler {method} failed: {e}")
                continue
        return None

    async def _call_github_mcp(self, action: str, **kwargs) -> Any:
        """Вызывает github_mcp инструмент."""
        return await self.call_tool("github_mcp", action=action, **kwargs)

    async def _call_git_cli(self, action: str, **kwargs) -> Any:
        """Вызывает встроенные git команды."""
        # Здесь должна быть реализация встроенных git команд
        # Временно используем subprocess как fallback
        if action == "branch":
            return await self._call_subprocess_git(["branch", "--show-current"])
        elif action == "status":
            detailed = kwargs.get("detailed", False)
            if detailed:
                return await self._call_subprocess_git(["status", "--branch", "--porcelain=v2"])
            else:
                return await self._call_subprocess_git(["status", "--porcelain"])
        elif action == "log":
            limit = kwargs.get("limit", 10)
            return await self._call_subprocess_git([
                "log", f"-{limit}", "--pretty=format:%H|%an|%ar|%s"
            ])
        else:
            raise ValueError(f"Unsupported git CLI action: {action}")

    async def _call_subprocess_git(self, cmd: List[str]) -> Any:
        """Выполняет git команду через subprocess."""
        if not self.is_git_repo:
            raise Exception("Not a git repository")

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git"] + cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                raise Exception(f"Git command failed: {result.stderr}")

            return self._parse_git_output(cmd[0], result.stdout.strip())

        except subprocess.TimeoutExpired:
            raise Exception("Git command timeout")
        except FileNotFoundError:
            raise Exception("Git not found in system")

    def _parse_git_output(self, cmd: str, output: str) -> Any:
        """Парсит вывод git команд."""
        if cmd == "branch" and output:
            return output
        elif cmd == "status":
            return self._parse_status_output(output)
        elif cmd == "log":
            return self._parse_log_output(output)
        elif cmd == "stats":
            return {"raw_output": output}
        else:
            return output

    def _parse_status_output(self, output: str) -> Dict[str, Any]:
        """Парсит вывод git status."""
        lines = output.split('\n')
        modified_files = []
        staged_files = []
        untracked_files = []
        current_branch = "unknown"

        for line in lines:
            if line.startswith('# branch.head '):
                current_branch = line.split(' ')[2]
            elif len(line) >= 3 and line[1] == ' ':
                status = line[0]
                filepath = line[3:]
                if status == 'M':
                    modified_files.append(filepath)
                elif status == 'A':
                    staged_files.append(filepath)
                elif status == '??':
                    untracked_files.append(filepath)

        return {
            "branch": current_branch,
            "modified_files": modified_files,
            "staged_files": staged_files,
            "untracked_files": untracked_files,
            "is_clean": len(modified_files) == 0 and len(staged_files) == 0
        }

    def _parse_log_output(self, output: str) -> List[Dict[str, str]]:
        """Парсит вывод git log."""
        if not output:
            return []

        commits = []
        for line in output.split('\n'):
            if line:
                parts = line.split('|')
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3]
                    })

        return commits

    def _get_cache_key(self, action: str, params: Dict[str, Any], method: str) -> str:
        """Генерирует ключ для кеша."""
        import hashlib
        params_str = str(sorted(params.items()))
        content = f"{action}_{method}_{params_str}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Any:
        """Получает результат из кеша."""
        if cache_key in self._cache:
            timestamp = self._cache_timestamps.get(cache_key, 0)
            if datetime.now().timestamp() - timestamp < self.cache_timeout:
                return self._cache[cache_key]
            else:
                # Удаляем устаревший кеш
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
        return None

    def _cache_result(self, cache_key: str, result: Any) -> None:
        """Сохраняет результат в кеш."""
        self._cache[cache_key] = result
        self._cache_timestamps[cache_key] = datetime.now().timestamp()

    def _update_stats(self, method: str, success: bool) -> None:
        """Обновляет статистику использования методов."""
        if success:
            self.fallback_stats[f"{method}_success"] += 1
        else:
            self.fallback_stats[f"{method}_failed"] += 1

    def _get_basic_response(self, action: str, params: Dict[str, Any]) -> Any:
        """Возвращает базовый ответ при недоступности всех методов."""
        if action == "get_current_branch":
            return {"branch": "unknown", "error": "All git methods unavailable"}
        elif action == "get_modified_files":
            return {"modified_files": [], "error": "All git methods unavailable"}
        elif action == "get_repo_status":
            return {
                "branch": "unknown",
                "modified_files": [],
                "staged_files": [],
                "untracked_files": [],
                "error": "All git methods unavailable"
            }
        elif action == "get_recent_commits":
            return []
        elif action == "search_commits":
            return []
        elif action == "get_stats":
            return {"error": "All git methods unavailable"}
        else:
            return None

    def _get_cached_branch(self) -> Dict[str, str]:
        """Возвращает закешированную информацию о ветке."""
        return {"branch": "unknown", "cached": True}

    def _get_cached_modified_files(self) -> Dict[str, Any]:
        """Возвращает закешированные измененные файлы."""
        return {"modified_files": [], "cached": True}

    def _get_cached_repo_status(self) -> Dict[str, Any]:
        """Возвращает закешированный статус репозитория."""
        return {
            "branch": "unknown",
            "modified_files": [],
            "staged_files": [],
            "untracked_files": [],
            "cached": True
        }

    def _get_cached_commits(self, limit: int) -> List[Dict[str, str]]:
        """Возвращает закешированные коммиты."""
        return []

    def _search_cached_commits(self, query: str, limit: int) -> List[Dict[str, str]]:
        """Ищет в закешированных коммитах."""
        return []

    def _get_cached_stats(self) -> Dict[str, Any]:
        """Возвращает закешированную статистику."""
        return {"cached": True, "error": "Git methods unavailable"}

    def get_fallback_stats(self) -> Dict[str, Any]:
        """Возвращает статистику использования fallback механизмов."""
        return self.fallback_stats.copy()

    def clear_cache(self) -> None:
        """Очищает кеш."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Cache cleared")

    async def validate_input(self, data: Dict[str, Any]) -> bool:
        """Валидация входных данных."""
        if not await super().validate_input(data):
            return False

        action = data.get("action")
        params = data.get("params", {})

        if action == "get_file_diff":
            if not params.get("filepath"):
                logger.error("Отсутствует параметр 'filepath'")
                return False

        elif action == "search_commits":
            if not params.get("query"):
                logger.error("Отсутствует параметр 'query'")
                return False

        return True
