# RAG Setup Guide - Руководство по настройке RAG

## ✅ Что было реализовано

Полная система RAG (Retrieval Augmented Generation) для DeepSeek с локальными эмбеддингами через Ollama.

### Основные компоненты

1. **Система индексации** (`src/embeddings/`)
   - `chunker.py` - разбивка документов на чанки
   - `embedder.py` - генерация эмбеддингов через Ollama
   - `indexer.py` - управление индексом
   - `searcher.py` - семантический поиск

2. **Интеграция с DeepSeek** (`src/integrations/`)
   - `deepseek_rag.py` - автоматическое использование контекста

3. **CLI инструменты**
   - `manage_index.py` - управление индексом через командную строку

4. **Конфигурация**
   - `config/embeddings_config.yaml` - все настройки системы

5. **Документация**
   - `docs/rag_implementation.md` - полное описание
   - `docs/rag_quickstart.md` - быстрый старт
   - Обновлённый `README.md`

## 🚀 Быстрый старт (3 минуты)

### 1. Установите Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Загрузите модель эмбеддингов
ollama pull bge-m3

# Запустите сервер
ollama serve
```

### 2. Установите зависимости

```bash
pip install -r requirements.txt
```

### 3. Проверьте работоспособность

```bash
python manage_index.py verify
```

Должно вывести:
```
✓ Ollama доступен
✓ Модель bge-m3 найдена
```

### 4. Индексируйте документы

В проекте уже есть примеры документов в `rag_docs/`:
- `documentation/bot_overview.md`
- `guides/getting_started.md`
- `reference/api_keys.txt`

Запустите индексацию:

```bash
python manage_index.py index
```

### 5. Тестовый поиск

```bash
python manage_index.py search "как настроить бота"
```

Вы должны увидеть релевантные фрагменты из документов.

## 📂 Структура проекта

```
ai_challenge_4_telegram/
├── rag_docs/                          # Документы для индексации
│   ├── documentation/                 # Документация
│   ├── guides/                        # Руководства
│   ├── notes/                         # Заметки
│   └── reference/                     # Справочники
├── src/
│   ├── embeddings/                    # Модули RAG
│   │   ├── chunker.py                # Разбивка на чанки
│   │   ├── embedder.py               # Генерация эмбеддингов
│   │   ├── indexer.py                # Управление индексом
│   │   └── searcher.py               # Семантический поиск
│   ├── integrations/
│   │   └── deepseek_rag.py           # Интеграция с DeepSeek
│   └── utils/
│       └── file_parser.py            # Парсинг файлов
├── data/
│   └── embeddings/
│       ├── document_index.json       # Индекс (создаётся автоматически)
│       └── backups/                  # Backup'ы индекса
├── config/
│   └── embeddings_config.yaml        # Конфигурация RAG
├── docs/
│   ├── rag_implementation.md         # Полная документация
│   └── rag_quickstart.md             # Быстрый старт
├── manage_index.py                   # CLI для управления индексом
└── README.md                         # Обновлённая документация
```

## 🎯 Использование

### CLI команды

```bash
# Индексация
python manage_index.py index                    # Индексировать rag_docs/
python manage_index.py index --source ./docs   # Индексировать другую директорию
python manage_index.py index --verbose          # С подробным выводом

# Поиск
python manage_index.py search "ваш запрос"
python manage_index.py search "query" --top-k 10

# Статистика
python manage_index.py stats

# Проверка Ollama
python manage_index.py verify

# Очистка
python manage_index.py clear
```

### В Python коде

```python
from src.embeddings.searcher import SemanticSearcher
from src.integrations.deepseek_rag import DeepSeekRAG

# Создание компонентов
searcher = SemanticSearcher(
    index_path="data/embeddings/document_index.json"
)

rag = DeepSeekRAG(
    searcher=searcher,
    context_chunks=3,
    max_context_tokens=2000
)

# Поиск контекста для запроса
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

    # Используем в DeepSeek
    # response = deepseek_provider.chat(prompt)

    print(f"Использованы источники:")
    for source in result['sources']:
        print(f"  - {source['file']}")
```

## ⚙️ Конфигурация

Все настройки в `config/embeddings_config.yaml`:

### Основные параметры

```yaml
# Ollama
ollama:
  url: "http://localhost:11434"
  model: "bge-m3"    # или mxbai-embed-large

