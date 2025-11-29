# MCP Filesystem Integration - Интеграция с файловой системой

## Обзор

MCP Filesystem сервер предоставляет инструменты для работы с файловой системой через Model Context Protocol, позволяя читать документы и открывать их через кликабельные ссылки в Telegram боте.

## Архитектура

```
┌─────────────────────┐
│  Telegram Bot       │
│  (RAG DeepSeek)     │
└──────────┬──────────┘
           │
           │ Генерация ссылок
           ▼
┌─────────────────────┐
│ MCPLinkGenerator    │
│ (mcp_link_generator)│
└──────────┬──────────┘
           │
           │ mcp://filesystem/...
           │
           ▼
┌─────────────────────┐
│  MCP Filesystem     │
│  Server             │
│  (filesystem.py)    │
└──────────┬──────────┘
           │
           │ Чтение/запись
           ▼
┌─────────────────────┐
│  Файловая система   │
│  (rag_docs/)        │
└─────────────────────┘
```

## Компоненты системы

### 1. MCP Filesystem Server

**Файл:** `mcp_server/filesystem.py`

FastMCP-based сервер, предоставляющий инструменты для работы с файловой системой.

#### Доступные инструменты

##### list_directory(path: str)
Вывод содержимого директории.

```python
@mcp.tool()
async def list_directory(path: str = ".") -> str:
    """
    Args:
        path: Путь к директории (по умолчанию текущая)

    Returns:
        Список файлов с метаинформацией
    """
```

**Пример ответа:**
```
📂 Содержимое директории: /path/to/rag_docs
Всего элементов: 15
================================================================================
Тип        | Размер     | Дата изменения      | Имя
--------------------------------------------------------------------------------
📁 DIR     | ---        | 2025-11-28 15:30:00 | documentation
📄 FILE    | 12.45 KB   | 2025-11-28 14:20:00 | overview.md
📄 FILE    | 8.32 KB    | 2025-11-27 10:15:00 | getting_started.md
```

##### change_directory(path: str)
Навигация по файловой системе.

```python
@mcp.tool()
async def change_directory(path: str) -> str:
    """
    Args:
        path: Целевой путь (абсолютный или относительный)

    Returns:
        Подтверждение и текущий путь
    """
```

##### read_file(path: str, encoding: str)
Чтение содержимого файла.

```python
@mcp.tool()
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """
    Args:
        path: Путь к файлу
        encoding: Кодировка (utf-8, cp1251, latin-1, ascii)

    Returns:
        Содержимое файла
    """
```

**Ограничения:**
- Максимальный размер файла: 10 MB
- Поддерживаемые кодировки: utf-8, cp1251, latin-1, ascii
- Бинарные файлы не поддерживаются

##### write_file(path: str, content: str, overwrite: bool, encoding: str)
Создание нового файла.

```python
@mcp.tool()
async def write_file(
    path: str,
    content: str,
    overwrite: bool = False,
    encoding: str = "utf-8"
) -> str:
    """
    Args:
        path: Путь к файлу
        content: Содержимое файла
        overwrite: Разрешить перезапись
        encoding: Кодировка
    """
```

**Ограничения:**
- Максимальный размер контента: 5 MB

##### edit_file(path: str, new_content: str, create_backup: bool, encoding: str)
Редактирование существующего файла.

```python
@mcp.tool()
async def edit_file(
    path: str,
    new_content: str,
    create_backup: bool = True,
    encoding: str = "utf-8"
) -> str:
    """
    Args:
        path: Путь к файлу
        new_content: Новое содержимое
        create_backup: Создать резервную копию
        encoding: Кодировка
    """
```

##### get_file_info(path: str)
Получение метаданных файла или директории.

```python
@mcp.tool()
async def get_file_info(path: str) -> str:
    """
    Args:
        path: Путь к файлу или директории

    Returns:
        Детальная информация с метаданными
    """
```

