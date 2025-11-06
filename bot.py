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
from prompts import SYSTEM_PROMPT_DEFAULT, SYSTEM_PROMPT_JSON, SYSTEM_PROMPT_XML, SYSTEM_PROMPT_JOKER

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


class JokeContext:
    """Контекст диалога для генерации анекдотов."""

    def __init__(self):
        """Инициализация контекста."""
        self.relevant_count = 0  # Счётчик релевантных сообщений
        self.characters = None   # Персонажи анекдота
        self.situation = None    # Ситуация
        self.location = None     # Место действия
        self.message_history = []  # История сообщений для контекста

    def update_from_response(self, response_data: dict) -> None:
        """
        Обновление контекста на основе ответа от Yandex GPT.

        Args:
            response_data: Распарсенный JSON ответ от GPT
        """
        if "relevant_count" in response_data:
            self.relevant_count = response_data["relevant_count"]

        if "collected_info" in response_data:
            info = response_data["collected_info"]
            if info.get("characters"):
                self.characters = info["characters"]
            if info.get("situation"):
                self.situation = info["situation"]
            if info.get("location"):
                self.location = info["location"]

    def add_message(self, role: str, text: str) -> None:
        """
        Добавление сообщения в историю.

        Args:
            role: Роль отправителя ("user" или "assistant")
            text: Текст сообщения
        """
        self.message_history.append({"role": role, "text": text})
        # Ограничиваем историю последними 10 сообщениями
        if len(self.message_history) > 10:
            self.message_history = self.message_history[-10:]

    def reset(self) -> None:
        """Сброс контекста для начала нового анекдота."""
        self.relevant_count = 0
        self.characters = None
        self.situation = None
        self.location = None
        self.message_history = []

    def is_joke_ready(self) -> bool:
        """Проверка, готов ли контекст для генерации анекдота."""
        return self.relevant_count >= 3


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

    async def send_message(
        self,
        user_message: str,
        system_prompt: str = SYSTEM_PROMPT_DEFAULT,
        message_history: Optional[list] = None
    ) -> Optional[str]:
        """
        Отправка сообщения в Yandex GPT и получение ответа.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт (по умолчанию SYSTEM_PROMPT_DEFAULT)
            message_history: История предыдущих сообщений для контекста

        Returns:
            Ответ от Yandex GPT или None в случае ошибки
        """
        # Формируем список сообщений с учётом истории
        messages = [
            {
                "role": "system",
                "text": system_prompt,
            }
        ]

        # Добавляем историю сообщений, если она есть
        if message_history:
            messages.extend(message_history)

        # Добавляем текущее сообщение пользователя
        messages.append({
            "role": "user",
            "text": user_message,
        })

        payload = {
            "modelUri": f"gpt://{os.getenv('YANDEX_FOLDER_ID', 'folder_id')}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.9,
                "maxTokens": 2000,
            },
            "messages": messages,
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
        self.user_modes: dict[int, str] = {}  # {user_id: "text" | "json" | "xml" | "joker"}

        # Хранилище контекстов для режима Joker
        self.joke_contexts: dict[int, JokeContext] = {}  # {user_id: JokeContext}

        # Менеджер форматов
        self.format_manager = FormatManager()

        # Регистрация обработчиков команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("text", self.text_mode_command))
        self.application.add_handler(CommandHandler("json", self.json_mode_command))
        self.application.add_handler(CommandHandler("xml", self.xml_mode_command))
        self.application.add_handler(CommandHandler("joker", self.joker_mode_command))
        self.application.add_handler(CommandHandler("newjoke", self.new_joke_command))
        self.application.add_handler(CommandHandler("status", self.status_command))

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
            "🔄 Режимы работы:\n"
            "/text - Текстовый режим (по умолчанию)\n"
            "/json - JSON код\n"
            "/xml - XML код\n"
            "/joker - Генератор анекдотов категории Б\n"
            "/status - Проверить текущий режим\n\n"
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
            "/status - Проверить текущий режим\n"
            "/newjoke - Начать создание нового анекдота (в режиме Joker)\n\n"
            "🔄 Режимы работы:\n"
            "/text - Текстовый режим (по умолчанию)\n"
            "  Ответ отображается в красивом формате с иконками\n\n"
            "/json - JSON режим\n"
            "  Ответ отображается в виде JSON кода\n\n"
            "/xml - XML режим\n"
            "  Ответ отображается в виде XML кода\n\n"
            "/joker - Режим генератора анекдотов категории Б\n"
            "  Бот собирает информацию о персонажах, ситуации и месте,\n"
            "  затем генерирует пикантный анекдот\n\n"
            "⚠️ Примечание: В обычных режимах я не могу выполнять команды,\n"
            "искать в интернете или обрабатывать файлы. Только текстовые ответы!"
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

    async def joker_mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /joker - переключение на режим генератора анекдотов."""
        user_id = update.effective_user.id
        self.user_modes[user_id] = "joker"

        # Создаём новый контекст для пользователя
        self.joke_contexts[user_id] = JokeContext()

        message = (
            "✅ Режим изменён: ГЕНЕРАТОР АНЕКДОТОВ\n\n"
            "Привет! Я помогу тебе создать отличный анекдот категории Б!\n\n"
            "Я буду задавать вопросы о:\n"
            "• Персонажах (кто участвует в анекдоте)\n"
            "• Ситуации (что происходит)\n"
            "• Месте действия (где происходит)\n\n"
            "После всех ответов я сгенерирую для тебя пикантный анекдот!\n\n"
            "💡 Команды:\n"
            "/newjoke - начать создание нового анекдота\n"
            "/text - вернуться в обычный режим\n\n"
            "Давай начнём! Расскажи, кто будут главные персонажи?"
        )
        await update.message.reply_text(message)
        logger.info(f"Пользователь {user_id} переключился на режим Joker")

    async def new_joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /newjoke - сброс контекста и начало нового анекдота."""
        user_id = update.effective_user.id

        # Проверка, что пользователь в режиме Joker
        if self.user_modes.get(user_id) != "joker":
            message = (
                "⚠️ Эта команда доступна только в режиме генератора анекдотов!\n\n"
                "Используй /joker для переключения в этот режим."
            )
            await update.message.reply_text(message)
            return

        # Сброс контекста
        self.joke_contexts[user_id] = JokeContext()

        message = (
            "🔄 Начинаем создание нового анекдота!\n\n"
            "Расскажи, кто будут главные персонажи твоего анекдота?\n"
            "Может быть, это будут студент и преподавательница,\n"
            "или начальник и секретарша?"
        )
        await update.message.reply_text(message)
        logger.info(f"Пользователь {user_id} начал создание нового анекдота")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /status - проверка текущего режима."""
        user_id = update.effective_user.id
        current_mode = self.user_modes.get(user_id, DEFAULT_MODE)

        mode_names = {
            "text": "ТЕКСТОВЫЙ (красивое форматирование)",
            "json": "JSON (код)",
            "xml": "XML (код)",
            "joker": "ГЕНЕРАТОР АНЕКДОТОВ"
        }

        message = f"ℹ️ Текущий режим: {mode_names.get(current_mode, 'НЕИЗВЕСТНЫЙ')}\n\n"

        # Дополнительная информация для режима Joker
        if current_mode == "joker":
            joke_ctx = self.joke_contexts.get(user_id)
            if joke_ctx:
                message += (
                    f"📊 Статистика текущего анекдота:\n"
                    f"• Релевантных сообщений: {joke_ctx.relevant_count}/3-5\n"
                    f"• Персонажи: {'✓' if joke_ctx.characters else '✗'}\n"
                    f"• Ситуация: {'✓' if joke_ctx.situation else '✗'}\n"
                    f"• Место: {'✓' if joke_ctx.location else '✗'}\n\n"
                )
            message += "💡 Команды:\n/newjoke - начать новый анекдот\n"
        else:
            message += (
                "Для смены режима используйте команды:\n"
                "/text - текстовый режим\n"
                "/json - JSON режим\n"
                "/xml - XML режим\n"
                "/joker - генератор анекдотов"
            )

        await update.message.reply_text(message)
        logger.info(f"Пользователь {user_id} проверил статус: режим {current_mode}")

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
        logger.info(f"Режим для пользователя {user_id}: {mode}")

        # Выбор системного промпта и истории в зависимости от режима
        message_history = None

        if mode == "joker":
            system_prompt = SYSTEM_PROMPT_JOKER
            # Получаем или создаём контекст для пользователя
            if user_id not in self.joke_contexts:
                self.joke_contexts[user_id] = JokeContext()
            joke_ctx = self.joke_contexts[user_id]
            message_history = joke_ctx.message_history
        elif mode == "json":
            system_prompt = SYSTEM_PROMPT_JSON
        elif mode == "xml":
            system_prompt = SYSTEM_PROMPT_XML
        else:  # text mode
            system_prompt = SYSTEM_PROMPT_DEFAULT

        # Отправка индикатора набора текста
        await update.message.chat.send_action("typing")

        # Отправка запроса в Yandex GPT с нужным системным промптом и историей
        response = await self.gpt_client.send_message(
            user_message,
            system_prompt,
            message_history
        )

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
            if mode == "joker":
                # Парсим JSON используя FormatManager (поддерживает markdown блоки)
                response_data = self.format_manager.parse_json(response)

                if response_data:
                    # Успешно распарсили JSON
                    # Обновляем контекст на основе ответа
                    joke_ctx.update_from_response(response_data)

                    # Добавляем сообщения в историю
                    joke_ctx.add_message("user", user_message)
                    joke_ctx.add_message("assistant", response_data.get("answer", ""))

                    # Форматируем ответ для пользователя из уже распарсенного dict
                    formatted_response = self.format_manager._format_joker_from_dict(response_data)

                    # Проверяем, был ли сгенерирован анекдот
                    message_type = response_data.get("message_type", "")
                    if message_type == "joke":
                        logger.info(f"Анекдот сгенерирован для пользователя {user_id}, сброс контекста")
                        # Сбрасываем контекст после генерации анекдота
                        self.joke_contexts[user_id].reset()
                    elif message_type == "redirecting":
                        logger.info(f"Пользователь {user_id} отклонился от темы, возврат к созданию анекдота")
                    elif message_type == "collecting":
                        logger.info(f"Сбор информации для анекдота, пользователь {user_id}, прогресс: {response_data.get('relevant_count', 0)}/3-5")
                else:
                    # Не удалось распарсить JSON - логируем полную информацию
                    logger.error(
                        f"Ошибка парсинга JSON в режиме Joker для пользователя {user_id}:\n"
                        f"parse_json() вернул None\n"
                        f"Ответ от GPT (первые 1000 символов):\n{response[:1000]}\n"
                        f"{'...' if len(response) > 1000 else ''}"
                    )
                    # Показываем пользователю ошибку
                    formatted_response = (
                        "❌ Ошибка обработки ответа\n\n"
                        "Извините, произошла ошибка при обработке ответа от AI.\n"
                        "Попробуйте переформулировать или используйте /newjoke для начала нового анекдота."
                    )

            elif mode == "text":
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
