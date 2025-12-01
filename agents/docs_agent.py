"""
DocsAgent - агент для работы с документацией проекта через RAG Tools.

Агент использует систему Tools для семантического поиска,
индексирования и извлечения примеров кода из документации.
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

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "content": self.content,
            "metadata": self.metadata,
            "score": self.score
        }

    def __repr__(self) -> str:
        source = self.metadata.get("source", "unknown")
        return f"<DocumentChunk(source={source}, score={self.score:.3f})>"


class DocsAgent(BaseAgent):
    """
    Агент для работы с документацией проекта через RAG Tools.

    Использует Tools систему для индексирования и поиска
    по документации проекта.

    Поддерживаемые действия:
    - search: семантический поиск по документации
    - index: индексирование документов проекта
    - get_code_examples: получение примеров кода по теме
    - get_api_docs: получение API документации
    - search_by_topic: поиск по конкретной теме/категории
    """

    def __init__(
        self,
        tool_manager,
        name: str = "docs_agent",
        enabled: bool = True
    ):
        """
        Инициализация DocsAgent.

        Args:
            tool_manager: Менеджер инструментов
            name: Имя агента
            enabled: Флаг активности
        """
        super().__init__(name, tool_manager, enabled)

        # Определяем необходимые инструменты
        self.required_tools = ["document_search"]

        # Определяем альтернативные инструменты
        self.preferred_tools = {
            "search": ["document_search"],
            "code_search": ["code_example_search"]
        }

        logger.info(f"DocsAgent инициализирован с Tool Manager")

    async def execute(self, task: Dict[str, Any]) -> Any:
        """
        Выполнение задачи агентом.

        Args:
            task: Словарь с параметрами:
                - action: "search", "index", "get_code_examples", "get_api_docs", "search_by_topic"
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

        logger.info(f"DocsAgent выполняет действие: {action}")

        if action == "search":
            return await self.search_documentation(
                query=params.get("query", ""),
                top_k=params.get("top_k", 5),
                min_similarity=params.get("min_similarity", 0.1)
            )
        elif action == "index":
            return await self.index_project_docs(
                docs_path=params.get("docs_path", "docs")
            )
        elif action == "get_code_examples":
            return await self.get_code_examples(
                topic=params.get("topic", ""),
                language=params.get("language")
            )
        elif action == "get_api_docs":
            return await self.get_api_documentation(
                api_name=params.get("api_name", "")
            )
        elif action == "search_by_topic":
            return await self.search_by_topic(
                topic=params.get("topic", ""),
                top_k=params.get("top_k", 5)
            )
        else:
            raise ValueError(f"Неизвестное действие: {action}")

    async def search_documentation(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.1
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

            # Преобразуем в DocumentChunk с правильными полями из searcher
            chunks = []
            for result in results:
                chunk = DocumentChunk(
                    content=result.get("text", ""),  # searcher возвращает 'text'
                    metadata=result.get("metadata", {}),
                    score=result.get("similarity_score", 0.0)  # searcher возвращает 'similarity_score'
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
                file_extensions=[".md", ".txt", ".py"]
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

    async def get_code_examples(
        self,
        topic: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение примеров кода по заданной теме.

        Ищет в документации фрагменты с кодом, релевантные теме.

        Args:
            topic: Тема для поиска примеров
            language: Язык программирования (опционально)

        Returns:
            Список примеров кода с метаданными
        """
        if not topic:
            logger.warning("Пустая тема для поиска примеров кода")
            return []

        logger.info(f"Поиск примеров кода по теме: '{topic}' (язык: {language or 'любой'})")

        try:
            # Формируем расширенный запрос с фильтром по языку
            search_query = topic
            if language:
                search_query = f"{topic} {language}"

            # Используем code_example_search Tool через call_tool
            code_examples = await self.call_tool(
                "code_example_search",
                topic=search_query,
                top_k=10,
                language=language
            )

            logger.info(f"Найдено примеров кода: {len(code_examples)}")
            return code_examples

        except Exception as e:
            logger.error(f"Ошибка при поиске примеров кода: {e}", exc_info=True)
            # Fallback: используем обычный поиск по документации
            try:
                chunks = await self.search_documentation(
                    query=f"code example {topic}",
                    top_k=5
                )
                return [chunk.to_dict() for chunk in chunks]
            except Exception:
                return []

    async def get_api_documentation(self, api_name: str) -> Optional[Dict[str, Any]]:
        """
        Получение документации по конкретному API.

        Args:
            api_name: Название API или функции

        Returns:
            Словарь с документацией API или None
        """
        if not api_name:
            logger.warning("Пустое название API")
            return None

        logger.info(f"Поиск документации для API: '{api_name}'")

        try:
            # Используем специализированный поиск с фокусом на API
            results = await self.search_documentation(
                query=f"API {api_name} documentation",
                top_k=3,
                min_similarity=0.1
            )

            if not results:
                return None

            # Возвращаем наиболее релевантный результат
            best_match = results[0]
            return {
                "api_name": api_name,
                "documentation": best_match.content,
                "source": best_match.metadata.get("source", "unknown"),
                "relevance": best_match.score
            }

        except Exception as e:
            logger.error(f"Ошибка при поиске API документации: {e}", exc_info=True)
            return None

    async def search_by_topic(
        self,
        topic: str,
        top_k: int = 5
    ) -> List[DocumentChunk]:
        """
        Поиск документации по конкретной теме/категории.

        Args:
            topic: Тема для поиска
            top_k: Количество результатов

        Returns:
            Список фрагментов документов по теме
        """
        if not topic:
            logger.warning("Пустая тема для поиска")
            return []

        logger.info(f"Поиск по теме: '{topic}'")

        # Используем семантический поиск с разумной релевантностью
        return await self.search_documentation(
            query=topic,
            top_k=top_k,
            min_similarity=0.1
        )

    async def format_search_results(
        self,
        chunks: List[DocumentChunk],
        include_metadata: bool = True
    ) -> str:
        """
        Форматирование результатов поиска для отображения пользователю.

        Args:
            chunks: Список фрагментов документов
            include_metadata: Включать ли метаданные в вывод

        Returns:
            Отформатированная строка с результатами
        """
        if not chunks:
            return "По вашему запросу ничего не найдено."

        result_parts = []
        result_parts.append(f"Найдено {len(chunks)} релевантных фрагментов:\n")

        for i, chunk in enumerate(chunks, 1):
            result_parts.append(f"\n## Результат {i} (релевантность: {chunk.score:.2f})")

            if include_metadata:
                source = chunk.metadata.get("source", "unknown")
                result_parts.append(f"Источник: {source}")

            result_parts.append(f"\n{chunk.content}\n")
            result_parts.append("-" * 50)

        return "\n".join(result_parts)

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

        elif action == "get_api_docs":
            if not params.get("api_name"):
                logger.error("Отсутствует обязательный параметр 'api_name' для действия 'get_api_docs'")
                return False

        elif action == "search_by_topic":
            if not params.get("topic"):
                logger.error("Отсутствует обязательный параметр 'topic' для действия 'search_by_topic'")
                return False

        return True
