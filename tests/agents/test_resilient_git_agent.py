"""
Unit тесты для ResilientGitAgent.

Тестируют fallback механизмы, кеширование и обработку ошибок.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import os
import json

from agents.resilient_git_agent import ResilientGitAgent
from agents.base_agent import BaseAgent


class TestResilientGitAgent:
    """Тесты для ResilientGitAgent."""

    @pytest.fixture
    def mock_tool_manager(self):
        """Mock для ToolManager."""
        manager = Mock()
        manager.tools = {}
        return manager

    @pytest.fixture
    def temp_git_repo(self):
        """Временный git репозиторий для тестов."""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        repo_path = Path(temp_dir)
        
        # Инициализируем git репозиторий
        os.system(f"cd {repo_path} && git init")
        os.system(f"cd {repo_path} && git config user.name 'Test User'")
        os.system(f"cd {repo_path} && git config user.email 'test@example.com'")
        
        # Создаем тестовый файл
        test_file = repo_path / "test.txt"
        test_file.write_text("Test content")
        os.system(f"cd {repo_path} && git add test.txt")
        os.system(f"cd {repo_path} && git commit -m 'Initial commit'")
        
        yield repo_path
        
        # Очистка
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def resilient_agent(self, mock_tool_manager, temp_git_repo):
        """Создает экземпляр ResilientGitAgent для тестов."""
        agent = ResilientGitAgent(
            tool_manager=mock_tool_manager,
            repo_path=str(temp_git_repo),
            cache_timeout=1  # Короткое время жизни кеша для тестов
        )
        return agent

    @pytest.mark.asyncio
    async def test_initialization(self, mock_tool_manager, temp_git_repo):
        """Тест инициализации агента."""
        agent = ResilientGitAgent(
            tool_manager=mock_tool_manager,
            repo_path=str(temp_git_repo)
        )
        
        assert agent.name == "resilient_git_agent"
        assert agent.enabled is True
        assert agent.enable_fallback is True
        assert agent.is_git_repo is True
        assert str(agent.repo_path) == str(temp_git_repo.resolve())

    @pytest.mark.asyncio
    async def test_initialization_non_git_repo(self, mock_tool_manager):
        """Тест инициализации с не-git директорией."""
        temp_dir = tempfile.mkdtemp()
        
        agent = ResilientGitAgent(
            tool_manager=mock_tool_manager,
            repo_path=temp_dir
        )
        
        assert agent.is_git_repo is False
        
        # Очистка
        os.rmdir(temp_dir)

    @pytest.mark.asyncio
    async def test_get_current_branch_success(self, resilient_agent):
        """Тест успешного получения текущей ветки."""
        # Мокаем успешный вызов github_mcp
        resilient_agent.call_tool = AsyncMock(return_value="main")
        
        result = await resilient_agent.execute({
            "action": "get_current_branch",
            "params": {}
        })
        
        assert result["success"] is True
        assert result["data"] == "main"
        assert result["method"] == "github_mcp"
        assert result["from_cache"] is False

    @pytest.mark.asyncio
    async def test_get_current_branch_fallback_to_subprocess(self, resilient_agent):
        """Тест fallback к subprocess при недоступности github_mcp."""
        # Мокаем неудачный вызов github_mcp и успешный subprocess
        resilient_agent.call_tool = AsyncMock(side_effect=Exception("MCP unavailable"))
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout="main\n"
            )
            
            result = await resilient_agent.execute({
                "action": "get_current_branch",
                "params": {}
            })
            
            assert result["success"] is True
            assert result["data"] == "main"
            assert result["method"] == "subprocess_git"

    @pytest.mark.asyncio
    async def test_get_current_branch_all_methods_fail(self, resilient_agent):
        """Тест поведения при недоступности всех методов."""
        # Мокаем неудачные вызовы всех методов
        resilient_agent.call_tool = AsyncMock(side_effect=Exception("All tools failed"))
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.side_effect = FileNotFoundError("Git not found")
            
            result = await resilient_agent.execute({
                "action": "get_current_branch",
                "params": {}
            })
            
            assert result["success"] is False
            assert result["method"] == "none"
            assert "error" in result
            assert result["data"]["branch"] == "unknown"

    @pytest.mark.asyncio
    async def test_caching_functionality(self, resilient_agent):
        """Тест работы кеша."""
        # Первый вызов
        resilient_agent.call_tool = AsyncMock(return_value="main")
        
        result1 = await resilient_agent.execute({
            "action": "get_current_branch",
            "params": {}
        })
        
        # Второй вызов должен использовать кеш
        result2 = await resilient_agent.execute({
            "action": "get_current_branch",
            "params": {}
        })
        
        assert result1["success"] is True
        assert result2["success"] is True
        assert result2["from_cache"] is True
        assert result2["method"] == "github_mcp"
        
        # Проверяем, что call_tool вызывался только один раз
        resilient_agent.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_expiration(self, resilient_agent):
        """Тест истечения времени жизни кеша."""
        # Устанавливаем очень короткое время жизни кеша
        resilient_agent.cache_timeout = 0.001  # 1ms
        
        resilient_agent.call_tool = AsyncMock(return_value="main")
        
        # Первый вызов
        result1 = await resilient_agent.execute({
            "action": "get_current_branch",
            "params": {}
        })
        
        # Ждем истечения кеша
        await asyncio.sleep(0.01)
        
        # Второй вызов не должен использовать кеш
        result2 = await resilient_agent.execute({
            "action": "get_current_branch",
            "params": {}
        })
        
        assert result1["from_cache"] is False
        assert result2["from_cache"] is False
        assert resilient_agent.call_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_get_modified_files_success(self, resilient_agent):
        """Тест получения измененных файлов."""
        mock_status = {
            "modified_files": ["file1.py", "file2.py"],
            "staged_files": [],
            "untracked_files": ["file3.py"],
            "is_clean": False
        }
        
        resilient_agent.call_tool = AsyncMock(return_value=mock_status)
        
        result = await resilient_agent.execute({
            "action": "get_modified_files",
            "params": {}
        })
        
        assert result["success"] is True
        assert result["data"]["modified_files"] == ["file1.py", "file2.py"]

    @pytest.mark.asyncio
    async def test_get_recent_commits_success(self, resilient_agent):
        """Тест получения последних коммитов."""
        mock_commits = [
            {"hash": "abc123", "author": "Test", "date": "2 hours ago", "message": "Test commit 1"},
            {"hash": "def456", "author": "Test", "date": "1 day ago", "message": "Test commit 2"}
        ]
        
        resilient_agent.call_tool = AsyncMock(return_value=mock_commits)
        
        result = await resilient_agent.execute({
            "action": "get_recent_commits",
            "params": {"limit": 10}
        })
        
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["hash"] == "abc123"

    @pytest.mark.asyncio
    async def test_search_commits_success(self, resilient_agent):
        """Тест поиска коммитов."""
        mock_commits = [
            {"hash": "abc123", "author": "Test", "date": "2 hours ago", "message": "Fix bug in search"}
        ]
        
        resilient_agent.call_tool = AsyncMock(return_value=mock_commits)
        
        result = await resilient_agent.execute({
            "action": "search_commits",
            "params": {"query": "bug", "limit": 5}
        })
        
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert "bug" in result["data"][0]["message"]

    @pytest.mark.asyncio
    async def test_fallback_stats_tracking(self, resilient_agent):
        """Тест отслеживания статистики fallback."""
        # Мокаем неудачный вызов github_mcp и успешный subprocess
        resilient_agent.call_tool = AsyncMock(side_effect=Exception("MCP failed"))
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout="main\n"
            )
            
            await resilient_agent.execute({
                "action": "get_current_branch",
                "params": {}
            })
            
            stats = resilient_agent.get_fallback_stats()
            
            assert stats["github_mcp_failed"] == 1
            assert stats["subprocess_git_success"] == 1

    @pytest.mark.asyncio
    async def test_clear_cache(self, resilient_agent):
        """Тест очистки кеша."""
        # Добавляем что-то в кеш
        resilient_agent._cache["test_key"] = "test_value"
        resilient_agent._cache_timestamps["test_key"] = 123456
        
        resilient_agent.clear_cache()
        
        assert len(resilient_agent._cache) == 0
        assert len(resilient_agent._cache_timestamps) == 0

    @pytest.mark.asyncio
    async def test_validate_input_success(self, resilient_agent):
        """Тест валидации входных данных - успех."""
        assert await resilient_agent.validate_input({
            "action": "get_current_branch",
            "params": {}
        })
        
        assert await resilient_agent.validate_input({
            "action": "get_file_diff",
            "params": {"filepath": "test.py"}
        })
        
        assert await resilient_agent.validate_input({
            "action": "search_commits",
            "params": {"query": "test"}
        })

    @pytest.mark.asyncio
    async def test_validate_input_failure(self, resilient_agent):
        """Тест валидации входных данных - ошибка."""
        assert not await resilient_agent.validate_input({
            "action": "get_file_diff",
            "params": {}  # Отсутствует filepath
        })
        
        assert not await resilient_agent.validate_input({
            "action": "search_commits",
            "params": {}  # Отсутствует query
        })

    @pytest.mark.asyncio
    async def test_unknown_action(self, resilient_agent):
        """Тест обработки неизвестного действия."""
        result = await resilient_agent.execute({
            "action": "unknown_action",
            "params": {}
        })
        
        assert result["success"] is False
        assert "Неизвестное действие" in result["error"]

    @pytest.mark.asyncio
    async def test_subprocess_git_timeout(self, resilient_agent):
        """Тест обработки таймаута subprocess."""
        resilient_agent.call_tool = AsyncMock(side_effect=Exception("MCP failed"))
        
        with patch('subprocess.run') as mock_subprocess:
            import subprocess
            mock_subprocess.side_effect = subprocess.TimeoutExpired("git", 30)
            
            result = await resilient_agent.execute({
                "action": "get_current_branch",
                "params": {}
            })
            
            assert result["success"] is False
            assert result["method"] == "none"  # Дошел до basic_response

    def test_parse_status_output(self, resilient_agent):
        """Тест парсинга вывода git status."""
        output = """# branch.head main
