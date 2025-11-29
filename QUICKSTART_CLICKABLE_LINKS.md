# Быстрый старт: Кликабельные ссылки на источники RAG

## Пошаговое руководство по запуску и использованию

---

## Шаг 1: Проверка зависимостей

Убедитесь, что все необходимые пакеты установлены:

```bash
# Проверка основных зависимостей
python -c "import fastmcp; print('FastMCP:', fastmcp.__version__)"
python -c "from src.integrations.mcp_link_generator import MCPLinkGenerator; print('MCPLinkGenerator: OK')"
python -c "from src.rag_integration import RAGManager; print('RAGManager: OK')"
```

Если что-то отсутствует:

```bash
pip install -r requirements.txt
```

---

## Шаг 2: Запуск MCP Filesystem сервера

### Вариант 1: Режим SSE (рекомендуется)

```bash
# Запуск в отдельном терминале
python mcp_server/filesystem.py
```

**Ожидаемый вывод:**
```
INFO:__main__:Запуск Filesystem MCP сервера в режиме SSE на порту 8003
INFO:uvicorn:Started server process
INFO:uvicorn:Waiting for application startup
INFO:uvicorn:Application startup complete
INFO:uvicorn:Uvicorn running on http://0.0.0.0:8003
```

### Вариант 2: Режим stdio

```bash
python mcp_server/filesystem.py --stdio
```

### Проверка работы сервера

```bash
# Проверка доступности
curl http://localhost:8003/sse

# Ожидаемый ответ: Server-Sent Events endpoint
```

---

## Шаг 3: Проверка конфигурации RAG

Убедитесь, что кликабельные ссылки включены:

```bash
# Проверка конфигурации
cat config/embeddings_config.yaml | grep -A 10 "mcp_links"
```

**Ожидаемый вывод:**
```yaml
mcp_links:
  enabled: true
  server_url: "http://localhost:8003"
  base_path: null
  supported_extensions:
    - ".txt"
    - ".md"
    - ".markdown"
  max_filename_length: 30
```

Если `enabled: false`, измените на `true`:

```bash
# Включение кликабельных ссылок
sed -i '' 's/enabled: false/enabled: true/g' config/embeddings_config.yaml
```

---

## Шаг 4: Запуск автотестов

Проверьте работоспособность всех компонентов:

```bash
python test_clickable_links.py
```

**Ожидаемый результат:**
```
================================================================================
ТЕСТИРОВАНИЕ КЛИКАБЕЛЬНЫХ ССЫЛОК НА ИСТОЧНИКИ
================================================================================

✅ Пройдено: 7/7
❌ Провалено: 0/7

🎉 Все тесты пройдены успешно!
```

---

## Шаг 5: Подготовка тестовых документов

Убедитесь, что есть проиндексированные документы:

```bash
# Проверка наличия документов
ls -la rag_docs/

# Проверка индекса
python manage_index.py stats
```

Если индекс пустой или отсутствует:

```bash
# Индексация документов
python manage_index.py index

# Проверка статистики
python manage_index.py stats
```

---

## Шаг 6: Тестирование через Python скрипт

Создайте тестовый скрипт для проверки end-to-end:

```python
# test_integration.py
import asyncio
from src.rag_integration import RAGManager

async def test_clickable_links():
    # Инициализация RAG Manager
    rag_manager = RAGManager()

    print("🔍 Тестирование кликабельных ссылок...\n")

    # Поиск с использованием RAG
    enriched_message, sources = rag_manager.enrich_message_with_rag(
        user_message="Расскажи про документацию бота",
        use_reranking=True
    )

    if sources:
        print(f"✅ Найдено источников: {len(sources)}\n")

        # Форматирование кликабельных источников
        clickable_sources = rag_manager.format_clickable_sources(
            search_results=sources,
            max_sources=5
        )

        print("📚 Результат:\n")
        print(clickable_sources)

        # Проверка наличия MCP ссылок
        if "mcp://filesystem/" in clickable_sources:
            print("\n✅ Кликабельные ссылки успешно сгенерированы!")
        else:
            print("\n⚠️ Кликабельные ссылки не найдены")
    else:
        print("❌ Источники не найдены. Проверьте индекс документов.")

if __name__ == "__main__":
    asyncio.run(test_clickable_links())
```

Запуск:

```bash
python test_integration.py
```

---

## Шаг 7: Запуск Telegram бота с DeepSeek

### 7.1 Проверка переменных окружения

```bash
# Проверка наличия необходимых ключей
echo "TELEGRAM_TOKEN: ${TELEGRAM_TOKEN:0:10}..."
echo "DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:0:10}..."
```

### 7.2 Запуск бота

```bash
# Запуск бота
python bot.py
```

**Ожидаемый вывод:**
```
INFO:__main__:RAG Manager инициализирован
INFO:__main__:DeepSeek Provider инициализирован с RAG
INFO:__main__:RAGManager initialized: index_path=data/embeddings/document_index.json, clickable_links=True
INFO:telegram.ext._application:Application started
```

---

## Шаг 8: Тестирование в Telegram

### 8.1 Переключение на DeepSeek

Отправьте боту команду:
```
/deepseek
```

