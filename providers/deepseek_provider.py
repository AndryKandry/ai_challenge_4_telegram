"""
Провайдер для работы с DeepSeek API.

DeepSeek использует OpenAI-совместимый API, поэтому реализация
основана на openai библиотеке с кастомным base_url.
"""

import logging
from typing import Optional, List, Dict

from openai import AsyncOpenAI
from openai import OpenAIError, APIConnectionError, RateLimitError, APIStatusError

from .base import LLMProvider

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com"


class DeepSeekProvider(LLMProvider):
    """
    Провайдер для работы с DeepSeek API.

    DeepSeek предоставляет OpenAI-совместимый API, поэтому используем
    библиотеку openai с кастомным base_url.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        timeout: int = 30,
        temperature: float = 0.9,
        max_tokens: int = 2000
    ):
        """
        Инициализация DeepSeek провайдера.

        Args:
            api_key: API ключ DeepSeek
            model: Название модели (по умолчанию deepseek-chat)
            timeout: Таймаут запроса в секундах
            temperature: Температура генерации (0.0-2.0)
            max_tokens: Максимальное количество токенов в ответе
        """
        super().__init__(api_key, timeout)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Создаём асинхронный клиент с кастомным base_url для DeepSeek
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=DEEPSEEK_API_URL,
            timeout=timeout
        )

        logger.info(f"DeepSeek Provider инициализирован с моделью {model}")

    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Генерация ответа от DeepSeek.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога

        Returns:
            Ответ от DeepSeek или None в случае ошибки
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

            logger.info(f"Отправка запроса в DeepSeek API (модель: {self.model})")
            logger.debug(f"Количество сообщений в контексте: {len(messages)}")

            # Отправляем запрос к DeepSeek API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # Извлекаем ответ
            if response.choices and len(response.choices) > 0:
                assistant_message = response.choices[0].message.content
                logger.info("Получен ответ от DeepSeek API")
                logger.debug(f"Длина ответа: {len(assistant_message) if assistant_message else 0} символов")
                return assistant_message
            else:
                logger.error("DeepSeek вернул пустой список choices")
                return None

        except RateLimitError as e:
            logger.error(f"Превышен лимит запросов к DeepSeek API: {e}")
            return None

        except APIConnectionError as e:
            logger.error(f"Ошибка соединения с DeepSeek API: {e}")
            return None

        except APIStatusError as e:
            logger.error(f"HTTP ошибка DeepSeek API: {e.status_code} - {e.message}")
            return None

        except OpenAIError as e:
            logger.error(f"Ошибка DeepSeek API: {e}")
            return None

        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к DeepSeek: {e}", exc_info=True)
            return None

    def get_provider_name(self) -> str:
        """
        Получение имени провайдера.

        Returns:
            Строка "deepseek"
        """
        return "deepseek"

    def _format_conversation_history(
        self,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """
        Форматирование истории диалога для DeepSeek API.

        Использует тот же формат что и OpenAI:
        {"role": "user"|"assistant", "content": "текст сообщения"}

        Args:
            conversation_history: История из БД

        Returns:
            Отформатированная история для DeepSeek
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
