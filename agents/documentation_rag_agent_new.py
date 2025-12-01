"""
DocumentationRAGAgent - агент для работы с документацией проекта через RAG Tools.

Новая версия, использующая систему Tools для работы с RAG.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DocumentChunk:
    """
    Класс для представления фрагмента документа.

    Attributes:
        content (str): Содержимое фрагмента
        metadata (dict): Метаданные (источник, позиция и т.д.)
        score (float): Релевантность (для результатов поиска)
    """

    def __init__(self, content: str, metadata: Dict[str, Any], score: float = 0.0):
        self.content = content
        self.metadata = metadata
        self.score = score

    def __repr__(self) -> str:
        source = self.metadata.get("source", "unknown")
        return f"<DocumentChunk(source={source}, score={self.score:.3f})>"


class DocumentationRAGAgent(BaseAgent):
    """
    Агент для работы с документацией проекта через RAG Tools.

    Использует Tools систему для индексирования и поиска
    по документации проекта.

    Поддерживаемые действия:
    - search: поиск по документации
    - index: индексирование документов
    - get_code_examples: получение примеров кода
    """

    def __init__(
        self,
        tool_manager,
        name: str = "documentation_rag",
        enabled: bool = True
    ):
        """
        Инициализация DocumentationRAGAgent.

        Args:
            tool_manager: Менеджер инструментов
            name: Имя агента
            enabled: Флаг активности
        """
        super().__init__(name, tool_manager, enabled)

        # Определяем необходимые инструменты
        self.required_tools = ["document_search", "code_example_search"]

        # Определяем альтернативные инструменты
        self.preferred_tools = {
            "search": ["document_search"],
            "code_search": ["code_example_search"]
        }

        logger.info(f"DocumentationRAGAgent инициализирован с Tool Manager")

    async def execute(self, task: Dict[str, Any]) -> Any:
        """
        Выполнение задачи агентом.

        Args:
            task: Словарь с параметрами:
                - action: "search", "index", "get_code_examples"
                - params: параметры для действия
                - context: дополнительный контекст (опционально)

        Returns:
            Результат выполнения задачи

        Raises:
            ValueError: Если действие не поддерживается
        """
        action = task.get("action")
        params = task.get("params", {})

        if action == "search":
            return await self.search_documentation(
                query=params.get("query", ""),
                top_k=params.get("top_k", 5),
                min_similarity=params.get("min_similarity", 0.5)
            )
        elif action == "index":
            return await self.index_project_docs(
                docs_path=params.get("docs_path", "docs")
            )
        elif action == "get_code_examples":
            return await self.get_code_examples(
                topic=params.get("topic", "")
            )
        else:
            raise ValueError(f"Неизвестное действие: {action}")

    async def search_documentation(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5
    ) -> List[DocumentChunk]:
        """
        Семантический поиск по документации.

        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            min_similarity: Минимальная релевантность

        Returns:
            Список фрагментов документов с релевантностью
        """
        if not query:
            logger.warning("Пустой запрос для поиска")
            return []

        logger.info(f"Поиск по документации: '{query}' (top_k={top_k})")

        try:
            # Используем document_search Tool через call_tool
            results = await self.call_tool(
                "document_search",
                query=query,
                top_k=top_k,
                min_similarity=min_similarity
            )

            # Преобразуем в DocumentChunk
            chunks = []
            for result in results:
                chunk = DocumentChunk(
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    score=result.get("similarity", 0.0)
                )
                chunks.append(chunk)

            logger.info(f"Найдено {len(chunks)} релевантных фрагментов")
            return chunks

        except Exception as e:
            logger.error(f"Ошибка при поиске по документации: {e}", exc_info=True)
            return []

    async def index_project_docs(self, docs_path: str) -> Dict[str, Any]:
        """
        Индексирование документов проекта.

        Args:
            docs_path: Путь к директории с документацией

        Returns:
            Словарь со статистикой индексирования:
                - indexed_files: количество проиндексированных файлов
                - total_chunks: количество фрагментов
                - errors: список ошибок
        """
        logger.info(f"Индексирование документации из: {docs_path}")

        docs_dir = Path(docs_path)
        if not docs_dir.exists():
            logger.error(f"Директория не найдена: {docs_path}")
            return {
                "indexed_files": 0,
                "total_chunks": 0,
                "errors": [f"Директория не найдена: {docs_path}"]
            }

        try:
            # Используем document_indexer Tool через call_tool
            result = await self.call_tool(
                "document_indexer",
                docs_path=docs_path,
                file_extensions=[".md", ".txt"]
            )

            logger.info(f"Индексирование завершено: {result}")
            return result

        except Exception as e:
            error_msg = f"Ошибка при индексировании: {e}"
            logger.error(error_msg)
            return {
                "indexed_files": 0,
                "total_chunks": 0,
                "errors": [error_msg]
            }

    async def get_code_examples(self, topic: str) -> List[str]:
        """
        Получение примеров кода по заданной теме.

        Ищет в документации фрагменты с кодом, релевантные теме.

        Args:
            topic: Тема для поиска примеров

        Returns:
            Список примеров кода (строк)
        """
        if not topic:
            logger.warning("Пустая тема для поиска примеров кода")
            return []

        logger.info(f"Поиск примеров кода по теме: '{topic}'")

        try:
            # Используем code_example_search Tool через call_tool
            code_examples = await self.call_tool(
                "code_example_search",
                topic=topic,
                top_k=10
            )

            logger.info(f"Найдено примеров кода: {len(code_examples)}")
            return code_examples

        except Exception as e:
            logger.error(f"Ошибка при поиске примеров кода: {e}", exc_info=True)
            return []

    async def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Валидация входных данных для агента.

        Проверяет наличие обязательных полей и корректность параметров.

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
        if action == "search":
            if not params.get("query"):
                logger.error("Отсутствует обязательный параметр 'query' для действия 'search'")
                return False

        elif action == "index":
            if not params.get("docs_path"):
                logger.error("Отсутствует обязательный параметр 'docs_path' для действия 'index'")
                return False

        elif action == "get_code_examples":
            if not params.get("topic"):
                logger.error("Отсутствует обязательный параметр 'topic' для действия 'get_code_examples'")
                return False

        return True