**Ожидаемый ответ:**
```
✅ Выбрана модель DeepSeek

Теперь я буду использовать DeepSeek для генерации ответов.

Используемая модель: deepseek-chat
```

### 8.2 Запрос с RAG

Отправьте вопрос с ключевым словом для активации RAG:
```
Расскажи про документацию бота
```

или

```
Как работает RAG в этом проекте?
```

**Ожидаемый ответ:**
```
[Ответ модели с цитатами [1], [2] и т.д.]

📚 **Источники:**
1. 📝 [bot_overview.md](mcp://filesystem/...) - строки 1-20 (релевантность: 95%)
2. 📝 [rag_implementation.md](mcp://filesystem/...) - строки 10-25 (релевантность: 92%)
3. 📝 [getting_started.md](mcp://filesystem/...) - строки 5-15 (релевантность: 87%)

💡 *Нажмите на ссылку чтобы открыть документ через MCP*
```

---

## Troubleshooting

### Проблема 1: MCP сервер не запускается

**Ошибка:**
```
Error: Address already in use
```

**Решение:**
```bash
# Найти процесс на порту 8003
lsof -i :8003

# Завершить процесс
kill -9 <PID>

# Перезапустить сервер
python mcp_server/filesystem.py
```

### Проблема 2: Нет источников в ответе

**Причины:**
- Индекс пустой или не создан
- Запрос не содержит RAG ключевых слов
- Релевантность источников слишком низкая

**Решение:**
```bash
# Проверка индекса
python manage_index.py stats

# Переиндексация
python manage_index.py index

# Поиск по индексу
python manage_index.py search "документация"
```

### Проблема 3: Ссылки не кликабельны в Telegram

**Причина:** Telegram не поддерживает нативно `mcp://` схему

**Решение:**
- Это ожидаемое поведение
- MCP ссылки работают только в MCP-совместимых клиентах
- В Telegram они отображаются как текст

**Альтернативы:**
1. Использовать MCP-совместимый клиент
2. Реализовать web-based предпросмотр (будущее улучшение)

### Проблема 4: Кликабельные ссылки отключены

**Проверка конфигурации:**
```python
python -c "
from src.rag_integration import RAGManager
rag = RAGManager()
print('Clickable links enabled:', rag.enable_clickable_links)
"
```

**Если False:**
```bash
# Включение в конфиге
vi config/embeddings_config.yaml
# Измените: enabled: true в секции mcp_links
```

---

## Проверочный чеклист

Используйте этот чеклист для проверки работоспособности:

- [ ] MCP filesystem сервер запущен (`http://localhost:8003`)
- [ ] Конфигурация `mcp_links.enabled: true`
- [ ] Индекс документов создан (проверка `manage_index.py stats`)
- [ ] Автотесты пройдены (`test_clickable_links.py`)
- [ ] Telegram бот запущен
- [ ] DeepSeek активирован (`/deepseek`)
- [ ] RAG срабатывает на ключевые слова
- [ ] Источники отображаются с кликабельными ссылками

---

## Примеры RAG ключевых слов

Используйте эти слова для активации RAG:

- "документация"
- "как работает"
- "инструкция"
- "руководство"
- "что такое"
- "объясни"
- "покажи пример"
- "как использовать"
- "расскажи про"
- "как настроить"
- "команды"

**Пример запроса:**
```
Объясни как работает система цитирования в RAG
```

---

## Мониторинг работы

### Проверка логов бота

```bash
# Просмотр логов в реальном времени
tail -f logs/*.log
```

### Проверка статистики RAG

```python
python -c "
from src.rag_integration import RAGManager
rag = RAGManager()
stats = rag.get_statistics()
print('RAG Statistics:')
for key, value in stats.items():
    print(f'  {key}: {value}')
"
```

---

## Дополнительные ресурсы

### Документация

- `/docs/mcp_filesystem_integration.md` - MCP filesystem интеграция
- `/docs/source_links_format.md` - Формат кликабельных ссылок
- `/docs/rag_implementation.md` - RAG система
- `CLICKABLE_LINKS_IMPLEMENTATION_SUMMARY.md` - Итоговый отчет

### Тестовые скрипты

- `test_clickable_links.py` - Автотесты компонентов
- `test_integration.py` - End-to-end тест (создайте самостоятельно)

### Конфигурация

- `config/embeddings_config.yaml` - Основная конфигурация RAG и MCP

---

## Следующие шаги

После успешного запуска вы можете:

1. **Добавить свои документы:**
   ```bash
   # Поместите .txt или .md файлы в rag_docs/
   cp my_documents/*.md rag_docs/documentation/

   # Переиндексируйте
   python manage_index.py index
   ```

2. **Настроить параметры:**
   - Количество источников: `citation.default_sources_count`
   - Минимальная релевантность: `search.min_similarity`
   - Максимальная длина имени: `mcp_links.max_filename_length`

3. **Расширить функциональность:**
   - Добавить поддержку новых форматов
   - Реализовать web-based предпросмотр
   - Улучшить точность номеров строк

---

**Дата создания:** 29.11.2025
**Версия:** 1.0
**Автор:** Claude Code (Sonnet 4.5)
