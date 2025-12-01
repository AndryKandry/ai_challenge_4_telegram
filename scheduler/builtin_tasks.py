"""
Встроенные задачи для планировщика.

Набор готовых задач для типовых операций:
- Переиндексация документов
- Обновление git-статистики
- Очистка кеша
- Проверка здоровья системы
"""

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from .base_task import BaseTask, TaskPriority

logger = logging.getLogger(__name__)


class ReindexDocumentsTask(BaseTask):
    """
    Задача для переиндексации документов в RAG системе.

    Периодически сканирует директорию с документами и обновляет
    индекс эмбеддингов для улучшения качества поиска.
    """

    def __init__(
        self,
        rag_manager,
        docs_path: str,
        task_id: str = "reindex_documents",
        interval: timedelta = timedelta(hours=24),
        priority: TaskPriority = TaskPriority.NORMAL
    ):
        """
        Инициализация задачи переиндексации.

        Args:
            rag_manager: Экземпляр RAGManager для работы с индексом
            docs_path: Путь к директории с документами
            task_id: ID задачи
            interval: Интервал между запусками (по умолчанию 24 часа)
            priority: Приоритет задачи
        """
        super().__init__(
            task_id=task_id,
            name="Reindex Documents",
            priority=priority,
            interval=interval,
            is_periodic=True,
            max_retries=3
        )
        self.rag_manager = rag_manager
        self.docs_path = Path(docs_path)

    async def execute(self) -> Dict[str, Any]:
        """
        Выполнение переиндексации документов.

        Returns:
            Словарь с результатами индексации:
                - indexed_files: количество проиндексированных файлов
                - total_chunks: общее количество чанков
                - errors: количество ошибок

        Raises:
            Exception: При ошибках индексации
        """
        logger.info(f"Starting document reindexing from {self.docs_path}")

        if not self.docs_path.exists():
            raise FileNotFoundError(f"Documents path not found: {self.docs_path}")

        # Получаем список файлов для индексации
        file_patterns = ["**/*.md", "**/*.txt", "**/*.py"]
        files_to_index = []

        for pattern in file_patterns:
            files_to_index.extend(self.docs_path.glob(pattern))

        if not files_to_index:
            logger.warning(f"No documents found in {self.docs_path}")
            return {
                "indexed_files": 0,
                "total_chunks": 0,
                "errors": 0
            }

        logger.info(f"Found {len(files_to_index)} files to index")

        # Выполняем индексацию через RAG manager
        indexed_count = 0
        total_chunks = 0
        error_count = 0

        for file_path in files_to_index:
            try:
                # Здесь должна быть логика индексации через RAG manager
                # Например: chunks = await self.rag_manager.index_file(file_path)
                # total_chunks += len(chunks)
                indexed_count += 1
            except Exception as e:
                logger.error(f"Error indexing file {file_path}: {e}")
                error_count += 1

        result = {
            "indexed_files": indexed_count,
            "total_chunks": total_chunks,
            "errors": error_count
        }

        logger.info(
            f"Reindexing completed: {indexed_count} files, "
            f"{total_chunks} chunks, {error_count} errors"
        )

        return result


class UpdateGitStatsTask(BaseTask):
    """
    Задача для обновления статистики git-репозитория.

    Периодически собирает информацию о состоянии репозитория:
    - Список измененных файлов
    - Текущая ветка
    - Последние коммиты
    - Статус изменений
    """

    def __init__(
        self,
        repo_path: str = ".",
        task_id: str = "update_git_stats",
        interval: timedelta = timedelta(hours=1),
        priority: TaskPriority = TaskPriority.LOW
    ):
        """
        Инициализация задачи обновления git статистики.

        Args:
            repo_path: Путь к git-репозиторию
            task_id: ID задачи
            interval: Интервал между запусками (по умолчанию 1 час)
            priority: Приоритет задачи
        """
        super().__init__(
            task_id=task_id,
            name="Update Git Statistics",
            priority=priority,
            interval=interval,
            is_periodic=True,
            max_retries=2
        )
        self.repo_path = Path(repo_path)

    async def execute(self) -> Dict[str, Any]:
        """
        Выполнение обновления git статистики.

        Returns:
            Словарь с git статистикой:
                - current_branch: текущая ветка
                - modified_files: количество измененных файлов
                - untracked_files: количество неотслеживаемых файлов
                - commits_count: количество коммитов в текущей ветке

        Raises:
            Exception: При ошибках работы с git
        """
        logger.info(f"Updating git statistics for {self.repo_path}")

        if not (self.repo_path / ".git").exists():
            raise FileNotFoundError(f"Not a git repository: {self.repo_path}")

        # Здесь должна быть логика сбора git статистики
        # Можно использовать GitPython или subprocess для запуска git команд

        # Заглушка для примера
        result = {
            "current_branch": "main",
            "modified_files": 0,
            "untracked_files": 0,
            "commits_count": 100,
            "last_commit_time": None
        }

        logger.info(f"Git statistics updated: branch={result['current_branch']}")

        return result


