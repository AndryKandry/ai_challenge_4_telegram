"""
Модуль управления состоянием пользователей для режима сравнения RAG.
Хранит настройки режима сравнения для каждого пользователя.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UserRAGState:
    """Состояние режима RAG для пользователя."""

    user_id: int
    rag_comparison_mode: bool = False
    last_comparison_time: Optional[datetime] = None
    statistics: Dict = field(default_factory=lambda: {
        'total_comparisons': 0,
        'rag_helpful': 0,
        'rag_not_helpful': 0
    })


class RAGStateManager:
    """Менеджер состояний режима сравнения RAG для пользователей."""

    def __init__(self):
        """Инициализация менеджера состояний."""
        self._states: Dict[int, UserRAGState] = {}
        logger.info("RAGStateManager initialized")

    def get_state(self, user_id: int) -> UserRAGState:
        """
        Получить состояние пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Состояние пользователя
        """
        if user_id not in self._states:
            self._states[user_id] = UserRAGState(user_id=user_id)
            logger.debug(f"Created new state for user {user_id}")

        return self._states[user_id]

    def is_comparison_mode(self, user_id: int) -> bool:
        """
        Проверить, включен ли режим сравнения для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            True если режим сравнения включен
        """
        state = self.get_state(user_id)
        return state.rag_comparison_mode

    def toggle_comparison_mode(self, user_id: int) -> bool:
        """
        Переключить режим сравнения для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Новое состояние режима (True = включен, False = выключен)
        """
        state = self.get_state(user_id)
        state.rag_comparison_mode = not state.rag_comparison_mode

        mode_str = "включен" if state.rag_comparison_mode else "выключен"
        logger.info(f"User {user_id}: RAG comparison mode {mode_str}")

        return state.rag_comparison_mode

    def set_comparison_mode(self, user_id: int, enabled: bool) -> None:
        """
        Установить режим сравнения для пользователя.

        Args:
            user_id: ID пользователя
            enabled: True для включения, False для выключения
        """
        state = self.get_state(user_id)
        state.rag_comparison_mode = enabled

        mode_str = "включен" if enabled else "выключен"
        logger.info(f"User {user_id}: RAG comparison mode {mode_str}")

    def record_comparison(self, user_id: int, rag_helpful: Optional[bool] = None) -> None:
        """
        Записать факт сравнения в статистику.

        Args:
            user_id: ID пользователя
            rag_helpful: True если RAG был полезен, False если нет, None если неизвестно
        """
        state = self.get_state(user_id)
        state.last_comparison_time = datetime.now()
        state.statistics['total_comparisons'] += 1

        if rag_helpful is True:
            state.statistics['rag_helpful'] += 1
        elif rag_helpful is False:
            state.statistics['rag_not_helpful'] += 1

        logger.debug(f"Recorded comparison for user {user_id}: rag_helpful={rag_helpful}")

    def get_statistics(self, user_id: int) -> Dict:
        """
        Получить статистику сравнений для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой
        """
        state = self.get_state(user_id)

        stats = state.statistics.copy()
        stats['last_comparison_time'] = state.last_comparison_time
        stats['comparison_mode_enabled'] = state.rag_comparison_mode

        # Рассчитываем процент полезности RAG
        total = stats['total_comparisons']
        if total > 0:
            helpful = stats['rag_helpful']
            stats['rag_helpful_percentage'] = (helpful / total) * 100
        else:
            stats['rag_helpful_percentage'] = 0

        return stats

    def reset_statistics(self, user_id: int) -> None:
        """
        Сбросить статистику для пользователя.

        Args:
            user_id: ID пользователя
        """
        state = self.get_state(user_id)
        state.statistics = {
            'total_comparisons': 0,
            'rag_helpful': 0,
            'rag_not_helpful': 0
        }
        state.last_comparison_time = None

        logger.info(f"Reset statistics for user {user_id}")

    def clear_user_state(self, user_id: int) -> None:
        """
        Полностью очистить состояние пользователя.

        Args:
            user_id: ID пользователя
        """
        if user_id in self._states:
            del self._states[user_id]
            logger.info(f"Cleared state for user {user_id}")

    def get_all_active_users(self) -> list:
        """
        Получить список всех пользователей с включенным режимом сравнения.

        Returns:
            Список ID пользователей
        """
        active_users = [
            user_id for user_id, state in self._states.items()
            if state.rag_comparison_mode
        ]
        return active_users

    def get_total_users(self) -> int:
        """
        Получить общее количество пользователей в системе.

        Returns:
            Количество пользователей
        """
        return len(self._states)