**Пример ответа:**
```
ℹ️ Информация о: /path/to/file.md
================================================================================
Тип: 📄 Файл
Имя: file.md
Размер: 15.42 KB
Расширение: .md
Дата создания: 2025-11-25 12:00:00
Дата изменения: 2025-11-28 15:30:00
Права доступа: rw-r--r-- (644)
Доступ (чтение): ✅
Доступ (запись): ✅
```

### 2. MCPLinkGenerator

**Файл:** `src/integrations/mcp_link_generator.py`

Генератор кликабельных ссылок на документы через MCP протокол.

#### Основные методы

##### generate_file_link(file_path: str, line_numbers: str)
Генерирует MCP URI ссылку на файл.

```python
def generate_file_link(
    self,
    file_path: str,
    line_numbers: Optional[str] = None
) -> str:
    """
    Args:
        file_path: Путь к файлу
        line_numbers: Номера строк (опционально)

    Returns:
        MCP URI в формате: mcp://filesystem/path/to/file.txt#lines=1-10
    """
```

**Формат ссылки:**
```
mcp://filesystem/{encoded_path}#lines={line_numbers}
```

**Пример:**
```python
link = generator.generate_file_link(
    "/path/to/document.md",
    "15-25"
)
# Результат: mcp://filesystem/%2Fpath%2Fto%2Fdocument.md#lines=15-25
```

##### format_clickable_source(source_file, chunk_id, line_numbers, relevance)
Форматирует кликабельный источник для отображения в Telegram.

```python
def format_clickable_source(
    self,
    source_file: str,
    chunk_id: str,
    line_numbers: str,
    relevance: str,
    max_filename_length: int = 30
) -> str:
    """
    Returns:
        Отформатированная строка с эмодзи, именем файла,
        кликабельной ссылкой, строками и релевантностью
    """
```

**Пример вывода:**
```
📝 [document.md](mcp://filesystem/...) - строки 15-25 (релевантность: 92%)
```

##### format_clickable_sources(search_results, max_sources, title)
Форматирует список кликабельных источников.

```python
def format_clickable_sources(
    self,
    search_results: List[Dict],
    max_sources: int = 5,
    title: str = "📚 **Источники:**"
) -> str:
    """
    Args:
        search_results: Результаты RAG поиска
        max_sources: Максимальное количество источников
        title: Заголовок списка

    Returns:
        Полный отформатированный список источников с примечанием
    """
```

**Пример вывода:**
```
📚 **Источники:**
1. 📝 [document.md](mcp://...) - строки 15-25 (релевантность: 92%)
2. 📄 [guide.txt](mcp://...) - строки 5-15 (релевантность: 87%)
3. 📝 [readme.md](mcp://...) - строки 1-10 (релевантность: 81%)

💡 *Нажмите на ссылку чтобы открыть документ через MCP*
```

##### is_supported_file(file_path: str)
Проверяет поддержку типа файла.

```python
def is_supported_file(self, file_path: str) -> bool:
    """
    Returns:
        True если расширение файла поддерживается

    Поддерживаемые расширения:
        - .txt
        - .md
        - .markdown
    """
```

##### filter_supported_sources(search_results)
Фильтрует источники по поддерживаемым типам.

```python
def filter_supported_sources(
    self,
    search_results: List[Dict]
) -> List[Dict]:
    """
    Оставляет только источники с поддерживаемыми расширениями
    """
```

### 3. Интеграция с RAG

**Файл:** `src/rag_integration.py`

#### format_clickable_sources()

Метод RAGManager, использующий MCPLinkGenerator для форматирования источников.

```python
def format_clickable_sources(
    self,
    search_results: List[Dict],
    max_sources: Optional[int] = None,
    title: str = "📚 **Источники:**"
) -> str:
    """
    Форматирует кликабельные источники для отображения в Telegram.

    Если enable_clickable_links=False, возвращает обычный формат.
    """
```

