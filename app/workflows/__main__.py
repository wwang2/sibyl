"""
Main entry point for workflows package.

This module provides a command-line interface for running individual workflows
or the complete scheduler.
"""

import asyncio
import argparse
import logging
import sys
from typing import Optional

from .scheduler import WorkflowScheduler, SchedulerConfig
from .market_mining import MarketMiningWorkflow, MiningConfig
from .discovery import DiscoveryWorkflow, DiscoveryConfig
from .prediction import PredictionWorkflow, PredictionConfig
from .research import ResearchWorkflow, ResearchConfig

def setup_logging(level: str = "INFO"):
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

async def run_scheduler(args):
    """Run the complete workflow scheduler."""
    config = SchedulerConfig(
        database_url=args.db_url,
        enable_market_mining=args.enable_market_mining,
        enable_discovery=args.enable_discovery,
        enable_prediction=args.enable_prediction,
        enable_research=args.enable_research,
        market_mining_interval=args.market_mining_interval,
        discovery_interval=args.discovery_interval,
        prediction_interval=args.prediction_interval,
        research_interval=args.research_interval
    )
    
    scheduler = WorkflowScheduler(config)
    
    try:
        await scheduler.initialize()
        await scheduler.start()
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("Received keyboard interrupt, shutting down...")
    except Exception as e:
        print(f"Error in scheduler: {e}")
    finally:
        await scheduler.stop()

async def run_workflow(args):
    """Run a specific workflow once."""
    workflow_name = args.workflow
    
    if workflow_name == "market_mining":
        config = MiningConfig(
            platforms=args.platforms.split(",") if args.platforms else ["kalshi", "polymarket"],
            categories=args.categories.split(",") if args.categories else None,
            limit_per_category=args.limit,
            create_proposals=args.create_proposals,
            database_url=args.db_url
        )
        workflow = MarketMiningWorkflow(config)
        await workflow.initialize()
        result = await workflow.mine_markets()
        await workflow.cleanup()
        
    elif workflow_name == "discovery":
        config = DiscoveryConfig(
            sources=args.sources.split(",") if args.sources else ["rss", "kalshi", "polymarket"],
            max_events_per_run=args.max_events,
            database_url=args.db_url,
            offline_mode=args.offline
        )
        workflow = DiscoveryWorkflow(config)
        await workflow.initialize()
        result = await workflow.discover_events()
        await workflow.cleanup()
        
    elif workflow_name == "prediction":
        config = PredictionConfig(
            max_events_per_run=args.max_events,
            prediction_horizon_days=args.horizon_days,
            database_url=args.db_url,
            confidence_threshold=args.confidence_threshold
        )
        workflow = PredictionWorkflow(config)
        await workflow.initialize()
        result = await workflow.make_predictions()
        await workflow.cleanup()
        
    elif workflow_name == "research":
        config = ResearchConfig(
            max_events_per_run=args.max_events,
            research_depth=args.depth,
            database_url=args.db_url,
            search_engines=args.search_engines.split(",") if args.search_engines else ["google", "bing"],
            max_search_results=args.max_results
        )
        workflow = ResearchWorkflow(config)
        await workflow.initialize()
        result = await workflow.research_events()
        await workflow.cleanup()
        
    else:
        raise ValueError(f"Unknown workflow: {workflow_name}")
    
    print(f"Workflow '{workflow_name}' completed: {result}")

def main():
    """Main entry point for the workflows CLI."""
    parser = argparse.ArgumentParser(description="Sybil Workflows CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Scheduler command
    scheduler_parser = subparsers.add_parser("scheduler", help="Run the complete workflow scheduler")
    scheduler_parser.add_argument("--db-url", default="sqlite:///./local.db", help="Database URL")
    scheduler_parser.add_argument("--enable-market-mining", action="store_true", default=True, help="Enable market mining workflow")
    scheduler_parser.add_argument("--enable-discovery", action="store_true", default=True, help="Enable discovery workflow")
    scheduler_parser.add_argument("--enable-prediction", action="store_true", default=True, help="Enable prediction workflow")
    scheduler_parser.add_argument("--enable-research", action="store_true", default=True, help="Enable research workflow")
    scheduler_parser.add_argument("--market-mining-interval", type=int, default=6, help="Market mining interval in hours")
    scheduler_parser.add_argument("--discovery-interval", type=int, default=4, help="Discovery interval in hours")
    scheduler_parser.add_argument("--prediction-interval", type=int, default=8, help="Prediction interval in hours")
    scheduler_parser.add_argument("--research-interval", type=int, default=12, help="Research interval in hours")
    
    # Workflow command
    workflow_parser = subparsers.add_parser("workflow", help="Run a specific workflow once")
    workflow_parser.add_argument("workflow", choices=["market_mining", "discovery", "prediction", "research"], help="Workflow to run")
    workflow_parser.add_argument("--db-url", default="sqlite:///./local.db", help="Database URL")
    
    # Market mining specific options
    workflow_parser.add_argument("--platforms", help="Comma-separated list of platforms (kalshi,polymarket)")
    workflow_parser.add_argument("--categories", help="Comma-separated list of categories")
    workflow_parser.add_argument("--limit", type=int, default=20, help="Limit per category")
    workflow_parser.add_argument("--create-proposals", action="store_true", help="Create event proposals")
    
    # Discovery specific options
    workflow_parser.add_argument("--sources", help="Comma-separated list of sources (rss,kalshi,polymarket)")
    workflow_parser.add_argument("--max-events", type=int, default=10, help="Maximum events per run")
    workflow_parser.add_argument("--offline", action="store_true", help="Use offline mode for RSS feeds")
    
    # Prediction specific options
    workflow_parser.add_argument("--horizon-days", type=int, default=30, help="Prediction horizon in days")
    workflow_parser.add_argument("--confidence-threshold", type=float, default=0.6, help="Confidence threshold")
    
    # Research specific options
    workflow_parser.add_argument("--depth", choices=["shallow", "medium", "deep"], default="medium", help="Research depth")
    workflow_parser.add_argument("--search-engines", help="Comma-separated list of search engines")
    workflow_parser.add_argument("--max-results", type=int, default=10, help="Maximum search results")
    
    # Global options
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    setup_logging(args.log_level)
    
    try:
        if args.command == "scheduler":
            asyncio.run(run_scheduler(args))
        elif args.command == "workflow":
            asyncio.run(run_workflow(args))
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("Interrupted by user")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
