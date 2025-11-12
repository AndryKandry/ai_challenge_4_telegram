# Система подсчета токенов - Техническая документация

## Обзор

Система подсчета токенов предоставляет полный функционал для отслеживания использования токенов в Telegram-боте с Yandex GPT API. Включает автоматический подсчет, интерактивное отображение статистики, проверку лимитов и персонализированные настройки для каждого пользователя.

## Архитектура

### Основные модули

#### 1. `config.py` - Конфигурация
Центральный файл конфигурации со всеми настройками:
- **Лимиты токенов** для разных моделей (YandexGPT Lite: 8192, Pro: 32000)
- **Пороги предупреждений** (80% и 90% от лимита)
- **Режимы отображения** (hidden, compact, detailed, warnings_only)
- **Эмодзи-индикаторы** (✅, ⚠️, 🔴)
- **Примерные коэффициенты** для подсчета токенов

```python
# Примеры использования
from config import get_model_token_limit, get_token_indicator

limit = get_model_token_limit("yandexgpt-lite")  # 8192
indicator = get_token_indicator(0.85)  # 🔴
```

#### 2. `token_counter.py` - Подсчет токенов

**Класс `TokenCounter`:**
- `count_tokens(text, model)` - Основной метод подсчета токенов
- `check_token_limit(tokens, model)` - Проверка лимита
- `get_token_limit_percentage(tokens, model)` - Процент использования
- `calculate_overflow(tokens, model)` - Вычисление превышения
- `log_token_usage(request_tokens, response_tokens, model)` - Логирование

**Алгоритм подсчета:**
1. Подсчет символов в тексте
2. Подсчет слов через regex
3. Примерная оценка: `(chars/4 + words*1.33) / 2`
4. Для более точного подсчета можно использовать API токенизации (пока не реализовано)

```python
from token_counter import TokenCounter

counter = TokenCounter(api_key)
tokens = counter.count_tokens("Привет, мир!")  # ~4 токена
is_ok = counter.check_token_limit(tokens, "yandexgpt-lite")  # True
```

#### 3. `token_ui.py` - Интерактивный интерфейс

Функции форматирования для пользователей:

**`format_token_stats(request, response, model, mode)`**
- Форматирует статистику токенов в зависимости от режима
- Режимы: hidden, compact, detailed, warnings_only

**`format_token_overflow_message(tokens, limit)`**
- Создает интерактивное сообщение о превышении лимита
- Показывает конкретные рекомендации по исправлению

**`format_token_help_message()`**
- Обучающее сообщение для первого использования
- Объясняет концепцию токенов простым языком

```python
from token_ui import format_token_stats, format_token_overflow_message

# Подробная статистика
stats = format_token_stats(45, 320, mode="detailed")

# Сообщение об ошибке
error_msg = format_token_overflow_message(9500, 8192)
```

#### 4. `user_settings.py` - Настройки пользователей

**Класс `UserTokenSettings`:**
- `display_mode` - Режим отображения токенов
- `show_help` - Показывать ли обучающие сообщения
- `auto_show` - Автоматически показывать токены
- `first_use` - Флаг первого использования

**Класс `TokenStatistics`:**
- Статистика за сессию (с момента запуска бота)
- Статистика за день (сбрасывается в полночь)
- Данные последнего запроса

**Класс `UserDataManager`:**
- Управление загрузкой/сохранением данных
- Кэширование в памяти для быстрого доступа
- Персистентность в JSON файлах

```python
from user_settings import UserDataManager

manager = UserDataManager()
settings = manager.get_settings(user_id)
stats = manager.get_stats(user_id)

stats.add_request(request_tokens=45, response_tokens=320)
manager.save_stats(user_id)
```

#### 5. `token_commands.py` - Обработчики команд

**Класс `TokenCommandHandler`:**
- `handle_tokens_command()` - /tokens
- `handle_tokens_stats_command()` - /tokens_stats
- `handle_token_mode_command()` - /token_mode on/off
- `handle_token_settings_command()` - /token_settings
- `handle_token_help_command()` - /token_help

Все обработчики асинхронные и интегрированы с Telegram Bot API.

#### 6. `error_handlers.py` - Обработка ошибок

**Функции:**
- `handle_token_overflow(update, context, tokens, model)` - Обработка превышения лимита
- `send_token_warning(update, context, tokens, model)` - Предупреждение при приближении
- `check_token_limit_before_request(tokens, model)` - Проверка ДО отправки в API

## Интеграция с bot.py

