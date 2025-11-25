"""
Модуль для разбивки текста на чанки с перекрытием.
Поддерживает markdown и текстовые файлы.
"""

import re
import logging
from typing import List, Dict
import tiktoken

logger = logging.getLogger('embeddings.chunker')


class TextChunker:
    """Разбивает текст на чанки с перекрытием."""

    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        """
        Args:
            chunk_size: Размер чанка в токенах
            overlap: Размер перекрытия между чанками в токенах
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")

        logger.info(f"TextChunker initialized: chunk_size={chunk_size}, overlap={overlap}")

    def chunk_text(self, text: str, metadata: dict) -> List[dict]:
        """
        Разбивает текст на чанки.

        Args:
            text: Исходный текст
            metadata: Метаданные документа (путь к файлу, тип и т.д.)

        Returns:
            Список словарей с чанками и метаданными
        """
        file_type = metadata.get('file_type', 'txt')

        if file_type == 'md':
            return self.chunk_markdown(text, metadata)
        else:
            return self._chunk_plain_text(text, metadata)

    def chunk_markdown(self, text: str, metadata: dict) -> List[dict]:
        """
        Разбивает markdown с учётом структуры заголовков.

        Args:
            text: Markdown текст
            metadata: Метаданные документа

        Returns:
            Список чанков с метаданными
        """
        chunks = []
        paragraphs = self._split_by_paragraphs(text)

        current_header = ""
        current_text = ""
        current_char_pos = 0

        for para in paragraphs:
            # Проверяем, является ли параграф заголовком
            header_match = re.match(r'^(#{1,6})\s+(.+)$', para.strip())

            if header_match:
                # Сохраняем текущий чанк если есть
                if current_text.strip():
                    chunks.extend(
                        self._create_chunks_from_text(
                            current_text,
                            metadata,
                            current_char_pos - len(current_text),
                            len(chunks),
                            current_header
                        )
                    )
                    current_text = ""

                current_header = para.strip()
                current_text += para + "\n\n"
            else:
                current_text += para + "\n\n"

            current_char_pos += len(para) + 2  # +2 для \n\n

            # Проверяем размер текущего текста
            token_count = self._count_tokens(current_text)
            if token_count >= self.chunk_size:
                chunks.extend(
                    self._create_chunks_from_text(
                        current_text,
                        metadata,
                        current_char_pos - len(current_text),
                        len(chunks),
                        current_header
                    )
                )
                current_text = ""

        # Добавляем остаток текста
        if current_text.strip():
            chunks.extend(
                self._create_chunks_from_text(
                    current_text,
                    metadata,
                    current_char_pos - len(current_text),
                    len(chunks),
                    current_header
                )
            )

        logger.info(f"Created {len(chunks)} chunks from markdown: {metadata.get('file_path', 'unknown')}")
        return chunks

    def _chunk_plain_text(self, text: str, metadata: dict) -> List[dict]:
        """
        Разбивает обычный текст на чанки.

        Args:
            text: Исходный текст
            metadata: Метаданные документа

        Returns:
            Список чанков
        """
        return self._create_chunks_from_text(text, metadata, 0, 0)

    def _create_chunks_from_text(
        self,
        text: str,
        metadata: dict,
        start_char: int,
        start_index: int,
        header: str = ""
    ) -> List[dict]:
        """
        Создаёт чанки из текста с перекрытием.

        Args:
            text: Текст для разбивки
            metadata: Метаданные документа
            start_char: Начальная позиция символа в исходном файле
            start_index: Начальный индекс чанка
            header: Текущий заголовок markdown (если есть)

        Returns:
            Список чанков
        """
        chunks = []
        sentences = self._split_by_sentences(text)

        if not sentences:
            return chunks

        current_chunk = []
        current_tokens = 0
        char_position = start_char

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            # Если предложение само по себе больше chunk_size
            if sentence_tokens > self.chunk_size:
                # Сохраняем текущий чанк
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    chunks.append(self._create_chunk(
                        chunk_text,
                        metadata,
                        char_position - len(chunk_text),
                        char_position,
                        start_index + len(chunks),
                        header
                    ))
                    current_chunk = []
                    current_tokens = 0

                # Разбиваем большое предложение на части
                words = sentence.split()
                word_chunk = []
                word_tokens = 0

                for word in words:
                    word_token_count = self._count_tokens(word)

                    if word_tokens + word_token_count > self.chunk_size:
                        # Сохраняем чанк из слов
                        if word_chunk:
                            chunk_text = ' '.join(word_chunk)
                            chunks.append(self._create_chunk(
                                chunk_text,
                                metadata,
                                char_position - len(chunk_text),
                                char_position,
                                start_index + len(chunks),
                                header
                            ))
                        word_chunk = [word]
                        word_tokens = word_token_count
                    else:
                        word_chunk.append(word)
                        word_tokens += word_token_count

                # Сохраняем остаток
                if word_chunk:
                    chunk_text = ' '.join(word_chunk)
                    chunks.append(self._create_chunk(
                        chunk_text,
                        metadata,
                        char_position - len(chunk_text),
                        char_position,
                        start_index + len(chunks),
                        header
                    ))
            elif current_tokens + sentence_tokens > self.chunk_size:
                # Сохраняем текущий чанк
                chunk_text = ' '.join(current_chunk)
                chunks.append(self._create_chunk(
                    chunk_text,
                    metadata,
                    char_position - len(chunk_text),
                    char_position,
                    start_index + len(chunks),
                    header
                ))

                # Создаём перекрытие
                overlap_text = []
                overlap_tokens = 0
                for sent in reversed(current_chunk):
                    sent_tokens = self._count_tokens(sent)
                    if overlap_tokens + sent_tokens <= self.overlap:
                        overlap_text.insert(0, sent)
                        overlap_tokens += sent_tokens
                    else:
                        break

                current_chunk = overlap_text + [sentence]
                current_tokens = overlap_tokens + sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

            char_position += len(sentence) + 1  # +1 для пробела

        # Сохраняем последний чанк
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(self._create_chunk(
                chunk_text,
                metadata,
                char_position - len(chunk_text),
                char_position,
                start_index + len(chunks),
                header
            ))

        return chunks

    def _create_chunk(
        self,
        text: str,
        metadata: dict,
        char_start: int,
        char_end: int,
        chunk_index: int,
        header: str = ""
    ) -> dict:
        """
        Создаёт словарь с данными чанка.

        Args:
            text: Текст чанка
            metadata: Метаданные исходного документа
            char_start: Начальная позиция в исходном файле
            char_end: Конечная позиция в исходном файле
            chunk_index: Порядковый номер чанка
            header: Markdown заголовок (если есть)

        Returns:
            Словарь с данными чанка
        """
        file_path = metadata.get('file_path', 'unknown')
        file_name = file_path.split('/')[-1] if '/' in file_path else file_path

        chunk_id = f"{file_name.replace('.', '_')}_chunk_{chunk_index}"

        chunk_data = {
            'chunk_id': chunk_id,
            'source_file': file_path,
            'chunk_index': chunk_index,
            'text': text.strip(),
            'metadata': {
                'file_type': metadata.get('file_type', 'txt'),
                'char_start': char_start,
                'char_end': char_end,
                'token_count': self._count_tokens(text)
            }
        }

        if header:
            chunk_data['metadata']['markdown_header'] = header

        return chunk_data

    def _split_by_paragraphs(self, text: str) -> List[str]:
        """
        Разбивает текст на параграфы.

        Args:
            text: Исходный текст

        Returns:
            Список параграфов
        """
        # Разбиваем по двойным переносам строк
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Разбивает текст на предложения.

        Args:
            text: Исходный текст

        Returns:
            Список предложений
        """
        # Простое разбиение по знакам препинания
        # Учитываем точку, восклицательный и вопросительный знаки
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _count_tokens(self, text: str) -> int:
        """
        Подсчитывает количество токенов в тексте.

        Args:
            text: Текст для подсчёта

        Returns:
            Количество токенов
        """
        if not text:
            return 0

        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}, falling back to word count")
            # Fallback: примерно 1 токен = 0.75 слова
            return int(len(text.split()) * 1.33)
