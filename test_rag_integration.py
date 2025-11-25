#!/usr/bin/env python3
"""
Тестовый скрипт для проверки RAG интеграции.
"""

import asyncio
import sys
from src.rag_integration import RAGManager


async def test_rag_integration():
    """Тестирует основные функции RAG интеграции."""

    print("🧪 Тестирование RAG интеграции\n")

    # Инициализация RAG Manager
    print("1. Инициализация RAG Manager...")
    try:
        rag_manager = RAGManager()
        print("   ✅ RAG Manager инициализирован\n")
    except Exception as e:
        print(f"   ❌ Ошибка инициализации: {e}\n")
        return False

    # Получение статистики
    print("2. Проверка статистики индекса...")
    try:
        stats = rag_manager.get_statistics()
        print(f"   📊 Статистика:")
        print(f"      - Включено: {stats.get('enabled')}")
        print(f"      - Документов: {stats.get('total_documents', 0)}")
        print(f"      - Чанков: {stats.get('total_chunks', 0)}")
        print(f"      - Ключевых слов: {stats.get('keywords_count', 0)}")
        print(f"      - Top-K: {stats.get('top_k', 0)}")
        print()
    except Exception as e:
        print(f"   ❌ Ошибка получения статистики: {e}\n")
        return False

    # Тест поиска
    print("3. Тест поиска релевантного контекста...")
    test_queries = [
        "как запустить бота",
        "что такое температура",
        "команды бота"
    ]

    for query in test_queries:
        print(f"   🔍 Запрос: '{query}'")
        try:
            results = rag_manager.search_relevant_context(query, top_k=3)

            if results:
                print(f"      Найдено документов: {len(results)}")
                for i, result in enumerate(results, 1):
                    source = result['source_file'].split('/')[-1]
                    similarity = result['similarity_score']
                    text_preview = result['text'][:80] + "..."
                    print(f"      {i}. {source} (сходство: {similarity:.3f})")
                    print(f"         {text_preview}")
            else:
                print(f"      ℹ️  Релевантных документов не найдено")
            print()
        except Exception as e:
            print(f"      ❌ Ошибка поиска: {e}\n")

    # Тест определения необходимости RAG
    print("4. Тест определения необходимости RAG...")
    test_messages = [
        ("Как запустить бота?", True),
        ("Привет!", False),
        ("Расскажи про команды", True),
        ("Какая погода?", False)
    ]

    for message, expected in test_messages:
        should_use = rag_manager.should_use_rag(message)
        status = "✅" if should_use == expected else "❌"
        print(f"   {status} '{message}' -> RAG: {should_use} (ожидалось: {expected})")
    print()

    # Тест обогащения сообщения
    print("5. Тест обогащения сообщения контекстом...")
    test_message = "Как запустить бота?"
    try:
        enriched_message, sources = rag_manager.enrich_message_with_rag(test_message)

        if sources:
            print(f"   ✅ Сообщение обогащено")
            print(f"   📚 Использовано источников: {len(sources)}")
            for i, source in enumerate(sources, 1):
                source_file = source['source_file'].split('/')[-1]
                print(f"      {i}. {source_file} (сходство: {source['similarity_score']:.3f})")

            # Показываем фрагмент обогащенного сообщения
            preview_length = 200
            if len(enriched_message) > preview_length:
                preview = enriched_message[:preview_length] + "..."
            else:
                preview = enriched_message
            print(f"\n   📝 Фрагмент обогащенного сообщения:")
            print(f"      {preview}\n")
        else:
            print(f"   ℹ️  Сообщение не было обогащено (не сработали триггеры RAG)\n")
    except Exception as e:
        print(f"   ❌ Ошибка обогащения: {e}\n")
        return False

    # Тест форматирования источников
    print("6. Тест форматирования источников для пользователя...")
    if sources:
        try:
            sources_info = rag_manager.format_sources_info(sources)
            print("   📋 Форматированная информация об источниках:")
            print(sources_info)
        except Exception as e:
            print(f"   ❌ Ошибка форматирования: {e}\n")
    else:
        print("   ⏭️  Пропущено (нет источников)\n")

    print("✅ Все тесты завершены!\n")
    return True


def main():
    """Главная функция."""
    try:
        result = asyncio.run(test_rag_integration())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
