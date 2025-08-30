"""Discovery agent for gathering candidate signals."""

import time
from datetime import datetime
from typing import List, Set, Optional

from ..adapters.rss import RSSAdapter
from ..core.hashing import generate_proto_event_key
from ..core.store import Store
from ..core.types import AgentRun, AgentType, Evidence, ProtoEvent, ProtoEventState


class DiscoveryAgent:
    """Agent responsible for discovering and gathering candidate signals."""
    
    def __init__(self, store: Store, max_feeds: Optional[int] = None, max_evidence_per_feed: Optional[int] = None, offline_mode: bool = False):
        """Initialize the discovery agent."""
        self.store = store
        self.rss_adapter = RSSAdapter(offline_mode=offline_mode)
        self.processed_hashes: Set[str] = set()
        self.max_feeds = max_feeds
        self.max_evidence_per_feed = max_evidence_per_feed
        self.offline_mode = offline_mode
    
    def run(self) -> AgentRun:
        """Run the discovery agent."""
        start_time = datetime.utcnow()
        
        # Initialize agent run
        agent_run = AgentRun(
            agent_type=AgentType.DISCOVERY,
            input_json={"sources": ["rss"]},
            started_at=start_time
        )
        
        try:
            # Gather evidence from sources
            all_evidence = self._gather_evidence()
            
            # Process evidence and create proto events
            proto_events = self._process_evidence(all_evidence)
            
            # Update agent run with results
            agent_run.output_json = {
                "evidence_count": len(all_evidence),
                "proto_events_count": len(proto_events),
                "new_evidence_count": len([e for e in all_evidence if e.content_hash not in self.processed_hashes])
            }
            
            agent_run.ended_at = datetime.utcnow()
            agent_run.latency_ms = int((agent_run.ended_at - start_time).total_seconds() * 1000)
            
            # Save agent run to database
            saved_run = self.store.add_agent_run(agent_run)
            
            return saved_run
            
        except Exception as e:
            # Handle errors
            agent_run.ended_at = datetime.utcnow()
            agent_run.output_json = {"error": str(e)}
            agent_run.latency_ms = int((agent_run.ended_at - start_time).total_seconds() * 1000)
            
            # Save error run to database
            saved_run = self.store.add_agent_run(agent_run)
            raise e
    
    def _gather_evidence(self) -> List[Evidence]:
        """Gather evidence from all configured sources."""
        all_evidence = []
        
        # Get RSS feeds
        rss_feeds = self.rss_adapter.get_default_feeds()
        
        # Apply feed limit if specified
        if self.max_feeds:
            rss_feeds = rss_feeds[:self.max_feeds]
            print(f"Limited to {len(rss_feeds)} feeds")
        
        for feed_url in rss_feeds:
            print(f"Fetching RSS feed: {feed_url}")
            
            # Get fallback feeds for this primary feed
            fallback_feeds = self.rss_adapter.get_fallback_feeds()
            
            # Try primary feed with fallbacks
            evidence_items = self.rss_adapter.fetch_feed_with_fallback(feed_url, fallback_feeds)
            
            if evidence_items:
                # Apply evidence per feed limit if specified
                if self.max_evidence_per_feed and len(evidence_items) > self.max_evidence_per_feed:
                    evidence_items = evidence_items[:self.max_evidence_per_feed]
                    print(f"Limited to {len(evidence_items)} items from {feed_url}")
                
                all_evidence.extend(evidence_items)
                print(f"Found {len(evidence_items)} items from {feed_url}")
            else:
                print(f"No evidence found for {feed_url} (including fallbacks)")
        
        return all_evidence
    
    def _process_evidence(self, evidence_list: List[Evidence]) -> List[ProtoEvent]:
        """Process evidence and create proto events."""
        proto_events = []
        
        for evidence in evidence_list:
            # Add evidence to database (this will dedupe by content_hash)
            saved_evidence = self.store.add_evidence(evidence)
            
            # Track processed hashes
            self.processed_hashes.add(saved_evidence.content_hash)
            
            # Generate proto event key
            proto_event_key = generate_proto_event_key(
                evidence.title,
                evidence.source_type.value,
                evidence.meta_json
            )
            
            # Get or create proto event
            proto_event = self.store.get_or_create_proto_event(proto_event_key)
            
            # Update proto event state if it's new evidence
            if saved_evidence.content_hash not in self.processed_hashes:
                if proto_event.state == ProtoEventState.STABLE:
                    proto_event.state = ProtoEventState.UPDATED
                elif proto_event.state == ProtoEventState.NEW:
                    # Keep as NEW for first evidence
                    pass
                
                # Update proto event in database
                self.store.update_proto_event(proto_event)
            
            proto_events.append(proto_event)
        
        return proto_events
    
    def get_new_proto_events(self) -> List[ProtoEvent]:
        """Get proto events that need assessment."""
        # This is a simplified implementation
        # In practice, you'd query the database for proto events that need assessment
        with self.store.get_session() as session:
            from ..core.store import ProtoEventModel
            models = session.query(ProtoEventModel).filter(
                ProtoEventModel.state.in_([ProtoEventState.NEW.value, ProtoEventState.UPDATED.value])
            ).all()
            
            return [
                ProtoEvent(
                    id=model.id,
                    key=model.key,
                    state=ProtoEventState(model.state),
                    first_seen_at=model.first_seen_at,
                    last_update_at=model.last_update_at
                )
                for model in models
            ]
