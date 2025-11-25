# RAG Quickstart - Быстрый старт с RAG

## Что вам понадобится

1. **Ollama** - для генерации эмбеддингов локально
2. **Python 3.10+** - для запуска скриптов
3. **Документы** - файлы `.md` или `.txt` для индексации

## Шаг 1: Установка Ollama

### macOS

```bash
brew install ollama
```

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows

Скачайте с https://ollama.com/download

## Шаг 2: Настройка Ollama

```bash
# Загрузите модель для эмбеддингов
ollama pull nomic-embed-text

# Запустите сервер
ollama serve
```

Проверьте что Ollama работает:
```bash
curl http://localhost:11434/api/tags
```

## Шаг 3: Установка зависимостей Python

```bash
pip install -r requirements.txt
```

Это установит:
- `numpy` - для работы с векторами
- `tiktoken` - для подсчёта токенов
- `click` и `rich` - для CLI
- `pyyaml` - для конфигурации
- `requests` - для работы с Ollama API

## Шаг 4: Добавление документов

Создайте структуру директорий в `rag_docs/`:

```bash
mkdir -p rag_docs/{documentation,guides,reference,notes}
```

Добавьте ваши документы:

```
rag_docs/
├── documentation/
│   ├── project_overview.md
│   └── architecture.md
├── guides/
│   ├── installation.md
│   └── configuration.md
├── reference/
│   └── api_reference.txt
└── notes/
    └── meeting_notes.md
```

**Поддерживаемые форматы:**
- Markdown (`.md`)
- Текстовые файлы (`.txt`)

## Шаг 5: Индексация

### Проверка Ollama

Сначала убедитесь что Ollama доступен:

```bash
python manage_index.py verify
```

Ожидаемый вывод:
```
✓ Ollama доступен
✓ Модель nomic-embed-text найдена
```

### Запуск индексации

```bash
python manage_index.py index
```

Процесс индексации:
1. Сканирует директорию `rag_docs/`
2. Разбивает каждый файл на чанки (~800 токенов)
3. Генерирует эмбеддинги через Ollama
4. Сохраняет индекс в `data/embeddings/document_index.json`

Пример вывода:
```
Индексация документов из: rag_docs
Found 15 files to index
Indexing [1/15]: rag_docs/documentation/project_overview.md
Created 5 chunks for rag_docs/documentation/project_overview.md
...
✓ Индексация завершена!
Проиндексировано файлов: 15/15
Создано чанков: 247
```

### Время выполнения

- **10-20 файлов**: ~1-2 минуты
- **50-100 файлов**: ~5-10 минут
- **200+ файлов**: ~20-30 минут

## Шаг 6: Проверка работы

### Просмотр статистики

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
│ Модель эмбеддингов  │ nomic-embed-text   │
│ Размерность векторов│ 768                │
└─────────────────────┴────────────────────┘
```

### Тестовый поиск

```bash
python manage_index.py search "как установить проект"
```

Результат:
```
Найдено результатов: 3

1. rag_docs/guides/installation.md
   Релевантность: 0.892
   ## Установка проекта

   Для установки проекта выполните следующие шаги:
   1. Клонируйте репозиторий...

2. rag_docs/documentation/project_overview.md
   Релевантность: 0.765
   В разделе установки описан процесс...

3. rag_docs/guides/configuration.md
   Релевантность: 0.623
   После установки необходимо настроить...
```

## Шаг 7: Использование в коде

### Простой пример

```python
from src.embeddings.searcher import SemanticSearcher

# Создаём searcher
searcher = SemanticSearcher(
    index_path="data/embeddings/document_index.json"
)

# Поиск
results = searcher.search(
    query="как запустить проект",
    top_k=3
)

# Выводим результаты
for result in results:
    print(f"Файл: {result['source_file']}")
    print(f"Текст: {result['text'][:200]}...")
    print(f"Релевантность: {result['similarity_score']:.3f}\n")
```

### Интеграция с DeepSeek

```python
from src.integrations.deepseek_rag import DeepSeekRAG
from src.embeddings.searcher import SemanticSearcher

# Инициализация
searcher = SemanticSearcher()
rag = DeepSeekRAG(searcher=searcher)

# Запрос с контекстом
result = rag.query_with_context(
    user_query="Как настроить конфигурацию?",
    use_rag=True
)

if result['used_rag']:
    print("Найдены релевантные документы:")
    for source in result['sources']:
        print(f"  - {source['file']} (релевантность: {source['score']:.3f})")

    # Создаём промпт с контекстом
    prompt = rag.create_rag_prompt(
        user_query=result['query'],
        context=result['context']
    )

    # Отправляем в DeepSeek
    # response = deepseek_api.chat(prompt)
```

## Частые проблемы и решения

### Ollama не доступен

**Проблема:**
```
❌ Ollama не доступен!
```

**Решение:**
```bash
# Проверьте что Ollama запущен
ollama serve

# В другом терминале
ollama list

# Если модель не установлена
ollama pull nomic-embed-text
```

### Модель не найдена

**Проблема:**
```
⚠ Модель nomic-embed-text не найдена
```

**Решение:**
```bash
ollama pull nomic-embed-text
```

### Пустой индекс

**Проблема:**
```
Проиндексировано файлов: 0/0
```

**Решение:**
1. Убедитесь что файлы есть в `rag_docs/`
2. Проверьте расширения файлов (`.md` или `.txt`)
3. Проверьте что файлы не пустые

### Ошибки кодировки

**Проблема:**
```
UnicodeDecodeError: 'utf-8' codec can't decode...
```

**Решение:**
Файлы автоматически пробуют несколько кодировок (UTF-8, UTF-16, CP1251). Если проблема остаётся, пересохраните файл в UTF-8.

## Следующие шаги

1. **Добавьте больше документов** в `rag_docs/`
2. **Экспериментируйте с поиском** используя разные запросы
3. **Настройте параметры** в `config/embeddings_config.yaml`:
   - Размер чанков (`chunk_size`)
   - Количество результатов (`top_k`)
   - Минимальное сходство (`min_similarity`)
4. **Интегрируйте с ботом** - см. полную документацию

## Дополнительные команды

### Обновление индекса

После изменения документов:

```bash
python manage_index.py index
```

Система автоматически переиндексирует только изменённые файлы.

### Очистка и переиндексация

```bash
# Очистить индекс
python manage_index.py clear

# Создать новый
python manage_index.py index
```

### Поиск с фильтрами

```bash
# Только markdown файлы
python manage_index.py search "query" --filter-type md

# Больше результатов
python manage_index.py search "query" --top-k 10

# Более строгий порог
python manage_index.py search "query" --min-similarity 0.7
```

## Полезные ссылки

- [Полная документация RAG](./rag_implementation.md)
- [Ollama Documentation](https://ollama.com/docs)
- [nomic-embed-text на Ollama](https://ollama.com/library/nomic-embed-text)

## Поддержка

Если у вас возникли проблемы:

1. Проверьте что Ollama запущен: `ollama serve`
2. Проверьте логи: `logs/embeddings.log`
3. Запустите с verbose: `python manage_index.py index --verbose`
