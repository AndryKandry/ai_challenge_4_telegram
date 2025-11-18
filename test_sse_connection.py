#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики SSE соединения с MCP сервером.
"""

import asyncio
import logging
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Включаем DEBUG логирование для httpx и MCP
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("mcp").setLevel(logging.DEBUG)


async def test_sse_connection():
    """Тест подключения к MCP серверу через SSE."""
    from mcp_client import MCPClient, get_weather_mcp_config

    logger.info("=" * 80)
    logger.info("Начало теста SSE соединения с Weather MCP сервером")
    logger.info("=" * 80)

    # Получение конфигурации
    config = get_weather_mcp_config()
    logger.info(f"Конфигурация сервера: {config}")

    # Создание клиента
    logger.info("\nСоздание MCP клиента...")
    client = MCPClient(config)

    try:
        # Попытка подключения с детальным логированием
        logger.info("\n" + "=" * 80)
        logger.info("ПОПЫТКА ПОДКЛЮЧЕНИЯ К СЕРВЕРУ")
        logger.info("=" * 80)

        connected = await client.connect()

        if connected:
            logger.info("\n✅ ПОДКЛЮЧЕНИЕ УСПЕШНО!")

            # Попытка получить список инструментов
            logger.info("\nПолучение списка инструментов...")
            tools = await client.list_tools()

            logger.info(f"\n✅ Получено {len(tools)} инструментов:")
            for tool in tools:
                logger.info(f"  - {tool['name']}: {tool['description']}")

        else:
            logger.error("\n❌ ПОДКЛЮЧЕНИЕ НЕ УДАЛОСЬ!")

    except asyncio.TimeoutError as e:
        logger.error(f"\n❌ ТАЙМАУТ ПРИ ПОДКЛЮЧЕНИИ: {e}")
        logger.error("Сервер не ответил в течение 30 секунд")

    except Exception as e:
        logger.error(f"\n❌ ОШИБКА: {e}", exc_info=True)

    finally:
        # Закрытие соединения
        logger.info("\nЗакрытие соединения...")
        try:
            await client.disconnect()
            logger.info("✅ Соединение закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка при закрытии: {e}")

    logger.info("\n" + "=" * 80)
    logger.info("ТЕСТ ЗАВЕРШЕН")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_sse_connection())
