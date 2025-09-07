"""Database store implementation for the event sourcing prediction system.

This module provides a high-level interface for managing the event sourcing
data flow: RawItems → EventProposals → Events → WorkflowRuns → Predictions.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import sessionmaker

from .database import get_database_url, validate_database_path, print_database_info

from .models import (
    Base, Event, EventProposal, EventState, MarketListing, Outcome, Prediction,
    PredictionAttribution, PredictionScore, Protocol, ProposalStatus, RawItem,
    Source, ToolCall, WorkflowRun
)
from .types import (
    AgentRun, AgentType, CreateEventProposalRequest, CreatePredictionRequest, CreateWorkflowRunRequest,
    EventWithMarketData, EventWithProposals, PredictionWithAttributions,
    ResolveOutcomeRequest, ReviewEventProposalRequest, ToolCallType, WorkflowRunWithDetails
)


class Store:
    """Database store for the event sourcing prediction system."""
    
    def __init__(self, db_url: Optional[str] = None):
        """Initialize the store with a database URL."""
        if db_url is None:
            db_url = get_database_url()
        
        # Validate the database path
        db_path = str(db_url).replace("sqlite:///", "")
        if not validate_database_path(db_path):
            print("⚠️ Warning: Database path validation failed, but continuing...")
        
        self.engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Print database info for debugging
        print_database_info()
    
    @classmethod
    def from_env(cls) -> "Store":
        """Create a store instance from environment variables."""
        import os
        db_url = os.getenv("DB_URL")
        return cls(db_url)
    
    def create_all(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get a database session."""
        return self.SessionLocal()

    # -------------------- Event Sourcing Flow --------------------
    
    def add_raw_item(self, raw_item: RawItem) -> RawItem:
        """Add a raw item to the database."""
        with self.get_session() as session:
            from .models import RawItem as RawItemModel
            
            # Check if raw item already exists by hash
            existing = session.query(RawItemModel).filter_by(
                raw_content_hash=raw_item.raw_content_hash
            ).first()
            
            if existing:
                return RawItem(
                    id=existing.id,
                    source_id=existing.source_id,
                    external_id=existing.external_id,
                    raw_url=existing.raw_url,
                    title=existing.title,
                    content_text=existing.content_text,
                    raw_content_hash=existing.raw_content_hash,
                    fetched_at=existing.fetched_at,
                    meta_json=existing.meta_json
                )
            
            # Create new raw item
            raw_item_model = RawItemModel(
                id=str(uuid4()),
                source_id=raw_item.source_id,
                external_id=raw_item.external_id,
                raw_url=raw_item.raw_url,
                title=raw_item.title,
                content_text=raw_item.content_text,
                raw_content_hash=raw_item.raw_content_hash,
                fetched_at=raw_item.fetched_at,
                meta_json=raw_item.meta_json
            )
            
            session.add(raw_item_model)
            session.commit()
            session.refresh(raw_item_model)
            
            return RawItem(
                id=raw_item_model.id,
                source_id=raw_item_model.source_id,
                external_id=raw_item_model.external_id,
                raw_url=raw_item_model.raw_url,
                title=raw_item_model.title,
                content_text=raw_item_model.content_text,
                raw_content_hash=raw_item_model.raw_content_hash,
                fetched_at=raw_item_model.fetched_at,
                meta_json=raw_item_model.meta_json
            )
    
    def create_event_proposal(self, request: CreateEventProposalRequest) -> EventProposal:
        """Create a new event proposal from a raw item."""
        with self.get_session() as session:
            proposal = EventProposal(
                id=str(uuid4()),
                raw_item_id=request.raw_item_id,
                event_key=request.event_key,
                title=request.title,
                description=request.description,
                proposed_by=request.proposed_by,
                confidence_score=request.confidence_score,
                meta_json=request.meta_json
            )
            
            session.add(proposal)
            session.commit()
            session.refresh(proposal)
            return proposal
    
    def review_event_proposal(self, request: ReviewEventProposalRequest) -> EventProposal:
        """Review and update an event proposal."""
        with self.get_session() as session:
            proposal = session.query(EventProposal).filter_by(id=request.proposal_id).first()
            if not proposal:
                raise ValueError(f"Event proposal {request.proposal_id} not found")
            
            proposal.status = request.status
            proposal.reviewed_by = request.reviewed_by
            proposal.review_notes = request.review_notes
            proposal.reviewed_at = datetime.utcnow()
            
            # If accepted, create the event
            if request.status == ProposalStatus.ACCEPTED:
                event = Event(
                    id=str(uuid4()),
                    event_proposal_id=proposal.id,
                    key=proposal.event_key,
                    title=proposal.title,
                    description=proposal.description,
                    state=EventState.DRAFT
                )
                session.add(event)
            
            session.commit()
            session.refresh(proposal)
            return proposal
    
    def get_event_by_key(self, key: str) -> Optional[Event]:
        """Get an event by its canonical key."""
        with self.get_session() as session:
            return session.query(Event).filter_by(key=key).first()
    
    def update_event_state(self, event_id: str, new_state: EventState) -> Event:
        """Update an event's state."""
        with self.get_session() as session:
            event = session.query(Event).filter_by(id=event_id).first()
            if not event:
                raise ValueError(f"Event {event_id} not found")
            
            event.state = new_state
            event.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(event)
            return event

    # -------------------- Market Integration --------------------
    
    def add_market_listing(self, market_listing: MarketListing) -> MarketListing:
        """Add a market listing for an event."""
        with self.get_session() as session:
            market_listing.id = str(uuid4())
            session.add(market_listing)
            session.commit()
            session.refresh(market_listing)
            return market_listing
    
    def get_event_with_market_data(self, event_id: str) -> Optional[EventWithMarketData]:
        """Get an event with its market listings and outcome."""
        with self.get_session() as session:
            event = session.query(Event).filter_by(id=event_id).first()
            if not event:
                return None
            
            market_listings = session.query(MarketListing).filter_by(
                event_id=event_id, is_active=True
            ).all()
            
            outcome = session.query(Outcome).filter_by(event_id=event_id).first()
            
            # Convert SQLAlchemy models to Pydantic models
            from .types import Event as EventType, MarketListing as MarketListingType, Outcome as OutcomeType
            
            event_type = EventType(
                id=event.id,
                event_proposal_id=event.event_proposal_id,
                key=event.key,
                title=event.title,
                description=event.description,
                state=event.state,
                resolution_criteria=event.resolution_criteria,
                expected_resolution_date=event.expected_resolution_date,
                created_at=event.created_at,
                updated_at=event.updated_at,
                meta_json=event.meta_json
            )
            
            market_listing_types = []
            for listing in market_listings:
                market_listing_types.append(MarketListingType(
                    id=listing.id,
                    event_id=listing.event_id,
                    market_name=listing.market_name,
                    market_id=listing.market_id,
                    market_url=listing.market_url,
                    current_price=float(listing.current_price) if listing.current_price else None,
                    volume=listing.volume,
                    is_active=listing.is_active,
                    created_at=listing.created_at,
                    last_sync_at=listing.last_sync_at,
                    meta_json=listing.meta_json
                ))
            
            outcome_type = None
            if outcome:
                outcome_type = OutcomeType(
                    id=outcome.id,
                    event_id=outcome.event_id,
                    resolved=outcome.resolved,
                    outcome_value=outcome.outcome_value,
                    resolved_at=outcome.resolved_at,
                    resolution_source=outcome.resolution_source,
                    notes=outcome.notes,
                    created_at=outcome.created_at
                )
            
            return EventWithMarketData(
                event=event_type,
                market_listings=market_listing_types,
                outcome=outcome_type
            )

    # -------------------- Prediction Workflows --------------------
    
    def create_workflow_run(self, request: CreateWorkflowRunRequest) -> WorkflowRun:
        """Create a new workflow run for an event."""
        with self.get_session() as session:
            workflow_run = WorkflowRun(
                id=str(uuid4()),
                event_id=request.event_id,
                protocol_id=request.protocol_id,
                meta_json=request.meta_json
            )
            
            session.add(workflow_run)
            session.commit()
            session.refresh(workflow_run)
            return workflow_run
    
    def add_tool_call(self, tool_call: ToolCall) -> ToolCall:
        """Add a tool call to a workflow run."""
        with self.get_session() as session:
            from .models import ToolCall as ToolCallModel, WorkflowRun as WorkflowRunModel
            
            tool_call_model = ToolCallModel(
                id=str(uuid4()),
                workflow_run_id=tool_call.workflow_run_id,
                step_number=tool_call.step_number,
                tool_type=tool_call.tool_type,
                tool_name=tool_call.tool_name,
                args_json=tool_call.args_json,
                result_json=tool_call.result_json,
                tokens_in=tool_call.tokens_in,
                tokens_out=tool_call.tokens_out,
                cost_usd=tool_call.cost_usd,
                latency_ms=tool_call.latency_ms,
                success=tool_call.success,
                error_message=tool_call.error_message
            )
            
            session.add(tool_call_model)
            
            # Update workflow run totals
            workflow_run = session.query(WorkflowRunModel).filter_by(
                id=tool_call.workflow_run_id
            ).first()
            
            if workflow_run:
                workflow_run.total_tokens_in += tool_call.tokens_in
                workflow_run.total_tokens_out += tool_call.tokens_out
                workflow_run.total_cost_usd = float(workflow_run.total_cost_usd) + tool_call.cost_usd
                workflow_run.total_latency_ms += tool_call.latency_ms
            
            session.commit()
            session.refresh(tool_call_model)
            
            return ToolCall(
                id=tool_call_model.id,
                workflow_run_id=tool_call_model.workflow_run_id,
                step_number=tool_call_model.step_number,
                tool_type=ToolCallType(tool_call_model.tool_type),
                tool_name=tool_call_model.tool_name,
                args_json=tool_call_model.args_json,
                result_json=tool_call_model.result_json,
                tokens_in=tool_call_model.tokens_in,
                tokens_out=tool_call_model.tokens_out,
                cost_usd=tool_call_model.cost_usd,
                latency_ms=tool_call_model.latency_ms,
                success=tool_call_model.success,
                error_message=tool_call_model.error_message,
                created_at=tool_call_model.created_at
            )
    
    def complete_workflow_run(self, workflow_run_id: str) -> WorkflowRun:
        """Mark a workflow run as completed."""
        with self.get_session() as session:
            workflow_run = session.query(WorkflowRun).filter_by(id=workflow_run_id).first()
            if not workflow_run:
                raise ValueError(f"Workflow run {workflow_run_id} not found")
            
            workflow_run.status = "completed"
            workflow_run.ended_at = datetime.utcnow()
            
            session.commit()
            session.refresh(workflow_run)
            return workflow_run
    
    def create_prediction(self, request: CreatePredictionRequest) -> PredictionWithAttributions:
        """Create a prediction with attributions to raw items."""
        with self.get_session() as session:
            # Create the prediction
            prediction = Prediction(
                id=str(uuid4()),
                workflow_run_id=request.workflow_run_id,
                protocol_id=request.protocol_id,
                p=request.p,
                horizon_hours=request.horizon_hours,
                rationale=request.rationale
            )
            
            session.add(prediction)
            session.commit()
            session.refresh(prediction)
            
            # Create attributions
            attributions = []
            raw_items = []
            
            for rank, raw_item_id in enumerate(request.attribution_raw_item_ids):
                attribution = PredictionAttribution(
                    prediction_id=prediction.id,
                    raw_item_id=raw_item_id,
                    rank=rank
                )
                session.add(attribution)
                attributions.append(attribution)
                
                # Get the raw item
                raw_item = session.query(RawItem).filter_by(id=raw_item_id).first()
                if raw_item:
                    raw_items.append(raw_item)
            
            session.commit()
            
            # Convert SQLAlchemy models to Pydantic models
            from .types import Prediction as PredictionType, PredictionAttribution as AttributionType, RawItem as RawItemType
            
            prediction_type = PredictionType(
                id=prediction.id,
                workflow_run_id=prediction.workflow_run_id,
                protocol_id=prediction.protocol_id,
                p=float(prediction.p),
                horizon_hours=prediction.horizon_hours,
                rationale=prediction.rationale,
                created_at=prediction.created_at
            )
            
            attribution_types = []
            for attr in attributions:
                attribution_types.append(AttributionType(
                    prediction_id=attr.prediction_id,
                    raw_item_id=attr.raw_item_id,
                    rank=attr.rank,
                    relevance_score=float(attr.relevance_score) if attr.relevance_score else None,
                    created_at=attr.created_at
                ))
            
            raw_item_types = []
            for item in raw_items:
                raw_item_types.append(RawItemType(
                    id=item.id,
                    source_id=item.source_id,
                    external_id=item.external_id,
                    raw_url=item.raw_url,
                    title=item.title,
                    content_text=item.content_text,
                    raw_content_hash=item.raw_content_hash,
                    fetched_at=item.fetched_at,
                    meta_json=item.meta_json
                ))
            
            return PredictionWithAttributions(
                prediction=prediction_type,
                attributions=attribution_types,
                raw_items=raw_item_types
            )
    
    def get_workflow_run_with_details(self, workflow_run_id: str) -> Optional[WorkflowRunWithDetails]:
        """Get a workflow run with all its tool calls and predictions."""
        with self.get_session() as session:
            workflow_run = session.query(WorkflowRun).filter_by(id=workflow_run_id).first()
            if not workflow_run:
                return None
            
            tool_calls = session.query(ToolCall).filter_by(
                workflow_run_id=workflow_run_id
            ).order_by(ToolCall.step_number).all()
            
            predictions = session.query(Prediction).filter_by(
                workflow_run_id=workflow_run_id
            ).all()
            
            # Get predictions with attributions
            predictions_with_attributions = []
            for prediction in predictions:
                attributions = session.query(PredictionAttribution).filter_by(
                    prediction_id=prediction.id
                ).order_by(PredictionAttribution.rank).all()
                
                raw_items = []
                for attr in attributions:
                    raw_item = session.query(RawItem).filter_by(id=attr.raw_item_id).first()
                    if raw_item:
                        raw_items.append(raw_item)
                
                predictions_with_attributions.append(
                    PredictionWithAttributions(
                        prediction=prediction,
                        attributions=attributions,
                        raw_items=raw_items
                    )
                )
            
            return WorkflowRunWithDetails(
                workflow_run=workflow_run,
                tool_calls=tool_calls,
                predictions=predictions_with_attributions
            )

    # -------------------- Outcomes & Scoring --------------------
    
    def resolve_outcome(self, request: ResolveOutcomeRequest) -> Outcome:
        """Resolve an event outcome."""
        with self.get_session() as session:
            # Check if outcome already exists
            existing_outcome = session.query(Outcome).filter_by(event_id=request.event_id).first()
            
            if existing_outcome:
                existing_outcome.resolved = True
                existing_outcome.outcome_value = request.outcome_value
                existing_outcome.resolved_at = datetime.utcnow()
                existing_outcome.resolution_source = request.resolution_source
                existing_outcome.notes = request.notes
                outcome = existing_outcome
            else:
                outcome = Outcome(
                    id=str(uuid4()),
                    event_id=request.event_id,
                    resolved=True,
                    outcome_value=request.outcome_value,
                    resolved_at=datetime.utcnow(),
                    resolution_source=request.resolution_source,
                    notes=request.notes
                )
                session.add(outcome)
            
            # Update event state
            event = session.query(Event).filter_by(id=request.event_id).first()
            if event:
                event.state = EventState.RESOLVED
                event.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(outcome)
            return outcome
    
    def add_prediction_score(self, prediction_id: str, score_type: str, score_value: float, 
                           horizon_hours: Optional[int] = None) -> PredictionScore:
        """Add a performance score for a prediction."""
        with self.get_session() as session:
            score = PredictionScore(
                id=str(uuid4()),
                prediction_id=prediction_id,
                score_type=score_type,
                score_value=score_value,
                horizon_hours=horizon_hours
            )
            
            session.add(score)
            session.commit()
            session.refresh(score)
            return score

    # -------------------- Query Methods --------------------
    
    def get_events_by_state(self, state: EventState, limit: int = 100) -> List[Event]:
        """Get events by state."""
        with self.get_session() as session:
            return session.query(Event).filter_by(state=state).order_by(
                Event.updated_at.desc()
            ).limit(limit).all()
    
    def get_pending_proposals(self, limit: int = 100) -> List[EventProposal]:
        """Get pending event proposals."""
        with self.get_session() as session:
            return session.query(EventProposal).filter_by(
                status=ProposalStatus.PENDING
            ).order_by(EventProposal.created_at.desc()).limit(limit).all()
    
    def get_recent_predictions(self, limit: int = 100) -> List[PredictionWithAttributions]:
        """Get recent predictions with their attributions."""
        with self.get_session() as session:
            predictions = session.query(Prediction).order_by(
                Prediction.created_at.desc()
            ).limit(limit).all()
            
            result = []
            for prediction in predictions:
                attributions = session.query(PredictionAttribution).filter_by(
                    prediction_id=prediction.id
                ).order_by(PredictionAttribution.rank).all()
                
                raw_items = []
                for attr in attributions:
                    raw_item = session.query(RawItem).filter_by(id=attr.raw_item_id).first()
                    if raw_item:
                        raw_items.append(raw_item)
                
                # Convert SQLAlchemy models to Pydantic models
                from .types import Prediction as PredictionType, PredictionAttribution as AttributionType, RawItem as RawItemType
                
                prediction_type = PredictionType(
                    id=prediction.id,
                    workflow_run_id=prediction.workflow_run_id,
                    protocol_id=prediction.protocol_id,
                    p=float(prediction.p),
                    horizon_hours=prediction.horizon_hours,
                    rationale=prediction.rationale,
                    created_at=prediction.created_at
                )
                
                attribution_types = []
                for attr in attributions:
                    attribution_types.append(AttributionType(
                        prediction_id=attr.prediction_id,
                        raw_item_id=attr.raw_item_id,
                        rank=attr.rank,
                        relevance_score=float(attr.relevance_score) if attr.relevance_score else None,
                        created_at=attr.created_at
                    ))
                
                raw_item_types = []
                for item in raw_items:
                    raw_item_types.append(RawItemType(
                        id=item.id,
                        source_id=item.source_id,
                        external_id=item.external_id,
                        raw_url=item.raw_url,
                        title=item.title,
                        content_text=item.content_text,
                        raw_content_hash=item.raw_content_hash,
                        fetched_at=item.fetched_at,
                        meta_json=item.meta_json
                    ))
                
                result.append(
                    PredictionWithAttributions(
                        prediction=prediction_type,
                        attributions=attribution_types,
                        raw_items=raw_item_types
                    )
                )
            
            return result
    
    def get_protocol_performance(self, protocol_id: str, days: int = 30) -> Dict[str, Any]:
        """Get performance statistics for a protocol."""
        with self.get_session() as session:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get predictions with scores
            predictions = session.query(Prediction).filter(
                Prediction.protocol_id == protocol_id,
                Prediction.created_at >= cutoff_date
            ).all()
            
            if not predictions:
                return {
                    'protocol_id': protocol_id,
                    'period_days': days,
                    'total_predictions': 0,
                    'avg_brier_score': None,
                    'avg_logloss': None,
                    'calibration_bins': []
                }
            
            prediction_ids = [p.id for p in predictions]
            
            # Get scores
            scores = session.query(PredictionScore).filter(
                PredictionScore.prediction_id.in_(prediction_ids)
            ).all()
            
            # Calculate metrics
            brier_scores = [s.score_value for s in scores if s.score_type == 'brier']
            logloss_scores = [s.score_value for s in scores if s.score_type == 'logloss']
            
            return {
                'protocol_id': protocol_id,
                'period_days': days,
                'total_predictions': len(predictions),
                'avg_brier_score': sum(brier_scores) / len(brier_scores) if brier_scores else None,
                'avg_logloss': sum(logloss_scores) / len(logloss_scores) if logloss_scores else None,
                'calibration_bins': []  # TODO: Implement calibration binning
            }
    
    def add_agent_run(self, agent_run: AgentRun) -> AgentRun:
        """Add an agent run to the database."""
        with self.get_session() as session:
            from .models import AgentRun as AgentRunModel
            
            agent_run_model = AgentRunModel(
                id=agent_run.id,
                agent_type=agent_run.agent_type.value,
                input_json=agent_run.input_json,
                output_json=agent_run.output_json,
                tokens_in=agent_run.tokens_in,
                tokens_out=agent_run.tokens_out,
                cost_usd=agent_run.cost_usd,
                latency_ms=agent_run.latency_ms,
                started_at=agent_run.started_at,
                ended_at=agent_run.ended_at
            )
            
            session.add(agent_run_model)
            session.commit()
            session.refresh(agent_run_model)
            
            return AgentRun(
                id=agent_run_model.id,
                agent_type=AgentType(agent_run_model.agent_type),
                input_json=agent_run_model.input_json,
                output_json=agent_run_model.output_json,
                tokens_in=agent_run_model.tokens_in,
                tokens_out=agent_run_model.tokens_out,
                cost_usd=agent_run_model.cost_usd,
                latency_ms=agent_run_model.latency_ms,
                started_at=agent_run_model.started_at,
                ended_at=agent_run_model.ended_at
            )
