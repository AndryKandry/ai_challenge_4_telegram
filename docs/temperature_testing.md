# Техническая документация: Тестирование температуры LLM

## Обзор

Модуль `temperature_tester.py` предоставляет функционал для сравнения результатов работы Yandex GPT при различных значениях параметра температуры. Это позволяет пользователям понять, как температура влияет на креативность, стабильность и вариативность ответов модели.

## Архитектура решения

### Компоненты системы

```
┌─────────────────┐
│  TelegramBot    │
│  (bot.py)       │
└────────┬────────┘
         │
         │ использует
         ▼
┌─────────────────────┐
│ TemperatureTester   │
│ (temperature_       │
│  tester.py)         │
└──────────┬──────────┘
           │
           │ отправляет запросы
           ▼
┌─────────────────────┐
│  Yandex GPT API     │
│  (3 параллельных    │
│   запроса)          │
└─────────────────────┘
```

### Модуль `temperature_tester.py`

#### Класс `TemperatureTester`

Основной класс для тестирования температур.

**Поля класса:**
- `api_key: str` - API ключ для Yandex Cloud
- `timeout: int` - Таймаут запроса (по умолчанию 30 секунд)
- `headers: dict` - HTTP заголовки для запросов к API
- `temperatures: list[float]` - Список тестируемых температур [0.0, 0.7, 1.0]

**Константы:**
```python
TEMPERATURE_DETERMINISTIC = 0.0    # Детерминированность
TEMPERATURE_BALANCED = 0.7         # Сбалансированность
TEMPERATURE_CREATIVE = 1.0         # Креативность
DEFAULT_TEST_PROMPT = "Придумай название для стартапа по доставке еды"
```

## API методов

### `__init__(api_key: str, timeout: int = 30)`

Инициализация тестера.

**Параметры:**
- `api_key` - API ключ Yandex Cloud
- `timeout` - Таймаут запроса в секундах (опционально)

**Пример:**
```python
tester = TemperatureTester(api_key="your_api_key", timeout=30)
```

---

### `async send_message_with_temperature(user_message: str, temperature: float, system_prompt: str = "") -> Optional[str]`

Отправка одного запроса с указанной температурой.

**Параметры:**
- `user_message` - Текст промпта от пользователя
- `temperature` - Значение температуры (0.0 - 1.0)
- `system_prompt` - Системный промпт (опционально)

**Возвращает:**
- `str` - Текст ответа от Yandex GPT
- `None` - В случае ошибки

**Пример:**
```python
response = await tester.send_message_with_temperature(
    user_message="Придумай слоган",
    temperature=0.7,
    system_prompt="Ты креативный маркетолог"
)
```

**Обработка ошибок:**
- `httpx.TimeoutException` - Превышен таймаут
- `httpx.HTTPStatusError` - HTTP ошибка (401, 400, 429 и т.д.)
- `ValueError` - Ошибка парсинга JSON
- `Exception` - Прочие непредвиденные ошибки

---

### `async test_temperatures(prompt: Optional[str] = None, system_prompt: str = "") -> Dict`

Основной метод тестирования - отправляет один промпт с тремя разными температурами.

**Параметры:**
- `prompt` - Текст промпта (если `None`, используется `DEFAULT_TEST_PROMPT`)
- `system_prompt` - Системный промпт (опционально)

**Возвращает:**
```python
{
    "prompt": "исходный текст промпта",
    "results": {
        "temp_0.0": {
            "temperature": 0.0,
            "text": "ответ от модели",
            "metadata": {
                "success": True
            }
        },
        "temp_0.7": {...},
        "temp_1.0": {...}
    },
    "analysis": {
        "recommendations": "текст рекомендаций",
        "comparison": {
            "similarity_scores": {
                "temp_0.0_vs_temp_0.7": 0.85,
                "temp_0.0_vs_temp_1.0": 0.72,
                "temp_0.7_vs_temp_1.0": 0.68
            },
            "average_similarity": 0.75,
            "average_diversity": 0.25
        }
    }
}
```

**Пример:**
```python
results = await tester.test_temperatures(
    prompt="Придумай название для кофейни"
)
```

---

### `format_test_results(results: Dict) -> str`

Форматирование результатов для вывода пользователю в Telegram.

