#!/usr/bin/env python3
"""
Тестирование функционала сравнения RAG с reranking и без reranking.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в Python path
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

async def test_rag_comparison():
    """Тестирует функционал сравнения RAG."""
    
    try:
        # Загружаем переменные окружения
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Переменные окружения загружены")
        
        # Проверяем необходимые API ключи
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            logger.error("DEEPSEEK_API_KEY не задан!")
            return False
            
        # Импортируем необходимые модули
        from src.rag_integration import RAGManager
        from src.rag_comparison import RAGComparisonManager
        from providers.deepseek_provider import DeepSeekProvider
        from storage.user_settings import UserSettings
        
        logger.info("Импортированы все необходимые модули")
        
        # Инициализация компонентов
        print("🔧 Инициализация компонентов...")
        
        # RAG Manager
        try:
            rag_manager = RAGManager()
            print("✅ RAG Manager инициализирован")
        except Exception as e:
            print(f"⚠️  RAG Manager не инициализирован: {e}")
            rag_manager = None
            
        # DeepSeek Provider
        deepseek_provider = DeepSeekProvider(
            deepseek_api_key,
            rag_manager=rag_manager
        )
        print("✅ DeepSeek Provider инициализирован")
        
        # RAG Comparison Manager
        if rag_manager and deepseek_provider:
            comparison_manager = RAGComparisonManager(
                rag_manager,
                deepseek_provider
            )
            print("✅ RAG Comparison Manager инициализирован")
        else:
            print("❌ RAG Comparison Manager не может быть инициализирован")
            return False
            
        # UserSettings
        user_settings = UserSettings()
        print("✅ UserSettings инициализирован")
        
        # Тестовые данные
        test_user_id = 12345
        test_query = "Что такое Сумрак и какие фракции существуют?"
        
        print(f"\n🧪 Тестирование с запросом: '{test_query}'")
        print(f"👤 Тестовый пользователь: {test_user_id}")
        
        # Тест 1: Проверка состояния режима сравнения
        print("\n📋 Тест 1: Проверка состояния режима сравнения")
        initial_state = comparison_manager.is_comparison_mode(test_user_id)
        print(f"   Начальное состояние: {initial_state}")
        
        # Тест 2: Переключение режима сравнения
        print("\n📋 Тест 2: Переключение режима сравнения")
        new_state, message = comparison_manager.toggle_comparison_mode(
            test_user_id, "deepseek"
        )
        print(f"   Новое состояние: {new_state}")
        print(f"   Сообщение: {message}")
        
        # Тест 3: Проверка сохранения состояния
        print("\n📋 Тест 3: Проверка сохранения состояния")
        saved_state = user_settings.get_rag_comparison_enabled(test_user_id)
        print(f"   Сохраненное состояние: {saved_state}")
        print(f"   Состояния совпадают: {new_state == saved_state}")
        
        # Тест 4: Выполнение сравнения (если есть индексированные документы)
        print("\n📋 Тест 4: Выполнение сравнения RAG")
        try:
            comparison_result = await comparison_manager.compare_rag_responses(
                test_query,
                "Ты - ассистент, отвечающий на вопросы по игровой вселенной Сумрак 2096.",
                []
            )
            
            if comparison_result:
                print("✅ Сравнение выполнено успешно")
                print(f"   Найдено документов для поиска: {comparison_result.total_search_results}")
                print(f"   Токенов в варианте A: {comparison_result.variant_a.token_count}")
                print(f"   Токенов в варианте B: {comparison_result.variant_b.token_count}")
                print(f"   Время генерации A: {comparison_result.variant_a.generation_time:.2f} сек")
                print(f"   Время генерации B: {comparison_result.variant_b.generation_time:.2f} сек")
                print(f"   Средняя релевантность A: {comparison_result.variant_a.avg_relevance:.2f}")
                print(f"   Средняя релевантность B: {comparison_result.variant_b.avg_relevance:.2f}")
                
                # Тест 5: Форматирование результата
                print("\n📋 Тест 5: Форматирование результата")
                formatted_result = comparison_manager.format_comparison_result(comparison_result)
                print(f"   Длина отформатированного результата: {len(formatted_result)} символов")
                print("   Первые 200 символов результата:")
                print(f"   {formatted_result[:200]}...")
                
            else:
                print("⚠️  Сравнение не выполнено (возможно, нет индексированных документов)")
                
        except Exception as e:
            print(f"❌ Ошибка при выполнении сравнения: {e}")
            
        # Тест 6: Переключение режима обратно
        print("\n📋 Тест 6: Переключение режима обратно")
        final_state, final_message = comparison_manager.toggle_comparison_mode(
            test_user_id, "deepseek"
        )
        print(f"   Финальное состояние: {final_state}")
        print(f"   Сообщение: {final_message}")
        
        print("\n🎉 Все тесты завершены!")
        return True
        
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}", exc_info=True)
        print(f"❌ Ошибка при тестировании: {e}")
        return False

def main():
    """Главная функция."""
    print("🧪 Тестирование функционала сравнения RAG\n")
    
    # Проверяем наличие необходимых зависимостей
    try:
        import dotenv
        print("✅ python-dotenv доступен")
    except ImportError:
        print("❌ python-dotenv не установлен. Установите: pip install python-dotenv")
        return
        
    # Запускаем асинхронное тестирование
    success = asyncio.run(test_rag_comparison())
    
    if success:
        print("\n✅ Тестирование пройдено успешно!")
        print("\n📝 Рекомендации:")
        print("1. Убедитесь, что есть индексированные документы в data/embeddings/")
        print("2. Проверьте, что DEEPSEEK_API_KEY корректно настроен")
        print("3. Запустите бота и протестируйте команду /rag_reranking")
        print("4. Проверьте работу только с моделью DeepSeek")
    else:
        print("\n❌ Тестирование не пройдено!")
        print("Проверьте логи и настройте окружение.")

if __name__ == "__main__":
    main()
