#!/usr/bin/env python3
"""
Модуль обработчиков команд пользователя для работы с токенами.
Содержит функции для обработки /tokens, /tokens_stats, /token_mode и других команд.
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from token_ui import (
    format_token_help_message,
    format_token_mode_response,
    format_token_settings_menu,
    format_tokens_command_response,
    format_tokens_stats_response,
)
from user_settings import UserDataManager

# Настройка логирования
logger = logging.getLogger(__name__)


class TokenCommandHandler:
    """Класс для обработки команд, связанных с токенами."""

    def __init__(self, user_manager: UserDataManager):
        """
        Инициализация обработчика команд.

        Args:
            user_manager: Менеджер данных пользователей
        """
        self.user_manager = user_manager

    async def handle_tokens_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обрабатывает команду /tokens - показывает статистику последнего запроса.

        Args:
            update: Объект обновления Telegram
            context: Контекст выполнения
        """
        user_id = update.effective_user.id
        stats = self.user_manager.get_stats(user_id)
        last_request = stats.get_last_request_stats()

        if last_request['total_tokens'] == 0:
            message = (
                "ℹ️ Пока нет статистики.\n\n"
                "Отправьте мне сообщение, и я покажу статистику использования токенов!"
            )
        else:
            message = format_tokens_command_response(
                last_request['request_tokens'],
                last_request['response_tokens'],
            )

        await update.message.reply_text(message)
        logger.info(f"User {user_id} requested /tokens command")

    async def handle_tokens_stats_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обрабатывает команду /tokens_stats - показывает общую статистику.

        Args:
            update: Объект обновления Telegram
            context: Контекст выполнения
        """
        user_id = update.effective_user.id
        stats = self.user_manager.get_stats(user_id)

        session_stats = stats.get_session_stats()
        daily_stats = stats.get_daily_stats()

        message = format_tokens_stats_response(session_stats, daily_stats)

        await update.message.reply_text(message)
        logger.info(f"User {user_id} requested /tokens_stats command")

    async def handle_token_mode_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обрабатывает команду /token_mode on/off.

        Args:
            update: Объект обновления Telegram
            context: Контекст выполнения
        """
        user_id = update.effective_user.id
        settings = self.user_manager.get_settings(user_id)

        # Проверяем аргументы команды
        if context.args and len(context.args) > 0:
            mode_arg = context.args[0].lower()
            if mode_arg == "on":
                settings.auto_show = True
                settings.display_mode = "detailed"
            elif mode_arg == "off":
                settings.auto_show = False
                settings.display_mode = "hidden"
            else:
                await update.message.reply_text(
                    "❌ Неверный аргумент. Используйте:\n"
                    "/token_mode on - включить\n"
                    "/token_mode off - отключить"
                )
                return
        else:
            # Переключаем режим
            settings.auto_show = not settings.auto_show
            if settings.auto_show:
                settings.display_mode = "detailed"
            else:
                settings.display_mode = "hidden"

        # Сохраняем настройки
        self.user_manager.save_settings(user_id)

        message = format_token_mode_response(settings.auto_show)
        await update.message.reply_text(message)
        logger.info(
            f"User {user_id} changed token_mode to {'on' if settings.auto_show else 'off'}"
        )

    async def handle_token_settings_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обрабатывает команду /token_settings - открывает меню настроек.

        Args:
            update: Объект обновления Telegram
            context: Контекст выполнения
        """
        user_id = update.effective_user.id

        message = format_token_settings_menu()
        await update.message.reply_text(message)
        logger.info(f"User {user_id} opened token settings menu")

    async def handle_token_help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обрабатывает команду /token_help - показывает справку о токенах.

        Args:
            update: Объект обновления Telegram
            context: Контекст выполнения
        """
        user_id = update.effective_user.id
        settings = self.user_manager.get_settings(user_id)

        # Проверяем аргументы
        if context.args and len(context.args) > 0:
            mode_arg = context.args[0].lower()
            if mode_arg == "off":
                settings.show_help = False
                self.user_manager.save_settings(user_id)
                await update.message.reply_text(
                    "✅ Обучающее сообщение отключено.\n"
                    "Вы всегда можете вызвать справку командой /token_help"
                )
                logger.info(f"User {user_id} disabled token help messages")
                return

        message = format_token_help_message()
        await update.message.reply_text(message)
        logger.info(f"User {user_id} requested /token_help command")

    async def handle_settings_choice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str
    ) -> None:
        """
        Обрабатывает выбор настройки из меню.

        Args:
            update: Объект обновления Telegram
            context: Контекст выполнения
            choice: Выбор пользователя (1-4)
        """
        user_id = update.effective_user.id
        settings = self.user_manager.get_settings(user_id)

        mode_map = {
            "1": "hidden",
            "2": "compact",
            "3": "detailed",
            "4": "warnings_only",
        }

        if choice in mode_map:
            settings.display_mode = mode_map[choice]
            settings.auto_show = choice != "1"  # Выключаем auto_show для hidden
            self.user_manager.save_settings(user_id)

            mode_names = {
                "hidden": "Скрытый",
                "compact": "Компактный",
                "detailed": "Подробный",
                "warnings_only": "Только предупреждения",
            }

            await update.message.reply_text(
                f"✅ Режим отображения изменен: {mode_names[settings.display_mode]}\n\n"
                f"Настройки сохранены!"
            )
            logger.info(f"User {user_id} changed display mode to {settings.display_mode}")


# ==================== ЭКСПОРТ ====================

__all__ = ["TokenCommandHandler"]
