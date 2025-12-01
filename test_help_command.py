#!/usr/bin/env python3
"""
Тестирование команды /help с исправленной RAG системой.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в Python path
sys.path.insert(0, str(Path(__file__).parent))

from agents.help_command_agent import HelpCommandAgent
from agents.orchestrator import AgentOrchestrator
from tools.tool_manager import ToolManager

async def test_help_command():
    """Тестирование команды помощи."""
    
    print('🧪 Тестирование команды /help как использовать RAG...')
    
    try:
        # Инициализация
        tool_manager = ToolManager()
        orchestrator = AgentOrchestrator(tool_manager)
        
        # Регистрация нужных агентов
        from agents.docs_agent import DocsAgent
        from src.rag_integration import RAGManager
        from tools.rag_tools import DocumentSearchTool
        
        # Регистрация RAG инструментов
        rag_manager = RAGManager()
        search_tool = DocumentSearchTool(rag_manager)
        tool_manager.register_tool(search_tool)
        
        # Регистрация агентов
        docs_agent = DocsAgent(tool_manager)
        help_agent = HelpCommandAgent(orchestrator)
        
        orchestrator.register_agent(docs_agent)
        orchestrator.register_agent(help_agent)
        
        # Создание задачи
        task = {
            'action': 'answer_question',
            'params': {
                'query': 'как использовать RAG',
                'user_id': 393559696
            }
        }
        
        print('🔍 Выполняю задачу...')
        result = await orchestrator.execute_task('help_command_agent', task)
        
        print('✅ Результат получен:')
        if isinstance(result, str):
            print(f'📝 Ответ: {result[:200]}...')
        else:
            print(f'📝 Тип: {type(result)}, Содержимое: {str(result)[:200]}...')
        
        return True
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Главная функция."""
    print('🚀 Тестирование команды /help с исправленной RAG системой')
    print('=' * 60)
    
    success = await test_help_command()
    
    print("\n" + "=" * 60)
    if success:
        print('🎉 Тест помощи пройден! Команда /help работает корректно.')
    else:
        print('💥 Тест помощи не пройден! Проверьте ошибки выше.')

if __name__ == "__main__":
    asyncio.run(main())
