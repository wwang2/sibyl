"""
Unit tests for Web Research Agent.

This module contains minimal tests for the WebResearchAgent class, focusing on core functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from agents.research import WebResearchAgent
from core.research_models import (
    EvidenceType, EvidenceReliability, PredictionConfidence,
    EvidenceSource, Evidence, EvidenceChain, Prediction, ResearchSession
)
from core.store import Store


class TestWebResearchAgent:
    """Test WebResearchAgent class with minimal essential tests."""
    
    @pytest.fixture
    def mock_store(self):
        """Create a mock store."""
        return Mock(spec=Store)
    
    @pytest.fixture
    def research_agent(self, mock_store):
        """Create a research agent in offline mode."""
        return WebResearchAgent(mock_store, offline_mode=True)
    
    def test_initialization_offline_mode(self, mock_store):
        """Test initialization in offline mode."""
        agent = WebResearchAgent(mock_store, offline_mode=True)
        
        assert agent.store == mock_store
        assert agent.offline_mode is True
        assert agent.search_tool is not None
        assert agent.current_session is None
    
    @pytest.mark.asyncio
    async def test_research_event_basic(self, research_agent):
        """Test basic research event functionality."""
        event_id = "test_event_001"
        event_description = "Will AI achieve AGI by 2030?"
        
        prediction = await research_agent.research_event(event_id, event_description)
        
        assert isinstance(prediction, Prediction)
        assert prediction.event_id == event_id
        assert prediction.prediction is not None
        assert prediction.confidence is not None
        assert prediction.confidence_score > 0
        assert prediction.reasoning is not None
        assert isinstance(prediction.evidence_chain, EvidenceChain)
        assert len(prediction.evidence_chain.evidence_items) > 0
    
    @pytest.mark.asyncio
    async def test_research_event_creates_session(self, research_agent):
        """Test that research event creates a research session."""
        event_id = "test_event_002"
        event_description = "Test event description"
        
        # Initially no session
        assert research_agent.current_session is None
        
        prediction = await research_agent.research_event(event_id, event_description)
        
        # Session should be created
        assert research_agent.current_session is not None
        assert isinstance(research_agent.current_session, ResearchSession)
        assert research_agent.current_session.event_id == event_id
        assert research_agent.current_session.event_description == event_description
        assert research_agent.current_session.final_prediction == prediction
    
    def test_mock_extract_facts(self, research_agent):
        """Test mock fact extraction."""
        result = {
            "title": "AI News Article",
            "content": "This is about artificial intelligence developments."
        }
        query = "What is AI?"
        
        fact, claim = research_agent._mock_extract_facts(result, query)
        
        assert isinstance(fact, str)
        assert isinstance(claim, str)
        assert len(fact) > 0
        assert len(claim) > 0
        assert "AI" in fact or "artificial intelligence" in fact.lower()
    
    def test_mock_analyze_and_predict(self, research_agent):
        """Test mock analysis and prediction."""
        event_id = "test_event_004"
        event_description = "Test event"
        
        # Create a mock evidence chain
        evidence_chain = EvidenceChain(
            event_id=event_id,
            research_query="test query"
        )
        
        # Add some mock evidence
        source = EvidenceSource(
            url="https://example.com/test",
            title="Test Source",
            domain="example.com",
            content="Test content",
            source_type=EvidenceType.NEWS_ARTICLE,
            reliability=EvidenceReliability.MEDIUM,
            relevance_score=0.8,
            credibility_score=0.7
        )
        
        evidence = Evidence(
            id="test_evidence",
            source=source,
            extracted_fact="Test fact",
            supporting_claim="Test claim",
            evidence_type=EvidenceType.NEWS_ARTICLE,
            reliability=EvidenceReliability.MEDIUM,
            relevance_to_event=0.8,
            confidence_in_fact=0.7
        )
        
        evidence_chain.add_evidence(evidence)
        
        prediction = research_agent._mock_analyze_and_predict(
            event_id, event_description, evidence_chain
        )
        
        assert isinstance(prediction, Prediction)
        assert prediction.event_id == event_id
        assert prediction.prediction is not None
        assert prediction.confidence is not None
        assert 0 <= prediction.confidence_score <= 1
        assert prediction.reasoning is not None
        assert prediction.evidence_chain == evidence_chain
        assert len(prediction.key_factors) > 0
        assert len(prediction.risks_and_uncertainties) > 0
        assert len(prediction.alternative_scenarios) > 0


class TestResearchModels:
    """Test research model classes with minimal essential tests."""
    
    def test_evidence_source_creation(self):
        """Test EvidenceSource creation."""
        source = EvidenceSource(
            url="https://example.com",
            title="Test Title",
            domain="example.com",
            content="Test content",
            source_type=EvidenceType.NEWS_ARTICLE,
            reliability=EvidenceReliability.HIGH,
            relevance_score=0.8,
            credibility_score=0.9
        )
        
        assert source.url == "https://example.com"
        assert source.title == "Test Title"
        assert source.domain == "example.com"
        assert source.content == "Test content"
        assert source.source_type == EvidenceType.NEWS_ARTICLE
        assert source.reliability == EvidenceReliability.HIGH
        assert source.relevance_score == 0.8
        assert source.credibility_score == 0.9
    
    def test_evidence_chain_operations(self):
        """Test EvidenceChain operations."""
        chain = EvidenceChain(
            event_id="test_event",
            research_query="test query"
        )
        
        assert len(chain.evidence_items) == 0
        
        # Add evidence
        source = EvidenceSource(
            url="https://example.com",
            title="Test Title",
            domain="example.com",
            content="Test content"
        )
        
        evidence = Evidence(
            id="test_evidence",
            source=source,
            extracted_fact="Test fact",
            supporting_claim="Test claim",
            evidence_type=EvidenceType.NEWS_ARTICLE,
            reliability=EvidenceReliability.HIGH,
            relevance_to_event=0.8,
            confidence_in_fact=0.9
        )
        
        chain.add_evidence(evidence)
        
        assert len(chain.evidence_items) == 1
        assert chain.evidence_items[0] == evidence
        assert chain.calculate_evidence_strength() > 0
