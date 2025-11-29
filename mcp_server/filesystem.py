#!/usr/bin/env python3
"""
Filesystem MCP Server - предоставляет инструменты для работы с файловой системой
через Model Context Protocol.

Реализованные инструменты:
- list_directory: вывод содержимого указанной папки
- change_directory: навигация по файловой системе
- read_file: чтение содержимого файла
- write_file: создание нового файла
- edit_file: редактирование существующего файла
- get_file_info: получение метаданных файла

Безопасность:
- Валидация путей для предотвращения path traversal атак
- Ограничение размера читаемых/записываемых файлов
- Логирование всех операций
"""

from typing import Any, Optional
from pathlib import Path
import os
import shutil
from datetime import datetime
from fastmcp import FastMCP
import logging

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы безопасности
MAX_FILE_SIZE_READ = 10 * 1024 * 1024  # 10 MB для чтения
MAX_FILE_SIZE_WRITE = 5 * 1024 * 1024  # 5 MB для записи
ALLOWED_ENCODINGS = ['utf-8', 'cp1251', 'latin-1', 'ascii']

# Текущая рабочая директория (для change_directory)
# Используется глобальная переменная для отслеживания текущей директории
current_working_directory = Path.home()

# Создание MCP сервера
mcp = FastMCP("filesystem")


def validate_path(path_str: str) -> tuple[bool, str, Optional[Path]]:
    """
    Валидация пути для предотвращения path traversal атак.

    Args:
        path_str: Строка с путем

    Returns:
        Кортеж (is_valid, error_message, resolved_path)
        - is_valid: True если путь валиден
        - error_message: Сообщение об ошибке (пустая строка если нет ошибки)
        - resolved_path: Разрешенный абсолютный путь или None
    """
    try:
        # Обработка тильды (~) для домашней директории
        if path_str.startswith('~'):
            path_str = os.path.expanduser(path_str)

        # Создаем Path объект
        path = Path(path_str)

        # Если путь относительный, разрешаем его относительно current_working_directory
        if not path.is_absolute():
            path = current_working_directory / path

        # Разрешаем путь (resolve symlinks и относительные части)
        try:
            resolved_path = path.resolve(strict=False)
        except (OSError, RuntimeError) as e:
            return False, f"Невозможно разрешить путь: {e}", None

        # Проверка на системные директории (базовая защита)
        # Список запрещенных директорий можно расширить
        forbidden_paths = [
            Path('/etc'),
            Path('/sys'),
            Path('/proc'),
            Path('/dev'),
            Path('/boot')
        ]

        for forbidden in forbidden_paths:
            try:
                if resolved_path == forbidden or forbidden in resolved_path.parents:
                    return False, f"Доступ к системной директории '{forbidden}' запрещен", None
            except ValueError:
                # На Windows может возникнуть ValueError при сравнении путей с разных дисков
                pass

        logger.debug(f"Путь валидирован: {path_str} -> {resolved_path}")
        return True, "", resolved_path

    except Exception as e:
        logger.error(f"Ошибка валидации пути '{path_str}': {e}")
        return False, f"Ошибка валидации пути: {e}", None


