# Система цитирования источников в RAG

## Обзор

Система цитирования обеспечивает обязательное указание источников информации в ответах модели DeepSeek, что повышает доверие к ответам и позволяет пользователям проверять информацию.

## Архитектура

### Компоненты

1. **Citation Metadata Enricher** - Обогащение результатов метаданными для цитирования
2. **Citation Formatter** - Форматирование цитат для ответов модели
3. **Citation Prompt Generator** - Создание промптов с требованиями цитирования
4. **DeepSeek Integration** - Интеграция с провайдером DeepSeek

### Файлы

- `src/rag_integration.py` - Основная реализация цитирования
- `providers/deepseek_provider.py` - Интеграция с DeepSeek
- `config/embeddings_config.yaml` - Конфигурация цитирования

## Формат цитирования

### Требования к цитатам

1. **Обязательность** - Каждый ответ с RAG должен содержать цитаты
2. **Полнота** - Цитата включает всю необходимую информацию
3. **Релевантность** - Указание процента релевантности
4. **Структура** - Единый формат всех цитат

### Формат источника

```
[index] Источник: filename, чанк chunk_id, строки start-end, релевантность: X%
```

**Пример:**
```
[1] Источник: bot_overview.md, чанк bot_overview_md_chunk_0, строки 1-10, релевантность: 95%
[2] Источник: getting_started.md, чанк getting_started_md_chunk_1, строки 15-25, релевантность: 89%
```

### Формат цитирования в тексте

- Квадратные скобки с номером источника: `[1]`, `[2]`
- Несколько источников через запятую: `[1,3]`
- Размещение после информации из источника

**Пример ответа:**
```
Система поддерживает работу с несколькими LLM-провайдерами [1], включая DeepSeek, OpenAI и Yandex GPT [2,3]. Бот использует RAG для обогащения контекста [1].
```

## Метаданные цитирования

### Обязательные поля

```python
{
    'citation_index': 1,                    # Порядковый номер
    'source_file_name': 'document.md',        # Имя файла
    'source_file': '/path/to/document.md',   # Полный путь
    'chunk_id': 'document_md_chunk_0',      # ID чанка
    'line_numbers': '1-15',                # Диапазон строк
    'similarity_score': 0.85,               # Исходное сходство
    'rerank_score': 0.92,                  # Оценка реранкинга
    'relevance_score': 92.0,                # Комбинированная релевантность
    'relevance_percentage': '92%'            # Релевантность в процентах
}
```

### Определение номеров строк

1. **Приоритет метаданных** - Используются `char_start` и `char_end`
2. **Аппроксимация** - ~50 символов на строку
3. **Fallback** - На основе `chunk_index`

```python
def _extract_line_numbers(self, result: Dict) -> str:
    metadata = result.get('metadata', {})
    
    if char_start is not None and char_end is not None:
        line_start = max(1, char_start // 50 + 1)
        line_end = max(line_start, char_end // 50 + 1)
        return f"{line_start}-{line_end}"
    
    chunk_index = result.get('chunk_index', 0)
    return f"{chunk_index * 10 + 1}-{chunk_index * 10 + 20}"
```

## Интеграция с DeepSeek

### Процесс работы

1. **RAG Retrieval** - Поиск релевантных документов
2. **Reranking** - Улучшение сортировки (опционально)
3. **Citation Enrichment** - Добавление метаданных цитирования
4. **Prompt Generation** - Создание промпта с требованиями цитирования
5. **Model Response** - Генерация ответа с цитатами
6. **Citation Formatting** - Форматирование финального списка источников

### Промпт для цитирования

```python
citation_instruction = """
ВАЖНО: Вы должны включить цитаты на источники в свой ответ.

Инструкция по цитированию:
- Используйте информацию из предоставленного контекста
- Включайте ссылки на источники в квадратных скобках [1], [2] и т.д.
- Номер в скобках должен соответствовать номеру источника в списке
- Ссылки должны размещаться после информации, которая взята из данного источника
- Если информация из нескольких источников, перечислите все номера через запятую: [1,3]

Пример цитирования в ответе:
"Согласно документации [1], система работает с эмбеддингами размером 1024 [2,3]."

Формат источников будет предоставлен после вашего ответа.
"""
```

## Конфигурация

```yaml
citation:
  enabled: true                           # Включить цитирование
  default_sources_count: 5                 # Количество источников по умолчанию
  
  citation_template: |
    {citation_instruction}
    
    Контекст из документации:
    ---
    {context}
    ---
    
    Вопрос пользователя: {query}
```

