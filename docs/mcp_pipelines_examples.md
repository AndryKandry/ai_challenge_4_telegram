# MCP Pipelines Examples - Примеры автоматических пайплайнов

## Обзор

Данная документация содержит примеры автоматических пайплайнов, которые DeepSeek может создавать, используя комбинацию инструментов из различных MCP серверов (GitHub, Filesystem и других).

## Простые пайплайны (один MCP сервер)

### Filesystem MCP

#### Пример 1.1: Чтение и анализ файла

**Запрос пользователя**:
```
Прочитай файл ~/Documents/report.txt и скажи, сколько в нем строк
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call**: `read_file`
   ```json
   {
     "name": "read_file",
     "arguments": {
       "path": "~/Documents/report.txt"
     }
   }
   ```

2. **Результат**: Содержимое файла
3. **Анализ DeepSeek**: Подсчитывает количество строк в полученном тексте
4. **Финальный ответ**: "В файле report.txt содержится 142 строки."

---

#### Пример 1.2: Создание структурированного файла

**Запрос пользователя**:
```
Создай файл ~/todo.txt со списком задач: купить молоко, сделать презентацию, позвонить клиенту
```

**Автоматический пайплайн DeepSeek**:

1. **DeepSeek формирует структурированный список**:
   ```
   TODO LIST
   =========
   [ ] Купить молоко
   [ ] Сделать презентацию
   [ ] Позвонить клиенту
   ```

2. **Tool call**: `write_file`
   ```json
   {
     "name": "write_file",
     "arguments": {
       "path": "~/todo.txt",
       "content": "TODO LIST\n=========\n[ ] Купить молоко\n[ ] Сделать презентацию\n[ ] Позвонить клиенту\n"
     }
   }
   ```

3. **Результат**: Файл создан
4. **Финальный ответ**: "Список задач сохранен в файл ~/todo.txt"

---

#### Пример 1.3: Резервное копирование с редактированием

**Запрос пользователя**:
```
Добавь строку "Обновлено: 2025-11-20" в конец файла ~/Documents/notes.txt
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call**: `read_file` (чтение текущего содержимого)
   ```json
   {
     "name": "read_file",
     "arguments": {
       "path": "~/Documents/notes.txt"
     }
   }
   ```

2. **Результат**: Текущее содержимое файла
3. **DeepSeek добавляет строку**: Старое содержимое + "\nОбновлено: 2025-11-20"

4. **Tool call**: `edit_file` (сохранение с backup)
   ```json
   {
     "name": "edit_file",
     "arguments": {
       "path": "~/Documents/notes.txt",
       "new_content": "<старое содержимое>\nОбновлено: 2025-11-20",
       "create_backup": true
     }
   }
   ```

5. **Результат**: Файл обновлен, создана резервная копия
6. **Финальный ответ**: "Строка добавлена в файл. Резервная копия сохранена."

---

### GitHub MCP

#### Пример 1.4: Информация о пользователе

**Запрос пользователя**:
```
Расскажи о пользователе GitHub torvalds
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call**: `get_user_info`
   ```json
   {
     "name": "get_user_info",
     "arguments": {
       "username": "torvalds"
     }
   }
   ```

2. **Результат**: Детальная информация о пользователе
3. **DeepSeek анализирует и форматирует**: Выделяет ключевую информацию
4. **Финальный ответ**: "Linus Torvalds - создатель Linux и Git. На GitHub с 2011 года, имеет N репозиториев и M подписчиков..."

---

#### Пример 1.5: Поиск популярных репозиториев

**Запрос пользователя**:
```
Покажи топ-5 репозиториев пользователя octocat по количеству звезд
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call**: `get_user_repositories`
   ```json
   {
     "name": "get_user_repositories",
     "arguments": {
       "username": "octocat"
     }
   }
   ```

2. **Результат**: Список репозиториев с информацией о звездах
3. **DeepSeek анализирует**: Сортирует по звездам, берет топ-5
4. **Финальный ответ**: Форматированный список топ-5 репозиториев

---

## Сложные пайплайны (несколько MCP серверов)

### GitHub + Filesystem

#### Пример 2.1: Сохранение информации о пользователе

