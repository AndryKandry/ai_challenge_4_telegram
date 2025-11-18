"""
Базовый абстрактный класс для провайдеров LLM.

Этот модуль определяет общий интерфейс для работы с различными
LLM провайдерами (OpenAI, Yandex GPT и т.д.).
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict


class LLMProvider(ABC):
    """
    Абстрактный базовый класс для всех LLM провайдеров.

    Определяет унифицированный интерфейс для работы с различными
    языковыми моделями.
    """

    def __init__(self, api_key: str, timeout: int = 30):
        """
        Инициализация провайдера.

        Args:
            api_key: API ключ для доступа к сервису
            timeout: Таймаут запроса в секундах
        """
        self.api_key = api_key
        self.timeout = timeout

    @abstractmethod
    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Генерация ответа от LLM на основе сообщения пользователя.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт для управления поведением модели
            conversation_history: История диалога (опционально)
                Формат: [{"message_text": str, "message_type": "user"|"assistant"}, ...]

        Returns:
            Текстовый ответ от LLM или None в случае ошибки
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Получение имени провайдера.

        Returns:
            Строка с именем провайдера (например, "openai", "yandex")
        """
        pass

    def _format_conversation_history(
        self,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """
        Форматирование истории диалога в унифицированный формат.

        Преобразует историю из формата базы данных в формат,
        подходящий для конкретного провайдера.

        Args:
            conversation_history: История диалога из БД

        Returns:
            Отформатированная история диалога
        """
        if not conversation_history:
            return []

        formatted_history = []
        for msg in conversation_history:
            role = "user" if msg["message_type"] == "user" else "assistant"
            formatted_history.append({
                "role": role,
                "content": msg["message_text"]
            })

        return formatted_history
