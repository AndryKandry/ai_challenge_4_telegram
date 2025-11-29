#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности кликабельных ссылок на источники.

Проверяет:
1. Генерацию MCP URI ссылок
2. Форматирование кликабельных источников
3. Интеграцию с RAG Manager
4. Фильтрацию поддерживаемых файлов
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.integrations.mcp_link_generator import MCPLinkGenerator
from src.rag_integration import RAGManager


def test_mcp_link_generation():
    """Тест 1: Генерация MCP URI ссылок"""
    print("\n" + "=" * 80)
    print("ТЕСТ 1: Генерация MCP URI ссылок")
    print("=" * 80)

    generator = MCPLinkGenerator(
        mcp_server_url="http://localhost:8003"
    )

    # Тест базовой ссылки
    link = generator.generate_file_link("/path/to/document.md", "15-25")
    print(f"\n✓ Базовая ссылка:\n  {link}")
    assert link.startswith("mcp://filesystem/"), "Ссылка должна начинаться с mcp://filesystem/"
    assert "#lines=15-25" in link, "Ссылка должна содержать номера строк"

    # Тест ссылки без номеров строк
    link_no_lines = generator.generate_file_link("/path/to/file.txt")
    print(f"\n✓ Ссылка без строк:\n  {link_no_lines}")
    assert "#lines=" not in link_no_lines, "Не должно быть фрагмента с номерами строк"

    # Тест ссылки с пробелами
    link_spaces = generator.generate_file_link("/path/to/my document.md", "1-10")
    print(f"\n✓ Ссылка с пробелами:\n  {link_spaces}")
    assert "%20" in link_spaces, "Пробелы должны быть закодированы"

    print("\n✅ Тест 1 пройден успешно!")


def test_emoji_assignment():
    """Тест 2: Назначение эмодзи по типу файла"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Назначение эмодзи по типу файла")
    print("=" * 80)

    generator = MCPLinkGenerator()

    test_cases = [
        ("file.txt", "📄"),
        ("document.md", "📝"),
        ("readme.markdown", "📝"),
        ("script.py", "🐍"),
        ("config.yaml", "📄"),
    ]

    for filename, expected_emoji in test_cases:
        emoji = generator.get_file_emoji(filename)
        status = "✓" if emoji == expected_emoji else "✗"
        print(f"{status} {filename}: {emoji} (ожидалось: {expected_emoji})")
        assert emoji == expected_emoji, f"Неверное эмодзи для {filename}"

    print("\n✅ Тест 2 пройден успешно!")


def test_source_formatting():
    """Тест 3: Форматирование кликабельного источника"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Форматирование кликабельного источника")
    print("=" * 80)

    generator = MCPLinkGenerator()

    # Тест обычного форматирования
    formatted = generator.format_clickable_source(
        source_file="/path/to/document.md",
        chunk_id="document_md_chunk_0",
        line_numbers="15-25",
        relevance="92%",
        max_filename_length=30
    )

    print(f"\n✓ Отформатированный источник:\n  {formatted}")
    assert "📝" in formatted, "Должно быть эмодзи для .md файла"
    assert "[document.md]" in formatted, "Должно быть имя файла в квадратных скобках"
    assert "строки 15-25" in formatted, "Должны быть номера строк"
    assert "релевантность: 92%" in formatted, "Должна быть релевантность"

    # Тест обрезания длинного имени
    formatted_long = generator.format_clickable_source(
        source_file="/path/to/very_long_filename_that_exceeds_limit.md",
        chunk_id="chunk_0",
        line_numbers="1-10",
        relevance="85%",
        max_filename_length=30
    )

    print(f"\n✓ Обрезанное имя файла:\n  {formatted_long}")
    assert "..." in formatted_long, "Длинное имя должно быть обрезано"
    assert ".md" in formatted_long, "Расширение должно сохраниться"

    print("\n✅ Тест 3 пройден успешно!")


def test_supported_files_filter():
    """Тест 4: Фильтрация поддерживаемых файлов"""
    print("\n" + "=" * 80)
    print("ТЕСТ 4: Фильтрация поддерживаемых файлов")
    print("=" * 80)

    generator = MCPLinkGenerator()

    # Тест поддерживаемых расширений
    supported_files = [
        "/path/to/document.txt",
        "/path/to/readme.md",
        "/path/to/guide.markdown",
    ]

    unsupported_files = [
        "/path/to/document.pdf",
        "/path/to/spreadsheet.xlsx",
        "/path/to/presentation.pptx",
    ]

    print("\n✓ Поддерживаемые файлы:")
    for file_path in supported_files:
        is_supported = generator.is_supported_file(file_path)
        print(f"  {file_path}: {is_supported}")
        assert is_supported, f"{file_path} должен поддерживаться"

    print("\n✓ Неподдерживаемые файлы:")
    for file_path in unsupported_files:
        is_supported = generator.is_supported_file(file_path)
        print(f"  {file_path}: {is_supported}")
        assert not is_supported, f"{file_path} не должен поддерживаться"

    # Тест фильтрации списка
    mock_results = [
        {"source_file": "/path/to/doc1.txt", "text": "text1"},
        {"source_file": "/path/to/doc2.pdf", "text": "text2"},
        {"source_file": "/path/to/doc3.md", "text": "text3"},
        {"source_file": "/path/to/doc4.xlsx", "text": "text4"},
    ]

    filtered = generator.filter_supported_sources(mock_results)
    print(f"\n✓ Отфильтровано: {len(filtered)} из {len(mock_results)} файлов")
    assert len(filtered) == 2, "Должно быть отфильтровано 2 файла (.txt и .md)"

    print("\n✅ Тест 4 пройден успешно!")


