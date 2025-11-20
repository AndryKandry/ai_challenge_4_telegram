# MCP Security - Безопасность и ограничения

## Обзор

Данная документация описывает политики безопасности, ограничения и best practices для безопасной работы с MCP серверами, особенно Filesystem MCP, который имеет прямой доступ к файловой системе компьютера.

---

## Общие принципы безопасности

### Принцип наименьших привилегий

MCP серверы должны иметь доступ **только** к тем ресурсам, которые необходимы для их работы:

- ✅ Filesystem MCP: Доступ к пользовательским файлам в домашней директории
- ❌ Filesystem MCP: Доступ к системным директориям (`/etc`, `/sys`, и т.д.)

### Defense in Depth

Безопасность обеспечивается на нескольких уровнях:

1. **Валидация входных данных** - проверка всех параметров инструментов
2. **Ограничения доступа** - blacklist/whitelist путей
3. **Ограничения ресурсов** - лимиты на размеры файлов, количество операций
4. **Логирование** - аудит всех операций
5. **Обработка ошибок** - graceful degradation без раскрытия чувствительной информации

---

## Filesystem MCP Server: Политики безопасности

### 1. Валидация путей

#### Функция validate_path()

**Что делает**:
1. Расширяет тильду (`~`) до полного пути
2. Преобразует относительные пути в абсолютные
3. Разрешает символические ссылки (`resolve()`)
4. Проверяет путь на принадлежность к запрещенным директориям

**Код**:
```python
def validate_path(path_str: str) -> tuple[bool, str, Optional[Path]]:
    # 1. Расширение тильды
    if path_str.startswith('~'):
        path_str = os.path.expanduser(path_str)

    # 2. Создание Path объекта
    path = Path(path_str)

    # 3. Преобразование относительных путей
    if not path.is_absolute():
        path = current_working_directory / path

    # 4. Разрешение symlinks и относительных компонентов
    resolved_path = path.resolve(strict=False)

    # 5. Проверка на запрещенные директории
    forbidden_paths = [
        Path('/etc'), Path('/sys'), Path('/proc'),
        Path('/dev'), Path('/boot')
    ]

    for forbidden in forbidden_paths:
        if resolved_path == forbidden or forbidden in resolved_path.parents:
            return False, f"Доступ к системной директории запрещен", None

    return True, "", resolved_path
```

**Защита от атак**:

- **Path Traversal** (`../../etc/passwd`):
  - `resolve()` преобразует в абсолютный путь
  - Проверка на `forbidden_paths` блокирует доступ

- **Symlink Escape** (создание symlink на `/etc/passwd`):
  - `resolve()` следует по symlink
  - Финальный путь проверяется на `forbidden_paths`

- **Null Byte Injection** (`file.txt\x00.jpg`):
  - Path автоматически обрабатывает некорректные символы
  - Ошибка при попытке доступа к несуществующему файлу

---

### 2. Защищенные директории (Blacklist)

#### Системные директории Linux/macOS

```python
forbidden_paths = [
    Path('/etc'),      # Конфигурационные файлы системы
    Path('/sys'),      # Системные файлы ядра
    Path('/proc'),     # Информация о процессах
    Path('/dev'),      # Файлы устройств
    Path('/boot'),     # Загрузчик системы
    Path('/root'),     # Домашняя директория root
    Path('/var/log'),  # Системные логи (опционально)
]
```

#### Системные директории Windows (рекомендуется добавить)

```python
forbidden_paths.extend([
    Path('C:/Windows'),        # Системная директория Windows
    Path('C:/Program Files'),  # Программы
    Path('C:/System Volume Information'),
])
```

#### Чувствительные файлы (опционально)

```python
forbidden_files = [
    '.ssh/id_rsa',           # SSH приватные ключи
    '.aws/credentials',      # AWS credentials
    '.env',                  # Environment variables (может содержать секреты)
    'credentials.json',      # Различные credentials
]
```

---

### 3. Ограничения размеров

#### Чтение файлов

```python
MAX_FILE_SIZE_READ = 10 * 1024 * 1024  # 10 MB
```

**Проверка**:
```python
file_size = resolved_path.stat().st_size
if file_size > MAX_FILE_SIZE_READ:
    return f"Файл слишком большой ({format_file_size(file_size)})"
```

**Защита от**:
- Out of Memory (OOM) атак
- DoS через чтение огромных файлов
- Случайного чтения бинарных/медиа файлов

#### Запись/редактирование файлов

```python
MAX_FILE_SIZE_WRITE = 5 * 1024 * 1024  # 5 MB
```

