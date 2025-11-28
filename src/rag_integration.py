"""
Модуль для интеграции RAG (Retrieval-Augmented Generation) с LLM провайдерами.
Обеспечивает семантический поиск и обогащение контекста для DeepSeek.
"""

import logging
import yaml
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from src.embeddings.embedder import OllamaEmbedder
from src.embeddings.searcher import SemanticSearcher
from src.embeddings.reranker import create_reranker

logger = logging.getLogger(__name__)


class RAGManager:
    """Менеджер для управления RAG функциональностью."""

    def __init__(
        self,
        config_path: str = "config/embeddings_config.yaml",
        index_path: Optional[str] = None
    ):
        """
        Инициализация RAG менеджера.

        Args:
            config_path: Путь к конфигурации эмбеддингов
            index_path: Путь к индексу (если None, берётся из конфига)
        """
        self.config = self._load_config(config_path)

        # Получаем параметры из конфига
        indexing_config = self.config.get('indexing', {})
        self.index_path = index_path or indexing_config.get(
            'index_path',
            'data/embeddings/document_index.json'
        )

        search_config = self.config.get('search', {})
        self.top_k = search_config.get('top_k', 3)
        self.min_similarity = search_config.get('min_similarity', 0.6)

        deepseek_config = self.config.get('deepseek_integration', {})
        self.context_chunks = deepseek_config.get('context_chunks', 3)
        self.max_context_tokens = deepseek_config.get('max_context_tokens', 2000)
        self.rag_keywords = deepseek_config.get('rag_keywords', [])

        # Инициализация компонентов
        ollama_config = self.config.get('ollama', {})
        self.embedder = OllamaEmbedder(**ollama_config)
        self.searcher = SemanticSearcher(
            index_path=self.index_path,
            embedder=self.embedder
        )

        # Инициализация реранкера
        reranker_config = self.config.get('reranker', {})
        reranker_type = reranker_config.get('type', 'simple')
        reranker_params = reranker_config.get('params', {})
        
        # Фильтруем параметры в зависимости от типа реранкера
        if reranker_type == 'simple':
            # SimpleReranker принимает только weight_similarity и weight_length
            filtered_params = {
                k: v for k, v in reranker_params.items() 
                if k in ['weight_similarity', 'weight_length']
            }
        else:
            # OllamaReranker принимает все параметры
            filtered_params = reranker_params
        
        self.reranker = create_reranker(reranker_type, **filtered_params)
        
        # Параметры цитирования
        self.citation_config = self.config.get('citation', {})
        self.default_sources_count = self.citation_config.get('default_sources_count', 5)
        self.enable_citations = self.citation_config.get('enabled', True)

        self.enabled = True

        logger.info(f"RAGManager initialized: index_path={self.index_path}")

    def _load_config(self, config_path: str) -> dict:
        """
        Загружает конфигурацию из YAML файла.

        Args:
            config_path: Путь к файлу конфигурации

        Returns:
            Словарь с конфигурацией
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            return {}

    def should_use_rag(self, user_message: str) -> bool:
        """
        Определяет, нужно ли использовать RAG для данного запроса.

        Args:
            user_message: Сообщение от пользователя

        Returns:
            True если RAG должен быть использован
        """
        if not self.enabled:
            return False

        # Проверяем наличие ключевых слов
        message_lower = user_message.lower()

        for keyword in self.rag_keywords:
            if keyword.lower() in message_lower:
                logger.info(f"RAG triggered by keyword: '{keyword}'")
                return True

        return False

    def search_relevant_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None
    ) -> List[Dict]:
        """
        Ищет релевантный контекст для запроса.

        Args:
            query: Поисковый запрос
            top_k: Количество результатов (если None, используется из конфига)
            min_similarity: Минимальное сходство (если None, используется из конфига)

        Returns:
            Список релевантных чанков с метаданными
        """
        top_k = top_k or self.context_chunks
        min_similarity = min_similarity or self.min_similarity

        try:
            results = self.searcher.search(
                query=query,
                top_k=top_k,
                min_similarity=min_similarity
            )

            logger.info(f"Found {len(results)} relevant documents for query")
            return results

        except Exception as e:
            logger.error(f"Error searching relevant context: {e}", exc_info=True)
            return []

    def format_rag_context(
        self,
        user_message: str,
        search_results: List[Dict]
    ) -> str:
        """
        Форматирует контекст RAG для добавления в промпт.

        Args:
            user_message: Исходное сообщение пользователя
            search_results: Результаты поиска

        Returns:
            Отформатированный контекст
        """
        if not search_results:
            return user_message

        # Получаем шаблон из конфига
        deepseek_config = self.config.get('deepseek_integration', {})
        template = deepseek_config.get('context_template', '')

        # Формируем текст контекста
        context_parts = []
        for i, result in enumerate(search_results, 1):
            source_file = Path(result['source_file']).name
            text = result['text'][:500]  # Ограничиваем длину
            similarity = result['similarity_score']

            context_parts.append(
                f"[Документ {i}: {source_file} (релевантность: {similarity:.2f})]\n{text}"
            )

        context_text = "\n\n".join(context_parts)

        # Используем шаблон из конфига
        if template:
            formatted = template.format(
                context=context_text,
                query=user_message
            )
        else:
            # Fallback формат
            formatted = (
                f"Контекст из документации:\n"
                f"---\n"
                f"{context_text}\n"
                f"---\n\n"
                f"Вопрос пользователя: {user_message}"
            )

        return formatted

    def enrich_message_with_rag(
        self,
        user_message: str,
        use_reranking: bool = True
    ) -> Tuple[str, List[Dict]]:
        """
        Обогащает сообщение пользователя контекстом из RAG.

        Args:
            user_message: Исходное сообщение
            use_reranking: Использовать ли реранкинг

        Returns:
            Кортеж (обогащенное_сообщение, список_источников)
        """
        # Проверяем, нужно ли использовать RAG
        if not self.should_use_rag(user_message):
            logger.debug("RAG not triggered for this message")
            return user_message, []

        # Ищем релевантный контекст (используем больше документов для реранкинга)
        initial_top_k = self.context_chunks * 2 if use_reranking else self.context_chunks
        search_results = self.search_relevant_context(user_message, top_k=initial_top_k)

        if not search_results:
            logger.info("No relevant context found, returning original message")
            return user_message, []

        # Применяем реранкинг если включен
        if use_reranking and len(search_results) > 1:
            search_results = self.reranker.rerank(
                query=user_message,
                documents=search_results,
                top_k=self.context_chunks
            )
            logger.info(f"Applied reranking, got {len(search_results)} results")
        
        # Обогащаем метаданные для цитирования
        enhanced_results = self._enrich_with_citation_metadata(search_results)

        # Форматируем обогащенное сообщение
        enriched_message = self.format_rag_context(user_message, enhanced_results)

        logger.info(
            f"Message enriched with {len(enhanced_results)} relevant documents"
        )

        return enriched_message, enhanced_results

    def _enrich_with_citation_metadata(self, search_results: List[Dict]) -> List[Dict]:
        """
        Обогащает результаты поиска метаданными для цитирования.

        Args:
            search_results: Результаты поиска

        Returns:
            Обогащенные результаты с метаданными для цитирования
        """
        enhanced_results = []
        
        for i, result in enumerate(search_results):
            enhanced_result = result.copy()
            
            # Вычисляем релевантность в процентах
            similarity = result.get('similarity_score', 0.0)
            rerank_score = result.get('rerank_score', similarity)
            relevance_percentage = max(similarity, rerank_score) * 100
            
            # Добавляем метаданные для цитирования
            enhanced_result.update({
                'citation_index': i + 1,
                'source_file_name': Path(result['source_file']).name,
                'chunk_id': result.get('chunk_id', f'chunk_{i}'),
                'line_numbers': self._extract_line_numbers(result),
                'relevance_score': relevance_percentage,
                'relevance_percentage': f"{relevance_percentage:.0f}%"
            })
            
            enhanced_results.append(enhanced_result)
        
        return enhanced_results

    def _extract_line_numbers(self, result: Dict) -> str:
        """
        Извлекает номера строк из метаданных результата.

        Args:
            result: Результат поиска

        Returns:
            Строка с номерами строк
        """
        metadata = result.get('metadata', {})
        
        # Пытаемся получить номера строк из метаданных
        char_start = metadata.get('char_start')
        char_end = metadata.get('char_end')
        
        if char_start is not None and char_end is not None:
            # Приблизительное определение строк (примерно 50 символов на строку)
            line_start = max(1, char_start // 50 + 1)
            line_end = max(line_start, char_end // 50 + 1)
            return f"{line_start}-{line_end}"
        
        # Fallback: используем chunk_index
        chunk_index = result.get('chunk_index', 0)
        return f"{chunk_index * 10 + 1}-{chunk_index * 10 + 20}"

    def format_citations(self, search_results: List[Dict], max_sources: Optional[int] = None) -> str:
        """
        Форматирует цитаты для включения в ответ модели.

        Args:
            search_results: Результаты поиска RAG
            max_sources: Максимальное количество источников (если None, используется из конфига)

        Returns:
            Отформатированная строка с цитатами
        """
        if not search_results or not self.enable_citations:
            return ""
        
        # Ограничиваем количество источников
        max_sources = max_sources or self.default_sources_count
        sources_to_use = search_results[:max_sources]
        
        citations = "\n\nИсточники:\n"
        
        for result in sources_to_use:
            citation_index = result.get('citation_index', 0)
            source_file = result.get('source_file_name', 'unknown')
            chunk_id = result.get('chunk_id', 'unknown')
            line_numbers = result.get('line_numbers', 'unknown')
            relevance = result.get('relevance_percentage', '0%')
            
            citations += (
                f"[{citation_index}] Источник: {source_file}, "
                f"чанк {chunk_id}, строки {line_numbers}, "
                f"релевантность: {relevance}\n"
            )
        
        return citations

    def create_citation_prompt(self, user_message: str, search_results: List[Dict]) -> str:
        """
        Создает промпт для DeepSeek с требованием цитирования источников.

        Args:
            user_message: Исходное сообщение пользователя
            search_results: Результаты поиска

        Returns:
            Промпт с требованием цитирования
        """
        if not search_results or not self.enable_citations:
            return user_message
        
        citation_instruction = """
