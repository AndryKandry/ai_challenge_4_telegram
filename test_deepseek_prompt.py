#!/usr/bin/env python3
"""
Тестовый скрипт для проверки нового промпта DeepSeek с MCP tools.
"""

import asyncio
import os
from dotenv import load_dotenv
from providers import DeepSeekProvider
from mcp_client import MCPClient, get_github_mcp_config, get_filesystem_mcp_config
from prompts import SYSTEM_PROMPT_DEEPSEEK_WITH_TOOLS

# Загрузка .env
load_dotenv()

async def test_deepseek_with_tools():
    """Тестирование DeepSeek с новым промптом и MCP tools."""

    # Получаем API ключ
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        print("❌ DEEPSEEK_API_KEY не задан")
        return

    print("=" * 60)
    print("🧪 ТЕСТ: DeepSeek с MCP Tools и новым промптом")
    print("=" * 60)

    # Создаем MCP клиенты
    print("\n📡 Подключение к MCP серверам...")

    # GitHub MCP
    github_config = get_github_mcp_config()
    github_client = MCPClient(github_config)
    await github_client.connect()
    print(f"✅ GitHub MCP подключен")

    # Filesystem MCP
    filesystem_config = get_filesystem_mcp_config()
    filesystem_client = MCPClient(filesystem_config)
    await filesystem_client.connect()
    print(f"✅ Filesystem MCP подключен")

    # Создаем DeepSeek провайдер с MCP клиентами
    print("\n🤖 Создание DeepSeek провайдера...")
    provider = DeepSeekProvider(deepseek_api_key, mcp_client=github_client)
    provider.add_mcp_client(filesystem_client)
    print(f"✅ DeepSeek провайдер создан с {len(provider.mcp_clients)} MCP клиентами")

    # Тестовый запрос
    test_message = "Сохрани информацию о github пользователе torvalds в файл ~/torvalds_info.txt"

    print("\n" + "=" * 60)
    print(f"📝 Тестовый запрос: {test_message}")
    print("=" * 60)

    print(f"\n🎯 Используемый промпт (первые 300 символов):")
    print(SYSTEM_PROMPT_DEEPSEEK_WITH_TOOLS[:300] + "...")

    # Отправляем запрос
    print("\n⏳ Отправка запроса в DeepSeek API...")
    response = await provider.generate_response(
        user_message=test_message,
        system_prompt=SYSTEM_PROMPT_DEEPSEEK_WITH_TOOLS,
        conversation_history=[]
    )

    print("\n" + "=" * 60)
    print("📬 РЕЗУЛЬТАТ:")
    print("=" * 60)
    if response:
        print(response)
        print("\n✅ Тест завершен успешно!")
    else:
        print("❌ Не удалось получить ответ от DeepSeek")

    # Отключаем клиенты
    print("\n🔌 Отключение от MCP серверов...")
    await github_client.disconnect()
    await filesystem_client.disconnect()
    print("✅ Отключено")

if __name__ == "__main__":
    asyncio.run(test_deepseek_with_tools())
