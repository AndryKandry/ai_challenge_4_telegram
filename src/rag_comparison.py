"""
Модуль для реализации режима сравнения RAG с reranking и без reranking.

Обеспечивает интерактивное сравнение качества ответов DeepSeek модели
с применением и без применения reranking/фильтрации релевантности.
"""

import asyncio
import time
import random
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

from src.rag_integration import RAGManager
from providers.deepseek_provider import DeepSeekProvider
from storage.user_settings import UserSettings

logger = logging.getLogger(__name__)


@dataclass
class RAGComparisonMetrics:
    """Метрики для одного варианта ответа."""
    response_text: str
    token_count: int
    generation_time: float
    documents_used: int
    context_size: int
    documents_list: List[Dict[str, Any]]
    avg_relevance: float
    completeness_score: float = 0.0


@dataclass
class RAGComparisonResult:
    """Результат сравнения двух вариантов RAG."""
    variant_a: RAGComparisonMetrics  # Без reranking (случайная выборка)
    variant_b: RAGComparisonMetrics  # С reranking (топ по релевантности)
    query: str
    total_search_results: int


class RAGComparisonConfig:
    """Конфигурация режима сравнения RAG."""
    
    def __init__(self):
        self.enabled = False  # состояние режима сравнения
        self.random_docs_count = 5  # количество случайных документов для варианта A
        self.top_docs_count = 5  # количество топовых документов для варианта B
        self.collect_metrics = True  # собирать метрики
        self.show_document_list = True  # показывать список документов с релевантностью
        self.show_avg_relevance = True  # показывать среднюю релевантность
        self.relevance_score_precision = 2  # количество знаков после запятой для scores