# branch.upstream origin/main
# branch.ab +0 -0
 M file1.py
A file2.py
?? file3.py
"""
        
        result = resilient_agent._parse_status_output(output)
        
        assert result["branch"] == "main"
        assert result["modified_files"] == ["file1.py"]
        assert result["staged_files"] == ["file2.py"]
        assert result["untracked_files"] == ["file3.py"]
        assert result["is_clean"] is False

    def test_parse_log_output(self, resilient_agent):
        """Тест парсинга вывода git log."""
        output = """abc123|Test User|2 hours ago|Test commit message
def456|Another User|1 day ago|Another commit"""
        
        result = resilient_agent._parse_log_output(output)
        
        assert len(result) == 2
        assert result[0]["hash"] == "abc123"
        assert result[0]["author"] == "Test User"
        assert result[0]["message"] == "Test commit message"
        assert result[1]["hash"] == "def456"

    def test_get_cache_key(self, resilient_agent):
        """Тест генерации ключа кеша."""
        key1 = resilient_agent._get_cache_key("get_branch", {"limit": 10}, "github_mcp")
        key2 = resilient_agent._get_cache_key("get_branch", {"limit": 10}, "github_mcp")
        key3 = resilient_agent._get_cache_key("get_branch", {"limit": 20}, "github_mcp")
        
        assert key1 == key2
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_fallback_disabled(self, resilient_agent):
        """Тест работы с отключенным fallback."""
        resilient_agent.enable_fallback = False
        resilient_agent.call_tool = AsyncMock(side_effect=Exception("MCP failed"))
        
        result = await resilient_agent.execute({
            "action": "get_current_branch",
            "params": {}
        })
        
        assert result["success"] is False
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__])
