#!/usr/bin/env python3
"""
Модуль для обработки кликабельных ссылок на документы в Telegram.
Обеспечивает создание inline кнопок и открытие чанков документов.
"""

import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

logger = logging.getLogger(__name__)


class TelegramDocumentHandler:
    """
    Обработчик кликабельных ссылок на документы для Telegram.
    
    Создает inline кнопки для источников документов и обрабатывает их нажатия.
    """
    
    def __init__(self, rag_manager, max_chunk_length: int = 3000):
        """
        Инициализация обработчика документов.
        
        Args:
            rag_manager: RAG менеджер для получения контента документов
            max_chunk_length: Максимальная длина чанка для отображения
        """
        self.rag_manager = rag_manager
        self.max_chunk_length = max_chunk_length
        self.callback_data_prefix = "doc_"
        
        logger.info(f"TelegramDocumentHandler initialized: max_chunk_length={max_chunk_length}")
    
    def create_document_button(
        self,
        source_file: str,
        chunk_id: str,
        line_numbers: str,
        relevance: str,
        max_filename_length: int = 25
    ) -> InlineKeyboardButton:
        """
        Создает inline кнопку для документа.
        
        Args:
            source_file: Путь к исходному файлу
            chunk_id: ID чанка
            line_numbers: Номера строк
            relevance: Релевантность
            max_filename_length: Максимальная длина имени файла
            
        Returns:
            InlineKeyboardButton для документа
        """
        try:
            file_path = Path(source_file)
            file_name = file_path.name
            
            # Обрезаем длинные имена файлов
            if len(file_name) > max_filename_length:
                name_part = file_name[:max_filename_length-3]
                extension = file_path.suffix
                file_name = f"{name_part}...{extension}"
            
            # Получаем эмодзи для файла
            emoji = self._get_file_emoji(source_file)
            
            # Формируем текст кнопки
            button_text = f"{emoji} {file_name}"
            if relevance and relevance != "0%":
                button_text += f" ({relevance})"
            
            # Создаем callback_data
            callback_data = self._create_callback_data(
                source_file, chunk_id, line_numbers
            )
            
            return InlineKeyboardButton(
                text=button_text,
                callback_data=callback_data
            )
            
        except Exception as e:
            logger.error(f"Error creating document button: {e}")
            # Fallback кнопка
            return InlineKeyboardButton(
                text=f"📄 {Path(source_file).name}",
                callback_data="error_invalid_link"
            )
    
    def create_document_inline_keyboard(
        self,
        search_results: List[Dict],
        max_sources: int = 5
    ) -> Optional[InlineKeyboardMarkup]:
        """
        Создает inline клавиатуру с кнопками документов.
        
        Args:
            search_results: Результаты поиска RAG
            max_sources: Максимальное количество источников
            
        Returns:
            InlineKeyboardMarkup с кнопками документов
        """
        if not search_results:
            return None
        
        try:
            # Ограничиваем количество источников
            sources_to_use = search_results[:max_sources]
            
            # Создаем кнопки для каждого источника
            buttons = []
            for i, result_item in enumerate(sources_to_use):
                source_file = result_item.get('source_file', 'unknown')
                chunk_id = result_item.get('chunk_id', f'chunk_{i}')
                line_numbers = result_item.get('line_numbers', 'unknown')
                relevance = result_item.get('relevance_percentage', '0%')
                
                # Создаем кнопку для документа
                button = self.create_document_button(
                    source_file, chunk_id, line_numbers, relevance
                )
                
                buttons.append([button])  # Каждая кнопка на новой строке
            
            if buttons:
                return InlineKeyboardMarkup(buttons)
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating document inline keyboard: {e}")
            return None
    
    def format_sources_with_buttons(
        self,
        search_results: List[Dict],
        max_sources: int = 5,
        title: str = "📚 **Источники:**"
    ) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """
        Форматирует источники с inline кнопками для Telegram.
        
        Args:
            search_results: Результаты поиска RAG
            max_sources: Максимальное количество источников
            title: Заголовок списка источников
            
        Returns:
            Кортеж (текст_с_заголовком, inline_keyboard)
        """
        if not search_results:
            return "", None
        
        try:
            # Формируем заголовок
            header = f"\n\n{title}\n"
            
            # Добавляем информацию о количестве источников
            sources_count = min(len(search_results), max_sources)
            header += f"📊 Найдено источников: {sources_count}\n"
            
            # Создаем inline клавиатуру
            keyboard = self.create_document_inline_keyboard(search_results, max_sources)
            
            # Добавляем инструкцию
            instruction = "\n💡 *Нажмите на документ чтобы посмотреть отрывок*"
            
            full_text = header + instruction
            
            return full_text, keyboard
            
        except Exception as e:
            logger.error(f"Error formatting sources with buttons: {e}")
            # Fallback на обычный текст
            fallback_text = f"\n\n{title}\nИсточники временно недоступны"
            return fallback_text, None
    
    async def handle_document_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обрабатывает нажатие на кнопку документа.

        Args:
            update: Объект обновления Telegram
            context: Контекст выполнения
        """
        try:
            callback_query = update.callback_query
            await callback_query.answer()

            # Парсим callback_data
            callback_data = callback_query.data
            if not callback_data.startswith("doc:"):
                await callback_query.edit_message_text(
                    "❌ Неверная ссылка на документ"
                )
                return

            # Извлекаем информацию о документе
            doc_info = self._parse_callback_data(callback_data)
            if not doc_info or not doc_info['chunk_id']:
                await callback_query.edit_message_text(
                    "❌ Ошибка чтения информации о документе"
                )
                return

            chunk_id = doc_info['chunk_id']

            # Получаем содержимое документа по chunk_id
            # source_file и line_numbers будут извлечены из индекса
            chunk_info = await self._get_chunk_content_by_id(chunk_id)

            if chunk_info:
                source_file = chunk_info.get('source_file', 'unknown')
                chunk_content = chunk_info.get('content', '')
                line_numbers = chunk_info.get('line_numbers', 'unknown')

                # Форматируем и отправляем ответ
                await self._send_document_preview(
                    callback_query, source_file, chunk_content, line_numbers
                )
            else:
                await callback_query.edit_message_text(
                    f"❌ Не удалось загрузить документ с ID: `{chunk_id[:20]}...`"
                )

        except Exception as e:
            logger.error(f"Error handling document callback: {e}", exc_info=True)
            try:
                await update.callback_query.edit_message_text(
                    "❌ Произошла ошибка при открытии документа"
                )
            except:
                pass
    
    async def _get_chunk_content(
        self,
        source_file: str,
        chunk_id: str,
        line_numbers: str
    ) -> Optional[str]:
        """
        Получает содержимое чанка документа (deprecated).
        Используйте _get_chunk_content_by_id вместо этого.

        Args:
            source_file: Путь к файлу
            chunk_id: ID чанка
            line_numbers: Номера строк

        Returns:
            Содержимое чанка или None
        """
        # Перенаправляем на новый метод
        chunk_info = await self._get_chunk_content_by_id(chunk_id)
        if chunk_info:
            return chunk_info.get('content')
        return None

    async def _get_chunk_content_by_id(
        self,
        chunk_id: str
    ) -> Optional[Dict]:
        """
        Получает содержимое чанка по ID.

        Args:
            chunk_id: ID чанка

        Returns:
            Словарь с информацией о чанке: {source_file, content, line_numbers}
        """
        try:
            # Используем прямой доступ к индексу через RAG Manager
            chunk = self.rag_manager.get_chunk_by_id(chunk_id)

            if not chunk:
                logger.warning(f"Chunk not found by ID: {chunk_id}")
                return None

            # Извлекаем данные из чанка
            # source_file находится на верхнем уровне, а не в metadata
            source_file = chunk.get('source_file', 'unknown')
            chunk_text = chunk.get('text', '')

            # Пытаемся вычислить номера строк из метаданных
            metadata = chunk.get('metadata', {})
            char_start = metadata.get('char_start', 0)
            char_end = metadata.get('char_end', 0)

            # Примерная оценка номеров строк (80 символов на строку в среднем)
            if char_start and char_end:
                start_line = char_start // 80 + 1
                end_line = char_end // 80 + 1
                line_numbers = f"{start_line}-{end_line}"
            else:
                line_numbers = "unknown"

            # Ограничиваем длину
            if len(chunk_text) > self.max_chunk_length:
                chunk_text = chunk_text[:self.max_chunk_length]
                chunk_text += "\n\n... (отрывок сокращен)"

            return {
                'source_file': source_file,
                'content': chunk_text,
                'line_numbers': line_numbers
            }

        except Exception as e:
            logger.error(f"Error getting chunk content by ID: {e}")
            return None
    
    async def _send_document_preview(
        self,
        callback_query,
        source_file: str,
        chunk_content: str,
        line_numbers: str
    ) -> None:
        """
        Отправляет превью документа.
        
        Args:
            callback_query: Callback query объект
            source_file: Путь к исходному файлу
            chunk_content: Содержимое чанка
            line_numbers: Номера строк
        """
        try:
            file_name = Path(source_file).name
            emoji = self._get_file_emoji(source_file)
            
            # Форматируем сообщение
            preview_text = (
                f"{emoji} **{file_name}**\n\n"
                f"📄 *Отрывок документа:*\n\n"
            )
            
            # Добавляем информацию о строках если есть
            if line_numbers and line_numbers != "unknown":
                preview_text += f"📍 Строки: {line_numbers}\n\n"
            
            # Добавляем содержимое
            preview_text += f"```text\n{chunk_content}\n```"
            
            # Добавляем кнопку для закрытия
            close_button = InlineKeyboardButton(
                text="❌ Закрыть",
                callback_data="close_preview"
            )
            
            keyboard = InlineKeyboardMarkup([[close_button]])
            
            # Редактируем сообщение
            await callback_query.edit_message_text(
                text=preview_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error sending document preview: {e}")
            raise
    
    def _get_file_emoji(self, file_path: str) -> str:
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
    
    def _create_callback_data(
        self,
        source_file: str,
        chunk_id: str,
        line_numbers: str
    ) -> str:
        """
        Создает callback_data для inline кнопки.

        ВАЖНО: Telegram ограничивает callback_data до 64 байт.
        Используем только chunk_id вместо полного пути к файлу.

        Args:
            source_file: Путь к файлу (не используется, chunk_id достаточно)
            chunk_id: ID чанка (уникальный идентификатор)
            line_numbers: Номера строк

        Returns:
            Закодированная строка callback_data (< 64 байт)
        """
        # Используем только chunk_id для минимального размера callback_data
        # chunk_id уникально идентифицирует чанк в индексе
        # Telegram limit: 64 bytes

        # Формат: doc:<chunk_id>
        # Это гарантирует короткий callback_data
        callback_data = f"doc:{chunk_id}"

        # Проверяем длину (должно быть меньше 64 байт)
        if len(callback_data.encode('utf-8')) > 64:
            # Обрезаем chunk_id если слишком длинный
            max_chunk_id_length = 64 - len("doc:") - 5  # запас
            chunk_id_short = chunk_id[:max_chunk_id_length]
            callback_data = f"doc:{chunk_id_short}"
            logger.warning(f"Chunk ID too long, truncated: {chunk_id} -> {chunk_id_short}")

        return callback_data
    
    def _parse_callback_data(self, callback_data: str) -> Optional[Dict]:
        """
        Парсит callback_data из inline кнопки.

        Args:
            callback_data: Строка callback_data формата "doc:<chunk_id>"

        Returns:
            Словарь с данными о документе
        """
        try:
            # Формат: doc:<chunk_id>
            if not callback_data.startswith("doc:"):
                return None

            # Извлекаем chunk_id
            chunk_id = callback_data[4:]  # Убираем "doc:"

            if not chunk_id:
                logger.error("Empty chunk_id in callback_data")
                return None

            # Возвращаем только chunk_id, source_file найдем из индекса
            return {
                'source_file': '',  # Будет найден через chunk_id
                'chunk_id': chunk_id,
                'line_numbers': ''  # Будет найден через chunk_id
            }

        except Exception as e:
            logger.error(f"Error parsing callback data: {e}")
            return None
    
    def create_callback_handler(self) -> CallbackQueryHandler:
        """
        Создает обработчик callback запросов для документов.
        
        Returns:
            CallbackQueryHandler для обработки нажатий на кнопки
        """
        return CallbackQueryHandler(
            self.handle_document_callback,
            pattern=f"^{self.callback_data_prefix}"
        )


def create_telegram_document_handler(
    rag_manager,
    max_chunk_length: int = 3000
) -> TelegramDocumentHandler:
    """
    Фабричная функция для создания TelegramDocumentHandler.
    
    Args:
        rag_manager: RAG менеджер
        max_chunk_length: Максимальная длина чанка
        
    Returns:
        Экземпляр TelegramDocumentHandler
    """
    return TelegramDocumentHandler(rag_manager, max_chunk_length)
