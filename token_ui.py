#!/usr/bin/env python3
"""
Модуль интерактивного интерфейса для отображения информации о токенах пользователям.
Форматирует сообщения, создает визуальные индикаторы и подсказки.
"""

import logging
from typing import Dict

from config import (
    MODEL_TOKEN_LIMITS,
    TOKEN_EMOJI_CHART,
    TOKEN_EMOJI_ERROR,
    TOKEN_EMOJI_INFO,
    TOKEN_EMOJI_LIGHTBULB,
    TOKEN_EMOJI_SETTINGS,
    TOKEN_EMOJI_STATS,
    get_model_token_limit,
    get_token_indicator,
)

# Настройка логирования
logger = logging.getLogger(__name__)


def format_token_stats(
    request_tokens: int,
    response_tokens: int,
    model: str = "yandexgpt-lite",
    mode: str = "detailed",
) -> str:
    """
    Форматирует статистику токенов для отображения пользователю.

    Args:
        request_tokens: Токены запроса
        response_tokens: Токены ответа
        model: Название модели
        mode: Режим отображения ("hidden", "compact", "detailed", "warnings_only")

    Returns:
        Отформатированная строка для отправки пользователю
    """
    if mode == "hidden":
        return ""

    total_tokens = request_tokens + response_tokens
    limit = get_model_token_limit(model)
    percentage = total_tokens / limit if limit > 0 else 0
    indicator = get_token_indicator(percentage)

    if mode == "compact":
        return f"\n💬 Токены: запрос {request_tokens} | ответ {response_tokens} | всего {total_tokens} {indicator}"

    elif mode == "detailed":
        message = (
            f"\n\n{TOKEN_EMOJI_STATS} Статистика:\n"
            f"├─ Ваш запрос: {request_tokens} токенов\n"
            f"├─ Мой ответ: {response_tokens} токенов\n"
            f"└─ Всего использовано: {total_tokens} токенов\n\n"
            f"{indicator} Токены: {total_tokens}/{limit} ({percentage:.0%})"
        )
        return message

    elif mode == "warnings_only":
        # Показываем только если >= 80% лимита
        if percentage >= 0.8:
            return (
                f"\n\n{indicator} Токены: {total_tokens}/{limit} ({percentage:.0%})\n"
                f"{'⚠️ Приближаетесь к лимиту модели' if percentage < 0.9 else '🔴 ВНИМАНИЕ! Очень близко к лимиту!'}"
            )
        return ""

    return ""


def get_token_indicator_with_message(tokens: int, limit: int) -> tuple[str, str]:
    """
    Возвращает визуальный индикатор и сообщение о статусе.

    Args:
        tokens: Текущее количество токенов
        limit: Лимит модели

    Returns:
        Кортеж (индикатор, сообщение)
    """
    percentage = tokens / limit if limit > 0 else 0
    indicator = get_token_indicator(percentage)

    if percentage >= 0.9:
        return indicator, "ВНИМАНИЕ! Очень близко к лимиту!"
    elif percentage >= 0.8:
        return indicator, "Приближаетесь к лимиту модели."
    elif percentage >= 0.5:
        return indicator, "Половина лимита использована."
    else:
        return indicator, "В пределах нормы."


def format_token_overflow_message(tokens: int, limit: int) -> str:
    """
    Формирует сообщение о превышении лимита токенов.

    Args:
        tokens: Количество токенов в запросе
        limit: Максимальный лимит

    Returns:
        Отформатированное сообщение с рекомендациями
    """
    overflow = tokens - limit
    percentage_over = (overflow / limit) * 100

    message = (
        f"🚫 Запрос слишком большой!\n\n"
        f"{TOKEN_EMOJI_STATS} Ваш текст: ~{tokens:,} токенов\n"
        f"📏 Максимум модели: {limit:,} токенов\n"
        f"{TOKEN_EMOJI_ERROR} Превышение: {overflow:,} токенов (~{percentage_over:.0f}%)\n\n"
        f"{TOKEN_EMOJI_LIGHTBULB} Что можно сделать:\n"
        f"1️⃣ Сократить текст примерно на {percentage_over:.0f}% (~{overflow:,} токенов)\n"
        f"2️⃣ Разбить на {(tokens // limit) + 1} части и отправить по очереди\n"
        f"3️⃣ Использовать более краткие формулировки\n\n"
        f"Попробуйте ещё раз с более коротким текстом!"
    )

    return message


def format_token_help_message() -> str:
    """
    Формирует обучающее сообщение о токенах для пользователя.

    Returns:
        Обучающее сообщение с примерами
    """
    message = (
        f"👋 Привет! Я теперь показываю статистику использования токенов.\n\n"
        f"🤔 Что такое токены?\n"
        f"Это единицы измерения текста для AI. Примерно:\n"
        f"• 1 токен ≈ 0.75 слова (на русском)\n"
        f"• 100 токенов ≈ 75 слов\n"
        f"• 1000 токенов ≈ 750 слов\n\n"
        f"{TOKEN_EMOJI_STATS} Зачем это нужно?\n"
        f"Понимание токенов помогает:\n"
        f"✓ Оптимизировать запросы\n"
        f"✓ Избежать превышения лимитов\n"
        f"✓ Понять, как работает AI\n\n"
        f"{TOKEN_EMOJI_LIGHTBULB} Команды:\n"
        f"/tokens - статистика последнего запроса\n"
        f"/tokens_stats - общая статистика\n"
        f"/token_mode off - отключить показ\n"
        f"/token_settings - настройки\n\n"
        f"Чтобы скрыть это сообщение в будущем: /token_help off"
    )

    return message


