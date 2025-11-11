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
from huggingface_client import HuggingFaceClient

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

        # HuggingFace клиент (опционально, если есть API ключ)
        try:
            self.hf_client = HuggingFaceClient()
            logger.info("HuggingFace клиент инициализирован")
        except Exception as e:
            logger.warning(f"HuggingFace клиент недоступен: {e}")
            self.hf_client = None

        # Регистрация обработчиков команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("text", self.text_mode_command))
        self.application.add_handler(CommandHandler("json", self.json_mode_command))
        self.application.add_handler(CommandHandler("xml", self.xml_mode_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("test_temperature", self.test_temperature_command))
        self.application.add_handler(CommandHandler("compare_hf", self.compare_hf_models_command))

        # Обработчик текстовых сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

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
            "🧪 Тестирование:\n"
            "/test_temperature - Сравнить работу LLM при разных температурах\n"
            "/compare_hf - Сравнить HuggingFace модели (интерактивно)\n\n"
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
            "🧪 Тестирование температуры LLM:\n"
            "/test_temperature - Тест с дефолтным промптом\n"
            "/test_temperature <промпт> - Тест с вашим промптом\n\n"
            "Температура влияет на креативность и предсказуемость ответов:\n"
            "• 0.0 = детерминированность (точные ответы)\n"
            "• 0.7 = баланс (универсальный режим)\n"
            "• 1.0 = креативность (оригинальные идеи)\n\n"
            "🤖 Сравнение LLM моделей:\n"
            "/compare_hf - Тест с дефолтным промптом\n"
            "/compare_hf <промпт> - Тест с вашим промптом\n\n"
            "Сравниваются 3 модели в реальном времени:\n"
            "• Qwen 2.5 7B (HuggingFace, 7.61B параметров)\n"
            "• Llama 3.2 3B (HuggingFace, 3.21B параметров)\n"
            "• Yandex GPT Lite (Yandex Cloud)\n\n"
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

    async def compare_hf_models_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /compare_hf - интерактивное сравнение LLM моделей.

        Сравниваются 3 модели:
        - Qwen 2.5 7B (HuggingFace)
        - Llama 3.2 3B (HuggingFace)
        - Yandex GPT Lite (Yandex Cloud)

        Использование:
            /compare_hf - использовать дефолтный промпт
            /compare_hf <ваш промпт> - использовать кастомный промпт
        """
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запустил сравнение LLM моделей")

        # Проверка доступности HuggingFace клиента
        if not self.hf_client:
            error_message = (
                "❌ HuggingFace API недоступен\n\n"
                "Для использования этой функции необходимо:\n"
                "1. Получить токен на https://huggingface.co/settings/tokens\n"
                "2. Добавить HUGGINGFACE_API_KEY в .env файл\n"
                "3. Перезапустить бота\n\n"
                "Подробнее: см. документацию в docs/huggingface_integration.md"
            )
            await update.message.reply_text(error_message)
            return

        # Получение промпта из аргументов команды
        if context.args:
            user_prompt = " ".join(context.args)
        else:
            user_prompt = "Объясни простыми словами, что такое квантовая запутанность"

        # Создание начального сообщения с прогрессом
        progress_message = await update.message.reply_text(
            "🤖 **СРАВНЕНИЕ LLM МОДЕЛЕЙ**\n\n"
            f"📝 Промпт: _{user_prompt}_\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⏳ Подготовка...",
            parse_mode="Markdown"
        )

        try:
            # Отправка индикатора набора текста
            await update.message.chat.send_action("typing")

            # Обновление: начинаем тестирование первой модели
            await progress_message.edit_text(
                "🤖 **СРАВНЕНИЕ LLM МОДЕЛЕЙ**\n\n"
                f"📝 Промпт: _{user_prompt}_\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🔄 Тестирование Qwen 2.5 7B...\n"
                "⏸️ Ожидание: Llama 3.2 3B\n"
                "⏸️ Ожидание: Yandex GPT",
                parse_mode="Markdown"
            )

            # Тестирование первой модели
            metrics_qwen = await asyncio.to_thread(
                self.hf_client.generate_response,
                "qwen",
                user_prompt,
                max_tokens=400,
                temperature=0.7
            )

            # Обновление: первая модель готова, начинаем вторую
            await progress_message.edit_text(
                "🤖 **СРАВНЕНИЕ LLM МОДЕЛЕЙ**\n\n"
                f"📝 Промпт: _{user_prompt}_\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ Qwen 2.5 7B: {metrics_qwen.execution_time:.2f}с\n"
                "🔄 Тестирование Llama 3.2 3B...\n"
                "⏸️ Ожидание: Yandex GPT",
                parse_mode="Markdown"
            )

            await update.message.chat.send_action("typing")

            # Тестирование второй модели
            metrics_llama = await asyncio.to_thread(
                self.hf_client.generate_response,
                "llama",
                user_prompt,
                max_tokens=400,
                temperature=0.7
            )

            # Обновление: вторая модель готова, начинаем третью
            await progress_message.edit_text(
                "🤖 **СРАВНЕНИЕ LLM МОДЕЛЕЙ**\n\n"
                f"📝 Промпт: _{user_prompt}_\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ Qwen 2.5 7B: {metrics_qwen.execution_time:.2f}с\n"
                f"✅ Llama 3.2 3B: {metrics_llama.execution_time:.2f}с\n"
                "🔄 Тестирование Yandex GPT...",
                parse_mode="Markdown"
            )

            await update.message.chat.send_action("typing")

            # Тестирование Yandex GPT
            import time
            start_time = time.time()
            yandex_response = await self.gpt_client.send_message(user_prompt)
            yandex_time = time.time() - start_time

            # Подсчет токенов для Yandex GPT (приблизительно)
            yandex_input_tokens = len(user_prompt) // 4
            yandex_output_tokens = len(yandex_response) // 4 if yandex_response else 0
            yandex_total_tokens = yandex_input_tokens + yandex_output_tokens

            # Обновление: все модели готовы
            await progress_message.edit_text(
                "🤖 **СРАВНЕНИЕ LLM МОДЕЛЕЙ**\n\n"
                f"📝 Промпт: _{user_prompt}_\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ Qwen 2.5 7B: {metrics_qwen.execution_time:.2f}с\n"
                f"✅ Llama 3.2 3B: {metrics_llama.execution_time:.2f}с\n"
                f"✅ Yandex GPT: {yandex_time:.2f}с\n\n"
                "📊 Формирование результатов...",
                parse_mode="Markdown"
            )

            await asyncio.sleep(0.5)

            # Формирование итогового отчета
            report = self._format_comparison_report(
                metrics_qwen,
                metrics_llama,
                yandex_response,
                yandex_time,
                yandex_input_tokens,
                yandex_output_tokens,
                yandex_total_tokens,
                user_prompt
            )

            # Удаление прогресс-сообщения
            await progress_message.delete()

            # Отправка результатов (может быть в нескольких сообщениях)
            max_length = 4096
            if len(report) <= max_length:
                await update.message.reply_text(report)
            else:
                parts = self._split_long_message(report, max_length)
                for part in parts:
                    await update.message.reply_text(part)
                    await asyncio.sleep(0.5)

            logger.info(f"Сравнение HuggingFace моделей завершено для пользователя {user_id}")

        except Exception as e:
            logger.error(f"Ошибка при сравнении HuggingFace моделей для пользователя {user_id}: {e}", exc_info=True)

            # Удаляем прогресс-сообщение при ошибке
            try:
                await progress_message.delete()
            except:
                pass

            error_message = (
                "❌ Произошла ошибка при сравнении моделей.\n\n"
                f"Детали: {str(e)[:200]}\n\n"
                "Пожалуйста, попробуйте позже или проверьте настройки API."
            )
            await update.message.reply_text(error_message)

    def _format_comparison_report(self, metrics_qwen, metrics_llama, yandex_response,
                                   yandex_time, yandex_input_tokens, yandex_output_tokens,
                                   yandex_total_tokens, prompt: str) -> str:
        """
        Форматирование отчета сравнения LLM моделей.

        Args:
            metrics_qwen: Метрики Qwen модели
            metrics_llama: Метрики Llama модели
            yandex_response: Ответ от Yandex GPT
            yandex_time: Время выполнения Yandex GPT
            yandex_input_tokens: Входные токены Yandex
            yandex_output_tokens: Выходные токены Yandex
            yandex_total_tokens: Всего токенов Yandex
            prompt: Промпт для тестирования

        Returns:
            Отформатированный отчет
        """
        # Определение самой быстрой модели
        times = {
            "Qwen 2.5 7B": metrics_qwen.execution_time,
            "Llama 3.2 3B": metrics_llama.execution_time,
            "Yandex GPT": yandex_time
        }
        fastest_model = min(times, key=times.get)

        # Определение самой детальной модели
        tokens = {
            "Qwen 2.5 7B": metrics_qwen.output_tokens,
            "Llama 3.2 3B": metrics_llama.output_tokens,
            "Yandex GPT": yandex_output_tokens
        }
        most_detailed_model = max(tokens, key=tokens.get)

        report = (
            "🤖 **РЕЗУЛЬТАТЫ СРАВНЕНИЯ LLM МОДЕЛЕЙ**\n\n"
            f"📝 Промпт: _{prompt[:80]}{'...' if len(prompt) > 80 else ''}_\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📊 **МЕТРИКИ**\n\n"
            f"**1️⃣ Qwen 2.5 7B** (HuggingFace, 7.61B)\n"
            f"https://huggingface.co/Qwen/Qwen2.5-7B-Instruct\n"
            f"⏱️ Время: {metrics_qwen.execution_time:.2f}с\n"
            f"📊 Токены: {metrics_qwen.input_tokens} → {metrics_qwen.output_tokens} ({metrics_qwen.total_tokens})\n"
            f"💰 {metrics_qwen.cost}\n\n"
            f"**2️⃣ Llama 3.2 3B** (HuggingFace, 3.21B)\n"
            f"https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct\n"
            f"⏱️ Время: {metrics_llama.execution_time:.2f}с\n"
            f"📊 Токены: {metrics_llama.input_tokens} → {metrics_llama.output_tokens} ({metrics_llama.total_tokens})\n"
            f"💰 {metrics_llama.cost}\n\n"
            f"**3️⃣ Yandex GPT Lite** (Yandex Cloud)\n"
            f"⏱️ Время: {yandex_time:.2f}с\n"
            f"📊 Токены: {yandex_input_tokens} → {yandex_output_tokens} ({yandex_total_tokens})\n"
            f"💰 По тарифу Yandex Cloud\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏆 **ВЫВОДЫ**\n\n"
            f"⚡ Самая быстрая: **{fastest_model}** ({times[fastest_model]:.2f}с)\n"
            f"📝 Самая детальная: **{most_detailed_model}** ({tokens[most_detailed_model]} токенов)\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💬 **ОТВЕТ: QWEN 2.5 7B**\n\n"
            f"{metrics_qwen.response[:500]}{'...' if len(metrics_qwen.response) > 500 else ''}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💬 **ОТВЕТ: LLAMA 3.2 3B**\n\n"
            f"{metrics_llama.response[:500]}{'...' if len(metrics_llama.response) > 500 else ''}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💬 **ОТВЕТ: YANDEX GPT**\n\n"
            f"{yandex_response[:500] if yandex_response else 'Ошибка получения ответа'}{'...' if yandex_response and len(yandex_response) > 500 else ''}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📚 Детали: docs/llm_comparison_results.md"
        )

        return report

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

            await update.message.reply_text(formatted_response)
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
