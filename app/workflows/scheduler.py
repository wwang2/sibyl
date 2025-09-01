"""
Workflow Scheduler

This module provides a centralized scheduler for all routine operations:
- Market mining workflow
- Discovery workflow
- Prediction workflow
- Research workflow

It coordinates the execution of these workflows and manages their schedules.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import signal
import sys

from .market_mining import MarketMiningWorkflow, MiningConfig
from .discovery import DiscoveryWorkflow, DiscoveryConfig
from .prediction import PredictionWorkflow, PredictionConfig
from .research import ResearchWorkflow, ResearchConfig

logger = logging.getLogger(__name__)

@dataclass
class SchedulerConfig:
    """Configuration for the workflow scheduler."""
    database_url: str = "sqlite:///./local.db"
    enable_market_mining: bool = True
    enable_discovery: bool = True
    enable_prediction: bool = True
    enable_research: bool = True
    
    # Schedule intervals (in hours)
    market_mining_interval: int = 6
    discovery_interval: int = 4
    prediction_interval: int = 8
    research_interval: int = 12
    
    # Workflow-specific configs
    market_mining_config: MiningConfig = None
    discovery_config: DiscoveryConfig = None
    prediction_config: PredictionConfig = None
    research_config: ResearchConfig = None

class WorkflowScheduler:
    """Centralized scheduler for all routine operations."""
    
    def __init__(self, config: SchedulerConfig):
        self.config = config
        self.workflows = {}
        self.running = False
        self.tasks = []
        
    async def initialize(self):
        """Initialize all enabled workflows."""
        logger.info("Initializing workflow scheduler...")
        
        # Initialize market mining workflow
        if self.config.enable_market_mining:
            mining_config = self.config.market_mining_config or MiningConfig(
                platforms=["kalshi", "polymarket"],
                categories=["Politics", "Economics", "Technology"],
                limit_per_category=20,
                create_proposals=True,
                schedule_interval_hours=self.config.market_mining_interval,
                database_url=self.config.database_url
            )
            self.workflows["market_mining"] = MarketMiningWorkflow(mining_config)
            await self.workflows["market_mining"].initialize()
        
        # Initialize discovery workflow
        if self.config.enable_discovery:
            discovery_config = self.config.discovery_config or DiscoveryConfig(
                sources=["rss", "kalshi", "polymarket"],
                max_events_per_run=10,
                schedule_interval_hours=self.config.discovery_interval,
                database_url=self.config.database_url,
                offline_mode=False
            )
            self.workflows["discovery"] = DiscoveryWorkflow(discovery_config)
            await self.workflows["discovery"].initialize()
        
        # Initialize prediction workflow
        if self.config.enable_prediction:
            prediction_config = self.config.prediction_config or PredictionConfig(
                max_events_per_run=5,
                prediction_horizon_days=30,
                schedule_interval_hours=self.config.prediction_interval,
                database_url=self.config.database_url,
                confidence_threshold=0.6
            )
            self.workflows["prediction"] = PredictionWorkflow(prediction_config)
            await self.workflows["prediction"].initialize()
        
        # Initialize research workflow
        if self.config.enable_research:
            research_config = self.config.research_config or ResearchConfig(
                max_events_per_run=3,
                research_depth="medium",
                schedule_interval_hours=self.config.research_interval,
                database_url=self.config.database_url,
                search_engines=["google", "bing"],
                max_search_results=10
            )
            self.workflows["research"] = ResearchWorkflow(research_config)
            await self.workflows["research"].initialize()
        
        logger.info(f"Workflow scheduler initialized with {len(self.workflows)} workflows")
    
    async def start(self):
        """Start all scheduled workflows."""
        logger.info("Starting workflow scheduler...")
        self.running = True
        
        # Start market mining workflow
        if "market_mining" in self.workflows:
            task = asyncio.create_task(self.workflows["market_mining"].run_scheduled())
            self.tasks.append(task)
            logger.info("Market mining workflow started")
        
        # Start discovery workflow
        if "discovery" in self.workflows:
            task = asyncio.create_task(self.workflows["discovery"].run_scheduled())
            self.tasks.append(task)
            logger.info("Discovery workflow started")
        
        # Start prediction workflow
        if "prediction" in self.workflows:
            task = asyncio.create_task(self.workflows["prediction"].run_scheduled())
            self.tasks.append(task)
            logger.info("Prediction workflow started")
        
        # Start research workflow
        if "research" in self.workflows:
            task = asyncio.create_task(self.workflows["research"].run_scheduled())
            self.tasks.append(task)
            logger.info("Research workflow started")
        
        logger.info(f"All workflows started. Running {len(self.tasks)} scheduled tasks.")
    
    async def stop(self):
        """Stop all workflows and cleanup resources."""
        logger.info("Stopping workflow scheduler...")
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Cleanup workflows
        for workflow in self.workflows.values():
            await workflow.cleanup()
        
        logger.info("Workflow scheduler stopped")
    
    async def run_once(self, workflow_name: str) -> Dict[str, Any]:
        """Run a specific workflow once."""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")
        
        logger.info(f"Running workflow '{workflow_name}' once...")
        
        workflow = self.workflows[workflow_name]
        
        if workflow_name == "market_mining":
            return await workflow.mine_markets()
        elif workflow_name == "discovery":
            return await workflow.discover_events()
        elif workflow_name == "prediction":
            return await workflow.make_predictions()
        elif workflow_name == "research":
            return await workflow.research_events()
        else:
            raise ValueError(f"Unknown workflow type: {workflow_name}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the status of all workflows."""
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "running": self.running,
            "workflows": {}
        }
        
        for name, workflow in self.workflows.items():
            status["workflows"][name] = {
                "enabled": True,
                "type": type(workflow).__name__,
                "status": "running" if self.running else "stopped"
            }
        
        return status

# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

# CLI interface for the scheduler
async def main():
    """Main entry point for the workflow scheduler."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create scheduler configuration
    config = SchedulerConfig(
        database_url="sqlite:///./local.db",
        enable_market_mining=True,
        enable_discovery=True,
        enable_prediction=True,
        enable_research=True
    )
    
    scheduler = WorkflowScheduler(config)
    
    try:
        await scheduler.initialize()
        await scheduler.start()
        
        # Keep running until interrupted
        while scheduler.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in scheduler: {e}")
    finally:
        await scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
