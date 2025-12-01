#!/usr/bin/env python3
"""
Тестирование команды /help с git запросами.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в Python path
sys.path.insert(0, str(Path(__file__).parent))

from agents.help_command_agent import HelpCommandAgent
from agents.orchestrator import AgentOrchestrator
from tools.tool_manager import ToolManager

async def test_git_questions():
    """Тестирование различных git запросов."""
    
    test_queries = [
        "покажи текущую ветку",
        "покажи последние коммиты",
        "какой статус репозитория",
        "покажи измененные файлы"
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
        
        # Регистрация агентов
        docs_agent = DocsAgent(tool_manager)
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
                    
                    if 'git_agent' in agents_used:
                        print('✅ Git агент успешно определен и использован')
                    else:
                        print('❌ Git агент НЕ был использован')
                    
                    # Показываем первую часть ответа
                    if answer:
                        print(f'📝 Ответ: {answer[:200]}...')
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
    print('🚀 Тестирование команды /help с git запросами')
    print('=' * 60)
    
    success = await test_git_questions()
    
    print("\n" + "=" * 60)
    if success:
        print('🎉 Тест git запросов завершен!')
    else:
        print('💥 Тест git запросов не пройден!')

if __name__ == "__main__":
    asyncio.run(main())
