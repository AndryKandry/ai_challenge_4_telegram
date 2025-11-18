#!/usr/bin/env python3
"""
MCP (Model Context Protocol) клиент для работы с MCP-серверами.
Обеспечивает подключение к MCP-серверам и получение списка доступных инструментов.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, List, Any
import json

# Импорт MCP SDK
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("MCP библиотека не установлена. Установите: pip install mcp")

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Клиент для работы с MCP-серверами.

    Обеспечивает:
    - Установку соединения с MCP-сервером
    - Получение списка доступных инструментов
    - Получение детальной информации об инструментах
    """

    def __init__(self, server_config: Dict[str, Any]):
        """
        Инициализация MCP клиента.

        Args:
            server_config: Конфигурация сервера с полями:
                Для stdio транспорта:
                - type: "stdio"
                - command: команда для запуска сервера (например, "npx")
                - args: аргументы команды (список строк)
                - env: переменные окружения (опционально)

                Для HTTP (SSE) транспорта:
                - type: "http" или "sse"
                - url: URL MCP сервера
                - headers: заголовки HTTP (опционально)
        """
        if not MCP_AVAILABLE:
            raise ImportError(
                "MCP библиотека не установлена. "
                "Установите её командой: pip install mcp"
            )

        self.server_config = server_config
        self.transport_type = server_config.get('type', 'stdio').lower()
        self.session: Optional[ClientSession] = None
        self.read_stream = None
        self.write_stream = None
        self._stdio_context = None
        self._sse_context = None
        self._connected = False

        transport_info = server_config.get('url') or server_config.get('command', 'unknown')
        logger.info(f"MCPClient инициализирован ({self.transport_type}): {transport_info}")

    async def connect(self) -> bool:
        """
        Установка соединения с MCP-сервером.

        Returns:
            True если подключение успешно, False в случае ошибки
        """
        if self._connected:
            logger.warning("Клиент уже подключен")
            return True

        try:
            if self.transport_type in ('http', 'sse'):
                return await self._connect_http()
            else:
                return await self._connect_stdio()

        except Exception as e:
            logger.error(f"Ошибка подключения к MCP-серверу: {e}", exc_info=True)
            self._connected = False
            return False

    async def _connect_stdio(self) -> bool:
        """Подключение через stdio транспорт."""
        # Подготовка параметров сервера
        command = self.server_config.get("command")
        args = self.server_config.get("args", [])
        env_vars = self.server_config.get("env", {})

        if not command:
            logger.error("Не указана команда для запуска MCP-сервера")
            return False

        # Объединяем переменные окружения
        server_env = os.environ.copy()
        server_env.update(env_vars)

        # Создание параметров сервера
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=server_env
        )

        logger.info(f"Подключение к MCP-серверу (stdio): {command} {' '.join(args)}")

        # Установка соединения через контекстный менеджер
        logger.debug("Создание stdio_client контекстного менеджера...")
        self._stdio_context = stdio_client(server_params)

        logger.debug("Вход в stdio_client контекст...")
        self.read_stream, self.write_stream = await self._stdio_context.__aenter__()
        logger.debug("Успешно получены потоки read/write")

        # Создание сессии
        logger.debug("Создание ClientSession...")
        self.session = ClientSession(self.read_stream, self.write_stream)

        # Вход в контекст сессии (запускает _receive_loop)
        logger.debug("Вход в контекст ClientSession...")
        await self.session.__aenter__()
        logger.debug("ClientSession контекст инициализирован, _receive_loop запущен")

        # Инициализация сессии
        logger.info("Инициализация MCP сессии...")
        await self.session.initialize()
        logger.debug("Сессия успешно инициализирована")

        self._connected = True
        logger.info("Успешное подключение к MCP-серверу (stdio)")
        return True

    async def _connect_http(self) -> bool:
        """Подключение через HTTP (SSE) транспорт."""
        url = self.server_config.get("url")
        headers = self.server_config.get("headers", {})

        if not url:
            logger.error("Не указан URL для HTTP MCP-сервера")
            return False

        logger.info(f"Подключение к MCP-серверу (HTTP): {url}")

        # Установка соединения через SSE
        logger.debug("Создание sse_client контекстного менеджера...")
        self._sse_context = sse_client(url, headers=headers)

        logger.debug("Вход в sse_client контекст...")
        self.read_stream, self.write_stream = await self._sse_context.__aenter__()
        logger.debug("Успешно получены потоки read/write")

        # Создание сессии
        logger.debug("Создание ClientSession...")
        self.session = ClientSession(self.read_stream, self.write_stream)

        # Вход в контекст сессии (запускает _receive_loop)
        logger.debug("Вход в контекст ClientSession...")
        await self.session.__aenter__()
        logger.debug("ClientSession контекст инициализирован, _receive_loop запущен")

        # Инициализация сессии с таймаутом
        logger.info("Инициализация MCP сессии...")
        try:
            # Добавляем таймаут 30 секунд для initialize (SSE может быть медленным)
            await asyncio.wait_for(self.session.initialize(), timeout=30.0)
            logger.debug("Сессия успешно инициализирована")
        except asyncio.TimeoutError:
            logger.error("Таймаут при инициализации MCP сессии (30 сек)")
            raise Exception("MCP session initialization timeout - сервер не отвечает")

        self._connected = True
        logger.info("Успешное подключение к MCP-серверу (HTTP)")
        return True

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Получение списка доступных инструментов от MCP-сервера.

        Returns:
            Список словарей с информацией об инструментах:
            - name: название инструмента
            - description: описание инструмента
            - inputSchema: схема входных параметров
        """
        if not self._connected or not self.session:
            logger.error("Клиент не подключен. Вызовите connect() сначала")
            return []

        try:
            logger.info("Запрос списка инструментов от MCP-сервера")

            # Получение списка инструментов
            response = await self.session.list_tools()

            tools = []
            if hasattr(response, 'tools'):
                for tool in response.tools:
                    tool_info = {
                        "name": tool.name,
                        "description": tool.description or "Описание отсутствует",
                        "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    }
                    tools.append(tool_info)

            logger.info(f"Получено {len(tools)} инструментов от MCP-сервера")
            return tools

        except Exception as e:
            logger.error(f"Ошибка получения списка инструментов: {e}", exc_info=True)
            return []

    async def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Получение детальной информации об инструменте.

        Args:
            tool_name: Название инструмента

        Returns:
            Словарь с информацией об инструменте или None если не найден
        """
        tools = await self.list_tools()

        for tool in tools:
            if tool["name"] == tool_name:
                return tool

        logger.warning(f"Инструмент '{tool_name}' не найден")
        return None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Any]:
        """
        Вызов MCP инструмента с заданными аргументами.

        Args:
            tool_name: Название инструмента
            arguments: Словарь с аргументами для инструмента

        Returns:
            Результат выполнения инструмента или None в случае ошибки
        """
        if not self._connected or not self.session:
            logger.error("Клиент не подключен. Вызовите connect() сначала")
            return None

        try:
            logger.info(f"Вызов MCP инструмента: {tool_name} с аргументами {arguments}")

            # Вызов инструмента через MCP сессию
            response = await self.session.call_tool(tool_name, arguments=arguments)

            # Обработка ответа
            if hasattr(response, 'content'):
                # Извлекаем текстовый контент из ответа
                result = []
                for content_item in response.content:
                    if hasattr(content_item, 'text'):
                        result.append(content_item.text)

                # Объединяем все текстовые части
                combined_result = '\n'.join(result) if result else None
                logger.info(f"Результат выполнения инструмента {tool_name} получен")
                return combined_result
            else:
                logger.warning(f"Инструмент {tool_name} вернул ответ без контента")
                return None

        except Exception as e:
            logger.error(f"Ошибка при вызове инструмента {tool_name}: {e}", exc_info=True)
            return None

    async def disconnect(self) -> None:
        """
        Закрытие соединения с MCP-сервером.
        """
        if not self._connected:
            logger.warning("Клиент уже отключен")
            return

        try:
            # Закрытие сессии (выход из контекста)
            if self.session:
                logger.info("Закрытие MCP сессии")
                try:
                    await self.session.__aexit__(None, None, None)
                    logger.debug("ClientSession контекст закрыт")
                except Exception as e:
                    logger.warning(f"Ошибка при закрытии сессии: {e}")

            # Правильное закрытие контекстного менеджера stdio_client
            if self._stdio_context:
                try:
                    await self._stdio_context.__aexit__(None, None, None)
                    logger.info("Контекстный менеджер stdio_client закрыт")
                except Exception as e:
                    logger.warning(f"Ошибка при закрытии stdio контекста: {e}")

            # Правильное закрытие контекстного менеджера sse_client
            if self._sse_context:
                try:
                    await self._sse_context.__aexit__(None, None, None)
                    logger.info("Контекстный менеджер sse_client закрыт")
                except Exception as e:
                    logger.warning(f"Ошибка при закрытии SSE контекста: {e}")

            self._connected = False
            self.session = None
            self.read_stream = None
            self.write_stream = None
            self._stdio_context = None
            self._sse_context = None

            logger.info("Соединение с MCP-сервером закрыто")

        except Exception as e:
            logger.error(f"Ошибка при закрытии соединения: {e}", exc_info=True)

    def is_connected(self) -> bool:
        """
        Проверка статуса подключения.

        Returns:
            True если подключен, False в противном случае
        """
        return self._connected

    async def __aenter__(self):
        """Поддержка контекстного менеджера (async with)."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие соединения при выходе из контекста."""
        await self.disconnect()


