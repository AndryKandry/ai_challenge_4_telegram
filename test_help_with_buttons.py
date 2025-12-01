#!/usr/bin/env python3
"""
Финальное тестирование команды /help с Telegram inline кнопками.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в Python path
sys.path.insert(0, str(Path(__file__).parent))

from agents.help_command_agent import HelpCommandAgent
from agents.orchestrator import AgentOrchestrator
from tools.tool_manager import ToolManager

async def test_help_with_buttons():
    """Тестирование команды /help с inline кнопками."""
    
    test_queries = [
        "как использовать RAG",
        "примеры кода",
        "API документация"
    ]
    
    try:
        # Инициализация
        tool_manager = ToolManager()
        orchestrator = AgentOrchestrator(tool_manager)
        
        # Регистрация нужных агентов
        from agents.docs_agent import DocsAgent
        from agents.git_agent import GitAgent
        from src.rag_integration import RAGManager
        from tools.rag_tools import DocumentSearchTool
        
        # Регистрация RAG инструментов
        rag_manager = RAGManager()
        search_tool = DocumentSearchTool(rag_manager)
        tool_manager.register_tool(search_tool)
        
        # Регистрация агентов с rag_manager для DocsAgent
        docs_agent = DocsAgent(tool_manager, rag_manager=rag_manager)
        git_agent = GitAgent(tool_manager)
        help_agent = HelpCommandAgent(orchestrator)
        
        orchestrator.register_agent(docs_agent)
        orchestrator.register_agent(git_agent)
        orchestrator.register_agent(help_agent)
        
        # Тестируем каждый запрос
        for query in test_queries:
            print(f'\n🧪 Тестируем запрос: "{query}"')
            
            task = {
                'action': 'answer_question',
                'params': {
                    'query': query,
                    'user_id': 393559696
                }
            }
            
            try:
                result = await orchestrator.execute_task('help_command_agent', task)
                
                if isinstance(result, dict):
                    answer = result.get('answer', '')
                    agents_used = result.get('agents_used', [])
                    
                    print(f'✅ Ответ получен')
                    print(f'🤖 Использованы агенты: {agents_used}')
                    
                    if 'docs_agent' in agents_used:
                        print('✅ Docs агент успешно определен и использован')
                        # Проверяем наличие inline кнопок в ответе
                        if 'Интерактивные источники доступны' in answer:
                            print('✅ Telegram inline кнопки доступны в ответе')
                        else:
                            print('⚠️ Inline кнопки не найдены в ответе')
                    else:
                        print('❌ Docs агент НЕ был использован')
                    
                    # Показываем первую часть ответа
                    if answer:
                        print(f'📝 Ответ: {answer[:400]}...')
                else:
                    print(f'❌ Неожиданный тип результата: {type(result)}')
                    
            except Exception as e:
                print(f'❌ Ошибка при выполнении запроса: {e}')
        
        return True
        
    except Exception as e:
        print(f'❌ Общая ошибка: {e}')
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Главная функция."""
    print('🚀 Финальное тестирование команды /help с Telegram inline кнопками')
    print('=' * 70)
    
    success = await test_help_with_buttons()
    
    print("\n" + "=" * 70)
    if success:
        print('🎉 Финальный тест команды /help завершен!')
    else:
        print('💥 Финальный тест команды /help не пройден!')

if __name__ == "__main__":
    asyncio.run(main())
