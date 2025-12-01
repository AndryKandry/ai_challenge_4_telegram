"""
System Tools - инструменты для системных операций.

Предоставляет инструменты для:
- Чтения файлов
- Записи в файлы
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool, ToolType, ToolFailureError

logger = logging.getLogger(__name__)


class FileReadTool(BaseTool):
    """Инструмент для чтения файлов."""

    def __init__(self, allowed_paths: Optional[List[str]] = None):
        """
        Инициализация FileReadTool.

        Args:
            allowed_paths: Список разрешенных путей (для безопасности)
        """
        super().__init__(
            name="file_read",
            tool_type=ToolType.SYSTEM,
            description="Read files from filesystem"
        )
        self.allowed_paths = [Path(p).resolve() for p in (allowed_paths or ["."])]
        logger.info(f"FileReadTool инициализирован: {self.allowed_paths}")

    async def execute(
        self,
        filepath: str,
        encoding: str = "utf-8",
        **kwargs
    ) -> str:
        """
        Прочитать файл.

        Args:
            filepath: Путь к файлу
            encoding: Кодировка файла
            **kwargs: Дополнительные параметры

        Returns:
            Содержимое файла

        Raises:
            ToolFailureError: При ошибке чтения
            ValueError: При некорректных параметрах
        """
        if not filepath:
            raise ValueError("Не указан путь к файлу")

        file_path = Path(filepath).resolve()

        # Проверка доступа
        allowed = any(
            str(file_path).startswith(str(allowed))
            for allowed in self.allowed_paths
        )

        if not allowed:
            raise ToolFailureError(f"Доступ к пути запрещен: {filepath}")

        if not file_path.exists():
            raise ToolFailureError(f"Файл не найден: {filepath}")

        if not file_path.is_file():
            raise ToolFailureError(f"Путь не является файлом: {filepath}")

        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except Exception as e:
            raise ToolFailureError(f"Ошибка чтения файла: {e}")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров."""
        if "filepath" not in params:
            logger.error("Отсутствует обязательный параметр 'filepath'")
            return False
        return True

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {
                "filepath": {
                    "type": "string",
                    "description": "Путь к файлу"
                },
                "encoding": {
                    "type": "string",
                    "description": "Кодировка файла",
                    "default": "utf-8"
                }
            },
            "required": ["filepath"]
        }


class FileWriteTool(BaseTool):
    """Инструмент для записи в файлы."""

    def __init__(self, allowed_paths: Optional[List[str]] = None):
        """
        Инициализация FileWriteTool.

        Args:
            allowed_paths: Список разрешенных путей (для безопасности)
        """
        super().__init__(
            name="file_write",
            tool_type=ToolType.SYSTEM,
            description="Write content to files"
        )
        self.allowed_paths = [Path(p).resolve() for p in (allowed_paths or ["."])]
        logger.info(f"FileWriteTool инициализирован: {self.allowed_paths}")

    async def execute(
        self,
        filepath: str,
        content: str,
        mode: str = "w",
        encoding: str = "utf-8",
        **kwargs
    ) -> bool:
        """
        Записать в файл.

        Args:
            filepath: Путь к файлу
            content: Содержимое для записи
            mode: Режим записи ('w' или 'a')
            encoding: Кодировка файла
            **kwargs: Дополнительные параметры

        Returns:
            True при успехе

        Raises:
            ToolFailureError: При ошибке записи
            ValueError: При некорректных параметрах
        """
        if not filepath:
            raise ValueError("Не указан путь к файлу")

        if mode not in ["w", "a"]:
            raise ValueError(f"Некорректный режим записи: {mode}")

        file_path = Path(filepath).resolve()

        # Проверка доступа
        allowed = any(
            str(file_path).startswith(str(allowed))
            for allowed in self.allowed_paths
        )

        if not allowed:
            raise ToolFailureError(f"Доступ к пути запрещен: {filepath}")

        try:
            # Создаем директории если нужно
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)

            logger.info(f"Файл успешно записан: {filepath}")
            return True

        except Exception as e:
            raise ToolFailureError(f"Ошибка записи файла: {e}")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров."""
        if "filepath" not in params:
            logger.error("Отсутствует обязательный параметр 'filepath'")
            return False

        if "content" not in params:
            logger.error("Отсутствует обязательный параметр 'content'")
            return False

        return True

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {
                "filepath": {
                    "type": "string",
                    "description": "Путь к файлу"
                },
                "content": {
                    "type": "string",
                    "description": "Содержимое для записи"
                },
                "mode": {
                    "type": "string",
                    "description": "Режим записи",
                    "enum": ["w", "a"],
                    "default": "w"
                },
                "encoding": {
                    "type": "string",
                    "description": "Кодировка файла",
                    "default": "utf-8"
                }
            },
            "required": ["filepath", "content"]
        }
