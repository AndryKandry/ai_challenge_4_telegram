"""
Интеграция RAG (Retrieval Augmented Generation) с DeepSeek.
Позволяет использовать контекст из документов для более точных ответов.
"""

import logging
import tiktoken
from typing import List, Dict, Optional

from src.embeddings.searcher import SemanticSearcher

logger = logging.getLogger('integrations.deepseek_rag')


class DeepSeekRAG:
    """Интеграция RAG с DeepSeek."""

    def __init__(
        self,
        searcher: SemanticSearcher,
        context_chunks: int = 3,
        max_context_tokens: int = 2000,
        rag_keywords: Optional[List[str]] = None
    ):
        """
        Args:
            searcher: Экземпляр SemanticSearcher
            context_chunks: Количество чанков для контекста
            max_context_tokens: Максимум токенов в контексте
            rag_keywords: Ключевые слова для автоматического использования RAG
        """
        self.searcher = searcher
        self.context_chunks = context_chunks
        self.max_context_tokens = max_context_tokens

        # Ключевые слова для автоопределения необходимости RAG
        self.rag_keywords = rag_keywords or [
            "документация", "как работает", "инструкция", "руководство",
            "что такое", "объясни", "покажи пример", "как использовать",
            "расскажи про", "как настроить", "как запустить", "команды",
            "api", "установка", "конфигурация"
        ]

        # Инициализация токенизатора
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to load tokenizer: {e}, using approximate counting")
            self.encoding = None

        logger.info(f"DeepSeekRAG initialized: context_chunks={context_chunks}, "
                   f"max_tokens={max_context_tokens}")

    def query_with_context(
        self,
        user_query: str,
        use_rag: bool = True,
        min_similarity: float = 0.5
    ) -> Dict:
        """
        Подготавливает запрос с контекстом из документов.

        Args:
            user_query: Запрос пользователя
            use_rag: Использовать ли RAG
            min_similarity: Минимальное сходство для включения чанка

        Returns:
            Словарь с запросом, контекстом и метаданными
        """
        if not use_rag or not self.should_use_rag(user_query):
            logger.info("RAG not used for this query")
            return {
                'query': user_query,
                'context': '',
                'used_rag': False,
                'sources': []
            }

        # Поиск релевантных чанков
        logger.info(f"Searching for context: '{user_query}'")

        try:
            results = self.searcher.search(
                query=user_query,
                top_k=self.context_chunks,
                min_similarity=min_similarity
            )
        except Exception as e:
            logger.error(f"Error searching for context: {e}")
            return {
                'query': user_query,
                'context': '',
                'used_rag': False,
                'sources': [],
                'error': str(e)
            }

        if not results:
            logger.info("No relevant context found")
            return {
                'query': user_query,
                'context': '',
                'used_rag': False,
                'sources': []
            }

        # Форматируем контекст
        context = self.format_context(results)

        # Обрезаем контекст если слишком длинный
        context = self._truncate_context(context, self.max_context_tokens)

        # Собираем источники
        sources = [
            {
                'file': result['source_file'],
                'score': result['similarity_score']
            }
            for result in results
        ]

        logger.info(f"RAG context prepared: {len(results)} chunks, {len(sources)} sources")

        return {
            'query': user_query,
            'context': context,
            'used_rag': True,
            'sources': sources,
            'chunks_used': len(results)
        }

    def format_context(self, chunks: List[dict]) -> str:
        """
        Форматирует чанки в контекст для промпта.

        Args:
            chunks: Список релевантных чанков

        Returns:
            Отформатированный контекст
        """
        if not chunks:
            return ""

        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            source = chunk.get('source_file', 'unknown')
            text = chunk.get('text', '')
            score = chunk.get('similarity_score', 0)

            # Форматируем чанк
            context_parts.append(
                f"[Источник {i}: {source} (релевантность: {score:.2f})]\n{text}\n"
            )

        context = "\n".join(context_parts)
        return context

    def create_rag_prompt(self, user_query: str, context: str) -> str:
        """
        Создаёт промпт с контекстом для DeepSeek.

        Args:
            user_query: Запрос пользователя
            context: Контекст из документов

        Returns:
            Полный промпт
        """
        if not context:
            return user_query

        prompt_template = """Используй следующую информацию из документации для ответа на вопрос пользователя.

Контекст из документации:
---
{context}
---

Вопрос пользователя: {query}

Инструкции:
- Используй информацию из контекста для ответа
- Если в контексте нет информации для ответа, скажи об этом
- Указывай источники информации когда это уместно
- Отвечай чётко и по делу
"""

        return prompt_template.format(context=context, query=user_query)

    def should_use_rag(self, query: str) -> bool:
        """
        Определяет, нужен ли RAG для данного запроса.

        Args:
            query: Запрос пользователя

        Returns:
            True если запрос требует контекста из документов
        """
        query_lower = query.lower()

        # Проверяем наличие ключевых слов
        for keyword in self.rag_keywords:
            if keyword.lower() in query_lower:
                logger.debug(f"RAG triggered by keyword: '{keyword}'")
                return True

        return False

    def _count_tokens(self, text: str) -> int:
        """
        Подсчитывает токены в тексте.

        Args:
            text: Текст для подсчёта

        Returns:
            Количество токенов
        """
        if not text:
            return 0

        if self.encoding:
            try:
                tokens = self.encoding.encode(text)
                return len(tokens)
            except Exception as e:
                logger.warning(f"Error counting tokens: {e}")

        # Fallback: примерная оценка
        # ~1 токен = 0.75 слова (для английского и русского)
        words = len(text.split())
        return int(words * 1.33)

    def _truncate_context(self, context: str, max_tokens: int) -> str:
        """
        Обрезает контекст до заданного количества токенов.

        Args:
            context: Исходный контекст
            max_tokens: Максимум токенов

        Returns:
            Обрезанный контекст
        """
        current_tokens = self._count_tokens(context)

        if current_tokens <= max_tokens:
            return context

        logger.info(f"Truncating context: {current_tokens} -> {max_tokens} tokens")

        # Обрезаем по предложениям
        sentences = context.split('. ')
        truncated = []
        tokens_so_far = 0

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            if tokens_so_far + sentence_tokens > max_tokens:
                break

            truncated.append(sentence)
            tokens_so_far += sentence_tokens

        result = '. '.join(truncated)

        # Добавляем индикатор обрезки
        if len(truncated) < len(sentences):
            result += "\n\n[... контекст обрезан ...]"

        return result

    def add_rag_keywords(self, keywords: List[str]) -> None:
        """
        Добавляет ключевые слова для автоопределения RAG.

        Args:
            keywords: Список новых ключевых слов
        """
        self.rag_keywords.extend(keywords)
        logger.info(f"Added {len(keywords)} new RAG keywords")

    def get_stats(self) -> Dict:
        """
        Возвращает статистику использования RAG.

        Returns:
            Словарь со статистикой
        """
        index_info = self.searcher.get_index_info()

        return {
            'context_chunks': self.context_chunks,
            'max_context_tokens': self.max_context_tokens,
            'rag_keywords_count': len(self.rag_keywords),
            'index_info': index_info
        }
