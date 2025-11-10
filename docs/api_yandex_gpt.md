# Yandex GPT API - Техническая документация

## Обзор

Yandex GPT API предоставляет доступ к большим языковым моделям (LLM) от Yandex Cloud. Этот документ описывает взаимодействие с API в контексте данного проекта.

## Базовая информация

**Endpoint:** `https://llm.api.cloud.yandex.net/foundationModels/v1/completion`

**Метод:** `POST`

**Аутентификация:** Bearer Token (API Key)

**Документация Yandex:** https://cloud.yandex.ru/docs/foundation-models/

## Настройка доступа

### 1. Получение API ключа

1. Зарегистрируйтесь в Yandex Cloud: https://cloud.yandex.ru/
2. Создайте сервисный аккаунт
3. Назначьте роль `ai.languageModels.user`
4. Создайте API ключ для сервисного аккаунта

### 2. Переменные окружения

Для работы с API необходимы следующие переменные:

```bash
YANDEX_API_KEY=<ваш_api_ключ>
YANDEX_FOLDER_ID=<ваш_folder_id>
```

**Где найти FOLDER_ID:**
- Откройте консоль Yandex Cloud
- Перейдите в нужный каталог (folder)
- Скопируйте ID из URL или настроек каталога

### 3. Пример .env файла

```env
TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
YANDEX_API_KEY=AQVN1234567890abcdefghijklmnop
YANDEX_FOLDER_ID=b1g1234567890abcdef
```

## Структура запроса

### HTTP Headers

```http
POST /foundationModels/v1/completion HTTP/1.1
Host: llm.api.cloud.yandex.net
Authorization: Bearer <YANDEX_API_KEY>
Content-Type: application/json
```

### Тело запроса (JSON)

```json
{
  "modelUri": "gpt://<FOLDER_ID>/yandexgpt-lite",
  "completionOptions": {
    "stream": false,
    "temperature": 0.7,
    "maxTokens": 2000
  },
  "messages": [
    {
      "role": "system",
      "text": "Ты — помощник."
    },
    {
      "role": "user",
      "text": "Привет!"
    }
  ]
}
```

## Параметры запроса

### `modelUri` (обязательный)

URI модели для генерации.

**Формат:** `gpt://<FOLDER_ID>/<MODEL_NAME>`

**Доступные модели:**
- `yandexgpt-lite` - Легкая версия (быстрее, дешевле)
- `yandexgpt` - Полная версия (более качественно)
- `yandexgpt-32k` - Версия с расширенным контекстом (до 32K токенов)

**Пример:**
```python
modelUri = f"gpt://{os.getenv('YANDEX_FOLDER_ID')}/yandexgpt-lite"
```

---

### `completionOptions` (обязательный)

Настройки генерации ответа.

#### `stream` (boolean)

Включение потоковой передачи ответа.

- `false` - получить полный ответ одним запросом (используется в проекте)
- `true` - получать ответ по частям (streaming)

**По умолчанию:** `false`

#### `temperature` (float)

**Самый важный параметр** - контролирует случайность и креативность ответов.

**Диапазон:** 0.0 - 1.0 (Yandex рекомендует), но можно до 2.0

**Влияние на ответы:**

| Temperature | Поведение | Применение |
|-------------|-----------|-----------|
| 0.0 | Детерминированный, всегда одинаковый ответ | Переводы, классификация, извлечение данных |
| 0.3 | Минимальная вариативность | Технические ответы, факты |
| 0.7 | Сбалансированная креативность | Диалоги, Q&A, общие задачи |
| 1.0 | Высокая креативность | Генерация идей, creative writing |
| 1.0+ | Максимальная креативность, может быть непредсказуемым | Brainstorming, художественные тексты |

**Примеры в коде:**

```python
# Детерминированный ответ
"completionOptions": {
    "temperature": 0.0
}

# Сбалансированный (по умолчанию в проекте)
"completionOptions": {
    "temperature": 0.7
}

# Креативный
"completionOptions": {
    "temperature": 1.0
}
```

**Важно:**
- При `temperature=0.0` модель всегда выбирает наиболее вероятный следующий токен
- При высокой температуре модель может выбирать менее вероятные варианты, что повышает креативность, но может снижать точность

#### `maxTokens` (integer)

Максимальное количество токенов в ответе.

**Диапазон:** 1 - 8000 (для yandexgpt-lite)

**Примерная оценка:**
- 1 токен ≈ 0.75 слова (для русского языка)
- 1000 токенов ≈ 750 слов ≈ 3-4 абзаца текста

**В проекте:** `2000` (достаточно для большинства ответов)

**Пример:**
```python
"completionOptions": {
    "maxTokens": 2000  # ~1500 слов максимум
}
```

---

### `messages` (обязательный)

Массив сообщений в формате диалога.

**Структура сообщения:**
```json
{
  "role": "system" | "user" | "assistant",
  "text": "текст сообщения"
}
```

