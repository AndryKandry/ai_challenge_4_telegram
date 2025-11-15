# API документация MemoryManager

## Содержание
- [Инициализация](#инициализация)
- [Работа с сообщениями](#работа-с-сообщениями)
- [Промежуточные результаты](#промежуточные-результаты)
- [Действия агента](#действия-агента)
- [База знаний](#база-знаний)
- [Управление сессиями](#управление-сессиями)
- [Служебные методы](#служебные-методы)

---

## Инициализация

### `__init__(db_path: str = "agent_memory.db")`

Создает экземпляр менеджера памяти.

**Параметры:**
- `db_path` (str): Путь к файлу базы данных SQLite

**Пример:**
```python
from database import MemoryManager

memory = MemoryManager("agent_memory.db")
memory.create_tables()
```

### `create_tables() -> None`

Создает структуру таблиц в базе данных.

**Исключения:**
- `FileNotFoundError`: Если schema.sql не найден
- `Exception`: При ошибках выполнения SQL

---

## Работа с сообщениями

### `save_message(user_id, chat_id, message, message_type, session_id=None) -> int`

Сохраняет сообщение в историю диалога.

**Параметры:**
- `user_id` (int): ID пользователя Telegram
- `chat_id` (int): ID чата Telegram
- `message` (str): Текст сообщения
- `message_type` (str): 'user' или 'assistant'
- `session_id` (str, optional): ID сессии

**Возвращает:**
- int: ID созданной записи

**Пример:**
```python
msg_id = memory.save_message(
    user_id=12345,
    chat_id=67890,
    message="Привет, бот!",
    message_type="user",
    session_id="uuid-here"
)
```

### `get_conversation_history(user_id, chat_id, limit=10, session_id=None) -> List[Dict]`

Получает историю диалога.

**Параметры:**
- `user_id` (int): ID пользователя
- `chat_id` (int): ID чата
- `limit` (int): Максимальное количество сообщений (по умолчанию 10)
- `session_id` (str, optional): Фильтр по сессии

**Возвращает:**
- List[Dict]: Список сообщений от старых к новым

**Пример:**
```python
history = memory.get_conversation_history(12345, 67890, limit=5)
for msg in history:
    print(f"{msg['message_type']}: {msg['message_text']}")
```

---

## Промежуточные результаты

### `save_intermediate_result(user_id, chat_id, task_name, result_data, status='pending') -> int`

Сохраняет промежуточный результат работы агента.

**Параметры:**
- `user_id` (int): ID пользователя
- `chat_id` (int): ID чата
- `task_name` (str): Название задачи
- `result_data` (Any): Данные результата (сериализуются в JSON)
- `status` (str): 'pending', 'completed' или 'failed'

**Возвращает:**
- int: ID созданной записи

**Пример:**
```python
result_id = memory.save_intermediate_result(
    user_id=12345,
    chat_id=67890,
    task_name="parsing_task",
    result_data={"parsed_items": 42, "errors": []},
    status="completed"
)
```

### `get_intermediate_results(user_id, chat_id, task_name=None, status=None) -> List[Dict]`

Получает промежуточные результаты.

**Параметры:**
- `user_id` (int): ID пользователя
- `chat_id` (int): ID чата
- `task_name` (str, optional): Фильтр по названию задачи
- `status` (str, optional): Фильтр по статусу

**Возвращает:**
- List[Dict]: Список результатов

### `update_intermediate_result_status(result_id, status, result_data=None) -> bool`

Обновляет статус промежуточного результата.

**Возвращает:**
- bool: True если обновление успешно

---

## Действия агента

### `save_action(user_id, chat_id, action_type, description=None, input_data=None, output_data=None, execution_time=None) -> int`

Сохраняет запись о действии агента.

**Параметры:**
- `user_id` (int): ID пользователя
- `chat_id` (int): ID чата
- `action_type` (str): Тип действия (например, 'api_call', 'parsing')
- `description` (str, optional): Описание действия
- `input_data` (Any, optional): Входные данные
- `output_data` (Any, optional): Выходные данные
- `execution_time` (int, optional): Время выполнения в миллисекундах

**Пример:**
```python
action_id = memory.save_action(
    user_id=12345,
    chat_id=67890,
    action_type="gpt_request",
    description="Запрос к Yandex GPT",
    input_data={"message": "Привет"},
    output_data={"response_received": True},
    execution_time=1500
)
```

### `get_actions_history(user_id, chat_id, action_type=None, limit=50) -> List[Dict]`

Получает историю действий агента.

---

## База знаний

### `save_knowledge(user_id, entity_type, key, value, confidence=1.0, source_message_id=None) -> int`

Сохраняет факт в базу знаний.

**Параметры:**
- `user_id` (int): ID пользователя
- `entity_type` (str): Тип сущности ('preference', 'fact', 'name' и т.д.)
- `key` (str): Ключ сущности
- `value` (str): Значение сущности
- `confidence` (float): Уверенность в факте (0.0 - 1.0)
- `source_message_id` (int, optional): ID исходного сообщения

**Пример:**
```python
knowledge_id = memory.save_knowledge(
    user_id=12345,
    entity_type="preference",
    key="favorite_color",
    value="blue",
    confidence=0.95
)
```

### `get_knowledge(user_id, entity_type=None) -> List[Dict]`

Получает знания о пользователе.

**Параметры:**
- `user_id` (int): ID пользователя
- `entity_type` (str, optional): Фильтр по типу сущности

**Возвращает:**
- List[Dict]: Список фактов

---

## Управление сессиями

### `create_session(user_id, chat_id) -> str`

Создает новую сессию.

**Возвращает:**
- str: UUID созданной сессии

**Пример:**
```python
session_id = memory.create_session(12345, 67890)
print(f"Создана сессия: {session_id}")
```

### `end_session(session_id) -> bool`

Завершает сессию.

**Возвращает:**
- bool: True если сессия успешно завершена

### `get_active_session(user_id, chat_id) -> Optional[str]`

Получает ID активной сессии для пользователя.

**Возвращает:**
- str или None: ID активной сессии или None

---

## Служебные методы

### `get_statistics(user_id=None) -> Dict[str, Any]`

Получает статистику по базе данных.

**Параметры:**
- `user_id` (int, optional): ID пользователя для персональной статистики

**Возвращает:**
- Dict: Словарь со статистикой

**Пример:**
```python
# Персональная статистика
stats = memory.get_statistics(user_id=12345)
print(f"Сообщений: {stats['messages_count']}")

# Общая статистика
global_stats = memory.get_statistics()
print(f"Всего пользователей: {global_stats['unique_users']}")
```

### `clear_user_history(user_id, chat_id) -> bool`

Очищает историю диалога для пользователя.

**Возвращает:**
- bool: True если очистка успешна

### `cleanup_old_data(days=30) -> Dict[str, int]`

Очищает старые данные из базы.

**Параметры:**
- `days` (int): Количество дней для хранения данных (по умолчанию 30)

**Возвращает:**
- Dict[str, int]: Количество удаленных записей по каждой таблице

**Пример:**
```python
deleted = memory.cleanup_old_data(days=7)
print(f"Удалено сообщений: {deleted['conversations']}")
```

### `export_conversation_history(user_id, chat_id, format='json') -> Optional[str]`

Экспортирует историю диалога в различных форматах.

**Параметры:**
- `user_id` (int): ID пользователя
- `chat_id` (int): ID чата
- `format` (str): Формат экспорта ('json', 'text', 'csv')

**Возвращает:**
- str или None: Строка с экспортированными данными

**Пример:**
```python
# Экспорт в JSON
json_data = memory.export_conversation_history(12345, 67890, format='json')
with open('history.json', 'w') as f:
    f.write(json_data)

# Экспорт в текст
text_data = memory.export_conversation_history(12345, 67890, format='text')
print(text_data)
```

---

## Обработка ошибок

Все методы MemoryManager обрабатывают ошибки и логируют их через модуль `logging`. При критических ошибках выбрасываются исключения:

- `ValueError`: Неверные параметры (например, неправильный message_type)
- `FileNotFoundError`: Отсутствует файл schema.sql
- `sqlite3.Error`: Ошибки при работе с базой данных

**Рекомендуется оборачивать вызовы в try-except:**

```python
try:
    memory.save_message(user_id, chat_id, text, "user")
except ValueError as e:
    logger.error(f"Неверные параметры: {e}")
except Exception as e:
    logger.error(f"Ошибка при сохранении: {e}")
```

---

## Потокобезопасность

MemoryManager использует `threading.Lock()` для обеспечения потокобезопасности. Можно безопасно использовать один экземпляр из нескольких потоков.

**Пример:**
```python
import threading

memory = MemoryManager()

def worker(thread_id):
    memory.save_message(thread_id, thread_id, f"Сообщение {thread_id}", "user")

threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

---

## См. также

- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Схема базы данных
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Руководство по интеграции