class RAGComparisonManager:
    """Менеджер для сравнения RAG с reranking и без reranking."""
    
    def __init__(self, rag_manager: RAGManager, deepseek_provider: DeepSeekProvider):
        """
        Инициализация менеджера сравнения RAG.
        
        Args:
            rag_manager: Менеджер RAG для поиска документов
            deepseek_provider: Провайдер DeepSeek для генерации ответов
        """
        self.rag_manager = rag_manager
        self.deepseek_provider = deepseek_provider
        self.config = RAGComparisonConfig()
        self.user_settings = UserSettings()
        
        logger.info("RAGComparisonManager initialized")
    
    def toggle_comparison_mode(self, user_id: int, current_provider: str) -> Tuple[bool, str]:
        """
        Переключает режим сравнения для пользователя.
        
        Args:
            user_id: ID пользователя
            current_provider: Текущий провайдер пользователя
            
        Returns:
            Кортеж (новое_состояние, сообщение_для_пользователя)
        """
        # Проверяем, что выбрана модель DeepSeek
        if current_provider != "deepseek":
            return False, "⚠️ Режим сравнения RAG доступен только для DeepSeek модели"
        
        # Переключаем режим используя UserSettings
        new_state = self.user_settings.toggle_rag_comparison(user_id)
        
        if new_state:
            message = "✅ Режим сравнения RAG включён. Вы будете получать два ответа: с reranking и без reranking"
        else:
            message = "❌ Режим сравнения RAG выключен. Возвращаемся к обычному режиму"
        
        logger.info(f"Comparison mode for user {user_id}: {new_state}")
        return new_state, message
    
    def is_comparison_mode(self, user_id: int) -> bool:
        """
        Проверяет, включен ли режим сравнения для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если режим сравнения включен
        """
        return self.user_settings.get_rag_comparison_enabled(user_id)
    
    async def compare_rag_responses(
        self,
        query: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[RAGComparisonResult]:
        """
        Выполняет сравнение RAG ответов с reranking и без.
        
        Args:
            query: Запрос пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога
            
        Returns:
            RAGComparisonResult с результатами сравнения или None
        """
        logger.info(f"Starting RAG comparison for query: '{query[:50]}...'")
        
        try:
            # Используем новый метод для получения документов для сравнения
            variant_a_docs, variant_b_docs = self.rag_manager.get_documents_for_comparison(
                query,
                self.config.random_docs_count,
                self.config.top_docs_count
            )
            
            if not variant_a_docs and not variant_b_docs:
                logger.warning("No search results found for comparison")
                return None
            
            total_search_results = len(variant_a_docs) + len(variant_b_docs)
            logger.info(f"Found {total_search_results} search results for comparison")
            
            # Шаг 3: Генерация ответов (параллельно)
            task_a = self._generate_variant_response(
                query, system_prompt, conversation_history, variant_a_docs, "A (без reranking)"
            )
            
            task_b = self._generate_variant_response(
                query, system_prompt, conversation_history, variant_b_docs, "B (с reranking)"
            )
            
            # Выполняем параллельно
            variant_a_metrics, variant_b_metrics = await asyncio.gather(
                task_a, task_b, return_exceptions=True
            )
            
            # Обрабатываем исключения
            if isinstance(variant_a_metrics, Exception):
                logger.error(f"Error in variant A: {variant_a_metrics}")
                variant_a_metrics = self._create_error_metrics(variant_a_metrics)
            
            if isinstance(variant_b_metrics, Exception):
                logger.error(f"Error in variant B: {variant_b_metrics}")
                variant_b_metrics = self._create_error_metrics(variant_b_metrics)
            
            # Шаг 4: Создаем результат
            result = RAGComparisonResult(
                variant_a=variant_a_metrics,
                variant_b=variant_b_metrics,
                query=query,
                total_search_results=total_search_results
            )
            
            logger.info("RAG comparison completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error in RAG comparison: {e}", exc_info=True)
            return None
    
    async def _generate_variant_response(
        self,
        query: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]],
        documents: List[Dict],
        variant_name: str
    ) -> RAGComparisonMetrics:
        """
        Генерирует ответ для одного варианта с метриками.
        
        Args:
            query: Запрос пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога
            documents: Список документов для контекста
            variant_name: Название варианта для логирования
            
        Returns:
            RAGComparisonMetrics с результатами
        """
        logger.info(f"Generating response for {variant_name}")
        start_time = time.time()
        
        # Формируем контекст
        context = self._format_context(documents, query)
        
        # Вычисляем метрики контекста
        context_size = len(context)
        documents_used = len(documents)
        
        # Вычисляем среднюю релевантность
        avg_relevance = sum(doc.get('similarity_score', 0.0) for doc in documents) / len(documents) if documents else 0.0
        
        try:
            # Отправляем запрос к DeepSeek
            response = await self.deepseek_provider.client.chat.completions.create(
                model=self.deepseek_provider.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                temperature=self.deepseek_provider.temperature,
                max_tokens=self.deepseek_provider.max_tokens
            )
            
            generation_time = time.time() - start_time
            
            if response.choices and len(response.choices) > 0:
                response_text = response.choices[0].message.content
                
                # Оценка токенов (приблизительно)
                token_count = len(response_text.split()) * 1.3  # Примерная оценка
                
                # Вычисляем полноту ответа
                completeness_score = self._calculate_completeness_score(response_text, query)
                
                # Формируем список документов с релевантностью
                documents_list = self._format_documents_list(documents)
                
                metrics = RAGComparisonMetrics(
                    response_text=response_text,
                    token_count=int(token_count),
                    generation_time=generation_time,
                    documents_used=documents_used,
                    context_size=context_size,
                    documents_list=documents_list,
                    avg_relevance=round(avg_relevance, self.config.relevance_score_precision),
                    completeness_score=round(completeness_score, 2)
                )
                
                logger.info(f"Generated response for {variant_name}: {token_count} tokens, {generation_time:.2f}s")
                return metrics
                
            else:
                raise Exception("Empty response from DeepSeek")
                
        except Exception as e:
            logger.error(f"Error generating response for {variant_name}: {e}")
            generation_time = time.time() - start_time
            raise e
    
    def _format_context(self, documents: List[Dict], query: str) -> str:
        """
        Форматирует контекст для отправки в LLM.
        
        Args:
            documents: Список документов
            query: Исходный запрос
            
        Returns:
            Отформатированный контекст
        """
        if not documents:
            return query
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            source_file = Path(doc['source_file']).name
            text = doc['text'][:500]  # Ограничиваем длину
            similarity = doc.get('similarity_score', 0.0)
            
            context_parts.append(
                f"[Документ {i}: {source_file} (релевантность: {similarity:.2f})]\n{text}"
            )
        
        context_text = "\n\n".join(context_parts)
        
        formatted = (
            f"Контекст из документации:\n"
            f"---\n"
            f"{context_text}\n"
            f"---\n\n"
            f"Вопрос пользователя: {query}"
        )
        
        return formatted
    
    def _format_documents_list(self, documents: List[Dict]) -> List[Dict[str, Any]]:
        """
        Форматирует список документов для отображения.
        
        Args:
            documents: Список документов
            
        Returns:
            Отформатированный список документов
        """
        formatted_docs = []
        for doc in documents:
            source_file = Path(doc['source_file']).name
            similarity = round(doc.get('similarity_score', 0.0), self.config.relevance_score_precision)
            
            formatted_docs.append({
                'name': source_file,
                'relevance': similarity,
                'id': doc.get('chunk_id', 'unknown'),
                'metadata': doc.get('metadata', {})
            })
        
        return formatted_docs
    
    def _calculate_completeness_score(self, response: str, query: str) -> float:
        """
        Вычисляет оценку полноты ответа.
        
        Args:
            response: Ответ LLM
            query: Исходный запрос
            
        Returns:
            Оценка полноты от 0 до 1
        """
        if not response:
            return 0.0
        
        score = 0.0
        
        # Количество предложений
        sentences = response.count('.') + response.count('!') + response.count('?')
        score += min(sentences * 0.1, 0.3)  # Максимум 0.3 за предложения
        
        # Наличие числовых данных
        import re
        numeric_facts = len(re.findall(r'\b\d+\b', response))
        score += min(numeric_facts * 0.05, 0.2)  # Максимум 0.2 за числа
        
        # Длина ответа по сравнению с вопросом
        length_ratio = len(response) / max(len(query), 1)
        score += min(length_ratio * 0.1, 0.3)  # Максимум 0.3 за длину
        
        # Наличие структурированных элементов
        if '•' in response or '1.' in response or '-' in response:
            score += 0.2  # 0.2 за списки
        
        return min(score, 1.0)
    
    def _create_error_metrics(self, error: Exception) -> RAGComparisonMetrics:
        """
        Создает метрики для случая ошибки.
        
        Args:
            error: Исключение
            
        Returns:
            Метрики с информацией об ошибке
        """
        return RAGComparisonMetrics(
            response_text=f"❌ Произошла ошибка: {str(error)}",
            token_count=0,
            generation_time=0.0,
            documents_used=0,
            context_size=0,
            documents_list=[],
            avg_relevance=0.0,
            completeness_score=0.0
        )
    
    def format_comparison_result(self, result: RAGComparisonResult) -> str:
        """
        Форматирует результат сравнения для отображения пользователю.
        
        Args:
            result: Результат сравнения
            
        Returns:
            Отформатированная строка для отправки пользователю
        """
        # Формируем заголовок
        output = "🔄 РЕЖИМ СРАВНЕНИЯ RAG\n\n"
        
        # Вариант A (без reranking)
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += "📊 ВАРИАНТ A: БЕЗ RERANKING\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"{result.variant_a.response_text}\n\n"
        output += "📈 Метрики:\n"
        output += f"• Токены: {result.variant_a.token_count}\n"
        output += f"• Время генерации: {result.variant_a.generation_time:.2f} сек\n"
        output += f"• Документов использовано: {result.variant_a.documents_used}\n"
        output += f"• Размер контекста: {result.variant_a.context_size} символов\n\n"
        output += "📄 Использованные документы (случайная выборка):\n"
        
        for i, doc in enumerate(result.variant_a.documents_list, 1):
            output += f"{i}. {doc['name']} - релевантность: {doc['relevance']:.2f}\n"
        
        # Вариант B (с reranking)
        output += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += "📊 ВАРИАНТ B: С RERANKING\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"{result.variant_b.response_text}\n\n"
        output += "📈 Метрики:\n"
        output += f"• Токены: {result.variant_b.token_count}\n"
        output += f"• Время генерации: {result.variant_b.generation_time:.2f} сек\n"
        output += f"• Документов использовано: {result.variant_b.documents_used}\n"
        output += f"• Размер контекста: {result.variant_b.context_size} символов\n\n"
        output += "📄 Использованные документы (топ по релевантности):\n"
        
        for i, doc in enumerate(result.variant_b.documents_list, 1):
            output += f"{i}. {doc['name']} - релевантность: {doc['relevance']:.2f}\n"
        
        # Сравнительный анализ
        output += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += "💡 СРАВНИТЕЛЬНЫЙ АНАЛИЗ\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Разница в токенах
        token_diff = result.variant_b.token_count - result.variant_a.token_count
        token_diff_pct = (token_diff / max(result.variant_a.token_count, 1)) * 100
        output += f"Разница в токенах: {token_diff:+d} ({token_diff_pct:+.1f}%)\n"
        
        # Разница во времени
        time_diff = result.variant_b.generation_time - result.variant_a.generation_time
        time_diff_pct = (time_diff / max(result.variant_a.generation_time, 0.001)) * 100
        output += f"Разница во времени: {time_diff:+.2f} сек ({time_diff_pct:+.1f}%)\n"
        
        # Средняя релевантность
        output += f"Средняя релевантность документов A: {result.variant_a.avg_relevance:.2f}\n"
        output += f"Средняя релевантность документов B: {result.variant_b.avg_relevance:.2f}\n"
        
        # Разница в релевантности
        relevance_diff = result.variant_b.avg_relevance - result.variant_a.avg_relevance
        relevance_diff_pct = (relevance_diff / max(result.variant_a.avg_relevance, 0.001)) * 100
        output += f"Разница в средней релевантности: {relevance_diff:+.2f} ({relevance_diff_pct:+.1f}%)\n"
        
        # Эффективность reranking
        if relevance_diff > 0.1:
            efficiency = "улучшение"
        elif relevance_diff < -0.1:
            efficiency = "ухудшение"
        else:
            efficiency = "нейтрально"
        output += f"Эффективность reranking: {efficiency}\n"
        
        return output