# Размер чанков
chunking:
  chunk_size: 800               # токены
  overlap: 150                  # перекрытие

# Директория с документами
indexing:
  default_docs_dir: "rag_docs"
  include_extensions:
    - ".md"
    - ".txt"

# Поиск
search:
  top_k: 5                      # количество результатов
  min_similarity: 0.5           # порог релевантности

# DeepSeek
deepseek_integration:
  context_chunks: 3             # чанков в контексте
  max_context_tokens: 2000      # максимум токенов
```

## 🔧 Интеграция с ботом

### Добавьте в bot.py

```python
# В начале файла
from src.embeddings.searcher import SemanticSearcher
from src.integrations.deepseek_rag import DeepSeekRAG

# При инициализации
searcher = SemanticSearcher(
    index_path="data/embeddings/document_index.json"
)

deepseek_rag = DeepSeekRAG(
    searcher=searcher,
    context_chunks=3
)

# В обработчике сообщений DeepSeek
async def handle_deepseek_message(update, context):
    user_message = update.message.text

    # Получаем контекст из документов
    rag_result = deepseek_rag.query_with_context(
        user_query=user_message,
        use_rag=True
    )

    if rag_result['used_rag']:
        # Создаём промпт с контекстом
        prompt = deepseek_rag.create_rag_prompt(
            user_query=rag_result['query'],
            context=rag_result['context']
        )
    else:
        prompt = user_message

    # Отправляем в DeepSeek
    response = await deepseek_provider.chat(prompt)

    await update.message.reply_text(response)
```

## 📊 Примеры использования

### Добавление своих документов

1. Поместите файлы в `rag_docs/`:
   ```bash
   cp my_docs/*.md rag_docs/documentation/
   ```

2. Индексируйте:
   ```bash
   python manage_index.py index
   ```

3. Система автоматически:
   - Разобьёт на чанки
   - Сгенерирует эмбеддинги
   - Обновит индекс

### Автоматическое использование RAG

DeepSeek автоматически использует RAG при наличии ключевых слов:
- "документация"
- "как работает"
- "инструкция"
- "как настроить"
- "как запустить"
- и другие...

Настройте в `config/embeddings_config.yaml`:
```yaml
deepseek_integration:
  rag_keywords:
    - "мой ключевое слово"
    - "ещё одно"
```

## 🐛 Troubleshooting

### Ollama недоступен

```bash
# Проверьте статус
curl http://localhost:11434/api/tags

# Перезапустите
ollama serve

# Проверьте модель
ollama list
```

### Модель не найдена

```bash
ollama pull bge-m3
```

### Пустой индекс

1. Проверьте наличие файлов в `rag_docs/`
2. Проверьте расширения (`.md` или `.txt`)
3. Убедитесь что файлы не пустые

### Медленная индексация

- Для больших коллекций (100+ файлов) индексация может занять 10-20 минут
- Ollama генерирует эмбеддинги локально, это требует ресурсов
- Используйте `--verbose` чтобы видеть прогресс

## 📚 Документация

- **[docs/rag_implementation.md](docs/rag_implementation.md)** - Полное описание реализации
- **[docs/rag_quickstart.md](docs/rag_quickstart.md)** - Руководство быстрого старта
- **[config/embeddings_config.yaml](config/embeddings_config.yaml)** - Все настройки с комментариями

## 🎉 Что дальше?

1. **Добавьте свои документы** в `rag_docs/`
2. **Протестируйте поиск** с разными запросами
3. **Интегрируйте с ботом** для автоматического использования контекста
4. **Настройте параметры** под вашу задачу

## 💡 Советы

1. **Структурируйте документы** по папкам (документация, руководства, справка)
2. **Используйте понятные имена файлов** - это помогает при отладке
3. **Регулярно обновляйте индекс** после изменения документов
4. **Экспериментируйте с параметрами** - разные задачи требуют разных настроек
5. **Проверяйте релевантность** результатов поиска

## 🔗 Полезные ссылки

- [Ollama](https://ollama.com)
- [bge-m3](https://ollama.com/library/bge-m3)
- [DeepSeek](https://deepseek.com)

---

**Готово!** Теперь ваш бот может использовать контекст из локальных документов для более точных ответов.
