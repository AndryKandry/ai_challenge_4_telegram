# GitHub Integration with DeepSeek

## Быстрый старт

GitHub MCP интеграция доступна **только при использовании DeepSeek** модели.

### 1. Запуск GitHub MCP сервера

```bash
# В отдельном терминале
python mcp_server/github.py
```

Сервер запустится на `http://localhost:8001/sse`

### 2. Запуск Telegram бота

```bash
python bot.py
```

Бот автоматически подключится к GitHub MCP серверу.

### 3. Переключение на DeepSeek

В Telegram отправьте команду:
```
/deepseek
```

### 4. Использование

Теперь можно задавать вопросы о GitHub на естественном языке:

```
"Покажи информацию о пользователе GitHub torvalds"
"Какие репозитории есть у пользователя octocat?"
"Покажи последние 5 коммитов из facebook/react"
"Расскажи о пользователе microsoft и покажи его репозитории"
```

DeepSeek автоматически:
1. Определит необходимость вызова GitHub tools
2. Вызовет нужные инструменты
3. Сформирует ответ на основе данных от GitHub API

## Доступные инструменты

- **get_user_info** - информация о пользователе
- **get_user_repositories** - список репозиториев
- **get_repository_commits** - коммиты репозитория

Подробнее см. [GITHUB_TOOLS.md](GITHUB_TOOLS.md)

## Ограничения

- **Только DeepSeek**: MCP tools доступны только при использовании DeepSeek
- **Rate Limit**: 60 запросов/час к GitHub API (без авторизации)
- **Timeout**: 30 секунд на каждый запрос к GitHub API

## Troubleshooting

### GitHub MCP сервер не подключен

**Проверка:**
```bash
lsof -i:8001  # Должен показать python процесс
```

**Решение:**
```bash
python mcp_server/github.py
```

### DeepSeek не использует tools

**Причины:**
- MCP сервер не запущен
- Не переключились на DeepSeek (`/deepseek`)
- Запрос не требует GitHub данных

**Проверка в логах:**
```
✅ GitHub MCP сервер успешно подключен для DeepSeek
Доступно 3 GitHub MCP tools
```

Подробнее см. [MCP_INTEGRATION.md](MCP_INTEGRATION.md)
