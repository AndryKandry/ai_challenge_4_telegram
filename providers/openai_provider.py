"""
Провайдер для работы с OpenAI GPT API.

Реализует интерфейс LLMProvider для работы с моделями OpenAI
(GPT-3.5, GPT-4 и другими).
"""

import logging
from typing import Optional, List, Dict

from openai import AsyncOpenAI
from openai import OpenAIError, APIConnectionError, RateLimitError, APIStatusError

from .base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    Провайдер для работы с OpenAI GPT API.

    Использует официальную библиотеку openai для асинхронного взаимодействия
    с API OpenAI.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        timeout: int = 30,
        temperature: float = 0.9,
        max_tokens: int = 2000
    ):
        """
        Инициализация OpenAI провайдера.

        Args:
            api_key: API ключ OpenAI
            model: Название модели (по умолчанию gpt-3.5-turbo)
            timeout: Таймаут запроса в секундах
            temperature: Температура генерации (0.0-2.0)
            max_tokens: Максимальное количество токенов в ответе
        """
        super().__init__(api_key, timeout)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Создаём асинхронный клиент OpenAI
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout
        )

        logger.info(f"OpenAI Provider инициализирован с моделью {model}")

    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Генерация ответа от OpenAI GPT.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога

        Returns:
            Ответ от OpenAI или None в случае ошибки
        """
        try:
            # Формируем список сообщений
            messages = [
                {"role": "system", "content": system_prompt}
            ]

            # Добавляем историю диалога
            if conversation_history:
                formatted_history = self._format_conversation_history(conversation_history)
                messages.extend(formatted_history)

            # Добавляем текущее сообщение пользователя
            messages.append({"role": "user", "content": user_message})

            logger.info(f"Отправка запроса в OpenAI API (модель: {self.model})")
            logger.debug(f"Количество сообщений в контексте: {len(messages)}")

            # Отправляем запрос к OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # Извлекаем ответ
            if response.choices and len(response.choices) > 0:
                assistant_message = response.choices[0].message.content
                logger.info("Получен ответ от OpenAI API")
                logger.debug(f"Длина ответа: {len(assistant_message) if assistant_message else 0} символов")
                return assistant_message
            else:
                logger.error("OpenAI вернул пустой список choices")
                return None

        except RateLimitError as e:
            logger.error(f"Превышен лимит запросов к OpenAI API: {e}")
            return None

        except APIConnectionError as e:
            logger.error(f"Ошибка соединения с OpenAI API: {e}")
            return None

        except APIStatusError as e:
            logger.error(f"HTTP ошибка OpenAI API: {e.status_code} - {e.message}")
            return None

        except OpenAIError as e:
            logger.error(f"Ошибка OpenAI API: {e}")
            return None

        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к OpenAI: {e}", exc_info=True)
            return None

    def get_provider_name(self) -> str:
        """
        Получение имени провайдера.

        Returns:
            Строка "openai"
        """
        return "openai"

    def _format_conversation_history(
        self,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """
        Форматирование истории диалога для OpenAI API.

        Преобразует формат из БД в формат OpenAI:
        {"role": "user"|"assistant", "content": "текст сообщения"}

        Args:
            conversation_history: История из БД

        Returns:
            Отформатированная история для OpenAI
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