def format_file_size(size_bytes: int) -> str:
    """Форматирование размера файла в человекочитаемый вид."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_file_permissions(mode: int) -> str:
    """Форматирование прав доступа файла."""
    permissions = []
    permissions.append('r' if mode & 0o400 else '-')
    permissions.append('w' if mode & 0o200 else '-')
    permissions.append('x' if mode & 0o100 else '-')
    permissions.append('r' if mode & 0o040 else '-')
    permissions.append('w' if mode & 0o020 else '-')
    permissions.append('x' if mode & 0o010 else '-')
    permissions.append('r' if mode & 0o004 else '-')
    permissions.append('w' if mode & 0o002 else '-')
    permissions.append('x' if mode & 0o001 else '-')
    return ''.join(permissions)


@mcp.tool()
async def list_directory(path: str = ".") -> str:
    """
    Вывод содержимого указанной папки.

    Args:
        path: Путь к директории (по умолчанию текущая директория)

    Returns:
        Список файлов и поддиректорий с метаинформацией или сообщение об ошибке
    """
    logger.info(f"list_directory: {path}")

    # Валидация пути
    is_valid, error_msg, resolved_path = validate_path(path)
    if not is_valid:
        return f"❌ Ошибка валидации пути: {error_msg}"

    # Проверка существования
    if not resolved_path.exists():
        return f"❌ Путь не существует: {resolved_path}"

    # Проверка что это директория
    if not resolved_path.is_dir():
        return f"❌ Путь не является директорией: {resolved_path}"

    # Проверка прав доступа
    if not os.access(resolved_path, os.R_OK):
        return f"❌ Нет прав на чтение директории: {resolved_path}"

    try:
        # Получаем список элементов
        items = []
        for item in sorted(resolved_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat_info = item.stat()
                item_type = "📁 DIR " if item.is_dir() else "📄 FILE"
                size = format_file_size(stat_info.st_size) if item.is_file() else "---"
                mtime = datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                items.append(f"{item_type} | {size:>10} | {mtime} | {item.name}")
            except (OSError, PermissionError) as e:
                items.append(f"❌ ERROR | {'---':>10} | {'---':^19} | {item.name} (Ошибка доступа)")

        if not items:
            result = f"📂 Директория пуста: {resolved_path}\n"
        else:
            result = f"📂 Содержимое директории: {resolved_path}\n"
            result += f"Всего элементов: {len(items)}\n"
            result += "=" * 80 + "\n"
            result += f"{'Тип':^10} | {'Размер':>10} | {'Дата изменения':^19} | Имя\n"
            result += "-" * 80 + "\n"
            result += "\n".join(items)

        logger.info(f"list_directory успешно: {len(items)} элементов")
        return result

    except PermissionError:
        return f"❌ Нет прав доступа к директории: {resolved_path}"
    except Exception as e:
        logger.error(f"Ошибка при чтении директории: {e}", exc_info=True)
        return f"❌ Ошибка при чтении директории: {e}"


@mcp.tool()
async def change_directory(path: str) -> str:
    """
    Навигация по файловой системе (смена текущей рабочей директории).

    Args:
        path: Целевой путь (абсолютный или относительный, поддерживается . и ..)

    Returns:
        Подтверждение смены директории и текущий путь
    """
    global current_working_directory

    logger.info(f"change_directory: {path}")

    # Валидация пути
    is_valid, error_msg, resolved_path = validate_path(path)
    if not is_valid:
        return f"❌ Ошибка валидации пути: {error_msg}"

    # Проверка существования
    if not resolved_path.exists():
        return f"❌ Путь не существует: {resolved_path}"

    # Проверка что это директория
    if not resolved_path.is_dir():
        return f"❌ Путь не является директорией: {resolved_path}"

    # Проверка прав доступа
    if not os.access(resolved_path, os.R_OK | os.X_OK):
        return f"❌ Нет прав доступа к директории: {resolved_path}"

    # Сохраняем старую директорию для логирования
    old_directory = current_working_directory

    # Меняем текущую директорию
    current_working_directory = resolved_path

    logger.info(f"Директория изменена: {old_directory} -> {current_working_directory}")

    return f"✅ Текущая директория изменена:\n📂 {current_working_directory}"


@mcp.tool()
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """
    Чтение содержимого файла.

    Args:
        path: Путь к файлу
        encoding: Кодировка файла (по умолчанию utf-8, также поддерживается cp1251, latin-1, ascii)

    Returns:
        Содержимое файла или сообщение об ошибке
    """
    logger.info(f"read_file: {path} (encoding: {encoding})")

    # Проверка кодировки
    if encoding not in ALLOWED_ENCODINGS:
        return f"❌ Неподдерживаемая кодировка. Разрешены: {', '.join(ALLOWED_ENCODINGS)}"

    # Валидация пути
    is_valid, error_msg, resolved_path = validate_path(path)
    if not is_valid:
        return f"❌ Ошибка валидации пути: {error_msg}"

    # Проверка существования
    if not resolved_path.exists():
        return f"❌ Файл не существует: {resolved_path}"

    # Проверка что это файл
    if not resolved_path.is_file():
        return f"❌ Путь не является файлом: {resolved_path}"

    # Проверка прав доступа
    if not os.access(resolved_path, os.R_OK):
        return f"❌ Нет прав на чтение файла: {resolved_path}"

    # Проверка размера файла
    file_size = resolved_path.stat().st_size
    if file_size > MAX_FILE_SIZE_READ:
        return f"❌ Файл слишком большой ({format_file_size(file_size)}). Максимум: {format_file_size(MAX_FILE_SIZE_READ)}"

    # Попытка определить бинарный файл по расширению
    binary_extensions = {'.exe', '.dll', '.so', '.dylib', '.bin', '.dat', '.zip', '.tar', '.gz',
                        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.mp3', '.mp4', '.avi', '.pdf'}
    if resolved_path.suffix.lower() in binary_extensions:
        return f"❌ Файл '{resolved_path.name}' является бинарным. Чтение бинарных файлов не поддерживается."

    try:
        # Чтение файла
        content = resolved_path.read_text(encoding=encoding)

        logger.info(f"read_file успешно: {len(content)} символов")

        result = f"📄 Файл: {resolved_path}\n"
        result += f"Размер: {format_file_size(file_size)}\n"
        result += f"Кодировка: {encoding}\n"
        result += "=" * 80 + "\n"
        result += content

        return result

    except UnicodeDecodeError:
        # Файл не может быть прочитан с указанной кодировкой
        return f"❌ Не удалось прочитать файл с кодировкой '{encoding}'. Возможно, файл бинарный или используется другая кодировка. Попробуйте: {', '.join([e for e in ALLOWED_ENCODINGS if e != encoding])}"

    except PermissionError:
        return f"❌ Нет прав доступа к файлу: {resolved_path}"

    except Exception as e:
        logger.error(f"Ошибка при чтении файла: {e}", exc_info=True)
        return f"❌ Ошибка при чтении файла: {e}"


@mcp.tool()
async def write_file(path: str, content: str, overwrite: bool = False, encoding: str = "utf-8") -> str:
    """
    Создание нового файла с указанным содержимым.

    Args:
        path: Путь к файлу
        content: Содержимое файла
        overwrite: Разрешить перезапись существующего файла (по умолчанию False)
        encoding: Кодировка файла (по умолчанию utf-8)

    Returns:
        Сообщение об успешном создании файла или ошибке
    """
    logger.info(f"write_file: {path} (overwrite: {overwrite}, encoding: {encoding})")

    # Проверка кодировки
    if encoding not in ALLOWED_ENCODINGS:
        return f"❌ Неподдерживаемая кодировка. Разрешены: {', '.join(ALLOWED_ENCODINGS)}"

    # Проверка размера содержимого
    content_size = len(content.encode(encoding))
    if content_size > MAX_FILE_SIZE_WRITE:
        return f"❌ Содержимое слишком большое ({format_file_size(content_size)}). Максимум: {format_file_size(MAX_FILE_SIZE_WRITE)}"

    # Валидация пути
    is_valid, error_msg, resolved_path = validate_path(path)
    if not is_valid:
        return f"❌ Ошибка валидации пути: {error_msg}"

    # Проверка существования файла
    if resolved_path.exists() and not overwrite:
        return f"❌ Файл уже существует: {resolved_path}\nИспользуйте параметр overwrite=true для перезаписи."

    # Проверка существования родительской директории
    parent_dir = resolved_path.parent
    if not parent_dir.exists():
        # Создаем промежуточные директории
        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Созданы промежуточные директории: {parent_dir}")
        except PermissionError:
            return f"❌ Нет прав на создание директории: {parent_dir}"
        except Exception as e:
            return f"❌ Ошибка при создании директории: {e}"

    # Проверка прав доступа к директории
    if not os.access(parent_dir, os.W_OK):
        return f"❌ Нет прав на запись в директорию: {parent_dir}"

    try:
        # Запись файла
        resolved_path.write_text(content, encoding=encoding)

        file_size = resolved_path.stat().st_size
        logger.info(f"write_file успешно: {file_size} байт")

        action = "перезаписан" if (resolved_path.exists() and overwrite) else "создан"

        result = f"✅ Файл успешно {action}:\n"
        result += f"📄 Путь: {resolved_path}\n"
        result += f"Размер: {format_file_size(file_size)}\n"
        result += f"Кодировка: {encoding}\n"

        return result

    except PermissionError:
        return f"❌ Нет прав на запись в файл: {resolved_path}"

    except Exception as e:
        logger.error(f"Ошибка при записи файла: {e}", exc_info=True)
        return f"❌ Ошибка при записи файла: {e}"


@mcp.tool()
async def edit_file(path: str, new_content: str, create_backup: bool = True, encoding: str = "utf-8") -> str:
    """
    Редактирование существующего файла (полная замена содержимого).

    Args:
        path: Путь к файлу
        new_content: Новое содержимое файла
        create_backup: Создать резервную копию перед редактированием (по умолчанию True)
        encoding: Кодировка файла (по умолчанию utf-8)

    Returns:
        Сообщение об успешном редактировании или ошибке
    """
    logger.info(f"edit_file: {path} (backup: {create_backup}, encoding: {encoding})")

    # Проверка кодировки
    if encoding not in ALLOWED_ENCODINGS:
        return f"❌ Неподдерживаемая кодировка. Разрешены: {', '.join(ALLOWED_ENCODINGS)}"

    # Проверка размера содержимого
    content_size = len(new_content.encode(encoding))
    if content_size > MAX_FILE_SIZE_WRITE:
        return f"❌ Содержимое слишком большое ({format_file_size(content_size)}). Максимум: {format_file_size(MAX_FILE_SIZE_WRITE)}"

    # Валидация пути
    is_valid, error_msg, resolved_path = validate_path(path)
    if not is_valid:
        return f"❌ Ошибка валидации пути: {error_msg}"

    # Проверка существования файла
    if not resolved_path.exists():
        return f"❌ Файл не существует: {resolved_path}\nИспользуйте write_file для создания нового файла."

    # Проверка что это файл
    if not resolved_path.is_file():
        return f"❌ Путь не является файлом: {resolved_path}"

    # Проверка прав доступа
    if not os.access(resolved_path, os.R_OK | os.W_OK):
        return f"❌ Нет прав на чтение/запись файла: {resolved_path}"

    backup_path = None

    try:
        # Создание резервной копии
        if create_backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = resolved_path.with_suffix(f".{timestamp}.backup{resolved_path.suffix}")
            shutil.copy2(resolved_path, backup_path)
            logger.info(f"Создана резервная копия: {backup_path}")

        # Чтение старого содержимого для логирования
        old_size = resolved_path.stat().st_size

        # Запись нового содержимого
        resolved_path.write_text(new_content, encoding=encoding)

        new_size = resolved_path.stat().st_size
        logger.info(f"edit_file успешно: {old_size} -> {new_size} байт")

        result = f"✅ Файл успешно отредактирован:\n"
        result += f"📄 Путь: {resolved_path}\n"
        result += f"Старый размер: {format_file_size(old_size)}\n"
        result += f"Новый размер: {format_file_size(new_size)}\n"
        result += f"Кодировка: {encoding}\n"
        if backup_path:
            result += f"💾 Резервная копия: {backup_path}\n"

        return result

    except PermissionError:
        return f"❌ Нет прав на редактирование файла: {resolved_path}"

    except Exception as e:
        logger.error(f"Ошибка при редактировании файла: {e}", exc_info=True)
        # Попытка восстановить из backup
        if backup_path and backup_path.exists():
            try:
                shutil.copy2(backup_path, resolved_path)
                return f"❌ Ошибка при редактировании файла: {e}\nФайл восстановлен из резервной копии."
            except:
                pass
        return f"❌ Ошибка при редактировании файла: {e}"


@mcp.tool()
async def get_file_info(path: str) -> str:
    """
    Получение метаданных файла или директории.

    Args:
        path: Путь к файлу или директории

    Returns:
        Детальная информация о файле/директории или сообщение об ошибке
    """
    logger.info(f"get_file_info: {path}")

    # Валидация пути
    is_valid, error_msg, resolved_path = validate_path(path)
    if not is_valid:
        return f"❌ Ошибка валидации пути: {error_msg}"

    # Проверка существования
    if not resolved_path.exists():
        return f"❌ Путь не существует: {resolved_path}"

    try:
        # Получение метаданных
        stat_info = resolved_path.stat()

        # Определение типа
        if resolved_path.is_file():
            item_type = "📄 Файл"
        elif resolved_path.is_dir():
            item_type = "📁 Директория"
        elif resolved_path.is_symlink():
            item_type = "🔗 Символическая ссылка"
        else:
            item_type = "❓ Неизвестный тип"

        # Форматирование информации
        result = f"ℹ️ Информация о: {resolved_path}\n"
        result += "=" * 80 + "\n"
        result += f"Тип: {item_type}\n"
        result += f"Имя: {resolved_path.name}\n"
        result += f"Родительская директория: {resolved_path.parent}\n"
        result += f"Абсолютный путь: {resolved_path.absolute()}\n"

        if resolved_path.is_file():
            result += f"Размер: {format_file_size(stat_info.st_size)}\n"
            result += f"Расширение: {resolved_path.suffix or 'нет'}\n"

        # Даты
        result += f"Дата создания: {datetime.fromtimestamp(stat_info.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"Дата изменения: {datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"Дата доступа: {datetime.fromtimestamp(stat_info.st_atime).strftime('%Y-%m-%d %H:%M:%S')}\n"

        # Права доступа
        permissions = format_file_permissions(stat_info.st_mode)
        result += f"Права доступа: {permissions} ({oct(stat_info.st_mode)[-3:]})\n"

        # Проверка прав текущего пользователя
        readable = "✅" if os.access(resolved_path, os.R_OK) else "❌"
        writable = "✅" if os.access(resolved_path, os.W_OK) else "❌"
        executable = "✅" if os.access(resolved_path, os.X_OK) else "❌"

        result += f"Доступ (чтение): {readable}\n"
        result += f"Доступ (запись): {writable}\n"
        result += f"Доступ (выполнение): {executable}\n"

        # Для директорий - количество элементов
        if resolved_path.is_dir():
            try:
                items_count = len(list(resolved_path.iterdir()))
                result += f"Элементов в директории: {items_count}\n"
            except PermissionError:
                result += f"Элементов в директории: (нет доступа)\n"

        # Для символических ссылок - куда указывает
        if resolved_path.is_symlink():
            try:
                target = resolved_path.readlink()
                result += f"Указывает на: {target}\n"
            except:
                result += f"Указывает на: (ошибка чтения)\n"

        logger.info(f"get_file_info успешно")
        return result

    except PermissionError:
        return f"❌ Нет прав доступа к: {resolved_path}"

    except Exception as e:
        logger.error(f"Ошибка при получении информации о файле: {e}", exc_info=True)
        return f"❌ Ошибка при получении информации: {e}"


if __name__ == "__main__":
    # Используем SSE транспорт вместо stdio из-за бага в MCP SDK
    # https://github.com/modelcontextprotocol/python-sdk/issues/862
    import sys

    # Если запущен с аргументом --stdio, использовать stdio (для совместимости)
    # Иначе использовать SSE по умолчанию
    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        logger.info("Запуск Filesystem MCP сервера в режиме stdio")
        mcp.run(transport="stdio")
    else:
        # SSE транспорт по умолчанию (работает стабильно)
        logger.info("Запуск Filesystem MCP сервера в режиме SSE на порту 8003")
        mcp.run(transport="sse", port=8003)
