# Реализация кликабельных ссылок в Telegram

## Обзор

Реализована полная функциональность кликабельных ссылок для источников RAG в Telegram боте. Пользователи могут нажимать на inline кнопки для просмотра исходных документов и конкретных chunks.

## Архитектура

### Основные компоненты

1. **TelegramDocumentHandler** (`src/integrations/telegram_document_handler.py`)
   - Управляет обработкой документов и callback запросов
   - Создает inline кнопки для источников
   - Обрабатывает нажатия на кнопки

2. **RAGManager** (`src/rag_integration.py`)
   - Интегрирован с TelegramDocumentHandler
   - Форматирует источники с inline кнопками
   - Поддерживает graceful degradation

3. **MCP_LINK_GENERATOR** (`src/integrations/mcp_link_generator.py`)
   - Генерирует рабочие ссылки на документы
   - Поддерживает различные форматы файлов
   - Создает ссылки на конкретные строки

## Функциональность

### 1. Форматирование источников

Источники RAG теперь отображаются с inline кнопками:

```python
# Пример форматирования
sources_text, inline_keyboard = rag_manager.format_sources_with_telegram_buttons(
    sources,
    title="📚 **Источники:**"
)
```

### 2. Inline кнопки

Для каждого источника создается кнопка с:
- Эмодзи типа файла
- Коротким именем файла
- Релевантностью (в %)
- Callback данными для обработки нажатия

### 3. Обработка нажатий

При нажатии на кнопку:
- Показывается информация о документе
- Отображается содержимое chunk (если найден)
- Предлагаются действия (полный документ, выделить строки)

### 4. Graceful degradation

Если TelegramDocumentHandler не доступен:
- Используется текстовый формат с обычными ссылками
- Сохраняется полная функциональность

## Поддерживаемые типы файлов

| Расширение | Эмодзи | Описание |
|------------|--------|----------|
| .txt | 📄 | Текстовые файлы |
| .md, .markdown | 📝 | Markdown файлы |
| .py | 🐍 | Python файлы |
| .json, .yaml, .yml | 📋 | Структурированные данные |
| .sql | 🗃️ | SQL файлы |
| .log | 📜 | Лог-файлы |
| прочие | 📄 | По умолчанию |

## Callback данные

Формат callback данных: `doc:{file_path}:{chunk_id}:{line_numbers}`

Пример: `doc:/rag_docs/test.md:chunk_0:1-20`

## Интеграция с ботом

### Настройка

```python
# В bot.py
from src.integrations.telegram_document_handler import create_telegram_document_handler
from src.rag_integration import RAGManager

# Инициализация
rag_manager = RAGManager()
doc_handler = create_telegram_document_handler(rag_manager)
rag_manager.set_document_handler(doc_handler)

# Регистрация handler
application.add_handler(CallbackQueryHandler(
    doc_handler.handle_document_callback, 
    pattern=r'^doc:'
))
```

### Использование в ответах

```python
# Получение отформатированных источников
sources_text, reply_markup = rag_manager.format_sources_with_telegram_buttons(
    sources,
    title="📚 **Источники:**"
)

# Отправка ответа с inline кнопками
await update.message.reply_text(
    response_text + sources_text,
    reply_markup=reply_markup,
    parse_mode='Markdown'
)
```

## Тестирование

### Финальный интеграционный тест

Запуск полного тестирования:
```bash
python test_final_clickable_links.py
```

Тест проверяет:
1. ✅ Инициализацию компонентов
2. ✅ Форматирование inline кнопок
3. ✅ Обработку callback данных
4. ✅ Обработку нажатий
5. ✅ Интеграцию с ботом
6. ✅ Эмодзи для файлов
7. ✅ Graceful degradation

### Дополнительные тесты

- `test_telegram_integration.py` - базовые тесты интеграции
- `test_rag_citation_integration.py` - тесты цитирования

## Возможные действия при нажатии на кнопку

1. **Показать chunk** - отображение содержимого chunk
2. **Полный документ** - отправка полного файла как документа
3. **Выделить строки** - выделение строк в документе (если возможно)

## Обработка ошибок

- Если chunk не найден - показывается сообщение об ошибке
- Если файл не существует - предлагается альтернатива
- Callback ошибки обрабатываются gracefully

## Преимущества реализации

1. **Удобство использования** - один клик для доступа к источнику
2. **Информативность** - эмодзи и процент релевантности
3. **Гибкость** - поддержка различных форматов
4. **Надежность** - graceful degradation при ошибках
5. **Масштабируемость** - легкое добавление новых типов файлов

## Будущие улучшения

1. Поддержка preview для больших файлов
2. Кэширование часто запрашиваемых chunks
3. Поиск по документам из интерфейса
4. Экспорт результатов в разные форматы

## Итог

Реализована полнофункциональная система кликабельных ссылок для RAG источников в Telegram боте. Система проходит все тесты и готова к использованию в production.