**Параметры:**
- `results` - Словарь с результатами (возвращаемый из `test_temperatures`)

**Возвращает:**
- `str` - Отформатированный текст для отправки пользователю

**Пример вывода:**
```
🧪 ТЕСТИРОВАНИЕ ТЕМПЕРАТУРЫ LLM

📝 Промпт: Придумай название для стартапа по доставке еды

==================================================

🌡️ Temperature = 0.0 (ДЕТЕРМИНИРОВАННОСТЬ)
--------------------------------------------------
💬 Ответ:
FoodExpress - быстрая доставка еды

🌡️ Temperature = 0.7 (СБАЛАНСИРОВАННОСТЬ)
--------------------------------------------------
💬 Ответ:
TastyRush - доставка вкуса к вашей двери

🌡️ Temperature = 1.0 (КРЕАТИВНОСТЬ)
--------------------------------------------------
💬 Ответ:
НямНямчик - твоя еда уже в пути!

==================================================

📊 АНАЛИЗ И РЕКОМЕНДАЦИИ
...
```

## Алгоритм сравнительного анализа

### 1. Расчет схожести текстов

Используется алгоритм **SequenceMatcher** из модуля `difflib`:

```python
def _calculate_similarity(text1: str, text2: str) -> float:
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
```

- Возвращает коэффициент от 0.0 (полностью различны) до 1.0 (идентичны)
- Сравнение нечувствительно к регистру

### 2. Попарное сравнение результатов

Для трех температур (0.0, 0.7, 1.0) выполняется 3 сравнения:
- temp_0.0 vs temp_0.7
- temp_0.0 vs temp_1.0
- temp_0.7 vs temp_1.0

### 3. Метрики

**Average Similarity** - средняя схожесть всех пар:
```python
avg_similarity = sum(similarity_scores.values()) / len(similarity_scores)
```

**Average Diversity** - средняя вариативность:
```python
avg_diversity = 1 - avg_similarity
```

### 4. Генерация рекомендаций

На основе `avg_similarity`:

| Значение | Интерпретация | Рекомендация |
|----------|--------------|--------------|
| > 0.8 | Высокая схожесть | Все температуры дают похожие результаты. Используйте 0.7 для баланса. |
| 0.5 - 0.8 | Средняя вариативность | Температура оказывает заметное влияние. |
| < 0.5 | Высокая вариативность | Используйте 0.0 для стабильности или 1.0 для креативности. |

## Интеграция в Telegram бота

### Команда `/test_temperature`

**Файл:** `bot.py`
**Метод:** `TelegramBot.test_temperature_command()`

**Использование:**
```
/test_temperature
/test_temperature Придумай название для кофейни
```

**Поток выполнения:**

1. Пользователь отправляет команду
2. Бот парсит аргументы (промпт)
3. Отправляется уведомление о начале тестирования
4. Вызывается `tester.test_temperatures(prompt)`
5. Результаты форматируются через `format_test_results()`
6. Если текст длиннее 4096 символов, разбивается на части через `_split_long_message()`
7. Результаты отправляются пользователю

**Обработка ошибок:**
- Перехватываются все исключения
- Пользователь получает понятное сообщение об ошибке
- Ошибки логируются с `exc_info=True`

## Примеры использования

### Базовое использование

```python
from temperature_tester import TemperatureTester
import asyncio

async def main():
    tester = TemperatureTester(api_key="your_api_key")
    results = await tester.test_temperatures()
    print(tester.format_test_results(results))

asyncio.run(main())
```

### С кастомным промптом

```python
results = await tester.test_temperatures(
    prompt="Напиши короткое стихотворение про кота"
)
```

### С системным промптом

```python
results = await tester.test_temperatures(
    prompt="Объясни квантовую механику",
    system_prompt="Ты — профессор физики. Объясняй просто и доступно."
)
```

### Обработка результатов программно

```python
results = await tester.test_temperatures("Придумай слоган")

# Извлечение отдельных ответов
temp_0_response = results["results"]["temp_0.0"]["text"]
temp_07_response = results["results"]["temp_0.7"]["text"]
temp_10_response = results["results"]["temp_1.0"]["text"]

# Получение метрик
avg_similarity = results["analysis"]["comparison"]["average_similarity"]
avg_diversity = results["analysis"]["comparison"]["average_diversity"]

print(f"Средняя схожесть: {avg_similarity:.0%}")
print(f"Средняя вариативность: {avg_diversity:.0%}")
```

