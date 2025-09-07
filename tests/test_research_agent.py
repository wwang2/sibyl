"""
Unit tests for Web Research Agent.

This module contains tests for the WebResearchAgent class.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

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
    """Test WebResearchAgent class."""
    
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
    
    def test_initialization_online_mode(self, mock_store):
        """Test initialization in online mode."""
        with patch('agents.research.TavilySearchTool') as mock_tavily:
            agent = WebResearchAgent(mock_store, offline_mode=False)
            
            assert agent.store == mock_store
            assert agent.offline_mode is False
            mock_tavily.assert_called_once()
    
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
    
    def test_generate_research_queries_offline(self, research_agent):
        """Test research query generation in offline mode."""
        event_description = "Will Bitcoin reach $100k?"
        
        queries = research_agent._mock_generate_queries(event_description)
        
        assert isinstance(queries, list)
        assert len(queries) > 0
        assert all(isinstance(q, str) for q in queries)
        assert all(len(q) > 0 for q in queries)
    
    @pytest.mark.asyncio
    async def test_build_evidence_chain(self, research_agent):
        """Test evidence chain building."""
        event_id = "test_event_003"
        queries = ["query 1", "query 2", "query 3"]
        
        evidence_chain = await research_agent._build_evidence_chain(event_id, queries)
        
        assert isinstance(evidence_chain, EvidenceChain)
        assert evidence_chain.event_id == event_id
        assert len(evidence_chain.evidence_items) > 0
        assert all(isinstance(e, Evidence) for e in evidence_chain.evidence_items)
    
    def test_classify_source_type(self, research_agent):
        """Test source type classification."""
        # Test government source
        gov_result = {"url": "https://www.gov.uk/ai-policy", "title": "AI Policy"}
        assert research_agent._classify_source_type(gov_result) == EvidenceType.OFFICIAL_STATEMENT
        
        # Test news source
        news_result = {"url": "https://www.reuters.com/ai-news", "title": "AI News"}
        assert research_agent._classify_source_type(news_result) == EvidenceType.NEWS_ARTICLE
        
        # Test social media
        social_result = {"url": "https://twitter.com/ai-update", "title": "AI Update"}
        assert research_agent._classify_source_type(social_result) == EvidenceType.SOCIAL_MEDIA
        
        # Test default
        default_result = {"url": "https://example.com", "title": "Example"}
        assert research_agent._classify_source_type(default_result) == EvidenceType.NEWS_ARTICLE
    
    def test_assess_reliability(self, research_agent):
        """Test reliability assessment."""
        # Test high reliability
        high_result = {"url": "https://www.reuters.com/news", "score": 0.8}
        assert research_agent._assess_reliability(high_result) == EvidenceReliability.HIGH
        
        # Test medium reliability
        medium_result = {"url": "https://example.com/news", "score": 0.8}
        assert research_agent._assess_reliability(medium_result) == EvidenceReliability.MEDIUM
        
        # Test low reliability
        low_result = {"url": "https://example.com/news", "score": 0.5}
        assert research_agent._assess_reliability(low_result) == EvidenceReliability.LOW
    
    def test_assess_credibility(self, research_agent):
        """Test credibility assessment."""
        # Test high credibility source
        high_result = {"url": "https://www.reuters.com/news", "score": 0.7}
        credibility = research_agent._assess_credibility(high_result)
        assert credibility > 0.7  # Should be boosted
        
        # Test regular source
        regular_result = {"url": "https://example.com/news", "score": 0.7}
        credibility = research_agent._assess_credibility(regular_result)
        assert credibility == 0.7  # Should remain the same
    
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
        for i in range(3):
            source = EvidenceSource(
                url=f"https://example.com/{i}",
                title=f"Test Source {i}",
                domain="example.com",
                content="Test content",
                source_type=EvidenceType.NEWS_ARTICLE,
                reliability=EvidenceReliability.MEDIUM,
                relevance_score=0.8,
                credibility_score=0.7
            )
            
            evidence = Evidence(
                id=f"evidence_{i}",
                source=source,
                extracted_fact=f"Test fact {i}",
                supporting_claim=f"Test claim {i}",
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
    
    def test_generate_reasoning(self, research_agent):
        """Test reasoning generation."""
        # Create evidence chain with some evidence
        evidence_chain = EvidenceChain(
            event_id="test",
            research_query="test query"
        )
        
        # Add evidence with different reliability levels
        for reliability in [EvidenceReliability.HIGH, EvidenceReliability.MEDIUM]:
            source = EvidenceSource(
                url="https://example.com",
                title="Test Source",
                domain="example.com",
                content="Test content",
                source_type=EvidenceType.NEWS_ARTICLE,
                reliability=reliability,
                relevance_score=0.8,
                credibility_score=0.7
            )
            
            evidence = Evidence(
                id="test_evidence",
                source=source,
                extracted_fact="Test fact",
                supporting_claim="Test claim",
                evidence_type=EvidenceType.NEWS_ARTICLE,
                reliability=reliability,
                relevance_to_event=0.8,
                confidence_in_fact=0.7
            )
            
            evidence_chain.add_evidence(evidence)
        
        reasoning = research_agent._generate_reasoning(evidence_chain, 0.75)
        
        assert isinstance(reasoning, str)
        assert len(reasoning) > 0
        assert "evidence" in reasoning.lower()
        assert "strength" in reasoning.lower()
    
    def test_extract_key_factors(self, research_agent):
        """Test key factor extraction."""
        # Create evidence chain with different evidence types
        evidence_chain = EvidenceChain(
            event_id="test",
            research_query="test query"
        )
        
        evidence_types = [
            EvidenceType.NEWS_ARTICLE,
            EvidenceType.OFFICIAL_STATEMENT,
            EvidenceType.EXPERT_OPINION
        ]
        
        for evidence_type in evidence_types:
            source = EvidenceSource(
                url="https://example.com",
                title="Test Source",
                domain="example.com",
                content="Test content",
                source_type=evidence_type,
                reliability=EvidenceReliability.MEDIUM,
                relevance_score=0.8,
                credibility_score=0.7
            )
            
            evidence = Evidence(
                id="test_evidence",
                source=source,
                extracted_fact="Test fact",
                supporting_claim="Test claim",
                evidence_type=evidence_type,
                reliability=EvidenceReliability.MEDIUM,
                relevance_to_event=0.8,
                confidence_in_fact=0.7
            )
            
            evidence_chain.add_evidence(evidence)
        
        factors = research_agent._extract_key_factors(evidence_chain)
        
        assert isinstance(factors, list)
        assert len(factors) > 0
        assert all(isinstance(factor, str) for factor in factors)
    
    def test_identify_risks(self, research_agent):
        """Test risk identification."""
        evidence_chain = EvidenceChain(
            event_id="test",
            research_query="test query"
        )
        
        risks = research_agent._identify_risks(evidence_chain)
        
        assert isinstance(risks, list)
        assert len(risks) > 0
        assert all(isinstance(risk, str) for risk in risks)
        assert any("outdated" in risk.lower() for risk in risks)
    
    def test_generate_alternatives(self, research_agent):
        """Test alternative scenario generation."""
        event_description = "Will AI achieve AGI by 2030?"
        
        alternatives = research_agent._generate_alternatives(event_description)
        
        assert isinstance(alternatives, list)
        assert len(alternatives) > 0
        assert all(isinstance(alt, str) for alt in alternatives)
        assert all("alternative" in alt.lower() for alt in alternatives)
    
    def test_get_research_summary_no_session(self, research_agent):
        """Test getting research summary when no session exists."""
        summary = research_agent.get_research_summary()
        assert summary is None
    
    def test_get_research_summary_with_session(self, research_agent):
        """Test getting research summary when session exists."""
        # Create a mock session
        research_agent.current_session = ResearchSession(
            event_id="test_event",
            event_description="Test description"
        )
        
        summary = research_agent.get_research_summary()
        
        assert summary is not None
        assert summary["event_id"] == "test_event"
        assert summary["event_description"] == "Test description"


class TestResearchModels:
    """Test research model classes."""
    
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
    
    def test_evidence_creation(self):
        """Test Evidence creation."""
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
        
        assert evidence.id == "test_evidence"
        assert evidence.source == source
        assert evidence.extracted_fact == "Test fact"
        assert evidence.supporting_claim == "Test claim"
        assert evidence.evidence_type == EvidenceType.NEWS_ARTICLE
        assert evidence.reliability == EvidenceReliability.HIGH
        assert evidence.relevance_to_event == 0.8
        assert evidence.confidence_in_fact == 0.9
    
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
    
    def test_evidence_chain_calculations(self):
        """Test EvidenceChain calculation methods."""
        chain = EvidenceChain(
            event_id="test_event",
            research_query="test query"
        )
        
        # Test empty chain
        assert chain.calculate_evidence_strength() == 0.0
        assert len(chain.get_high_reliability_evidence()) == 0
        assert len(chain.get_contradicting_evidence()) == 0
        
        # Add high reliability evidence
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
        
        assert chain.calculate_evidence_strength() > 0
        assert len(chain.get_high_reliability_evidence()) == 1
