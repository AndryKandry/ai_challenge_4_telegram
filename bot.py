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

# Импорт модулей форматирования и промптов
from format_manager import FormatManager
from prompts import SYSTEM_PROMPT_DEFAULT, SYSTEM_PROMPT_JSON, SYSTEM_PROMPT_XML
from temperature_tester import TemperatureTester

# Импорт модулей подсчета токенов
from token_counter import TokenCounter
from token_ui import (
    format_token_help_message,
    format_token_stats,
    format_token_overflow_message,
)
from token_commands import TokenCommandHandler
from error_handlers import check_token_limit_before_request, handle_token_overflow
from user_settings import UserDataManager
from token_limit_tester import TokenLimitTester

# Импорт модулей компрессии диалога
from dialog_compressor import DialogCompressor, DialogHistory

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
DEFAULT_MODE = "text"  # Режим вывода по умолчанию


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

    async def send_message(self, user_message: str, system_prompt: str = SYSTEM_PROMPT_DEFAULT) -> Optional[str]:
        """
        Отправка сообщения в Yandex GPT и получение ответа.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт (по умолчанию SYSTEM_PROMPT_DEFAULT)

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
                    "text": system_prompt,
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

        # Хранилище режимов вывода для каждого пользователя
        self.user_modes: dict[int, str] = {}  # {user_id: "text" | "json" | "xml"}

        # Менеджер форматов
        self.format_manager = FormatManager()

        # Тестер температуры
        self.temperature_tester = TemperatureTester(yandex_api_key)

        # Система подсчета токенов
        self.token_counter = TokenCounter(yandex_api_key)
        self.user_manager = UserDataManager()
        self.token_command_handler = TokenCommandHandler(self.user_manager)
        self.token_limit_tester = TokenLimitTester(self.gpt_client, self.token_counter)

        # Система компрессии диалога
        self.dialog_compressor = DialogCompressor(yandex_api_key, self.token_counter)
        self.user_histories: dict[int, DialogHistory] = {}  # {user_id: DialogHistory}

        # Регистрация обработчиков команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("text", self.text_mode_command))
        self.application.add_handler(CommandHandler("json", self.json_mode_command))
        self.application.add_handler(CommandHandler("xml", self.xml_mode_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("test_temperature", self.test_temperature_command))

        # Регистрация команд для работы с токенами
        self.application.add_handler(CommandHandler("tokens", self.tokens_command))
        self.application.add_handler(CommandHandler("tokens_stats", self.tokens_stats_command))
        self.application.add_handler(CommandHandler("token_mode", self.token_mode_command))
        self.application.add_handler(CommandHandler("token_settings", self.token_settings_command))
        self.application.add_handler(CommandHandler("token_help", self.token_help_command))
        self.application.add_handler(CommandHandler("test_tokens", self.test_tokens_command))

        # Регистрация команды компрессии диалога
        self.application.add_handler(CommandHandler("compact", self.compact_command))

        # Обработчик текстовых сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    def _get_or_create_history(self, user_id: int) -> DialogHistory:
        """
        Получить или создать историю диалога для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            История диалога пользователя
        """
        if user_id not in self.user_histories:
            self.user_histories[user_id] = DialogHistory()
            logger.info(f"Created new dialog history for user {user_id}")
        return self.user_histories[user_id]

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start."""
        user_id = update.effective_user.id
        welcome_message = (
            "👋 Привет! Я ИИ-ассистент на базе Yandex GPT.\n\n"
            "Просто отправь мне текстовое сообщение, и я постараюсь помочь!\n\n"
            "📝 Ограничение: максимум 2000 символов на сообщение.\n\n"
            "🔄 Режимы вывода:\n"
            "/text - Текстовый (по умолчанию)\n"
            "/json - JSON код\n"
            "/xml - XML код\n"
            "/status - Проверить текущий режим\n\n"
            "🗜️ Оптимизация:\n"
            "/compact - Сжать ВСЮ историю в резюме (экономия токенов)\n\n"
            "🧪 Тестирование:\n"
            "/test_temperature - Сравнить работу LLM при разных температурах\n"
            "/test_tokens - Демо: запросы разного размера и токены\n\n"
            "❓ Используй /help для полной справки."
        )
        await update.message.reply_text(welcome_message)
        logger.info(f"Пользователь {user_id} начал диалог")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help."""
        help_message = (
            "🤖 Справка по использованию бота:\n\n"
            "• Просто напиши мне любой вопрос или запрос\n"
            "• Я отвечу с помощью искусственного интеллекта Yandex GPT\n"
            "• Максимальная длина сообщения: 2000 символов\n\n"
            "📌 Основные команды:\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать эту справку\n"
            "/status - Проверить текущий режим вывода\n\n"
            "🔄 Режимы вывода:\n"
            "/text - Текстовый режим (по умолчанию)\n"
            "  Ответ отображается в красивом формате с иконками\n\n"
            "/json - JSON режим\n"
            "  Ответ отображается в виде JSON кода\n\n"
            "/xml - XML режим\n"
            "  Ответ отображается в виде XML кода\n\n"
            "📊 Подсчёт токенов:\n"
            "/tokens - Статистика последнего запроса\n"
            "/tokens_stats - Общая статистика за сессию/день\n"
            "/token_mode on/off - Включить/выключить показ токенов\n"
            "/token_settings - Настройки отображения токенов\n"
            "/token_help - Справка о токенах\n"
            "/test_tokens - Демо: тест разных размеров запросов\n\n"
            "🗜️ Оптимизация токенов:\n"
            "/compact - Сжать ВСЮ историю диалога в краткое резюме\n"
            "  • Создаёт резюме из ВСЕХ предыдущих сообщений\n"
            "  • Автокомпрессия: при 50 сообщениях (сохраняет 10 последних)\n"
            "  • Экономия: 30-50% токенов при длительных диалогах\n\n"
            "🧪 Тестирование температуры LLM:\n"
            "/test_temperature - Тест с дефолтным промптом\n"
            "/test_temperature <промпт> - Тест с вашим промптом\n\n"
            "Температура влияет на креативность и предсказуемость ответов:\n"
            "• 0.0 = детерминированность (точные ответы)\n"
            "• 0.7 = баланс (универсальный режим)\n"
            "• 1.0 = креативность (оригинальные идеи)\n\n"
            "⚠️ Примечание: Я не могу выполнять команды, искать в интернете "
            "или обрабатывать файлы. Только текстовые ответы!"
        )
        await update.message.reply_text(help_message)
        logger.info(f"Пользователь {update.effective_user.id} запросил справку")

    async def text_mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /text - переключение на текстовый режим."""
        user_id = update.effective_user.id
        self.user_modes[user_id] = "text"

        message = (
            "✅ Режим вывода изменен: ТЕКСТОВЫЙ\n\n"
            "Теперь ответы будут отображаться в красивом формате:\n"
            "📅 Дата и время\n"
            "❓ Тема вопроса\n"
            "💬 Ответ\n\n"
            "Структурированные данные (JSON/XML) будут скрыты от вас."
        )
        await update.message.reply_text(message)
        logger.info(f"Пользователь {user_id} переключился на текстовый режим")

    async def json_mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /json - переключение на JSON режим."""
        user_id = update.effective_user.id
        self.user_modes[user_id] = "json"

        message = (
            "✅ Режим вывода изменен: JSON\n\n"
            "Теперь ответы будут отображаться в формате JSON кода.\n"
            "Структура ответа:\n"
            "```json\n"
            "{\n"
            '  "datetime": "2025-11-05T14:30:00",\n'
            '  "question": "краткая тема вопроса",\n'
            '  "answer": "текстовый ответ"\n'
            "}\n"
            "```"
        )
        await update.message.reply_text(message)
        logger.info(f"Пользователь {user_id} переключился на JSON режим")

    async def xml_mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /xml - переключение на XML режим."""
        user_id = update.effective_user.id
        self.user_modes[user_id] = "xml"

        message = (
            "✅ Режим вывода изменен: XML\n\n"
            "Теперь ответы будут отображаться в формате XML кода.\n"
            "Структура ответа:\n"
            "```xml\n"
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<response>\n"
            "  <datetime>2025-11-05T14:30:00</datetime>\n"
            "  <question>краткая тема вопроса</question>\n"
            "  <answer>текстовый ответ</answer>\n"
            "</response>\n"
            "```"
        )
        await update.message.reply_text(message)
        logger.info(f"Пользователь {user_id} переключился на XML режим")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /status - проверка текущего режима."""
        user_id = update.effective_user.id
        current_mode = self.user_modes.get(user_id, DEFAULT_MODE)

        mode_names = {
            "text": "ТЕКСТОВЫЙ (красивое форматирование)",
            "json": "JSON (код)",
            "xml": "XML (код)"
        }

        message = (
            f"ℹ️ Текущий режим вывода: {mode_names.get(current_mode, 'НЕИЗВЕСТНЫЙ')}\n\n"
            f"Для смены режима используйте команды:\n"
            f"/text - текстовый режим\n"
            f"/json - JSON режим\n"
            f"/xml - XML режим"
        )
        await update.message.reply_text(message)
        logger.info(f"Пользователь {user_id} проверил статус: режим {current_mode}")

    async def test_temperature_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /test_temperature - тестирование разных температур LLM.

        Использование:
            /test_temperature - использовать дефолтный промпт
            /test_temperature <ваш промпт> - использовать кастомный промпт
        """
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запустил тестирование температуры")

        # Получение промпта из аргументов команды
        if context.args:
            user_prompt = " ".join(context.args)
        else:
            user_prompt = None  # Будет использован дефолтный промпт

        # Уведомление о начале тестирования
        await update.message.reply_text(
            "🧪 Запускаю тестирование температуры LLM...\n\n"
            "Отправляю запросы с тремя разными значениями температуры:\n"
            "• 0.0 (детерминированность)\n"
            "• 0.7 (сбалансированность)\n"
            "• 1.0 (креативность)\n\n"
            "⏳ Это может занять 10-30 секунд..."
        )

        # Отправка индикатора набора текста
        await update.message.chat.send_action("typing")

        try:
            # Запуск тестирования
            results = await self.temperature_tester.test_temperatures(user_prompt)

            # Форматирование и отправка результатов
            formatted_output = self.temperature_tester.format_test_results(results)

            # Отправка может быть длинной, разбиваем на части если нужно
            max_length = 4096  # Ограничение Telegram
            if len(formatted_output) <= max_length:
                await update.message.reply_text(formatted_output)
            else:
                # Разбиваем на части по разделителям
                parts = self._split_long_message(formatted_output, max_length)
                for part in parts:
                    await update.message.reply_text(part)
                    await asyncio.sleep(0.5)  # Небольшая задержка между частями

            logger.info(f"Тестирование температуры завершено для пользователя {user_id}")

        except Exception as e:
            logger.error(f"Ошибка при тестировании температуры для пользователя {user_id}: {e}", exc_info=True)
            error_message = (
                "❌ Произошла ошибка при тестировании температуры.\n\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            await update.message.reply_text(error_message)

    async def tokens_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /tokens - показывает статистику последнего запроса."""
        await self.token_command_handler.handle_tokens_command(update, context)

    async def tokens_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /tokens_stats - показывает общую статистику."""
        await self.token_command_handler.handle_tokens_stats_command(update, context)

    async def token_mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /token_mode - включение/выключение отображения токенов."""
        await self.token_command_handler.handle_token_mode_command(update, context)

    async def token_settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /token_settings - настройки отображения токенов."""
        await self.token_command_handler.handle_token_settings_command(update, context)

    async def token_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /token_help - справка о токенах."""
        await self.token_command_handler.handle_token_help_command(update, context)

    async def test_tokens_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /test_tokens - демонстрация поведения с разными размерами запросов.

        Отправляет 5 тестовых запросов разного размера:
        1. Короткий (< 100 токенов)
        2. Средний (~300-500 токенов)
        3. Длинный (~2000-3000 токенов)
        4. Очень длинный (~6000-7000 токенов, близко к лимиту)
        5. Превышающий лимит (> 10000 токенов)
        """
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запустил тестирование токенов")

        # Уведомление о начале тестирования
        await update.message.reply_text(
            "🧪 Запускаю тестирование лимитов токенов...\n\n"
            "Отправлю 5 тестовых запросов разного размера:\n"
            "1️⃣ Короткий (< 100 токенов)\n"
            "2️⃣ Средний (~300-500 токенов)\n"
            "3️⃣ Длинный (~2000-3000 токенов)\n"
            "4️⃣ Очень длинный (~6000-7000 токенов)\n"
            "5️⃣ Превышающий лимит (> 10000 токенов)\n\n"
            "⏳ Это займет 2-5 минут, будут отправлены реальные запросы в LLM..."
        )

        # Отправка индикатора набора текста
        await update.message.chat.send_action("typing")

        try:
            # Запуск тестирования
            results = await self.token_limit_tester.run_test_sequence()

            # Форматирование и отправка результатов
            formatted_output = self.token_limit_tester.format_test_results(results)

            # Отправка может быть длинной, разбиваем на части если нужно
            max_length = 4096  # Ограничение Telegram
            if len(formatted_output) <= max_length:
                await update.message.reply_text(formatted_output)
            else:
                # Разбиваем на части по разделителям
                parts = self._split_long_message(formatted_output, max_length)
                for part in parts:
                    await update.message.reply_text(part)
                    await asyncio.sleep(0.5)  # Небольшая задержка между частями

            logger.info(f"Тестирование токенов завершено для пользователя {user_id}")

        except Exception as e:
            logger.error(f"Ошибка при тестировании токенов для пользователя {user_id}: {e}", exc_info=True)
            error_message = (
                "❌ Произошла ошибка при тестировании токенов.\n\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            await update.message.reply_text(error_message)

    async def compact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /compact - ручная компрессия ВСЕЙ истории диалога.
        Создает резюме из ВСЕХ предыдущих сообщений, не сохраняя ни одного.
        """
        user_id = update.effective_user.id
        logger.info(f"User {user_id} requested manual compression of ALL messages")

        # Получить историю пользователя
        history = self._get_or_create_history(user_id)

        # Проверить, есть ли что сжимать
        if history.get_message_count() < 2:
            await update.message.reply_text(
                "ℹ️ История диалога слишком короткая для компрессии.\n\n"
                "Необходимо минимум 2 сообщения для выполнения компрессии."
            )
            return

        # Уведомление о начале компрессии
        await update.message.reply_text(
            "🗜️ Начинаю компрессию ВСЕЙ истории диалога...\n\n"
            "Все предыдущие сообщения будут заменены на краткое резюме.\n"
            "⏳ Это может занять несколько секунд..."
        )

        # Отправка индикатора набора текста
        await update.message.chat.send_action("typing")

        try:
            # Выполнить компрессию ВСЕХ сообщений (keep_last_n=0)
            success, result, stats = await self.dialog_compressor.compress_history(history, keep_last_n=0)

            if success:
                # Компрессия успешна - показываем статистику и резюме
                stats_message = self.dialog_compressor.get_compression_stats_message(stats)
                await update.message.reply_text(stats_message)

                # Показать резюме пользователю
                if history.compressed_context:
                    # Извлечь только резюме из сжатого контекста (без маркеров)
                    compressed_text = history.compressed_context
                    # Убираем маркеры [COMPRESSED CONTEXT] и [/COMPRESSED CONTEXT]
                    summary_text = compressed_text.replace("[COMPRESSED CONTEXT]", "").replace("[/COMPRESSED CONTEXT]", "").strip()

                    # Убираем заголовок "Резюме предыдущего диалога:" если есть
                    if summary_text.startswith("Резюме предыдущего диалога:"):
                        summary_text = summary_text.replace("Резюме предыдущего диалога:", "", 1).strip()

                    summary_message = f"📋 Резюме вашего диалога:\n\n{summary_text}"

                    # Разбиваем на части если слишком длинное
                    max_length = 4096  # Лимит Telegram
                    if len(summary_message) <= max_length:
                        await update.message.reply_text(summary_message)
                    else:
                        parts = self._split_long_message(summary_message, max_length)
                        for part in parts:
                            await update.message.reply_text(part)
                            await asyncio.sleep(0.3)

                logger.info(f"Manual compression (all messages) completed for user {user_id}: {stats}")
            else:
                # Ошибка компрессии
                error_message = (
                    f"❌ Ошибка при компрессии истории\n\n"
                    f"Причина: {result}\n\n"
                    f"Попробуйте позже или обратитесь к администратору."
                )
                await update.message.reply_text(error_message)
                logger.error(f"Manual compression failed for user {user_id}: {result}")

        except Exception as e:
            logger.error(f"Unexpected error during manual compression for user {user_id}: {e}", exc_info=True)
            error_message = (
                "❌ Произошла неожиданная ошибка при компрессии истории.\n\n"
                "Пожалуйста, попробуйте позже."
            )
            await update.message.reply_text(error_message)

    def _split_long_message(self, message: str, max_length: int) -> list[str]:
        """
        Разбивает длинное сообщение на части по разделителям.

        Args:
            message: Исходное сообщение
            max_length: Максимальная длина части

        Returns:
            Список частей сообщения
        """
        if len(message) <= max_length:
            return [message]

        parts = []
        current_part = ""
        lines = message.split("\n")

        for line in lines:
            if len(current_part) + len(line) + 1 <= max_length:
                current_part += line + "\n"
            else:
                if current_part:
                    parts.append(current_part.rstrip())
                current_part = line + "\n"

        if current_part:
            parts.append(current_part.rstrip())

        return parts

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

        # Получить историю диалога пользователя
        history = self._get_or_create_history(user_id)

        # Подсчет токенов в запросе пользователя
        request_tokens = self.token_counter.count_tokens(user_message)
        logger.info(f"Токены запроса пользователя {user_id}: {request_tokens}")

        # Проверка необходимости автоматической компрессии
        should_compress, reason = self.dialog_compressor.should_compress(history)
        if should_compress:
            logger.info(f"Auto-compression triggered for user {user_id}: {reason}")

            # Уведомить пользователя о компрессии
            compression_notice = (
                "🗜️ История диалога достигла лимита. Выполняю автоматическую компрессию...\n"
                "⏳ Секунду..."
            )
            notice_msg = await update.message.reply_text(compression_notice)

            try:
                # Выполнить автоматическую компрессию
                success, result, stats = await self.dialog_compressor.compress_history(history)

                if success:
                    # Удалить уведомление и показать статистику
                    await notice_msg.delete()
                    stats_message = (
                        f"✅ Автоматическая компрессия выполнена\n"
                        f"📊 Сэкономлено: {stats.get('savings', 0)}% токенов\n"
                    )
                    await update.message.reply_text(stats_message)
                    logger.info(f"Auto-compression completed for user {user_id}: {stats}")
                else:
                    # Компрессия не удалась, но продолжаем работу
                    await notice_msg.delete()
                    logger.warning(f"Auto-compression failed for user {user_id}: {result}")
            except Exception as e:
                logger.error(f"Error during auto-compression for user {user_id}: {e}", exc_info=True)
                # Продолжаем работу даже если компрессия не удалась

        # Проверка лимита токенов - показываем предупреждение, но отправляем запрос
        is_within_limit, error_msg = check_token_limit_before_request(request_tokens)
        if not is_within_limit:
            # Импортируем get_model_token_limit для расчета
            from config import get_model_token_limit

            # Отправляем предупреждение о превышении лимита, но продолжаем обработку
            limit = get_model_token_limit("yandexgpt-lite")
            overflow = request_tokens - limit
            percentage_over = (overflow / limit) * 100

            warning_message = (
                f"⚠️ Ваш запрос превышает рекомендуемый лимит!\n\n"
                f"📊 Ваш текст: ~{request_tokens:,} токенов\n"
                f"📏 Рекомендуемый лимит: {limit:,} токенов\n"
                f"❌ Превышение: {overflow:,} токенов (~{percentage_over:.0f}%)\n\n"
                f"⚠️ Отправляю запрос в LLM, но ответ может быть обрезан или некорректен.\n"
                f"Рекомендую сократить текст для лучшего результата."
            )
            await update.message.reply_text(warning_message)
            logger.warning(
                f"User {user_id} exceeds token limit: {request_tokens} > {limit}, "
                f"but request will be sent anyway"
            )
            # НЕ возвращаемся, продолжаем обработку запроса!

        # Получение текущего режима пользователя
        mode = self.user_modes.get(user_id, DEFAULT_MODE)
        logger.info(f"Режим вывода для пользователя {user_id}: {mode}")

        # Выбор системного промпта в зависимости от режима
        if mode == "json":
            system_prompt = SYSTEM_PROMPT_JSON
        elif mode == "xml":
            system_prompt = SYSTEM_PROMPT_XML
        else:  # text mode
            system_prompt = SYSTEM_PROMPT_DEFAULT

        # Установить системный промпт в историю (если еще не установлен)
        if history.system_prompt is None:
            history.set_system_prompt(system_prompt)

        # Отправка индикатора набора текста
        await update.message.chat.send_action("typing")

        # Отправка запроса в Yandex GPT с нужным системным промптом
        response = await self.gpt_client.send_message(user_message, system_prompt)

        if not response:
            # Ошибка получения ответа от API
            error_message = (
                "😔 Извините, произошла временная ошибка при обработке вашего запроса.\n\n"
                "Пожалуйста, попробуйте позже или переформулируйте вопрос."
            )
            await update.message.reply_text(error_message)
            logger.error(f"Не удалось получить ответ для пользователя {user_id}")
            return

        # Подсчет токенов в ответе
        response_tokens = self.token_counter.count_tokens(response)
        logger.info(f"Токены ответа для пользователя {user_id}: {response_tokens}")

        # Сохранение сообщений в историю диалога
        history.add_message("user", user_message)
        history.add_message("assistant", response)
        logger.debug(f"Saved messages to history for user {user_id}, total messages: {history.get_message_count()}")

        # Обновление статистики пользователя
        stats = self.user_manager.get_stats(user_id)
        stats.add_request(request_tokens, response_tokens)
        self.user_manager.save_stats(user_id)

        # Логирование использования токенов
        self.token_counter.log_token_usage(request_tokens, response_tokens)

        # Форматирование ответа в зависимости от режима
        try:
            if mode == "text":
                formatted_response = self.format_manager.format_text_response(response)
            elif mode == "json":
                formatted_response = self.format_manager.format_json_output(response)
            elif mode == "xml":
                formatted_response = self.format_manager.format_xml_output(response)
            else:
                # Fallback на текстовый режим
                formatted_response = self.format_manager.format_text_response(response)

            # Получение настроек пользователя для отображения токенов
            settings = self.user_manager.get_settings(user_id)

            # Показываем обучающее сообщение при первом использовании
            if settings.first_use and settings.show_help:
                help_message = format_token_help_message()
                await update.message.reply_text(help_message)
                settings.first_use = False
                self.user_manager.save_settings(user_id)

            # Добавляем статистику токенов к ответу если включено
            token_stats_message = format_token_stats(
                request_tokens, response_tokens, mode=settings.display_mode
            )

            # Отправляем ответ с статистикой токенов
            full_response = formatted_response + token_stats_message
            await update.message.reply_text(full_response)
            logger.info(f"Отправлен ответ пользователю {user_id} в режиме {mode}")

        except Exception as e:
            logger.error(f"Ошибка форматирования ответа для пользователя {user_id}: {e}")
            error_message = (
                "❌ Ошибка обработки ответа\n\n"
                "Произошла ошибка при форматировании ответа от AI.\n"
                "Пожалуйста, попробуйте снова."
            )
            await update.message.reply_text(error_message)

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
