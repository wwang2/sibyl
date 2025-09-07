"""Unit tests for the core mine→judge workflow."""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.store import Store
from app.core.models import RawItem, EventProposal, ProposalStatus
from app.core.types import CreateEventProposalRequest
from app.workflows.market_mining import MarketMiningWorkflow, MiningConfig
from app.agents.judge import EventJudgeAgent, JudgmentResult


class TestCoreWorkflow:
    """Test the core mine→judge workflow components."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_url = f"sqlite:///{db_path}"
            store = Store(db_url)
            store.create_all()
            yield store
    
    @pytest.fixture
    def sample_raw_item(self, temp_db):
        """Create a sample raw item for testing."""
        raw_item = RawItem(
            source_id="test_source",
            external_id="test_market_123",
            raw_url="https://example.com/market/123",
            title="Will Bitcoin reach $100,000 by end of 2024?",
            content_text="A prediction market about Bitcoin price",
            raw_content_hash="test_hash_123",
            meta_json={
                "platform": "kalshi",
                "market_type": "prediction_market",
                "category": "crypto"
            }
        )
        return temp_db.add_raw_item(raw_item)
    
    @pytest.fixture
    def sample_event_proposal(self, temp_db, sample_raw_item):
        """Create a sample event proposal for testing."""
        request = CreateEventProposalRequest(
            raw_item_id=sample_raw_item.id,
            event_key="bitcoin_100k_2024",
            title="Will Bitcoin reach $100,000 by end of 2024?",
            description="A prediction market about Bitcoin price reaching $100,000 by end of 2024",
            proposed_by="test_agent",
            confidence_score=0.8,
            meta_json={"source": "test"}
        )
        return temp_db.create_event_proposal(request)


class TestMarketMiningWorkflow(TestCoreWorkflow):
    """Test the market mining workflow."""
    
    @pytest.mark.asyncio
    async def test_mining_workflow_initialization(self, temp_db):
        """Test that the mining workflow initializes correctly."""
        config = MiningConfig(
            platforms=["kalshi", "polymarket"],
            categories=["Politics", "Economics"],
            limit_per_category=10,
            create_proposals=True,
            database_url=temp_db.engine.url
        )
        
        workflow = MarketMiningWorkflow(config)
        assert workflow.config == config
        assert workflow.store is not None
        assert workflow.kalshi_adapter is None
        assert workflow.polymarket_adapter is None
    
    @pytest.mark.asyncio
    async def test_mining_workflow_initialization_with_adapters(self, temp_db):
        """Test that adapters are initialized when platforms are specified."""
        config = MiningConfig(
            platforms=["kalshi", "polymarket"],
            database_url=temp_db.engine.url
        )
        
        workflow = MarketMiningWorkflow(config)
        
        # Mock the adapters
        with patch('app.workflows.market_mining.KalshiAdapter') as mock_kalshi, \
             patch('app.workflows.market_mining.PolymarketAdapter') as mock_polymarket:
            
            await workflow.initialize()
            
            # Verify adapters were created
            mock_kalshi.assert_called_once()
            mock_polymarket.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_event_proposals(self, temp_db):
        """Test creating event proposals from raw items."""
        # Create a test raw item
        raw_item = RawItem(
            source_id="test_source",
            external_id="test_market_456",
            raw_url="https://example.com/market/456",
            title="Will the S&P 500 reach 5000 by end of 2024?",
            content_text="A prediction market about S&P 500 index",
            raw_content_hash="test_hash_456",
            meta_json={
                "platform": "polymarket",
                "market_type": "prediction_market",
                "category": "economics"
            }
        )
        saved_raw_item = temp_db.add_raw_item(raw_item)
        
        config = MiningConfig(
            platforms=["polymarket"],
            create_proposals=True,
            database_url=temp_db.engine.url
        )
        
        workflow = MarketMiningWorkflow(config)
        
        # Test creating event proposals
        proposals_created = await workflow._create_event_proposals()
        
        # Verify proposal was created
        assert proposals_created > 0
        
        # Verify the proposal exists in database
        with temp_db.get_session() as session:
            proposals = session.query(EventProposal).all()
            assert len(proposals) > 0
            
            proposal = proposals[0]
            assert proposal.raw_item_id == saved_raw_item.id
            assert proposal.title == raw_item.title
            assert proposal.proposed_by == "market_mining_workflow"


class TestEventJudgeAgent(TestCoreWorkflow):
    """Test the event judge agent."""
    
    def test_judge_agent_initialization(self, temp_db):
        """Test that the judge agent initializes correctly."""
        agent = EventJudgeAgent(
            store=temp_db,
            model_name="test-model",
            approval_threshold=0.7,
            offline_mode=True
        )
        
        assert agent.store == temp_db
        assert agent.model_name == "test-model"
        assert agent.approval_threshold == 0.7
        assert agent.offline_mode is True
    
    def test_extract_temporal_info(self, temp_db, sample_event_proposal):
        """Test temporal information extraction from proposals."""
        agent = EventJudgeAgent(store=temp_db, offline_mode=True)
        
        temporal_info = agent._extract_temporal_info(sample_event_proposal)
        
        assert "extracted_dates" in temporal_info
        assert "has_relative_time" in temporal_info
        assert "is_past_event" in temporal_info
        assert "temporal_confidence" in temporal_info
        assert "current_time" in temporal_info
    
    def test_mock_judgment(self, temp_db, sample_event_proposal):
        """Test mock judgment functionality."""
        agent = EventJudgeAgent(store=temp_db, offline_mode=True)
        
        judgment = agent._mock_judgment(sample_event_proposal)
        
        assert judgment.proposal_id == sample_event_proposal.id
        assert judgment.result in [JudgmentResult.APPROVED, JudgmentResult.REJECTED, JudgmentResult.NEEDS_REVISION]
        assert 0.0 <= judgment.answerability_score <= 1.0
        assert 0.0 <= judgment.significance_score <= 1.0
        assert 0.0 <= judgment.frequency_score <= 1.0
        assert 0.0 <= judgment.temporal_score <= 1.0
        assert 0.0 <= judgment.overall_score <= 1.0
        assert isinstance(judgment.reasoning, str)
        assert isinstance(judgment.suggestions, list)
        # Consolidated tagging
        assert isinstance(judgment.primary_tag, str)
        assert isinstance(judgment.secondary_tags, list)
        assert 0.0 <= judgment.tag_confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_judge_proposal_offline(self, temp_db, sample_event_proposal):
        """Test judging a single proposal in offline mode."""
        agent = EventJudgeAgent(store=temp_db, offline_mode=True)
        
        judgment = await agent.judge_proposal(sample_event_proposal)
        
        assert judgment.proposal_id == sample_event_proposal.id
        assert judgment.result in [JudgmentResult.APPROVED, JudgmentResult.REJECTED, JudgmentResult.NEEDS_REVISION]
        assert isinstance(judgment.reasoning, str)
    
    @pytest.mark.asyncio
    async def test_judge_proposals_batch(self, temp_db, sample_event_proposal):
        """Test judging multiple proposals."""
        agent = EventJudgeAgent(store=temp_db, offline_mode=True)
        
        judgments = await agent.judge_proposals([sample_event_proposal], max_proposals=1)
        
        assert len(judgments) == 1
        assert judgments[0].proposal_id == sample_event_proposal.id
    
    @pytest.mark.asyncio
    async def test_judgment_workflow(self, temp_db, sample_event_proposal):
        """Test the complete judgment workflow."""
        agent = EventJudgeAgent(store=temp_db, offline_mode=True)
        
        result = await agent.run_judgment_workflow(max_proposals=1, status_filter="PENDING")
        
        assert result["success"] is True
        assert "proposals_judged" in result
        assert "approved" in result
        assert "rejected" in result
        assert "needs_revision" in result
        assert "execution_time" in result


class TestStoreOperations(TestCoreWorkflow):
    """Test core store operations."""
    
    def test_add_raw_item(self, temp_db):
        """Test adding raw items to the store."""
        raw_item = RawItem(
            source_id="test_source",
            external_id="test_123",
            raw_url="https://example.com/test",
            title="Test Item",
            content_text="Test content",
            raw_content_hash="hash123",
            meta_json={"test": "data"}
        )
        
        saved_item = temp_db.add_raw_item(raw_item)
        
        assert saved_item.id is not None
        assert saved_item.title == "Test Item"
        assert saved_item.raw_content_hash == "hash123"
    
    def test_create_event_proposal(self, temp_db, sample_raw_item):
        """Test creating event proposals."""
        request = CreateEventProposalRequest(
            raw_item_id=sample_raw_item.id,
            event_key="test_event",
            title="Test Event",
            description="Test description",
            proposed_by="test_agent",
            confidence_score=0.8
        )
        
        proposal = temp_db.create_event_proposal(request)
        
        assert proposal.id is not None
        assert proposal.event_key == "test_event"
        assert proposal.title == "Test Event"
        assert proposal.status == ProposalStatus.PENDING
    
    def test_get_pending_proposals(self, temp_db, sample_event_proposal):
        """Test retrieving pending proposals."""
        proposals = temp_db.get_pending_proposals()
        
        assert len(proposals) >= 1
        assert all(p.status == ProposalStatus.PENDING for p in proposals)


class TestWorkflowIntegration(TestCoreWorkflow):
    """Test integration between workflow components."""
    
    @pytest.mark.asyncio
    async def test_mine_to_judge_workflow(self, temp_db):
        """Test the complete mine→judge workflow."""
        # Step 1: Create a raw item (simulating mining)
        raw_item = RawItem(
            source_id="test_source",
            external_id="integration_test_123",
            raw_url="https://example.com/integration",
            title="Integration Test: Will AI replace programmers by 2030?",
            content_text="A test prediction market about AI and programming",
            raw_content_hash="integration_hash_123",
            meta_json={
                "platform": "kalshi",
                "market_type": "prediction_market",
                "category": "technology"
            }
        )
        saved_raw_item = temp_db.add_raw_item(raw_item)
        
        # Step 2: Create event proposal (simulating proposal creation)
        request = CreateEventProposalRequest(
            raw_item_id=saved_raw_item.id,
            event_key="ai_programmers_2030",
            title="Will AI replace programmers by 2030?",
            description="A prediction market about AI replacing human programmers by 2030",
            proposed_by="integration_test",
            confidence_score=0.9,
            meta_json={"test": "integration"}
        )
        proposal = temp_db.create_event_proposal(request)
        
        # Step 3: Judge the proposal
        judge_agent = EventJudgeAgent(store=temp_db, offline_mode=True)
        judgment = await judge_agent.judge_proposal(proposal)
        
        # Verify the workflow completed successfully
        assert judgment.proposal_id == proposal.id
        assert judgment.result in [JudgmentResult.APPROVED, JudgmentResult.REJECTED, JudgmentResult.NEEDS_REVISION]
        assert judgment.overall_score >= 0.0
        assert judgment.overall_score <= 1.0
        
        # Verify the judgment was saved to database
        with temp_db.get_session() as session:
            updated_proposal = session.query(EventProposal).filter_by(id=proposal.id).first()
            assert updated_proposal.meta_json is not None
            assert "judgment" in updated_proposal.meta_json
            # Verify judgment data structure
            judgment_data = updated_proposal.meta_json["judgment"]
            assert "result" in judgment_data
            assert "overall_score" in judgment_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
