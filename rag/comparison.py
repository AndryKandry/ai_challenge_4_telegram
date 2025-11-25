"""
Модуль сравнения ответов с RAG и без RAG для DeepSeek.
Координирует генерацию двух ответов, сбор метрик и анализ эффективности.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from rag.metrics import MetricsCollector, ResponseMetrics, ComparisonMetrics, PerformanceTimer

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Результат сравнения ответов с RAG и без RAG."""

    user_message: str
    without_rag_response: str
    with_rag_response: str
    comparison_metrics: ComparisonMetrics
    analysis: Dict
    formatted_output: str


class RAGAnalyzer:
    """Анализатор эффективности RAG."""

    def __init__(self):
        """Инициализация анализатора."""
        logger.info("RAGAnalyzer initialized")

    def analyze_effectiveness(
        self,
        comparison: ComparisonMetrics,
        user_message: str
    ) -> Dict:
        """
        Анализирует эффективность RAG на основе метрик.

        Args:
            comparison: Метрики сравнения
            user_message: Исходное сообщение пользователя

        Returns:
            Словарь с анализом эффективности
        """
        analysis = {
            'rag_helpful': False,
            'confidence': 'medium',
            'advantages': [],
            'limitations': []
        }

        # Критерии полезности RAG
        avg_relevance = comparison.with_rag.avg_relevance_score
        chunks_used = comparison.with_rag.chunks_used

        token_diff = comparison.get_token_difference()
        time_diff = comparison.get_time_difference()

        # 1. Проверка релевантности чанков
        if chunks_used > 0:
            if avg_relevance > 0.7:
                analysis['advantages'].append(
                    f"Найдены высокорелевантные документы (релевантность: {avg_relevance:.2f})"
                )
                analysis['rag_helpful'] = True
                analysis['confidence'] = 'high'

            elif avg_relevance > 0.5:
                analysis['advantages'].append(
                    f"Найдены релевантные документы (релевантность: {avg_relevance:.2f})"
                )
                analysis['rag_helpful'] = True

            else:
                analysis['limitations'].append(
                    f"Низкая релевантность документов ({avg_relevance:.2f})"
                )
        else:
            analysis['limitations'].append("Не найдено релевантных документов")

        # 2. Анализ разницы в длине ответов
        token_increase = token_diff['absolute']
        if token_increase > 50:
            analysis['advantages'].append(
                f"Ответ с RAG более развернутый (+{token_increase} токенов)"
            )
            analysis['rag_helpful'] = True

        elif token_increase < -20:
            analysis['limitations'].append(
                f"Ответ с RAG короче ({token_increase} токенов)"
            )

        # 3. Проверка на общие вопросы (где RAG не нужен)
        general_keywords = [
            'привет', 'как дела', 'что такое python',
            'кто ты', 'что ты умеешь', 'расскажи о себе'
        ]

        message_lower = user_message.lower()
        if any(keyword in message_lower for keyword in general_keywords):
            analysis['limitations'].append(
                "Вопрос не требует информации из документов"
            )
            analysis['rag_helpful'] = False
            analysis['confidence'] = 'high'

        # 4. Анализ времени генерации
        time_increase = time_diff['absolute']
        if time_increase > 5:
            analysis['limitations'].append(
                f"Значительное увеличение времени генерации (+{time_increase:.2f}с)"
            )

        # Если нет преимуществ, RAG не был полезен
        if not analysis['advantages']:
            analysis['rag_helpful'] = False
            if not analysis['limitations']:
                analysis['limitations'].append(
                    "RAG не добавил значимой информации к ответу"
                )

        logger.info(
            f"RAG effectiveness analysis: "
            f"helpful={analysis['rag_helpful']}, "
            f"confidence={analysis['confidence']}"
        )

        return analysis


