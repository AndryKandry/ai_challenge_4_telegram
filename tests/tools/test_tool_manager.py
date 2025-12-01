"""
Unit тесты для ToolManager.

Тестируют регистрацию инструментов, их вызов и обработку ошибок.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import os

from tools.tool_manager import ToolManager
from tools.base_tool import BaseTool


class MockTool(BaseTool):
    """Мок инструмент для тестов."""
    
    def __init__(self, name="mock_tool", should_fail=False):
        super().__init__(name)
        self.should_fail = should_fail
        self.call_count = 0
        self.last_params = None
    
    async def execute(self, **params):
        """Мок execute метода."""
        self.call_count += 1
        self.last_params = params
        
        if self.should_fail:
            raise Exception(f"Tool {self.name} failed")
        
        return {"result": f"Tool {self.name} executed", "params": params}


class TestToolManager:
    """Тесты для ToolManager."""

    @pytest.fixture
    def tool_manager(self):
        """Создает экземпляр ToolManager для тестов."""
        return ToolManager()

    @pytest.fixture
    def mock_tool(self):
        """Создает мок инструмент."""
        return MockTool("test_tool")

    def test_initialization(self, tool_manager):
        """Тест инициализации ToolManager."""
        assert len(tool_manager.tools) == 0
        assert tool_manager.default_timeout == 30
        assert tool_manager.enabled is True

    def test_register_tool_success(self, tool_manager, mock_tool):
        """Тест успешной регистрации инструмента."""
        result = tool_manager.register_tool(mock_tool)
        
        assert result is True
        assert "test_tool" in tool_manager.tools
        assert tool_manager.tools["test_tool"] == mock_tool

    def test_register_duplicate_tool(self, tool_manager, mock_tool):
        """Тест регистрации дублирующего инструмента."""
        tool_manager.register_tool(mock_tool)
        
        # Попытка зарегистрировать инструмент с таким же именем
        duplicate_tool = MockTool("test_tool")
        result = tool_manager.register_tool(duplicate_tool)
        
        assert result is False
        assert tool_manager.tools["test_tool"] == mock_tool  # Остался оригинал

    def test_register_invalid_tool(self, tool_manager):
        """Тест регистрации невалидного инструмента."""
        result = tool_manager.register_tool("not_a_tool")
        
        assert result is False
        assert len(tool_manager.tools) == 0

    def test_unregister_tool_success(self, tool_manager, mock_tool):
        """Тест успешной отмены регистрации инструмента."""
        tool_manager.register_tool(mock_tool)
        result = tool_manager.unregister_tool("test_tool")
        
        assert result is True
        assert "test_tool" not in tool_manager.tools

    def test_unregister_nonexistent_tool(self, tool_manager):
        """Тест отмены регистрации несуществующего инструмента."""
        result = tool_manager.unregister_tool("nonexistent_tool")
        
        assert result is False

    def test_get_tool_success(self, tool_manager, mock_tool):
        """Тест получения инструмента."""
        tool_manager.register_tool(mock_tool)
        result = tool_manager.get_tool("test_tool")
        
        assert result == mock_tool

    def test_get_nonexistent_tool(self, tool_manager):
        """Тест получения несуществующего инструмента."""
        result = tool_manager.get_tool("nonexistent_tool")
        
        assert result is None

    def test_list_tools(self, tool_manager):
        """Тест списка инструментов."""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        
        tool_manager.register_tool(tool1)
        tool_manager.register_tool(tool2)
        
        tools_list = tool_manager.list_tools()
        
        assert len(tools_list) == 2
        assert "tool1" in tools_list
        assert "tool2" in tools_list

    @pytest.mark.asyncio
    async def test_call_tool_success(self, tool_manager, mock_tool):
        """Тест успешного вызова инструмента."""
        tool_manager.register_tool(mock_tool)
        
        result = await tool_manager.call_tool("test_tool", param1="value1", param2="value2")
        
        assert result["result"] == "Tool test_tool executed"
        assert result["params"]["param1"] == "value1"
        assert result["params"]["param2"] == "value2"
        assert mock_tool.call_count == 1
        assert mock_tool.last_params["param1"] == "value1"

    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self, tool_manager):
        """Тест вызова несуществующего инструмента."""
        result = await tool_manager.call_tool("nonexistent_tool")
        
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_call_tool_exception(self, tool_manager):
        """Тест обработки исключения при вызове инструмента."""
        failing_tool = MockTool("failing_tool", should_fail=True)
        tool_manager.register_tool(failing_tool)
        
        result = await tool_manager.call_tool("failing_tool")
        
        assert "error" in result
        assert "failed" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_with_timeout(self, tool_manager):
        """Тест вызова инструмента с таймаутом."""
        class SlowTool(BaseTool):
            async def execute(self, **params):
                await asyncio.sleep(2)  # Дольше таймаута
                return {"result": "slow result"}
        
        slow_tool = SlowTool("slow_tool")
        tool_manager.register_tool(slow_tool)
        
        # Устанавливаем короткий таймаут
        tool_manager.default_timeout = 0.1
        
        result = await tool_manager.call_tool("slow_tool")
        
        assert "error" in result
        assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_parallel_tool_execution(self, tool_manager):
        """Тест параллельного выполнения инструментов."""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        
        tool_manager.register_tool(tool1)
        tool_manager.register_tool(tool2)
        
        # Создаем медленные инструменты для проверки параллелизма
        class SlowTool(BaseTool):
            def __init__(self, name, delay):
                super().__init__(name)
                self.delay = delay
            
            async def execute(self, **params):
                await asyncio.sleep(self.delay)
                return {"result": f"Tool {self.name} completed"}
        
        slow_tool1 = SlowTool("slow1", 0.1)
        slow_tool2 = SlowTool("slow2", 0.1)
        
        tool_manager.register_tool(slow_tool1)
        tool_manager.register_tool(slow_tool2)
        
        import time
        start_time = time.time()
        
        results = await tool_manager.call_tools_parallel([
            ("slow1", {}),
            ("slow2", {})
        ])
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Параллельное выполнение должно быть быстрее последовательного
        assert execution_time < 0.15  # Меньше чем 0.1 + 0.1
        assert len(results) == 2
        assert all("result" in result for result in results)

    @pytest.mark.asyncio
    async def test_tool_validation(self, tool_manager):
        """Тест валидации инструментов."""
        class InvalidTool:
            # Не наследуется от BaseTool
            pass
        
        invalid_tool = InvalidTool()
        result = tool_manager.register_tool(invalid_tool)
        
        assert result is False

    def test_enable_disable_manager(self, tool_manager, mock_tool):
        """Тест включения/выключения менеджера."""
        tool_manager.register_tool(mock_tool)
        
        # Отключаем менеджер
        tool_manager.enabled = False
        assert not tool_manager.enabled
        
        # Включаем менеджер
        tool_manager.enabled = True
        assert tool_manager.enabled

    @pytest.mark.asyncio
    async def test_call_tool_when_manager_disabled(self, tool_manager, mock_tool):
        """Тест вызова инструмента при отключенном менеджере."""
        tool_manager.register_tool(mock_tool)
        tool_manager.enabled = False
        
        result = await tool_manager.call_tool("test_tool")
        
        assert "error" in result
        assert "disabled" in result["error"].lower()

    def test_get_tool_stats(self, tool_manager):
        """Тест получения статистики инструментов."""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        
        tool_manager.register_tool(tool1)
        tool_manager.register_tool(tool2)
        
        stats = tool_manager.get_tool_stats()
        
        assert stats["total_tools"] == 2
        assert stats["enabled_tools"] == 2
        assert "tool1" in stats["tools"]
        assert "tool2" in stats["tools"]

    @pytest.mark.asyncio
    async def test_tool_with_context(self, tool_manager):
        """Тест вызова инструмента с контекстом."""
        class ContextTool(BaseTool):
            async def execute(self, **params):
                context = params.get("context", {})
                return {"result": f"Context: {context}"}
        
        context_tool = ContextTool("context_tool")
        tool_manager.register_tool(context_tool)
        
        result = await tool_manager.call_tool(
            "context_tool",
            context={"user_id": "123", "session": "abc"}
        )
        
        assert "123" in result["result"]
        assert "abc" in result["result"]

    def test_tool_categories(self, tool_manager):
        """Тест категорий инструментов."""
        tool1 = MockTool("tool1")
        tool1.category = "system"
        
        tool2 = MockTool("tool2")
        tool2.category = "network"
        
        tool_manager.register_tool(tool1)
        tool_manager.register_tool(tool2)
        
        system_tools = tool_manager.get_tools_by_category("system")
        network_tools = tool_manager.get_tools_by_category("network")
        
        assert len(system_tools) == 1
        assert system_tools[0].name == "tool1"
        assert len(network_tools) == 1
        assert network_tools[0].name == "tool2"

    @pytest.mark.asyncio
    async def test_tool_retry_mechanism(self, tool_manager):
        """Тест механизма повторных попыток."""
        class FlakyTool(BaseTool):
            def __init__(self, name, fail_count=1):
                super().__init__(name)
                self.fail_count = fail_count
                self.attempts = 0
            
            async def execute(self, **params):
                self.attempts += 1
                if self.attempts <= self.fail_count:
                    raise Exception(f"Attempt {self.attempts} failed")
                return {"result": "success after retries"}
        
        flaky_tool = FlakyTool("flaky_tool", fail_count=2)
        tool_manager.register_tool(flaky_tool)
        
        result = await tool_manager.call_tool("flaky_tool", max_retries=3)
        
        assert result["result"] == "success after retries"
        assert flaky_tool.attempts == 3

    @pytest.mark.asyncio
    async def test_tool_retry_exhausted(self, tool_manager):
        """Тест исчерпания попыток повторного вызова."""
        class AlwaysFailingTool(BaseTool):
            async def execute(self, **params):
                raise Exception("Always fails")
        
        failing_tool = AlwaysFailingTool("always_failing")
        tool_manager.register_tool(failing_tool)
        
        result = await tool_manager.call_tool("always_failing", max_retries=2)
        
        assert "error" in result
        assert "exhausted" in result["error"].lower() or "failed" in result["error"].lower()


if __name__ == "__main__":
    pytest.main([__file__])
