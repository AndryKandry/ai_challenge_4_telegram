# Implementation Roadmap - Оставшиеся задачи и план развития

## 📋 Статус текущей реализации

### ✅ Завершенные задачи
- [x] Проверить совместимость версий всех зависимостей
- [x] Исправить проблемы с MCP серверами (filesystem и github)
- [x] Проверить работу MCP для git branch через GitAgent
- [x] Протестировать /help на реальных вопросах о структуре проекта
- [x] Провести комплексное тестирование DocsAgent и GitAgent

## 🚧 Остальные нереализованные задачи

### 1. Оптимизация работы GitAgent для больших репозиториев

**Проблема**: GitAgent может быть медленным на больших репозиториях с тысячами коммитов и файлов.

**Решение**:
```python
# Добавить в GitAgent:
- Пагинацию для получения коммитов (по 100 за раз)
- Индексацию коммитов для быстрого поиска
- Кеширование результатов с TTL
- Лимиты на количество обрабатываемых файлов
- Асинхронную обработку больших diff'ов
```

**Пример улучшения**:
```python
async def get_commits_paginated(self, limit: int = 100, page: int = 1) -> List[Dict]:
    """Пагинация коммитов для больших репозиториев"""
    cache_key = f"commits_page_{page}_{limit}"
    if cached := self._get_from_cache(cache_key):
        return cached
    
    # Использовать git log --skip для пагинации
    skip = (page - 1) * limit
    commits = await self._run_git_command([
        "log", f"--skip={skip}", f"-{limit}", 
        "--pretty=format:%H|%an|%ar|%s"
    ])
    
    parsed = self._parse_commits(commits)
    self._cache_result(cache_key, parsed, ttl=300)
    return parsed
```

### 2. Добавить метаданные в индекс документов

**Проблема**: Текущий индекс документов не содержит достаточно метаданных для эффективного поиска.

**Решение**:
```python
# Расширить DocumentChunk метаданными:
{
    "id": "unique_id",
    "content": "document_content", 
    "metadata": {
        "source": "file_path",
        "file_type": "py|md|txt|json",
        "language": "python|markdown",
        "functions": ["function_names"],
        "classes": ["class_names"],
        "imports": ["module_imports"],
        "docstring": "function_documentation",
        "complexity": "cyclomatic_complexity",
        "last_modified": "timestamp",
        "author": "commit_author",
        "size": "file_size",
        "lines": "line_count"
    },
    "embedding": [float_values]
}
```

### 3. Улучшить качество поиска через реранкинг

**Проблема**: Простое сходство векторов не всегда дает релевантные результаты.

**Решение**:
```python
class AdvancedReranker:
    """Комплексный реранкинг документов"""
    
    def __init__(self):
        self.bm25 = BM25Okapi()
        self.cross_encoder = CrossEncoder('ms-marco-MiniLM-L-6-v2')
        
    async def rerank(self, query: str, documents: List[DocumentChunk]) -> List[DocumentChunk]:
        # 1. BM25 для текстового релевантности
        bm25_scores = self.bm25.score(query, [doc.content for doc in documents])
        
        # 2. Кросс-энкодер для семантического релевантности
        cross_scores = self.cross_encoder.predict([
            [query, doc.content] for doc in documents
        ])
        
        # 3. Комбинирование скоров
        final_scores = []
        for i, doc in enumerate(documents):
            combined_score = (
                0.3 * bm25_scores[i] + 
                0.5 * cross_scores[i] +
                0.2 * self._calculate_recency_score(doc)
            )
            final_scores.append(combined_score)
            
        # 4. Сортировка по финальному скору
        return sorted(zip(documents, final_scores), key=lambda x: x[1], reverse=True)
```

### 4. Интегрировать subagents в DeepSeekProvider

**Проблема**: LLM провайдер не умеет автоматически вызывать агенты для сложных задач.

**Решение**:
```python
class DeepSeekWithAgents(DeepSeekProvider):
    def __init__(self, agents_orchestrator):
        super().__init__()
        self.orchestrator = agents_orchestrator
        
    async def generate_with_agents(self, messages, context=None):
        # 1. Анализ запроса для определения нужных агентов
        agent_plan = await self._plan_agent_usage(messages[-1]["content"])
        
        # 2. Параллельный вызов агентов
        if agent_plan["needs_agents"]:
            agent_results = await self._execute_agents(agent_plan["agents"])
            context["agent_results"] = agent_results
            
        # 3. Генерация ответа с результатами агентов
        return await self.generate(messages, context=context)
        
    async def _plan_agent_usage(self, query: str) -> Dict:
        """Определение каких агентов нужно вызвать"""
        if any(keyword in query.lower() for keyword in ["git", "commit", "branch"]):
            return {"needs_agents": True, "agents": ["git_agent"]}
        if any(keyword in query.lower() for keyword in ["документация", "как использовать"]):
            return {"needs_agents": True, "agents": ["docs_agent"]}
        return {"needs_agents": False}
```

### 5. Улучшить graceful degradation при отсутствии github_mcp Tool

**Проблема**: Система может полностью отказать при отсутствии ключевых инструментов.

