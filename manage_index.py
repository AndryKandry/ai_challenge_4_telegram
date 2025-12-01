#!/usr/bin/env python3
"""
CLI скрипт для управления индексом документов RAG.

Команды:
- index: Индексация документов
- search: Поиск по индексу
- stats: Статистика индекса
- clear: Очистка индекса
- verify: Проверка работоспособности Ollama
"""

import sys
import os
import logging
from pathlib import Path

# Добавляем путь к проекту в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from src.embeddings.chunker import TextChunker
from src.embeddings.embedder import OllamaEmbedder, check_ollama_or_exit
from src.embeddings.indexer import DocumentIndexer
from src.embeddings.searcher import SemanticSearcher

console = Console()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def load_config(config_path: str = "config/embeddings_config.yaml") -> dict:
    """Загружает конфигурацию из YAML."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Ошибка загрузки конфигурации: {e}[/red]")
        return {}


@click.group()
def cli():
    """Управление индексом документов RAG."""
    pass


@cli.command()
@click.option('--source', default='docs', help='Директория с документами')
@click.option('--config', default='config/embeddings_config.yaml', help='Файл конфигурации')
@click.option('--recursive/--no-recursive', default=True, help='Рекурсивное сканирование')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
def index(source, config, recursive, verbose):
    """Индексация документов из директории."""

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    console.print(f"[bold blue]Индексация документов из: {source}[/bold blue]")

    # Загружаем конфигурацию
    cfg = load_config(config)

    # Проверяем Ollama
    try:
        embedder = check_ollama_or_exit(cfg)
    except SystemExit:
        return

    # Создаём компоненты
    chunking_config = cfg.get('chunking', {})
    chunker = TextChunker(
        chunk_size=chunking_config.get('chunk_size', 800),
        overlap=chunking_config.get('overlap', 150)
    )

    indexing_config = cfg.get('indexing', {})
    indexer = DocumentIndexer(
        chunker=chunker,
        embedder=embedder,
        index_path=indexing_config.get('index_path', 'data/embeddings/document_index.json')
    )

    # Индексируем
    try:
        with Progress() as progress:
            task = progress.add_task("[green]Индексация...", total=None)

            stats = indexer.index_directory(
                directory=source,
                extensions=indexing_config.get('include_extensions', ['.md', '.txt']),
                exclude_patterns=indexing_config.get('exclude_patterns', []),
                recursive=recursive
            )

            progress.update(task, completed=True)

        # Сохраняем индекс
        indexer.save_index()

        # Выводим статистику
        console.print("\n[bold green]✓ Индексация завершена![/bold green]")
        console.print(f"Проиндексировано файлов: {stats['indexed_files']}/{stats['total_files']}")
        console.print(f"Создано чанков: {stats['total_chunks']}")
        console.print(f"Пропущено файлов: {stats['skipped_files']}")

        if stats['errors']:
            console.print(f"\n[yellow]Ошибки ({len(stats['errors'])})[/yellow]:")
            for error in stats['errors'][:5]:  # Показываем первые 5
                console.print(f"  • {error['file']}: {error['error']}")

    except Exception as e:
        console.print(f"[red]Ошибка индексации: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('query')
@click.option('--top-k', default=5, help='Количество результатов')
@click.option('--min-similarity', default=0.5, help='Минимальное сходство (0-1)')
@click.option('--config', default='config/embeddings_config.yaml', help='Файл конфигурации')
def search(query, top_k, min_similarity, config):
    """Поиск по индексу."""

    console.print(f"[bold blue]Поиск: '{query}'[/bold blue]\n")

    # Загружаем конфигурацию
    cfg = load_config(config)

    # Проверяем Ollama
    try:
        embedder = check_ollama_or_exit(cfg)
    except SystemExit:
        return

    # Создаём searcher
    indexing_config = cfg.get('indexing', {})
    searcher = SemanticSearcher(
        index_path=indexing_config.get('index_path', 'data/embeddings/document_index.json'),
        embedder=embedder
    )

    # Выполняем поиск
    try:
        results = searcher.search(
            query=query,
            top_k=top_k,
            min_similarity=min_similarity
        )

        if not results:
            console.print("[yellow]Ничего не найдено[/yellow]")
            return

        # Выводим результаты
        console.print(f"[green]Найдено результатов: {len(results)}[/green]\n")

        for i, result in enumerate(results, 1):
            console.print(f"[bold]{i}. {result['source_file']}[/bold]")
            console.print(f"   Релевантность: {result['similarity_score']:.3f}")
            console.print(f"   {result['text'][:200]}...")
            console.print()

    except Exception as e:
        console.print(f"[red]Ошибка поиска: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--config', default='config/embeddings_config.yaml', help='Файл конфигурации')
def stats(config):
    """Статистика индекса."""

    # Загружаем конфигурацию
    cfg = load_config(config)

    indexing_config = cfg.get('indexing', {})
    index_path = indexing_config.get('index_path', 'data/embeddings/document_index.json')

    if not os.path.exists(index_path):
        console.print("[yellow]Индекс не найден. Выполните индексацию командой 'index'[/yellow]")
        return

    # Загружаем индекс для статистики
    try:
        searcher = SemanticSearcher(index_path=index_path)
        info = searcher.get_index_info()

        # Создаём таблицу
        table = Table(title="Статистика индекса")
        table.add_column("Параметр", style="cyan")
        table.add_column("Значение", style="green")

        table.add_row("Всего документов", str(info.get('total_documents', 0)))
        table.add_row("Всего чанков", str(info.get('total_chunks', 0)))
        table.add_row("Модель эмбеддингов", info.get('embedding_model', 'N/A'))
        table.add_row("Размерность векторов", str(info.get('embedding_dimension', 0)))
        table.add_row("Создан", info.get('created_at', 'N/A'))
        table.add_row("Обновлён", info.get('updated_at', 'N/A'))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Ошибка загрузки статистики: {e}[/red]")


@cli.command()
@click.option('--config', default='config/embeddings_config.yaml', help='Файл конфигурации')
@click.confirmation_option(prompt='Вы уверены, что хотите очистить индекс?')
def clear(config):
    """Очистка индекса."""

    cfg = load_config(config)
    indexing_config = cfg.get('indexing', {})
    index_path = indexing_config.get('index_path', 'data/embeddings/document_index.json')

    if os.path.exists(index_path):
        os.remove(index_path)
        console.print("[green]✓ Индекс очищен[/green]")
    else:
        console.print("[yellow]Индекс не найден[/yellow]")


@cli.command()
@click.option('--config', default='config/embeddings_config.yaml', help='Файл конфигурации')
def verify(config):
    """Проверка работоспособности Ollama."""

    console.print("[bold blue]Проверка Ollama...[/bold blue]\n")

    cfg = load_config(config)
    ollama_config = cfg.get('ollama', {})

    embedder = OllamaEmbedder(**ollama_config)

    if embedder.check_connection():
        console.print("[green]✓ Ollama доступен[/green]")

        # Получаем информацию о модели
        model_info = embedder.get_model_info()
        if model_info:
            console.print(f"[green]✓ Модель {ollama_config.get('model')} найдена[/green]")
        else:
            console.print(f"[yellow]⚠ Модель {ollama_config.get('model')} не найдена[/yellow]")
            console.print(f"[yellow]Выполните: ollama pull {ollama_config.get('model')}[/yellow]")
    else:
        console.print(f"[red]✗ Ollama недоступен по адресу {ollama_config.get('url')}[/red]")
        console.print("\n[yellow]Инструкция по запуску:[/yellow]")
        console.print("1. Установите Ollama: https://ollama.com/download")
        console.print("2. Запустите сервер: ollama serve")
        console.print(f"3. Загрузите модель: ollama pull {ollama_config.get('model')}")


if __name__ == '__main__':
    cli()
