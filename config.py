#!/usr/bin/env python3
"""
Конфигурация для системы подсчета токенов Telegram-бота с Yandex GPT.
Содержит лимиты, настройки отображения и другие параметры.
"""

import os
from typing import Final

# ==================== ЛИМИТЫ ТОКЕНОВ ДЛЯ МОДЕЛЕЙ YANDEX GPT ====================

# Максимальное количество токенов для моделей
# Источник: Yandex Cloud Foundation Models документация
YANDEX_GPT_LITE_MAX_TOKENS: Final[int] = 8192      # YandexGPT Lite
YANDEX_GPT_PRO_MAX_TOKENS: Final[int] = 32000      # YandexGPT Pro

# Используемая модель по умолчанию
DEFAULT_MODEL: Final[str] = "yandexgpt-lite"

# Маппинг моделей к их лимитам
MODEL_TOKEN_LIMITS: Final[dict[str, int]] = {
    "yandexgpt-lite": YANDEX_GPT_LITE_MAX_TOKENS,
    "yandexgpt": YANDEX_GPT_PRO_MAX_TOKENS,
    "yandexgpt-pro": YANDEX_GPT_PRO_MAX_TOKENS,
}


# ==================== НАСТРОЙКИ ЛОГИРОВАНИЯ ТОКЕНОВ ====================

# Включить логирование использования токенов
LOG_TOKEN_USAGE: Final[bool] = True

# Файл для логирования использования токенов
TOKEN_LOG_FILE: Final[str] = "token_usage.log"

# Формат логирования
TOKEN_LOG_FORMAT: Final[str] = "[TOKENS] Request: {request} tokens | Response: {response} tokens | Total: {total} tokens"


# ==================== НАСТРОЙКИ ПРЕДУПРЕЖДЕНИЙ ====================

# Порог предупреждения (80% от лимита)
TOKEN_WARNING_THRESHOLD: Final[float] = 0.8

# Порог критического предупреждения (90% от лимита)
TOKEN_DANGER_THRESHOLD: Final[float] = 0.9


# ==================== НАСТРОЙКИ ОТОБРАЖЕНИЯ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ====================

# Режим отображения токенов по умолчанию
# Варианты: "hidden", "compact", "detailed", "warnings_only"
DEFAULT_TOKEN_DISPLAY_MODE: Final[str] = "detailed"

# Показывать обучающее сообщение при первом использовании
SHOW_TOKEN_HELP_ON_FIRST_USE: Final[bool] = True

# Автоматически показывать токены после каждого ответа
AUTO_SHOW_TOKENS: Final[bool] = True


# ==================== НАСТРОЙКИ СТАТИСТИКИ ====================

# Включить сбор статистики использования токенов
ENABLE_TOKEN_STATISTICS: Final[bool] = True

# Час сброса дневной статистики (0-23)
RESET_DAILY_STATS_HOUR: Final[int] = 0


# ==================== ЭМОДЗИ ДЛЯ ИНДИКАТОРОВ ====================

# Визуальные индикаторы использования токенов
TOKEN_INDICATOR_OK: Final[str] = "✅"           # < 50% от лимита
TOKEN_INDICATOR_WARNING: Final[str] = "⚠️"      # 50-80% от лимита
TOKEN_INDICATOR_DANGER: Final[str] = "🔴"       # > 80% от лимита

# Другие эмодзи
TOKEN_EMOJI_STATS: Final[str] = "📊"
TOKEN_EMOJI_INFO: Final[str] = "ℹ️"
TOKEN_EMOJI_ERROR: Final[str] = "❌"
TOKEN_EMOJI_LIGHTBULB: Final[str] = "💡"
TOKEN_EMOJI_CHART: Final[str] = "📈"
TOKEN_EMOJI_SETTINGS: Final[str] = "⚙️"


# ==================== ПРИМЕРНЫЙ РАСЧЕТ ТОКЕНОВ ====================

# Примерное количество токенов на слово (если точный подсчет недоступен)
# Основано на исследовании Yandex GPT
APPROXIMATE_TOKENS_PER_WORD_RU: Final[float] = 1.33  # Для русского языка
APPROXIMATE_TOKENS_PER_WORD_EN: Final[float] = 0.75  # Для английского языка

