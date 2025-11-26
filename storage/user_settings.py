"""
Управление пользовательскими настройками.

Этот модуль обеспечивает хранение и извлечение настроек пользователей,
включая выбор LLM провайдера.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class UserSettings:
    """
    Класс для управления пользовательскими настройками.

    Хранит настройки в SQLite базе данных для персистентности между сессиями.
    """

    def __init__(self, db_path: str = "agent_memory.db"):
        """
        Инициализация менеджера настроек.

        Args:
            db_path: Путь к файлу базы данных SQLite
        """
        self.db_path = db_path
        self._ensure_table_exists()
        logger.info("UserSettings инициализирован")

    def _ensure_table_exists(self) -> None:
        """Создание таблицы настроек, если она не существует."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Сначала создаём таблицу без rag_comparison_enabled
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        user_id INTEGER PRIMARY KEY,
                        selected_provider TEXT NOT NULL DEFAULT 'deepseek',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Создаём индексы для быстрого поиска
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_settings_provider
                    ON user_settings(selected_provider)
                """)

                # Проверяем наличие колонки rag_comparison_enabled и добавляем если нужно
                cursor.execute("PRAGMA table_info(user_settings)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'rag_comparison_enabled' not in columns:
                    cursor.execute("""
                        ALTER TABLE user_settings 
                        ADD COLUMN rag_comparison_enabled BOOLEAN DEFAULT FALSE
                    """)
                    logger.info("Добавлена колонка rag_comparison_enabled в таблицу user_settings")

                # Создаём индекс для rag_comparison_enabled после добавления колонки
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_settings_rag_comparison
                    ON user_settings(rag_comparison_enabled)
                """)

                conn.commit()
                logger.debug("Таблица user_settings проверена/создана")
        except sqlite3.Error as e:
            logger.error(f"Ошибка создания таблицы user_settings: {e}")
            raise

    def get_provider(self, user_id: int) -> str:
        """
        Получить выбранного провайдера для пользователя.

        Args:
            user_id: ID пользователя в Telegram

        Returns:
            Название провайдера ("openai", "yandex" или "deepseek")
            По умолчанию возвращает "deepseek" для новых пользователей
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT selected_provider FROM user_settings WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()

                if result:
                    provider = result[0]
                    logger.debug(f"Провайдер для пользователя {user_id}: {provider}")
                    return provider
                else:
                    # Новый пользователь - возвращаем провайдер по умолчанию
                    logger.debug(f"Новый пользователь {user_id}, провайдер по умолчанию: deepseek")
                    return "deepseek"

        except sqlite3.Error as e:
            logger.error(f"Ошибка получения провайдера для пользователя {user_id}: {e}")
            return "deepseek"  # Fallback на deepseek

    def set_provider(self, user_id: int, provider: str) -> bool:
        """
        Установить провайдера для пользователя.

        Args:
            user_id: ID пользователя в Telegram
            provider: Название провайдера ("openai", "yandex" или "deepseek")

        Returns:
            True если успешно, False в случае ошибки
        """
        # Валидация provider
        if provider not in ["openai", "yandex", "deepseek"]:
            logger.error(f"Недопустимый провайдер: {provider}")
            return False

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Используем UPSERT (INSERT ... ON CONFLICT)
                cursor.execute("""
                    INSERT INTO user_settings (user_id, selected_provider, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        selected_provider = excluded.selected_provider,
                        updated_at = excluded.updated_at
                """, (user_id, provider, datetime.now()))

                conn.commit()
                logger.info(f"Провайдер для пользователя {user_id} установлен: {provider}")
                return True

        except sqlite3.Error as e:
            logger.error(f"Ошибка установки провайдера для пользователя {user_id}: {e}")
            return False

    def get_all_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить все настройки пользователя.

        Args:
            user_id: ID пользователя в Telegram

        Returns:
            Словарь с настройками или None если пользователь не найден
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM user_settings WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()

                if result:
                    return dict(result)
                else:
                    return None

        except sqlite3.Error as e:
            logger.error(f"Ошибка получения настроек для пользователя {user_id}: {e}")
            return None

    def delete_user_settings(self, user_id: int) -> bool:
        """
        Удалить настройки пользователя.

        Args:
            user_id: ID пользователя в Telegram

        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM user_settings WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()

                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Настройки пользователя {user_id} удалены")
                    return True
                else:
                    logger.warning(f"Настройки пользователя {user_id} не найдены для удаления")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Ошибка удаления настроек пользователя {user_id}: {e}")
            return False

    def get_statistics(self) -> Dict[str, int]:
        """
        Получить статистику по использованию провайдеров.

        Returns:
            Словарь со статистикой
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Общее количество пользователей
                cursor.execute("SELECT COUNT(*) FROM user_settings")
                total_users = cursor.fetchone()[0]

                # Количество пользователей OpenAI
                cursor.execute(
                    "SELECT COUNT(*) FROM user_settings WHERE selected_provider = 'openai'"
                )
                openai_users = cursor.fetchone()[0]

                # Количество пользователей Yandex
                cursor.execute(
                    "SELECT COUNT(*) FROM user_settings WHERE selected_provider = 'yandex'"
                )
                yandex_users = cursor.fetchone()[0]

                # Количество пользователей DeepSeek
                cursor.execute(
                    "SELECT COUNT(*) FROM user_settings WHERE selected_provider = 'deepseek'"
                )
                deepseek_users = cursor.fetchone()[0]

                return {
                    "total_users": total_users,
                    "openai_users": openai_users,
                    "yandex_users": yandex_users,
                    "deepseek_users": deepseek_users
                }

        except sqlite3.Error as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {
                "total_users": 0,
                "openai_users": 0,
                "yandex_users": 0,
                "deepseek_users": 0
            }

    def get_rag_comparison_enabled(self, user_id: int) -> bool:
        """
        Получить статус режима сравнения RAG для пользователя.

        Args:
            user_id: ID пользователя в Telegram

        Returns:
            True если режим включен, False в противном случае
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT rag_comparison_enabled FROM user_settings WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()

                if result:
                    enabled = bool(result[0])
                    logger.debug(f"Режим сравнения RAG для пользователя {user_id}: {enabled}")
                    return enabled
                else:
                    # Новый пользователь - режим выключен
                    logger.debug(f"Новый пользователь {user_id}, режим сравнения RAG выключен")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Ошибка получения режима сравнения RAG для пользователя {user_id}: {e}")
            return False  # Fallback на выключенный режим

    def set_rag_comparison_enabled(self, user_id: int, enabled: bool) -> bool:
        """
        Установить статус режима сравнения RAG для пользователя.

        Args:
            user_id: ID пользователя в Telegram
            enabled: True для включения режима, False для выключения

        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Используем UPSERT (INSERT ... ON CONFLICT)
                cursor.execute("""
                    INSERT INTO user_settings (user_id, rag_comparison_enabled, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        rag_comparison_enabled = excluded.rag_comparison_enabled,
                        updated_at = excluded.updated_at
                """, (user_id, enabled, datetime.now()))

                conn.commit()
                logger.info(f"Режим сравнения RAG для пользователя {user_id} установлен: {enabled}")
                return True

        except sqlite3.Error as e:
            logger.error(f"Ошибка установки режима сравнения RAG для пользователя {user_id}: {e}")
            return False

    def toggle_rag_comparison(self, user_id: int) -> bool:
        """
        Переключить режим сравнения RAG (включить/выключить).

        Args:
            user_id: ID пользователя в Telegram

        Returns:
            Новое состояние режима (True если включен, False если выключен)
        """
        current_state = self.get_rag_comparison_enabled(user_id)
        new_state = not current_state
        
        success = self.set_rag_comparison_enabled(user_id, new_state)
        
        if success:
            logger.info(f"Режим сравнения RAG переключен для пользователя {user_id}: {new_state}")
            return new_state
        else:
            logger.error(f"Не удалось переключить режим сравнения RAG для пользователя {user_id}")
            return current_state  # Возвращаем текущее состояние при ошибке
