#!/usr/bin/env python3
"""
Тестовый скрипт для проверки GitHub MCP сервера.
Подключается к серверу и тестирует все три инструмента.
"""

import asyncio
import logging
from mcp_client import MCPClient, get_github_mcp_config

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def test_github_mcp():
    """Тестирование GitHub MCP сервера."""
    logger.info("=" * 80)
    logger.info("ТЕСТИРОВАНИЕ GITHUB MCP СЕРВЕРА")
    logger.info("=" * 80)

    # Получение конфигурации
    config = get_github_mcp_config()
    logger.info(f"Конфигурация MCP: {config}")

    # Создание клиента
    client = MCPClient(config)

    try:
        # Подключение к серверу
        logger.info("\n[1] Подключение к GitHub MCP серверу...")
        connected = await client.connect()

        if not connected:
            logger.error("❌ Не удалось подключиться к серверу!")
            return

        logger.info("✅ Успешно подключено к GitHub MCP серверу")

        # Получение списка инструментов
        logger.info("\n[2] Получение списка доступных инструментов...")
        tools = await client.list_tools()

        logger.info(f"✅ Найдено {len(tools)} инструментов:")
        for idx, tool in enumerate(tools, 1):
            logger.info(f"  {idx}. {tool['name']}: {tool['description']}")

        # Тест 1: get_user_info для пользователя octocat
        logger.info("\n[3] ТЕСТ 1: Получение информации о пользователе 'octocat'")
        result1 = await client.call_tool("get_user_info", {"username": "octocat"})
        if result1:
            logger.info("✅ Результат get_user_info:")
            print(result1)
        else:
            logger.error("❌ get_user_info не вернул результат")

        # Тест 2: get_user_repositories для пользователя octocat
        logger.info("\n[4] ТЕСТ 2: Получение репозиториев пользователя 'octocat'")
        result2 = await client.call_tool("get_user_repositories", {"username": "octocat"})
        if result2:
            logger.info("✅ Результат get_user_repositories:")
            print(result2[:500] + "..." if len(result2) > 500 else result2)
        else:
            logger.error("❌ get_user_repositories не вернул результат")

        # Тест 3: get_repository_commits для torvalds/linux
        logger.info("\n[5] ТЕСТ 3: Получение коммитов из репозитория 'torvalds/linux'")
        result3 = await client.call_tool(
            "get_repository_commits",
            {"owner": "torvalds", "repo": "linux", "per_page": 5}
        )
        if result3:
            logger.info("✅ Результат get_repository_commits:")
            print(result3[:500] + "..." if len(result3) > 500 else result3)
        else:
            logger.error("❌ get_repository_commits не вернул результат")

        # Тест 4: Обработка ошибки 404
        logger.info("\n[6] ТЕСТ 4: Обработка ошибки (несуществующий пользователь)")
        result4 = await client.call_tool("get_user_info", {"username": "nonexistentuser123456789"})
        if result4:
            logger.info("✅ Результат (ожидается сообщение об ошибке):")
            print(result4)
        else:
            logger.error("❌ Тест ошибки не вернул результат")

        logger.info("\n[7] Все тесты завершены!")

    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}", exc_info=True)

    finally:
        # Отключение от сервера
        logger.info("\n[8] Отключение от GitHub MCP сервера...")
        await client.disconnect()
        logger.info("✅ Отключено от сервера")

    logger.info("\n" + "=" * 80)
    logger.info("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_github_mcp())
