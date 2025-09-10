"""Event Resolution Workflow for processing all open events.

This workflow processes all events with status 'open' and attempts to resolve them
using the EventResolutionAgent. It handles batch processing and provides progress
tracking and error handling.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Event, EventResolution, ResolutionStatus, EventState
from core.store import Store
from agents.event_resolution import EventResolutionAgent
from agents.research import WebResearchAgent

logger = logging.getLogger(__name__)


class EventResolutionWorkflow:
    """Workflow for resolving events based on evidence analysis."""
    
    def __init__(self, store: Store, research_agent: Optional[WebResearchAgent] = None):
        """Initialize the resolution workflow.
        
        Args:
            store: Database store
            research_agent: Optional research agent (will create one if not provided)
        """
        self.store = store
        self.research_agent = research_agent or WebResearchAgent(store)
        self.resolution_agent = EventResolutionAgent(store, self.research_agent)
    
    async def resolve_all_open_events(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Resolve all events that don't have a resolution yet.
        
        Args:
            limit: Optional limit on number of events to process
            
        Returns:
            Dictionary with resolution statistics
        """
        logger.info("Starting event resolution workflow")
        
        # Get events without resolutions
        events = self._get_events_for_resolution(limit)
        logger.info(f"Found {len(events)} events to resolve")
        
        if not events:
            logger.info("No events found for resolution")
            return {
                'total_processed': 0,
                'resolved': 0,
                'open': 0,
                'contradicted': 0,
                'errors': 0
            }
        
        # Process events
        stats = {
            'total_processed': 0,
            'resolved': 0,
            'open': 0,
            'contradicted': 0,
            'errors': 0
        }
        
        for i, event in enumerate(events, 1):
            try:
                logger.info(f"Processing event {i}/{len(events)}: {event.title}")
                
                # Check if event already has a resolution
                with self.store.get_session() as session:
                    existing_resolution = session.query(EventResolution).filter(
                        EventResolution.event_id == event.id
                    ).first()
                
                if existing_resolution:
                    logger.info(f"Event {event.id} already has resolution: {existing_resolution.resolution_status}")
                    continue
                
                # Resolve the event
                resolution = await self.resolution_agent.resolve_event(event)
                
                # Update statistics
                stats['total_processed'] += 1
                if resolution.resolution_status == ResolutionStatus.RESOLVED:
                    stats['resolved'] += 1
                elif resolution.resolution_status == ResolutionStatus.OPEN:
                    stats['open'] += 1
                elif resolution.resolution_status == ResolutionStatus.CONTRADICTED:
                    stats['contradicted'] += 1
                
                logger.info(f"Event {event.id} resolved as: {resolution.resolution_status.value}")
                
                # Add delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to resolve event {event.id}: {e}")
                stats['errors'] += 1
                continue
        
        logger.info(f"Resolution workflow completed: {stats}")
        return stats
    
    async def resolve_specific_events(self, event_ids: List[str]) -> Dict[str, int]:
        """Resolve specific events by ID.
        
        Args:
            event_ids: List of event IDs to resolve
            
        Returns:
            Dictionary with resolution statistics
        """
        logger.info(f"Starting resolution for {len(event_ids)} specific events")
        
        stats = {
            'total_processed': 0,
            'resolved': 0,
            'open': 0,
            'contradicted': 0,
            'errors': 0
        }
        
        for event_id in event_ids:
            try:
                event = self.store.session.query(Event).filter(Event.id == event_id).first()
                if not event:
                    logger.warning(f"Event {event_id} not found")
                    continue
                
                logger.info(f"Resolving event: {event.title}")
                
                # Check for existing resolution
                with self.store.get_session() as session:
                    existing_resolution = session.query(EventResolution).filter(
                        EventResolution.event_id == event.id
                    ).first()
                
                if existing_resolution:
                    logger.info(f"Event {event.id} already has resolution: {existing_resolution.resolution_status}")
                    continue
                
                # Resolve the event
                resolution = await self.resolution_agent.resolve_event(event)
                
                # Update statistics
                stats['total_processed'] += 1
                if resolution.resolution_status == ResolutionStatus.RESOLVED:
                    stats['resolved'] += 1
                elif resolution.resolution_status == ResolutionStatus.OPEN:
                    stats['open'] += 1
                elif resolution.resolution_status == ResolutionStatus.CONTRADICTED:
                    stats['contradicted'] += 1
                
                logger.info(f"Event {event.id} resolved as: {resolution.resolution_status.value}")
                
                # Add delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to resolve event {event_id}: {e}")
                stats['errors'] += 1
                continue
        
        logger.info(f"Specific event resolution completed: {stats}")
        return stats
    
    def _get_events_for_resolution(self, limit: Optional[int] = None) -> List[Event]:
        """Get events that need resolution.
        
        Args:
            limit: Optional limit on number of events
            
        Returns:
            List of events to resolve
        """
        with self.store.get_session() as session:
            query = session.query(Event).filter(
                Event.state == EventState.ACTIVE
            ).order_by(Event.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_resolution_summary(self) -> Dict[str, int]:
        """Get summary of all resolutions in the database.
        
        Returns:
            Dictionary with resolution statistics
        """
        with self.store.get_session() as session:
            resolutions = session.query(EventResolution).all()
        
        summary = {
            'total_resolutions': len(resolutions),
            'resolved': 0,
            'open': 0,
            'contradicted': 0,
            'human_overrides': 0
        }
        
        for resolution in resolutions:
            if resolution.resolution_status == ResolutionStatus.RESOLVED:
                summary['resolved'] += 1
            elif resolution.resolution_status == ResolutionStatus.OPEN:
                summary['open'] += 1
            elif resolution.resolution_status == ResolutionStatus.CONTRADICTED:
                summary['contradicted'] += 1
            
            if resolution.human_override:
                summary['human_overrides'] += 1
        
        return summary


async def main():
    """Main function for running the resolution workflow."""
    import sys
    from pathlib import Path
    
    # Add app directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from core.store import Store
    
    # Initialize store and workflow
    store = Store()
    workflow = EventResolutionWorkflow(store)
    
    # Run resolution for all open events
    stats = await workflow.resolve_all_open_events(limit=10)  # Limit for testing
    
    print(f"Resolution completed: {stats}")
    
    # Print summary
    summary = workflow.get_resolution_summary()
    print(f"Database summary: {summary}")


if __name__ == "__main__":
    asyncio.run(main())
