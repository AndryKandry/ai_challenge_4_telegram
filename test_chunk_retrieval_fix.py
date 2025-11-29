#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления получения чанков по ID.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_rag_manager_get_chunk_by_id():
    """Тест 1: Получение чанка из RAG Manager по ID"""
    print("\n" + "=" * 80)
    print("ТЕСТ 1: RAG Manager - get_chunk_by_id()")
    print("=" * 80)

    try:
        from src.rag_integration import RAGManager

        # Инициализируем RAG Manager
        rag = RAGManager()
        print("✓ RAG Manager инициализирован")

        # Получаем статистику для проверки наличия чанков
        stats = rag.get_statistics()
        total_chunks = stats.get('total_chunks', 0)
        print(f"✓ Всего чанков в индексе: {total_chunks}")

        if total_chunks == 0:
            print("❌ Индекс пустой, невозможно протестировать")
            return False

        # Загружаем индекс для получения примера chunk_id
        if not rag.searcher.index:
            rag.searcher._load_index()

        chunks = rag.searcher.index.get('chunks', [])
        if not chunks:
            print("❌ Не удалось загрузить чанки")
            return False

        # Берём первый чанк для теста
        test_chunk = chunks[0]
        test_chunk_id = test_chunk.get('chunk_id')

        if not test_chunk_id:
            print("❌ У первого чанка нет ID")
            return False

        print(f"\n✓ Тестовый chunk_id: {test_chunk_id}")

        # Пытаемся получить чанк по ID
        retrieved_chunk = rag.get_chunk_by_id(test_chunk_id)

        if not retrieved_chunk:
            print(f"❌ Не удалось получить чанк по ID: {test_chunk_id}")
            return False

        print(f"✅ Чанк успешно получен!")
        print(f"   - Chunk ID: {retrieved_chunk.get('chunk_id')}")
        print(f"   - Текст (первые 50 символов): {retrieved_chunk.get('text', '')[:50]}...")
        print(f"   - Source file: {retrieved_chunk.get('metadata', {}).get('source_file', 'unknown')}")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_telegram_handler_get_chunk():
    """Тест 2: Получение чанка через TelegramDocumentHandler"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: TelegramDocumentHandler - _get_chunk_content_by_id()")
    print("=" * 80)

    try:
        from src.rag_integration import RAGManager
        from src.integrations.telegram_document_handler import TelegramDocumentHandler
        import asyncio

        # Инициализируем RAG Manager
        rag = RAGManager()
        print("✓ RAG Manager инициализирован")

        # Создаём обработчик документов
        handler = TelegramDocumentHandler(rag)
        print("✓ TelegramDocumentHandler создан")

        # Получаем тестовый chunk_id
        if not rag.searcher.index:
            rag.searcher._load_index()

        chunks = rag.searcher.index.get('chunks', [])
        if not chunks:
            print("❌ Нет чанков для тестирования")
            return False

        test_chunk_id = chunks[0].get('chunk_id')
        print(f"\n✓ Тестовый chunk_id: {test_chunk_id}")

        # Получаем чанк через handler (async метод)
        async def test():
            chunk_info = await handler._get_chunk_content_by_id(test_chunk_id)
            return chunk_info

        chunk_info = asyncio.run(test())

        if not chunk_info:
            print(f"❌ Не удалось получить чанк")
            return False

        print(f"✅ Чанк успешно получен через handler!")
        print(f"   - Source file: {chunk_info.get('source_file')}")
        print(f"   - Content (первые 50 символов): {chunk_info.get('content', '')[:50]}...")
        print(f"   - Line numbers: {chunk_info.get('line_numbers')}")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_real_chunk_from_logs():
    """Тест 3: Тестирование с реальным chunk_id из логов"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Получение чанка с ID из логов")
    print("=" * 80)

    try:
        from src.rag_integration import RAGManager
        from src.integrations.telegram_document_handler import TelegramDocumentHandler
        import asyncio

        # chunk_id из логов ошибки
        real_chunk_id = "БОЛИВАРСКАЯ КОММУНА_txt_chunk_0"
        print(f"✓ Тестовый chunk_id из логов: {real_chunk_id}")

        # Инициализируем RAG Manager
        rag = RAGManager()

        # Пытаемся получить чанк
        chunk = rag.get_chunk_by_id(real_chunk_id)

        if not chunk:
            print(f"❌ Чанк не найден в индексе")
            print(f"   Возможно, chunk_id изменился после переиндексации")

            # Попробуем найти похожий
            if not rag.searcher.index:
                rag.searcher._load_index()

            chunks = rag.searcher.index.get('chunks', [])
            similar_chunks = [c for c in chunks if 'БОЛИВАРСКАЯ' in c.get('chunk_id', '')]

            if similar_chunks:
                print(f"\n   Найдено похожих чанков: {len(similar_chunks)}")
                for i, c in enumerate(similar_chunks[:3], 1):
                    print(f"   {i}. {c.get('chunk_id')}")

                # Тестируем с первым похожим
                test_chunk_id = similar_chunks[0].get('chunk_id')
                print(f"\n✓ Пробуем с похожим chunk_id: {test_chunk_id}")

                handler = TelegramDocumentHandler(rag)

                async def test():
                    return await handler._get_chunk_content_by_id(test_chunk_id)

                chunk_info = asyncio.run(test())

                if chunk_info:
                    print(f"✅ Похожий чанк успешно получен!")
                    print(f"   - Source file: {chunk_info.get('source_file')}")
                    print(f"   - Content preview: {chunk_info.get('content', '')[:100]}...")
                    return True
                else:
                    print(f"❌ Не удалось получить похожий чанк")
                    return False
            else:
                print(f"   Похожих чанков не найдено")
                return False
        else:
            print(f"✅ Чанк найден в индексе!")
            print(f"   - Source file: {chunk.get('metadata', {}).get('source_file')}")
            print(f"   - Text preview: {chunk.get('text', '')[:100]}...")
            return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ ПОЛУЧЕНИЯ ЧАНКОВ ПО ID")
    print("=" * 80)

    tests = [
        ("RAG Manager - get_chunk_by_id", test_rag_manager_get_chunk_by_id),
        ("TelegramDocumentHandler", test_telegram_handler_get_chunk),
        ("Реальный chunk_id из логов", test_real_chunk_from_logs),
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
        print("\n✅ Получение чанков по ID ИСПРАВЛЕНО")
        return 0
    else:
        print(f"\n⚠️  Некоторые тесты провалены.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
