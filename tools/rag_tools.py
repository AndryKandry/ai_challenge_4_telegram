"""
RAG Tools - инструменты для работы с RAG системой.

Предоставляет инструменты для:
- Поиска по документации через семантический поиск
- Индексирования документов
- Получения примеров кода из документации
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool, ToolType, ToolFailureError
from src.rag_integration import RAGManager
from src.embeddings.indexer import DocumentIndexer
from src.embeddings.chunker import TextChunker
from src.utils.file_parser import read_text, read_markdown

logger = logging.getLogger(__name__)


class DocumentSearchTool(BaseTool):
    """
    Инструмент для семантического поиска по документации.

    Использует RAGManager для поиска релевантных фрагментов
    документов по запросу пользователя.
    """

    def __init__(self, rag_manager: RAGManager):
        """
        Инициализация DocumentSearchTool.

        Args:
            rag_manager: Экземпляр RAGManager для работы с индексом
        """
        super().__init__(
            name="document_search",
            tool_type=ToolType.RAG,
            description="Semantic search through project documentation using RAG"
        )
        self.rag_manager = rag_manager
        logger.info("DocumentSearchTool инициализирован")

    async def execute(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Выполнить семантический поиск.

        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            min_similarity: Минимальная релевантность
            **kwargs: Дополнительные параметры

        Returns:
            Список словарей с результатами поиска:
                - content: содержимое фрагмента
                - metadata: метаданные (источник, позиция)
                - similarity: релевантность (0-1)

        Raises:
            ToolFailureError: При ошибке поиска
            ValueError: При некорректных параметрах
        """
        if not query:
            raise ValueError("Пустой запрос для поиска")

        if not self.rag_manager.enabled:
            raise ToolFailureError("RAG система отключена")

        logger.info(f"Поиск по документации: '{query}' (top_k={top_k})")

        try:
            # Используем существующий searcher из RAGManager с правильным порогом
            results = self.rag_manager.searcher.search(
                query=query,
                top_k=top_k,
                min_similarity=min_similarity
            )

            # Результаты уже отфильтрованы в searcher
            filtered_results = results

            logger.info(f"Найдено {len(filtered_results)} релевантных фрагментов")
            return filtered_results

        except Exception as e:
            logger.error(f"Ошибка при поиске по документации: {e}", exc_info=True)
            raise ToolFailureError(f"Ошибка поиска: {e}")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров поиска."""
        if "query" not in params:
            logger.error("Отсутствует обязательный параметр 'query'")
            return False

        if not isinstance(params["query"], str):
            logger.error("Параметр 'query' должен быть строкой")
            return False

        if "top_k" in params and (params["top_k"] < 1 or params["top_k"] > 100):
            logger.error("Параметр 'top_k' должен быть от 1 до 100")
            return False

        return True

    async def on_failure(self, error: Exception, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка ошибки при выполнении инструмента.
        
        Args:
            error: Исключение, возникшее при выполнении
            params: Параметры, с которыми вызывался инструмент
            
        Returns:
            Результат с информацией об ошибке
        """
        logger.warning(f"DocumentSearchTool завершился с ошибкой: {error}")
        
        return {
            "error": True,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "query": params.get("query", ""),
            "suggestion": "Попробуйте переформулировать запрос или проверьте доступность RAG системы",
            "fallback_results": []
        }

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Количество результатов",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 100
                },
                "min_similarity": {
                    "type": "number",
                    "description": "Минимальная релевантность (0-1)",
                    "default": 0.5,
                    "minimum": 0.0,
                    "maximum": 1.0
                }
            },
            "required": ["query"]
        }


