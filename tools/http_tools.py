"""
HTTP Tools - инструменты для HTTP запросов.

Предоставляет инструменты для:
- HTTP запросов к внешним API
"""

import logging
from typing import Any, Dict, Optional

import aiohttp

from .base_tool import BaseTool, ToolType, ToolFailureError

logger = logging.getLogger(__name__)


class HTTPRequestTool(BaseTool):
    """Инструмент для HTTP запросов к внешним API."""

    def __init__(self, timeout: int = 30):
        """
        Инициализация HTTPRequestTool.

        Args:
            timeout: Таймаут запроса в секундах
        """
        super().__init__(
            name="http_request",
            tool_type=ToolType.HTTP,
            description="Make HTTP requests to external APIs"
        )
        self.timeout = timeout
        logger.info(f"HTTPRequestTool инициализирован (timeout={timeout}s)")

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Выполнить HTTP запрос.

        Args:
            url: URL для запроса
            method: HTTP метод (GET, POST, PUT, DELETE)
            headers: HTTP заголовки
            data: Данные формы
            json_data: JSON данные
            **kwargs: Дополнительные параметры

        Returns:
            Словарь с результатом:
                - status: HTTP статус код
                - headers: заголовки ответа
                - body: тело ответа

        Raises:
            ToolFailureError: При ошибке запроса
            ValueError: При некорректных параметрах
        """
        if not url:
            raise ValueError("Не указан URL")

        method = method.upper()
        if method not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            raise ValueError(f"Некорректный HTTP метод: {method}")

        logger.info(f"HTTP {method} запрос: {url}")

        try:
            timeout_obj = aiohttp.ClientTimeout(total=self.timeout)

            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    json=json_data
                ) as response:
                    # Пытаемся прочитать как JSON
                    try:
                        body = await response.json()
                    except Exception:
                        # Если не JSON, читаем как текст
                        body = await response.text()

                    result = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": body
                    }

                    logger.info(f"HTTP запрос выполнен: статус {response.status}")
                    return result

        except aiohttp.ClientError as e:
            raise ToolFailureError(f"Ошибка HTTP запроса: {e}")
        except asyncio.TimeoutError:
            raise ToolFailureError(f"Таймаут HTTP запроса ({self.timeout}s)")
        except Exception as e:
            raise ToolFailureError(f"Неожиданная ошибка HTTP запроса: {e}")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров."""
        if "url" not in params:
            logger.error("Отсутствует обязательный параметр 'url'")
            return False

        url = params["url"]
        if not url.startswith(("http://", "https://")):
            logger.error(f"Некорректный URL: {url}")
            return False

        return True

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {
                "url": {
                    "type": "string",
                    "description": "URL для запроса"
                },
                "method": {
                    "type": "string",
                    "description": "HTTP метод",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "default": "GET"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP заголовки"
                },
                "data": {
                    "type": "object",
                    "description": "Данные формы"
                },
                "json_data": {
                    "type": "object",
                    "description": "JSON данные"
                }
            },
            "required": ["url"]
        }
