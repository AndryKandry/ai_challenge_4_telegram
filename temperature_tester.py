#!/usr/bin/env python3
"""
Модуль для тестирования различных значений температуры LLM в Yandex GPT.
Предоставляет функционал сравнения результатов работы модели при разных температурах.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional
from difflib import SequenceMatcher

import httpx

# Настройка логирования
logger = logging.getLogger(__name__)

# Константы температур
TEMPERATURE_DETERMINISTIC = 0.0    # Для точных задач
TEMPERATURE_BALANCED = 0.7         # Универсальное значение
TEMPERATURE_CREATIVE = 1.0         # Для креативных задач

# URL API Yandex GPT
YANDEX_GPT_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Дефолтный промпт для тестирования
DEFAULT_TEST_PROMPT = "Придумай название для стартапа по доставке еды"


class TemperatureTester:
    """Класс для тестирования различных значений температуры LLM."""

    def __init__(self, api_key: str, timeout: int = 30):
        """
        Инициализация тестера температуры.

        Args:
            api_key: API ключ для Yandex Cloud
            timeout: Таймаут запроса в секундах
        """
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.temperatures = [
            TEMPERATURE_DETERMINISTIC,
            TEMPERATURE_BALANCED,
            TEMPERATURE_CREATIVE,
        ]

    async def send_message_with_temperature(
        self, user_message: str, temperature: float, system_prompt: str = ""
    ) -> Optional[str]:
        """
        Отправка сообщения в Yandex GPT с указанной температурой.

        Args:
            user_message: Сообщение от пользователя
            temperature: Значение температуры (0.0 - 1.0)
            system_prompt: Системный промпт (опционально)

        Returns:
            Ответ от Yandex GPT или None в случае ошибки
        """
        messages = []

        # Добавляем системный промпт если указан
        if system_prompt:
            messages.append({
                "role": "system",
                "text": system_prompt,
            })

        # Добавляем сообщение пользователя
        messages.append({
            "role": "user",
            "text": user_message,
        })

        payload = {
            "modelUri": f"gpt://{os.getenv('YANDEX_FOLDER_ID', 'folder_id')}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": 2000,
            },
            "messages": messages,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Отправка запроса в Yandex GPT API (temperature={temperature})")
                response = await client.post(
                    YANDEX_GPT_API_URL,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()

                # Парсинг ответа
                data = response.json()
                logger.info(f"Получен ответ от Yandex GPT API (temperature={temperature})")

                # Извлечение текста ответа из структуры
                if "result" in data and "alternatives" in data["result"]:
                    alternatives = data["result"]["alternatives"]
                    if alternatives and len(alternatives) > 0:
                        message_text = alternatives[0].get("message", {}).get("text")
                        if message_text:
                            return message_text

                logger.error(f"Неожиданная структура ответа: {data}")
                return None

        except httpx.TimeoutException:
            logger.error(f"Превышен таймаут запроса к Yandex GPT API (temperature={temperature})")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP ошибка при запросе к Yandex GPT (temperature={temperature}): "
                f"{e.response.status_code} - {e.response.text}"
            )
            return None
        except ValueError as e:
            logger.error(f"Ошибка парсинга JSON ответа (temperature={temperature}): {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к Yandex GPT (temperature={temperature}): {e}")
            return None

    async def test_temperatures(
        self, prompt: Optional[str] = None, system_prompt: str = ""
    ) -> Dict:
        """
        Тестирование одного промпта с тремя разными температурами.

        Args:
            prompt: Текст промпта (если None, используется DEFAULT_TEST_PROMPT)
            system_prompt: Системный промпт (опционально)

        Returns:
            Словарь с результатами тестирования
        """
        if not prompt:
            prompt = DEFAULT_TEST_PROMPT

        results = {
            "prompt": prompt,
            "results": {},
            "analysis": {},
        }

        # Параллельная отправка запросов с разными температурами
        tasks = []
        for temp in self.temperatures:
            task = self.send_message_with_temperature(prompt, temp, system_prompt)
            tasks.append((temp, task))

        # Ожидание всех результатов
        for temp, task in tasks:
            response = await task
            temp_key = f"temp_{temp}"
            results["results"][temp_key] = {
                "temperature": temp,
                "text": response if response else "Ошибка получения ответа",
                "metadata": {
                    "success": response is not None,
                },
            }

        # Анализ результатов
        results["analysis"] = self._analyze_results(results["results"])

        return results

    def _analyze_results(self, results: Dict) -> Dict:
        """
        Анализ и сравнение результатов тестирования.

        Args:
            results: Словарь с результатами для разных температур

        Returns:
            Словарь с анализом и рекомендациями
        """
        analysis = {
            "recommendations": "",
            "comparison": {},
        }

        # Получаем тексты ответов
        texts = {}
        for temp_key, data in results.items():
            if data["metadata"]["success"]:
                texts[temp_key] = data["text"]

        if len(texts) < 2:
            analysis["recommendations"] = (
                "Недостаточно успешных ответов для проведения сравнительного анализа."
            )
            return analysis

        # Анализ схожести между ответами
        similarity_scores = {}
        text_list = list(texts.items())
        for i in range(len(text_list)):
            for j in range(i + 1, len(text_list)):
                key1, text1 = text_list[i]
                key2, text2 = text_list[j]
                similarity = self._calculate_similarity(text1, text2)
                pair_key = f"{key1}_vs_{key2}"
                similarity_scores[pair_key] = similarity

        # Расчет среднего уровня креативности (на основе различий)
        avg_similarity = sum(similarity_scores.values()) / len(similarity_scores) if similarity_scores else 0
        avg_diversity = 1 - avg_similarity

        analysis["comparison"] = {
            "similarity_scores": similarity_scores,
            "average_similarity": round(avg_similarity, 2),
            "average_diversity": round(avg_diversity, 2),
        }

        # Формирование рекомендаций
        recommendations = self._generate_recommendations(avg_similarity, texts)
        analysis["recommendations"] = recommendations

        return analysis

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Вычисление коэффициента схожести двух текстов.

        Args:
            text1: Первый текст
            text2: Второй текст

        Returns:
            Коэффициент схожести (0.0 - 1.0)
        """
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _generate_recommendations(self, avg_similarity: float, texts: Dict) -> str:
        """
        Генерация рекомендаций на основе анализа.

        Args:
            avg_similarity: Средний коэффициент схожести
            texts: Словарь с текстами ответов

        Returns:
            Текст рекомендаций
        """
        recommendations = []

        # Заголовок
        recommendations.append("📊 АНАЛИЗ И РЕКОМЕНДАЦИИ\n")

        # Оценка разнообразия
        if avg_similarity > 0.8:
            recommendations.append(
                "🔹 Высокая схожесть ответов (детерминированность)\n"
                "Все варианты температуры дают похожие результаты для данного промпта."
            )
        elif avg_similarity > 0.5:
            recommendations.append(
                "🔹 Средняя вариативность ответов\n"
                "Температура оказывает заметное влияние на результаты."
            )
        else:
            recommendations.append(
                "🔹 Высокая вариативность ответов\n"
                "Разные температуры дают существенно отличающиеся результаты."
            )

        # Рекомендации по использованию
        recommendations.append("\n📌 РЕКОМЕНДАЦИИ ПО ВЫБОРУ ТЕМПЕРАТУРЫ:\n")

        recommendations.append(
            "🌡️ Temperature = 0 (Детерминированность)\n"
            "   ✓ Подходит для: точных ответов, классификации, переводов\n"
            "   ✓ Характеристика: максимальная стабильность и предсказуемость\n"
        )

        recommendations.append(
            "🌡️ Temperature = 0.7 (Сбалансированность)\n"
            "   ✓ Подходит для: диалогов, Q&A, общих задач\n"
            "   ✓ Характеристика: баланс между точностью и естественностью\n"
        )

        recommendations.append(
            "🌡️ Temperature = 1.0 (Креативность)\n"
            "   ✓ Подходит для: генерации идей, creative writing, brainstorming\n"
            "   ✓ Характеристика: максимальное разнообразие и оригинальность\n"
        )

        # Специфичная рекомендация для данного промпта
        recommendations.append("\n💡 ДЛЯ ВАШЕГО ПРОМПТА:\n")

        if avg_similarity > 0.7:
            recommendations.append(
                "Для данного типа задачи разница между температурами минимальна. "
                "Рекомендуем использовать temperature=0.7 для оптимального баланса."
            )
        else:
            recommendations.append(
                "Данная задача показывает значительную вариативность. "
                "Используйте temperature=0 для стабильных результатов или "
                "temperature=1.0 для креативных решений."
            )

        return "\n".join(recommendations)

    def format_test_results(self, results: Dict) -> str:
        """
        Форматирование результатов тестирования для вывода пользователю.

        Args:
            results: Словарь с результатами тестирования

        Returns:
            Отформатированная строка с результатами
        """
        output_lines = []

        # Заголовок
        output_lines.append("🧪 ТЕСТИРОВАНИЕ ТЕМПЕРАТУРЫ LLM\n")
        output_lines.append(f"📝 Промпт: {results['prompt']}\n")
        output_lines.append("=" * 50)

        # Результаты для каждой температуры
        for temp_key in sorted(results["results"].keys()):
            data = results["results"][temp_key]
            temp = data["temperature"]

            # Название температуры
            if temp == TEMPERATURE_DETERMINISTIC:
                temp_name = "ДЕТЕРМИНИРОВАННОСТЬ"
            elif temp == TEMPERATURE_BALANCED:
                temp_name = "СБАЛАНСИРОВАННОСТЬ"
            elif temp == TEMPERATURE_CREATIVE:
                temp_name = "КРЕАТИВНОСТЬ"
            else:
                temp_name = "ПОЛЬЗОВАТЕЛЬСКАЯ"

            output_lines.append(f"\n🌡️ Temperature = {temp} ({temp_name})")
            output_lines.append("-" * 50)

            if data["metadata"]["success"]:
                output_lines.append(f"💬 Ответ:\n{data['text']}\n")
            else:
                output_lines.append(f"❌ Ошибка получения ответа\n")

        # Разделитель
        output_lines.append("=" * 50)

        # Анализ и рекомендации
        if "analysis" in results and "recommendations" in results["analysis"]:
            output_lines.append(f"\n{results['analysis']['recommendations']}")

            # Показатели схожести
            if "comparison" in results["analysis"]:
                comparison = results["analysis"]["comparison"]
                output_lines.append(f"\n\n📈 МЕТРИКИ:")
                output_lines.append(
                    f"• Средняя схожесть ответов: {comparison.get('average_similarity', 0):.0%}"
                )
                output_lines.append(
                    f"• Средняя вариативность: {comparison.get('average_diversity', 0):.0%}"
                )

        return "\n".join(output_lines)
