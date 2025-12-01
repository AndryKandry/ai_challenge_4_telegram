"""
Модуль для индексации документов и создания векторного индекса.
Поддерживает создание, обновление, сохранение и загрузку индекса.
"""

import json
import logging
import os
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Set, Any
from pathlib import Path
import ast
import hashlib

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
    - Обогащение метаданных документов
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
                'version': '2.0'  # Версия с расширенными метаданными
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

        # Получаем базовые метаданные файла
        try:
            metadata = get_file_metadata(file_path)
        except Exception as e:
            logger.warning(f"Failed to get metadata for {file_path}: {e}")
            metadata = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_type': os.path.splitext(file_path)[1].lstrip('.')
            }

        # Обогащаем метаданные
        enriched_metadata = self._enrich_file_metadata(file_path, content, metadata)

        # Разбиваем на чанки
        logger.info(f"Chunking file: {file_path}")
        chunks = self.chunker.chunk_text(content, enriched_metadata)

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

        # Обогащаем метаданные чанков
        enriched_chunks = []
        chunks_added = 0
        
        for chunk, embedding in zip(chunks, embeddings):
            if embedding:  # Проверяем что эмбеддинг не пустой
                # Обогащаем метаданные чанка
                enriched_chunk = self._enrich_chunk_metadata(
                    chunk, enriched_metadata, file_path
                )
                enriched_chunk['embedding'] = embedding
                enriched_chunks.append(enriched_chunk)
                chunks_added += 1
            else:
                logger.warning(f"Empty embedding for chunk {chunk['chunk_id']}, skipping")

        self.index['chunks'].extend(enriched_chunks)

        # Сохраняем расширенные метаданные документа
        self.index['documents'][file_path] = self._create_enriched_document_metadata(
            file_path, enriched_metadata, chunks_added, enriched_chunks
        )

        # Сохраняем хэш файла
        self.index['file_hashes'][file_path] = current_hash

        logger.info(f"Successfully indexed {file_path}: {chunks_added} chunks")

        return {
            'indexed': True,
            'chunks_created': chunks_added,
            'file_hash': current_hash
        }

    def _enrich_file_metadata(
        self,
        file_path: str,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Обогащает метаданные файла дополнительной информацией.

        Args:
            file_path: Путь к файлу
            content: Содержимое файла
            base_metadata: Базовые метаданные

        Returns:
            Обогащенные метаданные
        """
        enriched = base_metadata.copy()
        file_ext = os.path.splitext(file_path)[1].lower()

        # Определяем язык программирования
        enriched['language'] = self._detect_language(file_ext, content)
        
        # Анализ для Python файлов
        if file_ext == '.py':
            enriched.update(self._analyze_python_file(content))
        
        # Анализ для Markdown файлов
        elif file_ext in ['.md', '.markdown']:
            enriched.update(self._analyze_markdown_file(content))
        
        # Общие метрики
        enriched.update(self._calculate_text_metrics(content))
        
        # Добавляем информацию о сложности
        enriched['complexity'] = self._calculate_complexity(content, enriched['language'])
        
        return enriched

    def _enrich_chunk_metadata(
        self,
        chunk: Dict[str, Any],
        file_metadata: Dict[str, Any],
        file_path: str
    ) -> Dict[str, Any]:
        """
        Обогащает метаданные чанка.

        Args:
            chunk: Исходный чанк
            file_metadata: Метаданные файла
            file_path: Путь к файлу

        Returns:
            Обогащенный чанк
        """
        enriched_chunk = chunk.copy()
        
        # Добавляем метаданные из файла
        enriched_chunk['file_language'] = file_metadata.get('language', 'unknown')
        enriched_chunk['file_type'] = file_metadata.get('file_type', 'unknown')
        enriched_chunk['file_size'] = file_metadata.get('file_size', 0)
        enriched_chunk['file_complexity'] = file_metadata.get('complexity', 0)
        
        # Анализируем содержимое чанка
        chunk_content = chunk.get('text', '')
        
        # Поиск функций в чанке (для Python)
        if file_metadata.get('language') == 'python':
            functions = self._extract_functions_from_text(chunk_content)
            enriched_chunk['functions'] = functions
        
        # Поиск классов в чанке
        if file_metadata.get('language') == 'python':
            classes = self._extract_classes_from_text(chunk_content)
            enriched_chunk['classes'] = classes
        
        # Поиск импортов
        imports = self._extract_imports_from_text(chunk_content, file_metadata.get('language'))
        enriched_chunk['imports'] = imports
        
        # Дополнительные метрики чанка
        enriched_chunk.update(self._calculate_chunk_metrics(chunk_content))
        
        # Добавляем временную метку
        enriched_chunk['indexed_at'] = datetime.now().isoformat()
        
        return enriched_chunk

    def _create_enriched_document_metadata(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        chunks_count: int,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Создает обогащенные метаданные документа.

        Args:
            file_path: Путь к файлу
            metadata: Метаданные файла
            chunks_count: Количество чанков
            chunks: Список чанков

        Returns:
            Обогащенные метаданные документа
        """
        # Собираем все уникальные функции и классы из чанков
        all_functions = set()
        all_classes = set()
        all_imports = set()
        
        for chunk in chunks:
            all_functions.update(chunk.get('functions', []))
            all_classes.update(chunk.get('classes', []))
            all_imports.update(chunk.get('imports', []))
        
        enriched_metadata = {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'file_type': metadata.get('file_type', 'unknown'),
            'language': metadata.get('language', 'unknown'),
            'indexed_at': datetime.now().isoformat(),
            'chunks_count': chunks_count,
            'file_size': metadata.get('file_size', 0),
            'lines_count': metadata.get('lines', 0),
            'functions': list(all_functions),
            'classes': list(all_classes),
            'imports': list(all_imports),
            'complexity': metadata.get('complexity', 0),
            'author': metadata.get('author', 'unknown'),
            'last_modified': metadata.get('last_modified', 'unknown'),
            'docstrings': metadata.get('docstrings', []),
            'avg_chunk_length': metadata.get('avg_chunk_length', 0)
        }
        
        return enriched_metadata

    def _detect_language(self, file_ext: str, content: str) -> str:
        """Определяет язык программирования/формат файла."""
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'react',
            '.tsx': 'react',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.rs': 'rust',
            '.md': 'markdown',
            '.txt': 'text',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.sql': 'sql'
        }
        
        return extension_map.get(file_ext, 'unknown')

    def _analyze_python_file(self, content: str) -> Dict[str, Any]:
        """Анализирует Python файл."""
        try:
            tree = ast.parse(content)
            
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    else:
                        imports.append(f"from {node.module}")
            
            return {
                'functions': functions,
                'classes': classes,
                'imports': imports,
                'docstrings': self._extract_docstrings(tree)
            }
            
        except SyntaxError:
            logger.warning("Cannot parse Python file for analysis")
            return {'functions': [], 'classes': [], 'imports': [], 'docstrings': []}

    def _analyze_markdown_file(self, content: str) -> Dict[str, Any]:
        """Анализирует Markdown файл."""
        import re
        
        # Извлекаем заголовки
        headers = re.findall(r'^#{1,6}\s+(.+)$', content, re.MULTILINE)
        
        # Извлекаем кодовые блоки
        code_blocks = re.findall(r'```(\w+)?\n(.*?)\n```', content, re.DOTALL)
        
        # Извлекаем ссылки
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        
        return {
            'headers': headers,
            'code_blocks': [{'language': lang or 'text', 'content': code} for lang, code in code_blocks],
            'links': links,
            'sections_count': len(headers)
        }

    def _calculate_text_metrics(self, content: str) -> Dict[str, Any]:
        """Вычисляет текстовые метрики."""
        lines = content.split('\n')
        words = content.split()
        
        return {
            'lines': len(lines),
            'words': len(words),
            'characters': len(content),
            'avg_line_length': sum(len(line) for line in lines) / len(lines) if lines else 0,
            'avg_word_length': sum(len(word) for word in words) / len(words) if words else 0
        }

    def _calculate_complexity(self, content: str, language: str) -> int:
        """Вычисляет цикломатическую сложность."""
        if language == 'python':
            return self._calculate_python_complexity(content)
        else:
            # Упрощенная оценка для других языков
            complexity_indicators = ['if', 'else', 'elif', 'for', 'while', 'try', 'except', 'case', 'switch']
            complexity = 1  # Базовая сложность
            
            for indicator in complexity_indicators:
                complexity += content.count(indicator)
            
            return complexity

    def _calculate_python_complexity(self, content: str) -> int:
        """Вычисляет цикломатическую сложность для Python."""
        try:
            tree = ast.parse(content)
            complexity = 1  # Базовая сложность
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.With)):
                    complexity += 1
                elif isinstance(node, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            
            return complexity
            
        except SyntaxError:
            # Fallback - простой подсчет
            indicators = ['if', 'elif', 'for', 'while', 'except', 'with']
            complexity = 1
            for indicator in indicators:
                complexity += content.count(indicator)
            return complexity

    def _extract_functions_from_text(self, text: str) -> List[str]:
        """Извлекает имена функций из текста."""
        import re
        pattern = r'\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        return re.findall(pattern, text)

    def _extract_classes_from_text(self, text: str) -> List[str]:
        """Извлекает имена классов из текста."""
        import re
        pattern = r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[\(:]'
        return re.findall(pattern, text)

    def _extract_imports_from_text(self, text: str, language: str) -> List[str]:
        """Извлекает импорты из текста."""
        imports = []
        
        if language == 'python':
            import re
            # import module
            imports.extend(re.findall(r'\bimport\s+([a-zA-Z_][a-zA-Z0-9_.]*)', text))
            # from module import name
            imports.extend(re.findall(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import', text))
        
        return list(set(imports))  # Убираем дубликаты

    def _extract_docstrings(self, tree: ast.AST) -> List[str]:
        """Извлекает docstrings из AST."""
        docstrings = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring:
                    docstrings.append(docstring)
        
        return docstrings

    def _calculate_chunk_metrics(self, content: str) -> Dict[str, Any]:
        """Вычисляет метрики чанка."""
        words = content.split()
        sentences = content.split('.')
        
        return {
            'word_count': len(words),
            'sentence_count': len([s for s in sentences if s.strip()]),
            'avg_word_length': sum(len(word) for word in words) / len(words) if words else 0,
            'has_code': '```' in content or any(word in content for word in ['def ', 'class ', 'function', 'var ']),
            'has_numbers': bool(re.search(r'\d+', content)),
            'has_links': 'http' in content or 'www.' in content,
            'readability_score': self._calculate_readability(content)
        }

    def _calculate_readability(self, content: str) -> float:
        """Вычисляет простую оценку читаемости."""
        words = content.split()
        if not words:
            return 0.0
        
        # Упрощенная метрика: отношение коротких слов к общему количеству
        short_words = sum(1 for word in words if len(word) <= 4)
        return short_words / len(words)

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
        languages = {}
        
        for doc in self.index['documents'].values():
            file_type = doc.get('file_type', 'unknown')
            language = doc.get('language', 'unknown')
            
            file_types[file_type] = file_types.get(file_type, 0) + 1
            languages[language] = languages.get(language, 0) + 1

        stats['file_types'] = file_types
        stats['languages'] = languages
        
        # Дополнительная статистика
        total_functions = sum(len(doc.get('functions', [])) for doc in self.index['documents'].values())
        total_classes = sum(len(doc.get('classes', [])) for doc in self.index['documents'].values())
        
        stats['total_functions'] = total_functions
        stats['total_classes'] = total_classes
        stats['avg_chunks_per_document'] = stats['total_chunks'] / stats['total_documents'] if stats['total_documents'] > 0 else 0

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
                'version': '2.0'
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
