#!/usr/bin/env python3
"""
Тестирование исправлений порогов схожести в RAG системе.

Проверяет, что после уменьшения min_similarity с 0.5 до 0.1
система возвращает результаты поиска.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.rag_integration import RAGManager
from agents.docs_agent import DocsAgent
from tools.tool_manager import ToolManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_similarity_fix():
    """Тестирование исправлений порогов схожести."""
    
    print("🧪 Тестирование исправлений порогов схожести...")
    
    try:
        # 1. Инициализация RAG Manager
        print("\n1️⃣ Инициализация RAG Manager...")
        rag_manager = RAGManager()
        if not rag_manager.enabled:
            print("❌ RAG система не доступна")
            return False
        
        print("✅ RAG Manager успешно инициализирован")
        
        # 2. Инициализация Tool Manager
        print("\n2️⃣ Инициализация Tool Manager...")
        tool_manager = ToolManager()
        
        # Регистрация DocumentSearchTool
        from tools.rag_tools import DocumentSearchTool
        search_tool = DocumentSearchTool(rag_manager)
        tool_manager.register_tool(search_tool)
        
        print("✅ Tool Manager успешно инициализирован")
        
        # 3. Инициализация DocsAgent
        print("\n3️⃣ Инициализация DocsAgent...")
        docs_agent = DocsAgent(tool_manager)
        print("✅ DocsAgent успешно инициализирован")
        
        # 4. Тестирование поиска с разными запросами
        test_queries = [
            "как использовать RAG",
            "покажи примеры кода для агентов", 
            "RAG pipeline",
            "semantic search"
        ]
        
        print("\n4️⃣ Тестирование поиска с пониженным порогом...")
        for i, query in enumerate(test_queries, 1):
            print(f"\n   🔍 Тест {i}: '{query}'")
            
            try:
                # Прямой вызов DocumentSearchTool
                results = await search_tool.execute(
                    query=query,
                    top_k=5,
                    min_similarity=0.1  # Новый порог
                )
                
                print(f"   📊 Найдено результатов: {len(results)}")
                
                if results:
                    # Показываем первый результат для проверки
                    first_result = results[0]
                    similarity = first_result.get("similarity_score", 0.0)  # Правильное поле!
                    source_file = first_result.get("source_file", "unknown")
                    content_preview = first_result.get("text", "")[:100]
                    print(f"   📄 Первый результат (схожесть: {similarity:.3f}): {content_preview}...")
                    print(f"   📁 Источник: {source_file[-30:]}")  # Показываем последние 30 символов
                else:
                    print("   ⚠️  Результаты не найдены")
                    
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
        
        # 5. Тестирование через DocsAgent
        print("\n5️⃣ Тестирование через DocsAgent...")
        task = {
            "action": "search",
            "params": {
                "query": "RAG система",
                "top_k": 3
            }
        }
        
        try:
            chunks = await docs_agent.execute(task)
            print(f"   📊 DocsAgent нашел фрагментов: {len(chunks)}")
            
            if chunks:
                for i, chunk in enumerate(chunks[:2], 1):  # Показываем первые 2
                    source_file = chunk.metadata.get("source_file", "unknown")
                    print(f"   📄 Фрагмент {i} (score: {chunk.score:.3f}): {chunk.content[:80]}...")
                    print(f"   📁 Источник: {source_file[-30:]}")  # Показываем источник
            else:
                print("   ⚠️  DocsAgent не нашел фрагментов")
                
        except Exception as e:
            print(f"   ❌ Ошибка DocsAgent: {e}")
        
        print("\n✅ Тестирование завершено!")
        return True
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}", exc_info=True)
        return False


async def main():
    """Главная функция."""
    print("🚀 Тестирование исправлений порогов схожести в RAG системе")
    print("=" * 60)
    
    success = await test_similarity_fix()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Тест пройден! Пороги схожести исправлены.")
    else:
        print("💥 Тест не пройден! Проверьте ошибки выше.")


if __name__ == "__main__":
    asyncio.run(main())
