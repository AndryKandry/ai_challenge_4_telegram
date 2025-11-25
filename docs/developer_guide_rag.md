# Руководство разработчика: Режим сравнения RAG

## Содержание

1. [Архитектура](#архитектура)
2. [Структура кода](#структура-кода)
3. [API модулей](#api-модулей)
4. [Добавление новых метрик](#добавление-новых-метрик)
5. [Настройка анализа RAG](#настройка-анализа-rag)
6. [Тестирование](#тестирование)
7. [Отладка](#отладка)

## Архитектура

### Общая схема

Система сравнения RAG состоит из четырех основных компонентов:

```
┌─────────────────────────────────────────┐
│           Bot (bot.py)                  │
│  - Команда /rag                         │
│  - Обработчик сообщений                 │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┬──────────┬─────────┐
        │             │          │         │
        v             v          v         v
┌───────────┐  ┌─────────┐ ┌─────────┐ ┌─────────┐
│State      │  │Metrics  │ │Comparison│ │Analyzer │
│Manager    │  │Collector│ │          │ │         │
└───────────┘  └─────────┘ └─────────┘ └─────────┘
```

### Поток выполнения

1. **Пользователь активирует режим** → `RAGStateManager.toggle_comparison_mode()`
2. **Пользователь отправляет сообщение** → `Bot.handle_message()`
3. **Проверка режима** → `RAGStateManager.is_comparison_mode()`
4. **Если режим включен**:
   - Вызов `RAGComparator.compare_responses()`
   - Генерация ответа без RAG
   - Генерация ответа с RAG
   - Сбор метрик для обоих ответов
   - Анализ эффективности
   - Форматирование результата
5. **Отправка результата пользователю**
6. **Запись статистики**

## Структура кода

### Файловая структура

```
project/
├── bot.py                      # Основной файл бота с интеграцией
├── utils/
│   └── state_manager.py        # Управление состояниями пользователей
├── rag/
│   ├── __init__.py            # Экспорты модуля
│   ├── metrics.py             # Сбор и расчет метрик
│   ├── comparison.py          # Координация сравнения и анализ
└── docs/
    ├── rag_comparison_feature.md     # Пользовательская документация
    └── developer_guide_rag.md        # Эта документация
```

### Зависимости между модулями

```
bot.py
 ├─ импортирует → utils.state_manager.RAGStateManager
 └─ импортирует → rag.comparison.RAGComparator
     ├─ импортирует → rag.metrics.MetricsCollector
     ├─ импортирует → rag.metrics.PerformanceTimer
     └─ использует → providers.deepseek_provider.DeepSeekProvider
```

## API модулей

### utils/state_manager.py

#### RAGStateManager

**Основной класс для управления состояниями пользователей.**

```python
class RAGStateManager:
    """Менеджер состояний режима сравнения RAG."""

    def get_state(user_id: int) -> UserRAGState:
        """Получить состояние пользователя (создается автоматически)."""

    def is_comparison_mode(user_id: int) -> bool:
        """Проверить, включен ли режим сравнения."""

    def toggle_comparison_mode(user_id: int) -> bool:
        """Переключить режим (возвращает новое состояние)."""

    def set_comparison_mode(user_id: int, enabled: bool) -> None:
        """Установить режим явно."""

    def record_comparison(user_id: int, rag_helpful: Optional[bool]) -> None:
        """Записать результат сравнения в статистику."""

    def get_statistics(user_id: int) -> Dict:
        """Получить статистику пользователя."""

    def reset_statistics(user_id: int) -> None:
        """Сбросить статистику пользователя."""
```

**Пример использования:**

```python
state_manager = RAGStateManager()

# Включение режима
is_enabled = state_manager.toggle_comparison_mode(user_id=123)
print(f"Режим: {'включен' if is_enabled else 'выключен'}")

# Проверка состояния
if state_manager.is_comparison_mode(user_id=123):
    # Выполнить сравнение
    pass

# Запись результата
state_manager.record_comparison(user_id=123, rag_helpful=True)

# Получение статистики
stats = state_manager.get_statistics(user_id=123)
print(f"Всего сравнений: {stats['total_comparisons']}")
```

### rag/metrics.py

#### MetricsCollector

**Сборщик метрик для ответов LLM.**

```python
class MetricsCollector:
    """Сборщик метрик для ответов LLM."""

    def measure_response(
        response_text: str,
        generation_time: float,
        rag_sources: Optional[List[Dict]] = None
    ) -> ResponseMetrics:
        """Измерить метрики ответа."""

    def compare_responses(
        without_rag_metrics: ResponseMetrics,
        with_rag_metrics: ResponseMetrics
    ) -> ComparisonMetrics:
        """Сравнить метрики двух ответов."""
```

**Пример использования:**

```python
collector = MetricsCollector()

# Измерение метрик для ответа без RAG
metrics_no_rag = collector.measure_response(
    response_text="Ответ модели...",
    generation_time=2.34,
    rag_sources=[]
)

# Измерение метрик для ответа с RAG
metrics_with_rag = collector.measure_response(
    response_text="Ответ модели с контекстом...",
    generation_time=3.12,
    rag_sources=[{
        'source_file': 'doc.txt',
        'similarity_score': 0.85
    }]
)

# Сравнение
comparison = collector.compare_responses(metrics_no_rag, metrics_with_rag)

# Получение разницы
token_diff = comparison.get_token_difference()
print(f"Разница в токенах: {token_diff['absolute']} ({token_diff['percent']:.1f}%)")
```

#### PerformanceTimer

**Таймер для измерения времени выполнения.**

```python
class PerformanceTimer:
    """Таймер для измерения времени."""

    def start() -> None:
        """Запустить таймер."""

    def stop() -> float:
        """Остановить и вернуть время."""

    def get_elapsed() -> float:
        """Получить текущее время без остановки."""
```

**Пример использования:**

```python
# Вариант 1: Явное использование
timer = PerformanceTimer()
timer.start()
# ... выполнение кода ...
elapsed = timer.stop()
print(f"Время выполнения: {elapsed:.2f}с")

# Вариант 2: Контекстный менеджер
with PerformanceTimer() as timer:
    # ... выполнение кода ...
    pass
elapsed = timer.stop()
```

#### Утилиты подсчета токенов

```python
def count_tokens(text: str) -> int:
    """Подсчет токенов (tiktoken или приблизительный)."""

def count_tokens_tiktoken(text: str) -> Optional[int]:
    """Точный подсчет через tiktoken."""

def count_tokens_approximate(text: str) -> int:
    """Приблизительный подсчет (~1.33 токена/слово)."""
```

### rag/comparison.py

#### RAGComparator

**Координатор процесса сравнения.**

```python
class RAGComparator:
    """Класс для сравнения ответов DeepSeek с RAG и без."""

    def __init__(deepseek_provider: DeepSeekProvider):
        """Инициализация с провайдером DeepSeek."""

    async def compare_responses(
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> ComparisonResult:
        """Генерирует и сравнивает два ответа."""
```

**Пример использования:**

```python
comparator = RAGComparator(deepseek_provider)

# Выполнение сравнения
result = await comparator.compare_responses(
    user_message="Как настроить базу данных?",
    system_prompt="Ты полезный ассистент",
    conversation_history=[]
)

# Доступ к результатам
print(result.without_rag_response)
print(result.with_rag_response)
print(result.formatted_output)  # Готовый текст для отправки
print(result.analysis['rag_helpful'])
```

#### RAGAnalyzer

**Анализатор эффективности RAG.**

```python
class RAGAnalyzer:
    """Анализатор эффективности RAG."""

    def analyze_effectiveness(
        comparison: ComparisonMetrics,
        user_message: str
    ) -> Dict:
        """Анализирует эффективность RAG."""
```

**Структура результата анализа:**

```python
{
    'rag_helpful': bool,        # RAG был полезен?
    'confidence': str,          # 'low', 'medium', 'high'
    'advantages': List[str],    # Преимущества RAG
    'limitations': List[str]    # Ограничения RAG
}
```

## Добавление новых метрик

### Шаг 1: Обновить ResponseMetrics

В `rag/metrics.py`:

```python
@dataclass
class ResponseMetrics:
    response_text: str
    token_count: int
    generation_time: float
    chunks_used: int = 0
    avg_relevance_score: float = 0.0
    rag_sources: List[Dict] = None

    # Добавить новую метрику
    new_metric: float = 0.0
```

### Шаг 2: Обновить MetricsCollector

```python
def measure_response(
    self,
    response_text: str,
    generation_time: float,
    rag_sources: Optional[List[Dict]] = None,
    new_metric_value: float = 0.0  # Новый параметр
) -> ResponseMetrics:
    # ...

    metrics = ResponseMetrics(
        response_text=response_text,
        token_count=token_count,
        generation_time=generation_time,
        chunks_used=chunks_used,
        avg_relevance_score=avg_relevance,
        rag_sources=rag_sources or [],
        new_metric=new_metric_value  # Установить значение
    )

    return metrics
```

### Шаг 3: Добавить метод сравнения (опционально)

В `ComparisonMetrics`:

```python
def get_new_metric_difference(self) -> Dict:
    """Рассчитать разницу в новой метрике."""
    diff = self.with_rag.new_metric - self.without_rag.new_metric
    percent = 0.0

    if self.without_rag.new_metric > 0:
        percent = (diff / self.without_rag.new_metric) * 100

    return {
        'absolute': diff,
        'percent': percent,
        'without_rag': self.without_rag.new_metric,
        'with_rag': self.with_rag.new_metric
    }
```

### Шаг 4: Обновить форматирование вывода

В `RAGComparator._format_comparison_output()`:

```python
# Добавить в блок метрик
output += f"• Новая метрика: {comparison.without_rag.new_metric:.2f}\n"

# Добавить в блок анализа
new_metric_diff = comparison.get_new_metric_difference()
output += f"**Разница в новой метрике:** {new_metric_diff['absolute']:+.2f} "
output += f"({new_metric_diff['percent']:+.1f}%)\n"
```

## Настройка анализа RAG

### Критерии определения полезности

В `RAGAnalyzer.analyze_effectiveness()` можно настроить логику:

```python
def analyze_effectiveness(self, comparison, user_message):
    analysis = {
        'rag_helpful': False,
        'confidence': 'medium',
        'advantages': [],
        'limitations': []
    }

    # 1. Настройка порогов релевантности
    HIGH_RELEVANCE = 0.7  # Изменить здесь
    MEDIUM_RELEVANCE = 0.5

    if avg_relevance > HIGH_RELEVANCE:
        analysis['rag_helpful'] = True
        analysis['confidence'] = 'high'

    # 2. Настройка порогов токенов
    SIGNIFICANT_INCREASE = 50  # Изменить здесь

    if token_increase > SIGNIFICANT_INCREASE:
        analysis['advantages'].append(...)

    # 3. Добавление новых критериев
    if custom_condition:
        analysis['advantages'].append("Новое преимущество")

    return analysis
```

### Добавление новых ключевых слов

Для определения общих вопросов:

```python
general_keywords = [
    'привет', 'как дела',
    # Добавить новые ключевые слова
    'спасибо', 'пока',
]
```

## Тестирование

### Unit-тесты для MetricsCollector

```python
# tests/test_metrics.py
import pytest
from rag.metrics import MetricsCollector, count_tokens

def test_count_tokens():
    text = "Пример текста для подсчета токенов"
    tokens = count_tokens(text)
    assert tokens > 0
    assert isinstance(tokens, int)

def test_measure_response():
    collector = MetricsCollector()

    metrics = collector.measure_response(
        response_text="Тестовый ответ",
        generation_time=1.5,
        rag_sources=[]
    )

    assert metrics.token_count > 0
    assert metrics.generation_time == 1.5
    assert metrics.chunks_used == 0

def test_measure_response_with_rag():
    collector = MetricsCollector()

    rag_sources = [
        {'source_file': 'doc.txt', 'similarity_score': 0.85},
        {'source_file': 'doc2.txt', 'similarity_score': 0.75}
    ]

    metrics = collector.measure_response(
        response_text="Ответ с RAG",
        generation_time=2.5,
        rag_sources=rag_sources
    )

    assert metrics.chunks_used == 2
    assert metrics.avg_relevance_score == 0.8  # (0.85 + 0.75) / 2
```

### Интеграционные тесты

```python
# tests/test_comparison.py
import pytest
from rag.comparison import RAGComparator
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_compare_responses():
    # Mock провайдера
    mock_provider = Mock()
    mock_provider.generate_response = AsyncMock(return_value="Ответ без RAG")
    mock_provider.generate_response_with_sources = AsyncMock(
        return_value=("Ответ с RAG", [])
    )
    mock_provider.rag_manager = Mock()
    mock_provider.rag_manager.enabled = True
    mock_provider.rag_manager.enable = Mock()
    mock_provider.rag_manager.disable = Mock()

    # Создание компаратора
    comparator = RAGComparator(mock_provider)

    # Выполнение сравнения
    result = await comparator.compare_responses(
        user_message="Тестовый вопрос",
        system_prompt="Ты ассистент",
        conversation_history=[]
    )

    # Проверки
    assert result.without_rag_response == "Ответ без RAG"
    assert result.with_rag_response == "Ответ с RAG"
    assert result.formatted_output is not None
    assert 'rag_helpful' in result.analysis
```

### Тестирование состояния

```python
# tests/test_state_manager.py
from utils.state_manager import RAGStateManager

def test_toggle_comparison_mode():
    manager = RAGStateManager()
    user_id = 123

    # Изначально выключен
    assert not manager.is_comparison_mode(user_id)

    # Включаем
    is_on = manager.toggle_comparison_mode(user_id)
    assert is_on
    assert manager.is_comparison_mode(user_id)

    # Выключаем
    is_on = manager.toggle_comparison_mode(user_id)
    assert not is_on
    assert not manager.is_comparison_mode(user_id)

def test_record_statistics():
    manager = RAGStateManager()
    user_id = 456

    # Записываем несколько сравнений
    manager.record_comparison(user_id, rag_helpful=True)
    manager.record_comparison(user_id, rag_helpful=True)
    manager.record_comparison(user_id, rag_helpful=False)

    # Проверяем статистику
    stats = manager.get_statistics(user_id)
    assert stats['total_comparisons'] == 3
    assert stats['rag_helpful'] == 2
    assert stats['rag_not_helpful'] == 1
    assert abs(stats['rag_helpful_percentage'] - 66.67) < 0.1
```

## Отладка

### Логирование

Все модули используют стандартный logging:

```python
import logging
logger = logging.getLogger(__name__)

# В коде
logger.info("RAG comparison started")
logger.debug(f"Metrics: {metrics}")
logger.error("Error in comparison", exc_info=True)
```

Настройка уровня логирования в `bot.py`:

```python
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG  # Изменить на DEBUG для детальных логов
)
```

### Типичные проблемы и решения

#### Проблема: Tiktoken не найден

```
WARNING: tiktoken not available, using approximate counting
```

**Решение**:
```bash
pip install tiktoken
```

#### Проблема: RAG Comparator не инициализирован

```
ERROR: RAG Comparator недоступен
```

**Причины**:
1. DeepSeek Provider не инициализирован (отсутствует API ключ)
2. RAG Manager не инициализирован (проблемы с Ollama)

**Решение**:
```bash
# Проверить переменные окружения
echo $DEEPSEEK_API_KEY

# Проверить Ollama
ollama list
ollama pull nomic-embed-text  # Модель для эмбеддингов
```

#### Проблема: Долгое время генерации

**Причины**:
1. Медленное подключение к DeepSeek API
2. Ollama работает медленно
3. Большое количество чанков в RAG

**Решение**:
```yaml
# В config/embeddings_config.yaml
deepseek_integration:
  context_chunks: 2  # Уменьшить с 3 до 2
  max_context_tokens: 1000  # Уменьшить с 2000 до 1000
```

### Диагностика

Добавить диагностическую информацию:

```python
# В bot.py, метод rag_command
logger.info(f"DeepSeek Provider: {self.deepseek_provider is not None}")
logger.info(f"RAG Manager: {self.rag_manager is not None}")
logger.info(f"RAG Comparator: {self.rag_comparator is not None}")

# В RAGComparator.compare_responses
logger.info(f"Starting comparison for message: '{user_message[:50]}...'")
logger.info(f"RAG Manager enabled: {self.provider.rag_manager.enabled}")
```

## Производительность

### Оптимизация

1. **Параллельная генерация ответов**:
   Текущая реализация генерирует ответы последовательно. Для ускорения можно реализовать параллельную генерацию:

   ```python
   import asyncio

   async def compare_responses_parallel(self, ...):
       # Создаем задачи
       task_no_rag = self._generate_without_rag(...)
       task_with_rag = self._generate_with_rag(...)

       # Запускаем параллельно
       results = await asyncio.gather(task_no_rag, task_with_rag)

       without_rag_response, without_rag_metrics = results[0]
       with_rag_response, with_rag_metrics = results[1]
   ```

2. **Кэширование результатов RAG поиска**:
   Для одинаковых запросов можно кэшировать результаты поиска.

3. **Ограничение размера контекста**:
   Уменьшить `context_chunks` и `max_context_tokens` в конфиге.

### Мониторинг

Добавить метрики производительности:

```python
from prometheus_client import Counter, Histogram

# Счетчики
comparisons_total = Counter('rag_comparisons_total', 'Total RAG comparisons')
rag_helpful_total = Counter('rag_helpful_total', 'Times RAG was helpful')

# Гистограммы времени
comparison_duration = Histogram('rag_comparison_duration_seconds',
                               'RAG comparison duration')

# В коде
comparisons_total.inc()
with comparison_duration.time():
    result = await comparator.compare_responses(...)

if result.analysis['rag_helpful']:
    rag_helpful_total.inc()
```

## Расширение функциональности

### Добавление нового провайдера

Для поддержки других LLM:

1. Создать компаратор для нового провайдера
2. Обновить проверку в `bot.py`
3. Адаптировать логику включения/выключения RAG

### Экспорт результатов

Добавить возможность экспорта в `RAGStateManager`:

```python
def export_comparison_history(self, user_id: int, format: str = 'json') -> str:
    """Экспорт истории сравнений."""
    state = self.get_state(user_id)
    stats = state.statistics

    if format == 'json':
        return json.dumps(stats, indent=2)
    elif format == 'csv':
        # Реализация CSV экспорта
        pass
```

---

**Версия документа**: 1.0
**Дата создания**: 2025-11-25
**Статус**: Stable
