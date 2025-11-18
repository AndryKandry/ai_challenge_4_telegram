#!/usr/bin/env python3
"""
Минимальный тест для проверки работы бота с версией 22+
"""

import os
import logging
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text("Привет! Бот работает.")


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /test"""
    await update.message.reply_text("Тест успешен!")


def main():
    """Основная функция"""
    # Проверяем наличие токена
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN не установлен")
        print("Установите токен: export TELEGRAM_TOKEN='your_token'")
        return

    # Создаём приложение
    application = Application.builder().token(token).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))

    # Запускаем бота
    logger.info("Запуск тестового бота...")
    application.run_polling()


if __name__ == "__main__":
    main()