## Использование

### Базовое использование

```python
from src.rag_integration import RAGManager

# Создание RAG менеджера
rag_manager = RAGManager()

# Поиск с цитированием
enriched_message, sources = rag_manager.enrich_message_with_rag(
    user_message="Как работает система?",
    use_reranking=True
)

# Форматирование цитат
citations = rag_manager.format_citations(sources, max_sources=5)
```

### Интеграция с DeepSeek

```python
from providers.deepseek_provider import DeepSeekProvider
from src.rag_integration import RAGManager

# Создание компонентов
rag_manager = RAGManager()
deepseek = DeepSeekProvider(api_key="...", rag_manager=rag_manager)

# Генерация ответа с цитатами
response, sources = await deepseek.generate_response_with_sources(
    user_message="Вопрос",
    system_prompt="Системный промпт"
)

# response содержит текст ответа + список источников
# sources содержит метаданные источников
```

## Обработка edge cases

### Меньше 5 источников

```python
# Если источников меньше 5, возвращаем все доступные
sources_to_use = search_results[:min(max_sources, len(search_results))]
```

### Отсутствие источников

```python
if not sources:
    return "Извините, не нашел релевантной информации в документации."
```

### Низкая релевантность

```python
# Фильтрация по минимальной релевантности
min_relevance = 0.3  # 30%
filtered_sources = [s for s in sources if s['relevance_score'] >= min_relevance]
```

## Тестирование

### Unit тесты

```python
def test_citation_formatting():
    """Тест форматирования цитат"""
    sources = [
        {
            'citation_index': 1,
            'source_file_name': 'test.md',
            'chunk_id': 'test_chunk_0',
            'line_numbers': '1-10',
            'relevance_percentage': '95%'
        }
    ]
    
    citations = rag_manager.format_citations(sources)
    assert "[1] Источник: test.md, чанк test_chunk_0, строки 1-10, релевантность: 95%" in citations
```

### Интеграционные тесты

```python
async def test_deepseek_citation():
    """Тест цитирования в DeepSeek"""
    response, sources = await deepseek.generate_response_with_sources(
        user_message="Что такое RAG?",
        system_prompt="Отвечай кратко"
    )
    
    # Проверяем наличие цитат
    assert "[1]" in response or "[2]" in response
    assert "Источник:" in response
```

### Тестирование качества

```python
def test_citation_accuracy():
    """Тест точности цитирования"""
    # Проверяем что номера в тексте соответствуют источникам
    # Проверяем корректность метаданных
    # Проверяем форматирование
```

## Мониторинг

### Метрики

- **Citation Rate** - Процент ответов с цитатами
- **Citation Accuracy** - Точность номеров источников
- **Source Relevance** - Средняя релевантность источников
- **User Feedback** - Обратная связь от пользователей

### Логи

```python
logger.info(f"Generated response with {len(sources)} citations")
logger.debug(f"Citation metadata: {sources}")
logger.warning(f"Low relevance sources: {[s for s in sources if s['relevance_score'] < 0.5]}")
```

## Troubleshooting

### Распространенные проблемы

1. **Отсутствуют цитаты в ответе**
   ```
   Причина: Модель игнорирует инструкции
   Решение: Усилить промпт, проверить temperature
   ```

2. **Неправильные номера источников**
   ```
   Причина: Несоответствие индексов
   Решение: Проверить логику citation_index
   ```

3. **Некорректные номера строк**
   ```
   Причина: Ошибки в метаданных
   Решение: Проверить индексацию документов
   ```

### Диагностика

```python
# Проверка метаданных источников
for source in sources:
    print(f"Source {source['citation_index']}: {source['source_file_name']}")
    print(f"  Lines: {source['line_numbers']}")
    print(f"  Relevance: {source['relevance_percentage']}")
```

## Будущее развитие

### Планируемые улучшения

1. **Умное цитирование**
   - Автоматическое определение необходимости цитирования
   - Адаптивное количество источников

2. **Улучшенные метаданные**
   - Точные номера строк
   - Контекст цитирования
   - Доверие к источнику

3. **Интерактивные цитаты**
   - Ссылки на конкретные строки
   - Предпросмотр источников
   - Экспорт цитат

4. **Качество цитирования**
   - Automatic evaluation
   - User studies
   - A/B тестирование форматов

---

*Дата создания: 28.11.2025*
*Версия: 1.0*