class RAGComparator:
    """Класс для сравнения ответов DeepSeek с RAG и без RAG."""

    def __init__(self, deepseek_provider):
        """
        Инициализация компаратора.

        Args:
            deepseek_provider: Экземпляр DeepSeekProvider
        """
        self.provider = deepseek_provider
        self.metrics_collector = MetricsCollector()
        self.analyzer = RAGAnalyzer()

        logger.info("RAGComparator initialized")

    async def compare_responses(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> ComparisonResult:
        """
        Генерирует два ответа (с RAG и без) и сравнивает их.

        Args:
            user_message: Сообщение пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога

        Returns:
            Результат сравнения с метриками и анализом
        """
        logger.info(f"Starting RAG comparison for message: '{user_message[:50]}...'")

        # 1. Генерация ответа БЕЗ RAG
        logger.info("Generating response WITHOUT RAG...")
        without_rag_response, without_rag_metrics = await self._generate_without_rag(
            user_message, system_prompt, conversation_history
        )

        # 2. Генерация ответа С RAG
        logger.info("Generating response WITH RAG...")
        with_rag_response, with_rag_metrics = await self._generate_with_rag(
            user_message, system_prompt, conversation_history
        )

        # 3. Сравнение метрик
        comparison = self.metrics_collector.compare_responses(
            without_rag_metrics, with_rag_metrics
        )

        # 4. Анализ эффективности RAG
        analysis = self.analyzer.analyze_effectiveness(comparison, user_message)

        # 5. Форматирование результата
        formatted_output = self._format_comparison_output(
            without_rag_response,
            with_rag_response,
            comparison,
            analysis
        )

        result = ComparisonResult(
            user_message=user_message,
            without_rag_response=without_rag_response,
            with_rag_response=with_rag_response,
            comparison_metrics=comparison,
            analysis=analysis,
            formatted_output=formatted_output
        )

        logger.info("RAG comparison completed successfully")
        return result

    async def _generate_without_rag(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict]]
    ) -> Tuple[str, ResponseMetrics]:
        """
        Генерирует ответ БЕЗ использования RAG.

        Args:
            user_message: Сообщение пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога

        Returns:
            Кортеж (ответ, метрики)
        """
        # Временно отключаем RAG
        rag_was_enabled = self.provider.rag_manager.enabled if self.provider.rag_manager else False

        if self.provider.rag_manager:
            self.provider.rag_manager.disable()

        # Замеряем время генерации
        timer = PerformanceTimer()
        timer.start()

        try:
            response = await self.provider.generate_response(
                user_message, system_prompt, conversation_history
            )
        except Exception as e:
            logger.error(f"Error generating response without RAG: {e}")
            response = "[Ошибка генерации ответа без RAG]"

        generation_time = timer.stop()

        # Восстанавливаем состояние RAG
        if self.provider.rag_manager and rag_was_enabled:
            self.provider.rag_manager.enable()

        # Собираем метрики
        metrics = self.metrics_collector.measure_response(
            response_text=response or "",
            generation_time=generation_time,
            rag_sources=[]
        )

        return response or "", metrics

    async def _generate_with_rag(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict]]
    ) -> Tuple[str, ResponseMetrics]:
        """
        Генерирует ответ С использованием RAG.

        Args:
            user_message: Сообщение пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога

        Returns:
            Кортеж (ответ, метрики)
        """
        # Убеждаемся что RAG включен
        rag_was_enabled = self.provider.rag_manager.enabled if self.provider.rag_manager else False

        if self.provider.rag_manager:
            self.provider.rag_manager.enable()

        # Замеряем время генерации
        timer = PerformanceTimer()
        timer.start()

        try:
            response, rag_sources = await self.provider.generate_response_with_sources(
                user_message, system_prompt, conversation_history
            )
        except Exception as e:
            logger.error(f"Error generating response with RAG: {e}")
            response = "[Ошибка генерации ответа с RAG]"
            rag_sources = []

        generation_time = timer.stop()

        # Восстанавливаем состояние RAG
        if self.provider.rag_manager and not rag_was_enabled:
            self.provider.rag_manager.disable()

        # Собираем метрики
        metrics = self.metrics_collector.measure_response(
            response_text=response or "",
            generation_time=generation_time,
            rag_sources=rag_sources
        )

        return response or "", metrics

    def _format_comparison_output(
        self,
        without_rag_response: str,
        with_rag_response: str,
        comparison: ComparisonMetrics,
        analysis: Dict
    ) -> str:
        """
        Форматирует результаты сравнения для отправки пользователю.

        Args:
            without_rag_response: Ответ без RAG
            with_rag_response: Ответ с RAG
            comparison: Метрики сравнения
            analysis: Анализ эффективности

        Returns:
            Отформатированная строка
        """
        token_diff = comparison.get_token_difference()
        time_diff = comparison.get_time_difference()

        output = "🔍 **СРАВНЕНИЕ РЕЖИМОВ RAG**\n\n"

        # Блок: БЕЗ RAG
        output += "━━━━━━━━━━━━━━━━━━━━━━\n"
        output += "📊 **БЕЗ RAG**\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"{without_rag_response}\n\n"
        output += "📈 **Метрики:**\n"
        output += f"• Токенов: {comparison.without_rag.token_count}\n"
        output += f"• Время: {comparison.without_rag.generation_time:.2f}с\n"
        output += f"• Использовано чанков: 0\n\n"

        # Блок: С RAG
        output += "━━━━━━━━━━━━━━━━━━━━━━\n"
        output += "🎯 **С RAG**\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"{with_rag_response}\n\n"
        output += "📈 **Метрики:**\n"
        output += f"• Токенов: {comparison.with_rag.token_count}\n"
        output += f"• Время: {comparison.with_rag.generation_time:.2f}с\n"
        output += f"• Использовано чанков: {comparison.with_rag.chunks_used}\n"

        if comparison.with_rag.chunks_used > 0:
            output += f"• Релевантность чанков: {comparison.with_rag.avg_relevance_score:.2f}\n\n"
        else:
            output += "\n"

        # Блок: АНАЛИЗ СРАВНЕНИЯ
        output += "━━━━━━━━━━━━━━━━━━━━━━\n"
        output += "💡 **АНАЛИЗ СРАВНЕНИЯ**\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Разница в метриках
        output += f"**Разница в токенах:** {token_diff['absolute']:+d} "
        output += f"({token_diff['percent']:+.1f}%)\n"

        output += f"**Разница во времени:** {time_diff['absolute']:+.2f}с "
        output += f"({time_diff['percent']:+.1f}%)\n\n"

        # Преимущества RAG
        if analysis['advantages']:
            output += "✅ **Преимущества RAG:**\n"
            for advantage in analysis['advantages']:
                output += f"• {advantage}\n"
            output += "\n"

        # Ограничения RAG
        if analysis['limitations']:
            output += "⚠️ **Ограничения RAG:**\n"
            for limitation in analysis['limitations']:
                output += f"• {limitation}\n"
            output += "\n"

        # Итоговый вердикт
        if analysis['rag_helpful']:
            output += "🎉 **Вердикт:** RAG улучшил качество ответа\n"
        else:
            output += "📝 **Вердикт:** RAG не добавил значимой ценности\n"

        return output