**Проверка**:
```python
content_size = len(content.encode(encoding))
if content_size > MAX_FILE_SIZE_WRITE:
    return f"Содержимое слишком большое"
```

**Защита от**:
- Disk space exhaustion
- Случайного создания огромных файлов
- DoS атак

---

### 4. Фильтрация бинарных файлов

#### Определение по расширению

```python
binary_extensions = {
    '.exe', '.dll', '.so', '.dylib', '.bin',  # Исполняемые
    '.zip', '.tar', '.gz', '.rar', '.7z',     # Архивы
    '.jpg', '.jpeg', '.png', '.gif', '.bmp',  # Изображения
    '.mp3', '.mp4', '.avi', '.mkv',          # Медиа
    '.pdf', '.doc', '.docx',                  # Документы
}
```

**Проверка**:
```python
if resolved_path.suffix.lower() in binary_extensions:
    return "Файл является бинарным. Чтение бинарных файлов не поддерживается."
```

**Защита от**:
- Попытки чтения исполняемых файлов
- Чтения бессмысленного контента (изображения, видео)
- Потенциальных уязвимостей при парсинге бинарных данных

---

### 5. Обработка кодировок

#### Поддерживаемые кодировки

```python
ALLOWED_ENCODINGS = ['utf-8', 'cp1251', 'latin-1', 'ascii']
```

**Проверка**:
```python
if encoding not in ALLOWED_ENCODINGS:
    return f"Неподдерживаемая кодировка. Разрешены: {', '.join(ALLOWED_ENCODINGS)}"
```

**Обработка ошибок декодирования**:
```python
try:
    content = resolved_path.read_text(encoding=encoding)
except UnicodeDecodeError:
    return f"Не удалось прочитать файл с кодировкой '{encoding}'. " \
           f"Возможно, файл бинарный или используется другая кодировка."
```

**Защита от**:
- Попыток использования экзотических/небезопасных кодировок
- Крашей при декодировании бинарных данных как текста
- Injection атак через некорректные кодировки

---

### 6. Резервные копии при редактировании

#### Автоматический backup

```python
if create_backup:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = resolved_path.with_suffix(f".{timestamp}.backup{resolved_path.suffix}")
    shutil.copy2(resolved_path, backup_path)
```

**Формат**: `filename.20251120_153045.backup.txt`

**Защита от**:
- Случайной потери данных при редактировании
- Ошибок в логике редактирования
- Возможность rollback после проблемных изменений

#### Восстановление из backup

```python
except Exception as e:
    if backup_path and backup_path.exists():
        try:
            shutil.copy2(backup_path, resolved_path)
            return f"Ошибка: {e}. Файл восстановлен из резервной копии."
        except:
            pass
```

---

### 7. Логирование и аудит

#### Уровни логирования

```python
logger.info(f"list_directory: {path}")
logger.info(f"list_directory успешно: {len(items)} элементов")
logger.error(f"Ошибка при чтении директории: {e}", exc_info=True)
```

**Что логируется**:
- Все вызовы инструментов с параметрами
- Результаты выполнения (успех/ошибка)
- Детали ошибок (stack trace для отладки)
- Валидация путей (DEBUG уровень)

**Что НЕ логируется**:
- Содержимое файлов (может содержать секреты)
- Чувствительные пути целиком (только имена файлов)

#### Формат логов

```
2025-11-20 15:30:45 - __main__ - INFO - read_file: ~/config.txt (encoding: utf-8)
2025-11-20 15:30:45 - __main__ - INFO - read_file успешно: 512 символов
```

**Использование для аудита**:
- Отслеживание всех операций с файлами
- Расследование инцидентов безопасности
- Мониторинг необычной активности

---

## GitHub MCP Server: Политики безопасности

### 1. Rate Limiting

#### GitHub API Limits

- **Без авторизации**: 60 запросов/час
- **С авторизацией**: 5000 запросов/час

**Обработка**:
```python
remaining = response.headers.get("X-RateLimit-Remaining")
limit = response.headers.get("X-RateLimit-Limit")
if remaining:
    logger.debug(f"GitHub API Rate Limit: {remaining}/{limit}")
```

**При превышении**:
```python
if status_code == 403:
    reset_time = e.response.headers.get("X-RateLimit-Reset")
    return {
        "error": "rate_limit",
        "message": f"Превышен лимит запросов. Reset time: {reset_time}"
    }
```

### 2. Timeout защита

