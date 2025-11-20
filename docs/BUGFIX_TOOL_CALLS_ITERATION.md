# Исправление обработки множественных tool calls

**Дата:** 2025-11-20
**Статус:** Исправлено ✅

## Описание проблем

### Проблема 1: write_file не вызывается после GitHub tools

DeepSeek вызывал `get_user_info` и `get_user_repositories`, но не вызывал `write_file` для сохранения результата, хотя пользователь явно просил "сохрани в файл".

**Логи:**
```
2025-11-20 13:24:13,262 - providers.deepseek_provider - INFO - Вызов MCP tool: get_user_info
2025-11-20 13:24:13,905 - providers.deepseek_provider - INFO - Вызов MCP tool: get_user_repositories
2025-11-20 13:24:14,459 - providers.deepseek_provider - INFO - Отправка второго запроса с результатами tool calls
```

Отсутствует: `Вызов MCP tool: write_file` ❌

### Проблема 2: Ошибка парсинга ответа

После обработки tool calls DeepSeek возвращал ответ не в JSON формате:

```
2025-11-20 13:24:30,196 - format_manager - WARNING - Применяем fallback парсинг для JSON
2025-11-20 13:24:30,196 - format_manager - ERROR - Не удалось найти все обязательные поля в тексте
2025-11-20 13:24:30,198 - format_manager - WARNING - Применяем fallback парсинг для XML
2025-11-20 13:24:30,198 - format_manager - ERROR - Не удалось найти все обязательные поля в тексте
2025-11-20 13:24:30,199 - format_manager - ERROR - Не удалось распарсить или валидировать ответ
```

## Причина

### Корневая проблема в коде

В файле `providers/deepseek_provider.py` (строки 174-181 старая версия):

```python
# Делаем второй запрос для получения финального ответа
logger.info("Отправка второго запроса с результатами tool calls")
final_response = await self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    temperature=self.temperature,
    max_tokens=self.max_tokens
    # ❌ НЕТ параметра tools
    # ❌ НЕТ параметра tool_choice
)
```

### Последствия отсутствия параметра `tools`

1. **DeepSeek не может вызвать дополнительные инструменты:**
   - После получения данных от GitHub tools DeepSeek не может вызвать `write_file`
   - Модель "видит" результаты инструментов, но не может использовать новые инструменты

2. **DeepSeek возвращает свободный текст вместо JSON:**
   - Без параметра `tools` DeepSeek думает, что это обычный чат (не function calling режим)
   - Игнорирует инструкции из system prompt о JSON формате
   - Возвращает человекочитаемый текст вместо структурированного JSON

3. **Нарушается цепочка (chain) tool calls:**
   - Невозможны пайплайны типа: GitHub → обработка → Filesystem
   - Каждый запрос может вызвать инструменты только один раз

## Решение

### 1. Добавление параметра `tools` во второй запрос

Недостаточно, но первый шаг:

```python
final_response = await self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    temperature=self.temperature,
    max_tokens=self.max_tokens,
    tools=tools,  # ✅ Добавлено
    tool_choice="auto"  # ✅ Добавлено
)
```

### 2. Рефакторинг в цикл обработки tool calls

Проблема: второй запрос может снова вернуть tool calls (например, для `write_file`).

**Решение:** Цикл с максимум 5 итерациями:

```python
# Цикл обработки tool calls (максимум 5 итераций)
max_iterations = 5
iteration = 0

while iteration < max_iterations:
    iteration += 1

    # Отправляем запрос к DeepSeek API
    response = await self.client.chat.completions.create(
        model=self.model,
        messages=messages,
        temperature=self.temperature,
        max_tokens=self.max_tokens,
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message

    # Проверяем есть ли tool calls
    if hasattr(message, 'tool_calls') and message.tool_calls:
        logger.info(f"DeepSeek запросил вызов {len(message.tool_calls)} инструментов (итерация {iteration})")

        # Обрабатываем tool calls
        tool_results = await self._handle_tool_calls(message.tool_calls)

        # Добавляем результаты в историю сообщений
        messages.append(assistant_message_with_tool_calls)
        messages.extend(tool_results_messages)

        # Продолжаем цикл - следующая итерация может вызвать еще инструменты
        continue

    # Если нет tool calls - это финальный ответ
    return message.content
```

### Преимущества нового подхода

1. **✅ Поддержка множественных tool calls:**
   - Итерация 1: `get_user_info`, `get_user_repositories`
   - Итерация 2: `write_file` (использует результаты из итерации 1)
   - Итерация 3: финальный JSON ответ

2. **✅ Корректный формат ответа:**
   - DeepSeek всегда находится в function calling режиме
   - Следует инструкциям о JSON формате из system prompt
   - Парсер format_manager получает валидный JSON

3. **✅ Защита от бесконечного цикла:**
   - Максимум 5 итераций
   - После 5 итераций возвращается сообщение об ошибке

4. **✅ Детальное логирование:**
   - Логируется каждая итерация
   - Видно какие инструменты вызываются на каждом этапе
   - Легко отлаживать пайплайны

## Ожидаемое поведение после исправления

### Сценарий: "Сохрани информацию о GitHub пользователе в файл"

**ДО исправления:**