#### Роли сообщений

**`system`** - системные инструкции для модели

Определяет поведение и характер ответов модели.

```json
{
  "role": "system",
  "text": "Ты — профессиональный переводчик. Переводи точно, сохраняя стиль."
}
```

**`user`** - сообщение от пользователя

Вопрос или запрос пользователя.

```json
{
  "role": "user",
  "text": "Как работает квантовый компьютер?"
}
```

**`assistant`** - предыдущий ответ модели

Используется для поддержания контекста диалога (в данном проекте не используется, т.к. нет истории).

```json
{
  "role": "assistant",
  "text": "Квантовый компьютер использует кубиты..."
}
```

#### Примеры использования

**Простой запрос без системного промпта:**
```python
"messages": [
    {
        "role": "user",
        "text": "Расскажи про Python"
    }
]
```

**С системным промптом:**
```python
"messages": [
    {
        "role": "system",
        "text": "Ты — эксперт по программированию на Python."
    },
    {
        "role": "user",
        "text": "Как работают декораторы?"
    }
]
```

**С контекстом диалога (несколько сообщений):**
```python
"messages": [
    {"role": "system", "text": "Ты — помощник."},
    {"role": "user", "text": "Что такое AI?"},
    {"role": "assistant", "text": "AI это искусственный интеллект..."},
    {"role": "user", "text": "А машинное обучение?"}
]
```

## Структура ответа

### Успешный ответ (200 OK)

```json
{
  "result": {
    "alternatives": [
      {
        "message": {
          "role": "assistant",
          "text": "Текст ответа от модели"
        },
        "status": "ALTERNATIVE_STATUS_FINAL"
      }
    ],
    "usage": {
      "inputTextTokens": "42",
      "completionTokens": "128",
      "totalTokens": "170"
    },
    "modelVersion": "07.03.2024"
  }
}
```

### Извлечение текста ответа

```python
data = response.json()

if "result" in data and "alternatives" in data["result"]:
    alternatives = data["result"]["alternatives"]
    if alternatives and len(alternatives) > 0:
        message_text = alternatives[0].get("message", {}).get("text")
        if message_text:
            return message_text
```

**Где используется в проекте:**
- `bot.py` - метод `YandexGPTClient.send_message()` (строка 104-109)
- `temperature_tester.py` - метод `TemperatureTester.send_message_with_temperature()` (строка 104-109)

### Метаданные ответа

#### `usage`

Информация о потреблении токенов:

- `inputTextTokens` - токены в запросе
- `completionTokens` - токены в ответе
- `totalTokens` - общее количество токенов

**Используется для:**
- Подсчета стоимости запросов
- Мониторинга использования API

#### `modelVersion`

Версия модели, использованной для генерации.

Формат: `DD.MM.YYYY`

## Обработка ошибок

### HTTP коды ответов

| Код | Значение | Причина | Решение |
|-----|----------|---------|---------|
| 200 | OK | Успешный запрос | - |
| 400 | Bad Request | Некорректные параметры | Проверить структуру JSON |
| 401 | Unauthorized | Неверный API ключ | Проверить `YANDEX_API_KEY` |
| 403 | Forbidden | Нет доступа к модели | Проверить права сервисного аккаунта |
| 404 | Not Found | Неверный endpoint | Проверить URL |
| 429 | Too Many Requests | Превышен лимит запросов | Добавить задержки, повторить позже |
| 500 | Internal Server Error | Ошибка на стороне Yandex | Повторить запрос |

### Примеры ошибок

#### 401 Unauthorized

```json
{
  "code": 16,
  "message": "Unauthorized"
}
```

**Причины:**
- Неверный API ключ
- Истекший API ключ
- API ключ не передан в заголовке

**Решение:**
```bash
# Проверить переменную окружения
echo $YANDEX_API_KEY

# Пересоздать API ключ в консоли Yandex Cloud
```

#### 400 Bad Request (неверный folder_id)

```json
{
  "code": 3,
  "message": "model not found"
}
```

**Причины:**
- Неверный `YANDEX_FOLDER_ID`
- Модель недоступна в данном folder

**Решение:**
```bash
# Проверить folder_id
echo $YANDEX_FOLDER_ID

# Скопировать корректный ID из консоли Yandex Cloud
```

#### 429 Too Many Requests

```json
{
  "code": 8,
  "message": "quota exceeded"
}
```

**Причины:**
- Превышен лимит запросов в минуту
- Превышен лимит токенов

**Решение:**
- Добавить задержки между запросами
- Уменьшить частоту тестирования температуры
- Увеличить квоту в настройках Yandex Cloud

### Обработка ошибок в коде

