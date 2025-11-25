"""
Модуль для семантического поиска по индексу с использованием эмбеддингов.
"""

import json
import logging
import os
from typing import List, Dict, Optional
import numpy as np
from datetime import datetime, timedelta

from src.embeddings.embedder import OllamaEmbedder

logger = logging.getLogger('embeddings.searcher')


class SemanticSearcher:
    """Выполняет семантический поиск по индексу."""

    def __init__(
        self,
        index_path: str = "data/embeddings/document_index.json",
        embedder: Optional[OllamaEmbedder] = None,
        cache_ttl: int = 3600
    ):
        """
        Args:
            index_path: Путь к индексу
            embedder: Экземпляр OllamaEmbedder (создаётся автоматически если None)
            cache_ttl: Время жизни кэша запросов в секундах
        """
        self.index_path = index_path
        self.embedder = embedder or OllamaEmbedder()
        self.cache_ttl = cache_ttl

        self.index = {}
        self.query_cache = {}  # {query: (embedding, timestamp)}

        logger.info(f"SemanticSearcher initialized: index_path={index_path}")

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
        filter_by_type: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Выполняет семантический поиск.

        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            min_similarity: Минимальное косинусное сходство
            filter_by_type: Фильтр по типу файлов ['md', 'txt']

        Returns:
            Список релевантных чанков с оценками
        """
        if not query or not query.strip():
            logger.warning("Empty query provided")
            return []

        logger.info(f"Searching for: '{query}' (top_k={top_k}, min_sim={min_similarity})")

        # Загружаем индекс если не загружен
        if not self.index:
            if not self._load_index():
                logger.error("Failed to load index")
                return []

        chunks = self.index.get('chunks', [])
        if not chunks:
            logger.warning("No chunks in index")
            return []

        # Получаем эмбеддинг запроса (с кэшированием)
        query_embedding = self._get_query_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []

        # Вычисляем сходство со всеми чанками
        similarities = []

        for chunk in chunks:
            # Применяем фильтр по типу файла если указан
            if filter_by_type:
                file_type = chunk.get('metadata', {}).get('file_type', '')
                if file_type not in filter_by_type:
                    continue

            chunk_embedding = chunk.get('embedding')
            if not chunk_embedding:
                continue

            # Вычисляем косинусное сходство
            similarity = self.compute_similarity(query_embedding, chunk_embedding)

            # Проверяем минимальный порог
            if similarity >= min_similarity:
                similarities.append({
                    'chunk_id': chunk.get('chunk_id'),
                    'text': chunk.get('text'),
                    'source_file': chunk.get('source_file'),
                    'similarity_score': float(similarity),
                    'metadata': chunk.get('metadata', {})
                })

        # Сортируем по убыванию схожести
        similarities.sort(key=lambda x: x['similarity_score'], reverse=True)

        # Берём топ-K результатов
        results = similarities[:top_k]

        logger.info(f"Found {len(results)} results (from {len(similarities)} matches)")

        return results

    def compute_similarity(
        self,
        query_embedding: List[float],
        chunk_embedding: List[float]
    ) -> float:
        """
        Вычисляет косинусное сходство.

        Args:
            query_embedding: Вектор запроса
            chunk_embedding: Вектор чанка

        Returns:
            Значение от -1 до 1 (чем больше, тем более похожи)
        """
        # Преобразуем в numpy arrays
        vec1 = np.array(query_embedding, dtype=np.float32)
        vec2 = np.array(chunk_embedding, dtype=np.float32)

        # Проверяем размерность
        if vec1.shape != vec2.shape:
            logger.warning(f"Dimension mismatch: {vec1.shape} vs {vec2.shape}")
            return 0.0

        # Вычисляем косинусное сходство
        # cos(θ) = (A · B) / (||A|| * ||B||)
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        return float(similarity)

    def _load_index(self) -> bool:
        """
        Загружает индекс из JSON.

        Returns:
            True если индекс успешно загружен
        """
        if not os.path.exists(self.index_path):
            logger.error(f"Index file not found: {self.index_path}")
            return False

        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                self.index = json.load(f)

            total_chunks = len(self.index.get('chunks', []))
            logger.info(f"Index loaded: {total_chunks} chunks")

            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in index: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            return False

    def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Получает эмбеддинг запроса с кэшированием.

        Args:
            query: Поисковый запрос

        Returns:
            Вектор эмбеддинга или None
        """
        # Проверяем кэш
        if query in self.query_cache:
            cached_embedding, timestamp = self.query_cache[query]

            # Проверяем актуальность кэша
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                logger.debug(f"Using cached embedding for query: '{query}'")
                return cached_embedding
            else:
                # Кэш устарел, удаляем
                del self.query_cache[query]

        # Генерируем новый эмбеддинг
        try:
            embedding = self.embedder.embed_text(query)

            # Сохраняем в кэш
            self.query_cache[query] = (embedding, datetime.now())

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for query: {e}")
            return None

    def clear_cache(self) -> None:
        """Очищает кэш запросов."""
        self.query_cache.clear()
        logger.info("Query cache cleared")

    def reload_index(self) -> bool:
        """
        Перезагружает индекс из файла.

        Returns:
            True если индекс успешно перезагружен
        """
        self.index = {}
        return self._load_index()

    def get_index_info(self) -> Dict:
        """
        Возвращает информацию об индексе.

        Returns:
            Словарь с метаданными индекса
        """
        if not self.index:
            self._load_index()

        return {
            'total_chunks': len(self.index.get('chunks', [])),
            'total_documents': len(self.index.get('documents', [])),
            'embedding_model': self.index.get('embedding_model'),
            'embedding_dimension': self.index.get('embedding_dimension'),
            'created_at': self.index.get('created_at'),
            'updated_at': self.index.get('updated_at')
        }
