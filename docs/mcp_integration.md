# MCP Integration - Техническая документация

## Оглавление
- [Что такое MCP](#что-такое-mcp)
- [Архитектура интеграции](#архитектура-интеграции)
- [MCP Client](#mcp-client)
- [Weather MCP Server](#weather-mcp-server)
- [Протокол взаимодействия](#протокол-взаимодействия)
- [Использование в Telegram боте](#использование-в-telegram-боте)
- [Установка и настройка](#установка-и-настройка)
- [Примеры использования](#примеры-использования)
- [Troubleshooting](#troubleshooting)

---

## Что такое MCP

**Model Context Protocol (MCP)** — это открытый протокол, разработанный Anthropic для стандартизации взаимодействия между LLM-приложениями и внешними инструментами.

MCP позволяет:
- Подключать AI-агентов к внешним источникам данных
- Использовать готовые инструменты через унифицированный интерфейс
- Расширять возможности LLM без изменения основного кода
- Масштабировать систему за счет подключения новых MCP-серверов

**Официальная документация**: [https://modelcontextprotocol.io](https://modelcontextprotocol.io)

---

## Архитектура интеграции

### Общая схема

```
┌──────────────────┐
│  Telegram Bot    │
│  (bot.py)        │
└────────┬─────────┘
         │
         │ /mcp_tools команда
         │
         ▼
┌──────────────────┐
│   MCP Client     │
│  (mcp_client.py) │
└────────┬─────────┘
         │
         │ stdio транспорт
         │ (stdin/stdout)
         │
         ▼
┌──────────────────┐
│  Weather MCP     │
│  Server          │
│  (weather.py)    │
└────────┬─────────┘
         │
         │ HTTP API
         │
         ▼
┌──────────────────┐
│  NWS API         │
│  weather.gov     │
└──────────────────┘
```

### Компоненты системы

1. **Telegram Bot** (`bot.py`)
   - Основное приложение
   - Обрабатывает команду `/mcp_tools`
   - Отображает список инструментов пользователю

2. **MCP Client** (`mcp_client.py`)
   - Универсальный клиент для работы с MCP серверами
   - Поддерживает stdio и HTTP транспорты
   - Управляет жизненным циклом соединения

3. **Weather MCP Server** (`mcp_server/weather.py`)
   - Локальный MCP сервер на базе FastMCP
   - Предоставляет инструменты для получения погоды
   - Использует US National Weather Service API

---

## MCP Client

### Класс MCPClient

Универсальный клиент для работы с MCP-серверами.

```python
class MCPClient:
    def __init__(self, server_config: Dict[str, Any])
    async def connect() -> bool
    async def disconnect() -> None
    async def list_tools() -> List[Dict[str, Any]]
    async def get_tool_info(tool_name: str) -> Optional[Dict[str, Any]]
    def is_connected() -> bool
```

### Поддерживаемые транспорты

#### 1. stdio транспорт

Запуск MCP сервера как отдельного процесса с коммуникацией через stdin/stdout.

**Конфигурация:**
```python
{
    "type": "stdio",
    "command": "python",  # Команда для запуска
    "args": ["path/to/server.py"],  # Аргументы
    "env": {}  # Переменные окружения
}
```

**Использование:**
- Локальные MCP серверы
- Python-based серверы
- Node.js серверы (через npx)

#### 2. HTTP (SSE) транспорт

Подключение к удаленному MCP серверу через HTTP Server-Sent Events.

**Конфигурация:**
```python
{
    "type": "http",
    "url": "https://example.com/mcp",
    "headers": {
        "Authorization": "Bearer token"
    }
}
```

**Использование:**
- Удаленные MCP серверы
- Cloud-based сервисы
- Корпоративные API

### Методы клиента

#### connect()

Установка соединения с MCP-сервером.

```python
async def connect(self) -> bool:
    """
    Returns:
        True если подключение успешно, False в случае ошибки
    """
```

**Процесс подключения:**
1. Создание контекстного менеджера (stdio_client или sse_client)
2. Получение read/write потоков
3. Создание ClientSession
4. Инициализация сессии через MCP handshake

#### list_tools()

Получение списка доступных инструментов.

```python
async def list_tools(self) -> List[Dict[str, Any]]:
    """
    Returns:
        Список словарей с информацией об инструментах:
        - name: название инструмента
        - description: описание
        - inputSchema: схема входных параметров (JSON Schema)
    """
```

**Пример ответа:**
```python
[
    {
        "name": "get_alerts",
        "description": "Get weather alerts for a US state",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "Two-letter US state code"
                }
            },
            "required": ["state"]
        }
    }
]
```

#### disconnect()

Закрытие соединения с MCP-сервером.

```python
async def disconnect(self) -> None:
    """Корректное закрытие всех ресурсов"""
```

**Действия:**
1. Закрытие MCP сессии
2. Выход из контекстного менеджера
3. Очистка ресурсов

### Контекстный менеджер

MCPClient поддерживает использование с async with:

```python
async with MCPClient(config) as client:
    tools = await client.list_tools()
    # Автоматическое закрытие при выходе из блока
```

---

## Weather MCP Server

### Конфигурация для Weather MCP

Функция `get_weather_mcp_config()` возвращает конфигурацию для подключения к локальному Weather серверу:

```python
def get_weather_mcp_config() -> Dict[str, Any]:
    """
    Returns:
        {
            "type": "stdio",
            "command": "/path/to/python",
            "args": ["/path/to/mcp_server/weather.py"],
            "env": {}
        }
    """
```

**Особенности:**
- Автоматическое определение пути к weather.py
- Использование текущего Python интерпретатора (sys.executable)
- Не требует дополнительных переменных окружения

### Доступные инструменты

См. детальную документацию в [weather_mcp_server.md](weather_mcp_server.md)

1. **get_alerts(state: str)** - Погодные предупреждения для штата
2. **get_forecast(latitude: float, longitude: float)** - Прогноз погоды для координат

---

## Протокол взаимодействия

### Последовательность подключения

```
Client                          Server
  │                               │
  ├──── stdio process start ────▶│
  │                               │
  ├──── initialize request ─────▶│
  │◀──── initialize response ────┤
  │                               │
  ├──── initialized notification▶│
  │                               │
  │         [Ready]               │
  │                               │
  ├──── list_tools request ─────▶│
  │◀──── tools response ──────────┤
  │                               │
```

### Формат данных

#### Запрос списка инструментов

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
```

#### Ответ со списком инструментов

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "get_alerts",
        "description": "Get weather alerts for a US state",
        "inputSchema": {
          "type": "object",
          "properties": {
            "state": {"type": "string"}
          },
          "required": ["state"]
        }
      }
    ]
  }
}
```

---

## Использование в Telegram боте

### Команда /mcp_tools

Реализована в `bot.py` (метод `mcp_tools_command`, строки 903-1007).

**Алгоритм работы:**

1. Получение конфигурации Weather MCP
```python
mcp_config = get_weather_mcp_config()
```

2. Создание MCP клиента
```python
mcp_client = MCPClient(mcp_config)
```

3. Подключение к серверу
```python
connected = await mcp_client.connect()
```

4. Получение списка инструментов
```python
tools = await mcp_client.list_tools()
```

5. Форматирование и отправка ответа пользователю
```python
response = "🛠 Доступные MCP инструменты:\n\n"
for idx, tool in enumerate(tools, 1):
    response += f"{idx}. {tool['name']}\n"
    response += f"   📝 {tool['description']}\n"
    # ... параметры ...
```

6. Закрытие соединения
```python
await mcp_client.disconnect()
```

### Обработка ошибок

- **Ошибка подключения**: Сообщение с возможными причинами
- **Пустой список**: Уведомление пользователя
- **ImportError**: Инструкция по установке библиотеки
- **Общие ошибки**: Логирование + сообщение пользователю

---

## Установка и настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

Необходимые пакеты:
- `mcp>=1.21.0` - MCP SDK
- `fastmcp>=0.3.0` - FastMCP для Weather сервера
- `httpx>=0.27.0` - HTTP клиент

### 2. Проверка структуры проекта

```
project/
├── bot.py                 # Telegram бот
├── mcp_client.py          # MCP клиент
├── mcp_server/
│   └── weather.py         # Weather MCP сервер
├── requirements.txt
└── docs/
    ├── mcp_integration.md
    └── weather_mcp_server.md
```

### 3. Настройка переменных окружения

Для Weather MCP дополнительные переменные окружения не требуются.

Базовые переменные для бота (в `.env`):
```bash
TELEGRAM_TOKEN=your_token
YANDEX_API_KEY=your_api_key
YANDEX_FOLDER_ID=your_folder_id
```

---

## Примеры использования

### Пример 1: Базовое использование

```python
from mcp_client import MCPClient, get_weather_mcp_config

async def get_weather_tools():
    # Получение конфигурации
    config = get_weather_mcp_config()

    # Создание и подключение клиента
    client = MCPClient(config)
    await client.connect()

    try:
        # Получение списка инструментов
        tools = await client.list_tools()

        # Вывод информации
        for tool in tools:
            print(f"Tool: {tool['name']}")
            print(f"Description: {tool['description']}")
            print()

    finally:
        # Закрытие соединения
        await client.disconnect()
```

### Пример 2: Использование с контекстным менеджером

```python
from mcp_client import MCPClient, get_weather_mcp_config

async def list_weather_tools():
    config = get_weather_mcp_config()

    # Автоматическое управление соединением
    async with MCPClient(config) as client:
        tools = await client.list_tools()

        for tool in tools:
            print(f"- {tool['name']}: {tool['description']}")
```

### Пример 3: Получение детальной информации об инструменте

```python
async def get_tool_details(tool_name: str):
    config = get_weather_mcp_config()

    async with MCPClient(config) as client:
        tool_info = await client.get_tool_info(tool_name)

        if tool_info:
            print(f"Name: {tool_info['name']}")
            print(f"Description: {tool_info['description']}")
            print(f"Input Schema:")
            print(json.dumps(tool_info['inputSchema'], indent=2))
        else:
            print(f"Tool '{tool_name}' not found")
```

---

## Troubleshooting

### Проблема: "MCP библиотека не установлена"

**Ошибка:**
```
ImportError: cannot import name 'ClientSession' from 'mcp'
```

**Решение:**
```bash
pip install mcp>=1.21.0
```

### Проблема: "Ошибка подключения к MCP-серверу"

**Возможные причины:**
1. Файл `mcp_server/weather.py` не найден
2. Отсутствуют зависимости для Weather сервера
3. Ошибка при запуске Python процесса

**Решение:**
```bash
# Проверить наличие файла
ls mcp_server/weather.py

# Установить зависимости
pip install fastmcp httpx

# Проверить запуск сервера вручную
python mcp_server/weather.py
```

### Проблема: "Timeout при инициализации сессии"

**Возможные причины:**
- Сервер долго запускается
- Ошибка в коде сервера
- Проблемы с зависимостями

**Решение:**
1. Проверить логи сервера
2. Запустить сервер в отладочном режиме
3. Увеличить timeout в конфигурации

### Проблема: "Список инструментов пуст"

**Возможные причины:**
- Сервер запустился, но не зарегистрировал инструменты
- Ошибка в коде сервера
- Несовместимая версия MCP

**Решение:**
1. Проверить код weather.py на наличие `@mcp.tool()` декораторов
2. Обновить версии библиотек
3. Проверить логи на наличие ошибок

### Проблема: Бот не отвечает на /mcp_tools

**Возможные причины:**
- Команда не зарегистрирована в боте
- Ошибка при обработке команды
- Проблемы с Telegram API

**Решение:**
1. Проверить регистрацию команды в `bot.py`
2. Проверить логи бота на наличие ошибок
3. Протестировать команду в прямом сообщении боту

---

## Расширение функциональности

### Добавление нового MCP сервера

1. Создать новый файл в `mcp_server/`
2. Реализовать сервер на базе FastMCP
3. Добавить функцию конфигурации в `mcp_client.py`
4. Обновить команду `/mcp_tools` для выбора сервера

### Добавление новых инструментов в Weather сервер

```python
@mcp.tool()
async def new_tool(param: str) -> str:
    """
    Описание нового инструмента.

    Args:
        param: Описание параметра
    """
    # Реализация
    return result
```

---

## Ссылки

- [Model Context Protocol](https://modelcontextprotocol.io)
- [FastMCP Documentation](https://github.com/anthropics/fastmcp)
- [MCP Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Weather MCP Server Documentation](weather_mcp_server.md)