ВАЖНО: Вы должны включить цитаты на источники в свой ответ.

Инструкция по цитированию:
- Используйте информацию из предоставленного контекста
- Включайте ссылки на источники в квадратных скобках [1], [2] и т.д.
- Номер в скобках должен соответствовать номеру источника в списке
- Ссылки должны размещаться после информации, которая взята из данного источника
- Если информация из нескольких источников, перечислите все номера через запятую: [1,3]

Пример цитирования в ответе:
"Согласно документации [1], система работает с эмбеддингами размером 1024 [2,3]."

Формат источников будет предоставлен после вашего ответа.
"""
        
        # Получаем шаблон из конфига или используем стандартный
        deepseek_config = self.config.get('deepseek_integration', {})
        template = deepseek_config.get('citation_template')
        
        if template:
            return template.format(
                citation_instruction=citation_instruction,
                context=self.format_rag_context(user_message, search_results),
                query=user_message
            )
        else:
            # Стандартный формат с цитированием
            context = self.format_rag_context(user_message, search_results)
            return f"{citation_instruction}\n\n{context}"

    def format_sources_info(self, search_results: List[Dict]) -> str:
        """
        Форматирует информацию об источниках для отображения пользователю.

        Args:
            search_results: Результаты поиска RAG

        Returns:
            Отформатированная строка с информацией об источниках
        """
        if not search_results:
            return ""

        sources_info = "\n\n📚 **Использованные источники RAG:**\n"

        for i, result in enumerate(search_results, 1):
            source_file = Path(result['source_file']).name
            similarity = result['similarity_score']

            sources_info += f"{i}. `{source_file}` (релевантность: {similarity:.2f})\n"

        return sources_info

    def reload_index(self) -> bool:
        """
        Перезагружает индекс документов.

        Returns:
            True если индекс успешно перезагружен
        """
        try:
            success = self.searcher.reload_index()
            if success:
                logger.info("RAG index reloaded successfully")
            return success
        except Exception as e:
            logger.error(f"Failed to reload RAG index: {e}")
            return False

    def get_statistics(self) -> Dict:
        """
        Возвращает статистику RAG системы.

        Returns:
            Словарь со статистикой
        """
        try:
            index_info = self.searcher.get_index_info()
            return {
                'enabled': self.enabled,
                'index_path': self.index_path,
                'total_documents': index_info.get('total_documents', 0),
                'total_chunks': index_info.get('total_chunks', 0),
                'keywords_count': len(self.rag_keywords),
                'top_k': self.context_chunks,
                'min_similarity': self.min_similarity,
                'context_chunks': self.context_chunks
            }
        except Exception as e:
            logger.error(f"Failed to get RAG statistics: {e}")
            return {}

    def enable(self) -> None:
        """Включает RAG."""
        self.enabled = True
        logger.info("RAG enabled")

    def disable(self) -> None:
        """Отключает RAG."""
        self.enabled = False
        logger.info("RAG disabled")
