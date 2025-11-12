#!/usr/bin/env python3
"""
Модуль подсчета токенов для Yandex GPT API.
Предоставляет функции для подсчета токенов в тексте и проверки лимитов.
"""

import logging
import re
from typing import Optional

import httpx

from config import (
    APPROXIMATE_CHARS_PER_TOKEN_RU,
    APPROXIMATE_TOKENS_PER_WORD_RU,
    MODEL_TOKEN_LIMITS,
    TOKEN_LOG_FORMAT,
    YANDEX_GPT_LITE_MAX_TOKENS,
    get_model_token_limit,
)

# Настройка логирования
logger = logging.getLogger(__name__)


class TokenCounter:
    """Класс для подсчета токенов в текстах для Yandex GPT."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализация счетчика токенов.

        Args:
            api_key: API ключ Yandex Cloud (опционально, для использования API токенизации)
        """
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

    def count_tokens(self, text: str, model: str = "yandexgpt-lite") -> int:
        """
        Подсчитывает количество токенов в тексте для заданной модели.

        Использует примерный подсчет на основе количества символов,
        т.к. официальный API токенизации требует дополнительных запросов.

        Args:
            text: Входной текст
            model: Название модели Yandex GPT

        Returns:
            Количество токенов
        """
        if not text:
            return 0

        # Используем примерный подсчет на основе символов
        # Для русского языка: ~4 символа на токен
        char_count = len(text)
        estimated_tokens = int(char_count / APPROXIMATE_CHARS_PER_TOKEN_RU)

        # Альтернативный расчет на основе слов
        words = self._count_words(text)
        estimated_tokens_by_words = int(words * APPROXIMATE_TOKENS_PER_WORD_RU)

        # Берем среднее между двумя оценками
        final_estimate = (estimated_tokens + estimated_tokens_by_words) // 2

        logger.debug(
            f"Token estimation: {char_count} chars, {words} words -> "
            f"~{final_estimate} tokens (model: {model})"
        )

        return final_estimate

    async def count_tokens_precise(
        self, text: str, model: str = "yandexgpt-lite", timeout: int = 10
    ) -> Optional[int]:
        """
        Точный подсчет токенов через Yandex GPT Tokenizer API.

        ВНИМАНИЕ: Этот метод выполняет реальный API запрос к Yandex Cloud,
        что может занять время и расходовать квоту.

        Args:
            text: Входной текст
            model: Название модели
            timeout: Таймаут запроса в секундах

        Returns:
            Точное количество токенов или None в случае ошибки
        """
        if not self.api_key:
            logger.warning("API ключ не предоставлен, используем примерный подсчет")
            return self.count_tokens(text, model)

        # URL для токенизации (может требовать folder_id)
        # tokenize_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize"

        # Пока API токенизации не доступен или требует дополнительной настройки,
        # используем примерный подсчет
        logger.info("Точный подсчет токенов пока не реализован, используем примерный")
        return self.count_tokens(text, model)

    def _count_words(self, text: str) -> int:
        """
        Подсчитывает количество слов в тексте.

        Args:
            text: Входной текст

        Returns:
            Количество слов
        """
        # Удаляем лишние пробелы и разбиваем на слова
        words = re.findall(r'\b\w+\b', text)
        return len(words)

    def check_token_limit(self, tokens: int, model: str = "yandexgpt-lite") -> bool:
        """
        Проверяет, не превышает ли количество токенов лимит модели.

        Args:
            tokens: Количество токенов
            model: Название модели

        Returns:
            True, если в пределах лимита, False если превышает
        """
        limit = get_model_token_limit(model)
        is_within_limit = tokens <= limit

        if not is_within_limit:
            logger.warning(
                f"Token limit exceeded: {tokens} > {limit} for model {model}"
            )

        return is_within_limit

    def get_token_limit_percentage(
        self, tokens: int, model: str = "yandexgpt-lite"
    ) -> float:
        """
        Вычисляет процент использования от лимита модели.

        Args:
            tokens: Количество токенов
            model: Название модели

        Returns:
            Процент использования (0.0 - 1.0+)
        """
        limit = get_model_token_limit(model)
        if limit == 0:
            return 0.0

        percentage = tokens / limit
        return percentage

    def calculate_overflow(self, tokens: int, model: str = "yandexgpt-lite") -> int:
        """
        Вычисляет на сколько токенов превышен лимит.

        Args:
            tokens: Количество токенов
            model: Название модели

        Returns:
            Количество токенов превышения (0 если не превышен)
        """
        limit = get_model_token_limit(model)
        overflow = max(0, tokens - limit)
        return overflow

    def log_token_usage(
        self,
        request_tokens: int,
        response_tokens: int,
        model: str = "yandexgpt-lite",
    ) -> None:
        """
        Логирует использование токенов.

        Args:
            request_tokens: Токены запроса
            response_tokens: Токены ответа
            model: Название модели
        """
        total_tokens = request_tokens + response_tokens
        limit = get_model_token_limit(model)
        percentage = self.get_token_limit_percentage(total_tokens, model)

        log_message = TOKEN_LOG_FORMAT.format(
            request=request_tokens, response=response_tokens, total=total_tokens
        )

        logger.info(log_message)
        logger.info(
            f"[TOKENS] Model: {model} | Max context: {limit} tokens ({percentage:.1%} used)"
        )


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================


def count_tokens(text: str, model: str = "yandexgpt-lite") -> int:
    """
    Быстрая функция подсчета токенов без создания экземпляра класса.

    Args:
        text: Входной текст
        model: Название модели Yandex GPT

    Returns:
        Количество токенов
    """
    counter = TokenCounter()
    return counter.count_tokens(text, model)


def check_token_limit(tokens: int, model: str = "yandexgpt-lite") -> bool:
    """
    Быстрая проверка лимита токенов.

    Args:
        tokens: Количество токенов
        model: Название модели

    Returns:
        True, если в пределах лимита
    """
    counter = TokenCounter()
    return counter.check_token_limit(tokens, model)


def get_token_limit_percentage(tokens: int, model: str = "yandexgpt-lite") -> float:
    """
    Быстрая функция получения процента использования.

    Args:
        tokens: Количество токенов
        model: Название модели

    Returns:
        Процент использования (0.0 - 1.0+)
    """
    counter = TokenCounter()
    return counter.get_token_limit_percentage(tokens, model)


def log_token_usage(
    request_tokens: int, response_tokens: int, model: str = "yandexgpt-lite"
) -> None:
    """
    Быстрая функция логирования использования токенов.

    Args:
        request_tokens: Токены запроса
        response_tokens: Токены ответа
        model: Название модели
    """
    counter = TokenCounter()
    counter.log_token_usage(request_tokens, response_tokens, model)


# ==================== ЭКСПОРТ ====================

__all__ = [
    "TokenCounter",
    "count_tokens",
    "check_token_limit",
    "get_token_limit_percentage",
    "log_token_usage",
]
