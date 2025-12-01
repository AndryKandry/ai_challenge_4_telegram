#!/usr/bin/env python3
"""
Тестирование DocsAgent с Telegram inline кнопками.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в Python path
sys.path.insert(0, str(Path(__file__).parent))

from agents.docs_agent import DocsAgent
from agents.orchestrator import AgentOrchestrator
from tools.tool_manager import ToolManager
from src.rag_integration import RAGManager
from tools.rag_tools import DocumentSearchTool

async def test_docs_with_buttons():
    """Тестирование DocsAgent с inline кнопками."""
    
    test_queries = [
        "как использовать RAG",
        "примеры кода",
        "API документация"
    ]
    
    try:
        # Инициализация
        tool_manager = ToolManager()
        
        # Регистрация RAG инструментов
        rag_manager = RAGManager()
        search_tool = DocumentSearchTool(rag_manager)
        tool_manager.register_tool(search_tool)
        
        # Регистрация DocsAgent с rag_manager для TelegramDocumentHandler
        docs_agent = DocsAgent(tool_manager, rag_manager=rag_manager)
        
        # Тестируем каждый запрос
        for query in test_queries:
            print(f'\n🧪 Тестируем запрос: "{query}"')
            
            # Выполняем поиск через DocsAgent
            chunks = await docs_agent.search_documentation(query, top_k=3)
            
            if chunks:
                print(f'✅ Найдено {len(chunks)} фрагментов')
                
                # Форматируем с inline кнопками
                text, keyboard = await docs_agent.format_search_results_with_buttons(chunks)
                
                if text:
                    print(f'📝 Текст с заголовком:')
                    print(text[:300] + '...' if len(text) > 300 else text)
                
                if keyboard:
                    print(f'🔘 Inline клавиатура создана:')
                    print(f'   Тип: {type(keyboard)}')
                    if hasattr(keyboard, 'inline_keyboard'):
                        print(f'   Кнопок: {len(keyboard.inline_keyboard)}')
                        for i, row in enumerate(keyboard.inline_keyboard[:3]):  # Показываем первые 3
                            print(f'   Ряд {i+1}: {len(row)} кнопок')
                            for button in row:
                                if hasattr(button, 'text'):
                                    print(f'     - {button.text}')
                else:
                    print('⚠️ Клавиатура не создана (используется обычный текст)')
            else:
                print('❌ Фрагменты не найдены')
                
            print('-' * 50)
        
        return True
        
    except Exception as e:
        print(f'❌ Общая ошибка: {e}')
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Главная функция."""
    print('🚀 Тестирование DocsAgent с Telegram inline кнопками')
    print('=' * 60)
    
    success = await test_docs_with_buttons()
    
    print("\n" + "=" * 60)
    if success:
        print('🎉 Тест DocsAgent с inline кнопками завершен!')
    else:
        print('💥 Тест DocsAgent с inline кнопками не пройден!')

if __name__ == "__main__":
    asyncio.run(main())
