#!/usr/bin/env python3
"""
GitHub MCP Server - предоставляет инструменты для работы с GitHub API
через Model Context Protocol.

Реализованные инструменты:
- get_user_repositories: получение списка публичных репозиториев пользователя
- get_user_info: получение информации о пользователе GitHub
- get_repository_commits: получение информации о коммитах в репозитории
"""

from typing import Any, Optional
import httpx
from fastmcp import FastMCP
import logging

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы GitHub API
GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
USER_AGENT = "github-mcp-server/1.0"
REQUEST_TIMEOUT = 30.0  # секунды

# Создание MCP сервера
mcp = FastMCP("github")


async def make_github_request(url: str, params: Optional[dict] = None) -> dict[str, Any] | None:
    """
    Выполнение запроса к GitHub API с обработкой ошибок.

    Args:
        url: URL для запроса
        params: Параметры запроса (опционально)

    Returns:
        JSON ответ от GitHub API или None в случае ошибки
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": USER_AGENT
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Запрос к GitHub API: {url}")
            response = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True
            )

            # Проверка rate limit
            remaining = response.headers.get("X-RateLimit-Remaining")
            limit = response.headers.get("X-RateLimit-Limit")
            if remaining:
                logger.debug(f"GitHub API Rate Limit: {remaining}/{limit}")

            response.raise_for_status()
            logger.info(f"Успешный ответ от GitHub API: {response.status_code}")
            return response.json()

        except httpx.TimeoutException:
            logger.error(f"Timeout при запросе к GitHub API: {url}")
            return {
                "error": "timeout",
                "message": "Превышено время ожидания ответа от GitHub API (30 сек). Попробуйте позже."
            }

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP ошибка {status_code} при запросе к GitHub API: {url}")

            # Обработка специфичных ошибок GitHub
            if status_code == 404:
                return {
                    "error": "not_found",
                    "message": "Пользователь или репозиторий не найден. Проверьте правильность имени."
                }
            elif status_code == 403:
                # Проверка на rate limit
                reset_time = e.response.headers.get("X-RateLimit-Reset")
                return {
                    "error": "rate_limit",
                    "message": f"Превышен лимит запросов к GitHub API (60/час для неавторизованных запросов). "
                               f"Попробуйте позже. Reset time: {reset_time}"
                }
            elif status_code == 422:
                return {
                    "error": "validation_failed",
                    "message": "Невалидные параметры запроса. Проверьте корректность данных."
                }
            else:
                return {
                    "error": f"http_{status_code}",
                    "message": f"Ошибка GitHub API: {status_code}. Попробуйте позже."
                }

        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к GitHub API: {e}", exc_info=True)
            return {
                "error": "unknown",
                "message": f"Произошла неожиданная ошибка: {str(e)}"
            }


def format_repository(repo: dict) -> str:
    """
    Форматирование информации о репозитории в читаемый вид.

    Args:
        repo: Словарь с данными репозитория

    Returns:
        Отформатированная строка с информацией о репозитории
    """
    name = repo.get('name', 'Unknown')
    full_name = repo.get('full_name', 'Unknown')
    description = repo.get('description', 'No description')
    language = repo.get('language', 'N/A')
    stars = repo.get('stargazers_count', 0)
    forks = repo.get('forks_count', 0)
    url = repo.get('html_url', '')

    return f"""
Repository: {full_name}
Description: {description}
Language: {language}
Stars: ⭐ {stars} | Forks: 🍴 {forks}
URL: {url}
"""


def format_user_info(user: dict) -> str:
    """
    Форматирование информации о пользователе GitHub.

    Args:
        user: Словарь с данными пользователя

    Returns:
        Отформатированная строка с информацией о пользователе
    """
    login = user.get('login', 'Unknown')
    name = user.get('name', 'N/A')
    bio = user.get('bio', 'No bio available')
    location = user.get('location', 'N/A')
    public_repos = user.get('public_repos', 0)
    followers = user.get('followers', 0)
    following = user.get('following', 0)
    created_at = user.get('created_at', 'Unknown')
    url = user.get('html_url', '')

    return f"""
GitHub User: {login}
Name: {name}
Bio: {bio}
Location: {location}
Public Repositories: {public_repos}
Followers: {followers} | Following: {following}
Member since: {created_at}
Profile URL: {url}
"""


def format_commit(commit: dict) -> str:
    """
    Форматирование информации о коммите.

    Args:
        commit: Словарь с данными коммита

    Returns:
        Отформатированная строка с информацией о коммите
    """
    sha = commit.get('sha', 'Unknown')[:7]  # Короткий SHA
    commit_data = commit.get('commit', {})
    message = commit_data.get('message', 'No message').split('\n')[0]  # Первая строка
    author_data = commit_data.get('author', {})
    author_name = author_data.get('name', 'Unknown')
    author_date = author_data.get('date', 'Unknown')

    return f"""
