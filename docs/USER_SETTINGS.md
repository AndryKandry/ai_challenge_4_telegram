# Документация: Система управления пользовательскими настройками

## Обзор

Модуль `storage/user_settings.py` обеспечивает персистентное хранение пользовательских настроек в SQLite базе данных. Основная функция - сохранение выбора LLM провайдера для каждого пользователя между сессиями бота.

## Класс `UserSettings`

### Местоположение
`storage/user_settings.py`

### Описание
Класс для управления пользовательскими настройками с сохранением в SQLite.

---

## Инициализация

```python
from storage import UserSettings

settings = UserSettings(db_path="agent_memory.db")
```

### Параметры

- `db_path` (str): Путь к файлу базы данных SQLite (по умолчанию "agent_memory.db")

### Что происходит при инициализации

1. Создаётся таблица `user_settings` если её нет
2. Создаётся индекс для быстрого поиска по `selected_provider`
3. Логируется успешная инициализация

---

## Структура базы данных

### Таблица `user_settings`

| Колонка | Тип | Описание | Ограничения |
|---------|-----|----------|-------------|
| `user_id` | INTEGER | ID пользователя в Telegram | PRIMARY KEY |
| `selected_provider` | TEXT | Выбранный LLM провайдер | NOT NULL, DEFAULT 'openai' |
| `created_at` | TIMESTAMP | Дата создания записи | DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | Дата последнего обновления | DEFAULT CURRENT_TIMESTAMP |

### Индексы

- `idx_user_settings_provider`: Индекс на колонке `selected_provider` для быстрого поиска

---

## API методы

### `get_provider(user_id: int) -> str`

Получить выбранного провайдера для пользователя.

**Параметры:**
- `user_id` (int): ID пользователя в Telegram

**Возвращает:**
- `str`: Название провайдера ("openai", "yandex" или "deepseek")
- По умолчанию возвращает "openai" для новых пользователей

**Пример:**
```python
provider = settings.get_provider(123456789)
print(provider)  # "openai"
```

**Обработка ошибок:**
- При ошибке БД возвращается "openai"
- Ошибка логируется

---

### `set_provider(user_id: int, provider: str) -> bool`

Установить провайдера для пользователя.

**Параметры:**
- `user_id` (int): ID пользователя в Telegram
- `provider` (str): Название провайдера ("openai", "yandex" или "deepseek")

**Возвращает:**
- `bool`: True если успешно, False в случае ошибки

**Валидация:**
- Провайдер должен быть одним из: "openai", "yandex", "deepseek"
- При недопустимом значении возвращается False

**Пример:**
```python
success = settings.set_provider(123456789, "deepseek")
if success:
    print("Провайдер изменён")
```

**Особенности:**
- Использует UPSERT (INSERT ... ON CONFLICT)
- Если запись существует - обновляется
- Если записи нет - создаётся новая
- Автоматически обновляется `updated_at`

---

### `get_all_settings(user_id: int) -> Optional[Dict[str, Any]]`

Получить все настройки пользователя.

**Параметры:**
- `user_id` (int): ID пользователя в Telegram

**Возвращает:**
- `Dict[str, Any]`: Словарь с настройками или None если пользователь не найден

**Пример:**
```python
settings_dict = settings.get_all_settings(123456789)
if settings_dict:
    print(f"Provider: {settings_dict['selected_provider']}")
    print(f"Created: {settings_dict['created_at']}")
    print(f"Updated: {settings_dict['updated_at']}")
```

**Формат ответа:**
```python
{
    "user_id": 123456789,
    "selected_provider": "openai",
    "created_at": "2025-11-18 12:34:56",
    "updated_at": "2025-11-18 15:20:10"
}
```

---

### `delete_user_settings(user_id: int) -> bool`

Удалить настройки пользователя.

**Параметры:**
- `user_id` (int): ID пользователя в Telegram

**Возвращает:**
- `bool`: True если успешно, False если пользователь не найден или ошибка

**Пример:**
```python
deleted = settings.delete_user_settings(123456789)
if deleted:
    print("Настройки удалены")
else:
    print("Настройки не найдены")
```

---

### `get_statistics() -> Dict[str, int]`

Получить статистику по использованию провайдеров.

**Возвращает:**
- `Dict[str, int]`: Словарь со статистикой

**Пример:**
```python
stats = settings.get_statistics()
print(f"Всего пользователей: {stats['total_users']}")
print(f"OpenAI: {stats['openai_users']}")
print(f"Yandex: {stats['yandex_users']}")
print(f"DeepSeek: {stats['deepseek_users']}")
```

**Формат ответа:**
```python
{
    "total_users": 150,
    "openai_users": 90,
    "yandex_users": 45,
    "deepseek_users": 15
}
```

---

## Использование в боте

### Инициализация

В `bot.py`:

```python
class TelegramBot:
    def __init__(self, ...):
        # ...
        self.user_settings = UserSettings()
```

### Получение выбранного провайдера

В `handle_message`:

```python
selected_provider = self.user_settings.get_provider(user_id)

if selected_provider == "openai" and self.openai_provider:
    provider = self.openai_provider
elif selected_provider == "deepseek" and self.deepseek_provider:
    provider = self.deepseek_provider
else:
    provider = self.yandex_provider
```

### Изменение провайдера

В команде `/openai`:

```python
async def openai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    success = self.user_settings.set_provider(user_id, "openai")

    if success:
        await update.message.reply_text("✅ Выбрана модель OpenAI GPT")
    else:
        await update.message.reply_text("❌ Ошибка при сохранении настроек")
```

---

## Обработка ошибок

### Типы ошибок

1. **sqlite3.Error**: Ошибки базы данных
2. **Валидация**: Недопустимый провайдер

### Стратегия обработки

- Все ошибки логируются
- При ошибке чтения возвращается значение по умолчанию ("openai")
- При ошибке записи возвращается False
- Приложение продолжает работать даже при ошибках БД

### Примеры логов

```
ERROR - storage.user_settings - Ошибка получения провайдера для пользователя 123: ...
WARNING - storage.user_settings - Настройки пользователя 456 не найдены для удаления
INFO - storage.user_settings - Провайдер для пользователя 789 установлен: deepseek
```

---

## Миграции

### Добавление новых полей

Если нужно добавить новое поле в настройки:

1. Создайте миграцию:
```python
def migrate_add_field():
    with sqlite3.connect("agent_memory.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            ALTER TABLE user_settings
            ADD COLUMN new_field TEXT DEFAULT 'default_value'
        """)
        conn.commit()
```

2. Запустите миграцию перед инициализацией бота

---

## Производительность

### Оптимизации

- **Индексы**: Индекс на `selected_provider` ускоряет статистику
- **Primary Key**: `user_id` обеспечивает быстрый поиск
- **UPSERT**: Одна операция вместо SELECT + INSERT/UPDATE

### Benchmark (примерный)

- `get_provider`: ~0.1ms
- `set_provider`: ~0.5ms
- `get_statistics`: ~1ms для 1000 пользователей

---

## Безопасность

1. **SQL Injection**: Используются параметризованные запросы
2. **Конкурентный доступ**: SQLite обеспечивает блокировки
3. **Валидация**: Проверка допустимых значений провайдера

---

## Примеры использования

### Переключение провайдера с проверкой

```python
def switch_provider(settings, user_id, new_provider):
    # Получаем текущий провайдер
    current = settings.get_provider(user_id)

    if current == new_provider:
        print("Провайдер уже выбран")
        return

    # Меняем провайдер
    if settings.set_provider(user_id, new_provider):
        print(f"Изменено: {current} -> {new_provider}")
    else:
        print("Ошибка изменения")
```

### Просмотр настроек пользователя

```python
def show_user_info(settings, user_id):
    settings_dict = settings.get_all_settings(user_id)

    if not settings_dict:
        print("Пользователь не найден")
        return

    print("Настройки пользователя:")
    for key, value in settings_dict.items():
        print(f"  {key}: {value}")
```

### Статистика использования

```python
def show_provider_stats(settings):
    stats = settings.get_statistics()

    total = stats['total_users']
    if total == 0:
        print("Нет пользователей")
        return

    print(f"Статистика ({total} пользователей):")
    print(f"  OpenAI:   {stats['openai_users']:3d} ({stats['openai_users']/total*100:.1f}%)")
    print(f"  Yandex:   {stats['yandex_users']:3d} ({stats['yandex_users']/total*100:.1f}%)")
    print(f"  DeepSeek: {stats['deepseek_users']:3d} ({stats['deepseek_users']/total*100:.1f}%)")
```

---

## Интеграция с другими компонентами

### Связь с MemoryManager

`UserSettings` и `MemoryManager` используют одну и ту же базу данных:

```python
memory = MemoryManager("agent_memory.db")
settings = UserSettings("agent_memory.db")
```

Это обеспечивает:
- Единую точку хранения
- Консистентность данных
- Упрощённый backup

### Связь с провайдерами

```python
# Получить провайдер на основе настроек
selected_provider_name = settings.get_provider(user_id)

if selected_provider_name == "openai":
    provider = openai_provider
elif selected_provider_name == "deepseek":
    provider = deepseek_provider
else:
    provider = yandex_provider

# Использовать провайдер
response = await provider.generate_response(message, prompt, history)
```

---

## Тестирование

### Пример теста

```python
import unittest
from storage import UserSettings

class TestUserSettings(unittest.TestCase):
    def setUp(self):
        self.settings = UserSettings(":memory:")  # Используем in-memory БД

    def test_default_provider(self):
        provider = self.settings.get_provider(123)
        self.assertEqual(provider, "openai")

    def test_set_and_get(self):
        self.settings.set_provider(123, "yandex")
        provider = self.settings.get_provider(123)
        self.assertEqual(provider, "yandex")

    def test_invalid_provider(self):
        result = self.settings.set_provider(123, "invalid")
        self.assertFalse(result)
```

---

## FAQ

**Q: Что происходит при первом обращении нового пользователя?**
A: Возвращается значение по умолчанию "openai", запись в БД не создаётся до первого вызова `set_provider`.

**Q: Можно ли использовать отдельную БД для настроек?**
A: Да, передайте другой путь в конструктор: `UserSettings("user_settings.db")`

**Q: Как сбросить настройки всех пользователей?**
A: Используйте SQL запрос: `DELETE FROM user_settings` или удалите файл БД.

**Q: Поддерживается ли асинхронность?**
A: Нет, методы синхронные. SQLite в Python не требует async для простых операций.
