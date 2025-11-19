"""
Класс Database для работы с SQLite базой данных.

Предоставляет CRUD операции для assistants, execution_history, chat_metadata.
"""

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Assistant, ExecutionHistory, ChatMetadata

logger = logging.getLogger(__name__)


class Database:
    """
    Класс для работы с SQLite базой данных системы автоматических сводок.

    Управляет:
    - Ассистентами (assistants)
    - Историей выполнения (execution_history)
    - Метаданными чатов (chat_metadata)
    """

    def __init__(self, db_path: str = "data/assistants.db"):
        """
        Инициализация подключения к базе данных.

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path

        # Создаём директорию data, если её нет
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Подключение к БД
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Позволяет обращаться к колонкам по имени

        logger.info(f"Подключение к базе данных: {db_path}")

    def create_tables(self) -> None:
        """
        Создание таблиц базы данных из миграционного скрипта.

        Выполняет SQL-скрипт из migrations/001_initial_schema.sql
        """
        migration_path = Path(__file__).parent / "migrations" / "001_initial_schema.sql"

        try:
            with open(migration_path, 'r', encoding='utf-8') as f:
                migration_sql = f.read()

            self.conn.executescript(migration_sql)
            self.conn.commit()

            logger.info("Таблицы базы данных успешно созданы")

        except Exception as e:
            logger.error(f"Ошибка при создании таблиц: {e}")
            raise

    # ==================== CRUD для Assistants ====================

    def create_assistant(
        self,
        user_id: int,
        chat_id: str,
        chat_name: str,
        interval_type: str,
        interval_value: int,
        custom_prompt: Optional[str] = None
    ) -> Assistant:
        """
        Создание нового ассистента.

        Args:
            user_id: Telegram user_id владельца
            chat_id: ID чата для мониторинга
            chat_name: Название чата
            interval_type: Тип интервала ('minute', 'hour', 'day', 'custom')
            interval_value: Значение интервала в минутах
            custom_prompt: Пользовательский промпт (опционально)

        Returns:
            Созданный объект Assistant

        Raises:
            sqlite3.IntegrityError: Если ассистент для этого чата уже существует
        """
        assistant_id = str(uuid.uuid4())
        now = datetime.now()

        # Создаём объект ассистента
        assistant = Assistant(
            id=None,
            assistant_id=assistant_id,
            user_id=user_id,
            chat_id=chat_id,
            chat_name=chat_name,
            interval_type=interval_type,
            interval_value=interval_value,
            custom_prompt=custom_prompt,
            status='active',
            scheduler_job_id=None,
            created_at=now,
            updated_at=now
        )

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO assistants (
                    assistant_id, user_id, chat_id, chat_name,
                    interval_type, interval_value, custom_prompt, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assistant.assistant_id,
                assistant.user_id,
                assistant.chat_id,
                assistant.chat_name,
                assistant.interval_type,
                assistant.interval_value,
                assistant.custom_prompt,
                assistant.status,
                assistant.created_at,
                assistant.updated_at
            ))

            self.conn.commit()
            assistant.id = cursor.lastrowid

            logger.info(f"Создан ассистент {assistant_id} для пользователя {user_id}, чат {chat_name}")
            return assistant

        except sqlite3.IntegrityError as e:
            logger.error(f"Ошибка создания ассистента: {e}")
            raise

    def get_assistant(self, assistant_id: str) -> Optional[Assistant]:
        """
        Получение ассистента по ID.

        Args:
            assistant_id: ID ассистента

        Returns:
            Объект Assistant или None, если не найден
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM assistants WHERE assistant_id = ?", (assistant_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_assistant(row)
        return None

    def get_assistant_by_chat(self, user_id: int, chat_id: str) -> Optional[Assistant]:
        """
        Получение ассистента по user_id и chat_id.

        Args:
            user_id: Telegram user_id
            chat_id: ID чата

        Returns:
            Объект Assistant или None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM assistants WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_assistant(row)
        return None

    def get_active_assistants(self, user_id: Optional[int] = None) -> List[Assistant]:
        """
        Получение списка активных ассистентов.

        Args:
            user_id: Фильтр по user_id (опционально)

        Returns:
            Список активных ассистентов
        """
        cursor = self.conn.cursor()

        if user_id is not None:
            cursor.execute(
                "SELECT * FROM assistants WHERE user_id = ? AND status = 'active'",
                (user_id,)
            )
        else:
            cursor.execute("SELECT * FROM assistants WHERE status = 'active'")

        rows = cursor.fetchall()
        return [self._row_to_assistant(row) for row in rows]

    def get_user_assistants(self, user_id: int) -> List[Assistant]:
        """
        Получение всех ассистентов пользователя.

        Args:
            user_id: Telegram user_id

        Returns:
            Список ассистентов пользователя
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM assistants WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        return [self._row_to_assistant(row) for row in rows]

    def update_assistant_status(self, assistant_id: str, status: str) -> bool:
        """
        Обновление статуса ассистента.

        Args:
            assistant_id: ID ассистента
            status: Новый статус ('active', 'stopped', 'error')

        Returns:
            True, если обновление успешно
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE assistants SET status = ? WHERE assistant_id = ?",
                (status, assistant_id)
            )
            self.conn.commit()

            logger.info(f"Статус ассистента {assistant_id} обновлен на {status}")
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Ошибка обновления статуса ассистента {assistant_id}: {e}")
            return False

    def update_scheduler_job_id(self, assistant_id: str, job_id: str) -> bool:
        """
        Обновление scheduler_job_id ассистента.

        Args:
            assistant_id: ID ассистента
            job_id: ID задачи в APScheduler

        Returns:
            True, если обновление успешно
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE assistants SET scheduler_job_id = ? WHERE assistant_id = ?",
                (job_id, assistant_id)
            )
            self.conn.commit()

            logger.info(f"Scheduler job ID для ассистента {assistant_id} обновлен: {job_id}")
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Ошибка обновления scheduler_job_id: {e}")
            return False

    def update_last_run(self, assistant_id: str, last_run_at: datetime, next_run_at: Optional[datetime] = None) -> bool:
        """
        Обновление времени последнего и следующего запуска.

        Args:
            assistant_id: ID ассистента
            last_run_at: Время последнего запуска
            next_run_at: Время следующего запуска (опционально)

        Returns:
            True, если обновление успешно
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE assistants SET last_run_at = ?, next_run_at = ? WHERE assistant_id = ?",
                (last_run_at, next_run_at, assistant_id)
            )
            self.conn.commit()

            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Ошибка обновления времени запуска: {e}")
            return False

    def count_user_active_assistants(self, user_id: int) -> int:
        """
        Подсчёт количества активных ассистентов пользователя.

        Args:
            user_id: Telegram user_id

        Returns:
            Количество активных ассистентов
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM assistants WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        return cursor.fetchone()[0]

    def delete_assistant(self, assistant_id: str) -> bool:
        """
        Удаление ассистента из базы данных.

        Args:
            assistant_id: ID ассистента

        Returns:
            True, если удаление успешно
        """
        try:
            cursor = self.conn.cursor()

            # Удаляем связанные записи из execution_history
            cursor.execute(
                "DELETE FROM execution_history WHERE assistant_id = ?",
                (assistant_id,)
            )

            # Удаляем ассистента
            cursor.execute(
                "DELETE FROM assistants WHERE assistant_id = ?",
                (assistant_id,)
            )

            self.conn.commit()

            logger.info(f"Ассистент {assistant_id} удалён из БД")
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Ошибка удаления ассистента {assistant_id}: {e}")
            return False

    # ==================== CRUD для Execution History ====================

    def save_execution(
        self,
        assistant_id: str,
        started_at: datetime,
        completed_at: Optional[datetime],
        status: str,
        messages_count: int = 0,
        summary_sent: bool = False,
        error_message: Optional[str] = None
    ) -> Optional[int]:
        """
        Сохранение записи истории выполнения.

        Args:
            assistant_id: ID ассистента
            started_at: Время начала
            completed_at: Время завершения
            status: Статус ('success', 'error', 'no_messages')
            messages_count: Количество обработанных сообщений
            summary_sent: Была ли отправлена сводка
            error_message: Текст ошибки (если есть)

        Returns:
            ID созданной записи или None в случае ошибки
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO execution_history (
                    assistant_id, started_at, completed_at, status,
                    messages_count, summary_sent, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                assistant_id,
                started_at,
                completed_at,
                status,
                messages_count,
                summary_sent,
                error_message
            ))

            self.conn.commit()
            execution_id = cursor.lastrowid

            logger.info(f"Сохранена история выполнения {execution_id} для ассистента {assistant_id}")
            return execution_id

        except Exception as e:
            logger.error(f"Ошибка сохранения истории выполнения: {e}")
            return None

    def get_execution_history(self, assistant_id: str, limit: int = 10) -> List[ExecutionHistory]:
        """
        Получение истории выполнения для ассистента.

        Args:
            assistant_id: ID ассистента
            limit: Максимальное количество записей

        Returns:
            Список объектов ExecutionHistory
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM execution_history
            WHERE assistant_id = ?
            ORDER BY started_at DESC
            LIMIT ?
        """, (assistant_id, limit))

        rows = cursor.fetchall()
        return [self._row_to_execution_history(row) for row in rows]

    # ==================== CRUD для Chat Metadata ====================

    def save_chat_metadata(
        self,
        chat_id: str,
        chat_type: Optional[str],
        title: Optional[str],
        username: Optional[str],
        member_count: Optional[int],
        access_valid: bool = True
    ) -> bool:
        """
        Сохранение или обновление метаданных чата.

        Args:
            chat_id: ID чата
            chat_type: Тип чата
            title: Название
            username: Username
            member_count: Количество участников
            access_valid: Валиден ли доступ

        Returns:
            True, если операция успешна
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now()

            cursor.execute("""
                INSERT OR REPLACE INTO chat_metadata (
                    chat_id, chat_type, title, username, member_count,
                    last_checked, access_valid
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chat_id, chat_type, title, username, member_count, now, access_valid))

            self.conn.commit()
            logger.info(f"Метаданные чата {chat_id} сохранены")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения метаданных чата: {e}")
            return False

    def get_chat_metadata(self, chat_id: str) -> Optional[ChatMetadata]:
        """
        Получение метаданных чата.

        Args:
            chat_id: ID чата

        Returns:
            Объект ChatMetadata или None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM chat_metadata WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_chat_metadata(row)
        return None

    # ==================== Вспомогательные методы ====================

    def _row_to_assistant(self, row: sqlite3.Row) -> Assistant:
        """Преобразование строки БД в объект Assistant."""
        return Assistant(
            id=row['id'],
            assistant_id=row['assistant_id'],
            user_id=row['user_id'],
            chat_id=row['chat_id'],
            chat_name=row['chat_name'],
            interval_type=row['interval_type'],
            interval_value=row['interval_value'],
            custom_prompt=row['custom_prompt'],
            status=row['status'],
            scheduler_job_id=row['scheduler_job_id'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            last_run_at=datetime.fromisoformat(row['last_run_at']) if row['last_run_at'] else None,
            next_run_at=datetime.fromisoformat(row['next_run_at']) if row['next_run_at'] else None
        )

    def _row_to_execution_history(self, row: sqlite3.Row) -> ExecutionHistory:
        """Преобразование строки БД в объект ExecutionHistory."""
        return ExecutionHistory(
            id=row['id'],
            assistant_id=row['assistant_id'],
            started_at=datetime.fromisoformat(row['started_at']),
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            status=row['status'],
            messages_count=row['messages_count'],
            summary_sent=bool(row['summary_sent']),
            error_message=row['error_message']
        )

    def _row_to_chat_metadata(self, row: sqlite3.Row) -> ChatMetadata:
        """Преобразование строки БД в объект ChatMetadata."""
        return ChatMetadata(
            chat_id=row['chat_id'],
            chat_type=row['chat_type'],
            title=row['title'],
            username=row['username'],
            member_count=row['member_count'],
            last_checked=datetime.fromisoformat(row['last_checked']) if row['last_checked'] else None,
            access_valid=bool(row['access_valid'])
        )

    def close(self) -> None:
        """Закрытие соединения с базой данных."""
        if self.conn:
            self.conn.close()
            logger.info("Соединение с базой данных закрыто")

    def __del__(self):
        """Деструктор для автоматического закрытия соединения."""
        self.close()
