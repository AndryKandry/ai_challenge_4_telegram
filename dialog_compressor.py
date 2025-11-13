#!/usr/bin/env python3
"""
Модуль компрессии истории диалога для оптимизации использования токенов.
Реализует механизм сжатия, аналогичный команде /compact в Claude Code.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import httpx

from token_counter import TokenCounter

# Настройка логирования
logger = logging.getLogger(__name__)

# Константы
COMPRESSION_PROMPT_PATH = "prompts/compression_summary.txt"
YANDEX_GPT_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
REQUEST_TIMEOUT = 30


class DialogHistory:
    """Класс для хранения истории диалога."""

    def __init__(self):
        """Инициализация истории диалога."""
        self.messages: List[Dict[str, str]] = []
        self.system_prompt: Optional[str] = None
        self.compressed_context: Optional[str] = None

    def add_message(self, role: str, text: str) -> None:
        """
        Добавить сообщение в историю.

        Args:
            role: Роль отправителя ("user" или "assistant")
            text: Текст сообщения
        """
        self.messages.append({"role": role, "text": text})
        logger.debug(f"Added message to history: role={role}, length={len(text)}")

    def set_system_prompt(self, prompt: str) -> None:
        """
        Установить системный промпт.

        Args:
            prompt: Системный промпт
        """
        self.system_prompt = prompt

    def set_compressed_context(self, context: str) -> None:
        """
        Установить сжатый контекст.

        Args:
            context: Сжатый контекст
        """
        self.compressed_context = context

    def get_message_count(self) -> int:
        """Получить количество сообщений в истории."""
        return len(self.messages)

    def get_last_n_messages(self, n: int) -> List[Dict[str, str]]:
        """
        Получить последние N сообщений.

        Args:
            n: Количество сообщений

        Returns:
            Список последних N сообщений
        """
        return self.messages[-n:] if n > 0 else []

    def get_messages_to_compress(self, keep_last_n: int) -> List[Dict[str, str]]:
        """
        Получить сообщения для компрессии (все кроме последних N).

        Args:
            keep_last_n: Количество последних сообщений для сохранения

        Returns:
            Список сообщений для компрессии
        """
        if keep_last_n >= len(self.messages):
            return []
        return self.messages[:-keep_last_n] if keep_last_n > 0 else self.messages

    def clear_compressed_messages(self, keep_last_n: int) -> None:
        """
        Удалить сжатые сообщения из истории.

        Args:
            keep_last_n: Количество последних сообщений для сохранения
        """
        if keep_last_n > 0 and keep_last_n < len(self.messages):
            self.messages = self.messages[-keep_last_n:]
            logger.info(f"Cleared compressed messages, kept last {keep_last_n}")


class DialogCompressor:
    """Класс для компрессии истории диалога."""

    def __init__(self, yandex_api_key: str, token_counter: TokenCounter, config: Optional[Dict] = None):
        """
        Инициализация компрессора диалога.

        Args:
            yandex_api_key: API ключ Yandex Cloud
            token_counter: Экземпляр счетчика токенов
            config: Конфигурация компрессии (опционально)
        """
        self.api_key = yandex_api_key
        self.token_counter = token_counter
        self.headers = {
            "Authorization": f"Bearer {yandex_api_key}",
            "Content-Type": "application/json",
        }

        # Загрузка конфигурации
        if config is None:
            from config import (
                COMPRESSION_ENABLED,
                COMPRESSION_AUTO_COMPRESS,
                COMPRESSION_MAX_MESSAGES,
                COMPRESSION_MAX_TOKENS_PERCENT,
                COMPRESSION_KEEP_RECENT_MESSAGES,
                COMPRESSION_RATIO_TARGET,
            )
            config = {
                "enabled": COMPRESSION_ENABLED,
                "auto_compress": COMPRESSION_AUTO_COMPRESS,
                "max_messages": COMPRESSION_MAX_MESSAGES,
                "max_tokens_percent": COMPRESSION_MAX_TOKENS_PERCENT,
                "keep_recent_messages": COMPRESSION_KEEP_RECENT_MESSAGES,
                "compression_ratio_target": COMPRESSION_RATIO_TARGET,
            }

        self.config = config
        self.compression_prompt_template = self._load_compression_prompt()

        logger.info(f"DialogCompressor initialized with config: {config}")

    def _load_compression_prompt(self) -> str:
        """
        Загрузить шаблон промпта для компрессии.

        Returns:
            Шаблон промпта
        """
        try:
            with open(COMPRESSION_PROMPT_PATH, "r", encoding="utf-8") as f:
                prompt = f.read()
                logger.info(f"Loaded compression prompt from {COMPRESSION_PROMPT_PATH}")
                return prompt
        except FileNotFoundError:
            logger.error(f"Compression prompt file not found: {COMPRESSION_PROMPT_PATH}")
            # Fallback промпт
            return """Создай краткое резюме следующей истории диалога.
