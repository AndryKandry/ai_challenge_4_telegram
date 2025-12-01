"""
Модуль для реранкинга результатов поиска с использованием Cross-Encoder моделей.
Улучшает релевантность результатов RAG-системы.
"""

import logging
import json
import numpy as np
from typing import List, Dict, Optional, Tuple
import requests
from pathlib import Path

logger = logging.getLogger('embeddings.reranker')


class OllamaReranker:
    """
    Реранкер на основе моделей, доступных через Ollama.
    Использует cross-encoder модели для более точной оценки релевантности.
    """

    def __init__(
        self,
        model_name: str = "bge-reranker-base",
        ollama_url: str = "http://localhost:11434",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Инициализация реранкера.

        Args:
            model_name: Название модели для реранкинга (доступна через Ollama)
            ollama_url: URL Ollama API
            timeout: Таймаут запроса
            max_retries: Максимальное количество попыток
            retry_delay: Задержка между попытками
        """
        self.model_name = model_name
        self.ollama_url = ollama_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Проверяем доступность модели
        self._check_model_availability()

        logger.info(f"OllamaReranker initialized: model={model_name}, url={ollama_url}")

    def _check_model_availability(self) -> None:
        """Проверяет доступность модели в Ollama."""
        try:
            response = requests.get(
                f"{self.ollama_url}/api/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model.get('name', '') for model in models]
                
                if self.model_name not in model_names:
                    logger.warning(f"Model '{self.model_name}' not found in Ollama. "
                                 f"Available models: {model_names}")
                    logger.info(f"Attempting to pull model '{self.model_name}'...")
                    self._pull_model()
                else:
                    logger.info(f"Model '{self.model_name}' is available in Ollama")
            else:
                logger.error(f"Failed to check Ollama models: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")

    def _pull_model(self) -> None:
        """Загружает модель в Ollama."""
        try:
            logger.info(f"Pulling model '{self.model_name}' from Ollama...")
            response = requests.post(
                f"{self.ollama_url}/api/pull",
                json={"name": self.model_name},
                timeout=300  # 5 минут на загрузку
            )
            
            if response.status_code == 200:
                logger.info(f"Model '{self.model_name}' pulled successfully")
            else:
                logger.error(f"Failed to pull model: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error pulling model: {e}")

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Выполняет реранкинг документов по запросу.

        Args:
            query: Поисковый запрос
            documents: Список документов с метаданными
            top_k: Количество документов для возврата (если None, возвращаются все)

        Returns:
            Отсортированный список документов с оценками реранкинга
        """
        if not documents:
            logger.warning("No documents provided for reranking")
            return []

        if len(documents) == 1:
            logger.debug("Only one document, skipping reranking")
            return documents

        logger.info(f"Reranking {len(documents)} documents for query: '{query[:50]}...'")

        try:
            # Подготовка пар (запрос, документ)
            pairs = []
            for doc in documents:
                text = doc.get('text', '')
                pairs.append((query, text))

            # Получаем оценки реранкинга
            rerank_scores = self._compute_rerank_scores(pairs)

            # Добавляем оценки реранкинга к документам
            reranked_docs = []
            for i, doc in enumerate(documents):
                doc_copy = doc.copy()
                doc_copy['rerank_score'] = rerank_scores[i]
                reranked_docs.append(doc_copy)

            # Сортируем по убыванию оценки реранкинга
            reranked_docs.sort(key=lambda x: x['rerank_score'], reverse=True)

            # Ограничиваем количество результатов если нужно
            if top_k:
                reranked_docs = reranked_docs[:top_k]

            top_scores = [f'{doc.get("rerank_score", 0):.3f}' for doc in reranked_docs[:3]]
            logger.info(f"Reranking completed. Top scores: {top_scores}")

            return reranked_docs

        except Exception as e:
            logger.error(f"Error during reranking: {e}", exc_info=True)
            # Возвращаем исходный порядок в случае ошибки
            return documents

    def _compute_rerank_scores(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        Вычисляет оценки реранкинга для пар (запрос, документ).

        Args:
            pairs: Список пар (query, document)

        Returns:
            Список оценок релевантности
        """
        scores = []
        
        for query, document in pairs:
            try:
                score = self._compute_single_score(query, document)
                scores.append(score)
            except Exception as e:
                logger.warning(f"Error computing score for pair: {e}")
                scores.append(0.0)  # Минимальная оценка в случае ошибки

        return scores

    def _compute_single_score(self, query: str, document: str) -> float:
        """
        Вычисляет оценку релевантности для одной пары.

        Args:
            query: Запрос
            document: Документ

        Returns:
            Оценка релевантности (0.0 - 1.0)
        """
        # Подготовка промпта для cross-encoder
        prompt = f"Query: {query}\nDocument: {document}\nRelevance (0-1):"
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.0,  # Детерминированный результат
                            "max_tokens": 10     # Только оценка
                        }
                    },
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get('response', '').strip()
                    
                    # Извлекаем числовую оценку
                    score = self._parse_score(response_text)
                    return score

                else:
                    logger.warning(f"HTTP {response.status_code} from Ollama API")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.warning(f"Error (attempt {attempt + 1}/{self.max_retries}): {e}")

            if attempt < self.max_retries - 1:
                import time
                time.sleep(self.retry_delay)

        logger.error("Failed to compute rerank score after all retries")
        return 0.0

    def _parse_score(self, response_text: str) -> float:
        """
        Извлекает числовую оценку из ответа модели.

        Args:
            response_text: Ответ от модели

        Returns:
            Числовая оценка от 0.0 до 1.0
        """
        try:
            # Ищем число в ответе
            import re
            
            # Ищем числа от 0 до 1
            matches = re.findall(r'0?\.\d+|1\.0|0|1', response_text)
            
            if matches:
                score = float(matches[0])
                # Нормализуем в диапазон 0.0 - 1.0
                return max(0.0, min(1.0, score))
            else:
                # Пробуем преобразовать весь ответ
                score = float(response_text.strip())
                return max(0.0, min(1.0, score))
                
        except Exception as e:
            logger.warning(f"Error parsing score from '{response_text}': {e}")
            return 0.5  # Средняя оценка по умолчанию

    def get_model_info(self) -> Dict:
        """
        Возвращает информацию о модели реранкинга.

        Returns:
            Словарь с информацией о модели
        """
        return {
            'model_name': self.model_name,
            'ollama_url': self.ollama_url,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'available': True  # TODO: можно добавить реальную проверку доступности
        }


class SimpleReranker:
    """
    Простой реранкер на основе улучшенной метрики схожести.
    Используется как fallback когда Ollama недоступен.
    """

    def __init__(self, weight_similarity: float = 0.7, weight_length: float = 0.3):
        """
        Инициализация простого реранкера.

        Args:
            weight_similarity: Вес косинусного сходства
            weight_length: Вес учета длины документа
        """
        self.weight_similarity = weight_similarity
        self.weight_length = weight_length
        
        logger.info(f"SimpleReranker initialized: similarity_weight={weight_similarity}, length_weight={weight_length}")

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Выполняет простой реранкинг документов.

        Args:
            query: Поисковый запрос
            documents: Список документов с метаданными
            top_k: Количество документов для возврата

        Returns:
            Отсортированный список документов с оценками реранкинга
        """
        if not documents:
            return []

        logger.info(f"Simple reranking {len(documents)} documents")

        reranked_docs = []
        
        for doc in documents:
            # Базовая оценка - косинусное сходство
            similarity = doc.get('similarity_score', 0.0)
            
            # Дополнительный фактор - длина документа (предпочитаем среднюю длину)
            text = doc.get('text', '')
            length_score = self._compute_length_score(text)
            
            # Комбинированная оценка
            combined_score = (
                self.weight_similarity * similarity +
                self.weight_length * length_score
            )
            
            doc_copy = doc.copy()
            doc_copy['rerank_score'] = combined_score
            reranked_docs.append(doc_copy)

        # Сортируем по убыванию оценки
        reranked_docs.sort(key=lambda x: x['rerank_score'], reverse=True)

        if top_k:
            reranked_docs = reranked_docs[:top_k]

        return reranked_docs

    def _compute_length_score(self, text: str) -> float:
        """
        Вычисляет оценку на основе длины текста.

        Args:
            text: Текст документа

        Returns:
            Оценка от 0.0 до 1.0
        """
        if not text:
            return 0.0

        # Оптимальная длина - 200-800 символов
        length = len(text)
        
        if 200 <= length <= 800:
            return 1.0
        elif length < 200:
            return length / 200.0
        else:
            # Штраф за слишком длинные документы
            return max(0.0, 1.0 - (length - 800) / 2000.0)


class AdvancedReranker:
    """
    Комплексный реранкер с комбинированной оценкой релевантности.
    
    Комбинирует:
    - BM25 для текстовой релевантности
    - Cross-encoder для семантической релевантности  
    - Временные факторы (свежесть)
    - Метаданные документов
    """

    def __init__(
        self,
        model_name: str = "bge-reranker-base",
        ollama_url: str = "http://localhost:11434",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        bm25_weight: float = 0.3,
        semantic_weight: float = 0.5,
        recency_weight: float = 0.15,
        metadata_weight: float = 0.05
    ):
        """
        Инициализация AdvancedReranker.

        Args:
            model_name: Название модели для реранкинга
            ollama_url: URL Ollama API
            timeout: Таймаут запроса
            max_retries: Максимальное количество попыток
            retry_delay: Задержка между попытками
            bm25_weight: Вес BM25 релевантности
            semantic_weight: Вес семантической релевантности
            recency_weight: Вес временного фактора
            metadata_weight: Вес метаданных
        """
        self.model_name = model_name
        self.ollama_url = ollama_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Веса для комбинирования скоров
        self.bm25_weight = bm25_weight
        self.semantic_weight = semantic_weight
        self.recency_weight = recency_weight
        self.metadata_weight = metadata_weight
        
        # Проверяем сумму весов
        total_weight = bm25_weight + semantic_weight + recency_weight + metadata_weight
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total_weight:.3f}, normalizing to 1.0")
            self.bm25_weight /= total_weight
            self.semantic_weight /= total_weight
            self.recency_weight /= total_weight
            self.metadata_weight /= total_weight
        
        # Инициализация компонентов
        self.bm25 = None
        self.cross_encoder = None
        
        # Проверяем доступность модели
        self._check_model_availability()
        
        logger.info(f"AdvancedReranker initialized: model={model_name}")
        logger.info(f"Weights: BM25={self.bm25_weight:.3f}, "
                   f"Semantic={self.semantic_weight:.3f}, "
                   f"Recency={self.recency_weight:.3f}, "
                   f"Metadata={self.metadata_weight:.3f}")

    def _check_model_availability(self) -> None:
        """Проверяет доступность модели в Ollama."""
        try:
            import requests
            response = requests.get(
                f"{self.ollama_url}/api/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model.get('name', '') for model in models]
                
                if self.model_name not in model_names:
                    logger.warning(f"Model '{self.model_name}' not found in Ollama")
                    logger.info(f"Attempting to pull model '{self.model_name}'...")
                    self._pull_model()
                else:
                    logger.info(f"Model '{self.model_name}' is available in Ollama")
            else:
                logger.error(f"Failed to check Ollama models: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")

    def _pull_model(self) -> None:
        """Загружает модель в Ollama."""
        try:
            import requests
            logger.info(f"Pulling model '{self.model_name}' from Ollama...")
            response = requests.post(
                f"{self.ollama_url}/api/pull",
                json={"name": self.model_name},
                timeout=300  # 5 минут на загрузку
            )
            
            if response.status_code == 200:
                logger.info(f"Model '{self.model_name}' pulled successfully")
            else:
                logger.error(f"Failed to pull model: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error pulling model: {e}")

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Выполняет комплексный реранкинг документов.

        Args:
            query: Поисковый запрос
            documents: Список документов с метаданными
            top_k: Количество документов для возврата

        Returns:
            Отсортированный список документов с оценками реранкинга
        """
        if not documents:
            logger.warning("No documents provided for reranking")
            return []

        if len(documents) == 1:
            logger.debug("Only one document, skipping reranking")
            return documents

        logger.info(f"Advanced reranking {len(documents)} documents for query: '{query[:50]}...'")

        try:
            # 1. BM25 релевантность
            bm25_scores = self._compute_bm25_scores(query, documents)
            
            # 2. Семантическая релевантность через cross-encoder
            semantic_scores = self._compute_semantic_scores(query, documents)
            
            # 3. Временные факторы
            recency_scores = self._compute_recency_scores(documents)
            
            # 4. Метаданные
            metadata_scores = self._compute_metadata_scores(query, documents)
            
            # 5. Комбинирование всех скоров
            final_scores = []
            for i, doc in enumerate(documents):
                combined_score = (
                    self.bm25_weight * bm25_scores[i] +
                    self.semantic_weight * semantic_scores[i] +
                    self.recency_weight * recency_scores[i] +
                    self.metadata_weight * metadata_scores[i]
                )
                
                final_scores.append(combined_score)
            
            # 6. Создание обогащенных документов
            reranked_docs = []
            for i, (doc, final_score) in enumerate(zip(documents, final_scores)):
                enriched_doc = doc.copy()
                enriched_doc.update({
                    'rerank_score': final_score,
                    'bm25_score': bm25_scores[i],
                    'semantic_score': semantic_scores[i],
                    'recency_score': recency_scores[i],
                    'metadata_score': metadata_scores[i]
                })
                reranked_docs.append(enriched_doc)
            
            # 7. Сортировка по финальному скору
            reranked_docs.sort(key=lambda x: x['rerank_score'], reverse=True)

            # 8. Ограничение количества результатов
            if top_k:
                reranked_docs = reranked_docs[:top_k]

            # 9. Логирование топ результатов
            top_scores = [f'{doc["rerank_score"]:.3f}' for doc in reranked_docs[:3]]
            logger.info(f"Advanced reranking completed. Top scores: {top_scores}")

            return reranked_docs

        except Exception as e:
            logger.error(f"Error during advanced reranking: {e}", exc_info=True)
            # Возвращаем исходный порядок в случае ошибки
            return documents

    def _compute_bm25_scores(self, query: str, documents: List[Dict]) -> List[float]:
        """Вычисляет BM25 оценки релевантности."""
        try:
            from rank_bm25 import BM25Okapi
            
            # Токенизация запроса и документов
            tokenized_query = query.lower().split()
            tokenized_docs = [doc.get('text', '').lower().split() for doc in documents]
            
            # Создание BM25 модели
            bm25 = BM25Okapi(tokenized_docs)
            
            # Вычисление скоров
            scores = bm25.get_scores(tokenized_query)
            
            # Нормализация в [0, 1]
            if scores:
                max_score = max(scores)
                if max_score > 0:
                    scores = [s / max_score for s in scores]
            
            return scores
            
        except ImportError:
            logger.warning("rank_bm25 not available, using simple keyword matching")
            return self._compute_simple_keyword_scores(query, documents)
        except Exception as e:
            logger.error(f"Error computing BM25 scores: {e}")
            return [0.0] * len(documents)

    def _compute_simple_keyword_scores(self, query: str, documents: List[Dict]) -> List[float]:
        """Вычисляет простую оценку по ключевым словам как fallback для BM25."""
        query_words = set(query.lower().split())
        scores = []
        
        for doc in documents:
            text = doc.get('text', '').lower()
            text_words = set(text.split())
            
            # Jaccard similarity
            intersection = len(query_words.intersection(text_words))
            union = len(query_words.union(text_words))
            
            score = intersection / union if union > 0 else 0.0
            scores.append(score)
        
        return scores

    def _compute_semantic_scores(self, query: str, documents: List[Dict]) -> List[float]:
        """Вычисляет семантическую релевантность через cross-encoder."""
        scores = []
        
        for doc in documents:
            try:
                score = self._compute_single_semantic_score(query, doc.get('text', ''))
                scores.append(score)
            except Exception as e:
                logger.warning(f"Error computing semantic score: {e}")
                scores.append(0.0)
        
        return scores

    def _compute_single_semantic_score(self, query: str, document: str) -> float:
        """Вычисляет семантическую оценку для одной пары."""
        # Подготовка промпта для cross-encoder
        prompt = f"Query: {query}\nDocument: {document}\nRelevance (0-1):"
        
        for attempt in range(self.max_retries):
            try:
                import requests
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.0,  # Детерминированный результат
                            "max_tokens": 10     # Только оценка
                        }
                    },
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get('response', '').strip()
                    
                    # Извлекаем числовую оценку
                    score = self._parse_score(response_text)
                    return score

                else:
                    logger.warning(f"HTTP {response.status_code} from Ollama API")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.warning(f"Error (attempt {attempt + 1}/{self.max_retries}): {e}")

            if attempt < self.max_retries - 1:
                import time
                time.sleep(self.retry_delay)

        logger.error("Failed to compute semantic score after all retries")
        return 0.0

    def _parse_score(self, response_text: str) -> float:
        """Извлекает числовую оценку из ответа модели."""
        try:
            import re
            
            # Ищем числа от 0 до 1
            matches = re.findall(r'0?\.\d+|1\.0|0|1', response_text)
            
            if matches:
                score = float(matches[0])
                # Нормализуем в диапазон 0.0 - 1.0
                return max(0.0, min(1.0, score))
            else:
                # Пробуем преобразовать весь ответ
                score = float(response_text.strip())
                return max(0.0, min(1.0, score))
                
        except Exception as e:
            logger.warning(f"Error parsing score from '{response_text}': {e}")
            return 0.5  # Средняя оценка по умолчанию

    def _compute_recency_scores(self, documents: List[Dict]) -> List[float]:
        """Вычисляет временные факторы (свежесть)."""
        from datetime import datetime
        
        scores = []
        now = datetime.now()
        
        for doc in documents:
            # Пытаемся получить временную метку
            last_modified = doc.get('last_modified')
            indexed_at = doc.get('indexed_at')
            
            if last_modified:
                try:
                    # Парсим дату
                    if isinstance(last_modified, str):
                        mod_time = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
                    else:
                        mod_time = last_modified
                    
                    # Вычисляем "возраст" в днях
                    age_days = (now - mod_time).days
                    
                    # Чем новее документ, тем выше скор
                    # Экспоненциальное затухание: score = exp(-age_days/30)
                    score = max(0.0, min(1.0, 2.71828 ** (-age_days / 30)))
                    
                except Exception:
                    score = 0.5  # Средняя оценка при ошибке
                    
            elif indexed_at:
                try:
                    idx_time = datetime.fromisoformat(indexed_at.replace('Z', '+00:00'))
                    age_days = (now - idx_time).days
                    score = max(0.0, min(1.0, 2.71828 ** (-age_days / 30)))
                except Exception:
                    score = 0.5
            else:
                # Нет временной информации
                score = 0.3
            
            scores.append(score)
        
        return scores

    def _compute_metadata_scores(self, query: str, documents: List[Dict]) -> List[float]:
        """Вычисляет оценки на основе метаданных документов."""
        query_lower = query.lower()
        scores = []
        
        for doc in documents:
            score = 0.0
            
            # Проверяем релевантность имени файла
            file_name = doc.get('file_name', '').lower()
            if any(word in file_name for word in query_lower.split()):
                score += 0.3
            
            # Проверяем тип файла
            file_type = doc.get('file_type', '').lower()
            if file_type in ['md', 'markdown'] and any(word in query_lower for word in ['документация', 'инструкция']):
                score += 0.2
            elif file_type in ['py', 'js', 'ts'] and any(word in query_lower for word in ['код', 'функция', 'класс']):
                score += 0.2
            
            # Проверяем наличие релевантных функций/классов
            functions = doc.get('functions', [])
            classes = doc.get('classes', [])
            
            for func in functions:
                if any(word in func.lower() for word in query_lower.split()):
                    score += 0.1
                    break
            
            for cls in classes:
                if any(word in cls.lower() for word in query_lower.split()):
                    score += 0.1
                    break
            
            # Нормализуем в [0, 1]
            scores.append(min(score, 1.0))
        
        return scores

    def get_model_info(self) -> Dict:
        """
        Возвращает информацию о модели реранкинга.

        Returns:
            Словарь с информацией о модели
        """
        return {
            'model_name': self.model_name,
            'ollama_url': self.ollama_url,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'weights': {
                'bm25': self.bm25_weight,
                'semantic': self.semantic_weight,
                'recency': self.recency_weight,
                'metadata': self.metadata_weight
            },
            'type': 'advanced'
        }


def create_reranker(reranker_type: str = "ollama", **kwargs) -> object:
    """
    Фабрика для создания реранкера.

    Args:
        reranker_type: Тип реранкера ("ollama", "simple", "advanced")
        **kwargs: Дополнительные параметры для реранкера

    Returns:
        Экземпляр реранкера
    """
    if reranker_type == "ollama":
        return OllamaReranker(**kwargs)
    elif reranker_type == "simple":
        return SimpleReranker(**kwargs)
    elif reranker_type == "advanced":
        return AdvancedReranker(**kwargs)
    else:
        raise ValueError(f"Unknown reranker type: {reranker_type}")
