"""
Модуль для работы с HuggingFace Inference API.

Поддерживает:
- Подключение к различным LLM моделям через HuggingFace Inference Providers
- Замер времени выполнения запросов
- Подсчет токенов (input/output)
- Логирование результатов
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ModelMetrics:
    """Метрики выполнения запроса к модели"""
    model_name: str
    model_url: str
    prompt: str
    response: str
    execution_time: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: str  # "Free" или стоимость
    quality_notes: str = ""


class HuggingFaceClient:
    """
    Клиент для работы с HuggingFace Inference API.

    Поддерживаемые модели:
    1. Qwen/Qwen2.5-7B-Instruct - топовая модель (7B параметров)
    2. meta-llama/Llama-3.2-3B-Instruct - компактная модель (3B параметров)
    """

    # Конфигурация доступных моделей
    AVAILABLE_MODELS = {
        "qwen": {
            "name": "Qwen/Qwen2.5-7B-Instruct",
            "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
            "size": "7.61B",
            "category": "Топ-10 популярных",
            "provider": "Together AI"
        },
        "llama": {
            "name": "meta-llama/Llama-3.2-3B-Instruct",
            "url": "https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct",
            "size": "3.21B",
            "category": "Середина списка (50-100)",
            "provider": "Novita"
        },
    }

    def __init__(self, api_token: Optional[str] = None):
        """
        Инициализация клиента HuggingFace.

        Args:
            api_token: HuggingFace API токен (если не указан, берется из .env)
        """
        self.api_token = api_token or os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_API_KEY")
        if not self.api_token:
            raise ValueError(
                "HuggingFace API token не найден. "
                "Установите переменную окружения HUGGINGFACE_API_KEY (или HF_API_KEY) или передайте токен явно."
            )

        logger.info("HuggingFace клиент инициализирован")

    def _create_client(self, model_name: str) -> InferenceClient:
        """
        Создание клиента для конкретной модели.

        Args:
            model_name: Название модели на HuggingFace

        Returns:
            InferenceClient для работы с моделью
        """
        # Используем InferenceClient без явного указания endpoint
        # API автоматически использует правильный роутер
        return InferenceClient(
            token=self.api_token
        )

    def _estimate_tokens(self, text: str) -> int:
        """
        Приблизительная оценка количества токенов в тексте.
        Используется упрощенная формула: ~4 символа = 1 токен.

        Args:
            text: Текст для оценки

        Returns:
            Примерное количество токенов
        """
        return len(text) // 4

    def generate_response(
        self,
        model_key: str,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> ModelMetrics:
        """
        Генерация ответа от модели с замером метрик.

        Args:
            model_key: Ключ модели из AVAILABLE_MODELS ('qwen', 'llama')
            prompt: Текст запроса к модели
            max_tokens: Максимальное количество токенов в ответе
            temperature: Температура генерации (0.0 - 2.0)

        Returns:
            ModelMetrics с результатами и метриками
        """
        if model_key not in self.AVAILABLE_MODELS:
            raise ValueError(
                f"Модель '{model_key}' не найдена. "
                f"Доступные модели: {list(self.AVAILABLE_MODELS.keys())}"
            )

        model_info = self.AVAILABLE_MODELS[model_key]
        model_name = model_info["name"]

        logger.info(f"Отправка запроса к модели {model_name}...")

        try:
            # Создание клиента
            client = self._create_client(model_name)

            # Формирование сообщений для chat completion
            messages = [
                {"role": "user", "content": prompt}
            ]

            # Замер времени выполнения
            start_time = time.time()

            # Выполнение запроса
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            execution_time = time.time() - start_time

            # Извлечение текста ответа
            response_text = response.choices[0].message.content

            # Подсчет токенов
            input_tokens = self._estimate_tokens(prompt)
            output_tokens = self._estimate_tokens(response_text)
            total_tokens = input_tokens + output_tokens

            logger.info(
                f"Ответ получен за {execution_time:.2f}с, "
                f"токены: {input_tokens}/{output_tokens}/{total_tokens}"
            )

            # Формирование метрик
            metrics = ModelMetrics(
                model_name=model_name,
                model_url=model_info["url"],
                prompt=prompt,
                response=response_text,
                execution_time=execution_time,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost="Free (HuggingFace Inference API)"
            )

            return metrics

        except Exception as e:
            logger.error(f"Ошибка при запросе к модели {model_name}: {str(e)}")
            raise

    def test_all_models(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> List[ModelMetrics]:
        """
        Тестирование всех доступных моделей с единым промптом.

        Args:
            prompt: Текст запроса для всех моделей
            max_tokens: Максимальное количество токенов в ответе
            temperature: Температура генерации

        Returns:
            Список ModelMetrics для каждой модели
        """
        results = []

        logger.info(f"Начало тестирования {len(self.AVAILABLE_MODELS)} моделей")
        logger.info(f"Промпт: {prompt}")

        for model_key in self.AVAILABLE_MODELS.keys():
            try:
                metrics = self.generate_response(
                    model_key=model_key,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                results.append(metrics)

                # Небольшая пауза между запросами
                time.sleep(1)

            except Exception as e:
                logger.error(f"Не удалось протестировать модель {model_key}: {str(e)}")
                continue

        logger.info(f"Тестирование завершено. Успешно: {len(results)}/{len(self.AVAILABLE_MODELS)}")

        return results

    @staticmethod
    def format_metrics_table(metrics_list: List[ModelMetrics]) -> str:
        """
        Форматирование метрик в виде таблицы Markdown.

        Args:
            metrics_list: Список метрик для форматирования

        Returns:
            Строка с таблицей в формате Markdown
        """
        if not metrics_list:
            return "Нет данных для отображения"

        table = "| Модель | Время (сек) | Input токенов | Output токенов | Всего токенов | Стоимость |\n"
        table += "|--------|-------------|---------------|----------------|---------------|----------|\n"

        for metrics in metrics_list:
            model_short = metrics.model_name.split('/')[-1]
            table += (
                f"| [{model_short}]({metrics.model_url}) | "
                f"{metrics.execution_time:.2f} | "
                f"{metrics.input_tokens} | "
                f"{metrics.output_tokens} | "
                f"{metrics.total_tokens} | "
                f"{metrics.cost} |\n"
            )

        return table

    @staticmethod
    def get_model_info() -> Dict[str, Any]:
        """
        Получение информации о доступных моделях.

        Returns:
            Словарь с информацией о моделях
        """
        return HuggingFaceClient.AVAILABLE_MODELS


# Пример использования
if __name__ == "__main__":
    # Инициализация клиента
    client = HuggingFaceClient()

    # Тестовый промпт
    test_prompt = "Объясни простыми словами, что такое квантовая запутанность"

    # Тестирование всех моделей
    results = client.test_all_models(prompt=test_prompt)

    # Вывод результатов
    print("\n" + "="*80)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ HUGGINGFACE LLM МОДЕЛЕЙ")
    print("="*80 + "\n")

    print(f"Промпт: {test_prompt}\n")

    print(client.format_metrics_table(results))

    print("\nДетальные ответы:\n")
    for i, metrics in enumerate(results, 1):
        print(f"{i}. {metrics.model_name}")
        print(f"   Время: {metrics.execution_time:.2f}с")
        print(f"   Ответ: {metrics.response[:200]}...")
        print()
