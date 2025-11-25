"""
Модуль для индексации документов и создания векторного индекса.
Поддерживает создание, обновление, сохранение и загрузку индекса.
"""

import json
import logging
import os
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Set
from pathlib import Path

from .chunker import TextChunker
from .embedder import OllamaEmbedder, OllamaConnectionError
from ..utils.file_parser import (
    scan_directory,
    read_text,
    get_file_hash,
    get_file_metadata,
    ensure_directory_exists
)

logger = logging.getLogger('embeddings.indexer')


class IndexingError(Exception):
    """Исключение при ошибках индексации."""
    pass


class DocumentIndexer:
    """
    Класс для индексации документов и создания векторного индекса.

    Основные возможности:
    - Индексация документов из директории
    - Обновление индекса при изменении файлов
    - Сохранение и загрузка индекса
    - Создание резервных копий
    - Отслеживание изменений файлов по хэшу
    """

    def __init__(
        self,
        chunker: TextChunker,
        embedder: OllamaEmbedder,
        index_path: str = "data/index.json",
        backup_dir: str = "data/backups"
    ):
        """
        Инициализация индексатора.

        Args:
            chunker: Объект для разбивки текста на чанки
            embedder: Объект для генерации эмбеддингов
            index_path: Путь к файлу индекса
            backup_dir: Директория для резервных копий
        """
        self.chunker = chunker
        self.embedder = embedder
        self.index_path = os.path.abspath(index_path)
        self.backup_dir = os.path.abspath(backup_dir)

        # Внутренняя структура индекса
        self.index = {
            'metadata': {
                'created_at': None,
                'updated_at': None,
                'total_documents': 0,
                'total_chunks': 0,
                'version': '1.0'
            },
            'documents': {},  # file_path -> document metadata
            'chunks': [],     # список всех чанков с эмбеддингами
            'file_hashes': {} # file_path -> hash
        }

        logger.info(f"DocumentIndexer initialized: index_path={index_path}")

    def index_directory(
        self,
        directory: str,
        extensions: List[str] = ['.md', '.txt'],
        exclude_patterns: List[str] = ['.*', '__pycache__', '*.pyc'],
        recursive: bool = True
    ) -> Dict:
        """
        Индексирует все файлы в директории.

        Args:
            directory: Путь к директории
            extensions: Список расширений файлов для индексации
            exclude_patterns: Паттерны исключения (glob)
            recursive: Рекурсивный обход директории

        Returns:
            Словарь со статистикой индексации

        Raises:
            IndexingError: При ошибках индексации
        """
        logger.info(f"Starting directory indexing: {directory}")

        # Проверяем доступность embedder
        if not self.embedder.check_connection():
            raise IndexingError(
                "Ollama is not available. Please start Ollama server."
            )

        # Сканируем директорию
        files = scan_directory(
            directory=directory,
            extensions=extensions,
            exclude_patterns=exclude_patterns,
            recursive=recursive
        )

        if not files:
            logger.warning(f"No files found in {directory}")
            return {
                'total_files': 0,
                'indexed_files': 0,
                'skipped_files': 0,
                'total_chunks': 0,
                'errors': []
            }

        logger.info(f"Found {len(files)} files to index")

        # Статистика
        stats = {
            'total_files': len(files),
            'indexed_files': 0,
            'skipped_files': 0,
            'total_chunks': 0,
            'errors': []
        }

        # Индексируем каждый файл
        for file_path in files:
            try:
                result = self.index_file(file_path)
                if result['indexed']:
                    stats['indexed_files'] += 1
                    stats['total_chunks'] += result['chunks_created']
                else:
                    stats['skipped_files'] += 1

            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                stats['errors'].append({
                    'file': file_path,
                    'error': str(e)
                })

        # Обновляем метаданные индекса
        self._update_metadata()

        logger.info(
            f"Indexing complete: {stats['indexed_files']}/{stats['total_files']} files, "
            f"{stats['total_chunks']} chunks"
        )

        return stats

    def index_file(self, file_path: str) -> Dict:
        """
        Индексирует один файл.

        Args:
            file_path: Путь к файлу

        Returns:
            Словарь с результатами индексации

        Raises:
            IndexingError: При ошибках чтения или индексации файла
        """
        file_path = os.path.abspath(file_path)
        logger.info(f"Indexing file: {file_path}")

        # Вычисляем хэш файла
        try:
            current_hash = get_file_hash(file_path)
        except Exception as e:
            raise IndexingError(f"Failed to compute hash for {file_path}: {e}")

        # Проверяем, изменился ли файл
        if file_path in self.index['file_hashes']:
            old_hash = self.index['file_hashes'][file_path]
            if old_hash == current_hash:
                logger.info(f"File unchanged, skipping: {file_path}")
                return {
                    'indexed': False,
                    'reason': 'unchanged',
                    'chunks_created': 0
                }

        # Читаем файл
        try:
            content = read_text(file_path)
        except Exception as e:
            raise IndexingError(f"Failed to read {file_path}: {e}")

        if not content.strip():
            logger.warning(f"Empty file, skipping: {file_path}")
            return {
                'indexed': False,
                'reason': 'empty',
                'chunks_created': 0
            }

        # Получаем метаданные файла
        try:
            metadata = get_file_metadata(file_path)
        except Exception as e:
            logger.warning(f"Failed to get metadata for {file_path}: {e}")
            metadata = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_type': os.path.splitext(file_path)[1].lstrip('.')
            }

        # Разбиваем на чанки
        logger.info(f"Chunking file: {file_path}")
        chunks = self.chunker.chunk_text(content, metadata)

        if not chunks:
            logger.warning(f"No chunks created for {file_path}")
            return {
                'indexed': False,
                'reason': 'no_chunks',
                'chunks_created': 0
            }

        logger.info(f"Created {len(chunks)} chunks for {file_path}")

        # Генерируем эмбеддинги
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        texts = [chunk['text'] for chunk in chunks]

        try:
            embeddings = self.embedder.embed_batch(texts)
        except OllamaConnectionError as e:
            raise IndexingError(f"Ollama connection failed: {e}")
        except Exception as e:
            raise IndexingError(f"Failed to generate embeddings: {e}")

        # Проверяем результаты
        if len(embeddings) != len(chunks):
            raise IndexingError(
                f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)} chunks"
            )

        # Удаляем старые чанки этого файла из индекса
        self._remove_file_from_index(file_path)

        # Добавляем новые чанки в индекс
        chunks_added = 0
        for chunk, embedding in zip(chunks, embeddings):
            if embedding:  # Проверяем что эмбеддинг не пустой
                chunk['embedding'] = embedding
                self.index['chunks'].append(chunk)
                chunks_added += 1
            else:
                logger.warning(f"Empty embedding for chunk {chunk['chunk_id']}, skipping")

        # Сохраняем метаданные документа
        self.index['documents'][file_path] = {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'file_type': metadata.get('file_type', 'unknown'),
            'indexed_at': datetime.now().isoformat(),
            'chunks_count': chunks_added,
            'file_size': metadata.get('file_size', 0)
        }

        # Сохраняем хэш файла
        self.index['file_hashes'][file_path] = current_hash

        logger.info(f"Successfully indexed {file_path}: {chunks_added} chunks")

        return {
            'indexed': True,
            'chunks_created': chunks_added,
            'file_hash': current_hash
        }

    def update_index(
        self,
        directory: str,
        extensions: List[str] = ['.md', '.txt'],
        exclude_patterns: List[str] = ['.*', '__pycache__', '*.pyc'],
        recursive: bool = True
    ) -> Dict:
        """
        Обновляет индекс, индексируя только новые и изменённые файлы.

        Args:
            directory: Путь к директории
            extensions: Список расширений файлов
            exclude_patterns: Паттерны исключения
            recursive: Рекурсивный обход

        Returns:
            Словарь со статистикой обновления
        """
        logger.info(f"Updating index for directory: {directory}")

        # Сканируем директорию
        current_files = set(scan_directory(
            directory=directory,
            extensions=extensions,
            exclude_patterns=exclude_patterns,
            recursive=recursive
        ))

        # Файлы в текущем индексе
        indexed_files = set(self.index['documents'].keys())

        # Находим удалённые файлы
        deleted_files = indexed_files - current_files
        for file_path in deleted_files:
            logger.info(f"Removing deleted file from index: {file_path}")
            self._remove_file_from_index(file_path)

        # Индексируем новые и изменённые файлы
        stats = self.index_directory(
            directory=directory,
            extensions=extensions,
            exclude_patterns=exclude_patterns,
            recursive=recursive
        )

        stats['deleted_files'] = len(deleted_files)

        logger.info(f"Index update complete: {stats}")

        return stats

    def save_index(self, backup: bool = True) -> None:
        """
        Сохраняет индекс в JSON файл.

        Args:
            backup: Создать резервную копию перед сохранением

        Raises:
            IndexingError: При ошибках сохранения
        """
        logger.info(f"Saving index to {self.index_path}")

        # Создаём резервную копию
        if backup and os.path.exists(self.index_path):
            try:
                self.create_backup()
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")

        # Обновляем метаданные
        self._update_metadata()

        # Создаём директорию если нужно
        index_dir = os.path.dirname(self.index_path)
        if index_dir:
            ensure_directory_exists(index_dir)

        # Сохраняем индекс
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)

            logger.info(f"Index saved successfully: {self.index_path}")

        except Exception as e:
            raise IndexingError(f"Failed to save index: {e}")

    def load_index(self, index_path: Optional[str] = None) -> bool:
        """
        Загружает индекс из JSON файла.

        Args:
            index_path: Путь к файлу индекса (если None, используется self.index_path)

        Returns:
            True если индекс успешно загружен

        Raises:
            IndexingError: При ошибках загрузки
        """
        if index_path is None:
            index_path = self.index_path
        else:
            index_path = os.path.abspath(index_path)

        if not os.path.exists(index_path):
            logger.warning(f"Index file not found: {index_path}")
            return False

        logger.info(f"Loading index from {index_path}")

        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                loaded_index = json.load(f)

            # Валидация структуры индекса
            required_keys = ['metadata', 'documents', 'chunks', 'file_hashes']
            for key in required_keys:
                if key not in loaded_index:
                    raise IndexingError(f"Invalid index format: missing key '{key}'")

            self.index = loaded_index

            logger.info(
                f"Index loaded successfully: "
                f"{self.index['metadata']['total_documents']} documents, "
                f"{self.index['metadata']['total_chunks']} chunks"
            )

            return True

        except json.JSONDecodeError as e:
            raise IndexingError(f"Invalid JSON in index file: {e}")
        except Exception as e:
            raise IndexingError(f"Failed to load index: {e}")

    def create_backup(self) -> str:
        """
        Создаёт резервную копию текущего индекса.

        Returns:
            Путь к файлу резервной копии

        Raises:
            IndexingError: При ошибках создания бэкапа
        """
        if not os.path.exists(self.index_path):
            logger.warning("No index file to backup")
            return ""

        # Создаём директорию для бэкапов
        ensure_directory_exists(self.backup_dir)

        # Формируем имя файла с временной меткой
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"index_backup_{timestamp}.json"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        try:
            shutil.copy2(self.index_path, backup_path)
            logger.info(f"Backup created: {backup_path}")

            # Очищаем старые бэкапы (оставляем только последние 5)
            self._cleanup_old_backups(keep_last=5)

            return backup_path

        except Exception as e:
            raise IndexingError(f"Failed to create backup: {e}")

    def get_index_stats(self) -> Dict:
        """
        Возвращает статистику по индексу.

        Returns:
            Словарь со статистикой
        """
        stats = {
            'total_documents': len(self.index['documents']),
            'total_chunks': len(self.index['chunks']),
            'created_at': self.index['metadata'].get('created_at'),
            'updated_at': self.index['metadata'].get('updated_at'),
            'version': self.index['metadata'].get('version'),
            'index_size_mb': 0
        }

        # Вычисляем размер индекса
        if os.path.exists(self.index_path):
            stats['index_size_mb'] = round(
                os.path.getsize(self.index_path) / (1024 * 1024),
                2
            )

        # Статистика по типам файлов
        file_types = {}
        for doc in self.index['documents'].values():
            file_type = doc.get('file_type', 'unknown')
            file_types[file_type] = file_types.get(file_type, 0) + 1

        stats['file_types'] = file_types

        return stats

    def clear_index(self) -> None:
        """
        Очищает индекс (удаляет все данные).
        """
        logger.warning("Clearing index")

        self.index = {
            'metadata': {
                'created_at': None,
                'updated_at': None,
                'total_documents': 0,
                'total_chunks': 0,
                'version': '1.0'
            },
            'documents': {},
            'chunks': [],
            'file_hashes': {}
        }

        logger.info("Index cleared")

    def _remove_file_from_index(self, file_path: str) -> None:
        """
        Удаляет файл и его чанки из индекса.

        Args:
            file_path: Путь к файлу
        """
        # Удаляем чанки этого файла
        self.index['chunks'] = [
            chunk for chunk in self.index['chunks']
            if chunk.get('source_file') != file_path
        ]

        # Удаляем метаданные документа
        if file_path in self.index['documents']:
            del self.index['documents'][file_path]

        # Удаляем хэш
        if file_path in self.index['file_hashes']:
            del self.index['file_hashes'][file_path]

        logger.debug(f"Removed file from index: {file_path}")

    def _update_metadata(self) -> None:
        """
        Обновляет метаданные индекса.
        """
        now = datetime.now().isoformat()

        if self.index['metadata']['created_at'] is None:
            self.index['metadata']['created_at'] = now

        self.index['metadata']['updated_at'] = now
        self.index['metadata']['total_documents'] = len(self.index['documents'])
        self.index['metadata']['total_chunks'] = len(self.index['chunks'])

    def _cleanup_old_backups(self, keep_last: int = 5) -> None:
        """
        Удаляет старые резервные копии, оставляя только последние N.

        Args:
            keep_last: Количество последних бэкапов для сохранения
        """
        if not os.path.exists(self.backup_dir):
            return

        # Получаем список файлов бэкапов
        backup_files = []
        for filename in os.listdir(self.backup_dir):
            if filename.startswith('index_backup_') and filename.endswith('.json'):
                file_path = os.path.join(self.backup_dir, filename)
                backup_files.append((file_path, os.path.getmtime(file_path)))

        # Сортируем по времени модификации (новые первыми)
        backup_files.sort(key=lambda x: x[1], reverse=True)

        # Удаляем старые бэкапы
        for file_path, _ in backup_files[keep_last:]:
            try:
                os.remove(file_path)
                logger.debug(f"Removed old backup: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove backup {file_path}: {e}")
