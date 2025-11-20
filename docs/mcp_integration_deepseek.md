# MCP Integration with DeepSeek - Техническая документация

## Обзор

Данная документация описывает интеграцию Model Context Protocol (MCP) серверов с DeepSeek API через механизм Function Calling. DeepSeek использует OpenAI-совместимый API, что позволяет использовать стандартный формат инструментов (tools) для вызова MCP функций.

## Архитектура интеграции

### Компоненты системы

```
┌─────────────────┐
│  Telegram Bot   │
└────────┬────────┘
         │
         v
┌─────────────────────────┐
│  DeepSeekProvider       │
│  - mcp_clients: List    │
│  - generate_response()  │
│  - _handle_tool_calls() │
└────────┬────────────────┘
         │
         v
    ┌────────────────┐
    │  MCP Clients   │
    ├────────────────┤
    │ - GitHub       │
    │ - Filesystem   │
    │ - Other...     │
    └────────┬───────┘
             │
             v
       ┌──────────────┐
       │ MCP Servers  │
       │ (SSE/HTTP)   │
       └──────────────┘
```

### Поток данных

1. **Пользователь** отправляет запрос боту в Telegram
2. **Telegram Bot** передает запрос в **DeepSeekProvider**
3. **DeepSeekProvider** формирует список доступных tools из всех MCP клиентов
4. **DeepSeek API** анализирует запрос и решает, какие tools вызвать
5. **DeepSeekProvider** выполняет tool calls через соответствующие MCP клиенты
6. **MCP Clients** отправляют запросы к MCP серверам
7. **MCP Servers** выполняют операции и возвращают результаты
8. **DeepSeekProvider** передает результаты обратно в DeepSeek API
9. **DeepSeek API** генерирует финальный ответ пользователю
10. **Telegram Bot** отправляет ответ пользователю

---

## DeepSeekProvider: Интеграция MCP

### Инициализация

```python
from providers import DeepSeekProvider
from mcp_client import MCPClient, get_github_mcp_config, get_filesystem_mcp_config

# Создание MCP клиентов
github_client = MCPClient(get_github_mcp_config())
filesystem_client = MCPClient(get_filesystem_mcp_config())

# Подключение к MCP серверам
await github_client.connect()
await filesystem_client.connect()

# Инициализация DeepSeek с первым MCP клиентом (обратная совместимость)
provider = DeepSeekProvider(
    api_key="your_deepseek_api_key",
    mcp_client=github_client
)

# Добавление дополнительных MCP клиентов
provider.add_mcp_client(filesystem_client)
```

### Множественные MCP клиенты

`DeepSeekProvider` поддерживает работу с несколькими MCP клиентами одновременно:

```python
class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str, ..., mcp_client: Optional[Any] = None):
        # Список всех MCP клиентов
        self.mcp_clients = []
        if mcp_client:
            self.mcp_clients.append(mcp_client)

    def add_mcp_client(self, mcp_client: Any) -> None:
        """Добавление нового MCP клиента к списку."""
        if mcp_client and mcp_client not in self.mcp_clients:
            self.mcp_clients.append(mcp_client)
```

**Преимущества**:
- Один запрос может использовать инструменты из разных MCP серверов
- DeepSeek автоматически выбирает нужные инструменты
- Простое добавление новых MCP серверов без изменения кода

---

## Function Calling: Формат инструментов

### Получение списка tools

Метод `_get_mcp_tools_definitions()` собирает все инструменты от всех MCP клиентов и конвертирует их в формат OpenAI tools:

```python
async def _get_mcp_tools_definitions(self) -> List[Dict[str, Any]]:
    """Получение определений MCP tools в формате OpenAI function calling."""
    tools_definitions = []

    for mcp_client in self.mcp_clients:
        if mcp_client and mcp_client.is_connected():
            # Получаем список tools от MCP сервера
            mcp_tools = await mcp_client.list_tools()

            # Конвертируем в формат OpenAI tools
            for tool in mcp_tools:
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool.get("inputSchema", {})
                    }
                }
                tools_definitions.append(tool_def)

    return tools_definitions
```

### Формат инструмента

Каждый MCP инструмент преобразуется в следующий формат:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Чтение содержимого файла...",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Путь к файлу"
        },
        "encoding": {
          "type": "string",
          "description": "Кодировка файла",
          "default": "utf-8"
        }
      },
      "required": ["path"]
    }
  }
}
```

---

## Обработка Tool Calls

### Запрос к DeepSeek с tools

```python
async def generate_response(self, user_message: str, ...):
    # Формируем сообщения
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    # Получаем список доступных tools
    tools = await self._get_mcp_tools_definitions()

    # Отправляем запрос с tools
    response = await self.client.chat.completions.create(
        model=self.model,
        messages=messages,
        temperature=self.temperature,
        max_tokens=self.max_tokens,
        tools=tools,
        tool_choice="auto"  # DeepSeek решает, когда использовать tools
    )
