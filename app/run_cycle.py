"""Main orchestration logic for running discovery and assessment cycles with event sourcing."""

import argparse
import sys
from typing import Optional

try:
    # Try relative imports first (when run as module)
    from .agents.predict import AutoGenAssessorAgent
    from .agents.discovery import SmartDiscoveryAgent
    from .core.store import Store
    from .core.types import AgentRun
except ImportError:
    # Fall back to absolute imports (when run directly)
    from agents.predict import AutoGenAssessorAgent
    from agents.discovery import SmartDiscoveryAgent
    from core.store import Store
    from core.types import AgentRun


def main(max_feeds: Optional[int] = None, max_items_per_feed: Optional[int] = None, max_events: Optional[int] = None, offline_mode: bool = False, model_name: str = "gemini-1.5-flash-8b"):
    """Run a single discovery and assessment cycle with event sourcing."""
    print("Starting agentic event discovery cycle with event sourcing...")
    
    # Print limits if specified
    if max_feeds:
        print(f"Limiting to {max_feeds} RSS feeds")
    if max_items_per_feed:
        print(f"Limiting to {max_items_per_feed} raw items per feed")
    if max_events:
        print(f"Limiting to {max_events} events for assessment")
    if offline_mode:
        print("Running in offline mode with test fixtures")
    print(f"Using AutoGen with model: {model_name}")
    
    # Initialize store
    store = Store.from_env()
    
    # Create agents with limits
    discovery_agent = SmartDiscoveryAgent(
        store, 
        max_feeds=max_feeds, 
        max_items_per_feed=max_items_per_feed, 
        offline_mode=offline_mode,
        model_name=model_name
    )
    assessor_agent = AutoGenAssessorAgent(store, max_events=max_events, model_name=model_name)
    
    try:
        # Run discovery agent
        print("Running discovery agent...")
        discovery_run = discovery_agent.run()
        print(f"Discovery completed: {discovery_run.output_json}")
        
        # Get pending proposals for review
        pending_proposals = discovery_agent.get_pending_proposals()
        print(f"Found {len(pending_proposals)} pending event proposals")
        
        # Show discovery summary
        discovery_agent.print_discovery_summary()
        
        # For now, auto-accept all proposals (in production, this would be human review)
        if pending_proposals:
            print("Auto-accepting all pending proposals...")
            for proposal in pending_proposals:
                try:
                    from .core.types import ReviewEventProposalRequest, ProposalStatus
                except ImportError:
                    from core.types import ReviewEventProposalRequest, ProposalStatus
                review_request = ReviewEventProposalRequest(
                    proposal_id=proposal.id,
                    status=ProposalStatus.ACCEPTED,
                    reviewed_by="auto_reviewer",
                    review_notes="Auto-accepted for testing"
                )
                store.review_event_proposal(review_request)
                print(f"Accepted proposal: {proposal.title}")
        
        # Get active events for assessment
        try:
            from .core.types import EventState
        except ImportError:
            from core.types import EventState
        active_events = store.get_events_by_state(EventState.ACTIVE)
        print(f"Found {len(active_events)} active events for assessment")
        
        if active_events:
            # Run assessor agent
            print("Running assessor agent...")
            assessor_run = assessor_agent.run(active_events)
            print(f"Assessment completed: {assessor_run.output_json}")
            
            # Show AutoGen assessment summary
            assessor_agent.print_autogen_assessment_summary()
        else:
            print("No active events to assess")
        
        print("Cycle completed successfully!")
        
    except Exception as e:
        print(f"Error during cycle: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run agentic event discovery cycle")
    parser.add_argument("--max-feeds", type=int, help="Maximum number of RSS feeds to process")
    parser.add_argument("--max-items-per-feed", type=int, help="Maximum number of items per feed")
    parser.add_argument("--max-events", type=int, help="Maximum number of events to assess")
    parser.add_argument("--offline-mode", action="store_true", help="Run in offline mode with test fixtures")
    parser.add_argument("--model", type=str, default="gemini-1.5-flash-8b", help="AutoGen model to use")
    
    args = parser.parse_args()
    
    main(
        max_feeds=args.max_feeds,
        max_items_per_feed=args.max_items_per_feed,
        max_events=args.max_events,
        offline_mode=args.offline_mode,
        model_name=args.model
    )