def format_tokens_command_response(
    request_tokens: int, response_tokens: int, model: str = "yandexgpt-lite"
) -> str:
    """
    Форматирует ответ на команду /tokens.

    Args:
        request_tokens: Токены запроса
        response_tokens: Токены ответа
        model: Название модели

    Returns:
        Отформатированное сообщение
    """
    total_tokens = request_tokens + response_tokens
    limit = get_model_token_limit(model)
    percentage = total_tokens / limit if limit > 0 else 0
    indicator = get_token_indicator(percentage)

    message = (
        f"{TOKEN_EMOJI_STATS} Статистика последнего запроса:\n\n"
        f"Ваш запрос: {request_tokens} токенов\n"
        f"Ответ бота: {response_tokens} токенов\n"
        f"Всего: {total_tokens} токенов\n\n"
        f"Лимит модели: {limit:,} токенов\n"
        f"Использовано: {percentage:.1%} от лимита {indicator}\n\n"
        f"{TOKEN_EMOJI_LIGHTBULB} Команды:\n"
        f"/tokens_stats - общая статистика\n"
        f"/token_mode off - отключить показ токенов"
    )

    return message


def format_tokens_stats_response(session_stats: Dict, daily_stats: Dict) -> str:
    """
    Форматирует ответ на команду /tokens_stats.

    Args:
        session_stats: Статистика за сессию
        daily_stats: Статистика за день

    Returns:
        Отформатированное сообщение
    """
    message = (
        f"{TOKEN_EMOJI_CHART} Ваша статистика использования:\n\n"
        f"За эту сессию:\n"
        f"├─ Запросов: {session_stats['requests']}\n"
        f"├─ Всего токенов: {session_stats['total_tokens']:,}\n"
        f"└─ Средний запрос: {session_stats['avg_tokens']} токенов\n\n"
        f"За сегодня:\n"
        f"├─ Запросов: {daily_stats['requests']}\n"
        f"├─ Всего токенов: {daily_stats['total_tokens']:,}\n"
        f"└─ Средний запрос: {daily_stats['avg_tokens']} токенов\n\n"
    )

    # Добавляем комментарий в зависимости от использования
    if daily_stats['requests'] == 0:
        message += "Начните отправлять запросы, чтобы увидеть статистику!"
    elif daily_stats['requests'] < 10:
        message += "✅ Отличное начало! Продолжайте в том же духе."
    else:
        message += "✅ Отличная работа! Все запросы в пределах лимита."

    return message


def format_token_mode_response(enabled: bool) -> str:
    """
    Форматирует ответ на команду /token_mode.

    Args:
        enabled: True если токены включены, False если выключены

    Returns:
        Отформатированное сообщение
    """
    if enabled:
        message = (
            f"✅ Автоматический показ токенов включён\n"
            f"Теперь после каждого ответа вы будете видеть статистику использования.\n\n"
            f"Отключить: /token_mode off"
        )
    else:
        message = (
            f"{TOKEN_EMOJI_INFO} Автоматический показ токенов отключён\n"
            f"Вы по-прежнему можете просматривать статистику командами:\n"
            f"/tokens - последний запрос\n"
            f"/tokens_stats - общая статистика\n\n"
            f"Включить обратно: /token_mode on"
        )

    return message


def format_token_settings_menu() -> str:
    """
    Форматирует меню настроек токенов.

    Returns:
        Меню настроек
    """
    message = (
        f"{TOKEN_EMOJI_SETTINGS} Настройки отображения токенов:\n\n"
        f"Выберите режим:\n"
        f"1️⃣ Скрытый - не показывать токены\n"
        f"2️⃣ Компактный - краткая статистика\n"
        f"3️⃣ Подробный - полная информация ✓\n"
        f"4️⃣ Только предупреждения - показывать при >80% лимита\n\n"
        f"Отправьте номер режима (1-4) или используйте:\n"
        f"/token_mode on - включить показ\n"
        f"/token_mode off - отключить показ"
    )

    return message


def format_token_warning(tokens: int, limit: int) -> str:
    """
    Форматирует предупреждение при приближении к лимиту.

    Args:
        tokens: Текущее количество токенов
        limit: Лимит модели

    Returns:
        Сообщение-предупреждение
    """
    percentage = tokens / limit if limit > 0 else 0
    indicator, status_msg = get_token_indicator_with_message(tokens, limit)

    if percentage >= 0.9:
        message = (
            f"{indicator} Токены: {tokens:,}/{limit:,} ({percentage:.0%})\n"
            f"🔴 {status_msg}\n\n"
            f"⚠️ Следующий запрос такого размера может не обработаться.\n"
            f"Рекомендую:\n"
            f"• Использовать более короткие запросы\n"
            f"• Разбивать большие тексты на части\n"
            f"• Проверить статистику: /tokens_stats"
        )
    elif percentage >= 0.8:
        message = (
            f"{indicator} Токены: {tokens:,}/{limit:,} ({percentage:.0%})\n"
            f"⚠️ {status_msg}\n"
            f"Рекомендуется сократить следующие запросы."
        )
    else:
        message = ""

    return message


# ==================== ЭКСПОРТ ====================

__all__ = [
    "format_token_stats",
    "get_token_indicator_with_message",
    "format_token_overflow_message",
    "format_token_help_message",
    "format_tokens_command_response",
    "format_tokens_stats_response",
    "format_token_mode_response",
    "format_token_settings_menu",
    "format_token_warning",
]
