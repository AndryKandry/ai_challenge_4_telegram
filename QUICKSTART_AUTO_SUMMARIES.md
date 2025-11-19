# 🚀 Быстрый старт: Автоматические сводки из Telegram

## За 5 минут до первой сводки!

### 1️⃣ Установите зависимости

```bash
pip install -r requirements.txt
```

### 2️⃣ Настройте .env

```bash
# Скопируйте пример
cp .env.example .env

# Откройте .env и укажите:
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_API_ID=your_api_id          # Получите на https://my.telegram.org/apps
TELEGRAM_API_HASH=your_api_hash
DEEPSEEK_API_KEY=your_deepseek_key
```

### 3️⃣ Запустите MCP сервер

**Терминал 1:**
```bash
python mcp_server/telegram_assistant.py
```

### 4️⃣ Запустите бота

**Терминал 2:**
```bash
python bot.py
```

### 5️⃣ Создайте ассистента в Telegram

Откройте бота и отправьте:
```
/telegram_assistant @your_channel
```

### 🎉 Готово!

Через час вы получите первую сводку!

---

## 📖 Команды

```
/telegram_assistant <chat_id>     # Создать ассистента
/list_assistants                  # Список ассистентов
/stop_assistant <chat>            # Остановить ассистента
/stop_all_assistants confirm      # Остановить все
```

---

## 📚 Документация

- **Полная инструкция:** [docs/FINAL_INTEGRATION_COMPLETE.md](docs/FINAL_INTEGRATION_COMPLETE.md)
- **Техническая документация:** [docs/TELEGRAM_ASSISTANT_IMPLEMENTATION.md](docs/TELEGRAM_ASSISTANT_IMPLEMENTATION.md)
- **Troubleshooting:** [docs/QUICKSTART_TELEGRAM_ASSISTANT.md](docs/QUICKSTART_TELEGRAM_ASSISTANT.md)

---

**Нужна помощь?** Смотрите [docs/FINAL_INTEGRATION_COMPLETE.md](docs/FINAL_INTEGRATION_COMPLETE.md)
