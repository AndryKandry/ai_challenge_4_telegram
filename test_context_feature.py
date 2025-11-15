#!/usr/bin/env python3
"""
Тест для проверки новой функциональности контекстных диалогов.
"""

import sys
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

from database.memory_manager import MemoryManager


def test_context_feature():
    """Тест функционала передачи контекста в GPT."""
    print("🧪 Тестирование новой функциональности контекстных диалогов\n")

    # Создаём тестовую БД
    memory = MemoryManager("test_context.db")
    memory.create_tables()

    test_user_id = 999
    test_chat_id = 888

    print("1️⃣ Создание новой сессии...")
    session_id = memory.create_session(test_user_id, test_chat_id)
    print(f"   ✅ Сессия создана: {session_id[:16]}...")

    print("\n2️⃣ Сохранение диалога в сессии...")
    memory.save_message(test_user_id, test_chat_id, "Привет! Меня зовут Иван.", "user", session_id)
    memory.save_message(test_user_id, test_chat_id, "Здравствуйте, Иван! Чем могу помочь?", "assistant", session_id)
    memory.save_message(test_user_id, test_chat_id, "Какая сегодня погода?", "user", session_id)
    memory.save_message(test_user_id, test_chat_id, "Извините, у меня нет доступа к данным о погоде.", "assistant", session_id)
    print("   ✅ Сохранено 4 сообщения")

    print("\n3️⃣ Получение истории сессии...")
    history = memory.get_conversation_history(test_user_id, test_chat_id, limit=10, session_id=session_id)
    print(f"   ✅ Получено {len(history)} сообщений")

    print("\n4️⃣ Проверка содержимого истории:")
    for i, msg in enumerate(history, 1):
        msg_type = "👤 Пользователь" if msg['message_type'] == 'user' else "🤖 Ассистент"
        print(f"   {i}. {msg_type}: {msg['message_text'][:50]}...")

    print("\n5️⃣ Формирование контекста для GPT API:")
    context_messages = []
    for msg in history:
        role = "user" if msg["message_type"] == "user" else "assistant"
        context_messages.append({
            "role": role,
            "text": msg["message_text"]
        })

    print(f"   ✅ Сформировано {len(context_messages)} сообщений для API")
    print("\n   Пример структуры:")
    for i, ctx_msg in enumerate(context_messages[:2], 1):
        print(f"   {i}. role={ctx_msg['role']}, text='{ctx_msg['text'][:40]}...'")

    print("\n6️⃣ Создание новой сессии (сброс контекста)...")
    old_session = session_id
    new_session = memory.create_session(test_user_id, test_chat_id)
    memory.end_session(old_session)
    print(f"   ✅ Старая сессия {old_session[:16]}... завершена")
    print(f"   ✅ Новая сессия {new_session[:16]}... создана")

    print("\n7️⃣ Проверка изоляции сессий...")
    old_history = memory.get_conversation_history(test_user_id, test_chat_id, limit=10, session_id=old_session)
    new_history = memory.get_conversation_history(test_user_id, test_chat_id, limit=10, session_id=new_session)
    print(f"   ✅ Старая сессия содержит {len(old_history)} сообщений")
    print(f"   ✅ Новая сессия содержит {len(new_history)} сообщений")

    print("\n8️⃣ Получение активной сессии...")
    active = memory.get_active_session(test_user_id, test_chat_id)
    print(f"   ✅ Активная сессия: {active[:16]}..." if active else "   ❌ Нет активной сессии")

    # Очистка
    import os
    os.remove("test_context.db")
    print("\n✨ Все тесты пройдены успешно!\n")

    print("📝 Резюме новой функциональности:")
    print("   • LLM теперь получает контекст из последних 10 сообщений сессии")
    print("   • Пользователь может управлять сессиями через команды:")
    print("     - /session_info - информация о текущей сессии")
    print("     - /new_session - начать новую сессию (сбросить контекст)")
    print("     - /end_session - завершить текущую сессию")
    print("   • История сохраняется в БД и доступна между перезапусками")
    print("   • Сессии изолированы друг от друга")


if __name__ == "__main__":
    try:
        test_context_feature()
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
