"""
Базовые классы для системы фоновых задач.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Статусы выполнения задачи."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Приоритеты задач."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class BaseTask(ABC):
    """
    Базовый класс для всех фоновых задач.

    Каждая задача должна реализовать метод execute() для выполнения своей логики.

    Attributes:
        task_id (str): Уникальный идентификатор задачи
        name (str): Название задачи
        priority (TaskPriority): Приоритет выполнения
        status (TaskStatus): Текущий статус
        interval (timedelta): Интервал между запусками (для периодических задач)
        is_periodic (bool): Является ли задача периодической
        last_run (datetime): Время последнего запуска
        next_run (datetime): Время следующего запуска
        max_retries (int): Максимальное количество попыток при ошибке
        retry_count (int): Текущее количество попыток
    """

    def __init__(
        self,
        task_id: str,
        name: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        interval: Optional[timedelta] = None,
        is_periodic: bool = False,
        max_retries: int = 3
    ):
        """
        Инициализация базовой задачи.

        Args:
            task_id: Уникальный идентификатор задачи
            name: Название задачи
            priority: Приоритет выполнения
            interval: Интервал между запусками (для периодических задач)
            is_periodic: Является ли задача периодической
            max_retries: Максимальное количество попыток при ошибке
        """
        self.task_id = task_id
        self.name = name
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.interval = interval
        self.is_periodic = is_periodic
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.max_retries = max_retries
        self.retry_count = 0
        self.error_message: Optional[str] = None
        self.result: Optional[Any] = None

        # Если задача периодическая, планируем первый запуск
        if is_periodic and interval:
            self.next_run = datetime.now() + interval

        logger.info(
            f"Task '{name}' ({task_id}) initialized: "
            f"periodic={is_periodic}, priority={priority.name}"
        )

    @abstractmethod
    async def execute(self) -> Any:
        """
        Выполнение задачи.

        Каждая задача должна реализовать этот метод.

        Returns:
            Результат выполнения задачи

        Raises:
            Exception: Любые ошибки при выполнении
        """
        pass

    async def run(self) -> bool:
        """
        Запуск задачи с обработкой ошибок и статусами.

        Returns:
            True если задача выполнена успешно, False при ошибке
        """
        if self.status == TaskStatus.RUNNING:
            logger.warning(f"Task '{self.name}' ({self.task_id}) уже выполняется")
            return False

        self.status = TaskStatus.RUNNING
        self.last_run = datetime.now()

        logger.info(f"Starting task '{self.name}' ({self.task_id})")

        try:
            self.result = await self.execute()
            self.status = TaskStatus.COMPLETED
            self.retry_count = 0  # Сбрасываем счетчик попыток при успехе
            self.error_message = None

            # Планируем следующий запуск для периодических задач
            if self.is_periodic and self.interval:
                self.next_run = datetime.now() + self.interval
                self.status = TaskStatus.PENDING

            logger.info(f"Task '{self.name}' ({self.task_id}) completed successfully")
            return True

        except asyncio.CancelledError:
            self.status = TaskStatus.CANCELLED
            logger.warning(f"Task '{self.name}' ({self.task_id}) was cancelled")
            return False

        except Exception as e:
            self.retry_count += 1
            self.error_message = str(e)

            logger.error(
                f"Task '{self.name}' ({self.task_id}) failed: {e} "
                f"(attempt {self.retry_count}/{self.max_retries})",
                exc_info=True
            )

            # Обработка ошибки
            if self.retry_count >= self.max_retries:
                self.status = TaskStatus.FAILED
                await self.on_failure(e)
                logger.error(
                    f"Task '{self.name}' ({self.task_id}) failed after "
                    f"{self.retry_count} attempts"
                )
                return False
            else:
                # Планируем повторную попытку
                self.status = TaskStatus.PENDING
                retry_delay = timedelta(seconds=30 * self.retry_count)  # Экспоненциальная задержка
                self.next_run = datetime.now() + retry_delay
                logger.info(
                    f"Task '{self.name}' ({self.task_id}) will retry in "
                    f"{retry_delay.total_seconds()} seconds"
                )
                return False

    async def on_failure(self, error: Exception) -> None:
        """
        Обработчик ошибки при исчерпании попыток.

        Может быть переопределен в подклассах для специфической обработки.

        Args:
            error: Исключение, которое произошло
        """
        logger.error(
            f"Task '{self.name}' ({self.task_id}) reached max retries: {error}"
        )

    def should_run(self) -> bool:
        """
        Проверка, нужно ли запускать задачу сейчас.

        Returns:
            True если задача должна быть запущена
        """
        if self.status == TaskStatus.RUNNING:
            return False

        if self.status == TaskStatus.FAILED:
            return False

        if self.status == TaskStatus.CANCELLED:
            return False

        if not self.is_periodic:
            return self.status == TaskStatus.PENDING

        # Для периодических задач проверяем время следующего запуска
        if self.next_run is None:
            return True

        return datetime.now() >= self.next_run

    def cancel(self) -> None:
        """Отмена задачи."""
        if self.status == TaskStatus.RUNNING:
            logger.warning(
                f"Cannot cancel running task '{self.name}' ({self.task_id})"
            )
            return

        self.status = TaskStatus.CANCELLED
        logger.info(f"Task '{self.name}' ({self.task_id}) cancelled")

    def reset(self) -> None:
        """Сброс состояния задачи для повторного запуска."""
        self.status = TaskStatus.PENDING
        self.retry_count = 0
        self.error_message = None
        self.result = None

        if self.is_periodic and self.interval:
            self.next_run = datetime.now() + self.interval

        logger.info(f"Task '{self.name}' ({self.task_id}) reset")

    def get_info(self) -> Dict[str, Any]:
        """
        Получение информации о задаче.

        Returns:
            Словарь с информацией о задаче
        """
        return {
            "task_id": self.task_id,
            "name": self.name,
            "priority": self.priority.name,
            "status": self.status.name,
            "is_periodic": self.is_periodic,
            "interval_seconds": self.interval.total_seconds() if self.interval else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
        }

    def __repr__(self) -> str:
        """Строковое представление задачи."""
        return (
            f"<{self.__class__.__name__}("
            f"id='{self.task_id}', "
            f"name='{self.name}', "
            f"status={self.status.name}, "
            f"priority={self.priority.name})>"
        )
