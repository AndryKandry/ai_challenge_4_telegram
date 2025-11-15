#!/usr/bin/env python3
"""
Менеджер долговременной памяти для Telegram-бота.
Обеспечивает хранение и извлечение истории диалогов, промежуточных результатов,
действий агента и базы знаний в SQLite базе данных.
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class MemoryManager:
    """
    Менеджер долговременной памяти на базе SQLite.

    Обеспечивает потокобезопасное сохранение и извлечение:
    - Истории диалогов
    - Промежуточных результатов работы агента
    - Логов действий агента
    - Базы знаний о пользователях
    - Метаданных сессий
    """

    def __init__(self, db_path: str = "agent_memory.db"):
        """
        Инициализация менеджера памяти.

        Args:
            db_path: Путь к файлу базы данных SQLite
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()

        # Создание директории для БД, если не существует
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            self.logger.info(f"Создана директория для БД: {db_dir}")

        self.logger.info(f"Инициализация MemoryManager с БД: {db_path}")

    @contextmanager
    def _get_connection(self):
        """
        Контекстный менеджер для управления подключениями к БД.
        Обеспечивает автоматическое закрытие соединения и коммит транзакций.

        Yields:
            sqlite3.Connection: Объект подключения к БД
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # Для получения результатов как словарей
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Ошибка при работе с БД: {e}", exc_info=True)
            raise
        finally:
            if conn:
                conn.close()

    def create_tables(self) -> None:
        """
        Создание структуры таблиц в БД.
        Выполняет SQL скрипт из файла schema.sql.
        """
        with self._lock:
            try:
                # Поиск файла schema.sql
                schema_path = Path(__file__).parent / "schema.sql"

                if not schema_path.exists():
                    self.logger.error(f"Файл схемы не найден: {schema_path}")
                    raise FileNotFoundError(f"Файл schema.sql не найден: {schema_path}")

                # Чтение и выполнение SQL скрипта
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()

                with self._get_connection() as conn:
                    conn.executescript(schema_sql)
                    self.logger.info("Структура БД успешно создана")

            except Exception as e:
                self.logger.error(f"Ошибка при создании таблиц: {e}", exc_info=True)
                raise

    # ========================================================================
    # РАБОТА С СООБЩЕНИЯМИ
    # ========================================================================

    def save_message(
        self,
        user_id: int,
        chat_id: int,
        message: str,
        message_type: str,
        session_id: Optional[str] = None
    ) -> int:
        """
        Сохранение сообщения в историю диалога.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram
            message: Текст сообщения
            message_type: Тип сообщения ('user' или 'assistant')
            session_id: ID сессии (опционально)

        Returns:
            ID созданной записи

        Raises:
            ValueError: Если message_type не 'user' или 'assistant'
        """
        if message_type not in ('user', 'assistant'):
            raise ValueError(f"Неверный тип сообщения: {message_type}. Ожидается 'user' или 'assistant'")

        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO conversations (user_id, chat_id, message_text, message_type, session_id)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (user_id, chat_id, message, message_type, session_id)
                    )
                    message_id = cursor.lastrowid
                    self.logger.debug(
                        f"Сохранено сообщение #{message_id} от пользователя {user_id}, "
                        f"тип: {message_type}, длина: {len(message)}"
                    )
                    return message_id

            except Exception as e:
                self.logger.error(f"Ошибка при сохранении сообщения: {e}", exc_info=True)
                raise

    def get_conversation_history(
        self,
        user_id: int,
        chat_id: int,
        limit: int = 10,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение истории диалога для пользователя.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram
            limit: Максимальное количество сообщений (по умолчанию 10)
            session_id: ID сессии для фильтрации (опционально)

        Returns:
            Список словарей с сообщениями, отсортированных от старых к новым
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    if session_id:
                        query = """
                            SELECT id, user_id, chat_id, message_text, message_type,
                                   timestamp, session_id
                            FROM conversations
                            WHERE user_id = ? AND chat_id = ? AND session_id = ?
                            ORDER BY timestamp DESC
                            LIMIT ?
                        """
                        params = (user_id, chat_id, session_id, limit)
                    else:
                        query = """
                            SELECT id, user_id, chat_id, message_text, message_type,
                                   timestamp, session_id
                            FROM conversations
                            WHERE user_id = ? AND chat_id = ?
                            ORDER BY timestamp DESC
                            LIMIT ?
                        """
                        params = (user_id, chat_id, limit)

                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()

                    # Преобразуем в список словарей и разворачиваем (от старых к новым)
                    messages = [dict(row) for row in rows]
                    messages.reverse()

                    self.logger.debug(
                        f"Получено {len(messages)} сообщений для пользователя {user_id}, чат {chat_id}"
                    )
                    return messages

            except Exception as e:
                self.logger.error(f"Ошибка при получении истории диалога: {e}", exc_info=True)
                return []

    # ========================================================================
    # РАБОТА С ПРОМЕЖУТОЧНЫМИ РЕЗУЛЬТАТАМИ
    # ========================================================================

    def save_intermediate_result(
        self,
        user_id: int,
        chat_id: int,
        task_name: str,
        result_data: Any,
        status: str = 'pending'
    ) -> int:
        """
        Сохранение промежуточного результата работы агента.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram
            task_name: Название задачи
            result_data: Данные результата (будут сериализованы в JSON)
            status: Статус ('pending', 'completed', 'failed')

        Returns:
            ID созданной записи

        Raises:
            ValueError: Если status не является допустимым значением
        """
        if status not in ('pending', 'completed', 'failed'):
            raise ValueError(f"Неверный статус: {status}. Ожидается 'pending', 'completed' или 'failed'")

        with self._lock:
            try:
                # Сериализация данных в JSON
                if isinstance(result_data, str):
                    data_str = result_data
                else:
                    data_str = json.dumps(result_data, ensure_ascii=False)

                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO intermediate_results
                        (user_id, chat_id, task_name, result_data, status)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (user_id, chat_id, task_name, data_str, status)
                    )
                    result_id = cursor.lastrowid
                    self.logger.debug(
                        f"Сохранен промежуточный результат #{result_id} для задачи '{task_name}', статус: {status}"
                    )
                    return result_id

            except Exception as e:
                self.logger.error(f"Ошибка при сохранении промежуточного результата: {e}", exc_info=True)
                raise

    def get_intermediate_results(
        self,
        user_id: int,
        chat_id: int,
        task_name: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение промежуточных результатов.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram
            task_name: Фильтр по названию задачи (опционально)
            status: Фильтр по статусу (опционально)

        Returns:
            Список словарей с результатами
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    query = """
                        SELECT id, user_id, chat_id, task_name, result_data, status,
                               created_at, updated_at
                        FROM intermediate_results
                        WHERE user_id = ? AND chat_id = ?
                    """
                    params = [user_id, chat_id]

                    if task_name:
                        query += " AND task_name = ?"
                        params.append(task_name)

                    if status:
                        query += " AND status = ?"
                        params.append(status)

                    query += " ORDER BY updated_at DESC"

                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()

                    results = []
                    for row in rows:
                        result = dict(row)
                        # Попытка десериализации JSON
                        try:
                            result['result_data'] = json.loads(result['result_data'])
                        except (json.JSONDecodeError, TypeError):
                            pass  # Оставляем как строку
                        results.append(result)

                    self.logger.debug(f"Получено {len(results)} промежуточных результатов")
                    return results

            except Exception as e:
                self.logger.error(f"Ошибка при получении промежуточных результатов: {e}", exc_info=True)
                return []

    def update_intermediate_result_status(
        self,
        result_id: int,
        status: str,
        result_data: Optional[Any] = None
    ) -> bool:
        """
        Обновление статуса промежуточного результата.

        Args:
            result_id: ID результата
            status: Новый статус ('pending', 'completed', 'failed')
            result_data: Обновленные данные результата (опционально)

        Returns:
            True если обновление успешно, False иначе

        Raises:
            ValueError: Если status не является допустимым значением
        """
        if status not in ('pending', 'completed', 'failed'):
            raise ValueError(f"Неверный статус: {status}")

        with self._lock:
            try:
                with self._get_connection() as conn:
                    if result_data is not None:
                        if isinstance(result_data, str):
                            data_str = result_data
                        else:
                            data_str = json.dumps(result_data, ensure_ascii=False)

                        cursor = conn.execute(
                            """
                            UPDATE intermediate_results
                            SET status = ?, result_data = ?
                            WHERE id = ?
                            """,
                            (status, data_str, result_id)
                        )
                    else:
                        cursor = conn.execute(
                            """
                            UPDATE intermediate_results
                            SET status = ?
                            WHERE id = ?
                            """,
                            (status, result_id)
                        )

                    success = cursor.rowcount > 0
                    if success:
                        self.logger.debug(f"Обновлен статус результата #{result_id} на '{status}'")
                    return success

            except Exception as e:
                self.logger.error(f"Ошибка при обновлении статуса результата: {e}", exc_info=True)
                return False

    # ========================================================================
    # РАБОТА С ДЕЙСТВИЯМИ АГЕНТА
    # ========================================================================

    def save_action(
        self,
        user_id: int,
        chat_id: int,
        action_type: str,
        description: Optional[str] = None,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        execution_time: Optional[int] = None
    ) -> int:
        """
        Сохранение записи о действии агента.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram
            action_type: Тип действия (например, 'api_call', 'parsing', 'generation')
            description: Описание действия
            input_data: Входные данные (будут сериализованы в JSON)
            output_data: Выходные данные (будут сериализованы в JSON)
            execution_time: Время выполнения в миллисекундах

        Returns:
            ID созданной записи
        """
        with self._lock:
            try:
                # Сериализация данных
                input_str = json.dumps(input_data, ensure_ascii=False) if input_data is not None else None
                output_str = json.dumps(output_data, ensure_ascii=False) if output_data is not None else None

                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO agent_actions
                        (user_id, chat_id, action_type, action_description,
                         input_data, output_data, execution_time_ms)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, chat_id, action_type, description,
                         input_str, output_str, execution_time)
                    )
                    action_id = cursor.lastrowid
                    self.logger.debug(
                        f"Сохранено действие #{action_id} типа '{action_type}' для пользователя {user_id}"
                    )
                    return action_id

            except Exception as e:
                self.logger.error(f"Ошибка при сохранении действия агента: {e}", exc_info=True)
                raise

    def get_actions_history(
        self,
        user_id: int,
        chat_id: int,
        action_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получение истории действий агента.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram
            action_type: Фильтр по типу действия (опционально)
            limit: Максимальное количество записей

        Returns:
            Список словарей с действиями
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    if action_type:
                        query = """
                            SELECT id, user_id, chat_id, action_type, action_description,
                                   input_data, output_data, timestamp, execution_time_ms
                            FROM agent_actions
                            WHERE user_id = ? AND chat_id = ? AND action_type = ?
                            ORDER BY timestamp DESC
                            LIMIT ?
                        """
                        params = (user_id, chat_id, action_type, limit)
                    else:
                        query = """
                            SELECT id, user_id, chat_id, action_type, action_description,
                                   input_data, output_data, timestamp, execution_time_ms
                            FROM agent_actions
                            WHERE user_id = ? AND chat_id = ?
                            ORDER BY timestamp DESC
                            LIMIT ?
                        """
                        params = (user_id, chat_id, limit)

                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()

                    actions = []
                    for row in rows:
                        action = dict(row)
                        # Десериализация JSON данных
                        for field in ['input_data', 'output_data']:
                            if action[field]:
                                try:
                                    action[field] = json.loads(action[field])
                                except (json.JSONDecodeError, TypeError):
                                    pass
                        actions.append(action)

                    self.logger.debug(f"Получено {len(actions)} действий агента")
                    return actions

            except Exception as e:
                self.logger.error(f"Ошибка при получении истории действий: {e}", exc_info=True)
                return []

    # ========================================================================
    # РАБОТА С БАЗОЙ ЗНАНИЙ
    # ========================================================================

    def save_knowledge(
        self,
        user_id: int,
        entity_type: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source_message_id: Optional[int] = None
    ) -> int:
        """
        Сохранение факта в базу знаний.

        Args:
            user_id: ID пользователя Telegram
            entity_type: Тип сущности (например, 'preference', 'fact', 'name')
            key: Ключ сущности
            value: Значение сущности
            confidence: Уверенность в факте (0.0 - 1.0)
            source_message_id: ID исходного сообщения

        Returns:
            ID созданной или обновленной записи
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO knowledge_base
                        (user_id, entity_type, entity_key, entity_value,
                         confidence_score, source_message_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, entity_type, key, value, confidence, source_message_id)
                    )
                    knowledge_id = cursor.lastrowid
                    self.logger.debug(
                        f"Сохранен факт #{knowledge_id} типа '{entity_type}' "
                        f"для пользователя {user_id}: {key} = {value}"
                    )
                    return knowledge_id

            except Exception as e:
                self.logger.error(f"Ошибка при сохранении знания: {e}", exc_info=True)
                raise

    def get_knowledge(
        self,
        user_id: int,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение знаний о пользователе из базы.

        Args:
            user_id: ID пользователя Telegram
            entity_type: Фильтр по типу сущности (опционально)

        Returns:
            Список словарей с фактами
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    if entity_type:
                        query = """
                            SELECT id, user_id, entity_type, entity_key, entity_value,
                                   confidence_score, source_message_id, created_at, updated_at
                            FROM knowledge_base
                            WHERE user_id = ? AND entity_type = ?
                            ORDER BY updated_at DESC
                        """
                        params = (user_id, entity_type)
                    else:
                        query = """
                            SELECT id, user_id, entity_type, entity_key, entity_value,
                                   confidence_score, source_message_id, created_at, updated_at
                            FROM knowledge_base
                            WHERE user_id = ?
                            ORDER BY updated_at DESC
                        """
                        params = (user_id,)

                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()
                    knowledge = [dict(row) for row in rows]

                    self.logger.debug(f"Получено {len(knowledge)} фактов о пользователе {user_id}")
                    return knowledge

            except Exception as e:
                self.logger.error(f"Ошибка при получении знаний: {e}", exc_info=True)
                return []

    # ========================================================================
    # РАБОТА С СЕССИЯМИ
    # ========================================================================

    def create_session(self, user_id: int, chat_id: int) -> str:
        """
        Создание новой сессии.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram

        Returns:
            ID созданной сессии (UUID)
        """
        with self._lock:
            try:
                session_id = str(uuid.uuid4())

                with self._get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO sessions (session_id, user_id, chat_id, status)
                        VALUES (?, ?, ?, 'active')
                        """,
                        (session_id, user_id, chat_id)
                    )
                    self.logger.info(f"Создана новая сессия {session_id} для пользователя {user_id}")
                    return session_id

            except Exception as e:
                self.logger.error(f"Ошибка при создании сессии: {e}", exc_info=True)
                raise

    def end_session(self, session_id: str) -> bool:
        """
        Завершение сессии.

        Args:
            session_id: ID сессии

        Returns:
            True если сессия успешно завершена, False иначе
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        UPDATE sessions
                        SET status = 'inactive', ended_at = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                        """,
                        (session_id,)
                    )
                    success = cursor.rowcount > 0
                    if success:
                        self.logger.info(f"Завершена сессия {session_id}")
                    return success

            except Exception as e:
                self.logger.error(f"Ошибка при завершении сессии: {e}", exc_info=True)
                return False

    def get_active_session(self, user_id: int, chat_id: int) -> Optional[str]:
        """
        Получение ID активной сессии для пользователя.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram

        Returns:
            ID активной сессии или None, если нет активной сессии
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        SELECT session_id
                        FROM sessions
                        WHERE user_id = ? AND chat_id = ? AND status = 'active'
                        ORDER BY started_at DESC
                        LIMIT 1
                        """,
                        (user_id, chat_id)
                    )
                    row = cursor.fetchone()
                    return row['session_id'] if row else None

            except Exception as e:
                self.logger.error(f"Ошибка при получении активной сессии: {e}", exc_info=True)
                return None

    # ========================================================================
    # СЛУЖЕБНЫЕ МЕТОДЫ
    # ========================================================================

    def get_statistics(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Получение статистики по базе данных.

        Args:
            user_id: ID пользователя для персональной статистики (опционально)

        Returns:
            Словарь со статистикой
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    stats = {}

                    if user_id:
                        # Статистика для конкретного пользователя
                        cursor = conn.execute(
                            "SELECT COUNT(*) as count FROM conversations WHERE user_id = ?",
                            (user_id,)
                        )
                        stats['messages_count'] = cursor.fetchone()['count']

                        cursor = conn.execute(
                            "SELECT COUNT(*) as count FROM intermediate_results WHERE user_id = ?",
                            (user_id,)
                        )
                        stats['intermediate_results_count'] = cursor.fetchone()['count']

                        cursor = conn.execute(
                            "SELECT COUNT(*) as count FROM agent_actions WHERE user_id = ?",
                            (user_id,)
                        )
                        stats['actions_count'] = cursor.fetchone()['count']

                        cursor = conn.execute(
                            "SELECT COUNT(*) as count FROM knowledge_base WHERE user_id = ?",
                            (user_id,)
                        )
                        stats['knowledge_count'] = cursor.fetchone()['count']

                        cursor = conn.execute(
                            "SELECT COUNT(*) as count FROM sessions WHERE user_id = ? AND status = 'active'",
                            (user_id,)
                        )
                        stats['active_sessions'] = cursor.fetchone()['count']

                    else:
                        # Общая статистика
                        cursor = conn.execute("SELECT COUNT(*) as count FROM conversations")
                        stats['total_messages'] = cursor.fetchone()['count']

                        cursor = conn.execute("SELECT COUNT(DISTINCT user_id) as count FROM conversations")
                        stats['unique_users'] = cursor.fetchone()['count']

                        cursor = conn.execute("SELECT COUNT(*) as count FROM intermediate_results")
                        stats['total_intermediate_results'] = cursor.fetchone()['count']

                        cursor = conn.execute("SELECT COUNT(*) as count FROM agent_actions")
                        stats['total_actions'] = cursor.fetchone()['count']

                        cursor = conn.execute("SELECT COUNT(*) as count FROM knowledge_base")
                        stats['total_knowledge'] = cursor.fetchone()['count']

                        cursor = conn.execute("SELECT COUNT(*) as count FROM sessions WHERE status = 'active'")
                        stats['active_sessions'] = cursor.fetchone()['count']

                    return stats

            except Exception as e:
                self.logger.error(f"Ошибка при получении статистики: {e}", exc_info=True)
                return {}

    def clear_user_history(self, user_id: int, chat_id: int) -> bool:
        """
        Очистка истории диалога для пользователя.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram

        Returns:
            True если очистка успешна, False иначе
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        "DELETE FROM conversations WHERE user_id = ? AND chat_id = ?",
                        (user_id, chat_id)
                    )
                    self.logger.info(f"Очищена история диалога для пользователя {user_id}, чат {chat_id}")
                    return True

            except Exception as e:
                self.logger.error(f"Ошибка при очистке истории: {e}", exc_info=True)
                return False

    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """
        Очистка старых данных из базы.

        Args:
            days: Количество дней для хранения данных (по умолчанию 30)

        Returns:
            Словарь с количеством удаленных записей по каждой таблице
        """
        with self._lock:
            try:
                cutoff_date = datetime.now() - timedelta(days=days)
                deleted = {}

                with self._get_connection() as conn:
                    # Удаление старых сообщений
                    cursor = conn.execute(
                        "DELETE FROM conversations WHERE timestamp < ?",
                        (cutoff_date,)
                    )
                    deleted['conversations'] = cursor.rowcount

                    # Удаление старых промежуточных результатов
                    cursor = conn.execute(
                        "DELETE FROM intermediate_results WHERE created_at < ?",
                        (cutoff_date,)
                    )
                    deleted['intermediate_results'] = cursor.rowcount

                    # Удаление старых действий
                    cursor = conn.execute(
                        "DELETE FROM agent_actions WHERE timestamp < ?",
                        (cutoff_date,)
                    )
                    deleted['agent_actions'] = cursor.rowcount

                    # Удаление завершенных сессий старше cutoff_date
                    cursor = conn.execute(
                        "DELETE FROM sessions WHERE status = 'inactive' AND ended_at < ?",
                        (cutoff_date,)
                    )
                    deleted['sessions'] = cursor.rowcount

                    self.logger.info(f"Удалены старые данные (старше {days} дней): {deleted}")
                    return deleted

            except Exception as e:
                self.logger.error(f"Ошибка при очистке старых данных: {e}", exc_info=True)
                return {}

    def export_conversation_history(
        self,
        user_id: int,
        chat_id: int,
        format: str = 'json'
    ) -> Optional[str]:
        """
        Экспорт истории диалога в различных форматах.

        Args:
            user_id: ID пользователя Telegram
            chat_id: ID чата Telegram
            format: Формат экспорта ('json', 'text', 'csv')

        Returns:
            Строка с экспортированными данными или None в случае ошибки
        """
        try:
            messages = self.get_conversation_history(user_id, chat_id, limit=1000)

            if format == 'json':
                return json.dumps(messages, ensure_ascii=False, indent=2)

            elif format == 'text':
                lines = []
                for msg in messages:
                    timestamp = msg['timestamp']
                    msg_type = "Пользователь" if msg['message_type'] == 'user' else "Ассистент"
                    text = msg['message_text']
                    lines.append(f"[{timestamp}] {msg_type}: {text}\n")
                return "\n".join(lines)

            elif format == 'csv':
                import csv
                from io import StringIO

                output = StringIO()
                writer = csv.DictWriter(
                    output,
                    fieldnames=['id', 'timestamp', 'message_type', 'message_text']
                )
                writer.writeheader()
                for msg in messages:
                    writer.writerow({
                        'id': msg['id'],
                        'timestamp': msg['timestamp'],
                        'message_type': msg['message_type'],
                        'message_text': msg['message_text']
                    })
                return output.getvalue()

            else:
                self.logger.error(f"Неизвестный формат экспорта: {format}")
                return None

        except Exception as e:
            self.logger.error(f"Ошибка при экспорте истории: {e}", exc_info=True)
            return None
