"""
Модуль для сбора и расчета метрик сравнения RAG/без RAG.
Собирает метрики: количество токенов, время генерации, релевантность чанков.
"""

import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def count_tokens_approximate(text: str) -> int:
    """
    Приблизительный подсчет токенов в тексте.
    Использует эвристику: ~1 токен = 0.75 слова для русского и английского.

    Args:
        text: Текст для подсчета

    Returns:
        Приблизительное количество токенов
    """
    if not text:
        return 0

    # Разбиваем по словам
    words = text.split()
    # ~1.33 токена на слово (инверсия 0.75 слова на токен)
    return int(len(words) * 1.33)


def count_tokens_tiktoken(text: str) -> Optional[int]:
    """
    Точный подсчет токенов используя tiktoken (если доступен).

    Args:
        text: Текст для подсчета

    Returns:
        Количество токенов или None если tiktoken недоступен
    """
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        return len(tokens)
    except ImportError:
        logger.debug("tiktoken not available, using approximate counting")
        return None
    except Exception as e:
        logger.warning(f"Error counting tokens with tiktoken: {e}")
        return None


def count_tokens(text: str) -> int:
    """
    Подсчет токенов с попыткой использовать tiktoken, fallback на приблизительный.

    Args:
        text: Текст для подсчета

    Returns:
        Количество токенов
    """
    # Пытаемся использовать tiktoken
    tokens = count_tokens_tiktoken(text)
    if tokens is not None:
        return tokens

    # Fallback на приблизительный подсчет
    return count_tokens_approximate(text)


@dataclass
class ResponseMetrics:
    """Метрики одного ответа."""

    response_text: str
    token_count: int
    generation_time: float
    chunks_used: int = 0
    avg_relevance_score: float = 0.0
    rag_sources: List[Dict] = None

    def __post_init__(self):
        if self.rag_sources is None:
            self.rag_sources = []


@dataclass
class ComparisonMetrics:
    """Метрики сравнения двух ответов."""

    without_rag: ResponseMetrics
    with_rag: ResponseMetrics

    def get_token_difference(self) -> Dict:
        """
        Рассчитать разницу в токенах.

        Returns:
            Словарь с абсолютной и процентной разницей
        """
        diff = self.with_rag.token_count - self.without_rag.token_count
        percent = 0.0

        if self.without_rag.token_count > 0:
            percent = (diff / self.without_rag.token_count) * 100

        return {
            'absolute': diff,
            'percent': percent,
            'without_rag': self.without_rag.token_count,
            'with_rag': self.with_rag.token_count
        }

    def get_time_difference(self) -> Dict:
        """
        Рассчитать разницу во времени генерации.

        Returns:
            Словарь с абсолютной и процентной разницей
        """
        diff = self.with_rag.generation_time - self.without_rag.generation_time
        percent = 0.0

        if self.without_rag.generation_time > 0:
            percent = (diff / self.without_rag.generation_time) * 100

        return {
            'absolute': diff,
            'percent': percent,
            'without_rag': self.without_rag.generation_time,
            'with_rag': self.with_rag.generation_time
        }

    def get_comparison_summary(self) -> Dict:
        """
        Получить полное резюме сравнения.

        Returns:
            Словарь со всеми метриками сравнения
        """
        return {
            'token_difference': self.get_token_difference(),
            'time_difference': self.get_time_difference(),
            'chunks_used': self.with_rag.chunks_used,
            'avg_relevance': self.with_rag.avg_relevance_score
        }


class MetricsCollector:
    """Сборщик метрик для ответов LLM."""

    def __init__(self):
        """Инициализация сборщика метрик."""
        logger.info("MetricsCollector initialized")

    def measure_response(
        self,
        response_text: str,
        generation_time: float,
        rag_sources: Optional[List[Dict]] = None
    ) -> ResponseMetrics:
        """
        Измерить метрики ответа.

        Args:
            response_text: Текст ответа
            generation_time: Время генерации в секундах
            rag_sources: Источники RAG (если использовались)

        Returns:
            Метрики ответа
        """
        # Подсчитываем токены
        token_count = count_tokens(response_text)

        # Рассчитываем количество чанков и среднюю релевантность
        chunks_used = 0
        avg_relevance = 0.0

        if rag_sources:
            chunks_used = len(rag_sources)
            if chunks_used > 0:
                relevance_scores = [
                    source.get('similarity_score', 0.0)
                    for source in rag_sources
                ]
                avg_relevance = sum(relevance_scores) / len(relevance_scores)

        metrics = ResponseMetrics(
            response_text=response_text,
            token_count=token_count,
            generation_time=generation_time,
            chunks_used=chunks_used,
            avg_relevance_score=avg_relevance,
            rag_sources=rag_sources or []
        )

        logger.debug(
            f"Measured response: tokens={token_count}, "
            f"time={generation_time:.2f}s, chunks={chunks_used}"
        )

        return metrics

    def compare_responses(
        self,
        without_rag_metrics: ResponseMetrics,
        with_rag_metrics: ResponseMetrics
    ) -> ComparisonMetrics:
        """
        Сравнить метрики двух ответов.

        Args:
            without_rag_metrics: Метрики ответа без RAG
            with_rag_metrics: Метрики ответа с RAG

        Returns:
            Метрики сравнения
        """
        comparison = ComparisonMetrics(
            without_rag=without_rag_metrics,
            with_rag=with_rag_metrics
        )

        logger.info(
            f"Comparison: "
            f"tokens diff={comparison.get_token_difference()['absolute']}, "
            f"time diff={comparison.get_time_difference()['absolute']:.2f}s"
        )

        return comparison


class PerformanceTimer:
    """Таймер для измерения времени выполнения."""

    def __init__(self):
        """Инициализация таймера."""
        self.start_time = None
        self.end_time = None

    def start(self) -> None:
        """Запустить таймер."""
        self.start_time = time.time()
        self.end_time = None

    def stop(self) -> float:
        """
        Остановить таймер и вернуть время выполнения.

        Returns:
            Время выполнения в секундах
        """
        self.end_time = time.time()
        if self.start_time is None:
            logger.warning("Timer was not started")
            return 0.0

        elapsed = self.end_time - self.start_time
        return elapsed

    def get_elapsed(self) -> float:
        """
        Получить текущее время выполнения (без остановки таймера).

        Returns:
            Время выполнения в секундах
        """
        if self.start_time is None:
            return 0.0

        current_time = time.time()
        return current_time - self.start_time

    def __enter__(self):
        """Контекстный менеджер: начало."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: конец."""
        self.stop()
        return False
