"""
Unit тесты для DocsAgent.

Тестируют RAG функциональность, поиск документов и обработку ошибок.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import os
import json

from agents.docs_agent import DocsAgent
from agents.base_agent import BaseAgent


class TestDocsAgent:
    """Тесты для DocsAgent."""

    @pytest.fixture
    def mock_tool_manager(self):
        """Mock для ToolManager."""
        manager = Mock()
        manager.tools = {}
        return manager

    @pytest.fixture
    def mock_rag_manager(self):
        """Mock для RAGManager."""
        rag_manager = Mock()
        rag_manager.search_documents = AsyncMock()
        rag_manager.get_document_stats = AsyncMock()
        rag_manager.get_relevant_chunks = AsyncMock()
        return rag_manager

    @pytest.fixture
    def docs_agent(self, mock_tool_manager, mock_rag_manager):
        """Создает экземпляр DocsAgent для тестов."""
        agent = DocsAgent(
            tool_manager=mock_tool_manager,
            rag_manager=mock_rag_manager,
            name="test_docs_agent"
        )
        return agent

    @pytest.mark.asyncio
    async def test_initialization(self, mock_tool_manager, mock_rag_manager):
        """Тест инициализации агента."""
        agent = DocsAgent(
            tool_manager=mock_tool_manager,
            rag_manager=mock_rag_manager,
            name="test_docs_agent"
        )
        
        assert agent.name == "test_docs_agent"
        assert agent.enabled is True
        assert agent.rag_manager == mock_rag_manager

    @pytest.mark.asyncio
    async def test_search_documents_success(self, docs_agent, mock_rag_manager):
        """Тест успешного поиска документов."""
        mock_results = [
            {
                "content": "Test document content about Python",
                "source": "docs/python.md",
                "score": 0.85,
                "metadata": {"file_type": "md", "language": "markdown"}
            },
            {
                "content": "Another test document",
                "source": "docs/test.md", 
                "score": 0.75,
                "metadata": {"file_type": "md", "language": "markdown"}
            }
        ]
        
        mock_rag_manager.search_documents.return_value = mock_results
        
        result = await docs_agent.execute({
            "action": "search_documents",
            "params": {
                "query": "Python programming",
                "limit": 5
            }
        })
        
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert "Python" in result["data"][0]["content"]
        assert result["data"][0]["source"] == "docs/python.md"
        
        mock_rag_manager.search_documents.assert_called_once_with(
            "Python programming",
            limit=5,
            use_reranking=True
        )

    @pytest.mark.asyncio
    async def test_search_documents_empty_result(self, docs_agent, mock_rag_manager):
        """Тест поиска документов с пустым результатом."""
        mock_rag_manager.search_documents.return_value = []
        
        result = await docs_agent.execute({
            "action": "search_documents",
            "params": {
                "query": "nonexistent topic",
                "limit": 10
            }
        })
        
        assert result["success"] is True
        assert len(result["data"]) == 0

    @pytest.mark.asyncio
    async def test_search_documents_error(self, docs_agent, mock_rag_manager):
        """Тест обработки ошибки при поиске документов."""
        mock_rag_manager.search_documents.side_effect = Exception("Search failed")
        
        result = await docs_agent.execute({
            "action": "search_documents",
            "params": {
                "query": "test query",
                "limit": 5
            }
        })
        
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_document_stats_success(self, docs_agent, mock_rag_manager):
        """Тест получения статистики документов."""
        mock_stats = {
            "total_documents": 25,
            "total_chunks": 150,
            "file_types": {"md": 20, "txt": 5},
            "index_size_mb": 2.5
        }
        
        mock_rag_manager.get_document_stats.return_value = mock_stats
        
        result = await docs_agent.execute({
            "action": "get_document_stats",
            "params": {}
        })
        
        assert result["success"] is True
        assert result["data"]["total_documents"] == 25
        assert result["data"]["total_chunks"] == 150
        assert "md" in result["data"]["file_types"]

    @pytest.mark.asyncio
    async def test_get_relevant_chunks_success(self, docs_agent, mock_rag_manager):
        """Тест получения релевантных чанков."""
        mock_chunks = [
            {
                "content": "Python is a programming language",
                "source": "docs/python.md",
                "chunk_id": "chunk_1",
                "similarity_score": 0.9
            }
        ]
        
        mock_rag_manager.get_relevant_chunks.return_value = mock_chunks
        
        result = await docs_agent.execute({
            "action": "get_relevant_chunks",
            "params": {
                "query": "Python programming",
                "limit": 3
            }
        })
        
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert "Python" in result["data"][0]["content"]
        
        mock_rag_manager.get_relevant_chunks.assert_called_once_with(
            "Python programming",
            limit=3
        )

    @pytest.mark.asyncio
    async def test_unknown_action(self, docs_agent):
        """Тест обработки неизвестного действия."""
        result = await docs_agent.execute({
            "action": "unknown_action",
            "params": {}
        })
        
        assert result["success"] is False
        assert "Неизвестное действие" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_input_success(self, docs_agent):
        """Тест валидации входных данных - успех."""
        assert await docs_agent.validate_input({
            "action": "search_documents",
            "params": {"query": "test"}
        })
        
        assert await docs_agent.validate_input({
            "action": "get_document_stats",
            "params": {}
        })

    @pytest.mark.asyncio
    async def test_validate_input_failure(self, docs_agent):
        """Тест валидации входных данных - ошибка."""
        assert not await docs_agent.validate_input({
            "action": "search_documents",
            "params": {}  # Отсутствует query
        })

    @pytest.mark.asyncio
    async def test_search_with_reranking(self, docs_agent, mock_rag_manager):
        """Тест поиска с включенным реранкингом."""
        mock_results = [
            {"content": "Test content", "source": "test.md", "score": 0.8}
        ]
        
        mock_rag_manager.search_documents.return_value = mock_results
        
        # Тест с реранкингом по умолчанию
        await docs_agent.execute({
            "action": "search_documents",
            "params": {"query": "test"}
        })
        
        mock_rag_manager.search_documents.assert_called_with(
            "test",
            limit=None,
            use_reranking=True
        )

    @pytest.mark.asyncio
    async def test_search_without_reranking(self, docs_agent, mock_rag_manager):
        """Тест поиска с выключенным реранкингом."""
        mock_results = [
            {"content": "Test content", "source": "test.md", "score": 0.8}
        ]
        
        mock_rag_manager.search_documents.return_value = mock_results
        
        await docs_agent.execute({
            "action": "search_documents",
            "params": {"query": "test", "use_reranking": False}
        })
        
        mock_rag_manager.search_documents.assert_called_with(
            "test",
            limit=None,
            use_reranking=False
        )

    @pytest.mark.asyncio
    async def test_search_with_limit(self, docs_agent, mock_rag_manager):
        """Тест поиска с ограничением количества результатов."""
        mock_results = [
            {"content": "Test content", "source": "test.md", "score": 0.8}
        ]
        
        mock_rag_manager.search_documents.return_value = mock_results
        
        await docs_agent.execute({
            "action": "search_documents",
            "params": {"query": "test", "limit": 10}
        })
        
        mock_rag_manager.search_documents.assert_called_with(
            "test",
            limit=10,
            use_reranking=True
        )

    @pytest.mark.asyncio
    async def test_rag_manager_none(self, mock_tool_manager):
        """Тест работы без RAGManager."""
        agent = DocsAgent(
            tool_manager=mock_tool_manager,
            rag_manager=None
        )
        
        result = await agent.execute({
            "action": "search_documents",
            "params": {"query": "test"}
        })
        
        assert result["success"] is False
        assert "RAG manager not available" in result["error"]

    @pytest.mark.asyncio
    async def test_format_search_results(self, docs_agent):
        """Тест форматирования результатов поиска."""
        mock_results = [
            {
                "content": "Test document content",
                "source": "docs/test.md",
                "score": 0.85,
                "metadata": {"file_type": "md"}
            }
        ]
        
        formatted = await docs_agent._format_search_results(mock_results)
        
        assert "Test document content" in formatted
        assert "docs/test.md" in formatted
        assert "0.85" in formatted

    @pytest.mark.asyncio
    async def test_get_document_by_source(self, docs_agent, mock_rag_manager):
        """Тест получения документа по источнику."""
        mock_document = {
            "content": "Full document content",
            "source": "docs/test.md",
            "metadata": {"file_type": "md", "size": 1024}
        }
        
        mock_rag_manager.get_document_by_source.return_value = mock_document
        
        result = await docs_agent.execute({
            "action": "get_document_by_source",
            "params": {"source": "docs/test.md"}
        })
        
        assert result["success"] is True
        assert result["data"]["source"] == "docs/test.md"
        assert "Full document content" in result["data"]["content"]
        
        mock_rag_manager.get_document_by_source.assert_called_once_with("docs/test.md")

    @pytest.mark.asyncio
    async def test_get_document_by_source_not_found(self, docs_agent, mock_rag_manager):
        """Тест получения несуществующего документа."""
        mock_rag_manager.get_document_by_source.return_value = None
        
        result = await docs_agent.execute({
            "action": "get_document_by_source",
            "params": {"source": "nonexistent.md"}
        })
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_agent_disabled(self, docs_agent):
        """Тест работы отключенного агента."""
        docs_agent.enabled = False
        
        result = await docs_agent.execute({
            "action": "search_documents",
            "params": {"query": "test"}
        })
        
        assert result["success"] is False
        assert "disabled" in result["error"].lower()

    def test_str_representation(self, docs_agent):
        """Тест строкового представления агента."""
        str_repr = str(docs_agent)
        assert "test_docs_agent" in str_repr
        assert "enabled" in str_repr.lower()

    @pytest.mark.asyncio
    async def test_context_handling(self, docs_agent, mock_rag_manager):
        """Тест обработки контекста в запросах."""
        mock_results = [
            {"content": "Test content", "source": "test.md", "score": 0.8}
        ]
        
        mock_rag_manager.search_documents.return_value = mock_results
        
        result = await docs_agent.execute({
            "action": "search_documents",
            "params": {"query": "test"},
            "context": {"user_id": "123", "session_id": "abc"}
        })
        
        assert result["success"] is True
        # Контекст должен быть обработан, но не влиять на результат в этом случае


if __name__ == "__main__":
    pytest.main([__file__])
