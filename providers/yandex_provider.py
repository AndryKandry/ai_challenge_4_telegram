"""
Провайдер для работы с Yandex GPT API.

Реализует интерфейс LLMProvider для работы с моделями Yandex GPT.
"""

import logging
import os
from typing import Optional, List, Dict

import httpx

from .base import LLMProvider

logger = logging.getLogger(__name__)

YANDEX_GPT_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class YandexGPTProvider(LLMProvider):
    """
    Провайдер для работы с Yandex GPT API.

    Использует httpx для асинхронного взаимодействия с API Yandex Cloud.
    """

    def __init__(
        self,
        api_key: str,
        folder_id: Optional[str] = None,
        model: str = "yandexgpt-lite",
        timeout: int = 30,
        temperature: float = 0.9,
        max_tokens: int = 2000
    ):
        """
        Инициализация Yandex GPT провайдера.

        Args:
            api_key: API ключ Yandex Cloud
            folder_id: ID каталога в Yandex Cloud (если None, берётся из env)
            model: Название модели (по умолчанию yandexgpt-lite)
            timeout: Таймаут запроса в секундах
            temperature: Температура генерации (0.0-1.0)
            max_tokens: Максимальное количество токенов в ответе
        """
        super().__init__(api_key, timeout)
        self.folder_id = folder_id or os.getenv('YANDEX_FOLDER_ID', 'folder_id')
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"Yandex GPT Provider инициализирован с моделью {model}")

    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Генерация ответа от Yandex GPT.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога

        Returns:
            Ответ от Yandex GPT или None в случае ошибки
        """
        try:
            # Формируем список сообщений
            messages = [
                {"role": "system", "text": system_prompt}
            ]

            # Добавляем историю диалога
            if conversation_history:
                for msg in conversation_history:
                    role = "user" if msg["message_type"] == "user" else "assistant"
                    messages.append({
                        "role": role,
                        "text": msg["message_text"]
                    })

            # Добавляем текущее сообщение пользователя
            messages.append({
                "role": "user",
                "text": user_message,
            })

            # Формируем payload для Yandex API
            payload = {
                "modelUri": f"gpt://{self.folder_id}/{self.model}",
                "completionOptions": {
                    "stream": False,
                    "temperature": self.temperature,
                    "maxTokens": self.max_tokens,
                },
                "messages": messages,
            }

            logger.info(f"Отправка запроса в Yandex GPT API (модель: {self.model})")
            logger.debug(f"Количество сообщений в контексте: {len(messages)}")

            # Отправляем запрос
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    YANDEX_GPT_API_URL,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()

                # Парсинг ответа
                data = response.json()
                logger.info("Получен ответ от Yandex GPT API")

                # Извлечение текста ответа
                if "result" in data and "alternatives" in data["result"]:
                    alternatives = data["result"]["alternatives"]
                    if alternatives and len(alternatives) > 0:
                        message_text = alternatives[0].get("message", {}).get("text")
                        if message_text:
                            logger.debug(f"Длина ответа: {len(message_text)} символов")
                            return message_text

                logger.error(f"Неожиданная структура ответа: {data}")
                return None

        except httpx.TimeoutException:
            logger.error("Превышен таймаут запроса к Yandex GPT API")
            return None

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка Yandex GPT: {e.response.status_code} - {e.response.text}")
            return None

        except ValueError as e:
            logger.error(f"Ошибка парсинга JSON ответа от Yandex GPT: {e}")
            return None

        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к Yandex GPT: {e}", exc_info=True)
            return None

    def get_provider_name(self) -> str:
        """
        Получение имени провайдера.

        Returns:
            Строка "yandex"
        """
        return "yandex"
