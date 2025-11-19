"""
Логика выполнения задач планировщика.

Содержит функции для:
- Выполнения задачи сбора сообщений и генерации сводки
- Взаимодействия с LLM через DeepSeek
- Отправки сводок пользователю
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from storage import Database
from providers import DeepSeekProvider
from .context import get_context

logger = logging.getLogger(__name__)


async def execute_task(assistant_id: str) -> None:
    """
    Выполнение задачи планировщика: сбор сообщений и генерация сводки.

    Args:
        assistant_id: ID ассистента

    Процесс:
        1. Получить конфигурацию ассистента из БД
        2. Запросить LLM сгенерировать сводку (LLM вызовет MCP tool get_chat_messages)
        3. Отправить сводку пользователю
        4. Обновить время последнего запуска и сохранить в историю
    """
    started_at = datetime.now()
    logger.info(f"🚀 ЗАПУСК ЗАДАЧИ: assistant_id={assistant_id}, время={started_at}")

    # Получаем объекты из глобального контекста
    context = get_context()
    database = context.database
    llm_provider = context.llm_provider
    telegram_bot_instance = context.telegram_bot

    if not all([database, llm_provider, telegram_bot_instance]):
        logger.error(f"Контекст не инициализирован для выполнения задачи {assistant_id}")
        return

    logger.info(f"Контекст получен для ассистента {assistant_id}")

    try:
        # Получаем ассистента из БД
        assistant = database.get_assistant(assistant_id)

        if not assistant:
            logger.error(f"Ассистент {assistant_id} не найден в БД")
            return

        if assistant.status != 'active':
            logger.warning(f"Ассистент {assistant_id} не активен (статус: {assistant.status})")
            return

        # Определяем период для сбора сообщений
        if assistant.last_run_at:
            from_date = assistant.last_run_at
        else:
            # Если это первый запуск, берём сообщения за последний интервал
            from_date = datetime.now() - timedelta(minutes=assistant.interval_value)

        to_date = datetime.now()

        logger.info(f"Сбор сообщений из чата {assistant.chat_name} за период {from_date} - {to_date}")

        # Формируем промпт для LLM
        system_prompt = _build_system_prompt(assistant.custom_prompt)

        user_prompt = _build_user_prompt(
            chat_id=assistant.chat_id,
            chat_name=assistant.chat_name,
            from_date=from_date,
            to_date=to_date
        )

        # Отправляем запрос к LLM
        # DeepSeek Provider автоматически вызовет MCP tool get_chat_messages
        logger.info(f"Отправка запроса к LLM для генерации сводки")

        summary = await llm_provider.generate_response(
            user_message=user_prompt,
            system_prompt=system_prompt,
            conversation_history=[]
        )

        if not summary:
            logger.error(f"LLM не вернул сводку для ассистента {assistant_id}")

            # Сохраняем ошибку в историю
            database.save_execution(
                assistant_id=assistant_id,
                started_at=started_at,
                completed_at=datetime.now(),
                status='error',
                messages_count=0,
                summary_sent=False,
                error_message="LLM не вернул сводку"
            )
            return

        # Форматируем и отправляем сводку пользователю
        formatted_summary = _format_summary(
            chat_name=assistant.chat_name,
            from_date=from_date,
            to_date=to_date,
            summary=summary,
            next_run_at=assistant.next_run_at
        )

        # Отправка сводки через Telegram бота
        try:
            await telegram_bot_instance.application.bot.send_message(
                chat_id=assistant.user_id,
                text=formatted_summary,
                parse_mode=None
            )

            logger.info(f"Сводка отправлена пользователю {assistant.user_id}")
            summary_sent = True

        except Exception as e:
            logger.error(f"Ошибка отправки сводки пользователю {assistant.user_id}: {e}")
            summary_sent = False

        # Обновляем время последнего запуска
        # Получаем актуальное время следующего запуска из планировщика
        from .context import get_context as get_scheduler_context
        scheduler_context = get_scheduler_context()
        next_run_at = None

        if scheduler_context.telegram_bot and hasattr(scheduler_context.telegram_bot, 'scheduler_manager'):
            scheduler = scheduler_context.telegram_bot.scheduler_manager.scheduler
            job_id = f"assistant_{assistant_id}"
            job = scheduler.get_job(job_id)
            if job and job.next_run_time:
                next_run_at = job.next_run_time.replace(tzinfo=None)

        database.update_last_run(
            assistant_id=assistant_id,
            last_run_at=to_date,
            next_run_at=next_run_at
        )

        # Сохраняем в историю выполнения
        completed_at = datetime.now()
        database.save_execution(
            assistant_id=assistant_id,
            started_at=started_at,
            completed_at=completed_at,
            status='success',
            messages_count=-1,  # Не знаем точное количество, LLM получил через MCP
            summary_sent=summary_sent,
            error_message=None
        )

        execution_time = (completed_at - started_at).total_seconds()
        logger.info(f"Задача для ассистента {assistant_id} выполнена за {execution_time:.2f} сек")

    except Exception as e:
        logger.error(f"Неожиданная ошибка при выполнении задачи {assistant_id}: {e}", exc_info=True)

        # Сохраняем ошибку в историю
        database.save_execution(
            assistant_id=assistant_id,
            started_at=started_at,
            completed_at=datetime.now(),
            status='error',
            messages_count=0,
            summary_sent=False,
            error_message=str(e)
        )

        # Отправляем уведомление пользователю об ошибке
        try:
            assistant = database.get_assistant(assistant_id)
            if assistant:
                error_message = (
                    f"⚠️ Не удалось собрать сводку из чата '{assistant.chat_name}'\n\n"
                    f"Причина: {str(e)}\n\n"
                    f"Следующая попытка согласно расписанию."
                )

                await telegram_bot_instance.application.bot.send_message(
                    chat_id=assistant.user_id,
                    text=error_message
                )
        except Exception as notify_error:
            logger.error(f"Не удалось отправить уведомление об ошибке: {notify_error}")


def _build_system_prompt(custom_prompt: Optional[str]) -> str:
    """
    Построение системного промпта для LLM.

    Args:
        custom_prompt: Пользовательский промпт (опционально)

    Returns:
        Системный промпт
    """
    base_prompt = (
        "Ты - ассистент для анализа сообщений из Telegram чатов.\n\n"
        "У тебя есть доступ к инструменту get_chat_messages, который позволяет "
        "получить сообщения из чата за указанный период.\n\n"
        "ВАЖНО: Пользователь УЖЕ указал все параметры. Твоя задача:\n"
        "1. НЕМЕДЛЕННО вызови инструмент get_chat_messages с параметрами из user message\n"
        "2. Проанализируй полученные сообщения\n"
        "3. Создай краткую, структурированную сводку\n\n"
        "НЕ задавай пользователю вопросы об уточнении параметров - все параметры уже переданы в user message.\n"
        "НЕ уточняй временной период - используй параметры from_date и to_date из user message.\n\n"
    )

    if custom_prompt:
        base_prompt += f"Дополнительные инструкции по анализу:\n{custom_prompt}\n\n"
    else:
        base_prompt += (
            "При создании сводки:\n"
            "- Выдели основные темы обсуждения\n"
            "- Укажи важные решения или договоренности\n"
            "- Отметь упоминания о проблемах или блокерах\n"
            "- Используй маркированные списки для структурирования\n\n"
        )

    base_prompt += (
        "Если сообщений нет или их мало, сообщи об этом коротко.\n"
        "НЕ включай в ответ технические детали вызова инструмента - "
        "только итоговую сводку для пользователя."
    )

    return base_prompt


def _build_user_prompt(
    chat_id: str,
    chat_name: str,
    from_date: datetime,
    to_date: datetime,
    limit: int = 1000
) -> str:
    """
    Построение пользовательского промпта для LLM.

    Args:
        chat_id: ID чата
        chat_name: Название чата
        from_date: Начало периода
        to_date: Конец периода
        limit: Максимальное количество сообщений (по умолчанию 1000)

    Returns:
        Пользовательский промпт
    """
    return (
        f"Создай сводку сообщений из чата '{chat_name}'.\n\n"
        f"Параметры для инструмента get_chat_messages:\n"
        f"- chat_id: {chat_id}\n"
        f"- from_date: {from_date.isoformat()}\n"
        f"- to_date: {to_date.isoformat()}\n"
        f"- limit: {limit}\n\n"
        f"Проанализируй сообщения и создай структурированную сводку."
    )


def _format_summary(
    chat_name: str,
    from_date: datetime,
    to_date: datetime,
    summary: str,
    next_run_at: Optional[datetime]
) -> str:
    """
    Форматирование сводки для отправки пользователю.

    Args:
        chat_name: Название чата
        from_date: Начало периода
        to_date: Конец периода
        summary: Текст сводки от LLM
        next_run_at: Время следующего запуска

    Returns:
        Отформатированная сводка
    """
    # Форматируем даты
    from_str = from_date.strftime("%d.%m.%Y %H:%M")
    to_str = to_date.strftime("%d.%m.%Y %H:%M")

    result = f"📊 Сводка из чата: {chat_name}\n"
    result += f"🕐 Период: {from_str} - {to_str}\n\n"
    result += summary
    result += "\n\n---\n"

    if next_run_at:
        next_str = next_run_at.strftime("%d.%m.%Y в %H:%M")
        result += f"⏰ Следующая сводка: {next_str}"

    return result


async def execute_initial_summary(
    assistant_id: str,
    message_limit: int = 10
) -> None:
    """
    Выполнение первоначальной сводки при создании ассистента.

    Получает последние N сообщений из чата и создаёт сводку.

    Args:
        assistant_id: ID ассистента
        message_limit: Количество последних сообщений (по умолчанию 100)
    """
    # Получаем объекты из глобального контекста
    context = get_context()
    database = context.database
    llm_provider = context.llm_provider
    telegram_bot_instance = context.telegram_bot

    if not all([database, llm_provider, telegram_bot_instance]):
        logger.error(f"Контекст не инициализирован для выполнения первоначальной сводки {assistant_id}")
        return

    started_at = datetime.now()
    logger.info(f"Начало выполнения первоначальной сводки для ассистента {assistant_id}")

    try:
        # Получаем ассистента из БД
        assistant = database.get_assistant(assistant_id)

        if not assistant:
            logger.error(f"Ассистент {assistant_id} не найден в БД")
            return

        # Отправляем уведомление пользователю о начале создания первоначальной сводки
        try:
            await telegram_bot_instance.application.bot.send_message(
                chat_id=assistant.user_id,
                text=f"⏳ Создаю первоначальную сводку из чата '{assistant.chat_name}'...\n"
                     f"Анализирую последние {message_limit} сообщений."
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о начале: {e}")

        # Определяем период: последние 7 дней или с начала времени
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)  # Последние 7 дней

        logger.info(f"Запрос последних {message_limit} сообщений из чата {assistant.chat_name}")

        # Формируем специальный промпт для первоначальной сводки
        system_prompt = _build_initial_summary_prompt(assistant.custom_prompt, message_limit)

        user_prompt = _build_user_prompt(
            chat_id=assistant.chat_id,
            chat_name=assistant.chat_name,
            from_date=from_date,
            to_date=to_date,
            limit=message_limit
        )

        # Отправляем запрос к LLM
        logger.info(f"Отправка запроса к LLM для первоначальной сводки")

        summary = await llm_provider.generate_response(
            user_message=user_prompt,
            system_prompt=system_prompt,
            conversation_history=[]
        )

        if not summary:
            logger.error(f"LLM не вернул первоначальную сводку для ассистента {assistant_id}")

            # Уведомляем пользователя об ошибке
            try:
                await telegram_bot_instance.application.bot.send_message(
                    chat_id=assistant.user_id,
                    text=f"❌ Не удалось создать первоначальную сводку из чата '{assistant.chat_name}'\n\n"
                         f"Попробуйте позже или проверьте доступ к чату."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление об ошибке: {e}")

            # Сохраняем ошибку в историю
            database.save_execution(
                assistant_id=assistant_id,
                started_at=started_at,
                completed_at=datetime.now(),
                status='error',
                messages_count=0,
                summary_sent=False,
                error_message="LLM не вернул первоначальную сводку"
            )
            return

        # Форматируем и отправляем первоначальную сводку
        formatted_summary = _format_initial_summary(
            chat_name=assistant.chat_name,
            message_limit=message_limit,
            summary=summary,
            next_run_at=assistant.next_run_at
        )

        # Отправка сводки через Telegram бота
        try:
            await telegram_bot_instance.application.bot.send_message(
                chat_id=assistant.user_id,
                text=formatted_summary,
                parse_mode=None
            )

            logger.info(f"Первоначальная сводка отправлена пользователю {assistant.user_id}")
            summary_sent = True

        except Exception as e:
            logger.error(f"Ошибка отправки первоначальной сводки пользователю {assistant.user_id}: {e}")
            summary_sent = False

        # Сохраняем в историю выполнения
        completed_at = datetime.now()
        database.save_execution(
            assistant_id=assistant_id,
            started_at=started_at,
            completed_at=completed_at,
            status='success',
            messages_count=message_limit,
            summary_sent=summary_sent,
            error_message=None
        )

        execution_time = (completed_at - started_at).total_seconds()
        logger.info(f"Первоначальная сводка для ассистента {assistant_id} выполнена за {execution_time:.2f} сек")

    except Exception as e:
        logger.error(f"Неожиданная ошибка при выполнении первоначальной сводки {assistant_id}: {e}", exc_info=True)

        # Сохраняем ошибку в историю
        database.save_execution(
            assistant_id=assistant_id,
            started_at=started_at,
            completed_at=datetime.now(),
            status='error',
            messages_count=0,
            summary_sent=False,
            error_message=str(e)
        )

        # Отправляем уведомление пользователю об ошибке
        try:
            assistant = database.get_assistant(assistant_id)
            if assistant:
                error_message = (
                    f"⚠️ Не удалось создать первоначальную сводку из чата '{assistant.chat_name}'\n\n"
                    f"Причина: {str(e)}\n\n"
                    f"Автоматические сводки будут работать по расписанию."
                )

                await telegram_bot_instance.application.bot.send_message(
                    chat_id=assistant.user_id,
                    text=error_message
                )
        except Exception as notify_error:
            logger.error(f"Не удалось отправить уведомление об ошибке: {notify_error}")


def _build_initial_summary_prompt(custom_prompt: Optional[str], message_limit: int) -> str:
    """
    Построение системного промпта для первоначальной сводки.

    Args:
        custom_prompt: Пользовательский промпт (опционально)
        message_limit: Количество сообщений

    Returns:
        Системный промпт
    """
    base_prompt = (
        "Ты - ассистент для анализа сообщений из Telegram чатов.\n\n"
        "У тебя есть доступ к инструменту get_chat_messages, который позволяет "
        "получить сообщения из чата за указанный период.\n\n"
        "Сейчас ты создаёшь ПЕРВОНАЧАЛЬНУЮ СВОДКУ по последним сообщениям из чата.\n\n"
        "ВАЖНО: Пользователь УЖЕ указал все параметры. Твоя задача:\n"
        f"1. НЕМЕДЛЕННО вызови инструмент get_chat_messages с параметрами из user message\n"
        "2. Проанализируй полученные сообщения\n"
        "3. Создай обзорную сводку, которая познакомит пользователя с контекстом чата\n\n"
        "НЕ задавай пользователю вопросы об уточнении параметров - все параметры уже переданы в user message.\n"
        "НЕ уточняй временной период - используй параметры from_date и to_date из user message.\n\n"
    )

    if custom_prompt:
        base_prompt += f"Дополнительные инструкции по анализу:\n{custom_prompt}\n\n"
    else:
        base_prompt += (
            "При создании первоначальной сводки:\n"
            "- Дай общий обзор тематики и активности чата\n"
            "- Выдели основные темы, которые обсуждались в последнее время\n"
            "- Укажи ключевых участников обсуждений (если применимо)\n"
            "- Отметь важные решения, события или договоренности\n"
            "- Используй маркированные списки для структурирования\n\n"
        )

    base_prompt += (
        "Если сообщений мало, сообщи об этом.\n"
        "НЕ включай в ответ технические детали вызова инструмента - "
        "только итоговую сводку для пользователя."
    )

    return base_prompt


def _format_initial_summary(
    chat_name: str,
    message_limit: int,
    summary: str,
    next_run_at: Optional[datetime]
) -> str:
    """
    Форматирование первоначальной сводки для отправки пользователю.

    Args:
        chat_name: Название чата
        message_limit: Количество проанализированных сообщений
        summary: Текст сводки от LLM
        next_run_at: Время следующего запуска

    Returns:
        Отформатированная сводка
    """
    result = f"🎉 Первоначальная сводка из чата: {chat_name}\n"
    result += f"📨 Проанализировано последних сообщений: {message_limit}\n\n"
    result += summary
    result += "\n\n---\n"
    result += "✅ Ассистент запущен и будет автоматически создавать сводки\n"

    if next_run_at:
        next_str = next_run_at.strftime("%d.%m.%Y в %H:%M")
        result += f"⏰ Следующая автоматическая сводка: {next_str}"

    return result
