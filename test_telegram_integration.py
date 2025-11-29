#!/usr/bin/env python3
"""
Интеграционный тест для проверки кликабельных ссылок в Telegram.
Проверяет полную цепочку: RAG → Telegram Document Handler → Inline Buttons.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.rag_integration import RAGManager
from src.integrations.telegram_document_handler import TelegramDocumentHandler


class MockUpdate:
    """Mock объект для Telegram Update."""
    def __init__(self, callback_data: str):
        self.callback_query = Mock()
        self.callback_query.data = callback_data
        self.callback_query.answer = AsyncMock()
        self.callback_query.edit_message_text = AsyncMock()


class MockContext:
    """Mock объект для Telegram Context."""
    pass


async def test_telegram_document_handler():
    """Тест Telegram Document Handler с inline кнопками."""
    print("\n" + "=" * 80)
    print("ТЕСТ: Telegram Document Handler - Inline Buttons")
    print("=" * 80)

    try:
        # Инициализация RAG Manager
        rag_manager = RAGManager()
        print("✓ RAG Manager инициализирован")

        # Инициализация Telegram Document Handler
        doc_handler = TelegramDocumentHandler(rag_manager)
        print("✓ Telegram Document Handler инициализирован")

        # Создаем mock данные для теста
        mock_search_results = [
            {
                "source_file": "/rag_docs/documentation/guide.md",
                "chunk_id": "guide_md_chunk_0",
                "line_numbers": "1-20",
                "relevance_percentage": "95%",
                "similarity_score": 0.95,
                "text": "Это тестовый контент из guide.md"
            },
            {
                "source_file": "/rag_docs/reference/api_keys.txt",
                "chunk_id": "api_keys_txt_chunk_1",
                "line_numbers": "15-35",
                "relevance_percentage": "87%",
                "similarity_score": 0.87,
                "text": "Это тестовый контент из api_keys.txt"
            }
        ]

        # Тест форматирования с кнопками
        sources_text, inline_keyboard = doc_handler.format_sources_with_buttons(
            mock_search_results,
            max_sources=5,
            title="📚 **Источники:**"
        )

        print(f"\n✓ Отформатированный текст с кнопками:\n{sources_text}")

        if inline_keyboard:
            print("✓ Inline клавиатура создана")
            print(f"  Количество кнопок: {len(inline_keyboard.inline_keyboard)}")
            
            # Проверяем структуру кнопок
            for i, row in enumerate(inline_keyboard.inline_keyboard):
                for j, button in enumerate(row):
                    print(f"  Кнопка {i+1}-{j+1}: {button.text}")
                    assert button.callback_data, "У кнопки должен быть callback_data"
                    assert button.callback_data.startswith("doc_"), "Callback data должен начинаться с doc_"
        else:
            print("❌ Inline клавиатура не создана")
            return False

        print("\n✅ Тест Telegram Document Handler пройден!")
        return True

    except Exception as e:
        print(f"\n❌ Ошибка в тесте Telegram Document Handler: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_callback_data_handling():
    """Тест обработки callback данных."""
    print("\n" + "=" * 80)
    print("ТЕСТ: Callback Data Handling")
    print("=" * 80)

    try:
        rag_manager = RAGManager()
        doc_handler = TelegramDocumentHandler(rag_manager)

        # Тестовые данные
        test_file = "/rag_docs/documentation/guide.md"
        test_chunk = "guide_md_chunk_0"
        test_lines = "1-20"

        # Создаем callback data
        callback_data = doc_handler._create_callback_data(test_file, test_chunk, test_lines)
        print(f"✓ Создана callback data: {callback_data[:50]}...")

        # Парсим callback data
        parsed_data = doc_handler._parse_callback_data(callback_data)
        print(f"✓ Распарсена callback data:")
        print(f"  Файл: {parsed_data['source_file']}")
        print(f"  Чанк: {parsed_data['chunk_id']}")
        print(f"  Строки: {parsed_data['line_numbers']}")

        # Проверяем корректность
        assert parsed_data['source_file'] == test_file
        assert parsed_data['chunk_id'] == test_chunk
        assert parsed_data['line_numbers'] == test_lines

        print("\n✅ Тест callback data handling пройден!")
        return True

    except Exception as e:
        print(f"\n❌ Ошибка в тесте callback data handling: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integration_with_rag():
    """Тест интеграции с RAG Manager."""
    print("\n" + "=" * 80)
    print("ТЕСТ: Интеграция с RAG Manager")
    print("=" * 80)

    try:
        rag_manager = RAGManager()
        doc_handler = TelegramDocumentHandler(rag_manager)

        # Проверяем, что RAG Manager имеет document handler
        assert hasattr(rag_manager, 'document_handler'), "RAG Manager должен иметь document_handler"
        rag_manager.set_document_handler(doc_handler)
        print("✓ Document handler установлен в RAG Manager")

        # Тестируем метод format_sources_with_telegram_buttons
        mock_results = [
            {
                "source_file": "/rag_docs/documentation/guide.md",
                "chunk_id": "guide_md_chunk_0",
                "line_numbers": "1-20",
                "relevance_percentage": "95%"
            }
        ]

        sources_text, inline_keyboard = rag_manager.format_sources_with_telegram_buttons(
            mock_results,
            max_sources=3,
            title="📚 **Источники:**"
        )

        print(f"✓ Метод format_sources_with_telegram_buttons работает:")
        print(f"  Текст: {sources_text[:100]}...")
        print(f"  Клавиатура: {'создана' if inline_keyboard else 'не создана'}")

        print("\n✅ Тест интеграции с RAG Manager пройден!")
        return True

    except Exception as e:
        print(f"\n❌ Ошибка в тесте интеграции с RAG Manager: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_mock_callback_query():
    """Тест обработки mock callback запроса."""
    print("\n" + "=" * 80)
    print("ТЕСТ: Mock Callback Query")
    print("=" * 80)

    try:
        rag_manager = RAGManager()
        doc_handler = TelegramDocumentHandler(rag_manager)

        # Создаем mock callback данные
        test_file = "/rag_docs/documentation/guide.md"
        test_chunk = "guide_md_chunk_0"
        test_lines = "1-20"

        callback_data = doc_handler._create_callback_data(test_file, test_chunk, test_lines)
        
        # Создаем mock объекты
        mock_update = MockUpdate(callback_data)
        mock_context = MockContext()

        print("✓ Mock объекты созданы")
        print(f"  Callback data: {callback_data[:50]}...")

        # Проверяем, что метод можно вызвать без ошибок
        # (реальная обработка требует настоящего Telegram бота)
        try:
            # Проверяем парсинг данных
            parsed_data = doc_handler._parse_callback_data(callback_data)
            assert parsed_data is not None, "Данные должны быть распарсены"
            print("✓ Callback данные корректно парсятся")

            # Проверяем получение эмодзи
            emoji = doc_handler._get_file_emoji(test_file)
            print(f"✓ Эмодзи для файла: {emoji}")

            print("\n✅ Тест mock callback query пройден!")
            return True

        except Exception as e:
            print(f"❌ Ошибка при обработке callback: {e}")
            return False

    except Exception as e:
        print(f"\n❌ Ошибка в тесте mock callback query: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_integration_tests():
    """Запуск всех интеграционных тестов."""
    print("\n" + "=" * 80)
    print("ИНТЕГРАЦИОННОЕ ТЕСТИРОВАНИЕ КЛИКАБЕЛЬНЫХ ССЫЛОК")
    print("=" * 80)

    tests = [
        ("Telegram Document Handler", test_telegram_document_handler),
        ("Callback Data Handling", test_callback_data_handling),
        ("Интеграция с RAG Manager", test_integration_with_rag),
        ("Mock Callback Query", test_mock_callback_query),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Тест '{test_name}' провален с исключением!")
            print(f"   Ошибка: {e}")
            failed += 1

    # Итоговая статистика
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА ИНТЕГРАЦИОННЫХ ТЕСТОВ")
    print("=" * 80)
    print(f"✅ Пройдено: {passed}/{len(tests)}")
    print(f"❌ Провалено: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 Все интеграционные тесты пройдены успешно!")
        print("💡 Кликабельные ссылки готовы к использованию в Telegram боте!")
        return 0
    else:
        print(f"\n⚠️ Некоторые интеграционные тесты провалены.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_all_integration_tests()))