```

### Обработка вызовов инструментов

Когда DeepSeek возвращает tool calls, они обрабатываются методом `_handle_tool_calls()`:

```python
async def _handle_tool_calls(self, tool_calls: List[Any]) -> List[tuple]:
    """Обработка вызовов tools от DeepSeek."""
    results = []

    for tool_call in tool_calls:
        tool_call_id = tool_call.id
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        # Ищем MCP клиент, который имеет данный tool
        for mcp_client in self.mcp_clients:
            if mcp_client and mcp_client.is_connected():
                client_tools = await mcp_client.list_tools()
                tool_names = [t["name"] for t in client_tools]

                if tool_name in tool_names:
                    # Вызываем tool через этот MCP клиент
                    result = await mcp_client.call_tool(tool_name, tool_args)
                    results.append((tool_call_id, tool_name, result))
                    break

    return results
```

### Формирование финального ответа

После выполнения tool calls, результаты передаются обратно в DeepSeek для генерации финального ответа:

```python
# Добавляем assistant message с tool calls в историю
messages.append({
    "role": "assistant",
    "content": message.content,
    "tool_calls": [...]
})

# Добавляем результаты выполнения tools
for tool_call_id, tool_name, result in tool_results:
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": tool_name,
        "content": result
    })

# Делаем второй запрос для получения финального ответа
final_response = await self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    temperature=self.temperature,
    max_tokens=self.max_tokens
)
```

---

## Примеры использования

### Пример 1: Простой вызов filesystem инструмента

**Запрос пользователя**:
```
Прочитай файл ~/Documents/notes.txt
```

**Поток выполнения**:

1. DeepSeek получает запрос с доступными tools
2. DeepSeek анализирует запрос и решает вызвать `read_file`
3. DeepSeek возвращает tool_call:
   ```json
   {
     "id": "call_abc123",
     "type": "function",
     "function": {
       "name": "read_file",
       "arguments": "{\"path\": \"~/Documents/notes.txt\"}"
     }
   }
   ```
4. `DeepSeekProvider` выполняет вызов через Filesystem MCP клиент
5. Filesystem MCP сервер читает файл и возвращает содержимое
6. Результат передается обратно в DeepSeek
7. DeepSeek генерирует финальный ответ пользователю с содержимым файла

**Логи**:
```
INFO:providers.deepseek_provider - DeepSeek запросил вызов 1 инструментов
INFO:providers.deepseek_provider - Вызов MCP tool: read_file с аргументами: {'path': '~/Documents/notes.txt'}
INFO:providers.deepseek_provider - Tool read_file выполнен успешно через MCP клиент
INFO:providers.deepseek_provider - Получен финальный ответ от DeepSeek после tool calls
```

### Пример 2: Связка github + filesystem (pipeline)

**Запрос пользователя**:
```
Получи информацию о пользователе GitHub torvalds и сохрани в файл ~/torvalds_info.txt
```

**Поток выполнения**:

1. DeepSeek получает запрос со всеми доступными tools (GitHub + Filesystem)
2. DeepSeek анализирует и решает вызвать 2 инструмента последовательно
3. **Первый tool call** - получение информации о пользователе:
   ```json
   {
     "id": "call_123",
     "function": {
       "name": "get_user_info",
       "arguments": "{\"username\": \"torvalds\"}"
     }
   }
   ```
4. GitHub MCP клиент выполняет запрос к GitHub API
5. Результат возвращается DeepSeek
6. DeepSeek анализирует результат и делает **второй запрос с новым tool call**:
   ```json
   {
     "id": "call_456",
     "function": {
       "name": "write_file",
       "arguments": "{\"path\": \"~/torvalds_info.txt\", \"content\": \"GitHub User: torvalds\\nName: Linus Torvalds\\n...\"}"
     }
   }
   ```
7. Filesystem MCP клиент создает файл с информацией
8. Результат возвращается DeepSeek
9. DeepSeek генерирует финальный ответ: "Информация о пользователе torvalds получена и сохранена в файл ~/torvalds_info.txt"

**Важно**: DeepSeek может делать **множественные раунды tool calls**, если задача требует нескольких шагов.

### Пример 3: Параллельные tool calls

**Запрос пользователя**:
```
Получи информацию о пользователе torvalds и список его репозиториев
```

**Поток выполнения**:

1. DeepSeek получает запрос
2. DeepSeek решает вызвать **2 инструмента параллельно**:
   ```json
   [
     {
       "id": "call_111",
       "function": {
         "name": "get_user_info",
         "arguments": "{\"username\": \"torvalds\"}"
       }
     },
     {
       "id": "call_222",
       "function": {
         "name": "get_user_repositories",
         "arguments": "{\"username\": \"torvalds\"}"
       }
     }
   ]
   ```
3. Оба tool calls выполняются через GitHub MCP клиент
4. Результаты возвращаются DeepSeek
5. DeepSeek объединяет информацию и генерирует финальный ответ

---

## Конфигурация в bot.py

### Инициализация MCP клиентов

```python
class TelegramBot:
    def __init__(self, ...):
        # Инициализация DeepSeek с MCP клиентами
        self.deepseek_provider = None
        self.github_mcp_client = None
        self.filesystem_mcp_client = None

        if deepseek_api_key:
            # Создаём MCP клиент для GitHub
            try:
                github_config = get_github_mcp_config()
                self.github_mcp_client = MCPClient(github_config)
            except Exception as e:
                logger.warning(f"Не удалось создать GitHub MCP клиент: {e}")

            # Создаём MCP клиент для Filesystem
            try:
                filesystem_config = get_filesystem_mcp_config()
                self.filesystem_mcp_client = MCPClient(filesystem_config)
            except Exception as e:
                logger.warning(f"Не удалось создать Filesystem MCP клиент: {e}")

            # Создаём DeepSeek провайдер
            self.deepseek_provider = DeepSeekProvider(
                deepseek_api_key,
                mcp_client=self.github_mcp_client
            )

            # Добавляем Filesystem MCP клиент
            if self.filesystem_mcp_client:
                self.deepseek_provider.add_mcp_client(self.filesystem_mcp_client)
