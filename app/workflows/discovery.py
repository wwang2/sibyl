"""
Discovery Workflow

This workflow handles the routine operation of:
- Discovering events from RSS feeds and other sources
- Registering discovered events to database
- Running the SmartDiscoveryAgent to find new events
- Scheduling regular discovery cycles
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..core.store import Store
from ..core.types import AgentRun, AgentType
from ..agents.discovery import SmartDiscoveryAgent

logger = logging.getLogger(__name__)

@dataclass
class DiscoveryConfig:
    """Configuration for discovery workflow."""
    sources: List[str] = None  # ["rss", "kalshi", "polymarket"]
    max_events_per_run: int = 10
    schedule_interval_hours: int = 4
    database_url: str = "sqlite:///./local.db"
    offline_mode: bool = False  # For RSS feeds only

class DiscoveryWorkflow:
    """Workflow for discovering events from various sources."""
    
    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.store = Store(config.database_url)
        self.discovery_agent = None
        
    async def initialize(self):
        """Initialize discovery agent and database."""
        logger.info("Initializing discovery workflow...")
        self.store.create_all()
        
        # Initialize the SmartDiscoveryAgent
        self.discovery_agent = SmartDiscoveryAgent(
            store=self.store,
            max_feeds=3,  # Limit to 3 feeds for workflow
            max_items_per_feed=self.config.max_events_per_run,
            offline_mode=self.config.offline_mode
        )
        
        logger.info("Discovery workflow initialized")
    
    async def discover_events(self) -> Dict[str, Any]:
        """Run the discovery process to find new events."""
        logger.info("Starting event discovery...")
        
        try:
            # Run the discovery agent
            result = self.discovery_agent.run()
            
            # Save the agent run to database
            agent_run = AgentRun(
                agent_type=AgentType.DISCOVERY,
                input_json={"sources": self.config.sources, "max_events": self.config.max_events_per_run},
                output_json=result.output_json,
                meta_json=result.meta_json,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
                started_at=result.started_at,
                ended_at=result.ended_at
            )
            
            self.store.add_agent_run(agent_run)
            
            # Extract results
            events_discovered = len(result.output_json.get("event_proposals", []))
            sources_used = result.meta_json.get("fetched_sources", [])
            
            discovery_results = {
                "timestamp": datetime.utcnow().isoformat(),
                "events_discovered": events_discovered,
                "sources_used": sources_used,
                "agent_run_id": agent_run.id,
                "tokens_used": result.tokens_in + result.tokens_out,
                "cost_usd": result.cost_usd,
                "latency_ms": result.latency_ms
            }
            
            logger.info(f"Discovery completed: {events_discovered} events discovered from {len(sources_used)} sources")
            return discovery_results
            
        except Exception as e:
            logger.error(f"Error in event discovery: {e}")
            raise
    
    async def run_scheduled(self):
        """Run the discovery workflow on a schedule."""
        logger.info(f"Starting scheduled discovery (every {self.config.schedule_interval_hours} hours)")
        
        while True:
            try:
                await self.discover_events()
                await asyncio.sleep(self.config.schedule_interval_hours * 3600)
            except Exception as e:
                logger.error(f"Error in scheduled discovery: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.discovery_agent:
            # SmartDiscoveryAgent doesn't have a cleanup method
            pass

# CLI interface for the workflow
async def main():
    """Main entry point for discovery workflow."""
    config = DiscoveryConfig(
        sources=["rss", "kalshi", "polymarket"],
        max_events_per_run=10,
        offline_mode=False
    )
    
    workflow = DiscoveryWorkflow(config)
    
    try:
        await workflow.initialize()
        results = await workflow.discover_events()
        print(f"Discovery completed: {results}")
    finally:
        await workflow.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
