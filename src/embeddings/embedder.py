"""
Модуль для генерации эмбеддингов через Ollama.
"""

import time
import logging
import requests
import numpy as np
from typing import List, Optional, Dict

logger = logging.getLogger('embeddings.embedder')


class OllamaConnectionError(Exception):
    """Исключение при недоступности Ollama."""
    pass


class OllamaEmbedder:
    """Генерирует эмбеддинги через Ollama."""

    def __init__(
        self,
        model: str = "bge-m3",
        url: str = "http://localhost:11434",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        request_delay: float = 0.1
    ):
        """
        Args:
            model: Название модели в Ollama
            url: URL Ollama API
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество попыток
            retry_delay: Задержка между попытками (секунды)
            request_delay: Задержка между запросами для предотвращения перегрузки (секунды)
        """
        self.model = model
        self.url = url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.request_delay = request_delay

        logger.info(f"OllamaEmbedder initialized: model={model}, url={url}")

    def embed_text(self, text: str) -> List[float]:
        """
        Генерирует эмбеддинг для одного текста.

        Args:
            text: Текст для генерации эмбеддинга

        Returns:
            Вектор эмбеддинга

        Raises:
            OllamaConnectionError: Если Ollama недоступен
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return []

        def make_request():
            response = requests.post(
                f"{self.url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        try:
            result = self._retry_request(make_request)
            embedding = result.get('embedding', [])

            if not embedding:
                logger.error(f"Empty embedding returned from Ollama")
                raise OllamaConnectionError("Empty embedding returned")

            # Нормализация вектора
            normalized = self._normalize_embedding(embedding)
            return normalized

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Cannot connect to Ollama at {self.url}: {e}")
            raise OllamaConnectionError(f"Ollama is not available at {self.url}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout connecting to Ollama: {e}")
            raise OllamaConnectionError("Ollama request timeout")
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Генерирует эмбеддинги для батча текстов.

        Args:
            texts: Список текстов
            batch_size: Размер батча (для Ollama обрабатывается последовательно)

        Returns:
            Список векторов эмбеддингов
        """
        embeddings = []
        total = len(texts)

        logger.info(f"Starting batch embedding: {total} texts")

        for i, text in enumerate(texts, 1):
            try:
                embedding = self.embed_text(text)
                embeddings.append(embedding)

                # Задержка между запросами для предотвращения перегрузки Ollama
                if i < total and self.request_delay > 0:
                    time.sleep(self.request_delay)

                if i % 10 == 0:
                    logger.info(f"Progress: {i}/{total} texts embedded")

            except Exception as e:
                logger.error(f"Failed to embed text {i}/{total}: {e}")
                # Добавляем пустой эмбеддинг в случае ошибки
                embeddings.append([])

        logger.info(f"Batch embedding complete: {len(embeddings)}/{total} successful")
        return embeddings

    def check_connection(self) -> bool:
        """
        Проверяет доступность Ollama.

        Returns:
            True если Ollama доступен
        """
        try:
            response = requests.get(
                f"{self.url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def get_model_info(self) -> Optional[Dict]:
        """
        Получает информацию о модели.

        Returns:
            Словарь с информацией о модели или None
        """
        try:
            response = requests.post(
                f"{self.url}/api/show",
                json={"name": self.model},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Model {self.model} not found in Ollama")
                return None

        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return None

    def _normalize_embedding(self, embedding: List[float]) -> List[float]:
        """
        Нормализует вектор (L2 norm).

        Args:
            embedding: Исходный вектор

        Returns:
            Нормализованный вектор
        """
        if not embedding:
            return embedding

        # Преобразуем в numpy array для эффективных вычислений
        vec = np.array(embedding, dtype=np.float32)

        # Вычисляем L2 норму
        norm = np.linalg.norm(vec)

        if norm == 0:
            logger.warning("Zero norm vector, returning original")
            return embedding

        # Нормализуем
        normalized = vec / norm

        return normalized.tolist()

    def _retry_request(self, func, max_retries: Optional[int] = None):
        """
        Retry-логика для запросов.

        Args:
            func: Функция для выполнения
            max_retries: Максимальное количество попыток

        Returns:
            Результат функции

        Raises:
            Exception: Если все попытки не удались
        """
        if max_retries is None:
            max_retries = self.max_retries

        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                return func()

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = self.retry_delay * (2 ** (attempt - 1))  # Экспоненциальная задержка
                    logger.warning(
                        f"Request failed (attempt {attempt}/{max_retries}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed")

        raise last_error


def check_ollama_or_exit(config: Dict) -> OllamaEmbedder:
    """
    Проверяет Ollama и возвращает embedder или выводит инструкцию.

    Args:
        config: Конфигурация с параметрами Ollama

    Returns:
        OllamaEmbedder если Ollama доступен

    Raises:
        SystemExit: Если Ollama недоступен
    """
    embedder = OllamaEmbedder(**config.get('ollama', {}))

    if not embedder.check_connection():
        print("❌ Ollama не доступен!")
        print("\nИнструкция по запуску:")
        print("1. Установите Ollama: https://ollama.com/download")
        print("2. Запустите сервер: ollama serve")
        print(f"3. Загрузите модель: ollama pull {embedder.model}")
        print(f"\nПроверьте что Ollama запущен по адресу: {embedder.url}")
        raise SystemExit(1)

    logger.info("✓ Ollama connection verified")
    return embedder
