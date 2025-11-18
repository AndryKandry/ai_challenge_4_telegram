#!/bin/bash
# Скрипт для запуска Weather MCP сервера и Telegram бота

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Запуск Weather MCP системы...${NC}\n"

# Путь к виртуальному окружению
VENV_PYTHON=".venv/bin/python"

# Проверка виртуального окружения
if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${RED}❌ Ошибка: Виртуальное окружение не найдено${NC}"
    echo "Создайте виртуальное окружение: python -m venv .venv"
    echo "Активируйте и установите зависимости: .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Функция для остановки процессов при завершении скрипта
cleanup() {
    echo -e "\n${BLUE}🛑 Остановка серверов...${NC}"
    kill $SERVER_PID 2>/dev/null
    kill $BOT_PID 2>/dev/null
    exit 0
}

# Установка обработчика сигналов
trap cleanup SIGINT SIGTERM

# Запуск Weather MCP сервера
echo -e "${BLUE}📦 Запуск Weather MCP сервера...${NC}"
$VENV_PYTHON mcp_server/weather.py &
SERVER_PID=$!

# Ждем запуска сервера
sleep 3

# Проверка, что сервер запустился
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${RED}❌ Ошибка: Weather MCP сервер не запустился${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Weather MCP сервер запущен (PID: $SERVER_PID)${NC}"
echo -e "${BLUE}   URL: http://127.0.0.1:8000/sse${NC}\n"

# Запуск Telegram бота
echo -e "${BLUE}🤖 Запуск Telegram бота...${NC}"
$VENV_PYTHON bot.py &
BOT_PID=$!

# Ждем запуска бота
sleep 2

# Проверка, что бот запустился
if ! kill -0 $BOT_PID 2>/dev/null; then
    echo -e "${RED}❌ Ошибка: Telegram бот не запустился${NC}"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✅ Telegram бот запущен (PID: $BOT_PID)${NC}\n"

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🎉 Система успешно запущена!          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo -e "\n${BLUE}Для остановки нажмите Ctrl+C${NC}\n"

# Ожидание завершения процессов
wait
