#!/usr/bin/env python3
"""
Класс для сравнения различных стратегий рассуждения Yandex GPT.
Реализует 4 подхода: прямой ответ, пошаговое решение, мета-промптинг, группа экспертов.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable

from reasoning_prompts import (
    TEST_TASK,
    PROMPT_DIRECT,
    PROMPT_STEP_BY_STEP,
    PROMPT_META_STAGE1,
    PROMPT_EXPERTS,
    APPROACH_DESCRIPTIONS,
)


@dataclass
class ApproachResult:
    """Результат выполнения одного подхода к решению задачи."""

    approach_name: str  # Название подхода
    description: str  # Описание подхода
    prompt_used: str  # Использованный промпт
    response: str  # Ответ модели
    execution_time: float  # Время выполнения в секундах
    success: bool  # Успешно ли выполнен запрос
    error_message: Optional[str] = None  # Сообщение об ошибке, если есть


class ReasoningComparator:
    """
    Класс для сравнения различных стратегий рассуждения модели.
    Выполняет 4 подхода к решению одной задачи и собирает результаты.
    """

    def __init__(self, gpt_client, custom_task: Optional[str] = None):
        """
        Инициализация компаратора.

        Args:
            gpt_client: Экземпляр YandexGPTClient для взаимодействия с API
            custom_task: Пользовательская задача (опционально). Если не указана, используется TEST_TASK
        """
        self.gpt_client = gpt_client
        self.logger = logging.getLogger(__name__)
        self.task = custom_task if custom_task else TEST_TASK
        self.is_custom_task = custom_task is not None

    async def run_approach_direct(self) -> ApproachResult:
        """
        Подход 1: Прямой ответ.
        Модель получает только задачу без дополнительных инструкций.

        Returns:
            ApproachResult с результатами выполнения
        """
        self.logger.info("Запуск подхода 1: Прямой ответ")
        start_time = time.time()

        try:
            prompt = PROMPT_DIRECT.format(task=self.task)
            response = await self.gpt_client.send_message(self.task, prompt)
            execution_time = time.time() - start_time

            if response:
                return ApproachResult(
                    approach_name="Прямой ответ",
                    description=APPROACH_DESCRIPTIONS["direct"],
                    prompt_used=prompt,
                    response=response,
                    execution_time=execution_time,
                    success=True
                )
            else:
                return ApproachResult(
                    approach_name="Прямой ответ",
                    description=APPROACH_DESCRIPTIONS["direct"],
                    prompt_used=prompt,
                    response="",
                    execution_time=execution_time,
                    success=False,
                    error_message="Не удалось получить ответ от API"
                )

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Ошибка в подходе 'Прямой ответ': {e}")
            return ApproachResult(
                approach_name="Прямой ответ",
                description=APPROACH_DESCRIPTIONS["direct"],
                prompt_used=PROMPT_DIRECT.format(task=self.task),
                response="",
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )

    async def run_approach_step_by_step(self) -> ApproachResult:
        """
        Подход 2: Пошаговое решение.
        Явная инструкция модели решать задачу пошагово.

        Returns:
            ApproachResult с результатами выполнения
        """
        self.logger.info("Запуск подхода 2: Пошаговое решение")
        start_time = time.time()

        try:
            prompt = PROMPT_STEP_BY_STEP.format(task=self.task)
            response = await self.gpt_client.send_message(self.task, prompt)
            execution_time = time.time() - start_time

            if response:
                return ApproachResult(
                    approach_name="Пошаговое решение",
                    description=APPROACH_DESCRIPTIONS["step_by_step"],
                    prompt_used=prompt,
                    response=response,
                    execution_time=execution_time,
                    success=True
                )
            else:
                return ApproachResult(
                    approach_name="Пошаговое решение",
                    description=APPROACH_DESCRIPTIONS["step_by_step"],
                    prompt_used=prompt,
                    response="",
                    execution_time=execution_time,
                    success=False,
                    error_message="Не удалось получить ответ от API"
                )

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Ошибка в подходе 'Пошаговое решение': {e}")
            return ApproachResult(
                approach_name="Пошаговое решение",
                description=APPROACH_DESCRIPTIONS["step_by_step"],
                prompt_used=PROMPT_STEP_BY_STEP.format(task=self.task),
                response="",
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )

    async def run_approach_meta(self) -> ApproachResult:
        """
        Подход 3: Мета-промптинг.
        Сначала модель создает оптимальный промпт, затем использует его для решения.

        Returns:
            ApproachResult с результатами выполнения
        """
        self.logger.info("Запуск подхода 3: Мета-промптинг")
        start_time = time.time()

        try:
            # Этап 1: Генерация оптимального промпта
            meta_prompt = PROMPT_META_STAGE1.format(task=self.task)
            self.logger.info("Мета-промптинг: Генерация оптимального промпта...")
            generated_prompt = await self.gpt_client.send_message(self.task, meta_prompt)

            if not generated_prompt:
                execution_time = time.time() - start_time
                return ApproachResult(
                    approach_name="Мета-промптинг",
                    description=APPROACH_DESCRIPTIONS["meta"],
                    prompt_used=meta_prompt,
                    response="",
                    execution_time=execution_time,
                    success=False,
                    error_message="Не удалось сгенерировать промпт на этапе 1"
                )

            # Этап 2: Использование сгенерированного промпта для решения задачи
            self.logger.info("Мета-промптинг: Использование сгенерированного промпта...")
            final_response = await self.gpt_client.send_message(self.task, generated_prompt)
            execution_time = time.time() - start_time

            if final_response:
                # Форматируем результат с указанием сгенерированного промпта
                formatted_response = (
                    f"СГЕНЕРИРОВАННЫЙ ПРОМПТ:\n{generated_prompt}\n\n"
                    f"{'='*50}\n\n"
                    f"РЕШЕНИЕ С ИСПОЛЬЗОВАНИЕМ ПРОМПТА:\n{final_response}"
                )

                return ApproachResult(
                    approach_name="Мета-промптинг",
                    description=APPROACH_DESCRIPTIONS["meta"],
                    prompt_used=meta_prompt,
                    response=formatted_response,
                    execution_time=execution_time,
                    success=True
                )
            else:
                return ApproachResult(
                    approach_name="Мета-промптинг",
                    description=APPROACH_DESCRIPTIONS["meta"],
                    prompt_used=meta_prompt,
                    response="",
                    execution_time=execution_time,
                    success=False,
                    error_message="Не удалось получить решение на этапе 2"
                )

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Ошибка в подходе 'Мета-промптинг': {e}")
            return ApproachResult(
                approach_name="Мета-промптинг",
                description=APPROACH_DESCRIPTIONS["meta"],
                prompt_used=PROMPT_META_STAGE1.format(task=self.task),
                response="",
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )

    async def run_approach_experts(self) -> ApproachResult:
        """
        Подход 4: Группа экспертов.
        Создается виртуальная группа из 3 экспертов и модератора.

        Returns:
            ApproachResult с результатами выполнения
        """
        self.logger.info("Запуск подхода 4: Группа экспертов")
        start_time = time.time()

        try:
            prompt = PROMPT_EXPERTS.format(task=self.task)
            response = await self.gpt_client.send_message(self.task, prompt)
            execution_time = time.time() - start_time

            if response:
                return ApproachResult(
                    approach_name="Группа экспертов",
                    description=APPROACH_DESCRIPTIONS["experts"],
                    prompt_used=prompt,
                    response=response,
                    execution_time=execution_time,
                    success=True
                )
            else:
                return ApproachResult(
                    approach_name="Группа экспертов",
                    description=APPROACH_DESCRIPTIONS["experts"],
                    prompt_used=prompt,
                    response="",
                    execution_time=execution_time,
                    success=False,
                    error_message="Не удалось получить ответ от API"
                )

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Ошибка в подходе 'Группа экспертов': {e}")
            return ApproachResult(
                approach_name="Группа экспертов",
                description=APPROACH_DESCRIPTIONS["experts"],
                prompt_used=PROMPT_EXPERTS.format(task=self.task),
                response="",
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )

    async def compare_all_approaches(
        self,
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None
    ) -> list[ApproachResult]:
        """
        Выполняет все 4 подхода последовательно и возвращает результаты.

        Args:
            progress_callback: Опциональная async функция для обновления прогресса.
                             Принимает (текущий_номер, всего_подходов)

        Returns:
            Список ApproachResult для всех подходов
        """
        self.logger.info("Начало сравнения всех подходов к рассуждению")

        results = []
        total_approaches = 4

        # Выполняем подходы последовательно
        # Подход 1: Прямой ответ
        if progress_callback:
            await progress_callback(1, total_approaches)
        result1 = await self.run_approach_direct()
        results.append(result1)

        # Подход 2: Пошаговое решение
        if progress_callback:
            await progress_callback(2, total_approaches)
        result2 = await self.run_approach_step_by_step()
        results.append(result2)

        # Подход 3: Мета-промптинг (требует 2 запроса)
        if progress_callback:
            await progress_callback(3, total_approaches)
        result3 = await self.run_approach_meta()
        results.append(result3)

        # Подход 4: Группа экспертов
        if progress_callback:
            await progress_callback(4, total_approaches)
        result4 = await self.run_approach_experts()
        results.append(result4)

        self.logger.info(f"Сравнение завершено. Успешных подходов: {sum(1 for r in results if r.success)}/4")

        return results

    def format_comparison_report(self, results: list[ApproachResult]) -> str:
        """
        Форматирует результаты сравнения в читаемый отчет.

        Args:
            results: Список результатов выполнения подходов

        Returns:
            Отформатированный текстовый отчет
        """
        report_parts = []

        # Заголовок
        report_parts.append("=" * 60)
        report_parts.append("СРАВНЕНИЕ СТРАТЕГИЙ РАССУЖДЕНИЯ YANDEX GPT")
        report_parts.append("=" * 60)
        report_parts.append("")

        # Описание задачи
        task_type = "ПОЛЬЗОВАТЕЛЬСКАЯ ЗАДАЧА:" if self.is_custom_task else "ТЕСТОВАЯ ЗАДАЧА:"
        report_parts.append(task_type)
        report_parts.append(self.task)
        report_parts.append("")
        report_parts.append("=" * 60)
        report_parts.append("")

        # Результаты каждого подхода
        for i, result in enumerate(results, 1):
            report_parts.append(f"{'='*60}")
            report_parts.append(f"ПОДХОД {i}: {result.approach_name.upper()}")
            report_parts.append(f"{'='*60}")
            report_parts.append("")
            report_parts.append(f"Описание: {result.description}")
            report_parts.append(f"Время выполнения: {result.execution_time:.2f} сек")
            report_parts.append("")

            if result.success:
                report_parts.append("РЕЗУЛЬТАТ:")
                report_parts.append(result.response)
            else:
                report_parts.append(f"ОШИБКА: {result.error_message}")

            report_parts.append("")

        # Итоговая статистика
        report_parts.append("=" * 60)
        report_parts.append("СТАТИСТИКА")
        report_parts.append("=" * 60)
        report_parts.append("")

        successful = [r for r in results if r.success]
        report_parts.append(f"Успешно выполнено: {len(successful)}/4 подходов")

        if successful:
            total_time = sum(r.execution_time for r in successful)
            avg_time = total_time / len(successful)
            report_parts.append(f"Общее время выполнения: {total_time:.2f} сек")
            report_parts.append(f"Среднее время на подход: {avg_time:.2f} сек")
            report_parts.append("")
            report_parts.append("Время по подходам:")
            for r in successful:
                report_parts.append(f"  - {r.approach_name}: {r.execution_time:.2f} сек")

        report_parts.append("")
        report_parts.append("=" * 60)

        return "\n".join(report_parts)