```python
REQUEST_TIMEOUT = 30.0  # секунды

response = await client.get(url, timeout=REQUEST_TIMEOUT)
```

**Защита от**:
- Зависания при недоступности GitHub
- DoS через медленные запросы
- Накопления pending requests

### 3. Валидация входных данных

```python
if per_page < 1 or per_page > 100:
    return "Параметр per_page должен быть от 1 до 100."

if page < 1:
    return "Параметр page должен быть больше 0."
```

**Защита от**:
- Некорректных параметров
- Попыток получения слишком большого объема данных
- Injection атак

---

## DeepSeek Provider: Безопасность интеграции

### 1. Изоляция MCP клиентов

Каждый MCP клиент работает независимо:

```python
for mcp_client in self.mcp_clients:
    if mcp_client and mcp_client.is_connected():
        # Проверка, есть ли у этого клиента данный tool
        client_tools = await mcp_client.list_tools()
        if tool_name in tool_names:
            result = await mcp_client.call_tool(tool_name, tool_args)
            break
```

**Защита от**:
- Cross-contamination между MCP серверами
- Утечки данных между различными серверами
- Cascade failures (один сервер не влияет на другие)

### 2. Валидация tool calls

```python
try:
    tool_args = json.loads(tool_args_str)
except json.JSONDecodeError as e:
    error_msg = f"Ошибка парсинга аргументов tool {tool_name}: {e}"
    results.append((tool_call_id, tool_name, f"❌ {error_msg}"))
```

**Защита от**:
- Некорректных JSON в tool_calls
- Injection атак через аргументы
- Крашей при парсинге

### 3. Graceful degradation

```python
if not tool_executed:
    error_msg = f"MCP клиент с tool '{tool_name}' не найден"
    results.append((tool_call_id, tool_name, f"❌ {error_msg}"))
```

**Преимущества**:
- Бот продолжает работать, даже если MCP сервер недоступен
- Информативные сообщения об ошибках пользователю
- Нет cascade failures

---

## Расширенные меры безопасности

### 1. Whitelist подход (альтернатива blacklist)

Вместо запрещения определенных путей, можно разрешить только определенные:

```python
# В будущей версии
ALLOWED_BASE_PATHS = [
    Path.home(),           # Домашняя директория пользователя
    Path('/tmp'),          # Временные файлы
    Path('/var/tmp'),      # Временные файлы
]

def validate_path_whitelist(path: Path) -> bool:
    """Проверка, что путь находится внутри разрешенных директорий."""
    for allowed_base in ALLOWED_BASE_PATHS:
        try:
            path.relative_to(allowed_base)
            return True
        except ValueError:
            continue
    return False
```

### 2. Ограничение количества операций

```python
# В будущей версии
class RateLimiter:
    def __init__(self, max_calls_per_minute=60):
        self.max_calls = max_calls_per_minute
        self.calls = []

    def check_limit(self) -> bool:
        now = time.time()
        # Удаляем вызовы старше 1 минуты
        self.calls = [t for t in self.calls if now - t < 60]

        if len(self.calls) >= self.max_calls:
            return False

        self.calls.append(now)
        return True
```

**Применение**:
```python
rate_limiter = RateLimiter(max_calls_per_minute=60)

@mcp.tool()
async def read_file(path: str):
    if not rate_limiter.check_limit():
        return "❌ Превышен лимит запросов. Попробуйте позже."
    # ... остальной код
```

### 3. Проверка прав доступа

```python
def check_permissions(path: Path, mode: str) -> bool:
    """Проверка прав доступа текущего пользователя."""
    if mode == 'read':
        return os.access(path, os.R_OK)
    elif mode == 'write':
        return os.access(path, os.W_OK)
    elif mode == 'execute':
        return os.access(path, os.X_OK)
    return False
```

**Применение перед операциями**:
```python
if not os.access(resolved_path, os.R_OK):
    return f"❌ Нет прав на чтение файла: {resolved_path}"
```

### 4. Sandboxing (для production)

Для production среды рекомендуется запускать MCP серверы в изолированной среде:

**Docker контейнер**:
```dockerfile
FROM python:3.11-slim

# Создание непривилегированного пользователя
RUN useradd -m -u 1000 mcpuser

# Ограничение доступных директорий
VOLUME /home/mcpuser/data

USER mcpuser
WORKDIR /home/mcpuser

# Запуск MCP сервера
CMD ["python", "mcp_server/filesystem.py"]
```

