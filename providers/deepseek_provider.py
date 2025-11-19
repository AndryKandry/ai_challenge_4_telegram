"""
Провайдер для работы с DeepSeek API.

DeepSeek использует OpenAI-совместимый API, поэтому реализация
основана на openai библиотеке с кастомным base_url.

Поддерживает:
- Function calling для вызова MCP tools
- Интеграция с GitHub MCP сервером
"""

import logging
from typing import Optional, List, Dict, Any

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
        max_tokens: int = 2000,
        mcp_client: Optional[Any] = None
    ):
        """
        Инициализация DeepSeek провайдера.

        Args:
            api_key: API ключ DeepSeek
            model: Название модели (по умолчанию deepseek-chat)
            timeout: Таймаут запроса в секундах
            temperature: Температура генерации (0.0-2.0)
            max_tokens: Максимальное количество токенов в ответе
            mcp_client: MCP клиент для вызова инструментов (опционально, deprecated - используйте mcp_clients)
        """
        super().__init__(api_key, timeout)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Поддержка множественных MCP клиентов
        self.mcp_clients = []
        if mcp_client:
            self.mcp_clients.append(mcp_client)

        # Обратная совместимость
        self.mcp_client = mcp_client

        # Создаём асинхронный клиент с кастомным base_url для DeepSeek
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=DEEPSEEK_API_URL,
            timeout=timeout
        )

        logger.info(f"DeepSeek Provider инициализирован с моделью {model}")
        if mcp_client:
            logger.info("DeepSeek Provider: MCP клиент подключен для function calling")

    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Генерация ответа от DeepSeek с поддержкой MCP tools.

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

            # Получаем список доступных tools из всех MCP клиентов
            tools = None
            if self.mcp_clients:
                tools = await self._get_mcp_tools_definitions()

            logger.info(f"Отправка запроса в DeepSeek API (модель: {self.model})")
            logger.debug(f"Количество сообщений в контексте: {len(messages)}")
            if tools:
                logger.info(f"MCP Tools доступны: {len(tools)} инструментов")

            # Отправляем запрос к DeepSeek API
            if tools:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    tools=tools,
                    tool_choice="auto"  # Позволяем модели решать когда использовать tools
                )
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

            # Обработка ответа с возможными tool calls
            if response.choices and len(response.choices) > 0:
                message = response.choices[0].message

                # Проверяем есть ли tool calls
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    logger.info(f"DeepSeek запросил вызов {len(message.tool_calls)} инструментов")

                    # Обрабатываем tool calls
                    tool_results = await self._handle_tool_calls(message.tool_calls)

                    # Добавляем assistant message с tool calls в историю
                    messages.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in message.tool_calls
                        ]
                    })

                    # Добавляем результаты выполнения tools
                    for tool_call_id, tool_name, result in tool_results:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": result
                        })

                    # Делаем второй запрос для получения финального ответа
                    logger.info("Отправка второго запроса с результатами tool calls")
                    final_response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens
                    )

                    if final_response.choices and len(final_response.choices) > 0:
                        final_message = final_response.choices[0].message.content
                        logger.info("Получен финальный ответ от DeepSeek после tool calls")
                        return final_message
                    else:
                        logger.error("DeepSeek не вернул финальный ответ после tool calls")
                        return None

                # Обычный ответ без tool calls
                assistant_message = message.content
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

    async def _get_mcp_tools_definitions(self) -> List[Dict[str, Any]]:
        """
        Получение определений MCP tools в формате OpenAI function calling от всех MCP клиентов.

        Returns:
            Список определений tools для DeepSeek API
        """
        if not self.mcp_clients:
            return []

        tools_definitions = []

        try:
            # Собираем tools от всех подключенных MCP клиентов
            for mcp_client in self.mcp_clients:
                if mcp_client and mcp_client.is_connected():
                    # Получаем список tools от MCP сервера
                    mcp_tools = await mcp_client.list_tools()

                    # Конвертируем в формат OpenAI tools
                    for tool in mcp_tools:
                        tool_def = {
                            "type": "function",
                            "function": {
                                "name": tool["name"],
                                "description": tool["description"],
                                "parameters": tool.get("inputSchema", {})
                            }
                        }
                        tools_definitions.append(tool_def)

            logger.debug(f"Сформировано {len(tools_definitions)} определений tools для DeepSeek от {len(self.mcp_clients)} MCP клиентов")
            return tools_definitions

        except Exception as e:
            logger.error(f"Ошибка получения MCP tools definitions: {e}", exc_info=True)
            return []

    async def _handle_tool_calls(self, tool_calls: List[Any]) -> List[tuple]:
        """
        Обработка вызовов tools от DeepSeek.

        Args:
            tool_calls: Список tool calls от DeepSeek

        Returns:
            Список кортежей (tool_call_id, tool_name, result)
        """
        results = []

        for tool_call in tool_calls:
            tool_call_id = tool_call.id
            tool_name = tool_call.function.name
            tool_args_str = tool_call.function.arguments

            try:
                # Парсим аргументы из JSON строки
                import json
                tool_args = json.loads(tool_args_str)

                logger.info(f"Вызов MCP tool: {tool_name} с аргументами: {tool_args}")

                # Ищем MCP клиент, который имеет данный tool
                tool_executed = False
                for mcp_client in self.mcp_clients:
                    if mcp_client and mcp_client.is_connected():
                        # Проверяем, есть ли у этого клиента данный tool
                        client_tools = await mcp_client.list_tools()
                        tool_names = [t["name"] for t in client_tools]

                        if tool_name in tool_names:
                            # Вызываем tool через этот MCP клиент
                            result = await mcp_client.call_tool(tool_name, tool_args)

                            if result:
                                logger.info(f"Tool {tool_name} выполнен успешно через MCP клиент")
                                results.append((tool_call_id, tool_name, result))
                                tool_executed = True
                                break
                            else:
                                error_msg = f"Tool {tool_name} не вернул результат"
                                logger.error(error_msg)
                                results.append((tool_call_id, tool_name, f"❌ {error_msg}"))
                                tool_executed = True
                                break

                if not tool_executed:
                    error_msg = f"MCP клиент с tool '{tool_name}' не найден или не подключен"
                    logger.error(error_msg)
                    results.append((tool_call_id, tool_name, f"❌ {error_msg}"))

            except json.JSONDecodeError as e:
                error_msg = f"Ошибка парсинга аргументов tool {tool_name}: {e}"
                logger.error(error_msg)
                results.append((tool_call_id, tool_name, f"❌ {error_msg}"))

            except Exception as e:
                error_msg = f"Ошибка выполнения tool {tool_name}: {e}"
                logger.error(error_msg, exc_info=True)
                results.append((tool_call_id, tool_name, f"❌ {error_msg}"))

        return results

    def set_mcp_client(self, mcp_client: Any) -> None:
        """
        Установка MCP клиента для провайдера (deprecated - используйте add_mcp_client).

        Args:
            mcp_client: Экземпляр MCPClient
        """
        self.mcp_client = mcp_client
        if mcp_client and mcp_client not in self.mcp_clients:
            self.mcp_clients.append(mcp_client)
        logger.info("MCP клиент установлен для DeepSeek Provider")

    def add_mcp_client(self, mcp_client: Any) -> None:
        """
        Добавление MCP клиента к списку клиентов провайдера.

        Args:
            mcp_client: Экземпляр MCPClient
        """
        if mcp_client and mcp_client not in self.mcp_clients:
            self.mcp_clients.append(mcp_client)
            logger.info(f"MCP клиент добавлен к DeepSeek Provider (всего: {len(self.mcp_clients)})")