**Решение**:
```python
class ResilientGitAgent(GitAgent):
    def __init__(self, tool_manager, repo_path="."):
        super().__init__(tool_manager, repo_path)
        self.fallback_tools = {
            "github_mcp": "git_cli",
            "git_cli": "subprocess_git",
            "subprocess_git": None
        }
        
    async def call_tool_with_fallback(self, tool_name: str, **params):
        """Вызов инструмента с множественным fallback"""
        current_tool = tool_name
        
        while current_tool:
            try:
                return await self.call_tool(current_tool, **params)
            except Exception as e:
                logger.warning(f"Tool {current_tool} failed: {e}")
                current_tool = self.fallback_tools.get(current_tool)
                
        # Все инструменты недоступны - вернуть базовую информацию
        return await self._provide_basic_response(tool_name, **params)
```

### 6. Создать CodeSearchTool

**Функционал**: Интеллектуальный поиск по коду с поддержкой паттернов.

```python
class CodeSearchTool(BaseTool):
    """Инструмент для поиска по коду"""
    
    async def search_code(
        self, 
        pattern: str,
        file_types: List[str] = None,
        context_lines: int = 3
    ) -> List[CodeMatch]:
        """Поиск кода по паттерну с контекстом"""
        
    async def search_function_calls(
        self, 
        function_name: str,
        include_definitions: bool = True
    ) -> List[FunctionMatch]:
        """Поиск вызовов и определений функций"""
        
    async def search_class_usage(
        self, 
        class_name: str
    ) -> List[ClassMatch]:
        """Поиск использования класса"""
        
    async def semantic_search(
        self, 
        query: str,
        limit: int = 10
    ) -> List[SemanticMatch]:
        """Семантический поиск по коду"""
```

### 7. Создать FileSystemTool

**Функционал**: Расширенная работа с файловой системой.

```python
class FileSystemTool(BaseTool):
    """Расширенный инструмент для работы с файловой системой"""
    
    async def smart_search(
        self, 
        pattern: str,
        path: str = ".",
        recursive: bool = True
    ) -> List[FileMatch]:
        """Умный поиск файлов с поддержкой glob паттернов"""
        
    async def analyze_file(
        self, 
        file_path: str
    ) -> FileAnalysis:
        """Анализ файла: тип, язык, сложность, зависимости"""
        
    async def find_duplicates(
        self, 
        path: str = "."
    ) -> List[DuplicateGroup]:
        """Поиск дубликатов файлов по содержимому"""
        
    async def monitor_changes(
        self, 
        path: str = ".",
        callback: Callable = None
    ) -> AsyncIterator[FileChange]:
        """Мониторинг изменений в файловой системе"""
```

### 8. Создать unit-тесты для agents и tools

**Структура тестов**:
```
tests/
├── agents/
│   ├── test_git_agent.py
│   ├── test_docs_agent.py
│   ├── test_help_command_agent.py
│   └── test_orchestrator.py
├── tools/
│   ├── test_base_tool.py
│   ├── test_tool_manager.py
│   ├── test_mcp_tools.py
│   └── test_rag_tools.py
├── integration/
│   ├── test_agent_orchestration.py
│   ├── test_mcp_integration.py
│   └── test_end_to_end.py
└── fixtures/
    ├── sample_documents/
    ├── mock_repos/
    └── test_data.json
```

### 9. Написать расширенную документацию по Tools system

**Структура документации**:
```markdown
docs/
├── TOOLS_SYSTEM_GUIDE.md      # Основное руководство
├── AGENTS_DEVELOPMENT.md     # Разработка агентов
├── TOOLS_DEVELOPMENT.md      # Создание инструментов
├── MCP_INTEGRATION.md        # Интеграция MCP
├── ORCHESTRATION_PATTERNS.md # Паттерны оркестрации
├── TESTING_STRATEGIES.md      # Стратегии тестирования
├── PERFORMANCE_TUNING.md     # Оптимизация производительности
└── TROUBLESHOOTING.md       # Решение проблем
```

## 🎯 Приоритеты реализации

### Приоритет 1 (Критично)
1. **Graceful degradation** - отказоустойчивость системы
2. **Unit тесты** - покрытие основного функционала
3. **DocsAgent RAG** - полная функциональность поиска по документации

### Приоритет 2 (Важно)
4. **CodeSearchTool** - поиск по коду
5. **Реранкинг** - улучшение качества поиска
6. **Метаданные документов** - обогащение индекса

### Приоритет 3 (Желательно)
7. **FileSystemTool** - расширенная работа с файлами
8. **Интеграция agents в LLM** - интеллектуальные вызовы
9. **Оптимизация GitAgent** - работа с большими репозиториями

## 📅 Оценочные сроки

- **Приоритет 1**: 2-3 недели
- **Приоритет 2**: 3-4 недели  
- **Приоритет 3**: 4-6 недель

## 🔗 Связанные документы

- [`/docs/MEMORY_ARCHITECTURE.md`](MEMORY_ARCHITECTURE.md) - Архитектура памяти
- [`/docs/IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md) - Текущий статус
- [`/docs/INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) - Гайд по интеграции
- [`/docs/RAG_IMPLEMENTATION.md`](rag_implementation.md) - RAG система

---

**Примечание**: Данный roadmap является живым документом и может обновляться по мере развития проекта.