**Запрос пользователя**:
```
Получи информацию о пользователе GitHub torvalds и сохрани в файл ~/torvalds_info.txt
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call #1**: `get_user_info` (GitHub MCP)
   ```json
   {
     "name": "get_user_info",
     "arguments": {
       "username": "torvalds"
     }
   }
   ```

2. **Результат #1**: Информация о пользователе

3. **DeepSeek форматирует данные** для сохранения:
   ```
   GitHub User Profile: torvalds
   ================================
   Name: Linus Torvalds
   Bio: Creator of Linux and Git
   Location: Portland, OR
   Public Repositories: 6
   Followers: 150,000+
   ...
   ```

4. **Tool call #2**: `write_file` (Filesystem MCP)
   ```json
   {
     "name": "write_file",
     "arguments": {
       "path": "~/torvalds_info.txt",
       "content": "<форматированная информация>"
     }
   }
   ```

5. **Результат #2**: Файл создан

6. **Финальный ответ**: "Информация о пользователе torvalds получена и сохранена в файл ~/torvalds_info.txt"

---

#### Пример 2.2: Отчет по репозиториям

**Запрос пользователя**:
```
Создай отчет о репозиториях пользователя microsoft: названия, звезды, язык. Сохрани в файл ~/microsoft_repos_report.md
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call #1**: `get_user_repositories` (GitHub MCP)
   ```json
   {
     "name": "get_user_repositories",
     "arguments": {
       "username": "microsoft"
     }
   }
   ```

2. **Результат #1**: Список репозиториев (до 30 штук)

3. **DeepSeek создает Markdown отчет**:
   ```markdown
   # Microsoft GitHub Repositories Report

   Generated: 2025-11-20

   ## Top Repositories

   | Repository | Stars | Language | Description |
   |------------|-------|----------|-------------|
   | vscode | 150k+ | TypeScript | Visual Studio Code |
   | TypeScript | 90k+ | TypeScript | TypeScript language |
   ...
   ```

4. **Tool call #2**: `write_file` (Filesystem MCP)
   ```json
   {
     "name": "write_file",
     "arguments": {
       "path": "~/microsoft_repos_report.md",
       "content": "<markdown отчет>"
     }
   }
   ```

5. **Результат #2**: Markdown файл создан

6. **Финальный ответ**: "Отчет о репозиториях Microsoft создан и сохранен в ~/microsoft_repos_report.md"

---

#### Пример 2.3: Архивирование информации о коммитах

**Запрос пользователя**:
```
Получи последние 10 коммитов из репозитория torvalds/linux и сохрани в файл ~/linux_commits.txt
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call #1**: `get_repository_commits` (GitHub MCP)
   ```json
   {
     "name": "get_repository_commits",
     "arguments": {
       "owner": "torvalds",
       "repo": "linux",
       "per_page": 10
     }
   }
   ```

2. **Результат #1**: Список последних 10 коммитов

3. **DeepSeek форматирует для текстового файла**:
   ```
   Linux Kernel - Latest Commits
   =============================

   1. abc1234 - Fix memory leak in driver (Linus Torvalds, 2025-11-19)
   2. def5678 - Update documentation (John Doe, 2025-11-19)
   ...
   ```

4. **Tool call #2**: `write_file` (Filesystem MCP)
   ```json
   {
     "name": "write_file",
     "arguments": {
       "path": "~/linux_commits.txt",
       "content": "<форматированный список коммитов>"
     }
   }
   ```

5. **Результат #2**: Файл создан

6. **Финальный ответ**: "Последние 10 коммитов из torvalds/linux сохранены в ~/linux_commits.txt"

---

#### Пример 2.4: Сравнение пользователей

**Запрос пользователя**:
```
Сравни пользователей GitHub torvalds и gvanrossum (количество репозиториев, подписчики) и сохрани сравнение в файл ~/comparison.txt
```

**Автоматический пайплайн DeepSeek**:

1. **Параллельные tool calls** (GitHub MCP):
   ```json
   [
     {
       "name": "get_user_info",
       "arguments": {"username": "torvalds"}
     },
     {
       "name": "get_user_info",
       "arguments": {"username": "gvanrossum"}
     }
   ]
   ```

2. **Результаты #1**: Информация о обоих пользователях

3. **DeepSeek создает сравнительную таблицу**:
   ```
   GitHub Users Comparison
   =======================

   Metric              | torvalds  | gvanrossum
   --------------------|-----------|------------
   Name                | Linus Torvalds | Guido van Rossum
   Public Repositories | 6         | 25
   Followers           | 150,000+  | 45,000+
   Following           | 0         | 15
   ```

4. **Tool call #3**: `write_file` (Filesystem MCP)
   ```json
   {
     "name": "write_file",
     "arguments": {
       "path": "~/comparison.txt",
       "content": "<сравнительная таблица>"
     }
   }
   ```

5. **Результат #3**: Файл создан

6. **Финальный ответ**: "Сравнение пользователей сохранено в ~/comparison.txt. Torvalds имеет больше подписчиков, но меньше публичных репозиториев."

---

#### Пример 2.5: Обновление существующего отчета

**Запрос пользователя**:
```
Прочитай файл ~/repos_report.txt, добавь в конец информацию о новых репозиториях пользователя facebook и сохрани изменения
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call #1**: `read_file` (Filesystem MCP)
   ```json
   {
     "name": "read_file",
     "arguments": {
       "path": "~/repos_report.txt"
     }
   }
   ```

