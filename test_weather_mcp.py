#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы Weather MCP сервера.
"""

import asyncio
import logging
from mcp_client import MCPClient, get_weather_mcp_config

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_weather_mcp():
    """Тестирование подключения к Weather MCP серверу и получения списка инструментов."""
    print("\n" + "=" * 70)
    print("ТЕСТ WEATHER MCP СЕРВЕРА")
    print("=" * 70 + "\n")

    try:
        # Получение конфигурации
        print("🔧 Получение конфигурации Weather MCP...")
        config = get_weather_mcp_config()
        print(f"   Тип: {config['type']}")
        if config['type'] == 'stdio':
            print(f"   Команда: {config['command']}")
            print(f"   Аргументы: {config['args']}")
        elif config['type'] == 'http':
            print(f"   URL: {config['url']}")
        print()

        # Создание клиента
        print("🔌 Создание MCP клиента...")
        client = MCPClient(config)

        # Подключение к серверу
        print("🔗 Подключение к Weather MCP серверу...")
        connected = await client.connect()

        if not connected:
            print("❌ ОШИБКА: Не удалось подключиться к серверу")
            return False

        print("✅ Успешное подключение к серверу\n")

        # Получение списка инструментов
        print("📋 Запрос списка инструментов...")
        tools = await client.list_tools()

        if not tools:
            print("❌ ОШИБКА: Список инструментов пуст")
            await client.disconnect()
            return False

        print(f"✅ Получено {len(tools)} инструментов\n")

        # Вывод информации об инструментах
        print("🛠 ДОСТУПНЫЕ ИНСТРУМЕНТЫ:\n")
        for idx, tool in enumerate(tools, 1):
            print(f"{idx}. {tool['name']}")
            print(f"   Описание: {tool['description']}")

            # Извлечение параметров
            schema = tool.get('inputSchema', {})
            if isinstance(schema, dict):
                properties = schema.get('properties', {})
                if properties:
                    print(f"   Параметры:")
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'unknown')
                        param_desc = param_info.get('description', 'Нет описания')
                        print(f"     • {param_name} ({param_type}): {param_desc}")

                required = schema.get('required', [])
                if required:
                    print(f"   Обязательные параметры: {', '.join(required)}")

            print()

        # Закрытие соединения
        print("🔌 Закрытие соединения...")
        await client.disconnect()
        print("✅ Соединение закрыто\n")

        print("=" * 70)
        print("✅ ТЕСТ УСПЕШНО ЗАВЕРШЕН")
        print("=" * 70 + "\n")

        return True

    except ImportError as e:
        print(f"❌ ОШИБКА ИМПОРТА: {e}")
        print("   Установите зависимости: pip install -r requirements.txt")
        return False

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        logger.exception("Детальная информация об ошибке:")
        return False


async def main():
    """Главная функция."""
    success = await test_weather_mcp()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
