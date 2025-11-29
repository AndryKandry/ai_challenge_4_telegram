#!/usr/bin/env python3
"""
Модуль для генерации кликабельных MCP-ссылок на источники документов.
Обеспечивает создание ссылок, которые открывают документы через MCP filesystem сервер.
"""

import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import urllib.parse

logger = logging.getLogger(__name__)


class MCPLinkGenerator:
    """
    Генератор кликабельных ссылок для MCP filesystem сервера.
    
    Создает ссылки в формате mcp://filesystem/path/to/document.txt,
    которые могут быть обработаны MCP клиентом для открытия документов.
    """
    
    def __init__(self, mcp_server_url: str = "http://localhost:8003", base_path: Optional[str] = None):
        """
        Инициализация генератора MCP-ссылок.
        
        Args:
            mcp_server_url: URL MCP filesystem сервера
            base_path: Базовый путь для документов (опционально)
        """
        self.mcp_server_url = mcp_server_url.rstrip('/')
        self.base_path = Path(base_path) if base_path else None
        self.supported_extensions = {'.txt', '.md', '.markdown'}
        
        logger.info(f"MCPLinkGenerator initialized: server={mcp_server_url}, base_path={base_path}")
    
    def generate_file_link(self, file_path: str, line_numbers: Optional[str] = None) -> str:
        """
        Генерирует кликабельную ссылку на файл через MCP.
        
        Args:
            file_path: Путь к файлу
            line_numbers: Номера строк (опционально)
            
        Returns:
            Кликабельная ссылка в формате MCP URI
        """
        try:
            # Нормализация пути
            file_path = str(Path(file_path).as_posix())
            
            # Кодирование URL
            encoded_path = urllib.parse.quote(file_path, safe='')
            
            # Формирование MCP URI
            mcp_uri = f"mcp://filesystem/{encoded_path}"
            
            # Добавляем информацию о строках если есть
            if line_numbers:
                mcp_uri += f"#lines={line_numbers}"
            
            return mcp_uri
            
        except Exception as e:
            logger.error(f"Error generating MCP link for {file_path}: {e}")
            return file_path  # Fallback на обычный путь
    
    def get_file_emoji(self, file_path: str) -> str:
        """
        Возвращает эмодзи для типа файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Эмодзи соответствующий типу файла
        """
        extension = Path(file_path).suffix.lower()
        
        emoji_map = {
            '.txt': '📄',
            '.md': '📝',
            '.markdown': '📝',
            '.py': '🐍',
            '.js': '🟨',
            '.json': '📋',
            '.yaml': '📄',
            '.yml': '📄',
        }
        
        return emoji_map.get(extension, '📄')
    
    def format_clickable_source(
        self,
        source_file: str,
        chunk_id: str,
        line_numbers: str,
        relevance: str,
        max_filename_length: int = 30
    ) -> str:
        """
        Форматирует кликабельный источник для отображения в Telegram.
        
        Args:
            source_file: Путь к исходному файлу
            chunk_id: ID чанка
            line_numbers: Номера строк
            relevance: Релевантность в процентах
            max_filename_length: Максимальная длина имени файла
            
        Returns:
            Отформатированная строка с кликабельной ссылкой
        """
        try:
            file_path = Path(source_file)
            file_name = file_path.name
            
            # Обрезаем длинные имена файлов
            if len(file_name) > max_filename_length:
                name_part = file_name[:max_filename_length-3]
                extension = file_path.suffix
                file_name = f"{name_part}...{extension}"
            
            # Генерируем кликабельную ссылку
            link = self.generate_file_link(source_file, line_numbers)
            
            # Получаем эмодзи для файла
            emoji = self.get_file_emoji(source_file)
            
            # Форматируем для Telegram Markdown
            formatted_source = f"{emoji} [{file_name}]({link})"
            
            # Добавляем информацию о строках и релевантности
            if line_numbers and line_numbers != "unknown":
                formatted_source += f" - строки {line_numbers}"
            
            if relevance and relevance != "0%":
                formatted_source += f" (релевантность: {relevance})"
            
            return formatted_source
            
        except Exception as e:
            logger.error(f"Error formatting clickable source: {e}")
            # Fallback формат
            return f"📄 {Path(source_file).name} - строки {line_numbers}"
    
    def format_clickable_sources(
        self,
        search_results: List[Dict],
        max_sources: int = 5,
        title: str = "📚 **Источники:**"
    ) -> str:
        """
        Форматирует список кликабельных источников для ответа модели.
        
        Args:
            search_results: Результаты поиска RAG
            max_sources: Максимальное количество источников
            title: Заголовок списка источников
            
        Returns:
            Отформатированная строка с кликабельными источниками
        """
        if not search_results:
            return ""
        
        try:
            # Ограничиваем количество источников
            sources_to_use = search_results[:max_sources]
            
            # Формируем заголовок
            result = f"\n\n{title}\n"
            
            # Добавляем каждый источник
            for i, result_item in enumerate(sources_to_use, 1):
                source_file = result_item.get('source_file', 'unknown')
                chunk_id = result_item.get('chunk_id', f'chunk_{i}')
                line_numbers = result_item.get('line_numbers', 'unknown')
                relevance = result_item.get('relevance_percentage', '0%')
                
                formatted_source = self.format_clickable_source(
                    source_file, chunk_id, line_numbers, relevance
                )
                
                result += f"{i}. {formatted_source}\n"
            
            # Добавляем примечание о MCP
            result += "\n💡 *Нажмите на ссылку чтобы открыть документ через MCP*"
            
            return result
            
        except Exception as e:
            logger.error(f"Error formatting clickable sources: {e}")
            return "\n\n📚 Источники: недоступны"
    
    def is_supported_file(self, file_path: str) -> bool:
        """
        Проверяет, поддерживается ли тип файла для кликабельных ссылок.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если файл поддерживается
        """
        extension = Path(file_path).suffix.lower()
        return extension in self.supported_extensions
    
    def filter_supported_sources(self, search_results: List[Dict]) -> List[Dict]:
        """
        Фильтрует источники, оставляя только поддерживаемые типы файлов.
        
        Args:
            search_results: Результаты поиска RAG
            
        Returns:
            Отфильтрованный список источников
        """
        supported_sources = []
        
        for result in search_results:
            source_file = result.get('source_file', '')
            if self.is_supported_file(source_file):
                supported_sources.append(result)
            else:
                logger.debug(f"Skipping unsupported file: {source_file}")
        
        return supported_sources
    
    def create_mcp_client_config(self) -> Dict:
        """
        Создает конфигурацию MCP клиента для подключения к filesystem серверу.
        
        Returns:
            Словарь с конфигурацией MCP клиента
        """
        return {
            "type": "http",
            "url": f"{self.mcp_server_url}/sse",
            "headers": {}
        }
    
    def validate_file_path(self, file_path: str) -> Tuple[bool, str]:
        """
        Валидирует путь к файлу для безопасности.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Кортеж (is_valid, error_message)
        """
        try:
            path = Path(file_path)
            
            # Проверяем, что путь не содержит опасных последовательностей
            if '..' in path.parts:
                return False, "Path traversal detected"
            
            # Проверяем, что это файл (не директория)
            if path.suffix == '':
                return False, "Not a file"
            
            # Проверяем расширение
            if not self.is_supported_file(file_path):
                return False, f"Unsupported file type: {path.suffix}"
            
            # Проверяем существование файла (опционально)
            if self.base_path:
                full_path = self.base_path / path if not path.is_absolute() else path
                if not full_path.exists():
                    return False, f"File not found: {full_path}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation error: {e}"


def create_mcp_link_generator(
    mcp_server_url: str = "http://localhost:8003",
    base_path: Optional[str] = None
) -> MCPLinkGenerator:
    """
    Фабричная функция для создания MCPLinkGenerator.
    
    Args:
        mcp_server_url: URL MCP filesystem сервера
        base_path: Базовый путь для документов
        
    Returns:
        Экземпляр MCPLinkGenerator
    """
    return MCPLinkGenerator(mcp_server_url, base_path)