```

### Подключение при запуске

```python
async def _startup(self, application: Application) -> None:
    """Асинхронная инициализация при запуске бота."""

    # Подключение к GitHub MCP
    if self.github_mcp_client:
        connected = await self.github_mcp_client.connect()
        if connected:
            tools = await self.github_mcp_client.list_tools()
            logger.info(f"Доступно {len(tools)} GitHub MCP tools")

    # Подключение к Filesystem MCP
    if self.filesystem_mcp_client:
        connected = await self.filesystem_mcp_client.connect()
        if connected:
            tools = await self.filesystem_mcp_client.list_tools()
            logger.info(f"Доступно {len(tools)} Filesystem MCP tools")
```

### Отключение при shutdown

```python
async def _shutdown(self, application: Application) -> None:
    """Асинхронное завершение при остановке бота."""

    # Отключение от GitHub MCP
    if self.github_mcp_client and self.github_mcp_client.is_connected():
        await self.github_mcp_client.disconnect()

    # Отключение от Filesystem MCP
    if self.filesystem_mcp_client and self.filesystem_mcp_client.is_connected():
        await self.filesystem_mcp_client.disconnect()
```

---

## Обработка ошибок

### Ошибки подключения к MCP серверу

```python
try:
    connected = await mcp_client.connect()
    if not connected:
        logger.warning("Не удалось подключиться к MCP серверу")
        # DeepSeek будет работать без этих tools
except Exception as e:
    logger.error(f"Ошибка при подключении к MCP серверу: {e}")
```

### Ошибки выполнения tool calls

```python
try:
    result = await mcp_client.call_tool(tool_name, tool_args)
    if result:
        results.append((tool_call_id, tool_name, result))
    else:
        error_msg = f"Tool {tool_name} не вернул результат"
        results.append((tool_call_id, tool_name, f"❌ {error_msg}"))
except Exception as e:
    error_msg = f"Ошибка выполнения tool {tool_name}: {e}"
    results.append((tool_call_id, tool_name, f"❌ {error_msg}"))
```

DeepSeek получит сообщение об ошибке и сможет сообщить пользователю о проблеме.

---

## Best Practices

### 1. Запуск MCP серверов перед ботом

Убедитесь, что все MCP серверы запущены:

```bash
# Терминал 1: GitHub MCP
python mcp_server/github.py

# Терминал 2: Filesystem MCP
python mcp_server/filesystem.py