class DocumentIndexerTool(BaseTool):
    """
    Инструмент для индексирования документов.

    Индексирует markdown и текстовые файлы из указанной директории
    для последующего семантического поиска.
    """

    def __init__(self, rag_manager: RAGManager):
        """
        Инициализация DocumentIndexerTool.

        Args:
            rag_manager: Экземпляр RAGManager для работы с индексом
        """
        super().__init__(
            name="document_indexer",
            tool_type=ToolType.RAG,
            description="Index documentation files for semantic search"
        )
        self.rag_manager = rag_manager
        self.indexer = DocumentIndexer(
            embedder=rag_manager.embedder,
            index_path=rag_manager.index_path
        )
        logger.info("DocumentIndexerTool инициализирован")

    async def execute(
        self,
        docs_path: str,
        file_extensions: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Индексировать документы.

        Args:
            docs_path: Путь к директории с документацией
            file_extensions: Список расширений файлов (по умолчанию ['.md', '.txt'])
            **kwargs: Дополнительные параметры

        Returns:
            Словарь со статистикой:
                - indexed_files: количество проиндексированных файлов
                - total_chunks: количество фрагментов
                - errors: список ошибок

        Raises:
            ToolFailureError: При ошибке индексирования
            ValueError: При некорректных параметрах
        """
        if not docs_path:
            raise ValueError("Не указан путь к документам")

        docs_dir = Path(docs_path)
        if not docs_dir.exists():
            raise ValueError(f"Директория не найдена: {docs_path}")

        if file_extensions is None:
            file_extensions = ['.md', '.txt']

        logger.info(f"Индексирование документации из: {docs_path}")

        # Получаем список файлов
        all_files = []
        for ext in file_extensions:
            all_files.extend(docs_dir.glob(f"**/*{ext}"))

        logger.info(f"Найдено файлов: {len(all_files)}")

        indexed_count = 0
        total_chunks = 0
        errors = []

        # Индексируем каждый файл
        for file_path in all_files:
            try:
                # Читаем и парсим файл
                if str(file_path).endswith('.md'):
                    content = read_markdown(str(file_path))
                else:
                    content = read_text(str(file_path))
                
                chunker = TextChunker()
                chunks = chunker.chunk_text(
                    text=content,
                    metadata={"file_path": str(file_path)}
                )

                # Добавляем в индекс
                for chunk in chunks:
                    await self.indexer.add_document(
                        content=chunk["text"],
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

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров индексирования."""
        if "docs_path" not in params:
            logger.error("Отсутствует обязательный параметр 'docs_path'")
            return False

        return True

    async def on_failure(self, error: Exception, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка ошибки при выполнении инструмента.
        
        Args:
            error: Исключение, возникшее при выполнении
            params: Параметры, с которыми вызывался инструмент
            
        Returns:
            Результат с информацией об ошибке
        """
        logger.warning(f"DocumentIndexerTool завершился с ошибкой: {error}")
        
        return {
            "error": True,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "docs_path": params.get("docs_path", ""),
            "suggestion": "Проверьте путь к документам и права доступа",
            "indexed_files": 0,
            "total_chunks": 0,
            "errors": [str(error)]
        }

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {
                "docs_path": {
                    "type": "string",
                    "description": "Путь к директории с документацией"
                },
                "file_extensions": {
                    "type": "array",
                    "description": "Список расширений файлов",
                    "default": [".md", ".txt"],
                    "items": {"type": "string"}
                }
            },
            "required": ["docs_path"]
        }


class CodeExampleSearchTool(BaseTool):
    """
    Инструмент для поиска примеров кода в документации.

    Ищет фрагменты с кодом, релевантные заданной теме.
    """

    def __init__(self, rag_manager: RAGManager):
        """
        Инициализация CodeExampleSearchTool.

        Args:
            rag_manager: Экземпляр RAGManager для работы с индексом
        """
        super().__init__(
            name="code_example_search",
            tool_type=ToolType.RAG,
            description="Search for code examples in documentation by topic"
        )
        self.rag_manager = rag_manager
        logger.info("CodeExampleSearchTool инициализирован")

    async def execute(
        self,
        topic: str,
        language: Optional[str] = None,
        top_k: int = 10,
        **kwargs
    ) -> List[str]:
        """
        Поиск примеров кода по теме.

        Args:
            topic: Тема для поиска примеров
            language: Язык программирования (опционально)
            top_k: Количество результатов для анализа
            **kwargs: Дополнительные параметры

        Returns:
            Список строк с примерами кода

        Raises:
            ToolFailureError: При ошибке поиска
            ValueError: При некорректных параметрах
        """
        if not topic:
            raise ValueError("Пустая тема для поиска примеров кода")

        logger.info(f"Поиск примеров кода по теме: '{topic}'")

        # Формируем запрос для поиска кода
        code_query = f"{topic} пример код example"
        if language:
            code_query += f" {language}"

        try:
            # Ищем релевантные фрагменты
            results = self.rag_manager.searcher.search(
                query=code_query,
                top_k=top_k
            )

            # Извлекаем блоки кода из фрагментов
            code_examples = []
            for result in results:
                content = result.get("content", "")

                # Простой поиск блоков кода в markdown
                if "```" in content:
                    code_blocks = self._extract_code_blocks(content, language)
                    code_examples.extend(code_blocks)

            logger.info(f"Найдено примеров кода: {len(code_examples)}")
            return code_examples

        except Exception as e:
            logger.error(f"Ошибка при поиске примеров кода: {e}", exc_info=True)
            raise ToolFailureError(f"Ошибка поиска примеров: {e}")

    def _extract_code_blocks(
        self,
        content: str,
        language: Optional[str] = None
    ) -> List[str]:
        """
        Извлечь блоки кода из markdown текста.

        Args:
            content: Текст с markdown разметкой
            language: Фильтр по языку программирования

        Returns:
            Список блоков кода
        """
        lines = content.split("\n")
        in_code_block = False
        current_block = []
        current_lang = None
        code_blocks = []

        for line in lines:
            if line.strip().startswith("```"):
                if in_code_block:
                    # Конец блока кода
                    if current_block:
                        # Проверяем фильтр по языку
                        if language is None or current_lang == language:
                            code_blocks.append("\n".join(current_block))
                        current_block = []
                    in_code_block = False
                    current_lang = None
                else:
                    # Начало блока кода
                    in_code_block = True
                    # Извлекаем язык программирования
                    lang_part = line.strip()[3:].strip()
                    current_lang = lang_part if lang_part else None
            elif in_code_block:
                current_block.append(line)

        return code_blocks

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров поиска примеров."""
        if "topic" not in params:
            logger.error("Отсутствует обязательный параметр 'topic'")
            return False

        return True

    async def on_failure(self, error: Exception, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка ошибки при выполнении инструмента.
        
        Args:
            error: Исключение, возникшее при выполнении
            params: Параметры, с которыми вызывался инструмент
            
        Returns:
            Результат с информацией об ошибке
        """
        logger.warning(f"CodeExampleSearchTool завершился с ошибкой: {error}")
        
        return {
            "error": True,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "topic": params.get("topic", ""),
            "language": params.get("language", ""),
            "suggestion": "Попробуйте уточнить тему или проверить доступность RAG системы",
            "fallback_examples": []
        }

    def get_schema(self) -> Dict[str, Any]:
        """Получить схему параметров инструмента."""
        return {
            "name": self.name,
            "type": self.tool_type.value,
            "description": self.description,
            "parameters": {
                "topic": {
                    "type": "string",
                    "description": "Тема для поиска примеров кода"
                },
                "language": {
                    "type": "string",
                    "description": "Язык программирования (опционально)",
                    "examples": ["python", "javascript", "java"]
                },
                "top_k": {
                    "type": "integer",
                    "description": "Количество результатов для анализа",
                    "default": 10
                }
            },
            "required": ["topic"]
        }
