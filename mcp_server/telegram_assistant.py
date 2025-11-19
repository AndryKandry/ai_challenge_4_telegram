#!/usr/bin/env python3
"""
Telegram Assistant MCP Server - предоставляет инструменты для работы с Telegram API
через Model Context Protocol.

Реализованные инструменты:
- get_chat_messages: получение сообщений из Telegram чата за период
- get_chat_info: получение информации о чате
- validate_chat_access: проверка доступа к чату
"""

from typing import Any, Optional
from datetime import datetime
import logging
import os
from fastmcp import FastMCP

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создание MCP сервера
mcp = FastMCP("telegram_assistant")

# Проверка доступности Pyrogram
try:
    from pyrogram import Client
    from pyrogram.types import Message, Chat
    from pyrogram.errors import (
        ChannelPrivate,
        ChatAdminRequired,
        PeerIdInvalid,
        UsernameInvalid,
        RPCError
    )
    PYROGRAM_AVAILABLE = True
    logger.info("Pyrogram успешно импортирован")
except ImportError:
    PYROGRAM_AVAILABLE = False
    logger.warning("Pyrogram не установлен. Telegram Assistant MCP сервер будет работать в ограниченном режиме.")

# Глобальный клиент Telegram (инициализируется при первом использовании)
telegram_client: Optional[Client] = None
client_started = False


async def get_telegram_client() -> Optional[Client]:
    """
    Получение или создание Telegram клиента.

    Returns:
        Экземпляр Pyrogram Client или None, если недоступен
    """
    global telegram_client, client_started

    if not PYROGRAM_AVAILABLE:
        logger.error("Pyrogram недоступен")
        return None

    if telegram_client is None:
        # Получаем credentials из переменных окружения
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")

        if not api_id or not api_hash:
            logger.error("TELEGRAM_API_ID или TELEGRAM_API_HASH не заданы в переменных окружения")
            return None

        # Создаём директорию data, если её нет
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"Директория для session файлов: {data_dir}")

        # Создаём клиента
        telegram_client = Client(
            name="telegram_assistant_mcp",
            api_id=api_id,
            api_hash=api_hash,
            workdir=data_dir  # Сохраняем session в директорию data
        )
        logger.info("Telegram клиент создан")

    # Запускаем клиента если ещё не запущен
    if not client_started:
        try:
            await telegram_client.start()
            client_started = True
            logger.info("Telegram клиент успешно запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска Telegram клиента: {e}")
            return None

    return telegram_client


def format_message(message: Message) -> dict[str, Any]:
    """
    Форматирование сообщения Pyrogram в словарь.

    Args:
        message: Объект Message от Pyrogram

    Returns:
        Словарь с данными сообщения
    """
    from_user = None
    if message.from_user:
        from_user = {
            "id": message.from_user.id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }

    return {
        "message_id": message.id,
        "from_user": from_user,
        "date": message.date.isoformat() if message.date else None,
        "text": message.text or message.caption or "",
        "reply_to": message.reply_to_message_id if message.reply_to_message_id else None,
        "has_media": bool(message.media)
    }