```python
try:
    response = await client.post(YANDEX_GPT_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    # ... обработка ответа

except httpx.TimeoutException:
    logger.error("Превышен таймаут запроса к Yandex GPT API")
    return None

except httpx.HTTPStatusError as e:
    logger.error(
        f"HTTP ошибка: {e.response.status_code} - {e.response.text}"
    )
    return None

except ValueError as e:
    logger.error(f"Ошибка парсинга JSON: {e}")
    return None

except Exception as e:
    logger.error(f"Неожиданная ошибка: {e}")
    return None
```

## Лимиты и квоты

### Бесплатный уровень (Free Tier)

- **Запросы:** до 10 000 в месяц
- **Токены:** до 1 000 000 в месяц
- **Скорость:** до 20 запросов в минуту

### Платный уровень

Цены актуальны на 2025 год:
- **yandexgpt-lite:** ~0.3₽ за 1000 токенов
- **yandexgpt:** ~1.2₽ за 1000 токенов

**Расчет стоимости тестирования температуры:**
- 3 запроса × (50 токенов запрос + 200 токенов ответ) = 750 токенов
- 750 токенов × 0.3₽/1000 = ~0.23₽ за один тест

### Рекомендации по оптимизации

1. **Используйте yandexgpt-lite** для простых задач
2. **Кэшируйте результаты** для повторяющихся запросов
3. **Ограничивайте maxTokens** до необходимого минимума
4. **Добавьте rate limiting** в боте

## Примеры кода

### Базовый запрос

```python
import httpx
import os

async def simple_request():
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    headers = {
        "Authorization": f"Bearer {os.getenv('YANDEX_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "modelUri": f"gpt://{os.getenv('YANDEX_FOLDER_ID')}/yandexgpt-lite",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 2000
        },
        "messages": [
            {"role": "user", "text": "Привет!"}
        ]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        text = data["result"]["alternatives"][0]["message"]["text"]
        return text
```

### Запрос с системным промптом

```python
payload = {
    "modelUri": f"gpt://{folder_id}/yandexgpt-lite",
    "completionOptions": {
        "stream": False,
        "temperature": 0.7,
        "maxTokens": 2000
    },
    "messages": [
        {
            "role": "system",
            "text": "Ты — эксперт по Python. Отвечай кратко и по делу."
        },
        {
            "role": "user",
            "text": "Что такое list comprehension?"
        }
    ]
}
```

### Параллельные запросы (тестирование температуры)

```python
import asyncio

async def test_temperatures(prompt: str):
    temperatures = [0.0, 0.7, 1.0]

    async def request_with_temp(temp):
        # ... создание payload с нужной температурой
        response = await send_request(payload)
        return temp, response

    tasks = [request_with_temp(t) for t in temperatures]
    results = await asyncio.gather(*tasks)

    return dict(results)
```

## Best Practices

### 1. Переиспользование соединений

```python
# ❌ Плохо - создает новое соединение каждый раз
async def bad_request():
    async with httpx.AsyncClient() as client:
        response = await client.post(...)

# ✅ Хорошо - переиспользует соединение
class YandexGPTClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def request(self):
        response = await self.client.post(...)
```

### 2. Правильные таймауты

```python
# Учитывайте время генерации
client = httpx.AsyncClient(timeout=30)  # 30 секунд для длинных ответов
```

### 3. Логирование

```python
logger.info(f"Отправка запроса (temperature={temperature})")
logger.info(f"Получен ответ: {len(text)} символов, {tokens} токенов")
logger.error(f"Ошибка: {e.response.status_code} - {e.response.text}")
```

### 4. Обработка ошибок

```python
# Всегда перехватывайте исключения
try:
    response = await send_request()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        # Ждем и повторяем
        await asyncio.sleep(10)
        response = await send_request()
    else:
        raise
```

## Debugging

### Проверка запроса с curl

```bash
curl -X POST \
  https://llm.api.cloud.yandex.net/foundationModels/v1/completion \
  -H "Authorization: Bearer $YANDEX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "modelUri": "gpt://'"$YANDEX_FOLDER_ID"'/yandexgpt-lite",
    "completionOptions": {
      "stream": false,
      "temperature": 0.7,
      "maxTokens": 100
    },
    "messages": [
      {"role": "user", "text": "Привет!"}
    ]
  }'
```

### Логирование полного запроса

```python
import json

logger.debug(f"Request URL: {url}")
logger.debug(f"Request Headers: {headers}")
logger.debug(f"Request Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
```

## Полезные ссылки

- **Официальная документация:** https://cloud.yandex.ru/docs/foundation-models/
- **API Reference:** https://cloud.yandex.ru/docs/foundation-models/api-ref/
- **Консоль Yandex Cloud:** https://console.cloud.yandex.ru/
- **Pricing:** https://cloud.yandex.ru/docs/foundation-models/pricing
- **Примеры кода:** https://github.com/yandex-cloud/examples

---

**Версия документации:** 1.0
**Дата:** 2025-11-10
**Автор:** AI Challenge 4 Team
