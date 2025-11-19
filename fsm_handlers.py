"""
FSM обработчики для интерактивной настройки ассистентов.

Используется ConversationHandler для создания диалоговых сценариев.
"""

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

logger = logging.getLogger(__name__)

# Состояния FSM для создания ассистента
CHAT_ID, INTERVAL_TYPE, INTERVAL_VALUE, CUSTOM_PROMPT, CONFIRM = range(5)


class AssistantCreationFSM:
    """FSM для создания ассистента с настройкой параметров."""

    def __init__(self, scheduler_manager):
        """
        Инициализация FSM обработчика.

        Args:
            scheduler_manager: Экземпляр SchedulerManager
        """
        self.scheduler_manager = scheduler_manager

    async def start_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Начало создания ассистента.

        Команда: /create_assistant
        """
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} начал создание ассистента через FSM")

        await update.message.reply_text(
            "🤖 Создание ассистента для автоматических сводок\n\n"
            "Шаг 1/4: Укажите ID или username чата\n\n"
            "Примеры:\n"
            "• @channel_name\n"
            "• @username\n"
            "• -1001234567890\n\n"
            "Отправьте /cancel для отмены"
        )

        return CHAT_ID

    async def receive_chat_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение chat_id от пользователя."""
        chat_id = update.message.text.strip()

        # Сохраняем в context
        context.user_data['chat_id'] = chat_id
        context.user_data['chat_name'] = chat_id

        logger.info(f"Пользователь {update.effective_user.id} указал chat_id: {chat_id}")

        # Создаём inline клавиатуру для выбора типа интервала
        keyboard = [
            [
                InlineKeyboardButton("⏱ Минуты", callback_data="interval_type:minute"),
                InlineKeyboardButton("🕐 Часы", callback_data="interval_type:hour")
            ],
            [
                InlineKeyboardButton("📅 Дни", callback_data="interval_type:day")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ Чат: {chat_id}\n\n"
            f"Шаг 2/4: Выберите тип интервала\n\n"
            f"Как часто создавать сводки?",
            reply_markup=reply_markup
        )

        return INTERVAL_TYPE

    async def receive_interval_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение типа интервала через inline кнопки."""
        query = update.callback_query
        await query.answer()

        # Парсим callback_data
        interval_type = query.data.split(":")[1]
        context.user_data['interval_type'] = interval_type

        logger.info(f"Пользователь {update.effective_user.id} выбрал interval_type: {interval_type}")

        # Показываем варианты значений в зависимости от типа
        if interval_type == "minute":
            keyboard = [
                [
                    InlineKeyboardButton("5 минут", callback_data="interval_value:5"),
                    InlineKeyboardButton("10 минут", callback_data="interval_value:10"),
                    InlineKeyboardButton("15 минут", callback_data="interval_value:15")
                ],
                [
                    InlineKeyboardButton("30 минут", callback_data="interval_value:30"),
                    InlineKeyboardButton("45 минут", callback_data="interval_value:45")
                ],
                [InlineKeyboardButton("✏️ Ввести своё значение", callback_data="interval_value:custom")]
            ]
            prompt_text = "Шаг 3/4: Выберите интервал в минутах"

        elif interval_type == "hour":
            keyboard = [
                [
                    InlineKeyboardButton("1 час", callback_data="interval_value:1"),
                    InlineKeyboardButton("2 часа", callback_data="interval_value:2"),
                    InlineKeyboardButton("3 часа", callback_data="interval_value:3")
                ],
                [
                    InlineKeyboardButton("6 часов", callback_data="interval_value:6"),
                    InlineKeyboardButton("12 часов", callback_data="interval_value:12")
                ],
                [InlineKeyboardButton("✏️ Ввести своё значение", callback_data="interval_value:custom")]
            ]
            prompt_text = "Шаг 3/4: Выберите интервал в часах"

        else:  # day
            keyboard = [
                [
                    InlineKeyboardButton("1 день", callback_data="interval_value:1"),
                    InlineKeyboardButton("2 дня", callback_data="interval_value:2"),
                    InlineKeyboardButton("3 дня", callback_data="interval_value:3")
                ],
                [
                    InlineKeyboardButton("7 дней", callback_data="interval_value:7")
                ],
                [InlineKeyboardButton("✏️ Ввести своё значение", callback_data="interval_value:custom")]
            ]
            prompt_text = "Шаг 3/4: Выберите интервал в днях"

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=prompt_text,
            reply_markup=reply_markup
        )

        return INTERVAL_VALUE

    async def receive_interval_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение значения интервала."""
        query = update.callback_query
        await query.answer()

        value = query.data.split(":")[1]

        if value == "custom":
            # Пользователь хочет ввести своё значение
            await query.edit_message_text(
                "✏️ Введите своё значение (целое число):"
            )
            return INTERVAL_VALUE  # Ждём текстовое сообщение

        # Сохраняем значение
        interval_value = int(value)
        context.user_data['interval_value'] = interval_value

        logger.info(f"Пользователь {update.effective_user.id} выбрал interval_value: {interval_value}")

        # Переходим к выбору промпта
        keyboard = [
            [InlineKeyboardButton("✅ Использовать стандартный", callback_data="prompt:default")],
            [InlineKeyboardButton("✏️ Ввести свой промпт", callback_data="prompt:custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        interval_type = context.user_data.get('interval_type')
        type_names = {"minute": "минут", "hour": "часов", "day": "дней"}

        await query.edit_message_text(
            f"✅ Интервал: каждые {interval_value} {type_names.get(interval_type, '')}\\n\\n"
            f"Шаг 4/4: Промпт для анализа сообщений\\n\\n"
            f"Стандартный промпт фокусируется на:\\n"
            f"• Основных темах обсуждения\\n"
            f"• Важных решениях и договоренностях\\n"
            f"• Проблемах и блокерах\\n\\n"
            f"Хотите использовать свой промпт?",
            reply_markup=reply_markup
        )

        return CUSTOM_PROMPT

    async def receive_custom_interval_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение кастомного значения интервала через текстовое сообщение."""
        try:
            interval_value = int(update.message.text.strip())

            if interval_value <= 0:
                await update.message.reply_text(
                    "❌ Значение должно быть больше 0. Попробуйте ещё раз:"
                )
                return INTERVAL_VALUE

            context.user_data['interval_value'] = interval_value
            logger.info(f"Пользователь {update.effective_user.id} ввёл кастомное interval_value: {interval_value}")

            # Переходим к выбору промпта
            keyboard = [
                [InlineKeyboardButton("✅ Использовать стандартный", callback_data="prompt:default")],
                [InlineKeyboardButton("✏️ Ввести свой промпт", callback_data="prompt:custom")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            interval_type = context.user_data.get('interval_type')
            type_names = {"minute": "минут", "hour": "часов", "day": "дней"}

            await update.message.reply_text(
                f"✅ Интервал: каждые {interval_value} {type_names.get(interval_type, '')}\\n\\n"
                f"Шаг 4/4: Промпт для анализа сообщений\\n\\n"
                f"Стандартный промпт фокусируется на:\\n"
                f"• Основных темах обсуждения\\n"
                f"• Важных решениях и договоренностях\\n"
                f"• Проблемах и блокерах\\n\\n"
                f"Хотите использовать свой промпт?",
                reply_markup=reply_markup
            )

            return CUSTOM_PROMPT

        except ValueError:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите целое число:"
            )
            return INTERVAL_VALUE

    async def receive_prompt_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение выбора промпта."""
        query = update.callback_query
        await query.answer()

        choice = query.data.split(":")[1]

        if choice == "custom":
            # Пользователь хочет ввести свой промпт
            await query.edit_message_text(
                "✏️ Введите свой промпт для анализа сообщений:\n\n"
                "Например:\n"
                "\"Сфокусируйся на технических проблемах и их решениях\"\n"
                "\"Выдели только новости о продуктах\""
            )
            context.user_data['waiting_custom_prompt'] = True
            return CUSTOM_PROMPT

        # Используем стандартный промпт
        context.user_data['custom_prompt'] = None
        logger.info(f"Пользователь {update.effective_user.id} выбрал стандартный промпт")

        # Показываем финальное подтверждение
        await self._show_confirmation(query, context)
        return CONFIRM

    async def receive_custom_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение кастомного промпта."""
        custom_prompt = update.message.text.strip()
        context.user_data['custom_prompt'] = custom_prompt

        logger.info(f"Пользователь {update.effective_user.id} ввёл кастомный промпт")

        # Показываем финальное подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Создать", callback_data="confirm:yes"),
                InlineKeyboardButton("❌ Отменить", callback_data="confirm:no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        interval_type = context.user_data.get('interval_type')
        interval_value = context.user_data.get('interval_value')
        chat_id = context.user_data.get('chat_id')
        type_names = {"minute": "минут", "hour": "часов", "day": "дней"}

        await update.message.reply_text(
            "📋 Подтверждение создания ассистента\n\n"
            f"Чат: {chat_id}\n"
            f"Интервал: каждые {interval_value} {type_names.get(interval_type, '')}\n"
            f"Промпт: кастомный\n\n"
            f"Создать ассистента?",
            reply_markup=reply_markup
        )

        return CONFIRM

    async def _show_confirmation(self, query, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показ финального подтверждения."""
        keyboard = [
            [
                InlineKeyboardButton("✅ Создать", callback_data="confirm:yes"),
                InlineKeyboardButton("❌ Отменить", callback_data="confirm:no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        interval_type = context.user_data.get('interval_type')
        interval_value = context.user_data.get('interval_value')
        chat_id = context.user_data.get('chat_id')
        type_names = {"minute": "минут", "hour": "часов", "day": "дней"}

        await query.edit_message_text(
            "📋 Подтверждение создания ассистента\n\n"
            f"Чат: {chat_id}\n"
            f"Интервал: каждые {interval_value} {type_names.get(interval_type, '')}\n"
            f"Промпт: стандартный\n\n"
            f"Создать ассистента?",
            reply_markup=reply_markup
        )

    async def confirm_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждение и создание ассистента."""
        query = update.callback_query
        await query.answer()

        choice = query.data.split(":")[1]

        if choice == "no":
            await query.edit_message_text("❌ Создание ассистента отменено")
            context.user_data.clear()
            return ConversationHandler.END

        # Получаем данные из context
        user_id = update.effective_user.id
        chat_id = context.user_data.get('chat_id')
        chat_name = context.user_data.get('chat_name')
        interval_type = context.user_data.get('interval_type')
        interval_value = context.user_data.get('interval_value')
        custom_prompt = context.user_data.get('custom_prompt')

        logger.info(
            f"Создание ассистента: user={user_id}, chat={chat_id}, "
            f"interval={interval_type}:{interval_value}, prompt={custom_prompt is not None}"
        )

        await query.edit_message_text("⏳ Создаю ассистента...")

        # Создаём ассистента через SchedulerManager
        success, message, assistant = await self.scheduler_manager.create_assistant(
            user_id=user_id,
            chat_id=chat_id,
            chat_name=chat_name,
            interval_type=interval_type,
            interval_value=interval_value,
            custom_prompt=custom_prompt
        )

        type_names = {"minute": "минут", "hour": "часов", "day": "дней"}

        if success and assistant:
            response = (
                f"✅ Ассистент для чата '{chat_name}' создан!\n\n"
                f"📊 Интервал: каждые {interval_value} {type_names.get(interval_type, '')}\n"
                f"⏰ Первый запуск: через {interval_value} {type_names.get(interval_type, '')}\n"
                f"🆔 ID: {assistant.assistant_id[:8]}...\n\n"
                f"Используйте /list_assistants для просмотра всех ассистентов"
            )
        else:
            response = f"❌ {message}"

        await update.effective_message.reply_text(response)

        # Очищаем данные
        context.user_data.clear()

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена создания ассистента."""
        await update.message.reply_text(
            "❌ Создание ассистента отменено.\n\n"
            "Используйте /create_assistant для повторной попытки."
        )
        context.user_data.clear()
        logger.info(f"Пользователь {update.effective_user.id} отменил создание ассистента")
        return ConversationHandler.END


def get_assistant_creation_handler(scheduler_manager) -> ConversationHandler:
    """
    Создание ConversationHandler для FSM создания ассистента.

    Args:
        scheduler_manager: Экземпляр SchedulerManager

    Returns:
        ConversationHandler для регистрации в Application
    """
    fsm = AssistantCreationFSM(scheduler_manager)

    return ConversationHandler(
        entry_points=[CommandHandler("create_assistant", fsm.start_creation)],
        states={
            CHAT_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fsm.receive_chat_id)
            ],
            INTERVAL_TYPE: [
                CallbackQueryHandler(fsm.receive_interval_type, pattern="^interval_type:")
            ],
            INTERVAL_VALUE: [
                CallbackQueryHandler(fsm.receive_interval_value, pattern="^interval_value:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, fsm.receive_custom_interval_value)
            ],
            CUSTOM_PROMPT: [
                CallbackQueryHandler(fsm.receive_prompt_choice, pattern="^prompt:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, fsm.receive_custom_prompt)
            ],
            CONFIRM: [
                CallbackQueryHandler(fsm.confirm_creation, pattern="^confirm:")
            ]
        },
        fallbacks=[CommandHandler("cancel", fsm.cancel)],
        name="assistant_creation",
        persistent=False
    )
