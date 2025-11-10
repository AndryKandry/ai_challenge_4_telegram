#!/usr/bin/env python3
"""
Базовый тест модуля temperature_tester без реальных API запросов.
Проверяет структуру и логику анализа.
"""

from temperature_tester import TemperatureTester


def test_similarity_calculation():
    """Тест расчета схожести текстов."""
    tester = TemperatureTester(api_key="fake_key")

    # Идентичные тексты
    similarity1 = tester._calculate_similarity("Hello world", "Hello world")
    assert similarity1 == 1.0, f"Expected 1.0, got {similarity1}"
    print(f"✅ Идентичные тексты: схожесть = {similarity1}")

    # Полностью разные тексты
    similarity2 = tester._calculate_similarity("Hello", "Goodbye")
    assert similarity2 < 0.5, f"Expected < 0.5, got {similarity2}"
    print(f"✅ Разные тексты: схожесть = {similarity2:.2f}")

    # Похожие тексты
    similarity3 = tester._calculate_similarity(
        "Python is great",
        "Python is awesome"
    )
    assert 0.5 < similarity3 < 1.0, f"Expected 0.5 < x < 1.0, got {similarity3}"
    print(f"✅ Похожие тексты: схожесть = {similarity3:.2f}")


def test_recommendations_generation():
    """Тест генерации рекомендаций."""
    tester = TemperatureTester(api_key="fake_key")

    # Высокая схожесть
    recommendations1 = tester._generate_recommendations(0.9, {})
    assert "Высокая схожесть" in recommendations1
    assert "0.7" in recommendations1  # Рекомендует temperature 0.7
    print("✅ Рекомендации для высокой схожести сгенерированы")

    # Средняя вариативность
    recommendations2 = tester._generate_recommendations(0.6, {})
    assert "Средняя вариативность" in recommendations2
    print("✅ Рекомендации для средней вариативности сгенерированы")

    # Высокая вариативность
    recommendations3 = tester._generate_recommendations(0.3, {})
    assert "Высокая вариативность" in recommendations3
    print("✅ Рекомендации для высокой вариативности сгенерированы")


def test_format_results():
    """Тест форматирования результатов."""
    tester = TemperatureTester(api_key="fake_key")

    # Создаем фейковые результаты
    results = {
        "prompt": "Тестовый промпт",
        "results": {
            "temp_0.0": {
                "temperature": 0.0,
                "text": "Ответ с temperature=0",
                "metadata": {"success": True}
            },
            "temp_0.7": {
                "temperature": 0.7,
                "text": "Ответ с temperature=0.7",
                "metadata": {"success": True}
            },
            "temp_1.0": {
                "temperature": 1.0,
                "text": "Ответ с temperature=1.0",
                "metadata": {"success": True}
            }
        },
        "analysis": {
            "recommendations": "Тестовые рекомендации",
            "comparison": {
                "average_similarity": 0.5,
                "average_diversity": 0.5
            }
        }
    }

    formatted = tester.format_test_results(results)

    # Проверки
    assert "ТЕСТИРОВАНИЕ ТЕМПЕРАТУРЫ LLM" in formatted
    assert "Тестовый промпт" in formatted
    assert "Temperature = 0.0" in formatted
    assert "Temperature = 0.7" in formatted
    assert "Temperature = 1.0" in formatted
    assert "ДЕТЕРМИНИРОВАННОСТЬ" in formatted
    assert "СБАЛАНСИРОВАННОСТЬ" in formatted
    assert "КРЕАТИВНОСТЬ" in formatted
    assert "Тестовые рекомендации" in formatted

    print("✅ Форматирование результатов работает корректно")
    print(f"\nДлина отформатированного текста: {len(formatted)} символов")


def test_analysis_logic():
    """Тест логики анализа результатов."""
    tester = TemperatureTester(api_key="fake_key")

    # Создаем результаты с разными текстами
    results = {
        "temp_0.0": {
            "temperature": 0.0,
            "text": "FoodExpress - доставка еды",
            "metadata": {"success": True}
        },
        "temp_0.7": {
            "temperature": 0.7,
            "text": "ВкусДоставка - еда на дом",
            "metadata": {"success": True}
        },
        "temp_1.0": {
            "temperature": 1.0,
            "text": "НямПортал - телепортация еды!",
            "metadata": {"success": True}
        }
    }

    analysis = tester._analyze_results(results)

    # Проверки структуры
    assert "recommendations" in analysis
    assert "comparison" in analysis
    assert "similarity_scores" in analysis["comparison"]
    assert "average_similarity" in analysis["comparison"]
    assert "average_diversity" in analysis["comparison"]

    # Проверки значений
    avg_sim = analysis["comparison"]["average_similarity"]
    avg_div = analysis["comparison"]["average_diversity"]
    assert 0 <= avg_sim <= 1, f"Similarity должна быть 0-1, получено {avg_sim}"
    assert 0 <= avg_div <= 1, f"Diversity должна быть 0-1, получено {avg_div}"
    assert abs(avg_sim + avg_div - 1.0) < 0.01, "Similarity + Diversity должны давать 1.0"

    print(f"✅ Средняя схожесть: {avg_sim:.2f}")
    print(f"✅ Средняя вариативность: {avg_div:.2f}")
    print(f"✅ Количество пар сравнений: {len(analysis['comparison']['similarity_scores'])}")


def main():
    """Запуск всех тестов."""
    print("=" * 60)
    print("БАЗОВОЕ ТЕСТИРОВАНИЕ МОДУЛЯ temperature_tester")
    print("=" * 60)
    print()

    try:
        print("1. Тестирование расчета схожести текстов")
        print("-" * 60)
        test_similarity_calculation()
        print()

        print("2. Тестирование генерации рекомендаций")
        print("-" * 60)
        test_recommendations_generation()
        print()

        print("3. Тестирование форматирования результатов")
        print("-" * 60)
        test_format_results()
        print()

        print("4. Тестирование логики анализа")
        print("-" * 60)
        test_analysis_logic()
        print()

        print("=" * 60)
        print("✅ ВСЕ БАЗОВЫЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
        print("=" * 60)
        print()
        print("Примечание: Для полного тестирования запустите бота")
        print("и используйте команду /test_temperature в Telegram")

    except AssertionError as e:
        print(f"\n❌ ТЕСТ НЕ ПРОЙДЕН: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
