"""Main orchestration logic for running discovery and assessment cycles."""

import sys
from typing import Optional

from .agents.assessor import AssessorAgent
from .agents.discovery import DiscoveryAgent
from .core.store import Store
from .core.types import AgentRun


def main(max_feeds: Optional[int] = None, max_evidence_per_feed: Optional[int] = None, max_proto_events: Optional[int] = None, offline_mode: bool = False):
    """Run a single discovery and assessment cycle."""
    print("Starting agentic event discovery cycle...")
    
    # Print limits if specified
    if max_feeds:
        print(f"Limiting to {max_feeds} RSS feeds")
    if max_evidence_per_feed:
        print(f"Limiting to {max_evidence_per_feed} evidence items per feed")
    if max_proto_events:
        print(f"Limiting to {max_proto_events} proto events for assessment")
    if offline_mode:
        print("Running in offline mode with test fixtures")
    
    # Initialize store
    store = Store.from_env()
    
    # Create agents with limits
    discovery_agent = DiscoveryAgent(store, max_feeds=max_feeds, max_evidence_per_feed=max_evidence_per_feed, offline_mode=offline_mode)
    assessor_agent = AssessorAgent(store, max_proto_events=max_proto_events)
    
    try:
        # Run discovery agent
        print("Running discovery agent...")
        discovery_run = discovery_agent.run()
        print(f"Discovery completed: {discovery_run.output_json}")
        
        # Get new proto events for assessment
        proto_events = discovery_agent.get_new_proto_events()
        print(f"Found {len(proto_events)} proto events for assessment")
        
        if proto_events:
            # Run assessor agent
            print("Running assessor agent...")
            assessor_run = assessor_agent.run(proto_events)
            print(f"Assessment completed: {assessor_run.output_json}")
        else:
            print("No proto events to assess")
        
        print("Cycle completed successfully!")
        
    except Exception as e:
        print(f"Error during cycle: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
