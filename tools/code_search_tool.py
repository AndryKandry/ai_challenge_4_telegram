"""
CodeSearchTool - интеллектуальный поиск по коду с поддержкой паттернов.

Поддерживает поиск по коду, функциям, классам и семантический поиск.
"""

import re
import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
from dataclasses import dataclass

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


@dataclass
class CodeMatch:
    """Результат поиска по коду."""
    file_path: str
    line_number: int
    line_content: str
    context_before: List[str]
    context_after: List[str]
    match_type: str  # 'pattern', 'function', 'class', 'import'
    confidence: float


@dataclass
class FunctionMatch:
    """Результат поиска функции."""
    name: str
    file_path: str
    line_number: int
    signature: str
    docstring: Optional[str]
    is_async: bool
    decorators: List[str]
    context: List[str]


@dataclass
class ClassMatch:
    """Результат поиска класса."""
    name: str
    file_path: str
    line_number: int
    bases: List[str]
    methods: List[str]
    docstring: Optional[str]
    decorators: List[str]


@dataclass
class SemanticMatch:
    """Результат семантического поиска."""
    file_path: str
    content: str
    similarity_score: float
    context: str
    metadata: Dict[str, Any]


class CodeSearchTool(BaseTool):
    """
    Инструмент для интеллектуального поиска по коду.
    
    Возможности:
    - Поиск по регулярным выражениям
    - Поиск определений и вызовов функций
    - Поиск классов и их использования
    - Семантический поиск (если доступны эмбеддинги)
    - Анализ зависимостей
    """

    def __init__(
        self,
        name: str = "code_search",
        supported_extensions: Optional[List[str]] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        context_lines: int = 3,
        enable_semantic_search: bool = False
    ):
        """
        Инициализация CodeSearchTool.

        Args:
            name: Имя инструмента
            supported_extensions: Список поддерживаемых расширений файлов
            max_file_size: Максимальный размер файла для анализа (байты)
            context_lines: Количество строк контекста для результатов поиска
            enable_semantic_search: Включить семантический поиск
        """
        super().__init__(name)
        
        self.supported_extensions = supported_extensions or [
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c',
            '.h', '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs'
        ]
        self.max_file_size = max_file_size
        self.context_lines = context_lines
        self.enable_semantic_search = enable_semantic_search
        
        # Кеши для быстрого поиска
        self._function_cache: Dict[str, List[FunctionMatch]] = {}
        self._class_cache: Dict[str, List[ClassMatch]] = {}
        self._file_index_cache: Dict[str, List[str]] = {}
        
        # Статистика
        self.search_stats = {
            "pattern_searches": 0,
            "function_searches": 0,
            "class_searches": 0,
            "semantic_searches": 0,
            "files_scanned": 0,
            "total_matches": 0
        }

    async def search_code(
        self,
        pattern: str,
        path: str = ".",
        file_types: Optional[List[str]] = None,
        context_lines: Optional[int] = None,
        case_sensitive: bool = False,
        include_tests: bool = False
    ) -> List[CodeMatch]:
        """
        Поиск кода по паттерну.

        Args:
            pattern: Регулярное выражение или текст для поиска
            path: Путь для поиска
            file_types: Фильтр по типам файлов
            context_lines: Количество строк контекста
            case_sensitive: Чувствительность к регистру
            include_tests: Включать тестовые файлы

        Returns:
            Список результатов поиска
        """
        logger.info(f"Searching code pattern: '{pattern}' in {path}")
        self.search_stats["pattern_searches"] += 1
        
        try:
            # Компилируем регулярное выражение
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
            
            # Получаем список файлов для поиска
            files = await self._get_files_to_search(
                path, file_types, include_tests
            )
            
            matches = []
            context_lines = context_lines or self.context_lines
            
            # Ищем в каждом файле
            for file_path in files:
                file_matches = await self._search_in_file(
                    file_path, regex, context_lines
                )
                matches.extend(file_matches)
            
            # Сортируем по релевантности
            matches.sort(key=lambda x: x.confidence, reverse=True)
            
            logger.info(f"Found {len(matches)} matches for pattern: '{pattern}'")
            self.search_stats["total_matches"] += len(matches)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error searching code pattern '{pattern}': {e}")
            return []

    async def search_function_calls(
        self,
        function_name: str,
        path: str = ".",
        include_definitions: bool = True,
        include_calls: bool = True,
        file_types: Optional[List[str]] = None
    ) -> List[FunctionMatch]:
        """
        Поиск определений и вызовов функций.

        Args:
            function_name: Имя функции для поиска
            path: Путь для поиска
            include_definitions: Включать определения функций
            include_calls: Включать вызовы функций
            file_types: Фильтр по типам файлов

        Returns:
            Список результатов поиска функций
        """
        logger.info(f"Searching function: '{function_name}' in {path}")
        self.search_stats["function_searches"] += 1
        
        try:
            files = await self._get_files_to_search(path, file_types, False)
            matches = []
            
            for file_path in files:
                if not file_path.endswith('.py'):
                    continue  # Пока только Python
                
                file_matches = await self._search_functions_in_file(
                    file_path, function_name, include_definitions, include_calls
                )
                matches.extend(file_matches)
            
            logger.info(f"Found {len(matches)} function matches for: '{function_name}'")
            return matches
            
        except Exception as e:
            logger.error(f"Error searching function '{function_name}': {e}")
            return []

    async def search_class_usage(
        self,
        class_name: str,
        path: str = ".",
        include_definitions: bool = True,
        include_inheritance: bool = True,
        include_instantiation: bool = True,
        file_types: Optional[List[str]] = None
    ) -> List[ClassMatch]:
        """
        Поиск использования класса.

        Args:
            class_name: Имя класса для поиска
            path: Путь для поиска
            include_definitions: Включать определения классов
            include_inheritance: Включать наследование
            include_instantiation: Включать создание экземпляров
            file_types: Фильтр по типам файлов

        Returns:
            Список результатов поиска классов
        """
        logger.info(f"Searching class: '{class_name}' in {path}")
        self.search_stats["class_searches"] += 1
        
        try:
            files = await self._get_files_to_search(path, file_types, False)
            matches = []
            
            for file_path in files:
                if not file_path.endswith('.py'):
                    continue  # Пока только Python
                
                file_matches = await self._search_classes_in_file(
                    file_path, class_name, include_definitions,
                    include_inheritance, include_instantiation
                )
                matches.extend(file_matches)
            
            logger.info(f"Found {len(matches)} class matches for: '{class_name}'")
            return matches
            
        except Exception as e:
            logger.error(f"Error searching class '{class_name}': {e}")
            return []

    async def semantic_search(
        self,
        query: str,
        path: str = ".",
        limit: int = 10,
        file_types: Optional[List[str]] = None,
        min_similarity: float = 0.5
    ) -> List[SemanticMatch]:
        """
        Семантический поиск по коду.

        Args:
            query: Семантический запрос
            path: Путь для поиска
            limit: Максимальное количество результатов
            file_types: Фильтр по типам файлов
            min_similarity: Минимальный порог схожести

        Returns:
            Список семантических совпадений
        """
        logger.info(f"Semantic search: '{query}' in {path}")
        self.search_stats["semantic_searches"] += 1
        
        if not self.enable_semantic_search:
            logger.warning("Semantic search is not enabled")
            return []
        
        try:
            # TODO: Интегрировать с эмбеддингами
            # Временная реализация - поиск по ключевым словам
            files = await self._get_files_to_search(path, file_types, False)
            matches = []
            
            query_words = set(query.lower().split())
            
            for file_path in files:
                content = await self._read_file_content(file_path)
                if not content:
                    continue
                
                # Простая эвристика для семантического поиска
                content_words = set(content.lower().split())
                overlap = len(query_words.intersection(content_words))
                similarity = overlap / len(query_words) if query_words else 0
                
                if similarity >= min_similarity:
                    match = SemanticMatch(
                        file_path=file_path,
                        content=content[:1000] + "..." if len(content) > 1000 else content,
                        similarity_score=similarity,
                        context=content[:200] + "..." if len(content) > 200 else content,
                        metadata={"file_size": len(content)}
                    )
                    matches.append(match)
            
            # Сортируем по схожести
            matches.sort(key=lambda x: x.similarity_score, reverse=True)
            
            return matches[:limit]
            
        except Exception as e:
            logger.error(f"Error in semantic search '{query}': {e}")
            return []

    async def analyze_dependencies(
        self,
        path: str = ".",
        file_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Анализ зависимостей в коде.

        Args:
            path: Путь для анализа
            file_types: Фильтр по типам файлов

        Returns:
            Словарь с информацией о зависимостях
        """
        logger.info(f"Analyzing dependencies in: {path}")
        
        try:
            files = await self._get_files_to_search(path, file_types, False)
            imports = {}
            dependencies = {}
            
            for file_path in files:
                if not file_path.endswith('.py'):
                    continue
                
                file_imports = await self._extract_imports(file_path)
                imports[file_path] = file_imports
                
                # Анализируем зависимости
                for imp in file_imports:
                    module = imp.split('.')[0]
                    if module not in dependencies:
                        dependencies[module] = []
                    dependencies[module].append(file_path)
            
            return {
                "imports": imports,
                "dependencies": dependencies,
                "total_files": len(files),
                "unique_dependencies": len(dependencies)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            return {}

    async def _get_files_to_search(
        self,
        path: str,
        file_types: Optional[List[str]],
        include_tests: bool
    ) -> List[str]:
        """Получает список файлов для поиска."""
        files = []
        path_obj = Path(path)
        
        if path_obj.is_file():
            return [str(path_obj)]
        
        # Рекурсивный обход директории
        for file_path in path_obj.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Фильтр по расширениям
            if file_types:
                if not any(file_path.suffix == ft for ft in file_types):
                    continue
            elif file_path.suffix not in self.supported_extensions:
                continue
            
            # Фильтр тестовых файлов
            if not include_tests and self._is_test_file(file_path):
                continue
            
            # Фильтр по размеру
            if file_path.stat().st_size > self.max_file_size:
                logger.warning(f"Skipping large file: {file_path}")
                continue
            
            files.append(str(file_path))
        
        self.search_stats["files_scanned"] += len(files)
        return files

    async def _search_in_file(
        self,
        file_path: str,
        regex: re.Pattern,
        context_lines: int
    ) -> List[CodeMatch]:
        """Поиск паттерна в файле."""
        try:
            content = await self._read_file_content(file_path)
            if not content:
                return []
            
            lines = content.split('\n')
            matches = []
            
            for line_num, line in enumerate(lines, 1):
                if regex.search(line):
                    # Получаем контекст
                    start = max(0, line_num - 1 - context_lines)
                    end = min(len(lines), line_num + context_lines)
                    
                    context_before = lines[start:line_num-1]
                    context_after = lines[line_num:end]
                    
                    # Вычисляем уверенность
                    confidence = self._calculate_pattern_confidence(
                        regex, line, line_num, len(lines)
                    )
                    
                    match = CodeMatch(
                        file_path=file_path,
                        line_number=line_num,
                        line_content=line,
                        context_before=context_before,
                        context_after=context_after,
                        match_type="pattern",
                        confidence=confidence
                    )
                    matches.append(match)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error searching in file {file_path}: {e}")
            return []

    async def _search_functions_in_file(
        self,
        file_path: str,
        function_name: str,
        include_definitions: bool,
        include_calls: bool
    ) -> List[FunctionMatch]:
        """Поиск функций в файле."""
        try:
            content = await self._read_file_content(file_path)
            if not content:
                return []
            
            matches = []
            
            try:
                tree = ast.parse(content)
            except SyntaxError:
                logger.warning(f"Cannot parse Python file: {file_path}")
                return []
            
            # Поиск определений функций
            if include_definitions:
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == function_name:
                        match = self._create_function_match(node, file_path, "definition")
                        matches.append(match)
            
            # Поиск вызовов функций
            if include_calls:
                function_pattern = re.compile(rf'\b{re.escape(function_name)}\s*\(')
                lines = content.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    if function_pattern.search(line):
                        # Создаем простой матч для вызова
                        match = FunctionMatch(
                            name=function_name,
                            file_path=file_path,
                            line_number=line_num,
                            signature=line.strip(),
                            docstring=None,
                            is_async="async " in line,
                            decorators=[],
                            context=[lines[max(0, line_num-2):line_num+2]]
                        )
                        matches.append(match)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error searching functions in {file_path}: {e}")
            return []

    async def _search_classes_in_file(
        self,
        file_path: str,
        class_name: str,
        include_definitions: bool,
        include_inheritance: bool,
        include_instantiation: bool
    ) -> List[ClassMatch]:
        """Поиск классов в файле."""
        try:
            content = await self._read_file_content(file_path)
            if not content:
                return []
            
            matches = []
            
            try:
                tree = ast.parse(content)
            except SyntaxError:
                logger.warning(f"Cannot parse Python file: {file_path}")
                return []
            
            # Поиск определений классов
            if include_definitions:
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == class_name:
                        match = self._create_class_match(node, file_path)
                        matches.append(match)
            
            # Поиск наследования и инстанциации
            if include_inheritance or include_instantiation:
                lines = content.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    # Поиск наследования
                    if include_inheritance and f"({class_name})" in line:
                        match = ClassMatch(
                            name=class_name,
                            file_path=file_path,
                            line_number=line_num,
                            bases=[class_name],
                            methods=[],
                            docstring=None,
                            decorators=[],
                            context=[lines[max(0, line_num-2):line_num+2]]
                        )
                        matches.append(match)
                    
                    # Поиск инстанциации
                    if include_instantiation and re.search(rf'\b{re.escape(class_name)}\s*\(', line):
                        if "class " not in line:  # Исключаем определения
                            match = ClassMatch(
                                name=class_name,
                                file_path=file_path,
                                line_number=line_num,
                                bases=[],
                                methods=[],
                                docstring=None,
                                decorators=[],
                                context=[lines[max(0, line_num-2):line_num+2]]
                            )
                            matches.append(match)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error searching classes in {file_path}: {e}")
            return []

    async def _extract_imports(self, file_path: str) -> List[str]:
        """Извлекает импорты из файла."""
        try:
            content = await self._read_file_content(file_path)
            if not content:
                return []
            
            imports = []
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line.startswith('import '):
                    imports.append(line[7:].strip())
                elif line.startswith('from '):
                    imports.append(line)
            
            return imports
            
        except Exception as e:
            logger.error(f"Error extracting imports from {file_path}: {e}")
            return []

    async def _read_file_content(self, file_path: str) -> Optional[str]:
        """Читает содержимое файла."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None

    def _is_test_file(self, file_path: Path) -> bool:
        """Проверяет, является ли файл тестовым."""
        name = file_path.name.lower()
        path_parts = [part.lower() for part in file_path.parts]
        
        test_indicators = [
            'test_', '_test.', 'tests', 'spec'
        ]
        
        return any(indicator in name or indicator in path_parts for indicator in test_indicators)

    def _calculate_pattern_confidence(
        self,
        regex: re.Pattern,
        line: str,
        line_num: int,
        total_lines: int
    ) -> float:
        """Вычисляет уверенность в совпадении паттерна."""
        confidence = 0.5  # Базовая уверенность
        
        # Чем точнее совпадение, тем выше уверенность
        match = regex.search(line)
        if match:
            # Учет длины совпадения
            match_length = len(match.group())
            line_length = len(line)
            if match_length > 0:
                confidence += (match_length / line_length) * 0.3
            
            # Учет положения в файле (середина важнее концов)
            position_factor = 1.0 - abs(line_num - total_lines/2) / (total_lines/2)
            confidence += position_factor * 0.2
        
        return min(confidence, 1.0)

    def _create_function_match(
        self,
        node: ast.FunctionDef,
        file_path: str,
        match_type: str
    ) -> FunctionMatch:
        """Создает FunctionMatch из AST узла."""
        signature = f"def {node.name}("
        
        # Добавляем параметры
        if node.args.args:
            args = [arg.arg for arg in node.args.args]
            signature += ", ".join(args)
        
        signature += ")"
        
        docstring = ast.get_docstring(node)
        
        return FunctionMatch(
            name=node.name,
            file_path=file_path,
            line_number=node.lineno,
            signature=signature,
            docstring=docstring,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=[d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
            context=[]
        )

    def _create_class_match(
        self,
        node: ast.ClassDef,
        file_path: str
    ) -> ClassMatch:
        """Создает ClassMatch из AST узла."""
        bases = [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases]
        methods = [method.name for method in node.body if isinstance(method, ast.FunctionDef)]
        docstring = ast.get_docstring(node)
        
        return ClassMatch(
            name=node.name,
            file_path=file_path,
            line_number=node.lineno,
            bases=bases,
            methods=methods,
            docstring=docstring,
            decorators=[d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
        )

    def get_search_stats(self) -> Dict[str, Any]:
        """Возвращает статистику поиска."""
        return self.search_stats.copy()

    def clear_caches(self) -> None:
        """Очищает кеши."""
        self._function_cache.clear()
        self._class_cache.clear()
        self._file_index_cache.clear()
        logger.info("Code search caches cleared")

    async def execute(self, **params) -> Dict[str, Any]:
        """
        Основной метод выполнения инструмента.

        Args:
            action: Тип поиска ('pattern', 'function', 'class', 'semantic', 'dependencies')
            **params: Параметры для конкретного типа поиска

        Returns:
            Результат поиска
        """
        action = params.get('action', 'pattern')
        
        try:
            if action == 'pattern':
                return await self.search_code(**params)
            elif action == 'function':
                return await self.search_function_calls(**params)
            elif action == 'class':
                return await self.search_class_usage(**params)
            elif action == 'semantic':
                return await self.semantic_search(**params)
            elif action == 'dependencies':
                return await self.analyze_dependencies(**params)
            else:
                raise ValueError(f"Unknown action: {action}")
                
        except Exception as e:
            logger.error(f"Error executing code search: {e}")
            return {"error": str(e), "results": []}

    def get_tool_info(self) -> Dict[str, Any]:
        """Возвращает информацию об инструменте."""
        return {
            "name": self.name,
            "description": "Intelligent code search tool",
            "supported_extensions": self.supported_extensions,
            "max_file_size": self.max_file_size,
            "context_lines": self.context_lines,
            "semantic_search_enabled": self.enable_semantic_search,
            "search_stats": self.get_search_stats()
        }
