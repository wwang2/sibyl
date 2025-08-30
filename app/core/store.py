"""Database store implementation using SQLAlchemy."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text, create_engine,
    ForeignKey, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

from .types import (
    AgentRun, AgentType, Evidence, LLMInteraction, Prediction, PredictionEvidence,
    ProtoEvent, ProtoEventState, SourceType
)

Base = declarative_base()


class EvidenceModel(Base):
    """SQLAlchemy model for evidence."""
    __tablename__ = "evidence"
    
    id = Column(String, primary_key=True)
    source_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    snippet = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False, unique=True, index=True)
    first_seen_at = Column(DateTime, nullable=False, default=func.now())
    fetched_at = Column(DateTime, nullable=False, default=func.now())
    meta_json = Column(Text, nullable=False, default="{}")
    
    # Relationships
    prediction_evidence = relationship("PredictionEvidenceModel", back_populates="evidence")


class ProtoEventModel(Base):
    """SQLAlchemy model for proto events."""
    __tablename__ = "proto_events"
    
    id = Column(String, primary_key=True)
    key = Column(String, nullable=False, index=True)
    state = Column(String, nullable=False, default="new")
    first_seen_at = Column(DateTime, nullable=False, default=func.now())
    last_update_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    predictions = relationship("PredictionModel", back_populates="proto_event")


class PredictionModel(Base):
    """SQLAlchemy model for predictions."""
    __tablename__ = "predictions"
    
    id = Column(String, primary_key=True)
    proto_event_id = Column(String, ForeignKey("proto_events.id"), nullable=False)
    p = Column(Float, nullable=False)
    ttc_hours = Column(Integer, nullable=True)
    rationale = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    proto_event = relationship("ProtoEventModel", back_populates="predictions")
    prediction_evidence = relationship("PredictionEvidenceModel", back_populates="prediction")


class AgentRunModel(Base):
    """SQLAlchemy model for agent runs."""
    __tablename__ = "agent_runs"
    
    id = Column(String, primary_key=True)
    agent_type = Column(String, nullable=False)
    input_json = Column(Text, nullable=False, default="{}")
    output_json = Column(Text, nullable=False, default="{}")
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False, default=func.now())
    ended_at = Column(DateTime, nullable=True)


class PredictionEvidenceModel(Base):
    """SQLAlchemy model for prediction-evidence links."""
    __tablename__ = "prediction_evidence"
    
    prediction_id = Column(String, ForeignKey("predictions.id"), primary_key=True)
    evidence_id = Column(String, ForeignKey("evidence.id"), primary_key=True)
    rank = Column(Integer, nullable=False, default=0)
    
    # Relationships
    prediction = relationship("PredictionModel", back_populates="prediction_evidence")
    evidence = relationship("EvidenceModel", back_populates="prediction_evidence")


class LLMInteractionModel(Base):
    """SQLAlchemy model for detailed LLM interactions."""
    __tablename__ = "llm_interactions"
    
    id = Column(String, primary_key=True)
    agent_run_id = Column(String, ForeignKey("agent_runs.id"), nullable=False)
    model_name = Column(String, nullable=False)
    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=False, default=0)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    meta_json = Column(Text, nullable=False, default="{}")
    
    # Relationships
    agent_run = relationship("AgentRunModel")


class Store:
    """Database store for the agentic event discovery system."""
    
    def __init__(self, db_url: str):
        """Initialize the store with a database URL."""
        self.engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    @classmethod
    def from_env(cls) -> "Store":
        """Create a store instance from environment variables."""
        import os
        db_url = os.getenv("DB_URL", "sqlite:///./local.db")
        return cls(db_url)
    
    def create_all(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get a database session."""
        return self.SessionLocal()
    
    def add_evidence(self, evidence: Evidence) -> Evidence:
        """Add evidence to the database."""
        with self.get_session() as session:
            # Check if evidence already exists by content_hash
            existing = session.query(EvidenceModel).filter_by(
                content_hash=evidence.content_hash
            ).first()
            
            if existing:
                return Evidence(
                    id=existing.id,
                    source_type=SourceType(existing.source_type),
                    url=existing.url,
                    title=existing.title,
                    snippet=existing.snippet,
                    content_hash=existing.content_hash,
                    first_seen_at=existing.first_seen_at,
                    fetched_at=existing.fetched_at,
                    meta_json=json.loads(existing.meta_json)
                )
            
            # Create new evidence
            evidence_model = EvidenceModel(
                id=evidence.id,
                source_type=evidence.source_type.value,
                url=evidence.url,
                title=evidence.title,
                snippet=evidence.snippet,
                content_hash=evidence.content_hash,
                first_seen_at=evidence.first_seen_at,
                fetched_at=evidence.fetched_at,
                meta_json=json.dumps(evidence.meta_json)
            )
            
            session.add(evidence_model)
            session.commit()
            session.refresh(evidence_model)
            
            return Evidence(
                id=evidence_model.id,
                source_type=SourceType(evidence_model.source_type),
                url=evidence_model.url,
                title=evidence_model.title,
                snippet=evidence_model.snippet,
                content_hash=evidence_model.content_hash,
                first_seen_at=evidence_model.first_seen_at,
                fetched_at=evidence_model.fetched_at,
                meta_json=json.loads(evidence_model.meta_json)
            )
    
    def get_or_create_proto_event(self, key: str) -> ProtoEvent:
        """Get or create a proto event by key."""
        with self.get_session() as session:
            existing = session.query(ProtoEventModel).filter_by(key=key).first()
            
            if existing:
                return ProtoEvent(
                    id=existing.id,
                    key=existing.key,
                    state=ProtoEventState(existing.state),
                    first_seen_at=existing.first_seen_at,
                    last_update_at=existing.last_update_at
                )
            
            # Create new proto event
            proto_event_model = ProtoEventModel(
                id=str(uuid4()),
                key=key,
                state=ProtoEventState.NEW.value,
                first_seen_at=datetime.utcnow(),
                last_update_at=datetime.utcnow()
            )
            
            session.add(proto_event_model)
            session.commit()
            session.refresh(proto_event_model)
            
            return ProtoEvent(
                id=proto_event_model.id,
                key=proto_event_model.key,
                state=ProtoEventState(proto_event_model.state),
                first_seen_at=proto_event_model.first_seen_at,
                last_update_at=proto_event_model.last_update_at
            )
    
    def update_proto_event(self, proto_event: ProtoEvent):
        """Update a proto event."""
        with self.get_session() as session:
            model = session.query(ProtoEventModel).filter_by(id=proto_event.id).first()
            if model:
                model.state = proto_event.state.value
                model.last_update_at = datetime.utcnow()
                session.commit()
    
    def add_prediction(self, prediction: Prediction) -> Prediction:
        """Add a prediction to the database."""
        with self.get_session() as session:
            prediction_model = PredictionModel(
                id=prediction.id,
                proto_event_id=prediction.proto_event_id,
                p=prediction.p,
                ttc_hours=prediction.ttc_hours,
                rationale=prediction.rationale,
                created_at=prediction.created_at
            )
            
            session.add(prediction_model)
            session.commit()
            session.refresh(prediction_model)
            
            return Prediction(
                id=prediction_model.id,
                proto_event_id=prediction_model.proto_event_id,
                p=prediction_model.p,
                ttc_hours=prediction_model.ttc_hours,
                rationale=prediction_model.rationale,
                created_at=prediction_model.created_at
            )
    
    def link_prediction_evidence(self, prediction_id: str, evidence_ids: List[str]):
        """Link a prediction to evidence."""
        with self.get_session() as session:
            for rank, evidence_id in enumerate(evidence_ids):
                link = PredictionEvidenceModel(
                    prediction_id=prediction_id,
                    evidence_id=evidence_id,
                    rank=rank
                )
                session.add(link)
            session.commit()
    
    def add_agent_run(self, agent_run: AgentRun) -> AgentRun:
        """Add an agent run to the database."""
        with self.get_session() as session:
            agent_run_model = AgentRunModel(
                id=agent_run.id,
                agent_type=agent_run.agent_type.value,
                input_json=json.dumps(agent_run.input_json),
                output_json=json.dumps(agent_run.output_json),
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
                input_json=json.loads(agent_run_model.input_json),
                output_json=json.loads(agent_run_model.output_json),
                tokens_in=agent_run_model.tokens_in,
                tokens_out=agent_run_model.tokens_out,
                cost_usd=agent_run_model.cost_usd,
                latency_ms=agent_run_model.latency_ms,
                started_at=agent_run_model.started_at,
                ended_at=agent_run_model.ended_at
            )
    
    def get_recent_evidence_for_proto_event(self, proto_event_id: str, limit: int = 10) -> List[Evidence]:
        """Get recent evidence for a proto event."""
        with self.get_session() as session:
            # This is a simplified implementation - in practice, you'd need to
            # link evidence to proto events through some mechanism
            evidence_models = session.query(EvidenceModel).order_by(
                EvidenceModel.fetched_at.desc()
            ).limit(limit).all()
            
            return [
                Evidence(
                    id=model.id,
                    source_type=SourceType(model.source_type),
                    url=model.url,
                    title=model.title,
                    snippet=model.snippet,
                    content_hash=model.content_hash,
                    first_seen_at=model.first_seen_at,
                    fetched_at=model.fetched_at,
                    meta_json=json.loads(model.meta_json)
                )
                for model in evidence_models
            ]
    
    def add_llm_interaction(self, llm_interaction: LLMInteraction) -> LLMInteraction:
        """Add an LLM interaction to the database."""
        with self.get_session() as session:
            llm_interaction_model = LLMInteractionModel(
                id=llm_interaction.id,
                agent_run_id=llm_interaction.agent_run_id,
                model_name=llm_interaction.model_name,
                prompt_text=llm_interaction.prompt_text,
                response_text=llm_interaction.response_text,
                tokens_in=llm_interaction.tokens_in,
                tokens_out=llm_interaction.tokens_out,
                cost_usd=llm_interaction.cost_usd,
                latency_ms=llm_interaction.latency_ms,
                success=llm_interaction.success,
                error_message=llm_interaction.error_message,
                created_at=llm_interaction.created_at,
                meta_json=json.dumps(llm_interaction.metadata)
            )
            
            session.add(llm_interaction_model)
            session.commit()
            session.refresh(llm_interaction_model)
            
            return LLMInteraction(
                id=llm_interaction_model.id,
                agent_run_id=llm_interaction_model.agent_run_id,
                model_name=llm_interaction_model.model_name,
                prompt_text=llm_interaction_model.prompt_text,
                response_text=llm_interaction_model.response_text,
                tokens_in=llm_interaction_model.tokens_in,
                tokens_out=llm_interaction_model.tokens_out,
                cost_usd=llm_interaction_model.cost_usd,
                latency_ms=llm_interaction_model.latency_ms,
                success=llm_interaction_model.success,
                error_message=llm_interaction_model.error_message,
                created_at=llm_interaction_model.created_at,
                metadata=json.loads(llm_interaction_model.meta_json)
            )
    
    def get_llm_interactions_by_agent_run(self, agent_run_id: str) -> List[LLMInteraction]:
        """Get all LLM interactions for a specific agent run."""
        with self.get_session() as session:
            models = session.query(LLMInteractionModel).filter_by(
                agent_run_id=agent_run_id
            ).order_by(LLMInteractionModel.created_at).all()
            
            return [
                LLMInteraction(
                    id=model.id,
                    agent_run_id=model.agent_run_id,
                    model_name=model.model_name,
                    prompt_text=model.prompt_text,
                    response_text=model.response_text,
                    tokens_in=model.tokens_in,
                    tokens_out=model.tokens_out,
                    cost_usd=model.cost_usd,
                    latency_ms=model.latency_ms,
                    success=model.success,
                    error_message=model.error_message,
                    created_at=model.created_at,
                    metadata=json.loads(model.meta_json)
                )
                for model in models
            ]
    
    def get_llm_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get LLM usage statistics for the last N days."""
        with self.get_session() as session:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Total interactions
            total_interactions = session.query(LLMInteractionModel).filter(
                LLMInteractionModel.created_at >= cutoff_date
            ).count()
            
            # Successful interactions
            successful_interactions = session.query(LLMInteractionModel).filter(
                LLMInteractionModel.created_at >= cutoff_date,
                LLMInteractionModel.success == True
            ).count()
            
            # Total tokens and cost
            stats = session.query(
                func.sum(LLMInteractionModel.tokens_in).label('total_tokens_in'),
                func.sum(LLMInteractionModel.tokens_out).label('total_tokens_out'),
                func.sum(LLMInteractionModel.cost_usd).label('total_cost'),
                func.avg(LLMInteractionModel.latency_ms).label('avg_latency')
            ).filter(
                LLMInteractionModel.created_at >= cutoff_date
            ).first()
            
            # Model usage breakdown
            model_usage = session.query(
                LLMInteractionModel.model_name,
                func.count(LLMInteractionModel.id).label('count'),
                func.sum(LLMInteractionModel.cost_usd).label('cost')
            ).filter(
                LLMInteractionModel.created_at >= cutoff_date
            ).group_by(LLMInteractionModel.model_name).all()
            
            return {
                'period_days': days,
                'total_interactions': total_interactions,
                'successful_interactions': successful_interactions,
                'success_rate': successful_interactions / total_interactions if total_interactions > 0 else 0,
                'total_tokens_in': stats.total_tokens_in or 0,
                'total_tokens_out': stats.total_tokens_out or 0,
                'total_cost_usd': float(stats.total_cost or 0),
                'avg_latency_ms': float(stats.avg_latency or 0),
                'model_usage': [
                    {
                        'model': usage.model_name,
                        'count': usage.count,
                        'cost_usd': float(usage.cost or 0)
                    }
                    for usage in model_usage
                ]
            }