### Инициализация
```python
self.token_counter = TokenCounter(yandex_api_key)
self.user_manager = UserDataManager()
self.token_command_handler = TokenCommandHandler(self.user_manager)
```

### Регистрация команд
```python
self.application.add_handler(CommandHandler("tokens", self.tokens_command))
self.application.add_handler(CommandHandler("tokens_stats", self.tokens_stats_command))
# ... другие команды
```

### Обработка сообщений
```python
# 1. Подсчет токенов запроса
request_tokens = self.token_counter.count_tokens(user_message)

# 2. Проверка лимита ДО отправки в API
is_within_limit, error_msg = check_token_limit_before_request(request_tokens)
if not is_within_limit:
    await handle_token_overflow(update, context, request_tokens)
    return

# 3. Отправка в Yandex GPT
response = await self.gpt_client.send_message(user_message, system_prompt)

# 4. Подсчет токенов ответа
response_tokens = self.token_counter.count_tokens(response)

# 5. Обновление статистики
stats = self.user_manager.get_stats(user_id)
stats.add_request(request_tokens, response_tokens)
self.user_manager.save_stats(user_id)

# 6. Отображение статистики
settings = self.user_manager.get_settings(user_id)
token_stats_message = format_token_stats(
    request_tokens, response_tokens, mode=settings.display_mode
)
full_response = formatted_response + token_stats_message
```

## Хранение данных

### Структура файлов
```
user_data/
├── user_settings.json  # Настройки всех пользователей
└── user_stats.json     # Статистика всех пользователей
```

### Формат JSON

**user_settings.json:**
```json
{
  "123456789": {
    "user_id": 123456789,
    "display_mode": "detailed",
    "show_help": true,
    "auto_show": true,
    "first_use": false
  }
}
```

**user_stats.json:**
```json
{
  "123456789": {
    "user_id": 123456789,
    "session_requests": 12,
    "session_tokens": 5430,
    "daily_requests": 28,
    "daily_tokens": 12450,
    "last_reset": "2025-11-12T00:00:00",
    "last_request_tokens": 45,
    "last_response_tokens": 320
  }
}
```

## Лимиты и пороги

### Модели Yandex GPT
- **YandexGPT Lite**: 8,192 токена (максимальный контекст)
- **YandexGPT Pro**: 32,000 токенов (максимальный контекст)

### Визуальные индикаторы
- ✅ **0-50%** - Зеленый, все в порядке
- ⚠️ **50-80%** - Желтый, приближение к лимиту
- 🔴 **80-100%** - Красный, критическое приближение

### Примерная оценка
- **1 токен** ≈ 0.75 слова (русский)
- **1 токен** ≈ 4 символа (русский)
- **100 токенов** ≈ 75 слов ≈ 400 символов

## Логирование

Формат логов:
```
[TOKENS] Request: 45 tokens | Response: 320 tokens | Total: 365 tokens
[TOKENS] Model: yandexgpt-lite | Max context: 8192 tokens (4.5% used)
[TOKENS] User display mode: detailed
```

Логи пишутся в:
- Консоль (через Python logging)
- Опционально: `token_usage.log` файл

## Тестирование

См. [testing_scenarios.md](testing_scenarios.md) для подробных тестовых сценариев.

Файл с примерами: `tests/test_requests_examples.txt`
- Короткие запросы (< 100 токенов)
- Средние запросы (200-500 токенов)
- Длинные запросы (30-50% лимита)
- Очень длинные запросы (близко к лимиту)
- Запросы, превышающие лимит

## Производительность

- **Подсчет токенов**: O(n) где n - длина текста
- **Кэширование настроек**: In-memory кэш для быстрого доступа
- **Сохранение данных**: Асинхронное сохранение в JSON
- **Overhead**: < 10ms на запрос для подсчета токенов

## Возможные улучшения

1. **Точный подсчет через API**
   - Использовать официальный Tokenizer API от Yandex
   - Требует дополнительные API вызовы

2. **База данных**
   - Замена JSON на SQLite/PostgreSQL для большего масштаба
   - Более эффективные запросы при большом количестве пользователей

3. **Расширенная аналитика**
   - Графики использования токенов
   - Экспорт статистики в CSV
   - Агрегированная статистика по всем пользователям

4. **Кэширование результатов**
   - Кэш tokenize результатов для одинаковых текстов
   - Redis для распределенного кэширования

## API Reference

См. docstrings в каждом модуле для подробного API reference.

---

Документация обновлена: 2025-11-12
