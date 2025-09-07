"""
Unit tests for Tavily Search Adapter.

This module contains essential tests for the TavilySearchTool class, focusing on mock functionality.
"""

import pytest
import os
from unittest.mock import Mock, patch

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from adapters.tavily import TavilySearchTool, TavilySearchConfig, TavilySearchResult


class TestTavilySearchTool:
    """Test TavilySearchTool class with mock functionality."""
    
    def test_initialization_offline_mode(self):
        """Test initialization in offline mode."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        assert tool.config.offline_mode is True
        assert tool.client is None
    
    def test_mock_search_basic(self):
        """Test basic mock search functionality."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        result = tool.search("test query")
        
        assert isinstance(result, TavilySearchResult)
        assert result.query == "test query"
        assert len(result.results) > 0
        assert result.response_time > 0
    
    def test_mock_search_ai_query(self):
        """Test mock search with AI-related query."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        result = tool.search("What is AI?")
        
        assert result.query == "What is AI?"
        assert len(result.results) == 1
        assert "ai" in result.results[0]["title"].lower()
        assert "prediction" in result.results[0]["title"].lower()
    
    def test_mock_search_prediction_markets(self):
        """Test mock search with prediction markets query."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        result = tool.search("How do prediction markets work?")
        
        assert result.query == "How do prediction markets work?"
        assert len(result.results) == 1
        assert "prediction" in result.results[0]["title"].lower()
    
    def test_search_multiple_queries(self):
        """Test multiple searches functionality."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        queries = ["AI developments", "prediction markets", "machine learning"]
        results = tool.search_multiple(queries)
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.query == queries[i]
            assert len(result.results) > 0
    
    def test_extract_key_information(self):
        """Test key information extraction from mock results."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        result = tool.search("test query")
        key_info = tool.extract_key_information(result, max_results=1)
        
        assert len(key_info) == 1
        assert key_info[0]["rank"] == 1
        assert "title" in key_info[0]
        assert "url" in key_info[0]
        assert "score" in key_info[0]
        assert "domain" in key_info[0]
        assert "extracted_at" in key_info[0]
    
    def test_get_search_summary(self):
        """Test search summary functionality."""
        config = TavilySearchConfig(offline_mode=True)
        tool = TavilySearchTool(config)
        
        result = tool.search("test query")
        summary = tool.get_search_summary(result)
        
        assert summary["query"] == "test query"
        assert summary["results_count"] > 0
        assert summary["response_time"] > 0
        assert "domains" in summary
        assert "top_score" in summary
