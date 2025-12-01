#!/usr/bin/env python3
"""
Telegram бот с интеграцией Yandex GPT API.
Простой ИИ-агент без использования внешних инструментов.
"""

import asyncio
import logging
import os
import sys
import time
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
from database import MemoryManager
from mcp_client import MCPClient, get_all_mcp_configs

# Импорт провайдеров LLM и хранилища настроек
from providers import OpenAIProvider, YandexGPTProvider, DeepSeekProvider
from storage import UserSettings

# Импорт RAG модуля
from src.rag_integration import RAGManager
from src.integrations.telegram_document_handler import create_telegram_document_handler

# Импорт системы subagents
from agents import AgentOrchestrator, DocsAgent, GitAgent, HelpCommandAgent
from tools import ToolManager
from tools.rag_tools import DocumentSearchTool

# Импорт системы планировщика задач
from scheduler import TaskScheduler
from scheduler.builtin_tasks import ReindexDocumentsTask, HealthCheckTask

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


class RateLimiter:
    """
    Простой rate limiter для контроля частоты запросов пользователей.

    Использует sliding window алгоритм для отслеживания запросов.
    """

    def __init__(self, max_requests: int = 5, time_window: int = 60):
        """
        Инициализация rate limiter.

        Args:
            max_requests: Максимальное количество запросов в окне времени
            time_window: Размер окна времени в секундах
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.user_requests = {}  # {user_id: [timestamp1, timestamp2, ...]}

    def is_allowed(self, user_id: int) -> bool:
        """
        Проверяет, разрешен ли запрос для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            True если запрос разрешен, False если превышен лимит
        """
        current_time = time.time()

        # Получаем историю запросов пользователя
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        # Фильтруем запросы вне текущего окна времени
        self.user_requests[user_id] = [
            timestamp for timestamp in self.user_requests[user_id]
            if current_time - timestamp < self.time_window
        ]

        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.max_requests:
            return False

        # Добавляем текущий запрос
        self.user_requests[user_id].append(current_time)
        return True

    def get_wait_time(self, user_id: int) -> int:
        """
        Получает время ожидания до следующего разрешенного запроса.

        Args:
            user_id: ID пользователя

        Returns:
            Количество секунд до следующего разрешенного запроса
        """
        if user_id not in self.user_requests or not self.user_requests[user_id]:
            return 0

        current_time = time.time()
        oldest_request = min(self.user_requests[user_id])
        wait_time = self.time_window - (current_time - oldest_request)

        return max(0, int(wait_time))

    def reset_user(self, user_id: int) -> None:
        """
        Сбрасывает счетчик запросов для пользователя.

        Args:
            user_id: ID пользователя
        """
        if user_id in self.user_requests:
            del self.user_requests[user_id]


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
        Отправка сообщения в Yandex GPT и получение ответа (без контекста).

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт (по умолчанию SYSTEM_PROMPT_DEFAULT)

        Returns:
            Ответ от Yandex GPT или None в случае ошибки
        """
        return await self.send_message_with_history(user_message, system_prompt, [])

    async def send_message_with_history(
        self,
        user_message: str,
        system_prompt: str = SYSTEM_PROMPT_DEFAULT,
        conversation_history: list = None
    ) -> Optional[str]:
        """
        Отправка сообщения в Yandex GPT с учётом истории диалога.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога (список словарей с полями message_text и message_type)

        Returns:
            Ответ от Yandex GPT или None в случае ошибки
        """
        if conversation_history is None:
            conversation_history = []

        # Формируем список сообщений для API
        messages = [
            {
                "role": "system",
                "text": system_prompt,
            }
        ]

        # Добавляем историю диалога
        for msg in conversation_history:
            role = "user" if msg["message_type"] == "user" else "assistant"
            messages.append({
                "role": role,
                "text": msg["message_text"]
            })

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

    def __init__(
        self,
        telegram_token: str,
        yandex_api_key: str,
        openai_api_key: Optional[str] = None,
        deepseek_api_key: Optional[str] = None
    ):
        """
        Инициализация бота.

        Args:
            telegram_token: Токен Telegram бота
            yandex_api_key: API ключ Yandex Cloud
            openai_api_key: API ключ OpenAI (опционально)
            deepseek_api_key: API ключ DeepSeek (опционально)
        """
        # Сохраняем старый клиент для обратной совместимости
        self.gpt_client = YandexGPTClient(yandex_api_key)

        # Инициализация провайдеров
        self.yandex_provider = YandexGPTProvider(yandex_api_key)

        self.openai_provider = None
        if openai_api_key:
            self.openai_provider = OpenAIProvider(openai_api_key)
            logger.info("OpenAI Provider инициализирован")
        else:
            logger.warning("OPENAI_API_KEY не задан, OpenAI провайдер недоступен")

        # Инициализация RAG Manager
        try:
            self.rag_manager = RAGManager()
            logger.info("RAG Manager инициализирован")
        except Exception as e:
            logger.warning(f"RAG Manager не инициализирован: {e}")
            self.rag_manager = None

        # Инициализация Telegram документ хендлера
        try:
            self.document_handler = create_telegram_document_handler(self.rag_manager)
            if self.rag_manager:
                self.rag_manager.set_document_handler(self.document_handler)
            logger.info("Telegram document handler инициализирован")
        except Exception as e:
            logger.warning(f"Telegram document handler не инициализирован: {e}")
            self.document_handler = None

        self.deepseek_provider = None
        if deepseek_api_key:
            # Передаём RAG Manager в DeepSeek провайдер
            self.deepseek_provider = DeepSeekProvider(
                deepseek_api_key,
                rag_manager=self.rag_manager
            )
            logger.info("DeepSeek Provider инициализирован с RAG")
        else:
            logger.warning("DEEPSEEK_API_KEY не задан, DeepSeek провайдер недоступен")

        # Хранилище пользовательских настроек
        self.user_settings = UserSettings()

        # Создаём приложение с увеличенными таймаутами для стабильности
        self.application = (
            Application.builder()
            .token(telegram_token)
            .connect_timeout(60.0)  # Таймаут подключения
            .read_timeout(60.0)     # Таймаут чтения
            .write_timeout(60.0)    # Таймаут записи
            .pool_timeout(60.0)     # Таймаут пула соединений
            .get_updates_connect_timeout(60.0)  # Таймаут для get_updates
            .get_updates_read_timeout(60.0)     # Таймаут чтения для get_updates
            .build()
        )

        # Хранилище режимов вывода для каждого пользователя
        self.user_modes: dict[int, str] = {}  # {user_id: "text" | "json" | "xml"}

        # Менеджер форматов
        self.format_manager = FormatManager()

        # Rate limiter для команды /help (5 запросов в минуту)
        self.help_rate_limiter = RateLimiter(max_requests=5, time_window=60)
        logger.info("Rate limiter для /help инициализирован (5 запросов/60 секунд)")


        # Менеджер долговременной памяти
        self.memory = MemoryManager("agent_memory.db")
        self.memory.create_tables()
        logger.info("Система памяти инициализирована")

        # Инициализация системы subagents
        self.help_agent = None  # Будет инициализирован ниже
        try:
            self._initialize_subagents()
        except Exception as e:
            logger.warning(f"Не удалось инициализировать систему subagents: {e}")
            logger.warning("Команда /help будет недоступна")

        # Инициализация системы планировщика задач
        self.scheduler = None
        try:
            self._initialize_scheduler()
        except Exception as e:
            logger.warning(f"Не удалось инициализировать планировщик задач: {e}")
            logger.warning("Фоновые задачи будут недоступны")

        # Регистрация обработчиков команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("info", self.info_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("text", self.text_mode_command))
        self.application.add_handler(CommandHandler("json", self.json_mode_command))
        self.application.add_handler(CommandHandler("xml", self.xml_mode_command))
        self.application.add_handler(CommandHandler("status", self.status_command))

        # Команды управления памятью
        self.application.add_handler(CommandHandler("memory_stats", self.memory_stats_command))
        self.application.add_handler(CommandHandler("clear_memory", self.clear_memory_command))
        self.application.add_handler(CommandHandler("export_memory", self.export_memory_command))

        # Команды управления сессиями
        self.application.add_handler(CommandHandler("new_session", self.new_session_command))
        self.application.add_handler(CommandHandler("end_session", self.end_session_command))
        self.application.add_handler(CommandHandler("session_info", self.session_info_command))

        # Команды MCP
        self.application.add_handler(CommandHandler("mcp_tools", self.mcp_tools_command))

        # Команды переключения LLM провайдера
        self.application.add_handler(CommandHandler("openai", self.openai_command))
        self.application.add_handler(CommandHandler("yandex", self.yandex_command))
        self.application.add_handler(CommandHandler("deepseek", self.deepseek_command))
        self.application.add_handler(CommandHandler("model", self.model_command))

        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)

        # Обработчик текстовых сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        # Обработчик callback запросов для inline кнопок
        from telegram.ext import CallbackQueryHandler
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))

        # Регистрация post_init и post_shutdown для управления scheduler
        self.application.post_init = self._post_init
        self.application.post_shutdown = self._post_shutdown

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start."""
        user_id = update.effective_user.id
        welcome_message = (
            "👋 Привет! Я ИИ-ассистент с поддержкой нескольких LLM моделей.\n\n"
            "Просто отправь мне текстовое сообщение, и я постараюсь помочь!\n\n"
            "💡 Я помню контекст диалога в рамках сессии!\n"
            "📝 Ограничение: максимум 2000 символов на сообщение.\n\n"
            "🤖 Выбор LLM модели:\n"
            "/openai - OpenAI GPT (gpt-3.5-turbo)\n"
            "/yandex - Yandex GPT (yandexgpt-lite)\n"
            "/deepseek - DeepSeek (deepseek-chat)\n"
            "/model - Показать текущую модель\n\n"
            "🔄 Режимы вывода:\n"
            "/text - Текстовый (по умолчанию)\n"
            "/json - JSON код\n"
            "/xml - XML код\n"
            "/status - Проверить текущий режим\n\n"
            "💾 Управление сессиями:\n"
            "/session_info - Информация о текущей сессии\n"
            "/new_session - Начать новую сессию\n"
            "/end_session - Завершить текущую сессию\n\n"
            "🛠 MCP Инструменты:\n"
            "/mcp_tools - Показать доступные инструменты (Filesystem, GitHub)\n\n"
            "🤖 Работа с агентами с помощью команды /help\n"
            "❓ Используй /info для полной справки."
        )
        await update.message.reply_text(welcome_message)
        logger.info(f"Пользователь {user_id} начал диалог")

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /info - справка по боту."""
        help_message = (
            "🤖 Справка по использованию бота:\n\n"
            "• Просто напиши мне любой вопрос или запрос\n"
            "• Я отвечу с помощью искусственного интеллекта\n"
            "• Я помню контекст разговора в рамках текущей сессии! 💡\n"
            "• Максимальная длина сообщения: 2000 символов\n\n"
            "📌 Основные команды:\n"
            "/start - Начать работу с ботом\n"
            "/info - Показать эту справку\n"
            "/help <вопрос> - Получить помощь по проекту (документация, git)\n"
            "/status - Проверить текущий режим вывода\n\n"
            "🤖 Выбор LLM модели:\n"
            "/openai - OpenAI GPT (gpt-3.5-turbo)\n"
            "/yandex - Yandex GPT (yandexgpt-lite)\n"
            "/deepseek - DeepSeek (deepseek-chat)\n"
            "/model - Показать текущую выбранную модель\n\n"
            "По умолчанию используется OpenAI GPT для новых пользователей.\n"
            "Выбор модели сохраняется между сессиями.\n\n"
            "💾 Управление сессиями:\n"
            "/session_info - Информация о текущей сессии\n"
            "/new_session - Начать новую сессию (очистить контекст)\n"
            "/end_session - Завершить текущую сессию\n\n"
            "📊 Управление памятью:\n"
            "/memory_stats - Статистика памяти\n"
            "/clear_memory - Очистить всю историю диалога\n"
            "/export_memory - Экспорт истории в файл (text/json/csv)\n\n"
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
            "🛠 MCP (Model Context Protocol):\n"
            "/mcp_tools - Получить список доступных MCP инструментов\n\n"
            "MCP позволяет боту подключаться к внешним инструментам.\n"
            "Доступные серверы:\n"
            "• Filesystem - работа с файловой системой (чтение, запись, навигация)\n"
            "• GitHub - получение информации о пользователях и репозиториях\n\n"
            "💡 Как работают сессии:\n"
            "• Сессия автоматически создается при первом сообщении\n"
            "• Бот помнит последние 10 сообщений из текущей сессии\n"
            "• Используйте /new_session для начала нового диалога\n"
            "• Используйте /end_session для сброса контекста\n\n"
            "⚠️ Примечание: Я не могу выполнять команды, искать в интернете "
            "или обрабатывать файлы. Только текстовые ответы!"
        )
        await update.message.reply_text(help_message)
        logger.info(f"Пользователь {update.effective_user.id} запросил справку")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /help - интеллектуальная помощь по проекту.

        Использует систему subagents для ответов на вопросы о документации
        и состоянии репозитория.

        Использование:
            /help <вопрос> - задать вопрос
            /help - показать примеры использования
        """
        user_id = update.effective_user.id

        # Проверка rate limit (только для запросов с вопросами, не для /help без аргументов)
        if context.args and not self.help_rate_limiter.is_allowed(user_id):
            wait_time = self.help_rate_limiter.get_wait_time(user_id)
            rate_limit_message = (
                "⏱️ **Превышен лимит запросов**\n\n"
                f"Вы превысили лимит запросов к команде /help.\n"
                f"Пожалуйста, подождите {wait_time} секунд перед следующим запросом.\n\n"
                f"_Лимит: {self.help_rate_limiter.max_requests} запросов в {self.help_rate_limiter.time_window} секунд_"
            )
            await update.message.reply_text(rate_limit_message)
            logger.warning(f"Rate limit exceeded for user {user_id}, wait time: {wait_time}s")
            return

        # Получаем вопрос из аргументов команды
        if context.args:
            query = " ".join(context.args)
        else:
            # Показываем примеры использования
            examples_message = (
                "🤖 **Интеллектуальная помощь по проекту**\n\n"
                "Используйте команду `/help` с вопросом для получения информации:\n\n"
                "**Примеры:**\n"
                "• `/help как использовать RAG`\n"
                "• `/help как настроить бота`\n"
                "• `/help покажи примеры кода для агентов`\n"
                "• `/help покажи текущую ветку`\n"
                "• `/help покажи последние коммиты`\n"  
                "• `/help какой статус репозитория`\n"
                "• `/help покажи измененные файлы`\n\n"
                "**Я могу помочь с:**\n"
                "📚 Документацией проекта\n"
                "💻 Примерами кода\n"
                "🔧 Статусом репозитория\n"
                "📝 Историей коммитов\n"
                "🌿 Информацией о ветках\n\n"
                "Просто задайте вопрос после команды!"
            )
            await update.message.reply_text(examples_message)
            return

        logger.info(f"Пользователь {user_id} запросил помощь: '{query}'")

        # Проверяем доступность HelpCommandAgent
        if not hasattr(self, 'help_agent') or self.help_agent is None:
            error_message = (
                "⚠️ Система интеллектуальной помощи недоступна.\n\n"
                "Возможные причины:\n"
                "• Система subagents не инициализирована\n"
                "• Отсутствуют необходимые компоненты\n\n"
                "Используйте `/info` для получения справки по боту."
            )
            await update.message.reply_text(error_message)
            logger.error(f"HelpCommandAgent недоступен для пользователя {user_id}")
            return

        # Отправка индикатора набора текста
        await update.message.chat.send_action("typing")

        try:
            # Формируем задачу для HelpCommandAgent
            task = {
                "action": "answer_question",
                "params": {
                    "query": query
                },
                "context": {
                    "user_id": user_id,
                    "chat_id": update.effective_chat.id
                }
            }

            # Выполняем задачу через HelpCommandAgent
            result = await self.help_agent.execute(task)

            # Получаем ответ
            answer = result.get("answer", "Не удалось получить ответ.")
            sources = result.get("sources", [])
            agents_used = result.get("agents_used", [])

            # Форматируем ответ
            response_parts = [answer]

            # Добавляем информацию об использованных агентах (если включено в конфиге)
            if agents_used and len(agents_used) > 0:
                agents_str = ", ".join(agents_used)
                response_parts.append(f"\n\n_Использованы агенты: {agents_str}_")

            response = "\n".join(response_parts)

            # Отправляем ответ пользователю
            # Telegram ограничивает длину сообщения до 4096 символов
            if len(response) > 4000:
                # Разбиваем на части
                parts = self._split_long_message(response, 4000)
                for part in parts:
                    await update.message.reply_text(part)
                    await asyncio.sleep(0.5)
            else:
                await update.message.reply_text(response)

            logger.info(f"Ответ отправлен пользователю {user_id}")

        except Exception as e:
            logger.error(f"Ошибка при обработке /help для пользователя {user_id}: {e}", exc_info=True)
            error_message = (
                "❌ Произошла ошибка при обработке вашего вопроса.\n\n"
                f"Ошибка: {str(e)}\n\n"
                "Попробуйте:\n"
                "• Переформулировать вопрос\n"
                "• Использовать `/info` для справки\n"
                "• Обратиться к администратору"
            )
            await update.message.reply_text(error_message)

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
            update: Объект обновления Telegram
            context: Контекст выполнения
        """
        user_message = update.message.text
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

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

        # Получение или создание активной сессии
        session_id = self.memory.get_active_session(user_id, chat_id)
        if not session_id:
            session_id = self.memory.create_session(user_id, chat_id)
            logger.info(f"Создана новая сессия {session_id} для пользователя {user_id}")

        # Сохранение сообщения пользователя в БД
        start_time = time.time()
        try:
            self.memory.save_message(user_id, chat_id, user_message, "user", session_id)
            logger.debug(f"Сообщение пользователя {user_id} сохранено в БД")
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения пользователя: {e}")

        # Получение истории диалога для контекста (только сообщения из текущей сессии)
        conversation_history = self.memory.get_conversation_history(
            user_id, chat_id, limit=10, session_id=session_id
        )

        # Исключаем текущее сообщение из истории (оно ещё не сохранено)
        # История содержит предыдущие сообщения сессии
        logger.info(f"Загружено {len(conversation_history)} сообщений из истории сессии {session_id}")

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

        # Получаем выбранный провайдер для пользователя
        selected_provider = self.user_settings.get_provider(user_id)
        logger.info(f"Выбранный провайдер для пользователя {user_id}: {selected_provider}")

        # Выбор провайдера и отправка запроса
        rag_sources = []  # Список источников RAG

        if selected_provider == "openai" and self.openai_provider:
            provider = self.openai_provider
            response = await provider.generate_response(
                user_message, system_prompt, conversation_history
            )
        elif selected_provider == "deepseek" and self.deepseek_provider:
            provider = self.deepseek_provider
            # Для DeepSeek используем метод с источниками RAG
            response, rag_sources = await provider.generate_response_with_sources(
                user_message, system_prompt, conversation_history
            )
        else:
            # Fallback на Yandex если выбранный провайдер недоступен
            if selected_provider == "openai" and not self.openai_provider:
                logger.warning(
                    f"OpenAI выбран для пользователя {user_id}, но недоступен. "
                    f"Используется Yandex GPT"
                )
                self.user_settings.set_provider(user_id, "yandex")
            elif selected_provider == "deepseek" and not self.deepseek_provider:
                logger.warning(
                    f"DeepSeek выбран для пользователя {user_id}, но недоступен. "
                    f"Используется Yandex GPT"
                )
                self.user_settings.set_provider(user_id, "yandex")

            provider = self.yandex_provider
            response = await provider.generate_response(
                user_message, system_prompt, conversation_history
            )

        # Логирование действия агента
        execution_time = int((time.time() - start_time) * 1000)
        try:
            self.memory.save_action(
                user_id=user_id,
                chat_id=chat_id,
                action_type="gpt_request",
                description=f"Запрос к {selected_provider.upper()} GPT API",
                input_data={
                    "message": user_message[:100],
                    "mode": mode,
                    "provider": selected_provider
                },
                output_data={"response_received": response is not None},
                execution_time=execution_time
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения действия агента: {e}")

        if not response:
            # Ошибка получения ответа от API
            provider_names = {
                "openai": "OpenAI",
                "yandex": "Yandex GPT",
                "deepseek": "DeepSeek"
            }
            provider_name = provider_names.get(selected_provider, "LLM")

            error_message = (
                f"⚠️ Произошла ошибка при обращении к {provider_name}\n\n"
                f"Попробуйте позже или переключитесь на другой провайдер:\n"
                f"/openai - OpenAI GPT\n"
                f"/yandex - Yandex GPT\n"
                f"/deepseek - DeepSeek"
            )
            await update.message.reply_text(error_message)
            logger.error(f"Не удалось получить ответ от {provider_name} для пользователя {user_id}")
            return

        # Сохранение ответа ассистента в БД
        try:
            self.memory.save_message(user_id, chat_id, response, "assistant", session_id)
            logger.debug(f"Ответ ассистента для пользователя {user_id} сохранен в БД")
        except Exception as e:
            logger.error(f"Ошибка сохранения ответа ассистента: {e}")

        # Форматирование ответа в зависимости от режима
        try:
            if mode == "text":
                formatted_response = self.format_manager.format_text_response(response)

                # Добавляем информацию об источниках RAG только в текстовом режиме
                # и только если используется DeepSeek
                if rag_sources and selected_provider == "deepseek":
                    # Используем inline кнопки если доступны
                    if hasattr(self.rag_manager, 'enable_clickable_links') and self.rag_manager.enable_clickable_links and self.document_handler:
                        sources_text, inline_keyboard = self.rag_manager.format_sources_with_telegram_buttons(
                            rag_sources, 
                            title="📚 **Источники:**"
                        )
                        formatted_response += sources_text
                        
                        # Отправляем ответ с кнопками отдельно
                        await update.message.reply_text(formatted_response, reply_markup=inline_keyboard)
                        logger.info(f"Отправлен ответ с inline кнопками пользователю {user_id}")
                        return  # Выходим чтобы не отправлять второй раз
                    else:
                        sources_info = self.rag_manager.format_sources_info(rag_sources)
                        formatted_response += sources_info

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

    async def memory_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /memory_stats - показать статистику памяти."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        logger.info(f"Пользователь {user_id} запросил статистику памяти")

        try:
            # Получаем персональную статистику пользователя
            stats = self.memory.get_statistics(user_id=user_id)

            message = (
                "📊 Статистика вашей памяти:\n\n"
                f"💬 Сообщений: {stats.get('messages_count', 0)}\n"
                f"📋 Промежуточных результатов: {stats.get('intermediate_results_count', 0)}\n"
                f"⚡ Действий агента: {stats.get('actions_count', 0)}\n"
                f"🧠 Фактов в базе знаний: {stats.get('knowledge_count', 0)}\n"
                f"🔄 Активных сессий: {stats.get('active_sessions', 0)}\n\n"
                "Используйте /clear_memory для очистки истории\n"
                "Используйте /export_memory для экспорта данных"
            )

            await update.message.reply_text(message)

        except Exception as e:
            logger.error(f"Ошибка при получении статистики для пользователя {user_id}: {e}")
            error_message = (
                "❌ Ошибка получения статистики\n\n"
                "Произошла ошибка при обращении к базе данных."
            )
            await update.message.reply_text(error_message)

    async def clear_memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /clear_memory - очистить историю диалога."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        logger.info(f"Пользователь {user_id} запросил очистку памяти")

        # Проверяем, есть ли подтверждение
        if context.args and len(context.args) > 0 and context.args[0].lower() == 'confirm':
            try:
                # Выполняем очистку
                success = self.memory.clear_user_history(user_id, chat_id)

                if success:
                    # Завершаем активную сессию
                    active_session = self.memory.get_active_session(user_id, chat_id)
                    if active_session:
                        self.memory.end_session(active_session)

                    message = (
                        "✅ История диалога успешно очищена!\n\n"
                        "Все ваши сообщения и ответы ассистента были удалены из базы данных.\n"
                        "Вы можете начать новый диалог."
                    )
                    logger.info(f"История очищена для пользователя {user_id}")
                else:
                    message = "❌ Ошибка при очистке истории. Попробуйте позже."

                await update.message.reply_text(message)

            except Exception as e:
                logger.error(f"Ошибка при очистке истории для пользователя {user_id}: {e}")
                error_message = (
                    "❌ Ошибка очистки памяти\n\n"
                    "Произошла ошибка при обращении к базе данных."
                )
                await update.message.reply_text(error_message)

        else:
            # Показываем предупреждение с запросом подтверждения
            warning_message = (
                "⚠️ Вы уверены, что хотите очистить историю диалога?\n\n"
                "Это действие удалит:\n"
                "• Все сообщения в текущем чате\n"
                "• Историю диалога с ассистентом\n\n"
                "Для подтверждения используйте команду:\n"
                "/clear_memory confirm"
            )
            await update.message.reply_text(warning_message)

    async def export_memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /export_memory - экспорт истории диалога."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        logger.info(f"Пользователь {user_id} запросил экспорт памяти")

        # Определяем формат экспорта (по умолчанию text)
        export_format = 'text'
        if context.args and len(context.args) > 0:
            requested_format = context.args[0].lower()
            if requested_format in ['json', 'text', 'csv']:
                export_format = requested_format

        try:
            # Экспортируем историю
            exported_data = self.memory.export_conversation_history(user_id, chat_id, format=export_format)

            if not exported_data:
                message = (
                    "📭 История диалога пуста\n\n"
                    "У вас пока нет сохраненных сообщений."
                )
                await update.message.reply_text(message)
                return

            # Проверяем размер данных
            if len(exported_data) > 4000:
                # Telegram ограничивает размер сообщения, отправляем как файл
                from io import BytesIO

                file_extension = export_format
                filename = f"chat_history_{user_id}_{chat_id}.{file_extension}"

                file_data = BytesIO(exported_data.encode('utf-8'))
                file_data.name = filename

                await update.message.reply_document(
                    document=file_data,
                    filename=filename,
                    caption=f"📄 Экспорт истории диалога ({export_format.upper()})"
                )
                logger.info(f"Экспорт отправлен файлом для пользователя {user_id}, формат: {export_format}")

            else:
                # Отправляем как текстовое сообщение
                if export_format == 'json':
                    message = f"```json\n{exported_data}\n```"
                elif export_format == 'csv':
                    message = f"```csv\n{exported_data}\n```"
                else:
                    message = f"📝 История диалога:\n\n{exported_data}"

                await update.message.reply_text(message)
                logger.info(f"Экспорт отправлен сообщением для пользователя {user_id}, формат: {export_format}")

        except Exception as e:
            logger.error(f"Ошибка при экспорте истории для пользователя {user_id}: {e}")
            error_message = (
                "❌ Ошибка экспорта данных\n\n"
                "Произошла ошибка при формировании экспорта.\n"
                f"Попробуйте другой формат: /export_memory [text|json|csv]"
            )
            await update.message.reply_text(error_message)

    async def new_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /new_session - начать новую сессию диалога."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        logger.info(f"Пользователь {user_id} запросил создание новой сессии")

        try:
            # Завершаем старую активную сессию, если есть
            old_session_id = self.memory.get_active_session(user_id, chat_id)
            if old_session_id:
                self.memory.end_session(old_session_id)
                logger.info(f"Завершена старая сессия {old_session_id}")

            # Создаём новую сессию
            new_session_id = self.memory.create_session(user_id, chat_id)

            message = (
                "🆕 Новая сессия создана!\n\n"
                f"ID сессии: {new_session_id[:8]}...\n\n"
                "Теперь бот будет помнить контекст разговора в рамках этой сессии.\n"
                "Используйте /end_session для завершения текущей сессии.\n"
                "Используйте /session_info для просмотра информации о сессии."
            )

            await update.message.reply_text(message)
            logger.info(f"Создана новая сессия {new_session_id} для пользователя {user_id}")

        except Exception as e:
            logger.error(f"Ошибка при создании новой сессии для пользователя {user_id}: {e}")
            error_message = (
                "❌ Ошибка создания сессии\n\n"
                "Произошла ошибка при создании новой сессии."
            )
            await update.message.reply_text(error_message)

    async def end_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /end_session - завершить текущую сессию."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        logger.info(f"Пользователь {user_id} запросил завершение сессии")

        try:
            # Получаем активную сессию
            session_id = self.memory.get_active_session(user_id, chat_id)

            if not session_id:
                message = (
                    "ℹ️ Нет активной сессии\n\n"
                    "У вас нет активной сессии для завершения.\n"
                    "Используйте /new_session для создания новой сессии."
                )
                await update.message.reply_text(message)
                return

            # Получаем количество сообщений в сессии
            history = self.memory.get_conversation_history(
                user_id, chat_id, limit=1000, session_id=session_id
            )
            message_count = len(history)

            # Завершаем сессию
            success = self.memory.end_session(session_id)

            if success:
                message = (
                    "✅ Сессия завершена!\n\n"
                    f"ID сессии: {session_id[:8]}...\n"
                    f"Сообщений в сессии: {message_count}\n\n"
                    "Контекст текущего диалога очищен.\n"
                    "При следующем сообщении автоматически создастся новая сессия."
                )
                logger.info(f"Завершена сессия {session_id} для пользователя {user_id}")
            else:
                message = "❌ Ошибка при завершении сессии. Попробуйте позже."

            await update.message.reply_text(message)

        except Exception as e:
            logger.error(f"Ошибка при завершении сессии для пользователя {user_id}: {e}")
            error_message = (
                "❌ Ошибка завершения сессии\n\n"
                "Произошла ошибка при обращении к базе данных."
            )
            await update.message.reply_text(error_message)

    async def session_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /session_info - информация о текущей сессии."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        logger.info(f"Пользователь {user_id} запросил информацию о сессии")

        try:
            # Получаем активную сессию
            session_id = self.memory.get_active_session(user_id, chat_id)

            if not session_id:
                message = (
                    "ℹ️ Нет активной сессии\n\n"
                    "У вас нет активной сессии.\n"
                    "При следующем сообщении автоматически создастся новая сессия.\n\n"
                    "Команды управления сессиями:\n"
                    "/new_session - создать новую сессию\n"
                    "/session_info - информация о сессии"
                )
                await update.message.reply_text(message)
                return

            # Получаем историю сессии
            history = self.memory.get_conversation_history(
                user_id, chat_id, limit=1000, session_id=session_id
            )

            # Подсчитываем статистику
            message_count = len(history)
            user_messages = sum(1 for msg in history if msg['message_type'] == 'user')
            assistant_messages = sum(1 for msg in history if msg['message_type'] == 'assistant')

            # Получаем временные метки
            if history:
                first_message = history[0]
                last_message = history[-1]
                started_at = first_message['timestamp']
                last_activity = last_message['timestamp']
            else:
                started_at = "Неизвестно"
                last_activity = "Неизвестно"

            message = (
                "📊 Информация о текущей сессии\n\n"
                f"🆔 ID сессии: {session_id[:16]}...\n"
                f"📅 Начало: {started_at}\n"
                f"🕐 Последняя активность: {last_activity}\n\n"
                f"💬 Всего сообщений: {message_count}\n"
                f"👤 От вас: {user_messages}\n"
                f"🤖 От ассистента: {assistant_messages}\n\n"
                "Бот использует последние 10 сообщений из этой сессии для контекста.\n\n"
                "Команды:\n"
                "/new_session - начать новую сессию\n"
                "/end_session - завершить текущую сессию"
            )

            await update.message.reply_text(message)

        except Exception as e:
            logger.error(f"Ошибка при получении информации о сессии для пользователя {user_id}: {e}")
            error_message = (
                "❌ Ошибка получения информации\n\n"
                "Произошла ошибка при обращении к базе данных."
            )
            await update.message.reply_text(error_message)

    async def mcp_tools_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /mcp_tools - получение списка всех доступных MCP инструментов.

        Подключается ко всем доступным MCP серверам и выводит список инструментов
        только от успешно подключенных серверов.
        """
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запросил список MCP инструментов")

        # Отправка сообщения о начале загрузки
        loading_message = await update.message.reply_text(
            "🔄 Получаю список доступных MCP инструментов...\n"
            "Проверяю доступные серверы..."
        )

        try:
            # Получение конфигураций всех MCP серверов
            mcp_configs = get_all_mcp_configs()

            if not mcp_configs:
                error_message = (
                    "❌ Нет доступных MCP серверов\n\n"
                    "Не найдено ни одного MCP сервера для подключения.\n"
                    "Проверьте наличие файлов серверов в директории mcp_server/"
                )
                await loading_message.edit_text(error_message)
                return

            # Словарь для хранения результатов: {server_name: [tools]}
            server_tools = {}
            failed_servers = []

            # Пытаемся подключиться к каждому серверу
            for config in mcp_configs:
                server_name = config.get("name", "unknown")
                logger.info(f"Попытка подключения к MCP серверу: {server_name}")

                try:
                    # Создание MCP клиента
                    mcp_client = MCPClient(config)

                    # Подключение к серверу с таймаутом
                    connected = await asyncio.wait_for(
                        mcp_client.connect(),
                        timeout=10.0
                    )

                    if not connected:
                        logger.warning(f"Не удалось подключиться к серверу {server_name}")
                        failed_servers.append(server_name)
                        continue

                    # Получение списка инструментов
                    tools = await mcp_client.list_tools()

                    # Закрытие соединения
                    await mcp_client.disconnect()

                    if tools:
                        server_tools[server_name] = tools
                        logger.info(f"Получено {len(tools)} инструментов от сервера {server_name}")
                    else:
                        logger.warning(f"Сервер {server_name} не вернул инструменты")
                        failed_servers.append(server_name)

                except asyncio.TimeoutError:
                    logger.warning(f"Таймаут подключения к серверу {server_name}")
                    failed_servers.append(server_name)
                except Exception as e:
                    logger.error(f"Ошибка при работе с сервером {server_name}: {e}")
                    failed_servers.append(server_name)

            # Проверка, есть ли хотя бы один успешный сервер
            if not server_tools:
                error_message = (
                    "❌ Не удалось подключиться ни к одному MCP серверу\n\n"
                    f"Проверенные серверы: {', '.join(failed_servers)}\n\n"
                    "Возможные причины:\n"
                    "• Серверы не запущены\n"
                    "• Ошибка в конфигурации\n"
                    "• Отсутствуют зависимости (fastmcp, httpx)\n\n"
                    "Проверьте логи для подробностей."
                )
                await loading_message.edit_text(error_message)
                return

            # Формирование ответа
            response = "🛠 <b>Доступные MCP инструменты:</b>\n\n"

            total_tools = 0
            for server_name, tools in server_tools.items():
                response += f"📦 <b>Сервер: {server_name}</b>\n"
                response += f"Количество инструментов: {len(tools)}\n\n"

                for idx, tool in enumerate(tools, 1):
                    response += f"  {idx}. <b>{tool['name']}</b>\n"
                    response += f"     📝 {tool['description']}\n"

                    # Извлечение параметров из inputSchema
                    schema = tool.get('inputSchema', {})
                    if isinstance(schema, dict):
                        properties = schema.get('properties', {})
                        if properties:
                            params = list(properties.keys())
                            response += f"     ⚙️ Параметры: {', '.join(params)}\n"

                    response += "\n"

                total_tools += len(tools)

            # Добавление информации о недоступных серверах
            if failed_servers:
                response += f"⚠️ <b>Недоступные серверы:</b> {', '.join(failed_servers)}\n\n"

            response += f"📊 <b>Итого:</b>\n"
            response += f"✅ Доступных серверов: {len(server_tools)}\n"
            response += f"🔧 Всего инструментов: {total_tools}"

            # Проверка длины сообщения (Telegram ограничение)
            if len(response) > 4096:
                # Разбиваем на части
                parts = self._split_long_message(response, 4096)
                await loading_message.delete()
                for part in parts:
                    await update.message.reply_text(part, parse_mode="HTML")
                    await asyncio.sleep(0.5)
            else:
                # Отправка ответа пользователю
                await loading_message.edit_text(response, parse_mode="HTML")

            logger.info(
                f"Отправлен список инструментов пользователю {user_id}: "
                f"{len(server_tools)} серверов, {total_tools} инструментов"
            )

        except ImportError as e:
            logger.error(f"Ошибка импорта MCP библиотеки: {e}")
            error_message = (
                "❌ MCP библиотека не установлена\n\n"
                "Для использования MCP функций необходимо установить библиотеку:\n"
                "<code>pip install mcp fastmcp</code>\n\n"
                "После установки перезапустите бота."
            )
            await loading_message.edit_text(error_message, parse_mode="HTML")

        except Exception as e:
            logger.error(
                f"Ошибка при получении списка MCP инструментов для пользователя {user_id}: {e}",
                exc_info=True
            )
            error_message = (
                f"❌ Ошибка при получении списка инструментов\n\n"
                f"Произошла непредвиденная ошибка:\n"
                f"<code>{str(e)}</code>\n\n"
                f"Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            await loading_message.edit_text(error_message, parse_mode="HTML")

    async def openai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /openai - переключение на OpenAI GPT."""
        user_id = update.effective_user.id

        # Проверяем доступность OpenAI провайдера
        if not self.openai_provider:
            error_message = (
                "❌ OpenAI провайдер недоступен\n\n"
                "OpenAI API ключ не был настроен при запуске бота.\n"
                "Обратитесь к администратору для настройки OPENAI_API_KEY."
            )
            await update.message.reply_text(error_message)
            logger.warning(f"Пользователь {user_id} пытался переключиться на OpenAI, но провайдер недоступен")
            return

        # Сохраняем выбор
        success = self.user_settings.set_provider(user_id, "openai")

        if success:
            message = (
                "✅ Выбрана модель OpenAI GPT\n\n"
                "Теперь я буду использовать OpenAI для генерации ответов.\n\n"
                "Используемая модель: gpt-3.5-turbo\n"
                "Используйте /yandex для переключения на Yandex GPT\n"
                "Используйте /model для просмотра текущей модели"
            )
            logger.info(f"Пользователь {user_id} переключился на провайдер OpenAI")
        else:
            message = "❌ Ошибка при сохранении настроек. Попробуйте позже."
            logger.error(f"Ошибка сохранения провайдера OpenAI для пользователя {user_id}")

        await update.message.reply_text(message)

    async def yandex_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /yandex - переключение на Yandex GPT."""
        user_id = update.effective_user.id

        # Сохраняем выбор
        success = self.user_settings.set_provider(user_id, "yandex")

        if success:
            message = (
                "✅ Выбрана модель Yandex GPT\n\n"
                "Теперь я буду использовать Yandex для генерации ответов.\n\n"
                "Используемая модель: yandexgpt-lite\n"
                "Используйте /openai для переключения на OpenAI GPT\n"
                "Используйте /model для просмотра текущей модели"
            )
            logger.info(f"Пользователь {user_id} переключился на провайдер Yandex")
        else:
            message = "❌ Ошибка при сохранении настроек. Попробуйте позже."
            logger.error(f"Ошибка сохранения провайдера Yandex для пользователя {user_id}")

        await update.message.reply_text(message)

    async def deepseek_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /deepseek - переключение на DeepSeek."""
        user_id = update.effective_user.id

        # Проверяем доступность DeepSeek провайдера
        if not self.deepseek_provider:
            error_message = (
                "❌ DeepSeek провайдер недоступен\n\n"
                "DeepSeek API ключ не был настроен при запуске бота.\n"
                "Обратитесь к администратору для настройки DEEPSEEK_API_KEY."
            )
            await update.message.reply_text(error_message)
            logger.warning(f"Пользователь {user_id} пытался переключиться на DeepSeek, но провайдер недоступен")
            return

        # Сохраняем выбор
        success = self.user_settings.set_provider(user_id, "deepseek")

        if success:
            message = (
                "✅ Выбрана модель DeepSeek\n\n"
                "Теперь я буду использовать DeepSeek для генерации ответов.\n\n"
                "Используемая модель: deepseek-chat\n"
                "Используйте /openai для переключения на OpenAI GPT\n"
                "Используйте /yandex для переключения на Yandex GPT\n"
                "Используйте /model для просмотра текущей модели"
            )
            logger.info(f"Пользователь {user_id} переключился на провайдер DeepSeek")
        else:
            message = "❌ Ошибка при сохранении настроек. Попробуйте позже."
            logger.error(f"Ошибка сохранения провайдера DeepSeek для пользователя {user_id}")

        await update.message.reply_text(message)

    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /model - показать текущую выбранную модель."""
        user_id = update.effective_user.id

        # Получаем текущий провайдер
        provider = self.user_settings.get_provider(user_id)

        if provider == "openai":
            if self.openai_provider:
                message = (
                    "🤖 Текущая модель: OpenAI GPT\n\n"
                    "Модель: gpt-3.5-turbo\n"
                    "Провайдер: OpenAI\n\n"
                    "Альтернативы:\n"
                    "/yandex - Yandex GPT\n"
                    "/deepseek - DeepSeek"
                )
            else:
                message = (
                    "⚠️ Выбрана модель OpenAI GPT, но провайдер недоступен\n\n"
                    "Переключаюсь на Yandex GPT..."
                )
                self.user_settings.set_provider(user_id, "yandex")
        elif provider == "deepseek":
            if self.deepseek_provider:
                message = (
                    "🤖 Текущая модель: DeepSeek\n\n"
                    "Модель: deepseek-chat\n"
                    "Провайдер: DeepSeek\n\n"
                    "Альтернативы:\n"
                    "/openai - OpenAI GPT\n"
                    "/yandex - Yandex GPT\n"
                )
            else:
                message = (
                    "⚠️ Выбрана модель DeepSeek, но провайдер недоступен\n\n"
                    "Переключаюсь на Yandex GPT..."
                )
                self.user_settings.set_provider(user_id, "yandex")
        else:  # yandex
            message = (
                "🤖 Текущая модель: Yandex GPT\n\n"
                "Модель: yandexgpt-lite\n"
                "Провайдер: Yandex Cloud\n\n"
                "Альтернативы:\n"
                "/openai - OpenAI GPT\n"
                "/deepseek - DeepSeek"
            )

        await update.message.reply_text(message)
        logger.info(f"Пользователь {user_id} проверил текущую модель: {provider}")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик callback запросов от inline кнопок.
        
        Args:
            update: Объект обновления Telegram
            context: Контекст выполнения
        """
        query = update.callback_query
        user_id = query.from_user.id
        
        logger.info(f"Получен callback запрос от пользователя {user_id}: {query.data}")
        
        try:
            # Показываем индикатор обработки
            await query.answer("Обрабатываю запрос...")
            
            # Парсим данные callback
            callback_data = query.data
            
            if callback_data.startswith("doc:"):
                # Обработка нажатий на inline кнопки документов
                if self.rag_manager and self.rag_manager.document_handler:
                    try:
                        await self.rag_manager.document_handler.handle_document_callback(update, context)
                        logger.info(f"Обработано нажатие на кнопку документа пользователем {user_id}")
                    except Exception as e:
                        logger.error(f"Ошибка обработки кнопки документа: {e}")
                        await query.message.reply_text(
                            "❌ Ошибка при открытии документа. Попробуйте позже."
                        )
                else:
                    error_message = "❌ Обработчик документов недоступен"
                    await query.message.reply_text(error_message)
                    logger.warning(f"Document handler недоступен для пользователя {user_id}")
            else:
                # Неизвестный callback
                await query.message.reply_text("❌ Неизвестная команда")
                logger.warning(f"Получен неизвестный callback: {callback_data}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки callback запроса: {e}")
            await query.message.reply_text("❌ Ошибка обработки запроса")

    def _initialize_subagents(self) -> None:
        """
        Инициализация системы subagents (Tools, Agents, Orchestrator).

        Создает и настраивает всю архитектуру subagents для команды /help:
        - Tool Manager и Tools
        - DocsAgent и GitAgent
        - AgentOrchestrator
        - HelpCommandAgent
        """
        logger.info("Инициализация системы subagents...")

        # 1. Создаем Tool Manager
        tool_manager = ToolManager()
        logger.info("ToolManager создан")

        # 2. Регистрируем Tools
        if self.rag_manager:
            # DocumentSearchTool для поиска по документации
            doc_search_tool = DocumentSearchTool(self.rag_manager)
            tool_manager.register_tool(doc_search_tool)
            logger.info("DocumentSearchTool зарегистрирован")
        else:
            logger.warning("RAG Manager недоступен, DocumentSearchTool не будет зарегистрирован")

        # Здесь можно добавить другие Tools (MCPTool для GitHub и т.д.)
        # Пока DocumentSearchTool достаточно для базовой функциональности

        # 3. Создаем AgentOrchestrator
        orchestrator = AgentOrchestrator(tool_manager=tool_manager)
        logger.info("AgentOrchestrator создан")

        # 4. Создаем и регистрируем DocsAgent
        try:
            docs_agent = DocsAgent(
                tool_manager=tool_manager,
                name="docs_agent",
                enabled=True
            )
            orchestrator.register_agent(docs_agent)
            logger.info("DocsAgent создан и зарегистрирован")
        except Exception as e:
            logger.error(f"Ошибка создания DocsAgent: {e}")
            raise

        # 5. Создаем и регистрируем GitAgent
        try:
            git_agent = GitAgent(
                tool_manager=tool_manager,
                repo_path=".",
                name="git_agent",
                enabled=True
            )
            orchestrator.register_agent(git_agent)
            logger.info("GitAgent создан и зарегистрирован")
        except Exception as e:
            logger.warning(f"Не удалось создать GitAgent: {e}")
            # GitAgent не критичен, продолжаем без него

        # 6. Создаем HelpCommandAgent
        try:
            self.help_agent = HelpCommandAgent(
                orchestrator=orchestrator,
                name="help_command_agent",
                enabled=True
            )
            logger.info("HelpCommandAgent создан и готов к работе")
        except Exception as e:
            logger.error(f"Ошибка создания HelpCommandAgent: {e}")
            raise

        logger.info("Система subagents успешно инициализирована")

    def _initialize_scheduler(self) -> None:
        """
        Инициализация планировщика фоновых задач.

        Создает TaskScheduler и регистрирует встроенные задачи:
        - ReindexDocumentsTask - переиндексация документов каждые 24 часа
        - HealthCheckTask - проверка здоровья системы каждые 5 минут
        """
        logger.info("Инициализация планировщика задач...")

        # Создаем планировщик с интервалом проверки 60 секунд
        self.scheduler = TaskScheduler(check_interval=60)
        logger.info("TaskScheduler создан")

        # Регистрируем задачу переиндексации документов
        if self.rag_manager:
            from datetime import timedelta

            reindex_task = ReindexDocumentsTask(
                rag_manager=self.rag_manager,
                docs_path="docs/",
                interval=timedelta(hours=24)
            )
            self.scheduler.register_task(reindex_task)
            logger.info("ReindexDocumentsTask зарегистрирована (интервал: 24 часа)")
        else:
            logger.warning("RAG Manager недоступен, ReindexDocumentsTask не будет зарегистрирована")

        # Регистрируем задачу проверки здоровья системы
        try:
            from datetime import timedelta

            health_check_task = HealthCheckTask(
                interval=timedelta(minutes=5)
            )
            self.scheduler.register_task(health_check_task)
            logger.info("HealthCheckTask зарегистрирована (интервал: 5 минут)")
        except Exception as e:
            logger.warning(f"Не удалось зарегистрировать HealthCheckTask: {e}")

        logger.info("Планировщик задач успешно инициализирован")

    async def _post_init(self, application: Application) -> None:
        """
        Callback, вызываемый после инициализации приложения.
        Запускает планировщик задач в фоновом режиме.

        Args:
            application: Экземпляр Application
        """
        if self.scheduler:
            try:
                logger.info("Запуск планировщика задач в фоновом режиме...")
                await self.scheduler.start()
                logger.info("Планировщик задач успешно запущен")
            except Exception as e:
                logger.error(f"Ошибка при запуске планировщика задач: {e}", exc_info=True)
        else:
            logger.warning("Планировщик задач не инициализирован, пропускаем запуск")

    async def _post_shutdown(self, application: Application) -> None:
        """
        Callback, вызываемый при завершении работы приложения.
        Останавливает планировщик задач.

        Args:
            application: Экземпляр Application
        """
        if self.scheduler:
            try:
                logger.info("Остановка планировщика задач...")
                await self.scheduler.stop()
                logger.info("Планировщик задач успешно остановлен")
            except Exception as e:
                logger.error(f"Ошибка при остановке планировщика задач: {e}", exc_info=True)
        else:
            logger.debug("Планировщик задач не был запущен")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок бота."""
        logger.error(f"Произошла ошибка: {context.error}", exc_info=True)
        
        if update and hasattr(update, 'message') and update.message:
            try:
                await update.message.reply_text(
                    "❌ Произошла внутренняя ошибка. Попробуйте позже."
                )
            except Exception:
                pass  # Игнорируем ошибки при отправке сообщения об ошибке


def main() -> None:
    """Главная функция для запуска бота."""
    # Проверка переменных окружения
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    yandex_api_key = os.getenv("YANDEX_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

    if not telegram_token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения")
        sys.exit(1)

    if not yandex_api_key:
        logger.error("YANDEX_API_KEY не найден в переменных окружения")
        sys.exit(1)

    # Создание и запуск бота
    try:
        bot = TelegramBot(
            telegram_token=telegram_token,
            yandex_api_key=yandex_api_key,
            openai_api_key=openai_api_key,
            deepseek_api_key=deepseek_api_key
        )

        logger.info("Запуск Telegram бота...")
        bot.application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)


# Создаем глобальный экземпляр приложения для импорта
app = None

if __name__ == "__main__":
    main()