**Процесс работы:**
1. Проверка `enable_clickable_links` флага
2. Фильтрация поддерживаемых файлов
3. Ограничение количества источников
4. Форматирование через `link_generator.format_clickable_sources()`
5. Fallback на `format_sources_info()` при ошибке

#### generate_mcp_links_for_sources()

Обогащает результаты RAG ссылками MCP.

```python
def generate_mcp_links_for_sources(
    self,
    search_results: List[Dict]
) -> List[Dict]:
    """
    Добавляет поле 'mcp_link' к каждому источнику.

    Returns:
        Список источников с добавленными полями:
        - mcp_link: MCP URI ссылка
        - clickable: bool флаг поддержки
    """
```

## Конфигурация

### Настройки в embeddings_config.yaml

```yaml
mcp_links:
  enabled: true                           # Включить кликабельные ссылки
  server_url: "http://localhost:8003"     # URL MCP filesystem сервера
  base_path: null                         # Базовый путь к документам (опционально)

  # Поддерживаемые расширения файлов
  supported_extensions:
    - ".txt"
    - ".md"
    - ".markdown"

  # Максимальная длина имени файла в ссылке
  max_filename_length: 30
```

### Параметры конфигурации

- `enabled`: Глобальное включение/выключение функциональности
- `server_url`: URL MCP filesystem сервера (SSE endpoint)
- `base_path`: Опциональный базовый путь для валидации файлов
- `supported_extensions`: Список поддерживаемых расширений
- `max_filename_length`: Максимальная длина имени файла в отображении

## Безопасность

### Валидация путей

MCP filesystem сервер реализует защиту от path traversal атак:

```python
def validate_path(path_str: str) -> tuple[bool, str, Optional[Path]]:
    """
    Проверки:
    1. Разрешение относительных путей
    2. Блокировка path traversal (..)
    3. Запрет доступа к системным директориям
    4. Проверка существования пути
    """
```

**Запрещенные директории:**
- `/etc`
- `/sys`
- `/proc`
- `/dev`
- `/boot`

### Ограничения размеров

- **Чтение файла:** max 10 MB
- **Запись файла:** max 5 MB
- **Количество источников:** настраиваемо (по умолчанию 5)

### Разрешенные кодировки

- utf-8 (по умолчанию)
- cp1251
- latin-1
- ascii

## Использование в коде

### Создание генератора ссылок

```python
from src.integrations.mcp_link_generator import MCPLinkGenerator

# Создание генератора
link_generator = MCPLinkGenerator(
    mcp_server_url="http://localhost:8003",
    base_path="/path/to/rag_docs"  # опционально
)

# Генерация ссылки
link = link_generator.generate_file_link(
    file_path="/path/to/document.md",
    line_numbers="15-25"
)
```

### Интеграция с RAG Manager

```python
from src.rag_integration import RAGManager

# Создание RAG Manager с кликабельными ссылками
rag_manager = RAGManager(
    config_path="config/embeddings_config.yaml"
)

# Поиск с источниками
enriched_message, sources = rag_manager.enrich_message_with_rag(
    user_message="Как работает система?",
    use_reranking=True
)

# Форматирование кликабельных источников
clickable_sources = rag_manager.format_clickable_sources(
    sources,
    max_sources=5
)
```

### Использование в DeepSeek провайдере

```python
from providers.deepseek_provider import DeepSeekProvider

# DeepSeek автоматически использует кликабельные ссылки
response, sources = await deepseek_provider.generate_response_with_sources(
    user_message="Вопрос пользователя",
    system_prompt="Системный промпт"
)

# response уже содержит кликабельные ссылки в конце
```

## Запуск MCP Filesystem Server

### Режим SSE (по умолчанию)

```bash
python mcp_server/filesystem.py
```

Сервер запускается на `http://localhost:8003` с SSE транспортом.

### Режим stdio

```bash
python mcp_server/filesystem.py --stdio
```

Используется для прямого взаимодействия через stdin/stdout.

