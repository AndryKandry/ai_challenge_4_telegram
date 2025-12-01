"""
FileSystemTool - Расширенный инструмент для работы с файловой системой.

Предоставляет интеллектуальные возможности для поиска, анализа,
мониторинга и управления файлами и директориями.
"""

import os
import re
import hashlib
import mimetypes
from typing import List, Dict, Optional, AsyncIterator, Callable, Any
from pathlib import Path
import asyncio
import time
import logging
from datetime import datetime

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class FileMatch:
    """Результат поиска файла."""
    
    def __init__(
        self,
        path: str,
        name: str,
        size: int,
        modified_time: float,
        file_type: str,
        match_type: str = "pattern",
        score: float = 1.0
    ):
        self.path = path
        self.name = name
        self.size = size
        self.modified_time = modified_time
        self.file_type = file_type
        self.match_type = match_type
        self.score = score

    def to_dict(self) -> Dict:
        """Преобразует в словарь."""
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "modified_time": self.modified_time,
            "modified_date": datetime.fromtimestamp(self.modified_time).isoformat(),
            "file_type": self.file_type,
            "match_type": self.match_type,
            "score": self.score
        }


class FileAnalysis:
    """Результат анализа файла."""
    
    def __init__(
        self,
        path: str,
        file_type: str,
        language: str,
        size: int,
        lines: int,
        complexity: int,
        dependencies: List[str],
        functions: List[str],
        classes: List[str]
    ):
        self.path = path
        self.file_type = file_type
        self.language = language
        self.size = size
        self.lines = lines
        self.complexity = complexity
        self.dependencies = dependencies
        self.functions = functions
        self.classes = classes

    def to_dict(self) -> Dict:
        """Преобразует в словарь."""
        return {
            "path": self.path,
            "file_type": self.file_type,
            "language": self.language,
            "size": self.size,
            "lines": self.lines,
            "complexity": self.complexity,
            "dependencies": self.dependencies,
            "functions": self.functions,
            "classes": self.classes
        }


class FileChange:
    """Изменение в файловой системе."""
    
    def __init__(
        self,
        change_type: str,
        path: str,
        timestamp: float,
        size: Optional[int] = None
    ):
        self.change_type = change_type  # created, modified, deleted
        self.path = path
        self.timestamp = timestamp
        self.size = size

    def to_dict(self) -> Dict:
        """Преобразует в словарь."""
        return {
            "change_type": self.change_type,
            "path": self.path,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "size": self.size
        }


class DuplicateGroup:
    """Группа дубликатов файлов."""
    
    def __init__(self, hash_value: str, size: int):
        self.hash = hash_value
        self.size = size
        self.files: List[str] = []

    def add_file(self, path: str):
        """Добавляет файл в группу."""
        self.files.append(path)

    def to_dict(self) -> Dict:
        """Преобразует в словарь."""
        return {
            "hash": self.hash,
            "size": self.size,
            "files": self.files,
            "count": len(self.files)
        }