```
Логи:
- Итерация 1: get_user_info, get_user_repositories ✅
- Отправка второго запроса БЕЗ tools ❌
- DeepSeek возвращает текст вместо JSON ❌
- format_manager не может распарсить ответ ❌
- write_file НЕ вызван ❌

Результат: Ошибка парсинга, файл не создан
```

**ПОСЛЕ исправления:**

```
Логи:
- Итерация 1: get_user_info, get_user_repositories ✅
- Продолжаем обработку с результатами tool calls ✅
- Итерация 2: write_file с данными от GitHub ✅
- Продолжаем обработку с результатами tool calls ✅
- Итерация 3: Финальный JSON ответ ✅

Результат: Файл создан, валидный JSON ответ пользователю
```

## Изменённые файлы

- ✅ `providers/deepseek_provider.py` - рефакторинг метода `generate_response()`:
  - Добавлен цикл обработки tool calls (max 5 итераций)
  - Параметр `tools` передаётся на каждой итерации
  - Улучшено логирование итераций

## Тестирование

### Тест 1: Базовый пайплайн GitHub → Filesystem

```
Пользователь: Сохрани информацию о github пользователе torvalds в файл ~/torvalds_info.txt
```

**Ожидаемые логи:**
```
providers.deepseek_provider - INFO - DeepSeek запросил вызов 2 инструментов (итерация 1)
providers.deepseek_provider - INFO - Вызов MCP tool: get_user_info с аргументами: {'username': 'torvalds'}
providers.deepseek_provider - INFO - Вызов MCP tool: get_user_repositories с аргументами: {'username': 'torvalds'}
providers.deepseek_provider - INFO - Продолжаем обработку с результатами tool calls (итерация 1)
providers.deepseek_provider - INFO - DeepSeek запросил вызов 1 инструментов (итерация 2)
providers.deepseek_provider - INFO - Вызов MCP tool: write_file с аргументами: {'path': '~/torvalds_info.txt', 'content': '...'}
providers.deepseek_provider - INFO - Продолжаем обработку с результатами tool calls (итерация 2)
providers.deepseek_provider - INFO - Получен финальный ответ от DeepSeek API (после 3 итераций)
format_manager - INFO - JSON успешно распарсен напрямую
```

**Проверка:**
```bash
ls -lh ~/torvalds_info.txt
cat ~/torvalds_info.txt
```

### Тест 2: Множественные файловые операции

```
Пользователь: Создай файл ~/test1.txt с текстом "Hello", потом создай ~/test2.txt с текстом "World"
```

**Ожидаемые логи:**
```
providers.deepseek_provider - INFO - DeepSeek запросил вызов 1 инструментов (итерация 1)
providers.deepseek_provider - INFO - Вызов MCP tool: write_file (test1.txt)
providers.deepseek_provider - INFO - Продолжаем обработку с результатами tool calls (итерация 1)
providers.deepseek_provider - INFO - DeepSeek запросил вызов 1 инструментов (итерация 2)
providers.deepseek_provider - INFO - Вызов MCP tool: write_file (test2.txt)
providers.deepseek_provider - INFO - Получен финальный ответ от DeepSeek API (после 3 итераций)
```

### Тест 3: Проверка защиты от бесконечного цикла

Если DeepSeek продолжает вызывать инструменты без остановки:

```
providers.deepseek_provider - WARNING - Достигнуто максимальное количество итераций tool calls (5)
```

## Связанные исправления

- `docs/BUGFIX_FILESYSTEM_HALLUCINATION.md` - обновление system prompt для явных инструкций
- `prompts.py` - добавлены инструкции "ОБЯЗАТЕЛЬНО используй write_file"

## Технические детали

### Почему максимум 5 итераций?

1. **Типичные сценарии требуют 2-3 итерации:**
   - Итерация 1: Получение данных (GitHub, чтение файлов)
   - Итерация 2: Обработка и сохранение (write_file)
   - Итерация 3: Финальный ответ

2. **Защита от ошибок:**
   - Если модель "зацикливается" - предотвращаем бесконечный цикл
   - Экономия API токенов и времени
   - Явное сообщение пользователю о проблеме

3. **Можно увеличить при необходимости:**
   ```python
   max_iterations = 10  # Для сложных пайплайнов
   ```

### Формат сообщений в цикле

Каждая итерация добавляет в `messages`:

1. **Assistant message с tool_calls:**
   ```python
   {
       "role": "assistant",
       "content": null,
       "tool_calls": [
           {"id": "call_123", "function": {"name": "get_user_info", "arguments": "{...}"}}
       ]
   }
   ```

2. **Tool result messages:**
   ```python
   {
       "role": "tool",
       "tool_call_id": "call_123",
       "name": "get_user_info",
       "content": "✅ GitHub User: torvalds..."
   }
   ```

Это стандартный формат OpenAI function calling, который поддерживает DeepSeek.

## Примечания

- Эта проблема возникает только при использовании MCP tools с DeepSeek
- OpenAI и Yandex GPT провайдеры не затронуты (у них своя реализация)
- Исправление совместимо с существующим кодом
- Не требует изменений в MCP серверах или bot.py

---

**Автор:** Claude Code
**Проверено:** Требует тестирования пользователем после перезапуска бота
