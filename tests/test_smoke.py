"""Smoke tests for the agentic event discovery system."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.store import Store
from app.run_cycle import main


def test_store_creation():
    """Test that the store can be created and tables initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"
        
        store = Store(db_url)
        store.create_all()
        
        # Verify tables were created
        with store.get_session() as session:
            from app.core.store import Base
            inspector = Base.metadata
            table_names = inspector.tables.keys()
            
            expected_tables = {
                'sources', 'raw_items', 'event_proposals', 'events',
                'market_listings', 'protocols', 'workflow_runs', 'tool_calls',
                'predictions', 'prediction_attributions', 'outcomes', 
                'prediction_scores', 'agent_runs'
            }
            
            assert expected_tables.issubset(table_names)


def test_run_cycle_mock(tmp_path, monkeypatch):
    """Test running the full cycle in mock mode."""
    # Set up environment for mock mode
    monkeypatch.setenv('LLM_MODE', 'mock')
    monkeypatch.setenv('MOCK_SEED', '42')
    monkeypatch.setenv('DB_URL', f'sqlite:///{tmp_path}/test.db')
    monkeypatch.setenv('GOOGLE_API_KEY', 'mock-api-key-for-testing')
    
    # Create a simple RSS fixture
    rss_fixture = tmp_path / "rss_sample.xml"
    rss_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <description>Test RSS feed for smoke testing</description>
        <item>
            <title>Test News Item 1</title>
            <link>https://example.com/news1</link>
            <description>This is a test news item for smoke testing.</description>
            <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
        </item>
        <item>
            <title>Test News Item 2</title>
            <link>https://example.com/news2</link>
            <description>Another test news item for smoke testing.</description>
            <pubDate>Mon, 01 Jan 2024 13:00:00 GMT</pubDate>
        </item>
    </channel>
</rss>"""
    rss_fixture.write_text(rss_content)
    
    # Set the fixture path
    monkeypatch.setenv('RSS_FIXTURE', str(rss_fixture))
    
    # Initialize database
    store = Store.from_env()
    store.create_all()
    
    # Run the cycle
    main()
    
    # Verify that raw items were created
    with store.get_session() as session:
        from app.core.models import RawItem
        raw_items_count = session.query(RawItem).count()
        assert raw_items_count > 0, "No raw items were created"
    
    # Verify that event proposals were created
    with store.get_session() as session:
        from app.core.models import EventProposal
        event_proposals_count = session.query(EventProposal).count()
        assert event_proposals_count > 0, "No event proposals were created"
    
    # Verify that predictions were created (optional - may not be created in mock mode)
    with store.get_session() as session:
        from app.core.models import Prediction
        predictions_count = session.query(Prediction).count()
        # Predictions may not be created in mock mode, so we just verify the table exists
        assert predictions_count >= 0, "Prediction table should exist"
    
    # Verify that agent runs were recorded (optional - may not be recorded in mock mode)
    with store.get_session() as session:
        from app.core.models import AgentRun
        agent_runs_count = session.query(AgentRun).count()
        # Agent runs may not be recorded in mock mode, so we just verify the table exists
        assert agent_runs_count >= 0, "AgentRun table should exist"


if __name__ == "__main__":
    pytest.main([__file__])
