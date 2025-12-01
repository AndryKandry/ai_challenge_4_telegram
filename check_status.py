#!/usr/bin/env python3
"""
Скрипт для быстрой проверки состояния системы кликабельных ссылок.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_rag_manager():
    """Проверка RAG Manager"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА RAG MANAGER")
    print("=" * 60)

    try:
        from src.rag_integration import RAGManager

        rag = RAGManager()
        print("✅ RAG Manager инициализирован")

        # Проверка кликабельных ссылок
        if rag.enable_clickable_links:
            print("✅ Кликабельные ссылки: ВКЛЮЧЕНЫ")
        else:
            print("⚠️  Кликабельные ссылки: ВЫКЛЮЧЕНЫ")

        # Проверка MCP Link Generator
        if hasattr(rag, 'link_generator') and rag.link_generator:
            print(f"✅ MCP сервер: {rag.link_generator.mcp_server_url}")
            print(f"✅ Поддерживаемые форматы: {list(rag.link_generator.supported_extensions)}")
        else:
            print("❌ MCP Link Generator не инициализирован")

        # Статистика
        stats = rag.get_statistics()
        print(f"\n📊 Статистика RAG:")
        print(f"   - Всего документов: {stats.get('total_documents', 0)}")
        print(f"   - Всего чанков: {stats.get('total_chunks', 0)}")
        print(f"   - Top K: {stats.get('top_k', 0)}")
        print(f"   - Min similarity: {stats.get('min_similarity', 0)}")

        return True

    except Exception as e:
        print(f"❌ Ошибка при инициализации RAG Manager: {e}")
        print("\nВозможные причины:")
        print("  - Отсутствует файл конфигурации")
        print("  - Ollama не запущен")
        print("  - Индекс документов не создан")
        return False


def check_mcp_server():
    """Проверка MCP Filesystem сервера"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА MCP FILESYSTEM СЕРВЕРА")
    print("=" * 60)

    try:
        import httpx

        # Проверка доступности сервера
        response = httpx.get("http://localhost:8003/sse", timeout=2)

        if response.status_code == 200:
            print("✅ MCP сервер работает на http://localhost:8003")
            return True
        else:
            print(f"⚠️  MCP сервер вернул код: {response.status_code}")
            return False

    except httpx.ConnectError:
        print("❌ MCP сервер не доступен на http://localhost:8003")
        print("\nДля запуска сервера выполните:")
        print("  python mcp_server/filesystem.py")
        return False

    except Exception as e:
        print(f"❌ Ошибка при проверке MCP сервера: {e}")
        return False


def check_index():
    """Проверка индекса документов"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА ИНДЕКСА ДОКУМЕНТОВ")
    print("=" * 60)

    index_path = Path("data/embeddings/document_index.json")

    if index_path.exists():
        print(f"✅ Индекс найден: {index_path}")

        # Проверка размера
        size = index_path.stat().st_size
        if size > 0:
            print(f"✅ Размер индекса: {size:,} байт")
            return True
        else:
            print("⚠️  Индекс пустой")
            print("\nДля создания индекса выполните:")
            print("  python manage_index.py index")
            return False
    else:
        print(f"❌ Индекс не найден: {index_path}")
        print("\nДля создания индекса выполните:")
        print("  python manage_index.py index")
        return False


def check_documents():
    """Проверка наличия документов"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА ДОКУМЕНТОВ")
    print("=" * 60)

    docs_dir = Path("docs")

    if not docs_dir.exists():
        print(f"❌ Директория документов не найдена: {docs_dir}")
        return False

    # Поиск .txt и .md файлов
    txt_files = list(docs_dir.rglob("*.txt"))
    md_files = list(docs_dir.rglob("*.md"))

    total_files = len(txt_files) + len(md_files)

    if total_files > 0:
        print(f"✅ Найдено документов: {total_files}")
        print(f"   - TXT файлов: {len(txt_files)}")
        print(f"   - MD файлов: {len(md_files)}")
        return True
    else:
        print(f"⚠️  Документы не найдены в {docs_dir}")
        print("\nДобавьте документы и выполните индексацию:")
        print("  python manage_index.py index")
        return False


def check_config():
    """Проверка конфигурации"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА КОНФИГУРАЦИИ")
    print("=" * 60)

    config_path = Path("config/embeddings_config.yaml")

    if not config_path.exists():
        print(f"❌ Файл конфигурации не найден: {config_path}")
        return False

    print(f"✅ Конфигурация найдена: {config_path}")

    try:
        import yaml

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Проверка секции mcp_links
        mcp_links = config.get('mcp_links', {})

        print(f"\n🔧 MCP Links конфигурация:")
        print(f"   - enabled: {mcp_links.get('enabled', False)}")
        print(f"   - server_url: {mcp_links.get('server_url', 'не указан')}")
        print(f"   - supported_extensions: {mcp_links.get('supported_extensions', [])}")

        # Проверка секции citation
        citation = config.get('citation', {})
        print(f"\n📝 Citation конфигурация:")
        print(f"   - enabled: {citation.get('enabled', False)}")
        print(f"   - default_sources_count: {citation.get('default_sources_count', 0)}")

        return True

    except Exception as e:
        print(f"❌ Ошибка при чтении конфигурации: {e}")
        return False


def main():
    """Главная функция проверки"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА СИСТЕМЫ КЛИКАБЕЛЬНЫХ ССЫЛОК")
    print("=" * 60)

    results = {
        "Конфигурация": check_config(),
        "Документы": check_documents(),
        "Индекс": check_index(),
        "RAG Manager": check_rag_manager(),
        "MCP Сервер": check_mcp_server(),
    }

    # Итоговая статистика
    print("\n" + "=" * 60)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for component, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {component}")

    print(f"\nПройдено проверок: {passed}/{total}")

    if passed == total:
        print("\n🎉 Все компоненты работают корректно!")
        print("\nСистема готова к использованию.")
        return 0
    else:
        print("\n⚠️  Некоторые компоненты требуют внимания.")
        print("\nПожалуйста, исправьте ошибки и повторите проверку.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
