"""
Планировщик для управления фоновыми задачами.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from .base_task import BaseTask, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Планировщик для управления и выполнения фоновых задач.

    Функциональность:
    - Регистрация и управление задачами
    - Периодическое выполнение задач
    - Приоритизация задач
    - Мониторинг состояния задач
    - Автоматический retry при ошибках

    Attributes:
        tasks (Dict[str, BaseTask]): Словарь зарегистрированных задач
        is_running (bool): Флаг работы планировщика
        check_interval (int): Интервал проверки задач в секундах
    """

    def __init__(self, check_interval: int = 10):
        """
        Инициализация планировщика.

        Args:
            check_interval: Интервал проверки задач в секундах (по умолчанию 10)
        """
        self.tasks: Dict[str, BaseTask] = {}
        self.is_running = False
        self.check_interval = check_interval
        self._scheduler_task: Optional[asyncio.Task] = None
        logger.info(f"TaskScheduler initialized with check_interval={check_interval}s")

    def register_task(self, task: BaseTask) -> None:
        """
        Регистрация новой задачи в планировщике.

        Args:
            task: Экземпляр задачи для регистрации

        Raises:
            ValueError: Если задача с таким ID уже зарегистрирована
        """
        if task.task_id in self.tasks:
            raise ValueError(f"Task with ID '{task.task_id}' already registered")

        self.tasks[task.task_id] = task
        logger.info(
            f"Task '{task.name}' ({task.task_id}) registered "
            f"(periodic={task.is_periodic}, priority={task.priority.name})"
        )

    def unregister_task(self, task_id: str) -> bool:
        """
        Удаление задачи из планировщика.

        Args:
            task_id: ID задачи для удаления

        Returns:
            True если задача была удалена, False если не найдена
        """
        if task_id in self.tasks:
            task = self.tasks[task_id]

            # Отменяем задачу если она выполняется
            if task.status == TaskStatus.RUNNING:
                task.cancel()

            del self.tasks[task_id]
            logger.info(f"Task '{task.name}' ({task_id}) unregistered")
            return True

        logger.warning(f"Attempted to unregister non-existent task '{task_id}'")
        return False

    def get_task(self, task_id: str) -> Optional[BaseTask]:
        """
        Получение задачи по ID.

        Args:
            task_id: ID задачи

        Returns:
            Экземпляр задачи или None если не найдена
        """
        return self.tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[BaseTask]:
        """
        Получение списка задач с фильтрацией по статусу.

        Args:
            status: Фильтр по статусу (опционально)

        Returns:
            Список задач
        """
        if status is None:
            return list(self.tasks.values())

        return [task for task in self.tasks.values() if task.status == status]

    def get_pending_tasks(self) -> List[BaseTask]:
        """
        Получение списка задач, готовых к выполнению.

        Задачи сортируются по приоритету (от высокого к низкому).

        Returns:
            Список задач готовых к выполнению, отсортированных по приоритету
        """
        pending_tasks = [
            task for task in self.tasks.values()
            if task.should_run()
        ]

        # Сортируем по приоритету (от высокого к низкому)
        pending_tasks.sort(key=lambda t: t.priority.value, reverse=True)

        return pending_tasks

    async def start(self) -> None:
        """
        Запуск планировщика.

        Планировщик начинает периодическую проверку и выполнение задач.
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        self.is_running = True
        logger.info("TaskScheduler started")

        # Запускаем основной цикл планировщика в фоне
        self._scheduler_task = asyncio.create_task(self._run_scheduler())

    async def stop(self) -> None:
        """
        Остановка планировщика.

        Останавливает выполнение новых задач и ожидает завершения текущих.
        """
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        self.is_running = False
        logger.info("TaskScheduler stopping...")

        # Отменяем задачу планировщика
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        # Ожидаем завершения всех выполняющихся задач
        running_tasks = [
            task for task in self.tasks.values()
            if task.status == TaskStatus.RUNNING
        ]

        if running_tasks:
            logger.info(f"Waiting for {len(running_tasks)} running tasks to complete...")
            # Даем задачам время на завершение (макс 30 секунд)
            await asyncio.sleep(min(30, self.check_interval * 3))

        logger.info("TaskScheduler stopped")

    async def _run_scheduler(self) -> None:
        """
        Основной цикл планировщика.

        Периодически проверяет и запускает задачи, готовые к выполнению.
        """
        logger.info("Scheduler loop started")

        while self.is_running:
            try:
                # Получаем задачи, готовые к выполнению
                pending_tasks = self.get_pending_tasks()

                if pending_tasks:
                    logger.debug(f"Found {len(pending_tasks)} pending tasks")

                    # Запускаем задачи параллельно
                    task_coroutines = [task.run() for task in pending_tasks]
                    results = await asyncio.gather(*task_coroutines, return_exceptions=True)

                    # Логируем результаты
                    for task, result in zip(pending_tasks, results):
                        if isinstance(result, Exception):
                            logger.error(
                                f"Task '{task.name}' ({task.task_id}) raised exception: {result}"
                            )
                        elif result:
                            logger.debug(
                                f"Task '{task.name}' ({task.task_id}) completed successfully"
                            )

                # Ждем перед следующей проверкой
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)

        logger.info("Scheduler loop stopped")

    async def run_task_now(self, task_id: str) -> bool:
        """
        Немедленный запуск задачи вручную.

        Args:
            task_id: ID задачи для запуска

        Returns:
            True если задача успешно выполнена, False при ошибке

        Raises:
            ValueError: Если задача не найдена
        """
        task = self.get_task(task_id)

        if task is None:
            raise ValueError(f"Task '{task_id}' not found")

        logger.info(f"Manually running task '{task.name}' ({task_id})")
        return await task.run()

    def get_statistics(self) -> Dict[str, any]:
        """
        Получение статистики по задачам.

        Returns:
            Словарь со статистикой:
                - total: общее количество задач
                - pending: количество ожидающих задач
                - running: количество выполняющихся задач
                - completed: количество завершенных задач
                - failed: количество провалившихся задач
                - periodic: количество периодических задач
        """
        return {
            "total": len(self.tasks),
            "pending": len(self.list_tasks(TaskStatus.PENDING)),
            "running": len(self.list_tasks(TaskStatus.RUNNING)),
            "completed": len(self.list_tasks(TaskStatus.COMPLETED)),
            "failed": len(self.list_tasks(TaskStatus.FAILED)),
            "cancelled": len(self.list_tasks(TaskStatus.CANCELLED)),
            "periodic": len([t for t in self.tasks.values() if t.is_periodic]),
            "is_running": self.is_running,
            "check_interval": self.check_interval,
        }

    def get_tasks_info(self) -> List[Dict[str, any]]:
        """
        Получение информации о всех задачах.

        Returns:
            Список словарей с информацией о каждой задаче
        """
        return [task.get_info() for task in self.tasks.values()]

    async def health_check(self) -> Dict[str, any]:
        """
        Проверка здоровья планировщика.

        Returns:
            Словарь с информацией о состоянии планировщика
        """
        stats = self.get_statistics()
        failed_tasks = self.list_tasks(TaskStatus.FAILED)

        return {
            "healthy": len(failed_tasks) == 0 and self.is_running,
            "running": self.is_running,
            "statistics": stats,
            "failed_tasks": [
                {
                    "task_id": task.task_id,
                    "name": task.name,
                    "error": task.error_message,
                }
                for task in failed_tasks
            ],
        }

    def __repr__(self) -> str:
        """Строковое представление планировщика."""
        stats = self.get_statistics()
        return (
            f"<TaskScheduler("
            f"running={self.is_running}, "
            f"total_tasks={stats['total']}, "
            f"pending={stats['pending']}, "
            f"failed={stats['failed']})>"
        )