class FileSystemTool(BaseTool):
    """
    Расширенный инструмент для работы с файловой системой.
    
    Возможности:
    - Умный поиск файлов с glob паттернами
    - Анализ файлов (тип, язык, сложность, зависимости)
    - Поиск дубликатов по содержимому
    - Мониторинг изменений в файловой системе
    """

    def __init__(self):
        """Инициализация FileSystemTool."""
        super().__init__(
            name="file_system",
            description="Расширенная работа с файловой системой"
        )
        
        # Кеширование результатов
        self._search_cache = {}
        self._analysis_cache = {}
        self._cache_ttl = 300  # 5 минут
        
        # Поддерживаемые языки программирования
        self.language_extensions = {
            'python': ['.py'],
            'javascript': ['.js', '.mjs'],
            'typescript': ['.ts'],
            'java': ['.java'],
            'cpp': ['.cpp', '.cxx', '.cc'],
            'c': ['.c', '.h'],
            'csharp': ['.cs'],
            'go': ['.go'],
            'rust': ['.rs'],
            'ruby': ['.rb'],
            'php': ['.php'],
            'swift': ['.swift'],
            'kotlin': ['.kt', '.kts'],
            'scala': ['.scala'],
            'html': ['.html', '.htm'],
            'css': ['.css'],
            'sql': ['.sql'],
            'xml': ['.xml'],
            'yaml': ['.yaml', '.yml'],
            'json': ['.json'],
            'markdown': ['.md', '.markdown'],
            'text': ['.txt']
        }

        # Мониторинг изменений
        self._monitoring = False
        self._monitor_callbacks = []
        self._file_states = {}

    async def smart_search(
        self,
        pattern: str,
        path: str = ".",
        recursive: bool = True,
        file_types: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_results: int = 100
    ) -> List[FileMatch]:
        """
        Умный поиск файлов с поддержкой glob паттернов.

        Args:
            pattern: Паттерн поиска (поддерживает glob и regex)
            path: Путь для поиска
            recursive: Рекурсивный поиск
            file_types: Фильтр по типам файлов
            exclude_patterns: Паттерны исключения
            max_results: Максимум результатов

        Returns:
            Список найденных файлов
        """
        cache_key = f"search:{pattern}:{path}:{recursive}:{file_types}:{exclude_patterns}"
        
        # Проверяем кеш
        if cache_key in self._search_cache:
            cached_time, cached_results = self._search_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                logger.debug(f"Using cached search results for {cache_key}")
                return cached_results[:max_results]

        logger.info(f"Smart search: pattern='{pattern}', path='{path}'")
        
        try:
            search_path = Path(path).resolve()
            if not search_path.exists():
                return []

            results = []
            
            # Определяем тип паттерна
            if '*' in pattern or '?' in pattern or '[' in pattern:
                # Glob паттерн
                matches = self._glob_search(
                    search_path, pattern, recursive, file_types, exclude_patterns
                )
            else:
                # Regex паттерн или текстовый поиск
                matches = self._regex_search(
                    search_path, pattern, recursive, file_types, exclude_patterns
                )
            
            # Конвертируем в FileMatch объекты
            for match_path, match_type, score in matches:
                try:
                    stat = match_path.stat()
                    file_match = FileMatch(
                        path=str(match_path),
                        name=match_path.name,
                        size=stat.st_size,
                        modified_time=stat.st_mtime,
                        file_type=self._get_file_type(match_path),
                        match_type=match_type,
                        score=score
                    )
                    results.append(file_match)
                except OSError:
                    continue
            
            # Сортируем по релевантности и дате модификации
            results.sort(key=lambda x: (-x.score, -x.modified_time))
            
            # Кешируем результат
            self._search_cache[cache_key] = (time.time(), results)
            
            logger.info(f"Found {len(results)} files matching pattern '{pattern}'")
            return results[:max_results]

        except Exception as e:
            logger.error(f"Error in smart_search: {e}")
            return []

    def _glob_search(
        self,
        search_path: Path,
        pattern: str,
        recursive: bool,
        file_types: Optional[List[str]],
        exclude_patterns: Optional[List[str]]
    ) -> List[tuple]:
        """Поиск с использованием glob паттернов."""
        results = []
        
        try:
            if recursive:
                matches = search_path.rglob(pattern)
            else:
                matches = search_path.glob(pattern)
            
            for match in matches:
                if self._should_include_file(match, file_types, exclude_patterns):
                    results.append((match, "glob", 1.0))
        
        except Exception as e:
            logger.error(f"Error in glob search: {e}")
        
        return results

    def _regex_search(
        self,
        search_path: Path,
        pattern: str,
        recursive: bool,
        file_types: Optional[List[str]],
        exclude_patterns: Optional[List[str]]
    ) -> List[tuple]:
        """Поиск с использованием регулярных выражений."""
        results = []
        
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Если это не regex, ищем точное совпадение
            regex = None
        
        # Рекурсивный обход директории
        if recursive:
            pattern_to_use = "**/*" if not pattern else f"**/*{pattern}*"
            files = search_path.rglob(pattern_to_use)
        else:
            pattern_to_use = "*" if not pattern else f"*{pattern}*"
            files = search_path.glob(pattern_to_use)
        
        for file_path in files:
            if not file_path.is_file():
                continue
            
            if not self._should_include_file(file_path, file_types, exclude_patterns):
                continue
            
            # Проверяем совпадение имени
            match_type = "name"
            score = 0.5
            
            if regex:
                if regex.search(file_path.name):
                    match_type = "regex"
                    score = 0.8
            elif pattern.lower() in file_path.name.lower():
                match_type = "contains"
                score = 0.6
                if file_path.name.lower().startswith(pattern.lower()):
                    score = 0.9
            
            if score > 0:
                results.append((file_path, match_type, score))
        
        return results

    def _should_include_file(
        self,
        file_path: Path,
        file_types: Optional[List[str]],
        exclude_patterns: Optional[List[str]]
    ) -> bool:
        """Проверяет, нужно ли включать файл в результаты."""
        if not file_path.is_file():
            return False
        
        # Проверяем exclude паттерны
        if exclude_patterns:
            for exclude_pattern in exclude_patterns:
                if exclude_pattern in file_path.name:
                    return False
        
        # Проверяем типы файлов
        if file_types:
            file_ext = file_path.suffix.lower()
            file_type = self._get_file_type(file_path)
            
            if file_type not in file_types and file_ext not in [f".{ft}" for ft in file_types]:
                return False
        
        return True

    async def analyze_file(self, file_path: str) -> FileAnalysis:
        """
        Анализ файла: тип, язык, сложность, зависимости.

        Args:
            file_path: Путь к файлу

        Returns:
            Результат анализа файла
        """
        cache_key = f"analysis:{file_path}"
        
        # Проверяем кеш
        if cache_key in self._analysis_cache:
            cached_time, cached_analysis = self._analysis_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                logger.debug(f"Using cached analysis for {file_path}")
                return cached_analysis
        
        logger.info(f"Analyzing file: {file_path}")
        
        try:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Базовая информация
            file_type = self._get_file_type(path)
            language = self._detect_language(path)
            size = path.stat().st_size
            
            # Анализ содержимого
            if size > 10 * 1024 * 1024:  # 10MB лимит
                logger.warning(f"File too large for analysis: {file_path}")
                return FileAnalysis(
                    path=file_path,
                    file_type=file_type,
                    language=language,
                    size=size,
                    lines=0,
                    complexity=0,
                    dependencies=[],
                    functions=[],
                    classes=[]
                )
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = len(content.splitlines())
            complexity = self._calculate_complexity(content, language)
            dependencies = self._extract_dependencies(content, language)
            functions = self._extract_functions(content, language)
            classes = self._extract_classes(content, language)
            
            analysis = FileAnalysis(
                path=file_path,
                file_type=file_type,
                language=language,
                size=size,
                lines=lines,
                complexity=complexity,
                dependencies=dependencies,
                functions=functions,
                classes=classes
            )
            
            # Кешируем результат
            self._analysis_cache[cache_key] = (time.time(), analysis)
            
            logger.info(f"File analysis completed: {file_path}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return FileAnalysis(
                path=file_path,
                file_type="unknown",
                language="unknown",
                size=0,
                lines=0,
                complexity=0,
                dependencies=[],
                functions=[],
                classes=[]
            )

    def _get_file_type(self, file_path: Path) -> str:
        """Определяет тип файла."""
        # По расширению
        ext = file_path.suffix.lower()
        if ext:
            for language, extensions in self.language_extensions.items():
                if ext in extensions:
                    return language
        
        # По mime типу
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            if mime_type.startswith('text/'):
                return 'text'
            elif mime_type.startswith('image/'):
                return 'image'
            elif mime_type.startswith('audio/'):
                return 'audio'
            elif mime_type.startswith('video/'):
                return 'video'
        
        return 'binary'

    def _detect_language(self, file_path: Path) -> str:
        """Определяет язык программирования."""
        ext = file_path.suffix.lower()
        
        for language, extensions in self.language_extensions.items():
            if ext in extensions:
                return language
        
        # Дополнительная эвристика по имени файла
        name = file_path.name.lower()
        if name in ['makefile', 'dockerfile', 'rakefile', 'gemfile']:
            return 'makefile'
        elif name.endswith('.mk'):
            return 'makefile'
        elif name.startswith('.'):
            return 'config'
        
        return 'text'

    def _calculate_complexity(self, content: str, language: str) -> int:
        """Вычисляет цикломатическую сложность."""
        if language == 'python':
            return self._python_complexity(content)
        elif language in ['javascript', 'typescript']:
            return self._javascript_complexity(content)
        elif language in ['java', 'c', 'cpp', 'csharp']:
            return self._c_like_complexity(content)
        else:
            # Упрощенная оценка для других языков
            complexity_keywords = [
                'if', 'else', 'elif', 'for', 'while', 'do', 'switch', 'case',
                'try', 'except', 'catch', 'finally', 'and', 'or', '&&', '||'
            ]
            complexity = 1  # Базовая сложность
            for keyword in complexity_keywords:
                complexity += content.count(keyword)
            return complexity

    def _python_complexity(self, content: str) -> int:
        """Вычисляет сложность для Python."""
        try:
            import ast
            tree = ast.parse(content)
            complexity = 1
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.With)):
                    complexity += 1
                elif isinstance(node, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            
            return complexity
        except:
            # Fallback если AST парсинг не удался
            keywords = ['if', 'elif', 'for', 'while', 'try', 'except', 'with']
            complexity = 1
            for keyword in keywords:
                complexity += content.count(keyword)
            return complexity

    def _javascript_complexity(self, content: str) -> int:
        """Вычисляет сложность для JavaScript/TypeScript."""
        keywords = [
            'if', 'else if', 'for', 'while', 'do', 'switch', 'case',
            'try', 'catch', 'finally', '&&', '||'
        ]
        complexity = 1
        for keyword in keywords:
            complexity += content.count(keyword)
        return complexity

    def _c_like_complexity(self, content: str) -> int:
        """Вычисляет сложность для C-подобных языков."""
        keywords = [
            'if', 'else if', 'for', 'while', 'do', 'switch', 'case',
            'try', 'catch', '&&', '||'
        ]
        complexity = 1
        for keyword in keywords:
            complexity += content.count(keyword)
        return complexity

    def _extract_dependencies(self, content: str, language: str) -> List[str]:
        """Извлекает зависимости из файла."""
        dependencies = set()
        
        if language == 'python':
            import re
            # import module
            dependencies.update(re.findall(r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)', content, re.MULTILINE))
            # from module import name
            dependencies.update(re.findall(r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import', content, re.MULTILINE))
        
        elif language in ['javascript', 'typescript']:
            import re
            # import name from 'module'
            dependencies.update(re.findall(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', content))
            # require('module')
            dependencies.update(re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', content))
        
        elif language == 'java':
            import re
            # import package.Class
            dependencies.update(re.findall(r'import\s+([a-zA-Z_][a-zA-Z0-9_.*?);', content))
        
        return list(dependencies)

    def _extract_functions(self, content: str, language: str) -> List[str]:
        """Извлекает имена функций."""
        functions = []
        
        if language == 'python':
            import re
            # def function_name(
            functions.extend(re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', content))
        
        elif language in ['javascript', 'typescript']:
            import re
            # function name(
            functions.extend(re.findall(r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', content))
            # const name = function(
            functions.extend(re.findall(r'const\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*function', content))
            # const name = () =>
            functions.extend(re.findall(r'const\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\(', content))
        
        elif language in ['java', 'c', 'cpp', 'csharp']:
            import re
            # return_type name(
            functions.extend(re.findall(r'(?:public|private|protected)?\s*(?:static\s*)?(?:\w+\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', content))
        
        return functions

    def _extract_classes(self, content: str, language: str) -> List[str]:
        """Извлекает имена классов."""
        classes = []
        
        if language == 'python':
            import re
            # class ClassName:
            classes.extend(re.findall(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(|:)', content))
        
        elif language in ['java', 'csharp']:
            import re
            # public class ClassName
            classes.extend(re.findall(r'(?:public\s+)?class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\{|:)', content))
        
        elif language in ['javascript', 'typescript']:
            import re
            # class ClassName
            classes.extend(re.findall(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\{|extends)', content))
        
        elif language == 'cpp':
            import re
            # class ClassName
            classes.extend(re.findall(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\{|:|public|private)', content))
        
        return classes

    async def find_duplicates(self, path: str = ".", recursive: bool = True) -> List[DuplicateGroup]:
        """
        Поиск дубликатов файлов по содержимому.

        Args:
            path: Путь для поиска
            recursive: Рекурсивный поиск

        Returns:
            Список групп дубликатов
        """
        logger.info(f"Finding duplicates in: {path}")
        
        try:
            search_path = Path(path).resolve()
            if not search_path.exists():
                return []
            
            # Собираем все файлы
            files = []
            if recursive:
                for file_path in search_path.rglob("*"):
                    if file_path.is_file() and file_path.stat().st_size < 10 * 1024 * 1024:  # 10MB лимит
                        files.append(file_path)
            else:
                for file_path in search_path.glob("*"):
                    if file_path.is_file() and file_path.stat().st_size < 10 * 1024 * 1024:
                        files.append(file_path)
            
            # Группируем по хэшу
            hash_groups = {}
            
            for file_path in files:
                try:
                    file_hash = self._calculate_file_hash(file_path)
                    file_size = file_path.stat().st_size
                    
                    if file_hash not in hash_groups:
                        hash_groups[file_hash] = DuplicateGroup(file_hash, file_size)
                    
                    hash_groups[file_hash].add_file(str(file_path))
                    
                except Exception as e:
                    logger.warning(f"Error processing {file_path}: {e}")
                    continue
            
            # Фильтруем только дубликаты
            duplicates = [
                group for group in hash_groups.values()
                if len(group.files) > 1
            ]
            
            # Сортируем по размеру группы
            duplicates.sort(key=lambda x: (-len(x.files), -x.size))
            
            total_duplicates = sum(len(group.files) for group in duplicates)
            logger.info(f"Found {len(duplicates)} duplicate groups with {total_duplicates} files")
            
            return duplicates

        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            return []

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Вычисляет хэш файла."""
        hash_md5 = hashlib.md5()
        
        with open(file_path, 'rb') as f:
            # Читаем блоками для больших файлов
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()

    async def monitor_changes(
        self,
        path: str = ".",
        callback: Optional[Callable] = None,
        recursive: bool = True
    ) -> AsyncIterator[FileChange]:
        """
        Мониторинг изменений в файловой системе.

        Args:
            path: Путь для мониторинга
            callback: Callback функция для изменений
            recursive: Рекурсивный мониторинг

        Yields:
            Изменения в файловой системе
        """
        monitor_path = Path(path).resolve()
        if not monitor_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        if callback:
            self._monitor_callbacks.append(callback)
        
        # Инициализация состояния файлов
        self._file_states = {}
        if recursive:
            for file_path in monitor_path.rglob("*"):
                if file_path.is_file():
                    try:
                        self._file_states[str(file_path)] = file_path.stat().st_mtime
                    except OSError:
                        pass
        else:
            for file_path in monitor_path.glob("*"):
                if file_path.is_file():
                    try:
                        self._file_states[str(file_path)] = file_path.stat().st_mtime
                    except OSError:
                        pass
        
        self._monitoring = True
        logger.info(f"Started monitoring {path} for changes")
        
        try:
            while self._monitoring:
                changes = await self._check_for_changes(monitor_path, recursive)
                
                for change in changes:
                    # Вызываем callback если есть
                    for callback in self._monitor_callbacks:
                        try:
                            await callback(change)
                        except Exception as e:
                            logger.error(f"Error in monitor callback: {e}")
                    
                    yield change
                
                # Проверяем каждую секунду
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"Error in monitor_changes: {e}")
        finally:
            self._monitoring = False
            self._monitor_callbacks.clear()
            logger.info(f"Stopped monitoring {path}")

    async def _check_for_changes(self, monitor_path: Path, recursive: bool) -> List[FileChange]:
        """Проверяет изменения в файлах."""
        changes = []
        current_states = {}
        
        # Собираем текущие состояния
        if recursive:
            files = monitor_path.rglob("*")
        else:
            files = monitor_path.glob("*")
        
        for file_path in files:
            if not file_path.is_file():
                continue
            
            try:
                current_time = file_path.stat().st_mtime
                file_path_str = str(file_path)
                current_states[file_path_str] = current_time
                
                # Проверяем на изменение
                if file_path_str in self._file_states:
                    if current_time > self._file_states[file_path_str]:
                        # Файл изменен
                        change = FileChange(
                            change_type="modified",
                            path=file_path_str,
                            timestamp=current_time,
                            size=file_path.stat().st_size
                        )
                        changes.append(change)
                else:
                    # Новый файл
                    change = FileChange(
                        change_type="created",
                        path=file_path_str,
                        timestamp=current_time,
                        size=file_path.stat().st_size
                    )
                    changes.append(change)
            
            except OSError:
                continue
        
        # Проверяем на удаленные файлы
        for file_path_str in self._file_states:
            if file_path_str not in current_states:
                change = FileChange(
                    change_type="deleted",
                    path=file_path_str,
                    timestamp=time.time(),
                    size=None
                )
                changes.append(change)
        
        # Обновляем состояния
        self._file_states = current_states
        
        return changes

    def stop_monitoring(self):
        """Останавливает мониторинг изменений."""
        self._monitoring = False
        logger.info("Monitoring stopped")

    def clear_cache(self):
        """Очищает кеши."""
        self._search_cache.clear()
        self._analysis_cache.clear()
        logger.info("File system tool cache cleared")

    async def get_tool_info(self) -> Dict[str, Any]:
        """Возвращает информацию о инструменте."""
        return {
            "name": self.name,
            "description": self.description,
            "version": "1.0.0",
            "capabilities": [
                "smart_search",
                "file_analysis", 
                "duplicate_detection",
                "change_monitoring"
            ],
            "supported_languages": list(self.language_extensions.keys()),
            "cache_stats": {
                "search_cache_size": len(self._search_cache),
                "analysis_cache_size": len(self._analysis_cache),
                "cache_ttl": self._cache_ttl
            },
            "monitoring_status": self._monitoring
        }

    async def execute(self, command: str, **kwargs) -> Dict[str, Any]:
        """
        Выполняет команду инструмента.

        Args:
            command: Команда для выполнения
            **kwargs: Параметры команды

        Returns:
            Результат выполнения команды
        """
        try:
            if command == "smart_search":
                results = await self.smart_search(**kwargs)
                return {
                    "success": True,
                    "data": [result.to_dict() for result in results],
                    "count": len(results)
                }
            
            elif command == "analyze_file":
                result = await self.analyze_file(kwargs.get("file_path", ""))
                return {
                    "success": True,
                    "data": result.to_dict()
                }
            
            elif command == "find_duplicates":
                results = await self.find_duplicates(**kwargs)
                return {
                    "success": True,
                    "data": [group.to_dict() for group in results],
                    "groups_count": len(results),
                    "total_files": sum(len(group.files) for group in results)
                }
            
            elif command == "start_monitoring":
                # Запуск мониторинга (возвращаем generator для дальнейшего использования)
                return {
                    "success": True,
                    "message": "Use monitor_changes method to start monitoring",
                    "parameters": kwargs
                }
            
            elif command == "stop_monitoring":
                self.stop_monitoring()
                return {
                    "success": True,
                    "message": "Monitoring stopped"
                }
            
            elif command == "clear_cache":
                self.clear_cache()
                return {
                    "success": True,
                    "message": "Cache cleared"
                }
            
            elif command == "get_info":
                info = await self.get_tool_info()
                return {
                    "success": True,
                    "data": info
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown command: {command}"
                }
        
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