@mcp.tool()
async def get_chat_messages(
    chat_id: str,
    from_date: str,
    to_date: str,
    limit: int = 1000
) -> str:
    """
    Получить сообщения из Telegram чата за указанный период.

    Args:
        chat_id: ID чата или username (например, '@channelname' или '-1001234567890')
        from_date: Начало периода в формате ISO 8601 (например, '2025-01-19T10:00:00')
        to_date: Конец периода в формате ISO 8601 (например, '2025-01-19T14:00:00')
        limit: Максимальное количество сообщений (по умолчанию 1000, максимум 1000)

    Returns:
        JSON строка с метаданными и списком сообщений
    """
    if not PYROGRAM_AVAILABLE:
        return '{"error": "pyrogram_not_available", "message": "Pyrogram не установлен. Установите: pip install pyrogram tgcrypto"}'

    # Валидация параметров
    if limit < 1 or limit > 1000:
        return '{"error": "invalid_limit", "message": "Параметр limit должен быть от 1 до 1000"}'

    try:
        # Парсинг дат
        from_datetime = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        to_datetime = datetime.fromisoformat(to_date.replace('Z', '+00:00'))

        if from_datetime > to_datetime:
            return '{"error": "invalid_dates", "message": "from_date должна быть раньше to_date"}'

    except ValueError as e:
        return f'{{"error": "invalid_date_format", "message": "Неверный формат даты. Используйте ISO 8601: {str(e)}"}}'

    # Получение клиента
    client = await get_telegram_client()
    if not client:
        return '{"error": "client_unavailable", "message": "Telegram клиент недоступен. Проверьте TELEGRAM_API_ID и TELEGRAM_API_HASH"}'

    try:
        # Получаем информацию о чате
        chat: Chat = await client.get_chat(chat_id)

        messages_data = []
        message_count = 0

        # Получаем сообщения из истории чата
        async for message in client.get_chat_history(chat_id, limit=limit):
            # Проверяем диапазон дат
            if message.date < from_datetime:
                # Сообщения идут от новых к старым, если дошли до from_date - останавливаемся
                break

            if from_datetime <= message.date <= to_datetime:
                messages_data.append(format_message(message))
                message_count += 1

            if message_count >= limit:
                break

        logger.info(f"Получено {message_count} сообщений из чата {chat_id}")

        # Формируем JSON ответ
        import json
        result = {
            "chat_id": str(chat.id),
            "chat_name": chat.title or chat.first_name or "Unknown",
            "period": {
                "from": from_datetime.isoformat(),
                "to": to_datetime.isoformat()
            },
            "messages_count": message_count,
            "messages": messages_data
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except (ChannelPrivate, ChatAdminRequired) as e:
        logger.error(f"Нет доступа к чату {chat_id}: {e}")
        return f'{{"error": "access_denied", "message": "Нет доступа к чату {chat_id}"}}'

    except (PeerIdInvalid, UsernameInvalid) as e:
        logger.error(f"Чат {chat_id} не найден: {e}")
        return f'{{"error": "chat_not_found", "message": "Чат {chat_id} не найден"}}'

    except RPCError as e:
        logger.error(f"Ошибка Telegram API при получении сообщений из {chat_id}: {e}")
        return f'{{"error": "telegram_api_error", "message": "Ошибка Telegram API: {str(e)}"}}'

    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении сообщений из {chat_id}: {e}", exc_info=True)
        return f'{{"error": "unknown", "message": "Произошла неожиданная ошибка: {str(e)}"}}'


@mcp.tool()
async def get_chat_info(chat_id: str) -> str:
    """
    Получить информацию о Telegram чате.

    Args:
        chat_id: ID чата или username (например, '@channelname' или '-1001234567890')

    Returns:
        JSON строка с информацией о чате
    """
    if not PYROGRAM_AVAILABLE:
        return '{"error": "pyrogram_not_available", "message": "Pyrogram не установлен. Установите: pip install pyrogram tgcrypto"}'

    # Получение клиента
    client = await get_telegram_client()
    if not client:
        return '{"error": "client_unavailable", "message": "Telegram клиент недоступен. Проверьте TELEGRAM_API_ID и TELEGRAM_API_HASH"}'

    try:
        chat: Chat = await client.get_chat(chat_id)

        chat_info = {
            "chat_id": str(chat.id),
            "type": chat.type.value if chat.type else "unknown",
            "title": chat.title,
            "username": chat.username,
            "description": chat.description,
            "member_count": chat.members_count if hasattr(chat, 'members_count') else None,
            "is_verified": chat.is_verified if hasattr(chat, 'is_verified') else False,
            "is_restricted": chat.is_restricted if hasattr(chat, 'is_restricted') else False
        }

        logger.info(f"Получена информация о чате {chat_id}")

        import json
        return json.dumps(chat_info, ensure_ascii=False, indent=2)

    except (ChannelPrivate, ChatAdminRequired) as e:
        logger.error(f"Нет доступа к чату {chat_id}: {e}")
        return f'{{"error": "access_denied", "message": "Нет доступа к чату {chat_id}"}}'

    except (PeerIdInvalid, UsernameInvalid) as e:
        logger.error(f"Чат {chat_id} не найден: {e}")
        return f'{{"error": "chat_not_found", "message": "Чат {chat_id} не найден"}}'

    except Exception as e:
        logger.error(f"Ошибка при получении информации о чате {chat_id}: {e}", exc_info=True)
        return f'{{"error": "unknown", "message": "Произошла неожиданная ошибка: {str(e)}"}}'


@mcp.tool()
async def validate_chat_access(chat_id: str) -> str:
    """
    Проверить доступ к Telegram чату.

    Args:
        chat_id: ID чата или username (например, '@channelname' или '-1001234567890')

    Returns:
        JSON строка с результатом проверки
    """
    if not PYROGRAM_AVAILABLE:
        return '{"error": "pyrogram_not_available", "message": "Pyrogram не установлен. Установите: pip install pyrogram tgcrypto"}'

    # Получение клиента
    client = await get_telegram_client()
    if not client:
        return '{"error": "client_unavailable", "message": "Telegram клиент недоступен. Проверьте TELEGRAM_API_ID и TELEGRAM_API_HASH"}'

    try:
        await client.get_chat(chat_id)
        logger.info(f"Доступ к чату {chat_id} подтвержден")

        import json
        return json.dumps({
            "chat_id": chat_id,
            "access_valid": True,
            "message": f"Доступ к чату {chat_id} подтвержден"
        }, ensure_ascii=False, indent=2)

    except (ChannelPrivate, ChatAdminRequired, PeerIdInvalid, UsernameInvalid) as e:
        logger.warning(f"Нет доступа к чату {chat_id}: {e}")

        import json
        return json.dumps({
            "chat_id": chat_id,
            "access_valid": False,
            "message": f"Нет доступа к чату {chat_id}: {type(e).__name__}"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Ошибка при проверке доступа к чату {chat_id}: {e}", exc_info=True)

        import json
        return json.dumps({
            "chat_id": chat_id,
            "access_valid": False,
            "error": "unknown",
            "message": f"Произошла неожиданная ошибка: {str(e)}"
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Используем SSE транспорт (по аналогии с GitHub MCP)
    import sys

    # Если запущен с аргументом --stdio, использовать stdio (для совместимости)
    # Иначе использовать SSE по умолчанию
    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        logger.info("Запуск Telegram Assistant MCP сервера в режиме stdio")
        mcp.run(transport="stdio")
    else:
        # SSE транспорт по умолчанию (работает стабильно)
        logger.info("Запуск Telegram Assistant MCP сервера в режиме SSE на порту 8002")
        mcp.run(transport="sse", port=8002)
