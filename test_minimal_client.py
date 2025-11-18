#!/usr/bin/env python3
"""
Тестовый клиент для проверки подключения к минимальному MCP серверу.
"""

import asyncio
import sys
import logging
from pathlib import Path
from mcp_client import MCPClient

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Тестирование подключения к минимальному MCP серверу."""
    print("\n" + "=" * 70)
    print("ТЕСТ МИНИМАЛЬНОГО MCP СЕРВЕРА (PURE SDK)")
    print("=" * 70 + "\n")

    try:
        # Путь к минимальному серверу
        project_root = Path(__file__).parent
        server_path = project_root / "test_minimal_server.py"

        # Конфигурация
        config = {
            "type": "stdio",
            "command": sys.executable,
            "args": [str(server_path)],
            "env": {}
        }

        print(f"🔧 Конфигурация сервера:")
        print(f"   Команда: {config['command']}")
        print(f"   Путь: {server_path}")
        print()

        # Создание клиента
        print("🔌 Создание MCP клиента...")
        client = MCPClient(config)

        # Подключение к серверу
        print("🔗 Подключение к минимальному MCP серверу...")
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
            print()

        # Закрытие соединения
        print("🔌 Закрытие соединения...")
        await client.disconnect()
        print("✅ Соединение закрыто\n")

        print("=" * 70)
        print("✅ ТЕСТ УСПЕШНО ЗАВЕРШЕН")
        print("=" * 70 + "\n")

        return True

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        logger.exception("Детальная информация об ошибке:")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
