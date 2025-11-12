#!/usr/bin/env python3
"""
Модуль обработки ошибок, связанных с токенами.
Содержит функции для обработки превышения лимитов и предупреждений.
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from config import get_model_token_limit, should_show_warning
from token_ui import format_token_overflow_message, format_token_warning

# Настройка логирования
logger = logging.getLogger(__name__)


async def handle_token_overflow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tokens: int,
    model: str = "yandexgpt-lite",
) -> None:
    """
    Обрабатывает ситуацию превышения лимита токенов.

    Args:
        update: Объект обновления Telegram
        context: Контекст выполнения
        tokens: Количество токенов в запросе
        model: Название модели
    """
    limit = get_model_token_limit(model)
    message = format_token_overflow_message(tokens, limit)

    await update.message.reply_text(message)
    logger.warning(
        f"Token overflow for user {update.effective_user.id}: {tokens} > {limit}"
    )


async def send_token_warning(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tokens: int,
    model: str = "yandexgpt-lite",
) -> None:
    """
    Отправляет предупреждение при приближении к лимиту.

    Args:
        update: Объект обновления Telegram
        context: Контекст выполнения
        tokens: Текущее количество токенов
        model: Название модели
    """
    limit = get_model_token_limit(model)
    percentage = tokens / limit if limit > 0 else 0

    if should_show_warning(percentage):
        warning_message = format_token_warning(tokens, limit)
        if warning_message:
            await update.message.reply_text(warning_message)
            logger.info(
                f"Warning sent to user {update.effective_user.id}: {tokens}/{limit} tokens ({percentage:.0%})"
            )


def check_token_limit_before_request(
    tokens: int, model: str = "yandexgpt-lite"
) -> tuple[bool, Optional[str]]:
    """
    Проверяет лимит токенов ДО отправки запроса в API.

    Args:
        tokens: Количество токенов
        model: Название модели

    Returns:
        Кортеж (is_within_limit, error_message)
    """
    limit = get_model_token_limit(model)

    if tokens > limit:
        overflow = tokens - limit
        percentage_over = (overflow / limit) * 100
        error_msg = (
            f"Превышен лимит токенов: {tokens:,} > {limit:,}\n"
            f"Превышение: {overflow:,} токенов ({percentage_over:.0f}%)"
        )
        logger.warning(f"Token limit exceeded: {error_msg}")
        return False, error_msg

    return True, None


# ==================== ЭКСПОРТ ====================

__all__ = [
    "handle_token_overflow",
    "send_token_warning",
    "check_token_limit_before_request",
]
