# Реализация механизма Reranking в RAG-системе

## Обзор

Механизм реранкинга улучшает качество поиска в RAG-системе путем повторной сортировки результатов семантического поиска с использованием более точных моделей релевантности.

## Архитектура

### Компоненты

1. **OllamaReranker** - Основной реранкер на основе моделей из Ollama
2. **SimpleReranker** - Fallback реранкер на основе эвристик
3. **create_reranker** - Фабрика для создания реранкеров

### Файлы

- `src/embeddings/reranker.py` - Основная реализация
- `config/embeddings_config.yaml` - Конфигурация реранкера
- `src/rag_integration.py` - Интеграция с RAG менеджером

## Типы реранкеров

### 1. OllamaReranker

Использует cross-encoder модели для точной оценки релевантности.

**Преимущества:**
- Высокая точность реранкинга
- Учитывает семантическую близость запроса и документа

**Недостатки:**
- Требует установленной модели в Ollama
- Дополнительное время на обработку

**Поддерживаемые модели:**
- `bge-reranker-base`
- `ms-marco-MiniLM`
- Другие cross-encoder модели

### 2. SimpleReranker

Простой реранкер на основе эвристик и метрик сходства.

**Преимущества:**
- Быстрый
- Не требует дополнительных моделей
- Надежный fallback

**Недостатки:**
- Меньшая точность по сравнению с neural реранкерами

## Конфигурация

```yaml
reranker:
  type: "simple"  # "simple" или "ollama"
  params:
    # Для Ollama
    model_name: "bge-reranker-base"
    ollama_url: "http://localhost:11434"
    timeout: 30
    max_retries: 3
    retry_delay: 1.0
    
    # Для Simple
    weight_similarity: 0.7  # Вес косинусного сходства
    weight_length: 0.3      # Вес фактора длины
```

## Интеграция с RAG

### Процесс работы

1. **Initial Retrieval** - Получение расширенного списка документов (`context_chunks * 2`)
2. **Reranking** - Повторная сортировка документов с учетом релевантности
3. **Final Selection** - Выбор топ-К документов для контекста

### Пример использования

```python
from src.rag_integration import RAGManager

# Создание RAG менеджера с реранкером
rag_manager = RAGManager()

# Поиск с реранкингом
enriched_message, sources = rag_manager.enrich_message_with_rag(
    user_message="Как работает система?",
    use_reranking=True
)
```

## Метаданные результатов

После реранкинга каждый документ содержит:

```python
{
    'text': 'текст документа',
    'source_file': 'путь/к/файлу',
    'similarity_score': 0.85,        # Исходное сходство
    'rerank_score': 0.92,           # Оценка реранкинга
    'citation_index': 1,              # Порядковый номер для цитирования
    'relevance_score': 92.0,         # Комбинированная релевантность
    'relevance_percentage': '92%'     # Релевантность в процентах
}
```

## Оптимизация производительности

### Кэширование

- Запросы к Ollama кэшируются для повторного использования
- TTL кэша: 1 час (настраивается)

### Batch обработка

- Оценки реранкинга вычисляются для всех документов параллельно
- Ограничение максимального количества одновременных запросов

### Fallback механизм

- При недоступности Ollama автоматически переключается на SimpleReranker
- Логирование ошибок для диагностики

## Тестирование

### Unit тесты

```bash
python -m pytest tests/test_reranker.py -v
```

### Интеграционные тесты

```bash
python -m pytest tests/test_rag_reranking.py -v
```

### Ручное тестирование

```python
from src.embeddings.reranker import create_reranker

# Тест SimpleReranker
simple_reranker = create_reranker("simple")
results = simple_reranker.rerank(query, documents, top_k=5)

# Тест OllamaReranker
ollama_reranker = create_reranker("ollama", model_name="bge-reranker-base")
results = ollama_reranker.rerank(query, documents, top_k=5)
```

## Мониторинг и отладка

### Логи

- Уровень DEBUG для детальной информации о реранкинге
- INFO для основных операций
- WARNING для fallback переключений
- ERROR для критических ошибок

### Метрики

- Время выполнения реранкинга
- Количество документов до/после реранкинга
- Успешность запросов к Ollama
- Частота использования fallback

## Troubleshooting

### Распространенные проблемы

1. **Модель не найдена в Ollama**
   ```
   Решение: ollama pull bge-reranker-base
   ```

2. **Timeout при запросе к Ollama**
   ```
   Решение: Увеличить timeout в конфигурации
   ```

3. **Низкая точность реранкинга**
   ```
   Решение: Попробовать другую модель или настроить веса SimpleReranker
   ```

### Диагностика

```python
# Проверка доступности реранкера
reranker = create_reranker("ollama")
info = reranker.get_model_info()
print(f"Model: {info['model_name']}")
print(f"Available: {info['available']}")
```

## Будущее развитие

### Планируемые улучшения

1. **Поддержка дополнительных моделей**
   - T5-based реранкеры
   - Custom fine-tuned модели

2. **Оптимизация производительности**
   - GPU ускорение
   - Batch запросы к Ollama

3. **Adaptive реранкинг**
   - Автоматический выбор типа реранкера
   - Динамическая настройка параметров

4. **Метрики качества**
   - Automatic evaluation
   - A/B тестирование

---

*Дата создания: 28.11.2025*
*Версия: 1.0*
