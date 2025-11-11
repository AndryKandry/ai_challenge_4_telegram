# Интеграция HuggingFace LLM моделей

## Обзор

В проект интегрирован модуль для работы с HuggingFace Inference API, позволяющий использовать различные LLM модели с бесплатным доступом через Inference Providers.

## Выбранные модели

Для проекта были выбраны 3 модели разного уровня популярности и размера:

### 1. Qwen/Qwen2.5-7B-Instruct (Топ-10)
- **URL**: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
- **Размер**: 7.61B параметров (6.53B non-embedding)
- **Категория**: Топ-10 популярных моделей
- **Inference Provider**: Together AI
- **Описание**: Мощная мультиязычная модель от Alibaba Cloud, отлично справляется с различными задачами включая генерацию текста, ответы на вопросы, кодирование.

### 2. meta-llama/Llama-3.2-3B-Instruct (Середина)
- **URL**: https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
- **Размер**: 3.21B параметров
- **Категория**: Середина списка (позиции 50-100)
- **Inference Provider**: Novita
- **Описание**: Компактная версия Llama 3.2 от Meta, оптимизирована для инструкций, хорошо сбалансирована по качеству и скорости.

### 3. microsoft/Phi-3-mini-4k-instruct (Менее популярная)
- **URL**: https://huggingface.co/microsoft/Phi-3-mini-4k-instruct
- **Размер**: 3.8B параметров
- **Категория**: Менее популярная, но качественная
- **Inference Provider**: Azure AI / HuggingFace
- **Описание**: Компактная модель от Microsoft, обученная на высококачественных данных, эффективна для задач с контекстом до 4K токенов.

## Получение API ключа

Для работы с HuggingFace Inference API необходимо получить токен доступа:

1. Зарегистрируйтесь на [HuggingFace](https://huggingface.co/)
2. Перейдите в [настройки токенов](https://huggingface.co/settings/tokens)
3. Создайте новый токен с правами:
   - **Read access to contents of all repos you can access**
   - **Make calls to Inference Providers** (важно!)
4. Скопируйте токен и добавьте в файл `.env`:
   ```bash
   HF_API_KEY=hf_ваш_токен_здесь
   ```

## Архитектура модуля

### Файлы

- `huggingface_client.py` - основной модуль для работы с API
- Зависимости: `huggingface-hub==0.27.0`

### Основные компоненты

#### 1. HuggingFaceClient
Главный класс для работы с HuggingFace API.

**Методы:**
- `generate_response()` - генерация ответа от конкретной модели
- `test_all_models()` - тестирование всех моделей с единым промптом
- `format_metrics_table()` - форматирование результатов в таблицу
- `get_model_info()` - получение информации о доступных моделях

#### 2. ModelMetrics
Dataclass для хранения метрик выполнения запроса:
- `model_name` - название модели
- `model_url` - URL модели на HuggingFace
- `prompt` - исходный запрос
- `response` - ответ модели
- `execution_time` - время выполнения (секунды)
- `input_tokens` - количество входных токенов
- `output_tokens` - количество выходных токенов
- `total_tokens` - общее количество токенов
- `cost` - стоимость (для HF Inference API - "Free")

## Использование

### Базовое использование

```python
from huggingface_client import HuggingFaceClient

# Инициализация клиента (токен берется из .env)
client = HuggingFaceClient()

# Генерация ответа от конкретной модели
metrics = client.generate_response(
    model_key="qwen",  # или "llama", "phi"
    prompt="Объясни простыми словами, что такое машинное обучение",
    max_tokens=300,
    temperature=0.7
)

print(f"Ответ: {metrics.response}")
print(f"Время: {metrics.execution_time:.2f}с")
print(f"Токены: {metrics.total_tokens}")
```

### Тестирование всех моделей

```python
# Единый промпт для всех моделей
prompt = "Объясни простыми словами, что такое квантовая запутанность"

# Запуск тестирования
results = client.test_all_models(prompt=prompt)

# Вывод таблицы с результатами
print(client.format_metrics_table(results))
```

### Запуск из командной строки

```bash
# Активировать виртуальное окружение
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows

# Запустить тестирование
python huggingface_client.py
```

## Особенности HuggingFace Inference API

### Бесплатный tier (Free Tier)

HuggingFace Inference Providers включает бесплатный tier с лимитами:
- **Rate limits**:
  - 30 запросов/минута
  - 60,000 токенов/минута
  - 900 запросов/час
  - 1,000,000 токенов/час
  - 14,400 запросов/день

### Размер моделей
- Serverless Inference API поддерживает модели до 10GB
- Некоторые популярные модели доступны даже если превышают лимит

### Автоматический роутинг
API автоматически выбирает первого доступного провайдера для модели. Можно изменить стратегию:
- `:fastest` - максимальная пропускная способность
- `:cheapest` - минимальная стоимость на токен

## Ограничения и рекомендации

### Лимиты
1. Бесплатный tier имеет ограничения по количеству запросов
2. Модели >10GB могут быть недоступны в serverless режиме
3. Время ожидания ответа зависит от нагрузки на провайдера

### Рекомендации
1. Добавьте паузы между запросами (1-2 секунды)
2. Обрабатывайте ошибки rate limiting (429 код)
3. Для production используйте PRO аккаунт с увеличенными лимитами
4. Кэшируйте результаты для частых запросов

## Переменные окружения

Добавьте в файл `.env`:

```bash
# HuggingFace API Configuration
HF_API_KEY=hf_ваш_токен_здесь
```

## Логирование

Модуль использует стандартный Python logging:
- Уровень: `INFO`
- Логируются все запросы к API
- Логируются метрики (время, токены)
- Ошибки выводятся с полным traceback

Для отладки измените уровень на `DEBUG`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Безопасность

1. **Не коммитьте `.env` файл в репозиторий**
2. Добавьте `.env` в `.gitignore`
3. API токены не выводятся в логи
4. Используйте read-only токены для production

## Дальнейшие улучшения

- [ ] Добавить кэширование результатов
- [ ] Реализовать retry механизм при ошибках
- [ ] Добавить streaming для длинных ответов
- [ ] Интегрировать с Telegram ботом
- [ ] Поддержка пользовательских моделей
- [ ] Метрики качества (BLEU, ROUGE)
- [ ] Автоматическое A/B тестирование моделей

## Ссылки

- [HuggingFace Inference API Documentation](https://huggingface.co/docs/huggingface_hub/package_reference/inference_client)
- [Inference Providers](https://huggingface.co/docs/inference-providers/en/index)
- [Serverless Inference API](https://huggingface.co/docs/api-inference/en/index)
- [HuggingFace Token Settings](https://huggingface.co/settings/tokens)
