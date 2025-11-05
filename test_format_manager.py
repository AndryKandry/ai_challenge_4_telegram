#!/usr/bin/env python3
"""
Тестовый скрипт для проверки FormatManager.
Проверяет парсинг JSON, XML и форматирование.
"""

from format_manager import FormatManager


def test_json_parsing():
    """Тест парсинга JSON."""
    print("=" * 60)
    print("ТЕСТ 1: Парсинг корректного JSON")
    print("=" * 60)

    manager = FormatManager()

    # Тест 1.1: Чистый JSON
    json_response = '{"datetime": "2025-11-05T14:30:00", "question": "Тестовый вопрос", "answer": "Тестовый ответ"}'
    result = manager.parse_json(json_response)
    print(f"Чистый JSON: {'✅ PASS' if result else '❌ FAIL'}")
    print(f"Результат: {result}\n")

    # Тест 1.2: JSON в markdown блоке
    json_markdown = '''```json
{
  "datetime": "2025-11-05T14:30:00",
  "question": "Вопрос в markdown",
  "answer": "Ответ в markdown"
}
```'''
    result = manager.parse_json(json_markdown)
    print(f"JSON в markdown: {'✅ PASS' if result else '❌ FAIL'}")
    print(f"Результат: {result}\n")


def test_xml_parsing():
    """Тест парсинга XML."""
    print("=" * 60)
    print("ТЕСТ 2: Парсинг корректного XML")
    print("=" * 60)

    manager = FormatManager()

    # Тест 2.1: Чистый XML
    xml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<response>
  <datetime>2025-11-05T14:30:00</datetime>
  <question>Тестовый вопрос XML</question>
  <answer>Тестовый ответ XML</answer>
</response>'''
    result = manager.parse_xml(xml_response)
    print(f"Чистый XML: {'✅ PASS' if result else '❌ FAIL'}")
    print(f"Результат: {result}\n")

    # Тест 2.2: XML в markdown блоке
    xml_markdown = '''```xml
<?xml version="1.0" encoding="UTF-8"?>
<response>
  <datetime>2025-11-05T14:30:00</datetime>
  <question>Вопрос в XML markdown</question>
  <answer>Ответ в XML markdown</answer>
</response>
```'''
    result = manager.parse_xml(xml_markdown)
    print(f"XML в markdown: {'✅ PASS' if result else '❌ FAIL'}")
    print(f"Результат: {result}\n")


def test_validation():
    """Тест валидации данных."""
    print("=" * 60)
    print("ТЕСТ 3: Валидация данных")
    print("=" * 60)

    manager = FormatManager()

    # Тест 3.1: Корректные данные
    valid_data = {
        "datetime": "2025-11-05T14:30:00",
        "question": "Тест",
        "answer": "Ответ"
    }
    result = manager.validate_response(valid_data)
    print(f"Корректные данные: {'✅ PASS' if result else '❌ FAIL'}\n")

    # Тест 3.2: Отсутствует поле
    invalid_data = {
        "datetime": "2025-11-05T14:30:00",
        "question": "Тест"
        # Отсутствует answer
    }
    result = manager.validate_response(invalid_data)
    print(f"Отсутствует поле: {'✅ PASS' if not result else '❌ FAIL'}\n")


def test_text_formatting():
    """Тест форматирования для текстового режима."""
    print("=" * 60)
    print("ТЕСТ 4: Форматирование для TEXT режима")
    print("=" * 60)

    manager = FormatManager()

    json_response = '{"datetime": "2025-11-05T14:30:00", "question": "Что такое Python?", "answer": "Python - это высокоуровневый язык программирования."}'
    result = manager.format_text_response(json_response)
    print(result)
    print()


def test_json_formatting():
    """Тест форматирования для JSON режима."""
    print("=" * 60)
    print("ТЕСТ 5: Форматирование для JSON режима")
    print("=" * 60)

    manager = FormatManager()

    json_response = '{"datetime": "2025-11-05T14:30:00", "question": "Тест JSON вывода", "answer": "Ответ в JSON формате"}'
    result = manager.format_json_output(json_response)
    print(result)
    print()


def test_xml_formatting():
    """Тест форматирования для XML режима."""
    print("=" * 60)
    print("ТЕСТ 6: Форматирование для XML режима")
    print("=" * 60)

    manager = FormatManager()

    xml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<response>
  <datetime>2025-11-05T14:30:00</datetime>
  <question>Тест XML вывода</question>
  <answer>Ответ в XML формате</answer>
</response>'''
    result = manager.format_xml_output(xml_response)
    print(result)
    print()


def test_fallback_parsing():
    """Тест fallback парсинга."""
    print("=" * 60)
    print("ТЕСТ 7: Fallback парсинг из текста")
    print("=" * 60)

    manager = FormatManager()

    # Текст с вкраплениями структурированных данных
    messy_text = '''
    Вот ответ:
    datetime: 2025-11-05T14:30:00
    question: Какой-то вопрос
    answer: Какой-то ответ на вопрос пользователя
    '''
    result = manager.extract_structured_from_text(messy_text)
    print(f"Fallback парсинг: {'✅ PASS' if result else '❌ FAIL'}")
    print(f"Результат: {result}\n")


def main():
    """Запуск всех тестов."""
    print("\n🧪 ЗАПУСК ТЕСТОВ FormatManager\n")

    try:
        test_json_parsing()
        test_xml_parsing()
        test_validation()
        test_text_formatting()
        test_json_formatting()
        test_xml_formatting()
        test_fallback_parsing()

        print("=" * 60)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ ТЕСТОВ: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
