#!/usr/bin/env python3
"""
Telegram бот с интеграцией Yandex GPT API.
Простой ИИ-агент без использования внешних инструментов.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Константы
MAX_MESSAGE_LENGTH = 2000  # Максимальная длина запроса пользователя
REQUEST_TIMEOUT = 30  # Таймаут запроса к Yandex GPT (секунды)
YANDEX_GPT_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Системный промпт для Yandex GPT
SYSTEM_PROMPT = """Ты — помощник в Telegram. Отвечай на русском языке.
Будь вежливым и информативным. Не выполняй внешние команды и не запрашивай личные данные."""


class YandexGPTClient:
    """Клиент для работы с Yandex GPT API."""

    def __init__(self, api_key: str, timeout: int = REQUEST_TIMEOUT):
        """
        Инициализация клиента Yandex GPT.

        Args:
            api_key: API ключ для Yandex Cloud
            timeout: Таймаут запроса в секундах
        """
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def send_message(self, user_message: str) -> Optional[str]:
        """
        Отправка сообщения в Yandex GPT и получение ответа.

        Args:
            user_message: Сообщение от пользователя

        Returns:
            Ответ от Yandex GPT или None в случае ошибки
        """
        payload = {
            "modelUri": f"gpt://{os.getenv('YANDEX_FOLDER_ID', 'folder_id')}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.9,
                "maxTokens": 2000,
            },
            "messages": [
                {
                    "role": "system",
                    "text": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "text": user_message,
                },
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info("Отправка запроса в Yandex GPT API")
                response = await client.post(
                    YANDEX_GPT_API_URL,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()

                # Парсинг ответа
                data = response.json()
                logger.info("Получен ответ от Yandex GPT API")

                # Извлечение текста ответа из структуры
                if "result" in data and "alternatives" in data["result"]:
                    alternatives = data["result"]["alternatives"]
                    if alternatives and len(alternatives) > 0:
                        message_text = alternatives[0].get("message", {}).get("text")
                        if message_text:
                            return message_text

                logger.error(f"Неожиданная структура ответа: {data}")
                return None

        except httpx.TimeoutException:
            logger.error("Превышен таймаут запроса к Yandex GPT API")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка при запросе к Yandex GPT: {e.response.status_code} - {e.response.text}")
            return None
        except ValueError as e:
            logger.error(f"Ошибка парсинга JSON ответа: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к Yandex GPT: {e}")
            return None


class TelegramBot:
    """Основной класс Telegram бота."""

    def __init__(self, telegram_token: str, yandex_api_key: str):
        """
        Инициализация бота.

        Args:
            telegram_token: Токен Telegram бота
            yandex_api_key: API ключ Yandex Cloud
        """
        self.gpt_client = YandexGPTClient(yandex_api_key)
        self.application = Application.builder().token(telegram_token).build()

        # Регистрация обработчиков
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start."""
        welcome_message = (
            "👋 Привет! Я ИИ-ассистент на базе Yandex GPT.\n\n"
            "Просто отправь мне текстовое сообщение, и я постараюсь помочь!\n\n"
            "📝 Ограничение: максимум 2000 символов на сообщение.\n"
            "❓ Используй /help для получения справки."
        )
        await update.message.reply_text(welcome_message)
        logger.info(f"Пользователь {update.effective_user.id} начал диалог")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help."""
        help_message = (
            "🤖 Справка по использованию бота:\n\n"
            "• Просто напиши мне любой вопрос или запрос\n"
            "• Я отвечу с помощью искусственного интеллекта Yandex GPT\n"
            "• Максимальная длина сообщения: 2000 символов\n\n"
            "📌 Доступные команды:\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать эту справку\n\n"
            "⚠️ Примечание: Я не могу выполнять команды, искать в интернете "
            "или обрабатывать файлы. Только текстовые ответы!"
        )
        await update.message.reply_text(help_message)
        logger.info(f"Пользователь {update.effective_user.id} запросил справку")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик текстовых сообщений от пользователя.

        Args:
            update: Об��ект обновления Telegram
            context: Контекст выполнения
        """
        user_message = update.message.text
        user_id = update.effective_user.id

        logger.info(f"Получено сообщение от пользователя {user_id}: {user_message[:50]}...")

        # Проверка длины сообщения
        if len(user_message) > MAX_MESSAGE_LENGTH:
            error_message = (
                f"❌ Извините, ваше сообщение слишком длинное!\n\n"
                f"Текущая длина: {len(user_message)} символов\n"
                f"Максимум: {MAX_MESSAGE_LENGTH} символов\n\n"
                f"Пожалуйста, сократите ваш запрос."
            )
            await update.message.reply_text(error_message)
            logger.warning(f"Отклонено длинное сообщение от пользователя {user_id}: {len(user_message)} символов")
            return

        # Отправка индикатора набора текста
        await update.message.chat.send_action("typing")

        # Отправка запроса в Yandex GPT
        response = await self.gpt_client.send_message(user_message)

        if response:
            # Успешный ответ
            await update.message.reply_text(response)
            logger.info(f"Отправлен ответ пользователю {user_id}")
        else:
            # Ошибка получения ответа
            error_message = (
                "😔 Извините, произошла временная ошибка при обработке вашего запроса.\n\n"
                "Пожалуйста, попробуйте позже или переформулируйте вопрос."
            )
            await update.message.reply_text(error_message)
            logger.error(f"Не удалось получить ответ для пользователя {user_id}")

    def run(self) -> None:
        """Запуск бота."""
        logger.info("Запуск Telegram бота...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def validate_environment() -> tuple[str, str]:
    """
    Проверка наличия необходимых переменных окружения.

    Returns:
        Кортеж (telegram_token, yandex_api_key)

    Raises:
        ValueError: Если не заданы необходимые переменные окружения
    """
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    yandex_api_key = os.getenv("YANDEX_API_KEY")

    if not telegram_token:
        raise ValueError(
            "TELEGRAM_TOKEN не задан! Установите переменную окружения: "
            "export TELEGRAM_TOKEN='your_token_here'"
        )

    if not yandex_api_key:
        raise ValueError(
            "YANDEX_API_KEY не задан! Установите переменную окружения: "
            "export YANDEX_API_KEY='your_api_key_here'"
        )

    # Опциональная проверка YANDEX_FOLDER_ID
    folder_id = os.getenv("YANDEX_FOLDER_ID")
    if not folder_id:
        logger.warning(
            "YANDEX_FOLDER_ID не задан! Может потребоваться для корректной работы с Yandex GPT."
        )

    return telegram_token, yandex_api_key


def main() -> None:
    """Главная функция запуска бота."""
    try:
        # Попытка загрузить переменные из .env файла (опционально)
        try:
            from dotenv import load_dotenv
            load_dotenv()
            logger.info("Переменные окружения загружены из .env файла")
        except ImportError:
            logger.info("python-dotenv не установлен, используются системные переменные окружения")

        # Валидация переменных окружения
        telegram_token, yandex_api_key = validate_environment()

        # Создание и запуск бота
        bot = TelegramBot(telegram_token, yandex_api_key)
        bot.run()

    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