## Производительность

### Время выполнения

При параллельной отправке запросов:
- **Оптимистичный сценарий:** ~3-5 секунд (если API быстро отвечает)
- **Реалистичный сценарий:** ~10-15 секунд
- **Пессимистичный сценарий:** ~30 секунд (таймаут)

### Асинхронность

Запросы к API отправляются **параллельно**:

```python
tasks = []
for temp in self.temperatures:
    task = self.send_message_with_temperature(prompt, temp, system_prompt)
    tasks.append((temp, task))

# Все запросы выполняются одновременно
for temp, task in tasks:
    response = await task
```

## Логирование

Модуль использует стандартный `logging`:

```python
logger = logging.getLogger(__name__)
```

**Уровни логов:**
- `INFO` - успешные запросы и ответы
- `WARNING` - fallback операции, неожиданные данные
- `ERROR` - ошибки HTTP, таймауты, парсинг

**Примеры логов:**
```
INFO - Отправка запроса в Yandex GPT API (temperature=0.7)
INFO - Получен ответ от Yandex GPT API (temperature=0.7)
ERROR - HTTP ошибка при запросе к Yandex GPT (temperature=1.0): 429 - Too Many Requests
```

## Ограничения и известные проблемы

1. **Rate Limiting**
   - Yandex GPT API имеет лимиты запросов
   - При превышении лимита возвращается 429 ошибка
   - Рекомендуется добавить задержки между запусками теста

2. **Таймауты**
   - По умолчанию 30 секунд
   - Может быть недостаточно для сложных промптов
   - Можно увеличить при инициализации

3. **Длинные ответы**
   - Telegram ограничивает сообщения до 4096 символов
   - Реализовано автоматическое разбиение на части
   - Не поддерживается markdown в разбитых сообщениях

4. **Стоимость**
   - Каждый тест = 3 запроса к API
   - Следует учитывать стоимость при частом использовании

## Возможные улучшения

1. **Кэширование результатов**
   - Сохранять результаты тестов в БД
   - Избегать повторных запросов для одинаковых промптов

2. **Настройка температур**
   - Позволить пользователю выбирать значения температур
   - Добавить команду `/test_temperature_custom 0.3 0.6 1.0 <промпт>`

3. **Визуализация**
   - Графики схожести
   - Экспорт в PDF/HTML

4. **Расширенная аналитика**
   - Токсичность ответов
   - Длина ответов
   - Читаемость (flesch reading score)

5. **A/B тестирование**
   - Слепое сравнение (пользователь не видит температуру)
   - Голосование за лучший вариант

## Зависимости

Модуль требует:
- `httpx` - асинхронные HTTP запросы
- `logging` - встроенный модуль логирования
- `difflib` - встроенный модуль для сравнения текстов
- `asyncio` - асинхронное выполнение

Установка:
```bash
pip install httpx
```

## Тестирование

Для тестирования модуля создайте файл `test_temperature_tester.py`:

```python
import asyncio
from temperature_tester import TemperatureTester
import os
from dotenv import load_dotenv

async def test_basic():
    load_dotenv()
    api_key = os.getenv("YANDEX_API_KEY")

    tester = TemperatureTester(api_key)
    results = await tester.test_temperatures()

    assert "prompt" in results
    assert "results" in results
    assert "analysis" in results
    assert len(results["results"]) == 3

    print("✅ Базовый тест пройден")
    print(tester.format_test_results(results))

if __name__ == "__main__":
    asyncio.run(test_basic())
```

## Безопасность

1. **API ключ**
   - Никогда не логируется
   - Передается только через переменные окружения
   - Не должен попадать в Git

2. **Валидация ввода**
   - Промпты не имеют специальной валидации
   - Yandex GPT сам фильтрует небезопасный контент

3. **Обработка ошибок**
   - Все ошибки перехватываются
   - Не раскрывают внутреннюю структуру системы

## Контакты и поддержка

Для вопросов и предложений по модулю тестирования температуры обращайтесь к разработчикам проекта.

---

**Версия документации:** 1.0
**Дата:** 2025-11-10
**Автор:** AI Challenge 4 Team
