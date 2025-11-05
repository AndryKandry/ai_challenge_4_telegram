#!/usr/bin/env python3
"""
Менеджер форматов ответов от Yandex GPT.
Поддерживает парсинг и форматирование JSON и XML ответов.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional


class FormatManager:
    """Класс для управления форматами ответов (JSON, XML, текстовое форматирование)."""

    def __init__(self):
        """Инициализация менеджера форматов."""
        self.logger = logging.getLogger(__name__)

    # ==================== ПАРСИНГ ====================

    def parse_json(self, response: str) -> Optional[dict]:
        """
        Парсинг JSON с обработкой markdown блоков и fallback.

        Args:
            response: Строка с JSON данными (возможно в markdown блоке)

        Returns:
            Словарь с распарсенными данными или None в случае ошибки
        """
        # Попытка 1: Прямой парсинг JSON
        try:
            data = json.loads(response)
            self.logger.info("JSON успешно распарсен напрямую")
            return data
        except json.JSONDecodeError:
            self.logger.debug("Прямой парсинг JSON не удался, пробуем извлечь из markdown")

        # Попытка 2: Извлечение из markdown блока ```json...```
        try:
            json_pattern = r'```json\s*\n(.*?)\n```'
            match = re.search(json_pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                json_str = match.group(1).strip()
                data = json.loads(json_str)
                self.logger.info("JSON успешно извлечен из markdown блока")
                return data
        except (json.JSONDecodeError, AttributeError) as e:
            self.logger.debug(f"Извлечение JSON из markdown не удалось: {e}")

        # Попытка 3: Fallback - извлечение структуры из текста
        self.logger.warning("Применяем fallback парсинг для JSON")
        return self.extract_structured_from_text(response)

    def parse_xml(self, response: str) -> Optional[dict]:
        """
        Парсинг XML с обработкой markdown блоков и fallback.

        Args:
            response: Строка с XML данными (возможно в markdown блоке)

        Returns:
            Словарь с распарсенными данными или None в случае ошибки
        """
        # Попытка 1: Прямой парсинг XML
        try:
            root = ET.fromstring(response)
            data = {
                'datetime': root.find('datetime').text if root.find('datetime') is not None else None,
                'question': root.find('question').text if root.find('question') is not None else None,
                'answer': root.find('answer').text if root.find('answer') is not None else None,
            }
            self.logger.info("XML успешно распарсен напрямую")
            return data
        except ET.ParseError:
            self.logger.debug("Прямой парсинг XML не удался, пробуем извлечь из markdown")

        # Попытка 2: Извлечение из markdown блока ```xml...```
        try:
            xml_pattern = r'```xml\s*\n(.*?)\n```'
            match = re.search(xml_pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                xml_str = match.group(1).strip()
                root = ET.fromstring(xml_str)
                data = {
                    'datetime': root.find('datetime').text if root.find('datetime') is not None else None,
                    'question': root.find('question').text if root.find('question') is not None else None,
                    'answer': root.find('answer').text if root.find('answer') is not None else None,
                }
                self.logger.info("XML успешно извлечен из markdown блока")
                return data
        except (ET.ParseError, AttributeError) as e:
            self.logger.debug(f"Извлечение XML из markdown не удалось: {e}")

        # Попытка 3: Fallback - извлечение структуры из текста
        self.logger.warning("Применяем fallback парсинг для XML")
        return self.extract_structured_from_text(response)

    def extract_structured_from_text(self, text: str) -> Optional[dict]:
        """
        Fallback парсинг: поиск datetime, question, answer в тексте через regex.

        Args:
            text: Исходный текст с данными

        Returns:
            Словарь с извлеченными данными или None
        """
        try:
            # Паттерны для поиска полей
            datetime_pattern = r'"?datetime"?\s*[:\>]\s*"?([0-9T:\-\.]+)"?'
            question_pattern = r'"?question"?\s*[:\>]\s*"?([^"<\n]+)"?'
            answer_pattern = r'"?answer"?\s*[:\>]\s*"?(.+?)(?="?[\}\<]|$)'

            datetime_match = re.search(datetime_pattern, text, re.IGNORECASE)
            question_match = re.search(question_pattern, text, re.IGNORECASE)
            answer_match = re.search(answer_pattern, text, re.IGNORECASE | re.DOTALL)

            if datetime_match and question_match and answer_match:
                data = {
                    'datetime': datetime_match.group(1).strip(),
                    'question': question_match.group(1).strip(),
                    'answer': answer_match.group(1).strip().strip('"'),
                }
                self.logger.info("Данные успешно извлечены через fallback парсинг")
                return data
            else:
                self.logger.error("Не удалось найти все обязательные поля в тексте")
                return None

        except Exception as e:
            self.logger.error(f"Ошибка при fallback парсинге: {e}")
            return None

    # ==================== ВАЛИДАЦИЯ ====================

    def validate_response(self, data: dict) -> bool:
        """
        Проверка обязательных полей и формата данных.

        Args:
            data: Словарь с данными для валидации

        Returns:
            True если данные валидны, False иначе
        """
        if not data:
            self.logger.error("Валидация не прошла: данные отсутствуют")
            return False

        # Проверка наличия всех обязательных полей
        required_fields = ['datetime', 'question', 'answer']
        for field in required_fields:
            if field not in data or not data[field]:
                self.logger.error(f"Валидация не прошла: отсутствует поле '{field}'")
                return False

        # Проверка формата datetime
        if not self.validate_datetime(data['datetime']):
            self.logger.warning(f"Datetime '{data['datetime']}' не соответствует ISO 8601, но продолжаем")
            # Не возвращаем False, т.к. это не критично

        self.logger.info("Валидация данных успешно пройдена")
        return True

    def validate_datetime(self, dt_string: str) -> bool:
        """
        Валидация формата datetime (ISO 8601).

        Args:
            dt_string: Строка с датой и временем

        Returns:
            True если формат корректный, False иначе
        """
        try:
            # Пробуем несколько форматов ISO 8601
            formats = [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]
            for fmt in formats:
                try:
                    datetime.strptime(dt_string, fmt)
                    return True
                except ValueError:
                    continue
            return False
        except Exception as e:
            self.logger.debug(f"Ошибка валидации datetime: {e}")
            return False

    # ==================== ФОРМАТИРОВАНИЕ ДЛЯ ВЫВОДА ====================

    def format_text_response(self, response: str) -> str:
        """
        Форматирование ответа для режима TEXT.
        Парсит JSON/XML и возвращает красиво отформатированное сообщение.

        Args:
            response: Сырой ответ от Yandex GPT

        Returns:
            Отформатированное текстовое сообщение
        """
        # Сначала пробуем JSON
        data = self.parse_json(response)

        # Если JSON не удался, пробуем XML
        if not data:
            self.logger.debug("JSON парсинг не удался, пробуем XML")
            data = self.parse_xml(response)

        # Валидация данных
        if not data or not self.validate_response(data):
            self.logger.error("Не удалось распарсить или валидировать ответ")
            return (
                "❌ Ошибка обработки ответа\n\n"
                "Не удалось распарсить структурированный ответ от AI.\n"
                "Пожалуйста, попробуйте переформулировать вопрос или обратитесь к администратору."
            )

        # Форматирование красивого сообщения
        formatted_message = (
            f"📅 {data['datetime']}\n"
            f"❓ Тема: {data['question']}\n\n"
            f"💬 Ответ:\n{data['answer']}"
        )

        return formatted_message

    def format_json_output(self, response: str) -> str:
        """
        Форматирование ответа для режима JSON.
        Парсит и возвращает JSON в код-блоке.

        Args:
            response: Сырой ответ от Yandex GPT

        Returns:
            JSON в markdown код-блоке
        """
        data = self.parse_json(response)

        if not data or not self.validate_response(data):
            self.logger.error("Не удалось распарсить или валидировать JSON")
            return (
                "❌ Ошибка парсинга JSON\n\n"
                "Ответ от AI не является валидным JSON.\n"
                "Пожалуйста, попробуйте снова."
            )

        # Форматируем JSON с отступами
        try:
            pretty_json = json.dumps(data, ensure_ascii=False, indent=2)
            return f"```json\n{pretty_json}\n```"
        except Exception as e:
            self.logger.error(f"Ошибка форматирования JSON: {e}")
            return (
                "❌ Ошибка форматирования JSON\n\n"
                "Не удалось отформатировать JSON для вывода."
            )

    def format_xml_output(self, response: str) -> str:
        """
        Форматирование ответа для режима XML.
        Парсит и возвращает XML в код-блоке.

        Args:
            response: Сырой ответ от Yandex GPT

        Returns:
            XML в markdown код-блоке
        """
        data = self.parse_xml(response)

        if not data or not self.validate_response(data):
            self.logger.error("Не удалось распарсить или валидировать XML")
            return (
                "❌ Ошибка парсинга XML\n\n"
                "Ответ от AI не является валидным XML.\n"
                "Пожалуйста, попробуйте снова."
            )

        # Воссоздаем XML из распарсенных данных для красивого вывода
        try:
            xml_str = (
                f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<response>\n'
                f'  <datetime>{data["datetime"]}</datetime>\n'
                f'  <question>{data["question"]}</question>\n'
                f'  <answer>{data["answer"]}</answer>\n'
                f'</response>'
            )
            return f"```xml\n{xml_str}\n```"
        except Exception as e:
            self.logger.error(f"Ошибка форматирования XML: {e}")
            return (
                "❌ Ошибка форматирования XML\n\n"
                "Не удалось отформатировать XML для вывода."
            )