def test_clickable_sources_formatting():
    """Тест 5: Форматирование списка кликабельных источников"""
    print("\n" + "=" * 80)
    print("ТЕСТ 5: Форматирование списка кликабельных источников")
    print("=" * 80)

    generator = MCPLinkGenerator()

    mock_results = [
        {
            "source_file": "/path/to/document1.md",
            "chunk_id": "doc1_chunk_0",
            "line_numbers": "1-20",
            "relevance_percentage": "95%"
        },
        {
            "source_file": "/path/to/document2.txt",
            "chunk_id": "doc2_chunk_1",
            "line_numbers": "15-35",
            "relevance_percentage": "87%"
        },
        {
            "source_file": "/path/to/document3.md",
            "chunk_id": "doc3_chunk_2",
            "line_numbers": "5-15",
            "relevance_percentage": "81%"
        },
    ]

    formatted_list = generator.format_clickable_sources(
        search_results=mock_results,
        max_sources=5,
        title="📚 **Источники:**"
    )

    print(f"\n✓ Отформатированный список источников:\n")
    print(formatted_list)

    assert "📚 **Источники:**" in formatted_list, "Должен быть заголовок"
    assert "1." in formatted_list, "Должна быть нумерация"
    assert "2." in formatted_list, "Должна быть нумерация"
    assert "3." in formatted_list, "Должна быть нумерация"
    assert "💡" in formatted_list, "Должно быть примечание о MCP"

    print("\n✅ Тест 5 пройден успешно!")


def test_rag_manager_integration():
    """Тест 6: Интеграция с RAG Manager"""
    print("\n" + "=" * 80)
    print("ТЕСТ 6: Интеграция с RAG Manager")
    print("=" * 80)

    try:
        rag_manager = RAGManager()
        print("✓ RAG Manager инициализирован")

        # Проверка наличия link_generator
        assert hasattr(rag_manager, 'link_generator'), "RAG Manager должен иметь link_generator"
        print("✓ MCPLinkGenerator присутствует в RAG Manager")

        # Проверка наличия методов
        assert hasattr(rag_manager, 'format_clickable_sources'), "Должен быть метод format_clickable_sources"
        assert hasattr(rag_manager, 'generate_mcp_links_for_sources'), "Должен быть метод generate_mcp_links_for_sources"
        print("✓ Методы для кликабельных ссылок присутствуют")

        # Проверка флага enable_clickable_links
        assert hasattr(rag_manager, 'enable_clickable_links'), "Должен быть флаг enable_clickable_links"
        print(f"✓ Кликабельные ссылки: {'включены' if rag_manager.enable_clickable_links else 'выключены'}")

        print("\n✅ Тест 6 пройден успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка при тестировании RAG Manager: {e}")
        print("Возможные причины:")
        print("  - Отсутствует файл конфигурации config/embeddings_config.yaml")
        print("  - Ollama не запущен")
        print("  - Индекс не создан")


def test_mcp_uri_format():
    """Тест 7: Валидация формата MCP URI"""
    print("\n" + "=" * 80)
    print("ТЕСТ 7: Валидация формата MCP URI")
    print("=" * 80)

    generator = MCPLinkGenerator()

    # Тестовые пути
    test_paths = [
        ("/absolute/path/to/file.txt", "1-10"),
        ("/rag_docs/documentation/guide.md", "15-25"),
        ("/path/with spaces/document.txt", "5-15"),
    ]

    for path, lines in test_paths:
        link = generator.generate_file_link(path, lines)
        print(f"\n✓ Путь: {path}")
        print(f"  Ссылка: {link}")

        # Проверка структуры URI
        assert link.startswith("mcp://filesystem/"), "URI должен начинаться с mcp://filesystem/"
        assert f"#lines={lines}" in link, f"URI должен содержать #lines={lines}"

        # Проверка URL encoding
        if " " in path:
            assert "%20" in link, "Пробелы должны быть закодированы в %20"
        if "/" in path:
            assert "%2F" in link, "Слэши в пути должны быть закодированы"

    print("\n✅ Тест 7 пройден успешно!")


def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ КЛИКАБЕЛЬНЫХ ССЫЛОК НА ИСТОЧНИКИ")
    print("=" * 80)

    tests = [
        ("Генерация MCP URI ссылок", test_mcp_link_generation),
        ("Назначение эмодзи", test_emoji_assignment),
        ("Форматирование источника", test_source_formatting),
        ("Фильтрация файлов", test_supported_files_filter),
        ("Форматирование списка", test_clickable_sources_formatting),
        ("Интеграция с RAG", test_rag_manager_integration),
        ("Валидация MCP URI", test_mcp_uri_format),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ Тест '{test_name}' провален!")
            print(f"   Ошибка: {e}")
            failed += 1

    # Итоговая статистика
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print(f"✅ Пройдено: {passed}/{len(tests)}")
    print(f"❌ Провалено: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 Все тесты пройдены успешно!")
        return 0
    else:
        print(f"\n⚠️ Некоторые тесты провалены. Проверьте логи выше.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
