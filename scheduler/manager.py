"""
Scheduler Manager - менеджер планировщиков для системы автоматических сводок.

Управляет:
- Созданием и остановкой ассистентов
- Планированием задач через APScheduler
- Восстановлением после перезапуска
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED

from storage import Database, Assistant
from .config import get_scheduler_config
from .tasks import execute_task
from .context import get_context

logger = logging.getLogger(__name__)


class SchedulerManager:
    """
    Менеджер для управления планировщиками ассистентов.

    Создаёт, останавливает и восстанавливает задачи для автоматического
    сбора сообщений и генерации сводок из Telegram чатов.
    """

    def __init__(
        self,
        database: Database,
        llm_provider,
        telegram_bot_instance
    ):
        """
        Инициализация менеджера планировщиков.

        Args:
            database: Экземпляр базы данных
            llm_provider: Провайдер LLM (DeepSeek)
            telegram_bot_instance: Экземпляр Telegram бота
        """
        self.database = database
        self.llm_provider = llm_provider
        self.telegram_bot = telegram_bot_instance

        # Инициализируем глобальный контекст для задач
        context = get_context()
        context.initialize(database, llm_provider, telegram_bot_instance)
        logger.info("Глобальный контекст планировщика инициализирован")

        # Создаём планировщик
        scheduler_config = get_scheduler_config()
        self.scheduler = AsyncIOScheduler(**scheduler_config)

        # Добавляем слушатели событий для диагностики
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._job_missed_listener, EVENT_JOB_MISSED)

        logger.info("Event listeners добавлены для мониторинга выполнения задач")

        # Максимальное количество ассистентов на пользователя
        self.max_assistants_per_user = int(os.getenv("MAX_ASSISTANTS_PER_USER", "10"))

        logger.info("Scheduler Manager инициализирован")

    def _job_executed_listener(self, event):
        """Слушатель успешного выполнения задачи."""
        logger.info(f"✅ Job {event.job_id} выполнен успешно")

    def _job_error_listener(self, event):
        """Слушатель ошибок выполнения задачи."""
        logger.error(f"❌ Job {event.job_id} завершился с ошибкой: {event.exception}")

    def _job_missed_listener(self, event):
        """Слушатель пропущенных задач."""
        logger.warning(f"⚠️ Job {event.job_id} пропущен (misfire)")

    def start(self) -> None:
        """Запуск планировщика."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler запущен")

    def shutdown(self) -> None:
        """Остановка планировщика."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("APScheduler остановлен")

    async def create_assistant(
        self,
        user_id: int,
        chat_id: str,
        chat_name: str,
        interval_type: str,
        interval_value: int,
        start_time: Optional[datetime] = None,
        custom_prompt: Optional[str] = None
    ) -> tuple[bool, str, Optional[Assistant]]:
        """
        Создание нового ассистента.

        Args:
            user_id: Telegram user_id владельца
            chat_id: ID чата для мониторинга
            chat_name: Название чата
            interval_type: Тип интервала ('minute', 'hour', 'day', 'custom')
            interval_value: Значение интервала в минутах
            start_time: Время первого запуска (опционально, по умолчанию сейчас)
            custom_prompt: Пользовательский промпт (опционально)

        Returns:
            Кортеж (успех, сообщение, assistant)
        """
        try:
            # Проверка лимита ассистентов
            active_count = self.database.count_user_active_assistants(user_id)
            if active_count >= self.max_assistants_per_user:
                return False, f"Достигнут лимит активных ассистентов ({self.max_assistants_per_user})", None

            # Проверка существования ассистента для этого чата
            existing = self.database.get_assistant_by_chat(user_id, chat_id)
            if existing:
                return False, f"Ассистент для чата '{chat_name}' уже существует", None

            # Создаём ассистента в БД
            assistant = self.database.create_assistant(
                user_id=user_id,
                chat_id=chat_id,
                chat_name=chat_name,
                interval_type=interval_type,
                interval_value=interval_value,
                custom_prompt=custom_prompt
            )

            # Добавляем задачу в планировщик
            job_id = self._add_scheduler_job(assistant, start_time)

            # Сохраняем job_id в БД
            self.database.update_scheduler_job_id(assistant.assistant_id, job_id)

            # Обновляем next_run_at (НЕ обновляем last_run_at, т.к. задача ещё не выполнялась!)
            job = self.scheduler.get_job(job_id)
            if job and job.next_run_time:
                self.database.update_last_run(
                    assistant.assistant_id,
                    last_run_at=None,  # Задача ещё не запускалась
                    next_run_at=job.next_run_time.replace(tzinfo=None)
                )

            logger.info(f"Ассистент {assistant.assistant_id} создан для чата {chat_name}")

            # Запускаем первоначальную сводку по последним 100 сообщениям
            try:
                logger.info(f"Запуск первоначальной сводки для ассистента {assistant.assistant_id}")
                # Импортируем здесь, чтобы избежать циклических зависимостей
                from .tasks import execute_initial_summary

                # Запускаем в фоне через asyncio
                import asyncio
                asyncio.create_task(execute_initial_summary(
                    assistant_id=assistant.assistant_id,
                    message_limit=10
                ))
                logger.info(f"Первоначальная сводка для {assistant.assistant_id} запущена в фоне")
            except Exception as e:
                logger.error(f"Ошибка запуска первоначальной сводки: {e}", exc_info=True)
                # Не прерываем создание ассистента из-за ошибки первоначальной сводки

            return True, "Ассистент успешно создан", assistant

        except Exception as e:
            logger.error(f"Ошибка создания ассистента: {e}", exc_info=True)
            return False, f"Ошибка создания ассистента: {str(e)}", None

    def _add_scheduler_job(
        self,
        assistant: Assistant,
        start_time: Optional[datetime] = None
    ) -> str:
        """
        Добавление задачи в APScheduler.

        Args:
            assistant: Объект ассистента
            start_time: Время первого запуска (опционально, если None - запланируется через интервал)

        Returns:
            ID созданной задачи
        """
        job_id = f"assistant_{assistant.assistant_id}"

        # Определяем триггер в зависимости от типа интервала
        if assistant.interval_type == 'minute':
            trigger = IntervalTrigger(minutes=assistant.interval_value)
        elif assistant.interval_type == 'hour':
            trigger = IntervalTrigger(hours=assistant.interval_value)
        elif assistant.interval_type == 'day':
            trigger = IntervalTrigger(days=assistant.interval_value)
        else:  # custom
            trigger = IntervalTrigger(minutes=assistant.interval_value)

        # Если start_time не задан, вычисляем время первого запуска = сейчас + интервал
        if start_time is None:
            if assistant.interval_type == 'minute':
                start_time = datetime.now() + timedelta(minutes=assistant.interval_value)
            elif assistant.interval_type == 'hour':
                start_time = datetime.now() + timedelta(hours=assistant.interval_value)
            elif assistant.interval_type == 'day':
                start_time = datetime.now() + timedelta(days=assistant.interval_value)
            else:  # custom
                start_time = datetime.now() + timedelta(minutes=assistant.interval_value)

        # Добавляем задачу (передаем только assistant_id)
        self.scheduler.add_job(
            func=execute_task,
            trigger=trigger,
            args=[assistant.assistant_id],
            id=job_id,
            name=f"Assistant: {assistant.chat_name}",
            replace_existing=True,
            next_run_time=start_time
        )

        logger.info(f"Задача {job_id} добавлена в планировщик с первым запуском в {start_time}")

        # Дополнительная диагностика
        job = self.scheduler.get_job(job_id)
        if job:
            logger.info(f"Задача {job_id} проверка: next_run_time={job.next_run_time}, trigger={job.trigger}")
        else:
            logger.error(f"Задача {job_id} не найдена сразу после добавления!")

        return job_id

    async def stop_assistant(self, user_id: int, chat_name: str) -> tuple[bool, str]:
        """
        Остановка ассистента по названию чата.

        Args:
            user_id: Telegram user_id владельца
            chat_name: Название чата

        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            # Поиск ассистента (по chat_name)
            assistants = self.database.get_user_assistants(user_id)
            assistant = None

            for a in assistants:
                if a.chat_name.lower() == chat_name.lower():
                    assistant = a
                    break

            if not assistant:
                return False, f"Ассистент для чата '{chat_name}' не найден"

            # Удаляем задачу из планировщика
            if assistant.scheduler_job_id:
                try:
                    self.scheduler.remove_job(assistant.scheduler_job_id)
                    logger.info(f"Задача {assistant.scheduler_job_id} удалена из планировщика")
                except Exception as e:
                    logger.warning(f"Не удалось удалить задачу из планировщика: {e}")

            # Обновляем статус в БД
            self.database.update_assistant_status(assistant.assistant_id, 'stopped')

            logger.info(f"Ассистент {assistant.assistant_id} остановлен")

            return True, f"Ассистент для чата '{chat_name}' остановлен"

        except Exception as e:
            logger.error(f"Ошибка остановки ассистента: {e}", exc_info=True)
            return False, f"Ошибка остановки ассистента: {str(e)}"

    async def stop_all_assistants(self, user_id: int) -> tuple[bool, str, List[str]]:
        """
        Остановка всех активных ассистентов пользователя.

        Args:
            user_id: Telegram user_id владельца

        Returns:
            Кортеж (успех, сообщение, список остановленных)
        """
        try:
            active_assistants = self.database.get_active_assistants(user_id=user_id)

            if not active_assistants:
                return True, "Нет активных ассистентов для остановки", []

            stopped = []

            for assistant in active_assistants:
                # Удаляем задачу из планировщика
                if assistant.scheduler_job_id:
                    try:
                        self.scheduler.remove_job(assistant.scheduler_job_id)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить задачу {assistant.scheduler_job_id}: {e}")

                # Обновляем статус
                self.database.update_assistant_status(assistant.assistant_id, 'stopped')
                stopped.append(assistant.chat_name)

            logger.info(f"Остановлено {len(stopped)} ассистентов для пользователя {user_id}")

            return True, f"Остановлено ассистентов: {len(stopped)}", stopped

        except Exception as e:
            logger.error(f"Ошибка остановки всех ассистентов: {e}", exc_info=True)
            return False, f"Ошибка: {str(e)}", []

    def list_assistants(self, user_id: int) -> List[dict]:
        """
        Получение списка всех ассистентов пользователя.

        Args:
            user_id: Telegram user_id

        Returns:
            Список словарей с информацией об ассистентах
        """
        assistants = self.database.get_user_assistants(user_id)

        result = []

        for assistant in assistants:
            # Получаем информацию о следующем запуске из планировщика
            next_run_str = "-"

            if assistant.scheduler_job_id and assistant.status == 'active':
                try:
                    job = self.scheduler.get_job(assistant.scheduler_job_id)
                    if job and job.next_run_time:
                        next_run = job.next_run_time.replace(tzinfo=None)
                        delta = next_run - datetime.now()

                        if delta.total_seconds() > 0:
                            if delta.days > 0:
                                next_run_str = f"{next_run.strftime('%d.%m.%Y в %H:%M')}"
                            else:
                                minutes = int(delta.total_seconds() / 60)
                                next_run_str = f"{next_run.strftime('%H:%M')} (через {minutes} мин)"
                        else:
                            next_run_str = "скоро"
                except Exception as e:
                    logger.warning(f"Не удалось получить next_run_time для {assistant.scheduler_job_id}: {e}")

            # Форматируем интервал
            if assistant.interval_type == 'minute':
                interval_str = f"каждую минуту" if assistant.interval_value == 1 else f"каждые {assistant.interval_value} минут"
            elif assistant.interval_type == 'hour':
                interval_str = f"каждый час" if assistant.interval_value == 1 else f"каждые {assistant.interval_value} часов"
            elif assistant.interval_type == 'day':
                interval_str = f"каждый день" if assistant.interval_value == 1 else f"каждые {assistant.interval_value} дней"
            else:  # custom
                interval_str = f"каждые {assistant.interval_value} минут"

            result.append({
                "chat_name": assistant.chat_name,
                "interval": interval_str,
                "next_run": next_run_str,
                "status": assistant.status,
                "assistant_id": assistant.assistant_id[:8]  # Короткий ID
            })

        return result

    async def restore_assistants(self) -> int:
        """
        Восстановление всех активных ассистентов после перезапуска.

        Returns:
            Количество восстановленных ассистентов
        """
        logger.info("Восстановление активных ассистентов...")

        try:
            active_assistants = self.database.get_active_assistants()

            if not active_assistants:
                logger.info("Нет активных ассистентов для восстановления")
                return 0

            restored_count = 0

            for assistant in active_assistants:
                try:
                    # Вычисляем время следующего запуска на основе last_run_at
                    start_time = None
                    if assistant.last_run_at:
                        # Если задача уже выполнялась, следующий запуск = last_run_at + интервал
                        if assistant.interval_type == 'minute':
                            start_time = assistant.last_run_at + timedelta(minutes=assistant.interval_value)
                        elif assistant.interval_type == 'hour':
                            start_time = assistant.last_run_at + timedelta(hours=assistant.interval_value)
                        elif assistant.interval_type == 'day':
                            start_time = assistant.last_run_at + timedelta(days=assistant.interval_value)
                        else:  # custom
                            start_time = assistant.last_run_at + timedelta(minutes=assistant.interval_value)

                        # Если вычисленное время уже прошло, запускаем немедленно
                        if start_time < datetime.now():
                            start_time = datetime.now() + timedelta(seconds=10)  # Запуск через 10 секунд

                    # Пересоздаём задачу в планировщике с правильным start_time
                    job_id = self._add_scheduler_job(assistant, start_time)

                    # Обновляем job_id в БД (может измениться после перезапуска)
                    self.database.update_scheduler_job_id(assistant.assistant_id, job_id)

                    # Обновляем next_run_at
                    job = self.scheduler.get_job(job_id)
                    if job and job.next_run_time:
                        self.database.update_last_run(
                            assistant.assistant_id,
                            last_run_at=assistant.last_run_at,
                            next_run_at=job.next_run_time.replace(tzinfo=None)
                        )

                    restored_count += 1
                    logger.info(f"Восстановлен ассистент {assistant.assistant_id} ({assistant.chat_name}), next_run={job.next_run_time if job else 'N/A'}")

                except Exception as e:
                    logger.error(f"Не удалось восстановить ассистента {assistant.assistant_id}: {e}")
                    # Помечаем как error
                    self.database.update_assistant_status(assistant.assistant_id, 'error')

            logger.info(f"Восстановлено {restored_count} из {len(active_assistants)} ассистентов")

            return restored_count

        except Exception as e:
            logger.error(f"Ошибка при восстановлении ассистентов: {e}", exc_info=True)
            return 0

    async def delete_assistant(self, user_id: int, chat_name: str) -> tuple[bool, str]:
        """
        Удаление ассистента (остановка + удаление из БД).

        Args:
            user_id: Telegram user_id владельца
            chat_name: Название чата

        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            # Поиск ассистента (по chat_name)
            assistants = self.database.get_user_assistants(user_id)
            assistant = None

            for a in assistants:
                if a.chat_name.lower() == chat_name.lower():
                    assistant = a
                    break

            if not assistant:
                return False, f"Ассистент для чата '{chat_name}' не найден"

            # Удаляем задачу из планировщика
            if assistant.scheduler_job_id:
                try:
                    self.scheduler.remove_job(assistant.scheduler_job_id)
                    logger.info(f"Задача {assistant.scheduler_job_id} удалена из планировщика")
                except Exception as e:
                    logger.warning(f"Не удалось удалить задачу из планировщика: {e}")

            # Удаляем из БД
            self.database.delete_assistant(assistant.assistant_id)

            logger.info(f"Ассистент {assistant.assistant_id} удалён")

            return True, f"Ассистент для чата '{chat_name}' удалён"

        except Exception as e:
            logger.error(f"Ошибка удаления ассистента: {e}", exc_info=True)
            return False, f"Ошибка удаления ассистента: {str(e)}"

    async def delete_all_assistants(self, user_id: int) -> tuple[bool, str, List[str]]:
        """
        Удаление всех ассистентов пользователя (всех, не только активных).

        Args:
            user_id: Telegram user_id владельца

        Returns:
            Кортеж (успех, сообщение, список удалённых)
        """
        try:
            all_assistants = self.database.get_user_assistants(user_id)

            if not all_assistants:
                return True, "Нет ассистентов для удаления", []

            deleted = []

            for assistant in all_assistants:
                # Удаляем задачу из планировщика (если есть)
                if assistant.scheduler_job_id:
                    try:
                        self.scheduler.remove_job(assistant.scheduler_job_id)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить задачу {assistant.scheduler_job_id}: {e}")

                # Удаляем из БД
                self.database.delete_assistant(assistant.assistant_id)
                deleted.append(assistant.chat_name)

            logger.info(f"Удалено {len(deleted)} ассистентов для пользователя {user_id}")

            return True, f"Удалено ассистентов: {len(deleted)}", deleted

        except Exception as e:
            logger.error(f"Ошибка удаления всех ассистентов: {e}", exc_info=True)
            return False, f"Ошибка: {str(e)}", []