2. **Результат #1**: Текущее содержимое отчета

3. **Tool call #2**: `get_user_repositories` (GitHub MCP)
   ```json
   {
     "name": "get_user_repositories",
     "arguments": {
       "username": "facebook"
     }
   }
   ```

4. **Результат #2**: Список репозиториев Facebook

5. **DeepSeek объединяет**: Старый отчет + новая секция с репозиториями Facebook

6. **Tool call #3**: `edit_file` (Filesystem MCP)
   ```json
   {
     "name": "edit_file",
     "arguments": {
       "path": "~/repos_report.txt",
       "new_content": "<старый отчет>\n\nFacebook Repositories\n=====================\n<новые репозитории>",
       "create_backup": true
     }
   }
   ```

7. **Результат #3**: Файл обновлен с резервной копией

8. **Финальный ответ**: "Отчет обновлен информацией о репозиториях Facebook. Создана резервная копия."

---

## Продвинутые сценарии

### Пример 3.1: Многошаговая обработка данных

**Запрос пользователя**:
```
Найди топ-3 репозитория пользователя google по звездам, получи информацию о коммитах для каждого, создай сводный отчет и сохрани в ~/google_top_repos.md
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call #1**: `get_user_repositories` (GitHub MCP)
   ```json
   {"name": "get_user_repositories", "arguments": {"username": "google"}}
   ```

2. **DeepSeek анализирует**: Определяет топ-3 по звездам (например: tensorflow, protobuf, flutter)

3. **Параллельные tool calls #2-4**: `get_repository_commits` для каждого репозитория
   ```json
   [
     {"name": "get_repository_commits", "arguments": {"owner": "google", "repo": "tensorflow", "per_page": 5}},
     {"name": "get_repository_commits", "arguments": {"owner": "google", "repo": "protobuf", "per_page": 5}},
     {"name": "get_repository_commits", "arguments": {"owner": "google", "repo": "flutter", "per_page": 5}}
   ]
   ```

4. **DeepSeek создает Markdown отчет**:
   ```markdown
   # Google Top 3 Repositories Analysis

   ## 1. tensorflow (150k+ stars)
   Recent commits:
   - abc123: Fix GPU memory issue
   - def456: Update documentation
   ...

   ## 2. protobuf (60k+ stars)
   Recent commits:
   ...
   ```

5. **Tool call #5**: `write_file` (Filesystem MCP)
   ```json
   {
     "name": "write_file",
     "arguments": {
       "path": "~/google_top_repos.md",
       "content": "<детальный markdown отчет>"
     }
   }
   ```

6. **Финальный ответ**: "Анализ топ-3 репозиториев Google завершен. Отчет сохранен в ~/google_top_repos.md"

---

### Пример 3.2: Навигация и анализ файловой системы

**Запрос пользователя**:
```
Перейди в директорию ~/Documents, покажи список файлов, найди все .txt файлы и создай файл files_list.txt со списком этих файлов
```

**Автоматический пайплайн DeepSeek**:

1. **Tool call #1**: `change_directory` (Filesystem MCP)
   ```json
   {"name": "change_directory", "arguments": {"path": "~/Documents"}}
   ```

2. **Tool call #2**: `list_directory` (Filesystem MCP)
   ```json
   {"name": "list_directory", "arguments": {"path": "."}}
   ```

3. **DeepSeek анализирует результат**: Фильтрует только .txt файлы

4. **DeepSeek создает список**:
   ```
   Text Files in ~/Documents
   =========================
   1. notes.txt (512 B, modified: 2025-11-18)
   2. report.txt (1.2 KB, modified: 2025-11-19)
   3. todo.txt (256 B, modified: 2025-11-20)
   ```

5. **Tool call #3**: `write_file` (Filesystem MCP)
   ```json
   {
     "name": "write_file",
     "arguments": {
       "path": "files_list.txt",
       "content": "<список txt файлов>"
     }
   }
   ```

6. **Финальный ответ**: "Найдено 3 .txt файла в ~/Documents. Список сохранен в files_list.txt"

---

### Пример 3.3: Условная логика

**Запрос пользователя**:
```
Если файл ~/config.txt существует, прочитай его. Если нет - создай с содержимым "Default config"
```

**Автоматический пайплайн DeepSeek** (файл существует):

1. **Tool call #1**: `get_file_info` (Filesystem MCP)
   ```json
   {"name": "get_file_info", "arguments": {"path": "~/config.txt"}}
   ```

2. **Результат #1**: Информация о файле (файл существует)

3. **Tool call #2**: `read_file` (Filesystem MCP)
   ```json
   {"name": "read_file", "arguments": {"path": "~/config.txt"}}
   ```

4. **Финальный ответ**: "Файл config.txt существует. Содержимое: ..."

**Автоматический пайплайн DeepSeek** (файл НЕ существует):

1. **Tool call #1**: `get_file_info` (Filesystem MCP)
   ```json
   {"name": "get_file_info", "arguments": {"path": "~/config.txt"}}
   ```

2. **Результат #1**: Ошибка - файл не существует

3. **Tool call #2**: `write_file` (Filesystem MCP)
   ```json
   {
     "name": "write_file",
     "arguments": {
       "path": "~/config.txt",
       "content": "Default config"
     }
   }
   ```

4. **Финальный ответ**: "Файл config.txt не существовал. Создан с настройками по умолчанию."

---

## Best Practices для эффективных пайплайнов

### 1. Четкие инструкции

**Хорошо**:
```
Получи информацию о пользователе torvalds и сохрани в файл ~/torvalds.txt
```

**Плохо**:
```
Что-нибудь про torvalds в файл
```

### 2. Указание формата

**Хорошо**:
```
Создай Markdown отчет о репозиториях microsoft и сохрани в ~/report.md
```

**Результат**: DeepSeek создаст структурированный Markdown с таблицами

**Плохо**:
```
Какие-то репозитории microsoft в файл
```

**Результат**: Неструктурированный текст

### 3. Явное указание операций

**Хорошо**:
```
Прочитай файл ~/notes.txt, добавь строку "Updated today" и сохрани с резервной копией
```

**Результат**:
- read_file
- edit_file (с create_backup=true)

**Плохо**:
```
Обнови файл ~/notes.txt
```

**Результат**: Неясно, что именно обновить

### 4. Использование относительных путей после change_directory

**Хорошо**:
```
Перейди в ~/Documents, покажи файлы, прочитай файл notes.txt
```

**Результат**:
- change_directory ~/Documents
- list_directory .
- read_file notes.txt (относительный путь)

### 5. Параллельные операции

**Хорошо** (DeepSeek сделает параллельно):
```
Получи информацию о пользователях torvalds и gvanrossum
```

**Результат**: Оба запроса выполняются параллельно

**Плохо** (будет последовательно):
```
Получи информацию о torvalds. Потом получи информацию о gvanrossum.
```

---

## Ограничения и решения

### Ограничение 1: Размер контекста

**Проблема**: Очень большие файлы не поместятся в контекст

**Решение**:
```
Прочитай первые 100 строк файла ~/large_file.txt
```

DeepSeek поймет и запросит только начало файла (если такой функционал будет добавлен в MCP сервер)

### Ограничение 2: Количество tool calls

**Проблема**: Слишком сложные задачи могут требовать много вызовов

**Решение**: Разбить на подзадачи:
```
1. Создай отчет о пользователе torvalds и сохрани в ~/torvalds.txt
2. Создай отчет о пользователе gvanrossum и сохрани в ~/gvanrossum.txt
3. Объедини оба файла в ~/comparison.txt
```

### Ограничение 3: Сложная логика

**Проблема**: DeepSeek может не всегда понять очень сложную логику

**Решение**: Упростить и разбить:
```
Вместо: "Если файл A больше файла B, скопируй A в C, иначе создай новый D"
Лучше: "Проверь размер файлов A и B. Сравни их."
```

---

## Заключение

DeepSeek с MCP инструментами способен:
- ✅ Автоматически создавать сложные пайплайны из простых запросов
- ✅ Комбинировать инструменты из разных MCP серверов
- ✅ Выполнять последовательные и параллельные операции
- ✅ Применять условную логику
- ✅ Форматировать и структурировать данные
- ✅ Обрабатывать ошибки и предлагать альтернативы

Ключ к успешным пайплайнам - **четкие, конкретные инструкции** и **понимание возможностей доступных инструментов**.
