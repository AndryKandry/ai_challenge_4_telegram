"""
DocumentationRAGAgent - агент для работы с документацией проекта через RAG.

Предоставляет функциональность для:
- Индексирования документации проекта (markdown, текстовые файлы)
- Семантического поиска по документации
- Получения примеров кода из документации
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from src.rag_integration import RAGManager
from src.embeddings.indexer import DocumentIndexer
from src.embeddings.chunker import DocumentChunker
from src.utils.file_parser import parse_file

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
    Агент для работы с документацией проекта через RAG.

    Использует существующий RAGManager для индексирования и поиска
    по документации проекта.

    Поддерживаемые действия:
    - search: поиск по документации
    - index: индексирование документов
    - get_code_examples: получение примеров кода
    - get_stats: статистика индекса
    """

    def __init__(
        self,
        rag_manager: RAGManager,
        name: str = "documentation_rag",
        enabled: bool = True
    ):
        """
        Инициализация DocumentationRAGAgent.

        Args:
            rag_manager: Экземпляр RAGManager для работы с индексом
            name: Имя агента
            enabled: Флаг активности
        """
        super().__init__(name, enabled)
        self.rag_manager = rag_manager
        self.indexer = DocumentIndexer(
            embedder=rag_manager.embedder,
            index_path=rag_manager.index_path
        )
        logger.info(f"DocumentationRAGAgent инициализирован с индексом: {rag_manager.index_path}")

    async def execute(self, task: Dict[str, Any]) -> Any:
        """
        Выполнение задачи агентом.

        Args:
            task: Словарь с параметрами:
                - action: "search", "index", "get_code_examples", "get_stats"
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
        elif action == "get_stats":
            return await self.get_index_stats()
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
            # Используем существующий searcher из RAGManager
            results = await self.rag_manager.searcher.search(
                query=query,
                top_k=top_k
            )

            # Фильтруем по минимальной релевантности
            filtered_results = [
                r for r in results
                if r.get("similarity", 0.0) >= min_similarity
            ]

            # Преобразуем в DocumentChunk
            chunks = []
            for result in filtered_results:
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

        # Получаем список файлов
        markdown_files = list(docs_dir.glob("**/*.md"))
        text_files = list(docs_dir.glob("**/*.txt"))
        all_files = markdown_files + text_files

        logger.info(f"Найдено файлов: {len(all_files)} (.md: {len(markdown_files)}, .txt: {len(text_files)})")

        indexed_count = 0
        total_chunks = 0
        errors = []

        # Индексируем каждый файл
        for file_path in all_files:
            try:
                # Читаем и парсим файл
                content = parse_file(str(file_path))

                # Создаем чанки
                chunker = DocumentChunker()
                chunks = chunker.chunk_text(
                    text=content,
                    metadata={"source": str(file_path)}
                )

                # Добавляем в индекс
                for chunk in chunks:
                    await self.indexer.add_document(
                        content=chunk["content"],
                        metadata=chunk.get("metadata", {})
                    )

                indexed_count += 1
                total_chunks += len(chunks)
                logger.debug(f"Проиндексирован: {file_path} ({len(chunks)} фрагментов)")

            except Exception as e:
                error_msg = f"Ошибка при индексировании {file_path}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Сохраняем индекс
        try:
            await self.indexer.save_index()
            logger.info(f"Индекс сохранен: {self.indexer.index_path}")
        except Exception as e:
            error_msg = f"Ошибка при сохранении индекса: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        result = {
            "indexed_files": indexed_count,
            "total_chunks": total_chunks,
            "errors": errors
        }

        logger.info(f"Индексирование завершено: {result}")
        return result

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

        # Формируем запрос для поиска кода
        code_query = f"{topic} пример код example"

        # Ищем релевантные фрагменты
        chunks = await self.search_documentation(
            query=code_query,
            top_k=10,
            min_similarity=0.4  # Понижаем порог для большей выборки
        )

        # Извлекаем блоки кода из фрагментов
        code_examples = []
        for chunk in chunks:
            content = chunk.content

            # Простой поиск блоков кода в markdown
            # (может быть улучшен для более точного извлечения)
            if "```" in content:
                lines = content.split("\n")
                in_code_block = False
                current_block = []

                for line in lines:
                    if line.strip().startswith("```"):
                        if in_code_block:
                            # Конец блока кода
                            if current_block:
                                code_examples.append("\n".join(current_block))
                                current_block = []
                            in_code_block = False
                        else:
                            # Начало блока кода
                            in_code_block = True
                    elif in_code_block:
                        current_block.append(line)

        logger.info(f"Найдено примеров кода: {len(code_examples)}")
        return code_examples

    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Получение статистики индекса.

        Returns:
            Словарь со статистикой:
                - total_documents: количество документов
                - index_path: путь к индексу
                - enabled: активен ли RAG
        """
        stats = {
            "total_documents": len(self.indexer.documents),
            "index_path": str(self.indexer.index_path),
            "enabled": self.rag_manager.enabled
        }

        logger.info(f"Статистика индекса: {stats}")
        return stats

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
