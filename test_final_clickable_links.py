#!/usr/bin/env python3
"""
Финальный интеграционный тест для проверки полной функциональности кликабельных ссылок в Telegram.
Проверяет полную цепочку: Bot → RAG → Inline Buttons → Callback Handling.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_clickable_links_complete():
    """Полная проверка функциональности кликабельных ссылок."""
    print("🔍 ФИНАЛЬНАЯ ПРОВЕРКА КЛИКАБЕЛЬНЫХ ССЫЛОК")
    print("=" * 60)
    
    success_count = 0
    total_tests = 7
    
    # Тест 1: Проверка инициализации компонентов
    print("\n1️⃣ Проверка инициализации компонентов...")
    try:
        from src.rag_integration import RAGManager
        from src.integrations.telegram_document_handler import create_telegram_document_handler
        
        rag_manager = RAGManager()
        doc_handler = create_telegram_document_handler(rag_manager)
        rag_manager.set_document_handler(doc_handler)
        
        print("   ✅ RAG Manager инициализирован")
        print("   ✅ Telegram Document Handler инициализирован")
        print("   ✅ Document handler установлен в RAG Manager")
        success_count += 1
    except Exception as e:
        print(f"   ❌ Ошибка инициализации: {e}")
    
    # Тест 2: Проверка форматирования inline кнопок
    print("\n2️⃣ Проверка форматирования inline кнопок...")
    try:
        mock_sources = [
            {
                "source_file": "/rag_docs/documentation/guide.md",
                "chunk_id": "guide_md_chunk_0",
                "line_numbers": "1-20",
                "relevance_percentage": "95%",
                "similarity_score": 0.95
            },
            {
                "source_file": "/rag_docs/reference/api_keys.txt",
                "chunk_id": "api_keys_txt_chunk_1",
                "line_numbers": "15-35",
                "relevance_percentage": "87%",
                "similarity_score": 0.87
            }
        ]
        
        sources_text, inline_keyboard = rag_manager.format_sources_with_telegram_buttons(
            mock_sources,
            title="📚 **Источники:**"
        )
        
        if sources_text and inline_keyboard:
            print("   ✅ Текст с источниками отформатирован")
            print("   ✅ Inline клавиатура создана")
            print(f"   ✅ Количество кнопок: {len(inline_keyboard.inline_keyboard)}")
            success_count += 1
        else:
            print("   ❌ Ошибка форматирования inline кнопок")
    except Exception as e:
        print(f"   ❌ Ошибка форматирования: {e}")
    
    # Тест 3: Проверка callback данных
    print("\n3️⃣ Проверка callback данных...")
    try:
        test_callback_data = doc_handler._create_callback_data(
            "/test/file.md", "chunk_0", "1-20"
        )
        parsed_data = doc_handler._parse_callback_data(test_callback_data)
        
        if parsed_data and parsed_data['source_file'] == "/test/file.md":
            print("   ✅ Callback данные корректно созданы")
            print("   ✅ Callback данные корректно распарсены")
            success_count += 1
        else:
            print("   ❌ Ошибка обработки callback данных")
    except Exception as e:
        print(f"   ❌ Ошибка обработки callback данных: {e}")
    
    # Тест 4: Проверка обработки нажатий
    print("\n4️⃣ Проверка обработки нажатий...")
    try:
        from telegram import Update, CallbackQuery
        from telegram.ext import ContextTypes
        
        # Создаем mock объекты
        mock_update = Mock(spec=Update)
        mock_update.callback_query = Mock(spec=CallbackQuery)
        mock_update.callback_query.data = test_callback_data
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.message = Mock()
        mock_update.callback_query.message.reply_text = AsyncMock()
        mock_update.callback_query.message.reply_document = AsyncMock()
        
        mock_context = Mock(spec=ContextTypes)
        
        # Пытаемся обработать нажатие
        await doc_handler.handle_document_callback(mock_update, mock_context)
        
        print("   ✅ Обработка нажатия завершена без ошибок")
        success_count += 1
    except Exception as e:
        print(f"   ❌ Ошибка обработки нажатия: {e}")
    
    # Тест 5: Проверка интеграции с ботом
    print("\n5️⃣ Проверка интеграции с ботом...")
    try:
        # Проверяем, что бот может использовать inline кнопки
        if hasattr(rag_manager, 'format_sources_with_telegram_buttons'):
            print("   ✅ Метод format_sources_with_telegram_buttons доступен")
            success_count += 1
        else:
            print("   ❌ Метод format_sources_with_telegram_buttons недоступен")
    except Exception as e:
        print(f"   ❌ Ошибка проверки интеграции: {e}")
    
    # Тест 6: Проверка эмодзи для файлов
    print("\n6️⃣ Проверка эмодзи для файлов...")
    try:
        test_files = [
            ("test.txt", "📄"),
            ("test.md", "📝"),
            ("test.markdown", "📝"),
            ("test.py", "🐍"),
            ("test.json", "📋"),
            ("unknown.xyz", "📄")
        ]
        
        emoji_success = 0
        for filename, expected_emoji in test_files:
            actual_emoji = doc_handler._get_file_emoji(filename)
            if actual_emoji == expected_emoji:
                print(f"   ✅ {filename}: {actual_emoji}")
                emoji_success += 1
            else:
                print(f"   ❌ {filename}: {actual_emoji} (ожидалось: {expected_emoji})")
        
        if emoji_success == len(test_files):
            success_count += 1
    except Exception as e:
        print(f"   ❌ Ошибка проверки эмодзи: {e}")
    
    # Тест 7: Проверка graceful degradation
    print("\n7️⃣ Проверка graceful degradation...")
    try:
        # Проверяем, что система работает без document handler
        rag_no_handler = RAGManager()
        rag_no_handler.enable_clickable_links = True
        
        mock_sources = [
            {
                "source_file": "/test/file.txt",
                "chunk_id": "chunk_0",
                "relevance_percentage": "95%",
                "similarity_score": 0.95
            }
        ]
        
        # Должен использовать fallback формат
        fallback_result = rag_no_handler.format_sources_info(mock_sources)
        if fallback_result and "Использованные источники RAG" in fallback_result:
            print("   ✅ Graceful degradation работает корректно")
            success_count += 1
        else:
            print("   ❌ Graceful degradation не работает")
    except Exception as e:
        print(f"   ❌ Ошибка graceful degradation: {e}")
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ФИНАЛЬНОЙ ПРОВЕРКИ")
    print("=" * 60)
    print(f"✅ Пройдено тестов: {success_count}/{total_tests}")
    print(f"❌ Провалено тестов: {total_tests - success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("🎉 ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
        print("💡 Кликабельные ссылки полностью готовы к использованию!")
        return True
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        print("💡 Рекомендуется проверить настройки и зависимости")
        return False

def main():
    """Главная функция для запуска тестов."""
    print("🚀 Запуск финальной проверки кликабельных ссылок...")
    
    success = asyncio.run(test_clickable_links_complete())
    
    if success:
        print("\n✅ Кликабельные ссылки успешно протестированы и готовы к использованию!")
        sys.exit(0)
    else:
        print("\n❌ Некоторые тесты не пройдены. Проверьте логи выше.")
        sys.exit(1)

if __name__ == "__main__":
    main()