Сохрани только самую важную информацию.

История для сжатия:
{history_to_compress}

Формат резюме:
- Пользователь: [описание]
- Задача: [основная цель]
- Выполнено: [список]
- В работе: [список]
- Ключевые решения: [список]
- Важный контекст: [описание]"""

    def should_compress(self, history: DialogHistory) -> Tuple[bool, str]:
        """
        Проверить необходимость компрессии истории.

        Args:
            history: История диалога

        Returns:
            Tuple (нужна ли компрессия, причина)
        """
        if not self.config["enabled"]:
            return False, "Compression disabled in config"

        if not self.config["auto_compress"]:
            return False, "Auto-compression disabled"

        message_count = history.get_message_count()

        # Проверка по количеству сообщений
        if message_count >= self.config["max_messages"]:
            logger.info(f"Compression needed: {message_count} >= {self.config['max_messages']} messages")
            return True, f"Message count exceeded: {message_count} messages"

        # Проверка по количеству токенов
        total_tokens = self._calculate_total_tokens(history)
        from config import get_model_token_limit, DEFAULT_MODEL
        token_limit = get_model_token_limit(DEFAULT_MODEL)
        token_percentage = (total_tokens / token_limit) * 100

        if token_percentage >= self.config["max_tokens_percent"]:
            logger.info(f"Compression needed: {token_percentage:.1f}% >= {self.config['max_tokens_percent']}%")
            return True, f"Token usage at {token_percentage:.1f}%"

        return False, "Within limits"

    def _calculate_total_tokens(self, history: DialogHistory) -> int:
        """
        Подсчитать общее количество токенов в истории.

        Args:
            history: История диалога

        Returns:
            Количество токенов
        """
        total_tokens = 0

        # Системный промпт
        if history.system_prompt:
            total_tokens += self.token_counter.count_tokens(history.system_prompt)

        # Сжатый контекст
        if history.compressed_context:
            total_tokens += self.token_counter.count_tokens(history.compressed_context)

        # Все сообщения
        for message in history.messages:
            total_tokens += self.token_counter.count_tokens(message["text"])

        return total_tokens

    async def compress_history(
        self, history: DialogHistory, keep_last_n: Optional[int] = None
    ) -> Tuple[bool, str, Dict[str, int]]:
        """
        Сжать историю диалога.

        Args:
            history: История диалога
            keep_last_n: Количество последних сообщений для сохранения (None = из конфига)

        Returns:
            Tuple (успешно ли, сжатый контекст или сообщение об ошибке, статистика токенов)
        """
        if keep_last_n is None:
            keep_last_n = self.config["keep_recent_messages"]

        logger.info(f"Starting compression: total_messages={history.get_message_count()}, keep_last={keep_last_n}")

        # Получить сообщения для компрессии
        messages_to_compress = history.get_messages_to_compress(keep_last_n)

        if not messages_to_compress:
            logger.warning("No messages to compress")
            return False, "No messages to compress", {"tokens_before": 0, "tokens_after": 0, "savings": 0}

        # Подсчет токенов до компрессии
        tokens_before = sum(self.token_counter.count_tokens(msg["text"]) for msg in messages_to_compress)

        # Создать текстовое представление истории для компрессии
        history_text = self._format_messages_for_compression(messages_to_compress)

        # Создать резюме через Yandex GPT
        summary = await self.create_summary(history_text)

        if not summary:
            logger.error("Failed to create summary")
            return False, "Failed to create summary", {"tokens_before": tokens_before, "tokens_after": 0, "savings": 0}

        # Подсчет токенов после компрессии
        tokens_after = self.token_counter.count_tokens(summary)
        savings_percent = ((tokens_before - tokens_after) / tokens_before * 100) if tokens_before > 0 else 0

        # Формирование сжатого контекста
        compressed_context = f"""[COMPRESSED CONTEXT]