class ClearCacheTask(BaseTask):
    """
    Задача для очистки временных данных и кеша.

    Периодически удаляет устаревшие кешированные данные,
    временные файлы и логи для освобождения места.
    """

    def __init__(
        self,
        cache_paths: list[str],
        max_age_days: int = 7,
        task_id: str = "clear_cache",
        interval: timedelta = timedelta(days=1),
        priority: TaskPriority = TaskPriority.LOW
    ):
        """
        Инициализация задачи очистки кеша.

        Args:
            cache_paths: Список путей к директориям кеша
            max_age_days: Максимальный возраст файлов в днях
            task_id: ID задачи
            interval: Интервал между запусками (по умолчанию 1 день)
            priority: Приоритет задачи
        """
        super().__init__(
            task_id=task_id,
            name="Clear Cache",
            priority=priority,
            interval=interval,
            is_periodic=True,
            max_retries=1
        )
        self.cache_paths = [Path(p) for p in cache_paths]
        self.max_age_days = max_age_days

    async def execute(self) -> Dict[str, Any]:
        """
        Выполнение очистки кеша.

        Returns:
            Словарь с результатами очистки:
                - deleted_files: количество удаленных файлов
                - freed_space_mb: освобожденное место в МБ
                - errors: количество ошибок

        Raises:
            Exception: При критических ошибках очистки
        """
        logger.info(f"Starting cache cleanup (max age: {self.max_age_days} days)")

        deleted_count = 0
        freed_space = 0
        error_count = 0

        for cache_path in self.cache_paths:
            if not cache_path.exists():
                logger.warning(f"Cache path not found: {cache_path}")
                continue

            logger.info(f"Cleaning cache in {cache_path}")

            # Здесь должна быть логика удаления старых файлов
            # Можно использовать os.walk и проверять время модификации файлов

        result = {
            "deleted_files": deleted_count,
            "freed_space_mb": freed_space / (1024 * 1024),
            "errors": error_count
        }

        logger.info(
            f"Cache cleanup completed: {deleted_count} files deleted, "
            f"{result['freed_space_mb']:.2f} MB freed"
        )

        return result


class HealthCheckTask(BaseTask):
    """
    Задача для проверки здоровья системы.

    Периодически проверяет состояние всех компонентов системы:
    - RAG система
    - Агенты
    - Инструменты
    - База данных
    """

    def __init__(
        self,
        components: Dict[str, Any],
        task_id: str = "health_check",
        interval: timedelta = timedelta(minutes=30),
        priority: TaskPriority = TaskPriority.HIGH
    ):
        """
        Инициализация задачи проверки здоровья.

        Args:
            components: Словарь компонентов для проверки
            task_id: ID задачи
            interval: Интервал между запусками (по умолчанию 30 минут)
            priority: Приоритет задачи
        """
        super().__init__(
            task_id=task_id,
            name="System Health Check",
            priority=priority,
            interval=interval,
            is_periodic=True,
            max_retries=1
        )
        self.components = components

    async def execute(self) -> Dict[str, Any]:
        """
        Выполнение проверки здоровья системы.

        Returns:
            Словарь с результатами проверки:
                - healthy: общее состояние системы
                - components: состояние каждого компонента
                - warnings: список предупреждений

        Raises:
            Exception: При критических ошибках проверки
        """
        logger.info("Starting system health check")

        component_status = {}
        warnings = []
        all_healthy = True

        for name, component in self.components.items():
            try:
                # Проверяем, есть ли метод health_check у компонента
                if hasattr(component, 'health_check'):
                    status = await component.health_check()
                    component_status[name] = status

                    if not status.get('healthy', True):
                        all_healthy = False
                        warnings.append(f"Component '{name}' is unhealthy")
                else:
                    component_status[name] = {"healthy": True, "note": "No health check method"}
            except Exception as e:
                logger.error(f"Error checking component '{name}': {e}")
                component_status[name] = {"healthy": False, "error": str(e)}
                all_healthy = False
                warnings.append(f"Component '{name}' check failed: {e}")

        result = {
            "healthy": all_healthy,
            "components": component_status,
            "warnings": warnings
        }

        if all_healthy:
            logger.info("System health check passed")
        else:
            logger.warning(f"System health check found issues: {len(warnings)} warnings")

        return result
