"""
Tavily Search Adapter

This module provides a wrapper around the Tavily search API for use in the research agent.
It handles API calls, error handling, and result processing.
"""

import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from tavily import TavilyClient
except ImportError:
    print("Tavily not available. Install with: pip install tavily-python")
    raise


@dataclass
class TavilySearchResult:
    """Structured result from Tavily search."""
    query: str
    results: List[Dict[str, Any]]
    response_time: float
    request_id: Optional[str] = None
    answer: Optional[str] = None
    follow_up_questions: Optional[List[str]] = None


@dataclass
class TavilySearchConfig:
    """Configuration for Tavily search."""
    api_key: Optional[str] = None
    search_depth: str = "basic"  # "basic" or "advanced"
    max_results: int = 10
    include_domains: Optional[List[str]] = None
    exclude_domains: Optional[List[str]] = None
    offline_mode: bool = False


class TavilySearchTool:
    """Tool for performing web searches using Tavily API."""
    
    def __init__(self, config: Optional[TavilySearchConfig] = None):
        """Initialize the Tavily search tool."""
        self.config = config or TavilySearchConfig()
        
        # Get API key from config or environment
        if not self.config.api_key:
            self.config.api_key = os.getenv("TAVILY_API_KEY")
        
        if not self.config.api_key and not self.config.offline_mode:
            raise ValueError("TAVILY_API_KEY environment variable is required")
        
        # Initialize client if not in offline mode
        self.client = None
        if not self.config.offline_mode and self.config.api_key:
            self.client = TavilyClient(api_key=self.config.api_key)
    
    def search(self, query: str, **kwargs) -> TavilySearchResult:
        """
        Perform a web search using Tavily.
        
        Args:
            query: Search query string
            **kwargs: Additional search parameters
            
        Returns:
            TavilySearchResult with search results
        """
        if self.config.offline_mode:
            return self._mock_search(query, **kwargs)
        
        start_time = time.time()
        
        try:
            # Prepare search parameters
            search_params = {
                "query": query,
                "search_depth": kwargs.get("search_depth", self.config.search_depth),
                "max_results": kwargs.get("max_results", self.config.max_results),
            }
            
            # Add domain filters if specified
            if kwargs.get("include_domains") or self.config.include_domains:
                search_params["include_domains"] = kwargs.get("include_domains", self.config.include_domains)
            
            if kwargs.get("exclude_domains") or self.config.exclude_domains:
                search_params["exclude_domains"] = kwargs.get("exclude_domains", self.config.exclude_domains)
            
            # Perform search
            response = self.client.search(**search_params)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Parse response
            result = TavilySearchResult(
                query=response.get("query", query),
                results=response.get("results", []),
                response_time=response_time,
                request_id=response.get("request_id"),
                answer=response.get("answer"),
                follow_up_questions=response.get("follow_up_questions")
            )
            
            return result
            
        except Exception as e:
            # Return error result
            response_time = time.time() - start_time
            return TavilySearchResult(
                query=query,
                results=[],
                response_time=response_time,
                request_id=None
            )
    
    def _mock_search(self, query: str, **kwargs) -> TavilySearchResult:
        """Mock search for offline mode."""
        # Simulate some processing time
        time.sleep(0.1)
        
        # Return mock results based on query
        mock_results = []
        
        if "messi" in query.lower():
            mock_results = [
                {
                    "url": "https://example.com/messi-bio",
                    "title": "Lionel Messi - Football Legend",
                    "content": "Lionel Messi is an Argentine professional footballer who plays as a forward for Inter Miami CF and the Argentina national team.",
                    "score": 0.95,
                    "raw_content": None
                }
            ]
        elif "ai" in query.lower() or "prediction" in query.lower():
            mock_results = [
                {
                    "url": "https://example.com/ai-prediction-markets",
                    "title": "AI Prediction Markets - The Future of Forecasting",
                    "content": "Artificial intelligence is revolutionizing prediction markets with advanced algorithms and machine learning models.",
                    "score": 0.88,
                    "raw_content": None
                }
            ]
        else:
            mock_results = [
                {
                    "url": "https://example.com/generic-result",
                    "title": f"Search Results for: {query}",
                    "content": f"This is a mock search result for the query: {query}",
                    "score": 0.75,
                    "raw_content": None
                }
            ]
        
        return TavilySearchResult(
            query=query,
            results=mock_results,
            response_time=0.1,
            request_id="mock-request-id"
        )
    
    def search_multiple(self, queries: List[str], **kwargs) -> List[TavilySearchResult]:
        """
        Perform multiple searches in sequence.
        
        Args:
            queries: List of search queries
            **kwargs: Additional search parameters
            
        Returns:
            List of TavilySearchResult objects
        """
        results = []
        for query in queries:
            result = self.search(query, **kwargs)
            results.append(result)
        return results
    
    def get_search_summary(self, result: TavilySearchResult) -> Dict[str, Any]:
        """
        Get a summary of search results.
        
        Args:
            result: TavilySearchResult object
            
        Returns:
            Dictionary with summary information
        """
        return {
            "query": result.query,
            "results_count": len(result.results),
            "response_time": result.response_time,
            "request_id": result.request_id,
            "has_answer": result.answer is not None,
            "follow_up_questions_count": len(result.follow_up_questions) if result.follow_up_questions else 0,
            "top_score": max([r.get("score", 0) for r in result.results]) if result.results else 0,
            "domains": list(set([r.get("url", "").split("/")[2] for r in result.results if r.get("url")]))
        }
    
    def extract_key_information(self, result: TavilySearchResult, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Extract key information from search results.
        
        Args:
            result: TavilySearchResult object
            max_results: Maximum number of results to process
            
        Returns:
            List of dictionaries with extracted information
        """
        key_info = []
        
        for i, search_result in enumerate(result.results[:max_results]):
            info = {
                "rank": i + 1,
                "title": search_result.get("title", ""),
                "url": search_result.get("url", ""),
                "score": search_result.get("score", 0),
                "content": search_result.get("content", ""),
                "domain": search_result.get("url", "").split("/")[2] if search_result.get("url") else "",
                "extracted_at": datetime.utcnow().isoformat()
            }
            key_info.append(info)
        
        return key_info