Резюме предыдущего диалога:
{summary}
[/COMPRESSED CONTEXT]"""

        # Обновление истории
        history.set_compressed_context(compressed_context)
        history.clear_compressed_messages(keep_last_n)

        logger.info(
            f"Compression completed: {tokens_before} -> {tokens_after} tokens ({savings_percent:.1f}% saved)"
        )

        stats = {
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "savings": int(savings_percent),
            "messages_compressed": len(messages_to_compress),
            "messages_kept": keep_last_n,
        }

        return True, compressed_context, stats

    def _format_messages_for_compression(self, messages: List[Dict[str, str]]) -> str:
        """
        Форматировать сообщения для передачи в компрессор.

        Args:
            messages: Список сообщений

        Returns:
            Форматированный текст истории
        """
        formatted = []
        for i, msg in enumerate(messages, 1):
            role_name = "Пользователь" if msg["role"] == "user" else "Ассистент"
            formatted.append(f"[Сообщение {i} - {role_name}]\n{msg['text']}\n")

        return "\n".join(formatted)

    async def create_summary(self, history_text: str) -> Optional[str]:
        """
        Создать резюме истории через Yandex GPT.

        Args:
            history_text: Текст истории для сжатия

        Returns:
            Резюме или None в случае ошибки
        """
        # Формирование промпта для компрессии
        compression_prompt = self.compression_prompt_template.format(history_to_compress=history_text)

        payload = {
            "modelUri": f"gpt://{os.getenv('YANDEX_FOLDER_ID', 'folder_id')}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,  # Низкая температура для стабильности
                "maxTokens": 2000,
            },
            "messages": [
                {
                    "role": "system",
                    "text": "Ты — эксперт по анализу и сжатию информации. Твоя задача — создать максимально краткое, но информативное резюме диалога.",
                },
                {
                    "role": "user",
                    "text": compression_prompt,
                },
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                logger.info("Sending compression request to Yandex GPT API")
                response = await client.post(
                    YANDEX_GPT_API_URL,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()

                # Парсинг ответа
                data = response.json()
                logger.info("Received summary from Yandex GPT API")

                # Извлечение текста резюме
                if "result" in data and "alternatives" in data["result"]:
                    alternatives = data["result"]["alternatives"]
                    if alternatives and len(alternatives) > 0:
                        summary_text = alternatives[0].get("message", {}).get("text")
                        if summary_text:
                            return summary_text

                logger.error(f"Unexpected response structure: {data}")
                return None

        except httpx.TimeoutException:
            logger.error("Timeout while creating summary")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error while creating summary: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while creating summary: {e}")
            return None

    def extract_key_facts(self, summary: str) -> Dict[str, str]:
        """
        Извлечь ключевые факты из резюме.

        Args:
            summary: Текст резюме

        Returns:
            Словарь с ключевыми фактами
        """
        facts = {
            "user": "",
            "task": "",
            "completed": "",
            "in_progress": "",
            "decisions": "",
            "context": "",
        }

        # Простой парсинг по ключевым словам
        lines = summary.split("\n")
        current_key = None

        for line in lines:
            line = line.strip()
            if line.startswith("- Пользователь:"):
                current_key = "user"
                facts[current_key] = line.replace("- Пользователь:", "").strip()
            elif line.startswith("- Задача:"):
                current_key = "task"
                facts[current_key] = line.replace("- Задача:", "").strip()
            elif line.startswith("- Выполнено:"):
                current_key = "completed"
                facts[current_key] = line.replace("- Выполнено:", "").strip()
            elif line.startswith("- В работе:"):
                current_key = "in_progress"
                facts[current_key] = line.replace("- В работе:", "").strip()
            elif line.startswith("- Ключевые решения:"):
                current_key = "decisions"
                facts[current_key] = line.replace("- Ключевые решения:", "").strip()
            elif line.startswith("- Важный контекст:"):
                current_key = "context"
                facts[current_key] = line.replace("- Важный контекст:", "").strip()
            elif current_key and line:
                # Продолжение предыдущего раздела
                facts[current_key] += " " + line

        return facts

    def get_compression_stats_message(self, stats: Dict[str, int]) -> str:
        """
        Форматировать сообщение со статистикой компрессии.

        Args:
            stats: Статистика компрессии

        Returns:
            Форматированное сообщение
        """
        return f"""🗜️ Компрессия истории завершена

📊 Статистика:
├─ Сжато сообщений: {stats.get('messages_compressed', 0)}
├─ Сохранено последних: {stats.get('messages_kept', 0)}
├─ Токенов до: {stats.get('tokens_before', 0):,}
├─ Токенов после: {stats.get('tokens_after', 0):,}
└─ Экономия: {stats.get('savings', 0)}%

✅ История диалога оптимизирована для экономии токенов!
"""
