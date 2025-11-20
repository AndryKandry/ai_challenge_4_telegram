#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики проблемы с write_file.
"""

import asyncio
from mcp_client import MCPClient, get_filesystem_mcp_config


async def test_write_file():
    """Тест создания файла через Filesystem MCP."""

    print("=" * 80)
    print("ТЕСТ СОЗДАНИЯ ФАЙЛА")
    print("=" * 80)

    # Создаем MCP клиент
    config = get_filesystem_mcp_config()
    client = MCPClient(config)

    try:
        # Подключение
        print("\n1. Подключение к Filesystem MCP серверу...")
        connected = await client.connect()
        if not connected:
            print("❌ Не удалось подключиться к серверу")
            return
        print("✅ Подключение успешно")

        # Тест 1: Создание файла с абсолютным путем
        print("\n2. Тест write_file с абсолютным путем...")
        test_path = "/Users/andreykozyrev/test_absolute.txt"
        test_content = "Test content from absolute path"

        result = await client.call_tool("write_file", {
            "path": test_path,
            "content": test_content
        })
        print(f"Результат: {result}")

        # Проверка существования
        import os
        if os.path.exists(test_path):
            print(f"✅ Файл найден: {test_path}")
            with open(test_path, 'r') as f:
                print(f"Содержимое: {f.read()}")
            os.remove(test_path)
            print(f"✅ Файл удален")
        else:
            print(f"❌ Файл НЕ найден: {test_path}")

        # Тест 2: Создание файла с тильдой
        print("\n3. Тест write_file с тильдой (~)...")
        test_path_tilde = "~/test_tilde.txt"
        test_content2 = "Test content from tilde path"

        result = await client.call_tool("write_file", {
            "path": test_path_tilde,
            "content": test_content2
        })
        print(f"Результат: {result}")

        # Проверка существования
        expanded_path = os.path.expanduser(test_path_tilde)
        if os.path.exists(expanded_path):
            print(f"✅ Файл найден: {expanded_path}")
            with open(expanded_path, 'r') as f:
                print(f"Содержимое: {f.read()}")
            os.remove(expanded_path)
            print(f"✅ Файл удален")
        else:
            print(f"❌ Файл НЕ найден: {expanded_path}")

        # Тест 3: Создание файла как в вашем случае
        print("\n4. Тест write_file как в примере с AndryKandry...")
        test_path_example = "~/AndryKandry_test.txt"
        test_content3 = "GitHub User: AndryKandry\nTest content"

        result = await client.call_tool("write_file", {
            "path": test_path_example,
            "content": test_content3
        })
        print(f"Результат: {result}")

        # Проверка существования
        expanded_path3 = os.path.expanduser(test_path_example)
        if os.path.exists(expanded_path3):
            print(f"✅ Файл найден: {expanded_path3}")
            with open(expanded_path3, 'r') as f:
                print(f"Содержимое: {f.read()}")
            os.remove(expanded_path3)
            print(f"✅ Файл удален")
        else:
            print(f"❌ Файл НЕ найден: {expanded_path3}")
            print(f"Поиск в других местах:")
            # Поиск файла
            import subprocess
            find_result = subprocess.run(['find', os.path.expanduser('~'), '-name', 'AndryKandry_test.txt', '-type', 'f'],
                                       capture_output=True, text=True, timeout=10)
            if find_result.stdout:
                print(f"Файл найден в: {find_result.stdout}")
            else:
                print("Файл не найден нигде в домашней директории")

        print("\n" + "=" * 80)
        print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Отключение
        print("\n5. Отключение от сервера...")
        await client.disconnect()
        print("✅ Отключение выполнено")


if __name__ == "__main__":
    asyncio.run(test_write_file())
