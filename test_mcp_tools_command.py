#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функции получения списка MCP инструментов.
Имитирует выполнение команды /mcp_tools из бота.
"""

import asyncio
import logging
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


async def test_mcp_tools_command():
    """Тест получения списка MCP инструментов."""
    from mcp_client import MCPClient, get_weather_mcp_config

    logger.info("=" * 80)
    logger.info("Тест команды /mcp_tools")
    logger.info("=" * 80)

    try:
        # Получение конфигурации Weather MCP
        logger.info("\n1. Получение конфигурации Weather MCP...")
        mcp_config = get_weather_mcp_config()
        logger.info(f"   Конфигурация: {mcp_config}")

        # Создание MCP клиента
        logger.info("\n2. Создание MCP клиента...")
        mcp_client = MCPClient(mcp_config)

        # Подключение к серверу
        logger.info("\n3. Подключение к MCP серверу...")
        connected = await mcp_client.connect()

        if not connected:
            logger.error("❌ Ошибка подключения к MCP-серверу")
            return

        logger.info("✅ Успешное подключение к MCP-серверу")

        # Получение списка инструментов
        logger.info("\n4. Получение списка инструментов...")
        tools = await mcp_client.list_tools()

        # Закрытие соединения
        logger.info("\n5. Закрытие соединения...")
        await mcp_client.disconnect()

        if not tools:
            logger.warning("⚠️ Список инструментов пуст")
            return

        # Форматирование ответа
        logger.info("\n" + "=" * 80)
        logger.info("🛠 ДОСТУПНЫЕ MCP ИНСТРУМЕНТЫ:")
        logger.info("=" * 80)

        for idx, tool in enumerate(tools, 1):
            logger.info(f"\n{idx}. {tool['name']}")
            logger.info(f"   📝 {tool['description']}")

            # Извлечение параметров из inputSchema
            schema = tool.get('inputSchema', {})
            properties = schema.get('properties', {})
            required = schema.get('required', [])

            if properties:
                logger.info("   📋 Параметры:")
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'unknown')
                    param_desc = param_info.get('description', 'Нет описания')
                    is_required = '(обязательный)' if param_name in required else '(опциональный)'
                    logger.info(f"      • {param_name} ({param_type}) {is_required}")
                    logger.info(f"        {param_desc}")

        logger.info("\n" + "=" * 80)
        logger.info(f"✅ Всего инструментов: {len(tools)}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"\n❌ ОШИБКА: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_mcp_tools_command())
