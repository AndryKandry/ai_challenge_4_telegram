# Weather MCP Server - Техническая документация

## Описание

Weather MCP Server - это локальный MCP (Model Context Protocol) сервер, предоставляющий инструменты для получения погодной информации из US National Weather Service API.

## Расположение

```
mcp_server/weather.py
```

## Технологический стек

- **FastMCP** - фреймворк для создания MCP серверов
- **httpx** - асинхронный HTTP клиент для запросов к NWS API
- **Python 3.10+** - минимальная версия Python

## Архитектура

Weather MCP Server построен на базе FastMCP и использует stdio транспорт для взаимодействия с клиентами.

```
┌─────────────────┐
│   MCP Client    │
│   (bot.py)      │
└────────┬────────┘
         │ stdio
         │ (stdin/stdout)
         ▼
┌─────────────────┐
│  Weather MCP    │
│  Server         │
│  (weather.py)   │
└────────┬────────┘
         │ HTTP/HTTPS
         ▼
┌─────────────────┐
│  NWS API        │
│  weather.gov    │
└─────────────────┘
```

## Предоставляемые инструменты

### 1. get_alerts

Получение активных погодных предупреждений для штата США.

**Параметры:**
- `state` (str) - Двухбуквенный код штата США (например, "CA", "NY")

**Возвращает:**
- Строка с форматированным списком активных предупреждений
- Включает: событие, зона, серьезность, описание, инструкции

**Пример использования:**
```python
# Получить предупреждения для Калифорнии
alerts = await get_alerts("CA")
```

**Формат ответа:**
```
Event: Heat Advisory
Area: San Francisco Bay Area
Severity: Moderate
Description: Excessive heat warning in effect...
Instructions: Drink plenty of fluids...
---
Event: Wind Advisory
Area: Coastal areas
Severity: Minor
Description: Strong winds expected...
Instructions: Secure loose objects...
```

### 2. get_forecast

Получение прогноза погоды для конкретных географических координат.

**Параметры:**
- `latitude` (float) - Широта локации
- `longitude` (float) - Долгота локации

**Возвращает:**
- Строка с детальным прогнозом на ближайшие 5 периодов
- Включает: температуру, ветер, детальное описание

**Пример использования:**
```python
# Получить прогноз для Сан-Франциско (37.7749, -122.4194)
forecast = await get_forecast(37.7749, -122.4194)
```

**Формат ответа:**
```
Today:
Temperature: 72°F
Wind: 10 mph NW
Forecast: Partly cloudy skies. High near 72F. Winds NW at 5 to 10 mph.
---
Tonight:
Temperature: 55°F
Wind: 5 mph W
Forecast: Clear skies. Low 55F. Winds W at 5 mph.
---
...
```

## API интерфейс

### Инициализация сервера

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather")
```

### Вспомогательные функции

#### make_nws_request

Выполнение HTTP запроса к NWS API с обработкой ошибок.

```python
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """
    Args:
        url: URL для запроса к NWS API

    Returns:
        JSON ответ от API или None в случае ошибки
    """
```

**Особенности:**
- Автоматическая установка User-Agent заголовка
- Timeout 30 секунд
- Graceful обработка ошибок (возврат None)

#### format_alert

Форматирование объекта предупреждения в читаемую строку.

```python
def format_alert(feature: dict) -> str:
    """
    Args:
        feature: Объект предупреждения из NWS API

    Returns:
        Форматированная строка с информацией о предупреждении
    """
```

## Запуск сервера

### Standalone режим

```bash
python mcp_server/weather.py
```

Сервер запускается в stdio режиме и ожидает MCP команды через stdin.

### Через MCP Client

```python
from mcp_client import MCPClient, get_weather_mcp_config

# Получение конфигурации
config = get_weather_mcp_config()

# Создание клиента
async with MCPClient(config) as client:
    # Получение списка инструментов
    tools = await client.list_tools()
```

## Конфигурация

### Переменные окружения

Weather MCP Server не требует специальных переменных окружения.

### Константы

```python
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"
```

## Зависимости

```
fastmcp>=0.3.0
httpx>=0.27.0
mcp>=1.21.0
```

## Обработка ошибок

### Сетевые ошибки

При ошибке запроса к NWS API функция `make_nws_request` возвращает `None`:
- Timeout (> 30 секунд)
- HTTP ошибки (4xx, 5xx)
- Ошибки парсинга JSON

### Обработка в инструментах

- **get_alerts**: Возвращает сообщение "Unable to fetch alerts or no alerts found."
- **get_forecast**: Возвращает "Unable to fetch forecast data for this location."

## Ограничения

1. **Географические ограничения**: Работает только с US National Weather Service
   - Предупреждения доступны только для штатов США
   - Прогноз доступен только для координат на территории США

2. **Лимиты API**: NWS API имеет rate limiting, но конкретные лимиты не документированы

3. **Timeout**: Каждый запрос имеет timeout 30 секунд

## Примеры интеграции

### Пример 1: Получение списка инструментов

```python
from mcp_client import MCPClient, get_weather_mcp_config

async def list_weather_tools():
    config = get_weather_mcp_config()
    client = MCPClient(config)

    await client.connect()
    tools = await client.list_tools()
    await client.disconnect()

    for tool in tools:
        print(f"{tool['name']}: {tool['description']}")
```

### Пример 2: Использование в Telegram боте

См. `bot.py:mcp_tools_command()` (строки 903-1007)

## Troubleshooting

### Проблема: "Unable to fetch alerts"

**Возможные причины:**
- Неправильный код штата (должен быть двухбуквенный, например "CA")
- Проблемы с интернет-соединением
- NWS API недоступен

**Решение:**
- Проверить код штата
- Проверить доступность https://api.weather.gov
- Проверить логи на наличие ошибок HTTP

### Проблема: "Unable to fetch forecast"

**Возможные причины:**
- Координаты вне территории США
- NWS API не имеет данных для этих координат
- Проблемы с сетью

**Решение:**
- Убедиться что координаты находятся на территории США
- Попробовать другие координаты
- Проверить логи сервера

### Проблема: Сервер не запускается

**Возможные причины:**
- Отсутствуют зависимости (fastmcp, httpx)
- Неправильная версия Python (< 3.10)

**Решение:**
```bash
pip install -r requirements.txt
python --version  # Должен быть 3.10+
```

## Ссылки

- [US National Weather Service API](https://www.weather.gov/documentation/services-web-api)
- [FastMCP Documentation](https://github.com/anthropics/fastmcp)
- [Model Context Protocol](https://modelcontextprotocol.io)
