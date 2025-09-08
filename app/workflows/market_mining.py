"""
Market Mining Workflow

This workflow handles the routine operation of:
- Registering events from prediction markets (Kalshi, Polymarket)
- Saving market data to database as RawItems
- Creating EventProposals from market data
- Scheduling regular market data collection
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from ..core.store import Store
    from ..core.types import SourceType, RawItem, EventProposal
    from ..adapters.kalshi import KalshiAdapter
    from ..adapters.polymarket import PolymarketAdapter
except ImportError:
    from core.store import Store
    from core.types import SourceType, RawItem, EventProposal
    from adapters.kalshi import KalshiAdapter
    from adapters.polymarket import PolymarketAdapter

logger = logging.getLogger(__name__)

@dataclass
class MiningConfig:
    """Configuration for market mining workflow."""
    platforms: List[str] = None  # ["kalshi", "polymarket"]
    categories: List[str] = None  # ["Politics", "Economics", "Technology"]
    limit_per_category: int = 20
    create_proposals: bool = True
    schedule_interval_hours: int = 6
    database_url: str = "sqlite:///./local.db"

class MarketMiningWorkflow:
    """Workflow for mining prediction markets and registering events."""
    
    def __init__(self, config: MiningConfig):
        self.config = config
        self.store = Store(config.database_url)
        self.kalshi_adapter = None
        self.polymarket_adapter = None
        
    async def initialize(self):
        """Initialize adapters and database."""
        logger.info("Initializing market mining workflow...")
        self.store.create_all()
        
        if "kalshi" in self.config.platforms:
            self.kalshi_adapter = KalshiAdapter()
            
        if "polymarket" in self.config.platforms:
            self.polymarket_adapter = PolymarketAdapter()
            
        logger.info("Market mining workflow initialized")
    
    async def mine_markets(self) -> Dict[str, Any]:
        """Mine markets from all configured platforms."""
        logger.info("Starting market mining...")
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "platforms": {},
            "total_markets": 0,
            "total_saved": 0,
            "proposals_created": 0
        }
        
        try:
            # Mine Kalshi markets
            if self.kalshi_adapter:
                kalshi_result = await self._mine_kalshi_markets()
                results["platforms"]["kalshi"] = kalshi_result
                results["total_markets"] += kalshi_result["total_markets"]
                results["total_saved"] += kalshi_result["total_saved"]
            
            # Mine Polymarket markets
            if self.polymarket_adapter:
                polymarket_result = await self._mine_polymarket_markets()
                results["platforms"]["polymarket"] = polymarket_result
                results["total_markets"] += polymarket_result["total_markets"]
                results["total_saved"] += polymarket_result["total_saved"]
            
            # Create event proposals if configured
            if self.config.create_proposals:
                proposals_created = await self._create_event_proposals()
                results["proposals_created"] = proposals_created
            
            logger.info(f"Market mining completed: {results['total_saved']} markets saved, {results['proposals_created']} proposals created")
            return results
            
        except Exception as e:
            logger.error(f"Error in market mining: {e}")
            raise
    
    async def _mine_kalshi_markets(self) -> Dict[str, Any]:
        """Mine markets from Kalshi."""
        logger.info("Mining Kalshi markets...")
        
        try:
            # Fetch markets only (events method doesn't exist)
            markets = self.kalshi_adapter.fetch_markets_current(
                limit=self.config.limit_per_category
            )
            
            # No events method available in Kalshi adapter
            events = []
            
            # Save to database
            saved_markets = 0
            saved_events = 0
            
            for market in markets:
                try:
                    self.store.add_raw_item(market)
                    saved_markets += 1
                except Exception as e:
                    logger.warning(f"Failed to save Kalshi market {market.external_id}: {e}")
            
            for event in events:
                try:
                    self.store.add_raw_item(event)
                    saved_events += 1
                except Exception as e:
                    logger.warning(f"Failed to save Kalshi event {event.external_id}: {e}")
            
            logger.info(f"Kalshi mining completed: {saved_markets} markets, {saved_events} events saved")
            
            return {
                "total_markets": len(markets),
                "total_events": len(events),
                "total_saved": saved_markets + saved_events,
                "saved_markets": saved_markets,
                "saved_events": saved_events,
                "categories": {}
            }
            
        except Exception as e:
            logger.error(f"Error mining Kalshi markets: {e}")
            return {
                "total_markets": 0,
                "total_events": 0,
                "total_saved": 0,
                "error": str(e),
                "categories": {}
            }
    
    async def _mine_polymarket_markets(self) -> Dict[str, Any]:
        """Mine markets from Polymarket."""
        logger.info("Mining Polymarket markets...")
        
        try:
            # Fetch markets (including past events for now)
            markets = self.polymarket_adapter.fetch_markets(
                limit=self.config.limit_per_category,
                exclude_past=False  # Include past events for testing
            )
            
            # No events method available in Polymarket adapter
            events = []
            
            # Save to database
            saved_markets = 0
            saved_events = 0
            
            for market in markets:
                try:
                    self.store.add_raw_item(market)
                    saved_markets += 1
                except Exception as e:
                    logger.warning(f"Failed to save Polymarket market {market.external_id}: {e}")
            
            for event in events:
                try:
                    self.store.add_raw_item(event)
                    saved_events += 1
                except Exception as e:
                    logger.warning(f"Failed to save Polymarket event {event.external_id}: {e}")
            
            logger.info(f"Polymarket mining completed: {saved_markets} markets, {saved_events} events saved")
            
            return {
                "total_markets": len(markets),
                "total_events": len(events),
                "total_saved": saved_markets + saved_events,
                "saved_markets": saved_markets,
                "saved_events": saved_events,
                "categories": {}
            }
            
        except Exception as e:
            logger.error(f"Error mining Polymarket markets: {e}")
            return {
                "total_markets": 0,
                "total_events": 0,
                "total_saved": 0,
                "error": str(e),
                "categories": {}
            }
    
    async def _create_event_proposals(self) -> int:
        """Create event proposals from mined market data."""
        logger.info("Creating event proposals from market data...")
        
        try:
            # Get recent raw items from prediction markets
            with self.store.get_session() as session:
                try:
                    from ..core.models import RawItem as RawItemModel
                except ImportError:
                    from core.models import RawItem as RawItemModel
                
                # Get raw items from prediction markets
                from sqlalchemy import text
                raw_items = session.query(RawItemModel).filter(
                    text("json_extract(meta_json, '$.platform') IN ('kalshi', 'polymarket')")
                ).order_by(RawItemModel.fetched_at.desc()).limit(100).all()
                
                proposals_created = 0
                
                for raw_item in raw_items:
                    try:
                        # Extract event information from meta_json
                        meta = raw_item.meta_json
                        platform = meta.get('platform', 'unknown')
                        market_type = meta.get('market_type', 'unknown')
                        
                        # Create event key based on platform and external ID
                        # For events without external_id, use the title hash
                        if raw_item.external_id:
                            event_key = f"{platform}_{raw_item.external_id}"
                        else:
                            # Create a key from the title for events without external_id
                            import hashlib
                            title_hash = hashlib.md5(raw_item.title.encode()).hexdigest()[:8]
                            event_key = f"{platform}_event_{title_hash}"
                        
                        # Create title and description
                        title = raw_item.title or f"{platform.title()} Market"
                        description = raw_item.content_text or "No description available"
                        
                        # For events, improve the description
                        if market_type == 'prediction_event' and description == "No description available":
                            description = f"Prediction event from {platform.title()}: {title}"
                        
                        # Create event proposal request
                        try:
                            from ..core.types import CreateEventProposalRequest
                        except ImportError:
                            from core.types import CreateEventProposalRequest
                        request = CreateEventProposalRequest(
                            raw_item_id=raw_item.id,
                            event_key=event_key,
                            title=title,
                            description=description,
                            proposed_by="market_mining_workflow",
                            confidence_score=0.8,  # High confidence for prediction markets
                            meta_json={
                                "platform": platform,
                                "external_id": raw_item.external_id,
                                "market_type": market_type,
                                "source": "automated_mining",
                                "original_ticker": meta.get('ticker'),
                                "original_status": meta.get('status'),
                                "category": meta.get('category'),
                                "subcategory": meta.get('subcategory'),
                                "close_time": meta.get('close_time'),
                                "data_quality": "good" if raw_item.external_id else "event_level"
                            }
                        )
                        
                        # Create the proposal
                        self.store.create_event_proposal(request)
                        proposals_created += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to create event proposal for raw item {raw_item.id}: {e}")
                        continue
                
                logger.info(f"Created {proposals_created} event proposals from market data")
                return proposals_created
                
        except Exception as e:
            logger.error(f"Error creating event proposals: {e}")
            return 0
    
    async def run_scheduled(self):
        """Run the mining workflow on a schedule."""
        logger.info(f"Starting scheduled market mining (every {self.config.schedule_interval_hours} hours)")
        
        while True:
            try:
                await self.mine_markets()
                await asyncio.sleep(self.config.schedule_interval_hours * 3600)
            except Exception as e:
                logger.error(f"Error in scheduled mining: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.kalshi_adapter:
            self.kalshi_adapter.close()
        if self.polymarket_adapter:
            self.polymarket_adapter.close()

# CLI interface for the workflow
async def main():
    """Main entry point for market mining workflow."""
    config = MiningConfig(
        platforms=["kalshi", "polymarket"],
        categories=["Politics", "Economics", "Technology"],
        limit_per_category=20,
        create_proposals=True
    )
    
    workflow = MarketMiningWorkflow(config)
    
    try:
        await workflow.initialize()
        results = await workflow.mine_markets()
        print(f"Market mining completed: {results}")
    finally:
        await workflow.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