# Терминал 3: Telegram Bot
python bot.py
```

### 2. Логирование

Включайте подробное логирование для отладки:

```python
logging.basicConfig(level=logging.INFO)
# или для детальной отладки:
logging.basicConfig(level=logging.DEBUG)
```

### 3. Graceful degradation

Если MCP сервер недоступен, бот продолжает работать без этих tools:

```python
if deepseek_api_key:
    try:
        github_client = MCPClient(get_github_mcp_config())
    except Exception as e:
        logger.warning(f"GitHub MCP недоступен: {e}. DeepSeek будет работать без GitHub tools.")
        github_client = None
```

### 4. Timeout настройки

Настройте адекватные таймауты для MCP операций:

```python
# В mcp_client.py
REQUEST_TIMEOUT = 30.0  # секунды

# В DeepSeekProvider
self.client = AsyncOpenAI(
    api_key=api_key,
    base_url=DEEPSEEK_API_URL,
    timeout=60  # увеличенный таймаут для tool calls
)
```

### 5. Мониторинг доступных tools

Периодически проверяйте список доступных tools:

```python
tools = await self.deepseek_provider._get_mcp_tools_definitions()
logger.info(f"Всего доступно {len(tools)} инструментов для DeepSeek")
for tool in tools:
    logger.debug(f"- {tool['function']['name']}")
```

---

## Расширение: Добавление новых MCP серверов

### Шаг 1: Создать конфигурацию в mcp_client.py

```python
def get_weather_mcp_config() -> Dict[str, Any]:
    return {
        "type": "http",
        "url": "http://localhost:8004/sse",
        "headers": {}
    }
```

### Шаг 2: Создать MCP клиент в bot.py

```python
self.weather_mcp_client = None
try:
    weather_config = get_weather_mcp_config()
    self.weather_mcp_client = MCPClient(weather_config)
except Exception as e:
    logger.warning(f"Weather MCP недоступен: {e}")
```

### Шаг 3: Добавить к DeepSeek провайдеру

```python
if self.weather_mcp_client:
    self.deepseek_provider.add_mcp_client(self.weather_mcp_client)
```

### Шаг 4: Подключить при startup

```python
if self.weather_mcp_client:
    await self.weather_mcp_client.connect()
```

### Шаг 5: Отключить при shutdown

```python
if self.weather_mcp_client and self.weather_mcp_client.is_connected():
    await self.weather_mcp_client.disconnect()
```

---

## Troubleshooting

### DeepSeek не вызывает tools

**Возможные причины**:
1. Tools не загружены (проверьте логи: "Доступно X инструментов")
2. Запрос слишком неоднозначный (уточните формулировку)
3. Temperature слишком высокая (попробуйте снизить до 0.5-0.7)

**Решение**:
```python
# Проверить список tools
tools = await provider._get_mcp_tools_definitions()
print(f"Tools count: {len(tools)}")

# Снизить temperature
provider.temperature = 0.7
```

### Tool calls возвращают ошибки

**Проверьте**:
1. MCP сервер запущен и доступен
2. Аргументы tool call корректны
3. Логи MCP сервера на наличие ошибок

**Debugging**:
```python
# Включить DEBUG логирование
logging.getLogger('providers.deepseek_provider').setLevel(logging.DEBUG)
logging.getLogger('mcp_client').setLevel(logging.DEBUG)
```

### MCP сервер не отвечает

**Проверьте**:
1. Сервер запущен: `ps aux | grep "mcp_server"`
2. Порт доступен: `curl http://localhost:8003/sse`
3. Firewall не блокирует порт

---

## Производительность

### Оптимизация количества tool calls

DeepSeek автоматически оптимизирует количество вызовов, но вы можете помочь:

1. **Четкие инструкции**: "Получи информацию о пользователе и сохрани в файл" (2 tool calls)
2. **Избегайте избыточности**: Не запрашивайте одни и те же данные дважды

### Кэширование результатов

Для часто запрашиваемых данных можно добавить кэширование на уровне MCP клиента:

```python
# В будущей версии
class CachedMCPClient(MCPClient):
    def __init__(self, config, cache_ttl=300):
        super().__init__(config)
        self.cache = {}
        self.cache_ttl = cache_ttl
```

---

## Заключение

Интеграция MCP с DeepSeek обеспечивает:
- ✅ Автоматический выбор нужных инструментов
- ✅ Поддержку множественных MCP серверов
- ✅ Последовательные и параллельные tool calls
- ✅ Graceful degradation при недоступности серверов
- ✅ Подробное логирование для отладки
- ✅ Легкое расширение новыми MCP серверами

DeepSeek работает как "оркестратор", автоматически создавая пайплайны из доступных MCP инструментов для решения задач пользователя.
