# RAG Implementation - Реализация поиска по документам с эмбеддингами

## Обзор

Система RAG (Retrieval Augmented Generation) позволяет DeepSeek использовать контекст из локальных документов для более точных и релевантных ответов.

## Архитектура

```
┌─────────────────┐
│  Пользователь   │
└────────┬────────┘
         │ Запрос
         ▼
┌─────────────────┐
│  DeepSeek RAG   │
│   Integration   │
└────────┬────────┘
         │
         ├──► Semantic Searcher ──► Index (JSON)
         │          ▲
         │          │ Embeddings
         │          │
         └─────► Ollama (Local)
```

### Компоненты системы

1. **TextChunker** (`src/embeddings/chunker.py`)
   - Разбивает документы на чанки размером ~800 токенов
   - Поддерживает markdown и txt форматы
   - Сохраняет перекрытие между чанками (150 токенов)

2. **OllamaEmbedder** (`src/embeddings/embedder.py`)
   - Генерирует эмбеддинги через локальный Ollama
   - Использует модель `bge-m3` (768-мерные векторы)
   - Батчевая обработка и retry-логика

3. **DocumentIndexer** (`src/embeddings/indexer.py`)
   - Индексирует документы из директории `rag_docs/`
   - Отслеживает изменения файлов по SHA-256 хэшу
   - Сохраняет индекс в JSON формате

4. **SemanticSearcher** (`src/embeddings/searcher.py`)
   - Семантический поиск по индексу
   - Косинусное сходство векторов
   - Кэширование запросов

5. **DeepSeekRAG** (`src/integrations/deepseek_rag.py`)
   - Интеграция поиска с DeepSeek
   - Автоматическое определение необходимости RAG
   - Форматирование контекста для промпта

## Быстрый старт

### 1. Установка Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Загрузка модели эмбеддингов
ollama pull bge-m3

# Запуск сервера
ollama serve
```

### 2. Установка зависимостей Python

```bash
pip install -r requirements.txt
```

### 3. Добавление документов

Поместите ваши документы (`.md` или `.txt`) в директорию `rag_docs/`:

```
rag_docs/
├── documentation/
│   └── bot_overview.md
├── guides/
│   └── getting_started.md
└── reference/
    └── api_keys.txt
```

### 4. Индексация

```bash
python manage_index.py index
```

### 5. Проверка работы

```bash
# Поиск по индексу
python manage_index.py search "как настроить бота"

# Статистика
python manage_index.py stats

# Проверка Ollama
python manage_index.py verify
```

## Использование в коде

### Индексация документов

```python
from src.embeddings.chunker import TextChunker
from src.embeddings.embedder import OllamaEmbedder
from src.embeddings.indexer import DocumentIndexer

# Создание компонентов
chunker = TextChunker(chunk_size=800, overlap=150)
embedder = OllamaEmbedder(model="bge-m3")
indexer = DocumentIndexer(
    chunker=chunker,
    embedder=embedder,
    index_path="data/embeddings/document_index.json"
)

# Индексация
stats = indexer.index_directory(
    directory="rag_docs",
    extensions=['.md', '.txt'],
    recursive=True
)

# Сохранение индекса
indexer.save_index()

print(f"Проиндексировано: {stats['indexed_files']} файлов, {stats['total_chunks']} чанков")
```

### Поиск по документам

```python
from src.embeddings.searcher import SemanticSearcher
from src.embeddings.embedder import OllamaEmbedder

# Создание searcher
embedder = OllamaEmbedder()
searcher = SemanticSearcher(
    index_path="data/embeddings/document_index.json",
    embedder=embedder
)

# Поиск
results = searcher.search(
    query="как установить зависимости",
    top_k=3,
    min_similarity=0.5
)

# Результаты
for result in results:
    print(f"Файл: {result['source_file']}")
    print(f"Релевантность: {result['similarity_score']:.3f}")
    print(f"Текст: {result['text'][:200]}...")
    print()
```

### Интеграция с DeepSeek

```python
from src.integrations.deepseek_rag import DeepSeekRAG
from src.embeddings.searcher import SemanticSearcher

# Создание RAG
searcher = SemanticSearcher(index_path="data/embeddings/document_index.json")
rag = DeepSeekRAG(
    searcher=searcher,
    context_chunks=3,
    max_context_tokens=2000
)

# Подготовка запроса с контекстом
result = rag.query_with_context(
    user_query="Как запустить бота?",
    use_rag=True
)

if result['used_rag']:
    # Создаём промпт с контекстом
    prompt = rag.create_rag_prompt(
        user_query=result['query'],
        context=result['context']
    )

    # Отправляем в DeepSeek
    response = deepseek_client.chat(prompt)

    print(f"Использованы источники: {result['sources']}")
    print(f"Ответ: {response}")
```

## CLI Команды

### Индексация

```bash
# Индексация из rag_docs (по умолчанию)
python manage_index.py index

# Индексация из другой директории
python manage_index.py index --source ./my_docs

# Без рекурсивного обхода
python manage_index.py index --no-recursive

# С подробным выводом
python manage_index.py index --verbose
```

### Поиск

```bash
# Простой поиск
python manage_index.py search "как работает бот"

# С параметрами
python manage_index.py search "telegram api" --top-k 10 --min-similarity 0.7
```

### Статистика

```bash
python manage_index.py stats
```

Вывод:
```
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Параметр            ┃ Значение           ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ Всего документов    │ 15                 │
│ Всего чанков        │ 247                │
│ Модель эмбеддингов  │ bge-m3   │
│ Размерность векторов│ 768                │
│ Создан              │ 2025-11-25T00:30:00│
│ Обновлён            │ 2025-11-25T01:15:00│
└─────────────────────┴────────────────────┘
```

### Проверка Ollama

```bash
python manage_index.py verify
```

### Очистка индекса

```bash
python manage_index.py clear
```

## Конфигурация

Настройки находятся в `config/embeddings_config.yaml`:

```yaml
# Настройки Ollama
ollama:
  url: "http://localhost:11434"
  model: "bge-m3"
  timeout: 30

