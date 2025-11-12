#!/usr/bin/env python3
"""
Модуль для управления настройками пользователей и статистикой токенов.
Хранит настройки отображения и собирает статистику использования.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from config import (
    DEFAULT_TOKEN_DISPLAY_MODE,
    RESET_DAILY_STATS_HOUR,
    SHOW_TOKEN_HELP_ON_FIRST_USE,
    USER_DATA_DIR,
    USER_SETTINGS_FILE,
    USER_STATS_FILE,
)

# Настройка логирования
logger = logging.getLogger(__name__)


class UserTokenSettings:
    """Класс для хранения настроек пользователя по отображению токенов."""

    def __init__(self, user_id: int):
        """
        Инициализация настроек пользователя.

        Args:
            user_id: ID пользователя Telegram
        """
        self.user_id = user_id
        self.display_mode = DEFAULT_TOKEN_DISPLAY_MODE  # hidden, compact, detailed, warnings_only
        self.show_help = SHOW_TOKEN_HELP_ON_FIRST_USE
        self.auto_show = True
        self.first_use = True  # Флаг первого использования

    def to_dict(self) -> dict:
        """Преобразует настройки в словарь для сохранения."""
        return {
            "user_id": self.user_id,
            "display_mode": self.display_mode,
            "show_help": self.show_help,
            "auto_show": self.auto_show,
            "first_use": self.first_use,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserTokenSettings":
        """Создает экземпляр из словаря."""
        settings = cls(data["user_id"])
        settings.display_mode = data.get("display_mode", DEFAULT_TOKEN_DISPLAY_MODE)
        settings.show_help = data.get("show_help", SHOW_TOKEN_HELP_ON_FIRST_USE)
        settings.auto_show = data.get("auto_show", True)
        settings.first_use = data.get("first_use", True)
        return settings


class TokenStatistics:
    """Класс для хранения статистики использования токенов."""

    def __init__(self, user_id: int):
        """
        Инициализация статистики пользователя.

        Args:
            user_id: ID пользователя Telegram
        """
        self.user_id = user_id
        self.session_requests = 0
        self.session_tokens = 0
        self.session_request_tokens = 0
        self.session_response_tokens = 0

        self.daily_requests = 0
        self.daily_tokens = 0
        self.daily_request_tokens = 0
        self.daily_response_tokens = 0

        self.last_reset = datetime.now()
        self.last_request_tokens = 0
        self.last_response_tokens = 0

    def add_request(self, request_tokens: int, response_tokens: int) -> None:
        """
        Добавляет информацию о новом запросе в статистику.

        Args:
            request_tokens: Количество токенов в запросе
            response_tokens: Количество токенов в ответе
        """
        total = request_tokens + response_tokens

        # Обновляем статистику за сессию
        self.session_requests += 1
        self.session_tokens += total
        self.session_request_tokens += request_tokens
        self.session_response_tokens += response_tokens

        # Обновляем статистику за день
        self._check_daily_reset()
        self.daily_requests += 1
        self.daily_tokens += total
        self.daily_request_tokens += request_tokens
        self.daily_response_tokens += response_tokens

        # Сохраняем последний запрос
        self.last_request_tokens = request_tokens
        self.last_response_tokens = response_tokens

        logger.debug(
            f"User {self.user_id} stats updated: "
            f"session={self.session_requests} reqs, daily={self.daily_requests} reqs"
        )

    def _check_daily_reset(self) -> None:
        """Проверяет, нужно ли сбросить дневную статистику."""
        now = datetime.now()
        # Сброс в указанный час (по умолчанию в полночь)
        reset_time = now.replace(hour=RESET_DAILY_STATS_HOUR, minute=0, second=0, microsecond=0)

        # Если прошло больше 24 часов или наступило время сброса
        if now >= reset_time and self.last_reset < reset_time:
            logger.info(f"Resetting daily stats for user {self.user_id}")
            self.daily_requests = 0
            self.daily_tokens = 0
            self.daily_request_tokens = 0
            self.daily_response_tokens = 0
            self.last_reset = now

    def get_session_stats(self) -> dict:
        """Возвращает статистику за сессию."""
        avg_tokens = (
            self.session_tokens // self.session_requests if self.session_requests > 0 else 0
        )
        return {
            "requests": self.session_requests,
            "total_tokens": self.session_tokens,
            "request_tokens": self.session_request_tokens,
            "response_tokens": self.session_response_tokens,
            "avg_tokens": avg_tokens,
        }

    def get_daily_stats(self) -> dict:
        """Возвращает статистику за день."""
        avg_tokens = (
            self.daily_tokens // self.daily_requests if self.daily_requests > 0 else 0
        )
        return {
            "requests": self.daily_requests,
            "total_tokens": self.daily_tokens,
            "request_tokens": self.daily_request_tokens,
            "response_tokens": self.daily_response_tokens,
            "avg_tokens": avg_tokens,
        }

    def get_last_request_stats(self) -> dict:
        """Возвращает статистику последнего запроса."""
        return {
            "request_tokens": self.last_request_tokens,
            "response_tokens": self.last_response_tokens,
            "total_tokens": self.last_request_tokens + self.last_response_tokens,
        }

    def to_dict(self) -> dict:
        """Преобразует статистику в словарь для сохранения."""
        return {
            "user_id": self.user_id,
            "session_requests": self.session_requests,
            "session_tokens": self.session_tokens,
            "session_request_tokens": self.session_request_tokens,
            "session_response_tokens": self.session_response_tokens,
            "daily_requests": self.daily_requests,
            "daily_tokens": self.daily_tokens,
            "daily_request_tokens": self.daily_request_tokens,
            "daily_response_tokens": self.daily_response_tokens,
            "last_reset": self.last_reset.isoformat(),
            "last_request_tokens": self.last_request_tokens,
            "last_response_tokens": self.last_response_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenStatistics":
        """Создает экземпляр из словаря."""
        stats = cls(data["user_id"])
        stats.session_requests = data.get("session_requests", 0)
        stats.session_tokens = data.get("session_tokens", 0)
        stats.session_request_tokens = data.get("session_request_tokens", 0)
        stats.session_response_tokens = data.get("session_response_tokens", 0)
        stats.daily_requests = data.get("daily_requests", 0)
        stats.daily_tokens = data.get("daily_tokens", 0)
        stats.daily_request_tokens = data.get("daily_request_tokens", 0)
        stats.daily_response_tokens = data.get("daily_response_tokens", 0)

        if "last_reset" in data:
            stats.last_reset = datetime.fromisoformat(data["last_reset"])

        stats.last_request_tokens = data.get("last_request_tokens", 0)
        stats.last_response_tokens = data.get("last_response_tokens", 0)

        return stats


class UserDataManager:
    """Менеджер для сохранения и загрузки данных пользователей."""

    def __init__(self):
        """Инициализация менеджера данных."""
        # Создаем директорию если не существует
        Path(USER_DATA_DIR).mkdir(parents=True, exist_ok=True)

        self.settings_cache: Dict[int, UserTokenSettings] = {}
        self.stats_cache: Dict[int, TokenStatistics] = {}

        # Загружаем существующие данные
        self._load_all_data()

    def _load_all_data(self) -> None:
        """Загружает все данные из файлов."""
        self._load_settings()
        self._load_stats()

    def _load_settings(self) -> None:
        """Загружает настройки всех пользователей."""
        if os.path.exists(USER_SETTINGS_FILE):
            try:
                with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id_str, settings_data in data.items():
                        user_id = int(user_id_str)
                        self.settings_cache[user_id] = UserTokenSettings.from_dict(settings_data)
                logger.info(f"Loaded settings for {len(self.settings_cache)} users")
            except Exception as e:
                logger.error(f"Error loading user settings: {e}")

    def _load_stats(self) -> None:
        """Загружает статистику всех пользователей."""
        if os.path.exists(USER_STATS_FILE):
            try:
                with open(USER_STATS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id_str, stats_data in data.items():
                        user_id = int(user_id_str)
                        self.stats_cache[user_id] = TokenStatistics.from_dict(stats_data)
                logger.info(f"Loaded stats for {len(self.stats_cache)} users")
            except Exception as e:
                logger.error(f"Error loading user stats: {e}")

    def get_settings(self, user_id: int) -> UserTokenSettings:
        """
        Получает настройки пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Настройки пользователя
        """
        if user_id not in self.settings_cache:
            self.settings_cache[user_id] = UserTokenSettings(user_id)
        return self.settings_cache[user_id]

    def get_stats(self, user_id: int) -> TokenStatistics:
        """
        Получает статистику пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Статистика пользователя
        """
        if user_id not in self.stats_cache:
            self.stats_cache[user_id] = TokenStatistics(user_id)
        return self.stats_cache[user_id]

    def save_settings(self, user_id: int) -> None:
        """Сохраняет настройки конкретного пользователя."""
        self._save_all_settings()

    def save_stats(self, user_id: int) -> None:
        """Сохраняет статистику конкретного пользователя."""
        self._save_all_stats()

    def _save_all_settings(self) -> None:
        """Сохраняет все настройки в файл."""
        try:
            data = {
                str(user_id): settings.to_dict()
                for user_id, settings in self.settings_cache.items()
            }
            with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved settings for {len(data)} users")
        except Exception as e:
            logger.error(f"Error saving user settings: {e}")

    def _save_all_stats(self) -> None:
        """Сохраняет всю статистику в файл."""
        try:
            data = {
                str(user_id): stats.to_dict()
                for user_id, stats in self.stats_cache.items()
            }
            with open(USER_STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved stats for {len(data)} users")
        except Exception as e:
            logger.error(f"Error saving user stats: {e}")


# ==================== ЭКСПОРТ ====================

__all__ = [
    "UserTokenSettings",
    "TokenStatistics",
    "UserDataManager",
]
