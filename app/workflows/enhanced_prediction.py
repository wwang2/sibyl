"""
Enhanced Prediction Workflow with Research Agent Integration

This workflow integrates the WebResearchAgent into the prediction pipeline:
1. Fetch events that need predictions
2. Use research agent to build evidence chains
3. Generate predictions with structured reasoning
4. Save predictions with full attribution
5. Export data for static visualization
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.store import Store
from core.models import Event, EventProposal, EventResolution, Prediction, WorkflowRun, ToolCall, ToolCallType, RawItem, PredictionAttribution, Protocol, Source, SourceType, EventState
from core.types import ProposalStatus
from core.types import ProtocolKind
from core.research_models import Prediction as ResearchPrediction
from core.types import CreateWorkflowRunRequest
from agents.research import WebResearchAgent

logger = logging.getLogger(__name__)

@dataclass
class EnhancedPredictionConfig:
    """Configuration for enhanced prediction workflow."""
    max_events_per_run: int = 3
    prediction_horizon_days: int = 30
    database_url: str = "sqlite:///./local.db"
    offline_mode: bool = False
    export_dir: str = "docs/data"
    min_confidence_threshold: float = 0.3

class EnhancedPredictionWorkflow:
    """Enhanced workflow that integrates research agent for predictions."""
    
    def __init__(self, config: EnhancedPredictionConfig):
        self.config = config
        self.store = Store(config.database_url)
        self.research_agent = WebResearchAgent(self.store, offline_mode=config.offline_mode)
        self.workflow_run = None
        
    async def initialize(self):
        """Initialize the workflow."""
        logger.info("Initializing enhanced prediction workflow...")
        self.store.create_all()
        
        # Create or get research protocol
        self.protocol = await self._get_or_create_protocol()
        
        logger.info("Enhanced prediction workflow initialized")
    
    async def _get_or_create_protocol(self) -> Protocol:
        """Get or create the research protocol."""
        with self.store.get_session() as session:
            protocol = session.query(Protocol).filter_by(
                name="research_agent",
                version="1.0"
            ).first()
            
            if not protocol:
                protocol = Protocol(
                    name="research_agent",
                    kind=ProtocolKind.AGENT,
                    version="1.0",
                    description="Web research agent for evidence-based predictions"
                )
                session.add(protocol)
                session.commit()
                session.refresh(protocol)
            
            return protocol
    
    async def run_prediction_cycle(self) -> Dict[str, Any]:
        """Run a complete prediction cycle."""
        logger.info("Starting enhanced prediction cycle...")
        
        try:
            # Get events that need predictions
            events = await self._get_events_for_prediction()
            
            if not events:
                logger.info("No events found for prediction")
                return await self._create_empty_results()
            
            predictions_created = 0
            total_cost = 0.0
            processed_events = []
            
            for event in events:
                try:
                    # Research and predict for this event
                    prediction_result = await self._research_and_predict(event)
                    
                    if prediction_result:
                        predictions_created += 1
                        total_cost += prediction_result.get("cost_usd", 0.0)
                        processed_events.append({
                            "event_id": event.id,
                            "event_key": event.key,
                            "prediction_confidence": prediction_result.get("confidence_score", 0.0),
                            "evidence_count": prediction_result.get("evidence_count", 0)
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing event {event.id}: {e}")
                    continue
            
            # Export data for visualization
            await self._export_prediction_data()
            
            results = {
                "timestamp": datetime.utcnow().isoformat(),
                "workflow_type": "enhanced_prediction",
                "events_processed": len(processed_events),
                "predictions_created": predictions_created,
                "total_cost": total_cost,
                "processed_events": processed_events
            }
            
            logger.info(f"Enhanced prediction cycle completed: {predictions_created} predictions created")
            return results
            
        except Exception as e:
            logger.error(f"Error in enhanced prediction cycle: {e}")
            raise
    
    async def _get_events_for_prediction(self) -> List[Event]:
        """Get events that need predictions."""
        # Get approved proposals that don't have predictions yet
        with self.store.get_session() as session:
            from sqlalchemy import and_, not_
            
            # First, try to get approved proposals that don't have events yet
            approved_proposals = session.query(EventProposal).filter(
                EventProposal.status == ProposalStatus.ACCEPTED
            ).all()
            
            events = []
            for proposal in approved_proposals:
                # Check if this proposal already has an event with predictions
                existing_event = session.query(Event).filter(
                    Event.event_proposal_id == proposal.id
                ).first()
                
                if existing_event:
                    # Check if this event already has predictions
                    has_predictions = session.query(Prediction).join(
                        WorkflowRun, Prediction.workflow_run_id == WorkflowRun.id
                    ).filter(WorkflowRun.event_id == existing_event.id).first() is not None
                    
                    if not has_predictions:
                        events.append(existing_event)
                else:
                    # Create a temporary Event object from the proposal for prediction
                    temp_event = Event(
                        id=proposal.id,  # Use proposal ID as event ID
                        event_proposal_id=proposal.id,
                        key=proposal.event_key,
                        title=proposal.title,
                        description=proposal.description,
                        state=EventState.ACTIVE,
                        created_at=proposal.created_at
                    )
                    events.append(temp_event)
            
            # Limit the number of events to process
            events = events[:self.config.max_events_per_run]
        
        logger.info(f"Found {len(events)} events/proposals without predictions")
        return events
    
    async def _research_and_predict(self, event: Event) -> Optional[Dict[str, Any]]:
        """Research an event and create a prediction."""
        logger.info(f"Researching and predicting for event: {event.key}")
        
        try:
            # If this is a temporary event from a proposal, create the actual event first
            if hasattr(event, 'event_proposal_id') and event.event_proposal_id:
                with self.store.get_session() as session:
                    # Check if event already exists
                    existing_event = session.query(Event).filter(
                        Event.event_proposal_id == event.event_proposal_id
                    ).first()
                    
                    if not existing_event:
                        # Create the actual event from the proposal
                        actual_event = Event(
                            event_proposal_id=event.event_proposal_id,
                            key=event.key,
                            title=event.title,
                            description=event.description,
                            state=EventState.ACTIVE,
                            created_at=datetime.utcnow()
                        )
                        session.add(actual_event)
                        session.commit()
                        session.refresh(actual_event)
                        event = actual_event  # Use the actual event for the rest of the process
            
            # Create workflow run for this event
            workflow_request = CreateWorkflowRunRequest(
                event_id=event.id,
                protocol_id=self.protocol.id,
                meta_json={"workflow_type": "enhanced_prediction"}
            )
            workflow_run = self.store.create_workflow_run(workflow_request)
            
            # Create tool call for research
            start_time = datetime.utcnow()
            research_tool_call = ToolCall(
                workflow_run_id=workflow_run.id,
                step_number=1,
                tool_type=ToolCallType.SEARCH,
                tool_name="web_research",
                args_json={"event_id": event.id, "event_key": event.key}
            )
            
            # Research the event using the research agent
            research_prediction = await self.research_agent.research_event(
                event_id=event.id,
                event_description=event.key
            )
            
            # Update tool call with results
            end_time = datetime.utcnow()
            research_tool_call.result_json = {
                "evidence_count": len(research_prediction.evidence_chain.evidence_items),
                "evidence_strength": research_prediction.evidence_chain.calculate_evidence_strength(),
                "confidence": research_prediction.confidence_score,
                "prediction": research_prediction.prediction
            }
            research_tool_call.latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Save tool call
            with self.store.get_session() as session:
                session.add(research_tool_call)
                session.commit()
            
            # Create prediction record
            prediction = Prediction(
                workflow_run_id=workflow_run.id,
                protocol_id=self.protocol.id,
                p=research_prediction.confidence_score,
                horizon_hours=24 * 7,  # 1 week horizon
                rationale=research_prediction.reasoning
            )
            
            # Save prediction
            with self.store.get_session() as session:
                session.add(prediction)
                session.commit()
                session.refresh(prediction)
            
            # Create attributions for evidence sources
            with self.store.get_session() as session:
                # Get or create a web research source
                source = session.query(Source).filter_by(name="web_research").first()
                if not source:
                    source = Source(
                        name="web_research",
                        source_type=SourceType.CUSTOM,
                        endpoint="https://tavily.com"
                    )
                    session.add(source)
                    session.commit()
                    session.refresh(source)
                
                for i, evidence in enumerate(research_prediction.evidence_chain.evidence_items):
                    # Create raw item for evidence source with unique external_id
                    evidence_external_id = f"evidence_{event.id}_{evidence.id}_{i}"
                    raw_item = RawItem(
                        source_id=source.id,
                        external_id=evidence_external_id,
                        raw_url=evidence.source.url,
                        title=evidence.source.title,
                        content_text=evidence.source.content,
                        raw_content_hash=f"hash_{evidence.id}_{i}",
                        meta_json={
                            "evidence_id": evidence.id,
                            "source_type": evidence.source.source_type.value,
                            "reliability": evidence.source.reliability.value,
                            "relevance_score": evidence.relevance_to_event,
                            "extracted_fact": evidence.extracted_fact
                        }
                    )
                    session.add(raw_item)
                    session.commit()
                    session.refresh(raw_item)
                    
                    # Create attribution
                    attribution = PredictionAttribution(
                        prediction_id=prediction.id,
                        raw_item_id=raw_item.id,
                        rank=i + 1,
                        relevance_score=evidence.relevance_to_event
                    )
                    session.add(attribution)
                
                session.commit()
            
            return {
                "confidence_score": research_prediction.confidence_score,
                "prediction": research_prediction.prediction,
                "evidence_count": len(research_prediction.evidence_chain.evidence_items),
                "evidence_strength": research_prediction.evidence_chain.calculate_evidence_strength(),
                "cost_usd": 0.0,  # Research agent doesn't track costs yet
                "prediction_id": prediction.id
            }
            
        except Exception as e:
            logger.error(f"Error researching event {event.id}: {e}")
            return None
    
    async def _export_prediction_data(self):
        """Export prediction data for static visualization."""
        logger.info("Exporting prediction data for visualization...")
        
        # Ensure export directory exists
        export_path = Path(self.config.export_dir)
        export_path.mkdir(parents=True, exist_ok=True)
        
        # Get recent predictions with full data
        predictions_data = await self._get_predictions_for_export()
        
        # Export to JSON
        export_file = export_path / "predictions.json"
        with open(export_file, 'w') as f:
            json.dump(predictions_data, f, indent=2, default=str)
        
        # Export summary statistics
        summary_data = await self._get_prediction_summary()
        summary_file = export_path / "prediction_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2, default=str)
        
        logger.info(f"Exported prediction data to {export_path}")
    
    async def _get_predictions_for_export(self) -> Dict[str, Any]:
        """Get predictions data for export, grouped by events."""
        # Get recent predictions with their attributions
        with self.store.get_session() as session:
            predictions = session.query(Prediction).filter(
                Prediction.created_at >= datetime.utcnow() - timedelta(days=7)
            ).order_by(Prediction.created_at.desc()).all()
        
        # Group predictions by event
        events_data = {}
        
        for prediction in predictions:
            # Get event information
            with self.store.get_session() as session:
                workflow_run = session.query(WorkflowRun).filter(
                    WorkflowRun.id == prediction.workflow_run_id
                ).first()
                
                event = None
                if workflow_run:
                    event = session.query(Event).filter(
                        Event.id == workflow_run.event_id
                    ).first()
                
                # Get attributions
                attributions = session.query(PredictionAttribution).filter(
                    PredictionAttribution.prediction_id == prediction.id
                ).order_by(PredictionAttribution.rank).all()
            
            if not event:
                continue
                
            # Initialize event data if not exists
            if event.id not in events_data:
                # Get resolution information for this event
                resolution = None
                with self.store.get_session() as session:
                    resolution = session.query(EventResolution).filter(
                        EventResolution.event_id == event.id
                    ).first()
                
                events_data[event.id] = {
                    "event_id": event.id,
                    "event_key": event.key,
                    "event_title": event.title,
                    "event_description": event.description,
                    "event_state": event.state.value,
                    "expected_resolution_date": event.expected_resolution_date.isoformat() if event.expected_resolution_date else None,
                    "created_at": event.created_at.isoformat(),
                    "resolution": {
                        "status": resolution.resolution_status.value if resolution else "none",
                        "confidence_score": float(resolution.confidence_score) if resolution and resolution.confidence_score else None,
                        "confirming_sources_count": resolution.confirming_sources_count if resolution else 0,
                        "contradicting_sources_count": resolution.contradicting_sources_count if resolution else 0,
                        "total_sources_checked": resolution.total_sources_checked if resolution else 0,
                        "resolution_summary": resolution.resolution_summary if resolution else None,
                        "resolution_date": resolution.resolution_date.isoformat() if resolution and resolution.resolution_date else None,
                        "human_override": resolution.human_override if resolution else False
                    },
                    "predictions": []
                }
            
            # Add prediction data
            prediction_data = {
                "id": prediction.id,
                "probability": float(prediction.p),
                "horizon_hours": prediction.horizon_hours,
                "rationale": prediction.rationale,
                "created_at": prediction.created_at.isoformat(),
                "evidence_sources": []
            }
            
            for attr in attributions:
                with self.store.get_session() as session:
                    raw_item = session.query(RawItem).filter(
                        RawItem.id == attr.raw_item_id
                    ).first()
                
                if raw_item:
                    prediction_data["evidence_sources"].append({
                        "rank": attr.rank,
                        "relevance_score": float(attr.relevance_score) if attr.relevance_score else None,
                        "title": raw_item.title,
                        "url": raw_item.raw_url,
                        "source_type": raw_item.meta_json.get("source_type") if raw_item.meta_json else None,
                        "reliability": raw_item.meta_json.get("reliability") if raw_item.meta_json else None,
                        "extracted_fact": raw_item.meta_json.get("extracted_fact") if raw_item.meta_json else None
                    })
            
            # Add prediction to the event's predictions list
            events_data[event.id]["predictions"].append(prediction_data)
        
        # Convert to list format for export
        export_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "events": list(events_data.values())
        }
        
        return export_data
    
    async def _get_prediction_summary(self) -> Dict[str, Any]:
        """Get prediction summary statistics."""
        # Get all predictions
        with self.store.get_session() as session:
            predictions = session.query(Prediction).all()
        
        if not predictions:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "total_predictions": 0,
                "average_confidence": 0.0,
                "confidence_distribution": {},
                "recent_activity": []
            }
        
        # Calculate statistics
        total_predictions = len(predictions)
        average_confidence = sum(float(p.p) for p in predictions) / total_predictions
        
        # Confidence distribution
        confidence_bins = {"low": 0, "medium": 0, "high": 0}
        for p in predictions:
            conf = float(p.p)
            if conf < 0.4:
                confidence_bins["low"] += 1
            elif conf < 0.7:
                confidence_bins["medium"] += 1
            else:
                confidence_bins["high"] += 1
        
        # Recent activity (last 7 days)
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_predictions = [p for p in predictions if p.created_at >= recent_cutoff]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_predictions": total_predictions,
            "average_confidence": round(average_confidence, 3),
            "confidence_distribution": confidence_bins,
            "recent_activity": {
                "predictions_last_7_days": len(recent_predictions),
                "average_confidence_recent": round(sum(float(p.p) for p in recent_predictions) / len(recent_predictions), 3) if recent_predictions else 0.0
            }
        }
    
    async def _create_empty_results(self) -> Dict[str, Any]:
        """Create empty results when no events are found."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "workflow_type": "enhanced_prediction",
            "events_processed": 0,
            "predictions_created": 0,
            "total_cost": 0.0,
            "processed_events": []
        }
    
    async def cleanup(self):
        """Cleanup resources."""
        # No cleanup needed for per-event workflow runs
        pass

# CLI interface
async def main():
    """Main entry point for enhanced prediction workflow."""
    config = EnhancedPredictionConfig(
        max_events_per_run=3,
        offline_mode=True,  # Use offline mode for testing
        export_dir="docs/data"
    )
    
    workflow = EnhancedPredictionWorkflow(config)
    
    try:
        await workflow.initialize()
        results = await workflow.run_prediction_cycle()
        print(f"Enhanced prediction cycle completed: {results}")
    finally:
        await workflow.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