### Проверка работы сервера

```bash
# Проверка доступности
curl http://localhost:8003/sse

# Тест инструментов через MCP клиент
python -c "
from mcp_client import MCPClient

config = {
    'type': 'http',
    'url': 'http://localhost:8003/sse'
}

async def test():
    client = MCPClient(config)
    await client.connect()
    tools = await client.list_tools()
    print(tools)
    await client.disconnect()

import asyncio
asyncio.run(test())
"
```

## Формат MCP URI

### Базовый формат

```
mcp://filesystem/{url_encoded_path}#lines={start}-{end}
```

### Компоненты URI

1. **Схема:** `mcp://`
2. **Сервис:** `filesystem`
3. **Путь:** URL-encoded абсолютный путь к файлу
4. **Фрагмент:** Опциональный `#lines={start}-{end}`

### Примеры URI

```
# Простой файл
mcp://filesystem/%2Fpath%2Fto%2Fdocument.txt

# С указанием строк
mcp://filesystem/%2Fpath%2Fto%2Ffile.md#lines=15-25

# С пробелами в имени
mcp://filesystem/%2Fpath%2Fto%2Fmy%20document.txt#lines=1-10
```

## Troubleshooting

### MCP сервер не запускается

**Проблема:**
```
Error: Address already in use
```

**Решение:**
```bash
# Найти процесс на порту 8003
lsof -i :8003

# Завершить процесс
kill -9 <PID>

# Или использовать другой порт
# Отредактировать mcp_server/filesystem.py
mcp.run(transport="sse", port=8004)
```

### Ссылки не работают в Telegram

**Причина:** Telegram не поддерживает нативные mcp:// ссылки

**Решение:**
- MCP ссылки предназначены для клиентов с поддержкой MCP протокола
- В Telegram они отображаются как текст
- Для полной функциональности используйте MCP-совместимые клиенты

### Файл не найден при чтении

**Проблема:**
```
❌ Файл не существует: /path/to/file.md
```

**Решение:**
1. Проверить путь к файлу
2. Убедиться что файл проиндексирован
3. Проверить права доступа
4. Переиндексировать документы

```bash
python manage_index.py index
```

### Некорректные номера строк

**Причина:** Аппроксимация при отсутствии точных метаданных

**Решение:**
Обновить индексатор для сохранения точных номеров строк:

```python
# В DocumentIndexer
metadata = {
    'char_start': start_char,
    'char_end': end_char,
    'line_start': start_line,  # точный номер
    'line_end': end_line        # точный номер
}
```

## Лучшие практики

### 1. Организация документов

```
rag_docs/
├── documentation/
│   ├── architecture.md
│   └── api_reference.md
├── guides/
│   ├── getting_started.md
│   └── advanced_usage.md
└── reference/
    └── commands.txt
```

### 2. Именование файлов

- Используйте понятные, описательные имена
- Избегайте специальных символов
- Используйте snake_case или kebab-case
- Добавляйте расширение файла

### 3. Размер документов

- Оптимальный размер: 1-10 KB
- Максимальный размер: 10 MB
- Разбивайте большие документы на разделы

### 4. Безопасность

- Не индексируйте конфиденциальные документы
- Проверяйте права доступа к файлам
- Используйте валидацию путей
- Ограничивайте доступ к системным директориям

## Будущие улучшения

### Планируемые функции

1. **Поддержка дополнительных форматов**
   - PDF документы
   - DOCX файлы
   - HTML страницы

2. **Улучшенная навигация**
   - Переход к конкретной строке
   - Подсветка синтаксиса
   - Предпросмотр содержимого

3. **Расширенные метаданные**
   - Автор документа
   - Дата последнего изменения
   - Теги и категории

4. **Интеграция с внешними сервисами**
   - GitHub repositories
   - Google Drive
   - Dropbox

---

*Дата создания: 29.11.2025*
*Версия: 1.0*