def load_mcp_config(config_path: str = "config/mcp_config.json") -> Dict[str, Any]:
    """
    Загрузка конфигурации MCP из файла.

    Args:
        config_path: Путь к файлу конфигурации

    Returns:
        Словарь с конфигурацией MCP-серверов
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"Конфигурация MCP загружена из {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"Файл конфигурации {config_path} не найден")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON конфигурации: {e}")
        return {}
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        return {}


def get_weather_mcp_config() -> Dict[str, Any]:
    """
    Получение конфигурации для локального Weather MCP сервера.

    Weather MCP сервер предоставляет инструменты для получения погодной информации
    из US National Weather Service API.

    ВАЖНО: Из-за бага в MCP Python SDK (https://github.com/modelcontextprotocol/python-sdk/issues/862),
    stdio транспорт зависает при инициализации. Используется HTTP/SSE транспорт.

    Для работы нужно запустить сервер отдельно:
        python mcp_server/weather.py

    Returns:
        Словарь с конфигурацией для подключения к Weather MCP серверу
    """
    return {
        "type": "http",
        "url": "http://localhost:8000/sse",
        "headers": {}
    }


def get_weather_stdio_mcp_config() -> Dict[str, Any]:
    """
    Получение конфигурации для Weather MCP сервера через stdio транспорт.

    ВНИМАНИЕ: stdio транспорт имеет критический баг в MCP Python SDK 1.21.2,
    который вызывает зависание при инициализации на macOS, Windows и Linux.
    См. https://github.com/modelcontextprotocol/python-sdk/issues/862

    Эта функция сохранена для обратной совместимости и может быть использована
    когда баг будет исправлен в будущих версиях SDK.

    Returns:
        Словарь с конфигурацией для подключения к Weather MCP серверу через stdio
    """
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent
    weather_server_path = project_root / "mcp_server" / "weather.py"

    if not weather_server_path.exists():
        logger.warning(f"Weather MCP сервер не найден: {weather_server_path}")

    return {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(weather_server_path), "--stdio"],
        "env": {}
    }


def get_github_mcp_config() -> Dict[str, Any]:
    """
    Получение конфигурации для локального GitHub MCP сервера.

    GitHub MCP сервер предоставляет инструменты для работы с GitHub API:
    - get_user_repositories: получение списка публичных репозиториев пользователя
    - get_user_info: получение информации о пользователе GitHub
    - get_repository_commits: получение информации о коммитах в репозитории

    ВАЖНО: Из-за бага в MCP Python SDK (https://github.com/modelcontextprotocol/python-sdk/issues/862),
    stdio транспорт зависает при инициализации. Используется HTTP/SSE транспорт.

    Для работы нужно запустить сервер отдельно:
        python mcp_server/github.py

    Returns:
        Словарь с конфигурацией для подключения к GitHub MCP серверу
    """
    return {
        "type": "http",
        "url": "http://localhost:8001/sse",
        "headers": {}
    }


def get_github_stdio_mcp_config() -> Dict[str, Any]:
    """
    Получение конфигурации для GitHub MCP сервера через stdio транспорт.

    ВНИМАНИЕ: stdio транспорт имеет критический баг в MCP Python SDK 1.21.2,
    который вызывает зависание при инициализации на macOS, Windows и Linux.
    См. https://github.com/modelcontextprotocol/python-sdk/issues/862

    Эта функция сохранена для обратной совместимости и может быть использована
    когда баг будет исправлен в будущих версиях SDK.

    Returns:
        Словарь с конфигурацией для подключения к GitHub MCP серверу через stdio
    """
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent
    github_server_path = project_root / "mcp_server" / "github.py"

    if not github_server_path.exists():
        logger.warning(f"GitHub MCP сервер не найден: {github_server_path}")

    return {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(github_server_path), "--stdio"],
        "env": {}
    }
