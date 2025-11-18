# Quick Start Guide: GitHub Integration с DeepSeek

## 📋 Предварительные требования

- Python 3.10+
- Установленные зависимости (`pip install -r requirements.txt`)
- DEEPSEEK_API_KEY в .env файле
- TELEGRAM_TOKEN в .env файле

## 🚀 Запуск за 3 шага

### Шаг 1: Запустить GitHub MCP сервер

```bash
# Терминал 1
python mcp_server/github.py
```

Вы должны увидеть:
```
╭──────────────────────────────────────────────────────────────╮
│                         FastMCP 2.13.1                        │
│                  🖥  Server name: github                       │
│                  📦 Transport:   SSE                           │
│                  🔗 Server URL:  http://127.0.0.1:8001/sse    │
╰──────────────────────────────────────────────────────────────╯
```

### Шаг 2: Запустить Telegram бота

```bash
# Терминал 2
python bot.py
```

Вы должны увидеть:
```
✅ GitHub MCP сервер успешно подключен для DeepSeek
Доступно 3 GitHub MCP tools: ['get_user_repositories', 'get_user_info', 'get_repository_commits']
```

### Шаг 3: Использовать в Telegram

1. Найдите своего бота в Telegram
2. Отправьте `/deepseek` для переключения на DeepSeek
3. Начните задавать вопросы о GitHub:

```
"Покажи информацию о пользователе torvalds"
"Какие репозитории есть у octocat?"
"Покажи последние коммиты в facebook/react"
```

## ✅ Проверка работоспособности

### Тест MCP сервера

```bash
python test_github_mcp.py
```

Должны пройти все 4 теста:
- ✅ Подключение к серверу
- ✅ Получение списка tools (3 инструмента)
- ✅ get_user_info для octocat
- ✅ get_user_repositories для octocat
- ✅ get_repository_commits для torvalds/linux
- ✅ Обработка ошибки 404

### Проверка логов бота

```bash
tail -f bot_test.log
```

Ищите строки:
```
GitHub MCP клиент создан для DeepSeek Provider
✅ GitHub MCP сервер успешно подключен для DeepSeek
DeepSeek запросил вызов N инструментов
Tool <имя> выполнен успешно
```

## 🐛 Troubleshooting

### MCP сервер не запускается

**Проблема:**
```
Address already in use: 8001
```

**Решение:**
```bash
# Найти процесс на порту 8001
lsof -i:8001

# Убить процесс
kill -9 <PID>

# Или использовать другой порт
python mcp_server/github.py  # изменить порт в коде
```

### Бот не подключается к MCP серверу

**Проблема:**
```
❌ Не удалось подключиться к GitHub MCP серверу
```

**Решение:**
1. Убедитесь что MCP сервер запущен (`lsof -i:8001`)
2. Проверьте что порт 8001 доступен
3. Перезапустите оба процесса

### DeepSeek не использует tools

**Возможные причины:**
- Не переключились на DeepSeek (`/deepseek`)
- MCP клиент не подключен (проверьте логи)
- Вопрос не требует GitHub данных

**Проверка:**
```bash
# В логах должно быть:
grep "MCP Tools доступны" bot_test.log
grep "DeepSeek запросил вызов" bot_test.log
```

### GitHub API timeout

**Проблема:**
```
❌ Ошибка: Превышено время ожидания ответа от GitHub API (30 сек)
```

**Причины:**
- Проблемы с интернет соединением
- GitHub API недоступен
- Rate limit exceeded

**Решение:**
- Проверьте интернет соединение
- Попробуйте позже
- Проверьте статус GitHub: https://www.githubstatus.com/

## 📚 Полезные команды

```bash
# Проверка зависимостей
pip list | grep -E "mcp|fastmcp|httpx"

# Просмотр логов в реальном времени
tail -f bot_test.log

# Проверка портов
lsof -i:8001  # GitHub MCP
lsof -i:8000  # Weather MCP (если запущен)

# Остановка всех процессов
pkill -f "python.*mcp_server"
pkill -f "python.*bot.py"
```

## 📖 Дополнительная документация

- [GITHUB_TOOLS.md](docs/GITHUB_TOOLS.md) - Описание всех GitHub tools
- [GITHUB_INTEGRATION.md](docs/GITHUB_INTEGRATION.md) - Быстрый старт
- [MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) - Техническая документация
- [README.md](README.md) - Основная документация проекта

## 🎯 Примеры запросов

### Простые запросы
```
"Покажи информацию о пользователе octocat"
"Какие репозитории у torvalds?"
"Последние коммиты в microsoft/vscode"
```

### Комплексные запросы (множественные tool calls)
```
"Расскажи о пользователе microsoft и покажи его топ репозитории"
"Сравни количество репозиториев у facebook и google"
"Покажи профиль torvalds, его репозитории и последние коммиты в linux"
```

### На английском
```
"Show me information about user golang"
"What repositories does kubernetes have?"
"Show recent commits in tensorflow/tensorflow"
```

---

**Готово! 🎉** Теперь вы можете использовать GitHub integration с DeepSeek!
