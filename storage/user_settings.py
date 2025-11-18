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
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        user_id INTEGER PRIMARY KEY,
                        selected_provider TEXT NOT NULL DEFAULT 'deepseek',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Создаём индекс для быстрого поиска
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_settings_provider
                    ON user_settings(selected_provider)
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
