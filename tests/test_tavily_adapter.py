"""
Unit tests for Tavily Search Adapter.

This module contains comprehensive tests for the TavilySearchTool class.
"""

import pytest
import os
from unittest.mock import Mock, patch
from datetime import datetime

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from adapters.tavily import TavilySearchTool, TavilySearchConfig, TavilySearchResult


class TestTavilySearchConfig:
    """Test TavilySearchConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TavilySearchConfig()
        
        assert config.api_key is None
        assert config.search_depth == "basic"
        assert config.max_results == 10
        assert config.include_domains is None
        assert config.exclude_domains is None
        assert config.offline_mode is False
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = TavilySearchConfig(
            api_key="test-key",
            search_depth="advanced",
            max_results=5,
            include_domains=["example.com"],
            exclude_domains=["wikipedia.org"],
            offline_mode=True
        )
        
        assert config.api_key == "test-key"
        assert config.search_depth == "advanced"
        assert config.max_results == 5
        assert config.include_domains == ["example.com"]
        assert config.exclude_domains == ["wikipedia.org"]
        assert config.offline_mode is True


class TestTavilySearchResult:
    """Test TavilySearchResult class."""
    
    def test_search_result_creation(self):
        """Test creating a search result."""
        result = TavilySearchResult(
            query="test query",
            results=[{"title": "Test Result", "url": "https://example.com"}],
            response_time=1.5,
            request_id="test-id",
            answer="Test answer",
            follow_up_questions=["What is this?"]
        )
        
        assert result.query == "test query"
        assert len(result.results) == 1
        assert result.response_time == 1.5
        assert result.request_id == "test-id"
        assert result.answer == "Test answer"
        assert result.follow_up_questions == ["What is this?"]


class TestTavilySearchTool:
    """Test TavilySearchTool class."""
    
    def test_initialization_with_api_key(self):
        """Test initialization with API key."""
        config = TavilySearchConfig(api_key="test-key")
        
        with patch('adapters.tavily.TavilyClient') as mock_client:
            tool = TavilySearchTool(config)
            
            assert tool.config.api_key == "test-key"
            mock_client.assert_called_once_with(api_key="test-key")
    
    def test_initialization_with_env_var(self):
        """Test initialization with environment variable."""
        with patch.dict(os.environ, {'TAVILY_API_KEY': 'env-key'}):
            with patch('adapters.tavily.TavilyClient') as mock_client:
                tool = TavilySearchTool()
                
                assert tool.config.api_key == "env-key"
                mock_client.assert_called_once_with(api_key="env-key")
    
    def test_initialization_offline_mode(self):
        """Test initialization in offline mode."""
        config = TavilySearchConfig(offline_mode=True)
        
        with patch('adapters.tavily.TavilyClient') as mock_client:
            tool = TavilySearchTool(config)
            
            assert tool.config.offline_mode is True
            assert tool.client is None
            mock_client.assert_not_called()
    
    def test_initialization_no_api_key(self):
        """Test initialization without API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="TAVILY_API_KEY environment variable is required"):
                TavilySearchTool()
    
    def test_mock_search(self):
        """Test mock search functionality."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        result = tool.search("test query")
        
        assert isinstance(result, TavilySearchResult)
        assert result.query == "test query"
        assert len(result.results) > 0
        assert result.response_time > 0
    
    def test_mock_search_messi(self):
        """Test mock search with Messi query."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        result = tool.search("Who is Leo Messi?")
        
        assert result.query == "Who is Leo Messi?"
        assert len(result.results) == 1
        assert "messi" in result.results[0]["title"].lower()
    
    def test_mock_search_ai(self):
        """Test mock search with AI query."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        result = tool.search("What is AI?")
        
        assert result.query == "What is AI?"
        assert len(result.results) == 1
        assert "ai" in result.results[0]["title"].lower()
    
    @patch('adapters.tavily.TavilyClient')
    def test_real_search(self, mock_client_class):
        """Test real search functionality with mocked client."""
        # Mock the client and its search method
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = {
            "query": "test query",
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "Test content",
                    "score": 0.9
                }
            ],
            "response_time": 1.5,
            "request_id": "test-id"
        }
        mock_client.search.return_value = mock_response
        
        config = TavilySearchConfig(api_key="test-key")
        tool = TavilySearchTool(config)
        
        result = tool.search("test query")
        
        assert isinstance(result, TavilySearchResult)
        assert result.query == "test query"
        assert len(result.results) == 1
        assert result.results[0]["title"] == "Test Result"
        assert result.request_id == "test-id"
        
        # Verify the client was called correctly
        mock_client.search.assert_called_once_with(
            query="test query",
            search_depth="basic",
            max_results=10
        )
    
    @patch('adapters.tavily.TavilyClient')
    def test_search_with_custom_params(self, mock_client_class):
        """Test search with custom parameters."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {"query": "test", "results": [], "response_time": 1.0}
        
        config = TavilySearchConfig(
            search_depth="advanced",
            max_results=5,
            include_domains=["example.com"],
            exclude_domains=["wikipedia.org"]
        )
        tool = TavilySearchTool(config)
        
        tool.search("test query")
        
        # Verify the client was called with custom parameters
        mock_client.search.assert_called_once_with(
            query="test query",
            search_depth="advanced",
            max_results=5,
            include_domains=["example.com"],
            exclude_domains=["wikipedia.org"]
        )
    
    def test_search_multiple(self):
        """Test multiple searches functionality."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        queries = ["query 1", "query 2", "query 3"]
        results = tool.search_multiple(queries)
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.query == queries[i]
    
    def test_get_search_summary(self):
        """Test search summary functionality."""
        result = TavilySearchResult(
            query="test query",
            results=[
                {"url": "https://example.com", "score": 0.9},
                {"url": "https://test.com", "score": 0.8}
            ],
            response_time=1.5,
            request_id="test-id",
            answer="Test answer",
            follow_up_questions=["Question 1", "Question 2"]
        )
        
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        summary = tool.get_search_summary(result)
        
        assert summary["query"] == "test query"
        assert summary["results_count"] == 2
        assert summary["response_time"] == 1.5
        assert summary["request_id"] == "test-id"
        assert summary["has_answer"] is True
        assert summary["follow_up_questions_count"] == 2
        assert summary["top_score"] == 0.9
        assert "example.com" in summary["domains"]
        assert "test.com" in summary["domains"]
    
    def test_extract_key_information(self):
        """Test key information extraction."""
        result = TavilySearchResult(
            query="test query",
            results=[
                {
                    "title": "Test Result 1",
                    "url": "https://example.com/page1",
                    "content": "Test content 1",
                    "score": 0.9
                },
                {
                    "title": "Test Result 2",
                    "url": "https://test.com/page2",
                    "content": "Test content 2",
                    "score": 0.8
                }
            ],
            response_time=1.5
        )
        
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        key_info = tool.extract_key_information(result, max_results=2)
        
        assert len(key_info) == 2
        
        # Check first result
        assert key_info[0]["rank"] == 1
        assert key_info[0]["title"] == "Test Result 1"
        assert key_info[0]["url"] == "https://example.com/page1"
        assert key_info[0]["score"] == 0.9
        assert key_info[0]["domain"] == "example.com"
        assert "extracted_at" in key_info[0]
        
        # Check second result
        assert key_info[1]["rank"] == 2
        assert key_info[1]["title"] == "Test Result 2"
        assert key_info[1]["domain"] == "test.com"
    
    def test_extract_key_information_max_results(self):
        """Test key information extraction with max_results limit."""
        result = TavilySearchResult(
            query="test query",
            results=[
                {"title": f"Result {i}", "url": f"https://example.com/{i}", "score": 0.9}
                for i in range(5)
            ],
            response_time=1.5
        )
        
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        key_info = tool.extract_key_information(result, max_results=3)
        
        assert len(key_info) == 3
        assert key_info[0]["rank"] == 1
        assert key_info[2]["rank"] == 3


class TestTavilyIntegration:
    """Integration tests for Tavily adapter."""
    
    @pytest.mark.skipif(
        not os.getenv("TAVILY_API_KEY"),
        reason="TAVILY_API_KEY not set - skipping integration test"
    )
    def test_real_api_integration(self):
        """Test real API integration (requires TAVILY_API_KEY)."""
        config = TavilySearchConfig()
        tool = TavilySearchTool(config)
        
        result = tool.search("What is artificial intelligence?")
        
        assert isinstance(result, TavilySearchResult)
        assert result.query == "What is artificial intelligence?"
        assert len(result.results) > 0
        assert result.response_time > 0
        
        # Check that results have expected structure
        for search_result in result.results:
            assert "title" in search_result
            assert "url" in search_result
            assert "content" in search_result
            assert "score" in search_result
