#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления ошибки Button_data_invalid.
Проверяет что callback_data для inline кнопок не превышает 64 байт.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.integrations.telegram_document_handler import TelegramDocumentHandler


def test_callback_data_length():
    """Тест 1: Проверка длины callback_data"""
    print("\n" + "=" * 80)
    print("ТЕСТ 1: Проверка длины callback_data")
    print("=" * 80)

    # Создаём mock RAG manager
    class MockRAGManager:
        def search_relevant_context(self, query, top_k):
            return []

    handler = TelegramDocumentHandler(MockRAGManager())

    # Тестируем разные варианты путей
    test_cases = [
        {
            'source_file': '/Users/andreykozyrev/PycharmProjects/ai_challenge_4_telegram/rag_docs/documentation/sumrak2096/pravila_igry.txt',
            'chunk_id': 'pravila_igry_txt_chunk_0',
            'line_numbers': '1-20'
        },
        {
            'source_file': '/very/long/path/to/some/deeply/nested/directory/structure/with/many/subdirs/document.md',
            'chunk_id': 'very_long_document_name_with_many_characters_chunk_42',
            'line_numbers': '100-150'
        },
        {
            'source_file': '/short/path.txt',
            'chunk_id': 'short_chunk_1',
            'line_numbers': '1-5'
        }
    ]

    all_passed = True

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Тест кейс {i}:")
        print(f"   Файл: {test_case['source_file'][:50]}...")
        print(f"   Chunk ID: {test_case['chunk_id']}")

        # Генерируем callback_data
        callback_data = handler._create_callback_data(
            test_case['source_file'],
            test_case['chunk_id'],
            test_case['line_numbers']
        )

        # Проверяем длину
        byte_length = len(callback_data.encode('utf-8'))

        print(f"   Callback data: {callback_data}")
        print(f"   Длина в байтах: {byte_length}")

        if byte_length <= 64:
            print(f"   ✅ PASSED (лимит: 64 байт)")
        else:
            print(f"   ❌ FAILED (превышен лимит 64 байт!)")
            all_passed = False

    if all_passed:
        print("\n✅ Все тесты пройдены!")
        return True
    else:
        print("\n❌ Некоторые тесты провалены!")
        return False


def test_callback_data_parsing():
    """Тест 2: Проверка парсинга callback_data"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Проверка парсинга callback_data")
    print("=" * 80)

    class MockRAGManager:
        def search_relevant_context(self, query, top_k):
            return []

    handler = TelegramDocumentHandler(MockRAGManager())

    # Тестовые данные
    test_chunk_id = "test_document_chunk_5"

    # Создаём callback_data
    callback_data = handler._create_callback_data(
        "/some/path/test.txt",
        test_chunk_id,
        "10-20"
    )

    print(f"\n✓ Создан callback_data: {callback_data}")

    # Парсим обратно
    parsed = handler._parse_callback_data(callback_data)

    if parsed and parsed['chunk_id'] == test_chunk_id:
        print(f"✅ Парсинг успешен!")
        print(f"   Извлечённый chunk_id: {parsed['chunk_id']}")
        return True
    else:
        print(f"❌ Парсинг провален!")
        return False


def test_button_creation():
    """Тест 3: Проверка создания inline кнопок"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Проверка создания inline кнопок")
    print("=" * 80)

    class MockRAGManager:
        def search_relevant_context(self, query, top_k):
            return []

    handler = TelegramDocumentHandler(MockRAGManager())

    # Создаём кнопку
    button = handler.create_document_button(
        source_file="/rag_docs/documentation/guide.md",
        chunk_id="guide_md_chunk_0",
        line_numbers="1-20",
        relevance="95%"
    )

    print(f"\n✓ Создана кнопка:")
    print(f"   Текст: {button.text}")
    print(f"   Callback data: {button.callback_data}")
    print(f"   Длина callback data: {len(button.callback_data.encode('utf-8'))} байт")

    if len(button.callback_data.encode('utf-8')) <= 64:
        print(f"✅ Кнопка создана корректно (< 64 байт)")
        return True
    else:
        print(f"❌ Кнопка превышает лимит Telegram!")
        return False


def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ ОШИБКИ BUTTON_DATA_INVALID")
    print("=" * 80)

    tests = [
        ("Проверка длины callback_data", test_callback_data_length),
        ("Проверка парсинга callback_data", test_callback_data_parsing),
        ("Проверка создания inline кнопок", test_button_creation),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Тест '{test_name}' провален с ошибкой!")
            print(f"   Ошибка: {e}")
            failed += 1

    # Итоговая статистика
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print(f"✅ Пройдено: {passed}/{len(tests)}")
    print(f"❌ Провалено: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 Все тесты пройдены успешно!")
        print("\n✅ Ошибка Button_data_invalid ИСПРАВЛЕНА")
        return 0
    else:
        print(f"\n⚠️  Некоторые тесты провалены.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