# Параметры чанкинга
chunking:
  chunk_size: 800
  overlap: 150

# Настройки индексации
indexing:
  default_docs_dir: "rag_docs"
  index_path: "data/embeddings/document_index.json"
  include_extensions:
    - ".md"
    - ".txt"

# Настройки поиска
search:
  top_k: 5
  min_similarity: 0.5
  cache_queries: true

# Интеграция с DeepSeek
deepseek_integration:
  context_chunks: 3
  max_context_tokens: 2000
  rag_keywords:
    - "документация"
    - "как работает"
    - "инструкция"
    - "как настроить"
```

## Производительность

### Индексация

- **100 документов** (~1MB): ~2-3 минуты
- **1000 документов** (~10MB): ~15-20 минут

### Поиск

- **Время отклика**: < 1 секунда
- **Кэширование**: Повторные запросы < 100ms

## Troubleshooting

### Ollama недоступен

```
❌ Ollama не доступен!

Инструкция по запуску:
1. Установите Ollama: https://ollama.com/download
2. Запустите сервер: ollama serve
3. Загрузите модель: ollama pull bge-m3
```

**Решение:**
```bash
# Проверьте статус
curl http://localhost:11434/api/tags

# Перезапустите Ollama
ollama serve
```

### Модель не найдена

```bash
# Загрузите модель
ollama pull bge-m3

# Проверьте доступные модели
ollama list
```

### Индекс поврежден

```bash
# Создайте новый индекс
python manage_index.py clear
python manage_index.py index
```

## Расширенное использование

### Добавление новых документов

1. Поместите документы в `rag_docs/`
2. Запустите индексацию:
   ```bash
   python manage_index.py index
   ```

Система автоматически обновит только изменённые файлы.

### Настройка ключевых слов RAG

Отредактируйте `config/embeddings_config.yaml`:

```yaml
deepseek_integration:
  rag_keywords:
    - "документация"
    - "как сделать"
    - "пример кода"
    - # добавьте свои ключевые слова
```

### Использование разных моделей эмбеддингов

```yaml
ollama:
  model: "mxbai-embed-large"  # 1024-мерные векторы, более точные
```

Доступные модели:
- `bge-m3` - 768 измерений, быстрая
- `mxbai-embed-large` - 1024 измерения, более точная
- `all-minilm` - 384 измерения, самая быстрая

## Лучшие практики

1. **Организация документов**
   - Используйте понятную структуру директорий
   - Называйте файлы описательно
   - Разделяйте документы по темам

2. **Размер чанков**
   - Для технической документации: 800-1000 токенов
   - Для коротких заметок: 500-700 токенов
   - Для длинных статей: 1000-1500 токенов

3. **Поиск**
   - Используйте конкретные запросы
   - Экспериментируйте с `min_similarity`
   - Увеличивайте `top_k` для более широкого контекста

4. **Обновление индекса**
   - Переиндексируйте после изменения документов
   - Используйте автоматическую индексацию при добавлении файлов
   - Создавайте backup перед полной переиндексацией

## Кликабельные ссылки на источники

### Обзор

Система поддерживает генерацию кликабельных ссылок на источники документов через MCP (Model Context Protocol) filesystem сервер.

### Функциональность

При использовании DeepSeek с RAG, ответы содержат кликабельные ссылки в формате:

```markdown
📚 **Источники:**
1. 📝 [document.md](mcp://filesystem/...) - строки 15-25 (релевантность: 92%)
2. 📄 [guide.txt](mcp://filesystem/...) - строки 5-15 (релевантность: 87%)

💡 *Нажмите на ссылку чтобы открыть документ через MCP*
```

### Поддерживаемые форматы

- **TXT файлы** (`.txt`) - 📄
- **Markdown файлы** (`.md`, `.markdown`) - 📝

### Настройка

```yaml
# config/embeddings_config.yaml
mcp_links:
  enabled: true
  server_url: "http://localhost:8003"
  supported_extensions:
    - ".txt"
    - ".md"
    - ".markdown"
  max_filename_length: 30
```

### Использование

```python
from src.rag_integration import RAGManager

rag_manager = RAGManager()

# Поиск с источниками
enriched_message, sources = rag_manager.enrich_message_with_rag(
    user_message="Как работает бот?",
    use_reranking=True
)

# Форматирование кликабельных ссылок
clickable_sources = rag_manager.format_clickable_sources(
    search_results=sources,
    max_sources=5
)
```

### Интеграция с DeepSeek

DeepSeek автоматически использует кликабельные ссылки:

```python
from providers.deepseek_provider import DeepSeekProvider

# Генерация ответа с кликабельными ссылками
response, sources = await deepseek.generate_response_with_sources(
    user_message="Вопрос",
    system_prompt="Системный промпт"
)
# response уже содержит кликабельные ссылки
```

### Подробнее

- [MCP Filesystem Integration](./mcp_filesystem_integration.md) - Интеграция с filesystem сервером
- [Source Links Format](./source_links_format.md) - Формат кликабельных ссылок

## Ссылки

- [Ollama Documentation](https://ollama.com/docs)
- [bge-m3 Model](https://ollama.com/library/bge-m3)
- [MCP Filesystem Integration](./mcp_filesystem_integration.md)
- [Source Links Format](./source_links_format.md)
- [Source Citation System](./source_citation_system.md)