**Chroot jail** (Linux):
```bash
# Создание изолированной среды
mkdir -p /var/mcp_jail/{bin,lib,lib64,home}
cp /usr/bin/python3 /var/mcp_jail/bin/
# ... копирование необходимых библиотек

# Запуск в chroot
chroot /var/mcp_jail /bin/python3 mcp_server/filesystem.py
```

---

## Мониторинг и алертинг

### 1. Метрики для мониторинга

```python
# Счетчики операций
filesystem_operations = {
    'read_file': 0,
    'write_file': 0,
    'edit_file': 0,
    'list_directory': 0,
    'errors': 0
}

# Обновление при каждой операции
filesystem_operations['read_file'] += 1
```

### 2. Подозрительная активность

**Сигналы для алерта**:
- Попытки доступа к запрещенным директориям (> 5 раз в минуту)
- Частые ошибки permission denied
- Попытки чтения очень больших файлов
- Необычно большое количество операций записи

**Логирование подозрительной активности**:
```python
if "forbidden" in error_msg.lower():
    logger.warning(f"SECURITY: Попытка доступа к запрещенной директории: {path}")
```

---

## Best Practices

### Для разработчиков

1. **Всегда валидировать входные данные** - не доверяйте никаким входным параметрам
2. **Использовать whitelist вместо blacklist** где возможно
3. **Логировать все операции** для аудита
4. **Тестировать edge cases** - пустые строки, null bytes, очень длинные пути
5. **Обновлять зависимости** - регулярно обновлять MCP SDK и другие библиотеки

### Для администраторов

1. **Запускать MCP серверы от непривилегированного пользователя**
2. **Ограничивать сетевой доступ** - только localhost, если не требуется remote доступ
3. **Настроить файрволл** - разрешить только необходимые порты
4. **Мониторить логи** - автоматическое обнаружение подозрительной активности
5. **Регулярные backup** - особенно для критичных данных

### Для пользователей

1. **Не давать доступ к системным директориям** через конфигурацию
2. **Проверять backup файлы** перед удалением
3. **Использовать отдельную директорию** для работы с MCP (например, `~/mcp_workspace`)
4. **Не хранить секреты в plaintext файлах** в доступных директориях
5. **Регулярно проверять логи** на необычную активность

---

## Чеклист безопасности

### Перед деплоем

- [ ] Проверена валидация всех входных параметров
- [ ] Настроены ограничения размеров файлов
- [ ] Определены запрещенные директории
- [ ] Логирование всех операций работает
- [ ] Обработка ошибок не раскрывает чувствительную информацию
- [ ] MCP сервер запускается от непривилегированного пользователя
- [ ] Настроен firewall (только localhost или нужные IP)
- [ ] Регулярные backup критичных данных
- [ ] Мониторинг и алертинг настроены
- [ ] Протестированы основные атаки (path traversal, injection)

### Регулярный аудит

- [ ] Проверка логов на подозрительную активность
- [ ] Обновление зависимостей (MCP SDK, библиотек)
- [ ] Проверка списка запрещенных директорий (актуален ли)
- [ ] Проверка ограничений (размеры файлов актуальны)
- [ ] Тестирование restore из backup

---

## Известные уязвимости и патчи

### CVE-подобные проблемы (гипотетические примеры)

**Проблема 1**: Symlink escape через `change_directory`

**Описание**: Пользователь мог создать symlink в разрешенной директории, указывающий на `/etc`, затем сделать `change_directory` в symlink.

**Решение**: Добавлена проверка resolved path после resolve() в validate_path()

**Версия исправления**: v1.0.0

---

**Проблема 2**: Race condition при создании backup

**Описание**: Между чтением файла и созданием backup файл мог измениться другим процессом.

**Решение**: Использование `shutil.copy2()` с atomic operations

**Версия исправления**: v1.0.0

---

## Reporting Security Issues

Если вы обнаружили уязвимость безопасности:

1. **НЕ публикуйте** в публичных issue trackers
2. **Отправьте email** на security@yourproject.com
3. **Опишите** проблему, шаги для воспроизведения, потенциальное воздействие
4. **Дайте время** на исправление (responsible disclosure - 90 дней)

---

## Заключение

Безопасность MCP серверов - это многоуровневая задача, требующая:

- ✅ Валидации на уровне входных данных
- ✅ Ограничений доступа (blacklist/whitelist)
- ✅ Ограничений ресурсов (размеры, rate limiting)
- ✅ Подробного логирования и аудита
- ✅ Graceful degradation и обработки ошибок
- ✅ Регулярного мониторинга и обновлений

Следование этим принципам обеспечит безопасную работу с MCP серверами в production среде.
