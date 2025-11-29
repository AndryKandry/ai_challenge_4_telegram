# Руководство по началу работы

## Установка и настройка

### Шаг 1: Установка зависимостей

```bash
pip install -r requirements.txt
```

### Шаг 2: Настройка переменных окружения

Создайте файл `.env` в корневой директории проекта:

```env
TELEGRAM_TOKEN=ваш_TELEGRAM_TOKEN
YANDEX_API_KEY=ваш_yandex_api_key
YANDEX_FOLDER_ID=ваш_yandex_folder_id
OPENAI_API_KEY=ваш_openai_api_key
DEEPSEEK_API_KEY=ваш_deepseek_api_key
```

### Шаг 3: Запуск бота

```bash
python bot.py
```

## Первые шаги

1. Найдите вашего бота в Telegram по имени
2. Отправьте команду `/start`
3. Начните общение с ботом

## Переключение между моделями

Для переключения между различными LLM моделями используйте команды:
- `/openai` - переключиться на OpenAI GPT
- `/yandex` - переключиться на Yandex GPT
- `/deepseek` - переключиться на DeepSeek

Выбор модели сохраняется между сессиями для каждого пользователя.
