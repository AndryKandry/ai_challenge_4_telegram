#!/usr/bin/env python3
"""
Скрипт для интерактивной авторизации Telegram клиента.

Создаёт session файл для Pyrogram, который затем будет использоваться
MCP сервером telegram_assistant.

Запустите этот скрипт ОДИН РАЗ перед первым использованием telegram_assistant.
"""

import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

try:
    from pyrogram import Client
except ImportError:
    print("❌ Pyrogram не установлен!")
    print("Установите: pip install pyrogram tgcrypto")
    sys.exit(1)

def main():
    """Главная функция для создания Telegram session."""
    print("=" * 60)
    print("НАСТРОЙКА TELEGRAM SESSION ДЛЯ MCP СЕРВЕРА")
    print("=" * 60)
    print()

    # Получаем credentials
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("❌ ОШИБКА: TELEGRAM_API_ID или TELEGRAM_API_HASH не найдены в .env")
        print()
        print("Получите эти данные на https://my.telegram.org/apps")
        print("И добавьте в файл .env:")
        print("  TELEGRAM_API_ID=your_api_id")
        print("  TELEGRAM_API_HASH=your_api_hash")
        sys.exit(1)

    print(f"✅ API ID: {api_id}")
    print(f"✅ API Hash: {api_hash[:8]}...")
    print()

    # Создаём директорию для session файлов
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    print(f"✅ Директория для session: {data_dir}/")
    print()

    # Создаём клиента
    print("Создание Telegram клиента...")
    client = Client(
        name="telegram_assistant_mcp",
        api_id=api_id,
        api_hash=api_hash,
        workdir=data_dir
    )

    print()
    print("=" * 60)
    print("АВТОРИЗАЦИЯ")
    print("=" * 60)
    print()
    print("Сейчас вам нужно будет:")
    print("1. Ввести номер телефона (в международном формате, например: +79991234567)")
    print("2. Ввести код подтверждения из Telegram")
    print("3. Если включена 2FA - ввести пароль")
    print()
    print("Это нужно сделать ОДИН РАЗ. Session файл сохранится и будет")
    print("использоваться автоматически при следующих запусках.")
    print()
    input("Нажмите Enter для начала авторизации...")
    print()

    try:
        # Запускаем клиента (тут будет интерактивный ввод)
        with client:
            # Получаем информацию о себе
            me = client.get_me()
            print()
            print("=" * 60)
            print("✅ АВТОРИЗАЦИЯ УСПЕШНА!")
            print("=" * 60)
            print()
            print(f"Вы вошли как: {me.first_name}")
            if me.username:
                print(f"Username: @{me.username}")
            print(f"ID: {me.id}")
            print()
            print(f"Session файл сохранён: {data_dir}/telegram_assistant_mcp.session")
            print()
            print("Теперь можете запускать MCP сервер и бота:")
            print("  python mcp_server/telegram_assistant.py")
            print("  python bot.py")
            print()

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ОШИБКА АВТОРИЗАЦИИ")
        print("=" * 60)
        print()
        print(f"Причина: {e}")
        print()
        print("Проверьте:")
        print("1. Правильность TELEGRAM_API_ID и TELEGRAM_API_HASH")
        print("2. Правильность введённого номера телефона")
        print("3. Правильность кода подтверждения")
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()
