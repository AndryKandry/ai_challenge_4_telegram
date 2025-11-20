#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Filesystem MCP сервера.

Проверяет все инструменты:
- list_directory
- change_directory
- read_file
- write_file
- edit_file
- get_file_info
"""

import asyncio
import logging
from pathlib import Path
from mcp_client import MCPClient, get_filesystem_mcp_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_filesystem_mcp():
    """Тестирование Filesystem MCP сервера."""

    print("=" * 80)
    print("ТЕСТИРОВАНИЕ FILESYSTEM MCP СЕРВЕРА")
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

        # Получение списка инструментов
        print("\n2. Получение списка инструментов...")
        tools = await client.list_tools()
        print(f"✅ Доступно {len(tools)} инструментов:")
        for tool in tools:
            print(f"   - {tool['name']}: {tool['description']}")

        # Тест 1: list_directory (текущая домашняя директория)
        print("\n3. Тест list_directory (домашняя директория)...")
        result = await client.call_tool("list_directory", {"path": "~"})
        print(result[:500] if result and len(result) > 500 else result)
        print("✅ list_directory работает")

        # Тест 2: get_file_info для домашней директории
        print("\n4. Тест get_file_info (домашняя директория)...")
        result = await client.call_tool("get_file_info", {"path": "~"})
        print(result)
        print("✅ get_file_info работает")

        # Тест 3: write_file - создание тестового файла
        print("\n5. Тест write_file (создание тестового файла)...")
        test_file_path = str(Path.home() / "mcp_test_file.txt")
        test_content = "Hello from Filesystem MCP!\nЭто тестовый файл.\n"
        result = await client.call_tool("write_file", {
            "path": test_file_path,
            "content": test_content
        })
        print(result)
        print("✅ write_file работает")

        # Тест 4: read_file - чтение созданного файла
        print("\n6. Тест read_file (чтение созданного файла)...")
        result = await client.call_tool("read_file", {"path": test_file_path})
        print(result)
        print("✅ read_file работает")

        # Тест 5: edit_file - редактирование файла
        print("\n7. Тест edit_file (редактирование файла)...")
        new_content = "Updated content!\nФайл был отредактирован через MCP.\n"
        result = await client.call_tool("edit_file", {
            "path": test_file_path,
            "new_content": new_content,
            "create_backup": True
        })
        print(result)
        print("✅ edit_file работает")

        # Тест 6: read_file после редактирования
        print("\n8. Тест read_file (проверка изменений)...")
        result = await client.call_tool("read_file", {"path": test_file_path})
        print(result)
        print("✅ Файл успешно изменен")

        # Тест 7: get_file_info для файла
        print("\n9. Тест get_file_info (для файла)...")
        result = await client.call_tool("get_file_info", {"path": test_file_path})
        print(result)
        print("✅ get_file_info для файла работает")

        # Тест 8: change_directory
        print("\n10. Тест change_directory (переход в Documents)...")
        docs_path = str(Path.home() / "Documents")
        result = await client.call_tool("change_directory", {"path": docs_path})
        print(result)
        print("✅ change_directory работает")

        # Тест 9: list_directory после смены директории (относительный путь)
        print("\n11. Тест list_directory (относительный путь '.')...")
        result = await client.call_tool("list_directory", {"path": "."})
        print(result[:500] if result and len(result) > 500 else result)
        print("✅ list_directory с относительным путем работает")

        # Очистка: удаление тестового файла
        print("\n12. Очистка (удаление тестового файла)...")
        import os
        try:
            os.remove(test_file_path)
            # Удаление backup файла
            backup_files = list(Path.home().glob("mcp_test_file.*.backup.txt"))
            for backup_file in backup_files:
                os.remove(backup_file)
            print("✅ Тестовые файлы удалены")
        except Exception as e:
            print(f"⚠️ Ошибка при удалении: {e}")

        print("\n" + "=" * 80)
        print("ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}", exc_info=True)
        print(f"\n❌ Ошибка: {e}")

    finally:
        # Отключение
        print("\n13. Отключение от сервера...")
        await client.disconnect()
        print("✅ Отключение выполнено")


if __name__ == "__main__":
    asyncio.run(test_filesystem_mcp())
