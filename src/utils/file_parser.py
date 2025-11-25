"""
Утилиты для работы с файлами: чтение, валидация, сканирование директорий.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Dict
import fnmatch

logger = logging.getLogger('embeddings.file_parser')


def read_markdown(file_path: str) -> str:
    """
    Читает markdown файл.

    Args:
        file_path: Путь к файлу

    Returns:
        Содержимое файла

    Raises:
        FileNotFoundError: Если файл не найден
        UnicodeDecodeError: Если файл не в UTF-8
    """
    return read_text(file_path)


def read_text(file_path: str) -> str:
    """
    Читает текстовый файл с поддержкой различных кодировок.

    Args:
        file_path: Путь к файлу

    Returns:
        Содержимое файла

    Raises:
        FileNotFoundError: Если файл не найден
    """
    encodings = ['utf-8', 'utf-16', 'cp1251', 'latin-1']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                logger.debug(f"Successfully read {file_path} with encoding {encoding}")
                return content
        except UnicodeDecodeError:
            logger.debug(f"Failed to decode {file_path} with {encoding}, trying next encoding")
            continue
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            raise

    # Если все кодировки не сработали
    raise UnicodeDecodeError(
        'multiple',
        b'',
        0,
        1,
        f'Could not decode {file_path} with any of: {encodings}'
    )


def get_file_hash(file_path: str) -> str:
    """
    Вычисляет SHA-256 хэш файла.

    Args:
        file_path: Путь к файлу

    Returns:
        Хэш в hex формате
    """
    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            # Читаем файл блоками для эффективности
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    except Exception as e:
        logger.error(f"Error computing hash for {file_path}: {e}")
        raise


def is_valid_file(file_path: str, extensions: List[str]) -> bool:
    """
    Проверяет валидность файла.

    Args:
        file_path: Путь к файлу
        extensions: Список допустимых расширений (например: ['.md', '.txt'])

    Returns:
        True если файл валиден
    """
    if not os.path.isfile(file_path):
        return False

    # Проверка расширения
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext not in [ext.lower() for ext in extensions]:
        return False

    # Проверка что файл не пустой
    try:
        if os.path.getsize(file_path) == 0:
            logger.debug(f"Skipping empty file: {file_path}")
            return False
    except OSError:
        return False

    return True


def scan_directory(
    directory: str,
    extensions: List[str],
    exclude_patterns: List[str],
    recursive: bool = True
) -> List[str]:
    """
    Сканирует директорию и возвращает пути к файлам.

    Args:
        directory: Путь к директории
        extensions: Список расширений для поиска (например: ['.md', '.txt'])
        exclude_patterns: Паттерны исключения (glob patterns)
        recursive: Рекурсивный обход

    Returns:
        Список путей к файлам
    """
    files = []
    directory = os.path.abspath(directory)

    if not os.path.isdir(directory):
        logger.warning(f"Directory not found: {directory}")
        return files

    logger.info(f"Scanning directory: {directory} (recursive={recursive})")

    if recursive:
        for root, dirs, filenames in os.walk(directory):
            # Исключаем директории по паттернам
            dirs[:] = [d for d in dirs if not _should_exclude(d, exclude_patterns)]

            for filename in filenames:
                file_path = os.path.join(root, filename)

                # Проверяем файл на исключение и валидность
                if not _should_exclude(filename, exclude_patterns) and \
                   is_valid_file(file_path, extensions):
                    files.append(file_path)
    else:
        # Только файлы в текущей директории
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)

            if os.path.isfile(file_path) and \
               not _should_exclude(filename, exclude_patterns) and \
               is_valid_file(file_path, extensions):
                files.append(file_path)

    logger.info(f"Found {len(files)} files in {directory}")
    return sorted(files)


def _should_exclude(name: str, patterns: List[str]) -> bool:
    """
    Проверяет, соответствует ли имя файла/директории паттернам исключения.

    Args:
        name: Имя файла или директории
        patterns: Список glob-паттернов

    Returns:
        True если файл нужно исключить
    """
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def get_file_metadata(file_path: str) -> Dict:
    """
    Получает метаданные файла.

    Args:
        file_path: Путь к файлу

    Returns:
        Словарь с метаданными (размер, дата изменения и т.д.)
    """
    try:
        stat = os.stat(file_path)

        return {
            'file_path': os.path.abspath(file_path),
            'file_name': os.path.basename(file_path),
            'file_size': stat.st_size,
            'file_type': os.path.splitext(file_path)[1].lstrip('.'),
            'modified_at': stat.st_mtime,
            'created_at': stat.st_ctime,
        }

    except Exception as e:
        logger.error(f"Error getting metadata for {file_path}: {e}")
        raise


def ensure_directory_exists(directory: str) -> None:
    """
    Создаёт директорию если она не существует.

    Args:
        directory: Путь к директории
    """
    Path(directory).mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {directory}")