Commit: {sha}
Author: {author_name}
Date: {author_date}
Message: {message}
"""


@mcp.tool()
async def get_user_repositories(username: str) -> str:
    """
    Получить список публичных репозиториев пользователя GitHub.

    Args:
        username: Имя пользователя GitHub (например, 'torvalds', 'octocat')

    Returns:
        Отформатированный список репозиториев или сообщение об ошибке
    """
    url = f"{GITHUB_API_BASE}/users/{username}/repos"
    params = {
        "sort": "updated",  # Сортировка по дате обновления
        "per_page": 10      # Максимум 10 репозиториев (уменьшено для быстрой обработки)
    }

    data = await make_github_request(url, params)

    if not data:
        return "Не удалось получить список репозиториев. Попробуйте позже."

    # Проверка на ошибку
    if "error" in data:
        return f"❌ Ошибка: {data['message']}"

    # Проверка что получен список
    if not isinstance(data, list):
        return "Неожиданный формат ответа от GitHub API."

    if len(data) == 0:
        return f"У пользователя {username} нет публичных репозиториев."

    # Форматирование результатов
    result = f"📚 Публичные репозитории пользователя {username} (показаны последние {len(data)}):\n"
    result += "=" * 60 + "\n"

    for repo in data:
        result += format_repository(repo)
        result += "-" * 60 + "\n"

    return result


@mcp.tool()
async def get_user_info(username: str) -> str:
    """
    Получить информацию о пользователе GitHub.

    Args:
        username: Имя пользователя GitHub (например, 'torvalds', 'octocat')

    Returns:
        Отформатированная информация о пользователе или сообщение об ошибке
    """
    url = f"{GITHUB_API_BASE}/users/{username}"

    data = await make_github_request(url)

    if not data:
        return "Не удалось получить информацию о пользователе. Попробуйте позже."

    # Проверка на ошибку
    if "error" in data:
        return f"❌ Ошибка: {data['message']}"

    # Форматирование результата
    result = "👤 Информация о пользователе GitHub:\n"
    result += "=" * 60 + "\n"
    result += format_user_info(data)

    return result


@mcp.tool()
async def get_repository_commits(
    owner: str,
    repo: str,
    per_page: int = 30,
    page: int = 1
) -> str:
    """
    Получить информацию о коммитах в репозитории.

    Args:
        owner: Владелец репозитория (например, 'torvalds')
        repo: Название репозитория (например, 'linux')
        per_page: Количество коммитов на странице (по умолчанию 30, максимум 100)
        page: Номер страницы (по умолчанию 1)

    Returns:
        Отформатированный список коммитов или сообщение об ошибке
    """
    # Валидация параметров
    if per_page < 1 or per_page > 100:
        return "❌ Параметр per_page должен быть от 1 до 100."

    if page < 1:
        return "❌ Параметр page должен быть больше 0."

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
    params = {
        "per_page": per_page,
        "page": page
    }

    data = await make_github_request(url, params)

    if not data:
        return "Не удалось получить список коммитов. Попробуйте позже."

    # Проверка на ошибку
    if "error" in data:
        return f"❌ Ошибка: {data['message']}"

    # Проверка что получен список
    if not isinstance(data, list):
        return "Неожиданный формат ответа от GitHub API."

    if len(data) == 0:
        return f"В репозитории {owner}/{repo} нет коммитов или страница {page} пуста."

    # Форматирование результатов
    result = f"📝 Коммиты в репозитории {owner}/{repo} (страница {page}, показано {len(data)}):\n"
    result += "=" * 60 + "\n"

    for commit in data:
        result += format_commit(commit)
        result += "-" * 60 + "\n"

    return result


if __name__ == "__main__":
    # Используем SSE транспорт вместо stdio из-за бага в MCP SDK
    # https://github.com/modelcontextprotocol/python-sdk/issues/862
    import sys

    # Если запущен с аргументом --stdio, использовать stdio (для совместимости)
    # Иначе использовать SSE по умолчанию
    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        logger.info("Запуск GitHub MCP сервера в режиме stdio")
        mcp.run(transport="stdio")
    else:
        # SSE транспорт по умолчанию (работает стабильно)
        logger.info("Запуск GitHub MCP сервера в режиме SSE на порту 8001")
        mcp.run(transport="sse", port=8001)
