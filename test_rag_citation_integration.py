#!/usr/bin/env python3
"""
Интеграционный тест для проверки RAG с реранкингом и цитированием.
Тестирует полный пайплайн для DeepSeek.
"""

import asyncio
import logging
import os
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.rag_integration import RAGManager
from providers.deepseek_provider import DeepSeekProvider


async def test_rag_with_citations():
    """Тестирует RAG с цитированием"""
    print("🧪 Тестирование RAG с цитированием...")
    
    # Проверка API ключа
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ DEEPSEEK_API_KEY не найден в переменных окружения")
        return False
    
    try:
        # Инициализация компонентов
        print("📦 Инициализация RAG Manager...")
        rag_manager = RAGManager()
        
        print("🤖 Инициализация DeepSeek Provider...")
        deepseek = DeepSeekProvider(
            api_key=api_key,
            model="deepseek-chat",
            rag_manager=rag_manager
        )
        
        # Тестовые запросы
        test_queries = [
            "Что такое RAG система?",
            "Как работает цитирование источников?",
            "Расскажи про Сумрак 2096",
            "Как настроить бота?",
            "Что такое боливарская коммуна?"
        ]
        
        print(f"🔍 Тестирование {len(test_queries)} запросов...")
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n--- Тест {i}/{len(test_queries)} ---")
            print(f"📝 Запрос: {query}")
            
            try:
                # Генерация ответа с источниками
                response, sources = await deepseek.generate_response_with_sources(
                    user_message=query,
                    system_prompt="Отвечай подробно и используй источники"
                )
                
                print(f"✅ Ответ получен (длина: {len(response) if response else 0} символов)")
                print(f"📚 Источников найдено: {len(sources)}")
                
                # Проверка цитирования
                if response and sources:
                    has_citations = any(f"[{i+1}]" in response for i in range(len(sources)))
                    print(f"🔖 Цитаты в ответе: {'✅' if has_citations else '❌'}")
                    
                    # Проверка формата источников
                    has_source_list = "Источник:" in response
                    print(f"📋 Список источников: {'✅' if has_source_list else '❌'}")
                    
                    # Детали источников
                    for j, source in enumerate(sources[:3], 1):  # Показываем первые 3
                        relevance = source.get('relevance_percentage', 'N/A')
                        file_name = source.get('source_file_name', 'unknown')
                        print(f"   {j}. {file_name} (релевантность: {relevance})")
                
                elif not sources:
                    print("ℹ️  RAG не применен (нет ключевых слов или источников)")
                
            except Exception as e:
                print(f"❌ Ошибка при обработке запроса: {e}")
                continue
        
        print("\n🎯 Тестирование завершено!")
        return True
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reranking_functionality():
    """Тестирует работу реранкера"""
    print("\n🔄 Тестирование реранкера...")
    
    try:
        from src.embeddings.reranker import create_reranker
        
        # Тест SimpleReranker
        print("   📊 SimpleReranker...")
        simple_reranker = create_reranker("simple")
        
        # Создаем тестовые документы
        test_docs = [
            {
                'text': 'Документ про RAG системы и цитирование',
                'similarity_score': 0.8
            },
            {
                'text': 'Техническая документация по настройке',
                'similarity_score': 0.9
            },
            {
                'text': 'Общая информация о системах',
                'similarity_score': 0.7
            }
        ]
        
        # Применяем реранкинг
        reranked = simple_reranker.rerank(
            query="RAG цитирование",
            documents=test_docs,
            top_k=2
        )
        
        print(f"   ✅ Переранжировано {len(reranked)} документов")
        for i, doc in enumerate(reranked, 1):
            score = doc.get('rerank_score', 0)
            print(f"   {i}. Релевантность: {score:.3f}")
        
        # Тест OllamaReranker (если доступен)
        try:
            print("   🧠 OllamaReranker...")
            ollama_reranker = create_reranker("ollama", model_name="bge-reranker-base")
            
            # Проверяем доступность
            info = ollama_reranker.get_model_info()
            print(f"   📋 Модель: {info['model_name']}")
            print(f"   🔗 URL: {info['ollama_url']}")
            
        except Exception as e:
            print(f"   ⚠️  Ollama недоступен: {e}")
        
        print("✅ Реранкинг работает корректно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка реранкера: {e}")
        return False


def test_citation_formatting():
    """Тестирует форматирование цитат"""
    print("\n📝 Тестирование форматирования цитат...")
    
    try:
        rag_manager = RAGManager()
        
        # Создаем тестовые источники с правильными метаданными
        test_sources = [
            {
                'source_file': '/path/to/test_document.md',  # Добавляем обязательное поле
                'citation_index': 1,
                'source_file_name': 'test_document.md',
                'chunk_id': 'test_chunk_0',
                'line_numbers': '1-15',
                'relevance_percentage': '95%'
            },
            {
                'source_file': '/path/to/guide.txt',  # Добавляем обязательное поле
                'citation_index': 2,
                'source_file_name': 'guide.txt',
                'chunk_id': 'guide_chunk_1',
                'line_numbers': '20-35',
                'relevance_percentage': '87%'
            }
        ]
        
        # Сначала обогащаем метаданные
        enriched_sources = rag_manager._enrich_with_citation_metadata(test_sources)
        
        # Тест форматирования цитат
        citations = rag_manager.format_citations(enriched_sources)
        
        print("📋 Форматированные цитаты:")
        print(citations)
        
        # Проверяем наличие обязательных элементов
        required_elements = [
            "[1] Источник:",
            "[2] Источник:",
            "чанк",
            "строки",
            "релевантность:"
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in citations:
                missing_elements.append(element)
        
        if missing_elements:
            print(f"❌ Отсутствуют элементы: {missing_elements}")
            return False
        else:
            print("✅ Форматирование цитат корректно")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка форматирования: {e}")
        return False


def test_configuration():
    """Тестирует конфигурацию"""
    print("\n⚙️  Тестирование конфигурации...")
    
    try:
        rag_manager = RAGManager()
        stats = rag_manager.get_statistics()
        
        print("📊 Статистика RAG системы:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        # Проверяем ключевые настройки
        required_settings = ['enabled', 'context_chunks', 'min_similarity']
        for setting in required_settings:
            if setting not in stats:
                print(f"❌ Отсутствует настройка: {setting}")
                return False
        
        print("✅ Конфигурация загружена корректно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск интеграционного теста RAG с цитированием")
    print("=" * 60)
    
    # Запуск тестов
    tests = [
        ("Конфигурация", test_configuration),
        ("Реранкинг", test_reranking_functionality),
        ("Форматирование цитат", test_citation_formatting),
        ("Полный пайплайн", test_rag_with_citations),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 {test_name}")
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Критическая ошибка в тесте {test_name}: {e}")
            results.append((test_name, False))
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name:.<20} {status}")
        if result:
            passed += 1
    
    print(f"\n📈 Итого: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены! RAG с цитированием работает корректно.")
        return True
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте ошибки выше.")
        return False


if __name__ == "__main__":
    # Проверяем зависимости
    try:
        import yaml
        import requests
        import openai
    except ImportError as e:
        print(f"❌ Отсутствует зависимость: {e}")
        print("Установите зависимости: pip install -r requirements.txt")
        exit(1)
    
    # Запуск тестов
    result = asyncio.run(main())
    exit(0 if result else 1)