# Примерное количество символов на токен
APPROXIMATE_CHARS_PER_TOKEN_RU: Final[float] = 4.0   # Для русского языка
APPROXIMATE_CHARS_PER_TOKEN_EN: Final[float] = 4.5   # Для английского языка


# ==================== API ENDPOINTS ====================

# URL для токенизации (если будет использоваться официальный API)
YANDEX_TOKENIZE_API_URL: Final[str] = "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize"
YANDEX_TOKENIZE_COMPLETION_API_URL: Final[str] = "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenizeCompletion"


# ==================== НАСТРОЙКИ ДИРЕКТОРИЙ ====================

# Директория для хранения данных пользователей
USER_DATA_DIR: Final[str] = "user_data"

# Файл для хранения настроек пользователей
USER_SETTINGS_FILE: Final[str] = os.path.join(USER_DATA_DIR, "user_settings.json")

# Файл для хранения статистики
USER_STATS_FILE: Final[str] = os.path.join(USER_DATA_DIR, "user_stats.json")


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_model_token_limit(model: str) -> int:
    """
    Получить лимит токенов для указанной модели.

    Args:
        model: Название модели

    Returns:
        Лимит токенов для модели (по умолчанию для yandexgpt-lite)
    """
    return MODEL_TOKEN_LIMITS.get(model, YANDEX_GPT_LITE_MAX_TOKENS)


def get_token_indicator(percentage: float) -> str:
    """
    Получить визуальный индикатор на основе процента использования.

    Args:
        percentage: Процент использования (0.0 - 1.0)

    Returns:
        Эмодзи-индикатор
    """
    if percentage >= TOKEN_DANGER_THRESHOLD:
        return TOKEN_INDICATOR_DANGER
    elif percentage >= TOKEN_WARNING_THRESHOLD:
        return TOKEN_INDICATOR_WARNING
    else:
        return TOKEN_INDICATOR_OK


def should_show_warning(percentage: float) -> bool:
    """
    Определить, нужно ли показать предупреждение.

    Args:
        percentage: Процент использования (0.0 - 1.0)

    Returns:
        True если нужно показать предупреждение
    """
    return percentage >= TOKEN_WARNING_THRESHOLD


# ==================== ЭКСПОРТ КОНФИГУРАЦИИ ====================

__all__ = [
    # Лимиты
    "YANDEX_GPT_LITE_MAX_TOKENS",
    "YANDEX_GPT_PRO_MAX_TOKENS",
    "DEFAULT_MODEL",
    "MODEL_TOKEN_LIMITS",

    # Логирование
    "LOG_TOKEN_USAGE",
    "TOKEN_LOG_FILE",
    "TOKEN_LOG_FORMAT",

    # Предупреждения
    "TOKEN_WARNING_THRESHOLD",
    "TOKEN_DANGER_THRESHOLD",

    # Отображение
    "DEFAULT_TOKEN_DISPLAY_MODE",
    "SHOW_TOKEN_HELP_ON_FIRST_USE",
    "AUTO_SHOW_TOKENS",

    # Статистика
    "ENABLE_TOKEN_STATISTICS",
    "RESET_DAILY_STATS_HOUR",

    # Эмодзи
    "TOKEN_INDICATOR_OK",
    "TOKEN_INDICATOR_WARNING",
    "TOKEN_INDICATOR_DANGER",
    "TOKEN_EMOJI_STATS",
    "TOKEN_EMOJI_INFO",
    "TOKEN_EMOJI_ERROR",
    "TOKEN_EMOJI_LIGHTBULB",
    "TOKEN_EMOJI_CHART",
    "TOKEN_EMOJI_SETTINGS",

    # Примерный расчет
    "APPROXIMATE_TOKENS_PER_WORD_RU",
    "APPROXIMATE_TOKENS_PER_WORD_EN",
    "APPROXIMATE_CHARS_PER_TOKEN_RU",
    "APPROXIMATE_CHARS_PER_TOKEN_EN",

    # API
    "YANDEX_TOKENIZE_API_URL",
    "YANDEX_TOKENIZE_COMPLETION_API_URL",

    # Директории
    "USER_DATA_DIR",
    "USER_SETTINGS_FILE",
    "USER_STATS_FILE",

    # Функции
    "get_model_token_limit",
    "get_token_indicator",
    "should_show_warning",
]
