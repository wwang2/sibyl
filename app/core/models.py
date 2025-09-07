"""SQLAlchemy 2.x typed ORM models for Sybil data system - Event Sourcing Version.

This module defines the canonical data model using SQLAlchemy 2.x with type annotations.
The ORM models are the source of truth - DDL is generated via Alembic from these models.

Key Changes from v1:
- Removed Evidence layer - predictions link directly to RawItems via PredictionAttribution
- Added Event Sourcing pattern: RawItems → EventProposals → Events
- Added WorkflowRun and ToolCall for full reasoning transparency
- Added MarketListing for external market integration
- Simplified prediction attribution to direct RawItem links
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, Boolean
)
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# -------------------- Enums --------------------
class SourceType(str, Enum):
    """Types of data sources."""
    RSS = "rss"
    PRWIRES = "prwires"
    EDGAR = "edgar"
    CUSTOM = "custom"


class EventState(str, Enum):
    """States of events in their lifecycle."""
    DRAFT = "draft"
    ACTIVE = "active"
    LOCKED = "locked"
    RESOLVED = "resolved"
    CANCELED = "canceled"
    ARCHIVED = "archived"


class ProposalStatus(str, Enum):
    """Status of event proposals."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MERGED = "merged"


class ProtocolKind(str, Enum):
    """Types of prediction protocols."""
    AGENT = "agent"
    RANDOM = "random"
    HEURISTIC = "heuristic"
    HUMAN = "human"


class ToolCallType(str, Enum):
    """Types of tool calls in workflows."""
    LLM = "llm"
    API = "api"
    SEARCH = "search"
    CALCULATION = "calculation"
    DATA_FETCH = "data_fetch"


# -------------------- Core Event Sourcing Entities --------------------
class Source(Base):
    """Data source configuration and metadata."""
    __tablename__ = "sources"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False)
    fetch_config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_fetch_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    health_status: Mapped[Optional[str]] = mapped_column(String(20), default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    raw_items: Mapped[List[RawItem]] = relationship(back_populates="source")


class RawItem(Base):
    """Raw data items from sources before processing."""
    __tablename__ = "raw_items"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(512))
    raw_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    content_text: Mapped[Optional[str]] = mapped_column(Text)
    raw_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    source: Mapped[Source] = relationship(back_populates="raw_items")
    event_proposals: Mapped[List[EventProposal]] = relationship(back_populates="raw_item", cascade="all, delete-orphan")
    prediction_attributions: Mapped[List[PredictionAttribution]] = relationship(back_populates="raw_item", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_rawitem_source_extid"),
        Index("idx_raw_items_source_id", "source_id"),
        Index("idx_raw_items_hash", "raw_content_hash"),
        Index("idx_raw_items_fetched_at", "fetched_at"),
    )


class EventProposal(Base):
    """Candidate events mined from raw items by agents."""
    __tablename__ = "event_proposals"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    raw_item_id: Mapped[str] = mapped_column(ForeignKey("raw_items.id"), nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)  # Canonical key for grouping
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_by: Mapped[str] = mapped_column(String(50), nullable=False)  # agent_name or "human"
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(3,2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(50))
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    raw_item: Mapped[RawItem] = relationship(back_populates="event_proposals")
    event: Mapped[Optional[Event]] = relationship(back_populates="event_proposal")

    __table_args__ = (
        Index("idx_event_proposals_status", "status"),
        Index("idx_event_proposals_event_key", "event_key"),
        Index("idx_event_proposals_created_at", "created_at"),
        CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name="ck_proposal_confidence_range"),
    )


class Event(Base):
    """Canonical events after moderation and acceptance."""
    __tablename__ = "events"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_proposal_id: Mapped[Optional[str]] = mapped_column(ForeignKey("event_proposals.id"))
    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)  # Canonical key
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[EventState] = mapped_column(SAEnum(EventState), default=EventState.DRAFT, nullable=False)
    resolution_criteria: Mapped[Optional[str]] = mapped_column(Text)  # How to determine outcome
    expected_resolution_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    event_proposal: Mapped[Optional[EventProposal]] = relationship(back_populates="event")
    market_listings: Mapped[List[MarketListing]] = relationship(back_populates="event", cascade="all, delete-orphan")
    workflow_runs: Mapped[List[WorkflowRun]] = relationship(back_populates="event", cascade="all, delete-orphan")
    outcome: Mapped[Optional[Outcome]] = relationship(back_populates="event", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_events_key", "key"),
        Index("idx_events_state", "state"),
        Index("idx_events_updated_at", "updated_at"),
    )


class MarketListing(Base):
    """External market representations of events (Kalshi, Polymarket, etc.)."""
    __tablename__ = "market_listings"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False)
    market_name: Mapped[str] = mapped_column(String(50), nullable=False)  # "kalshi", "polymarket"
    market_id: Mapped[str] = mapped_column(String(100), nullable=False)  # External market ID
    market_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Numeric(3,2))  # Current market price
    volume: Mapped[Optional[int]] = mapped_column(Integer)  # Trading volume
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    event: Mapped[Event] = relationship(back_populates="market_listings")

    __table_args__ = (
        UniqueConstraint("market_name", "market_id", name="uq_market_listing_name_id"),
        Index("idx_market_listings_event_id", "event_id"),
        Index("idx_market_listings_market_name", "market_name"),
        CheckConstraint("current_price >= 0.0 AND current_price <= 1.0", name="ck_market_price_range"),
    )


# -------------------- Prediction Workflow Entities --------------------
class Protocol(Base):
    """Prediction protocols (agent/random/heuristic/human)."""
    __tablename__ = "protocols"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[ProtocolKind] = mapped_column(SAEnum(ProtocolKind), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    predictions: Mapped[List[Prediction]] = relationship(back_populates="protocol")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_protocol_name_version"),
    )


class WorkflowRun(Base):
    """Full reasoning trace for producing predictions."""
    __tablename__ = "workflow_runs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False)
    protocol_id: Mapped[str] = mapped_column(ForeignKey("protocols.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # running/completed/failed
    total_tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(10,4), default=0.0, nullable=False)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    event: Mapped[Event] = relationship(back_populates="workflow_runs")
    protocol: Mapped[Protocol] = relationship()
    tool_calls: Mapped[List[ToolCall]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")
    predictions: Mapped[List[Prediction]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_workflow_runs_event_id", "event_id"),
        Index("idx_workflow_runs_protocol_id", "protocol_id"),
        Index("idx_workflow_runs_started_at", "started_at"),
    )


class ToolCall(Base):
    """Individual steps in workflow execution."""
    __tablename__ = "tool_calls"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_type: Mapped[ToolCallType] = mapped_column(SAEnum(ToolCallType), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    args_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10,4), default=0.0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success: Mapped[bool] = mapped_column(default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="tool_calls")

    __table_args__ = (
        Index("idx_tool_calls_workflow_run_id", "workflow_run_id"),
        Index("idx_tool_calls_step_number", "step_number"),
        Index("idx_tool_calls_tool_type", "tool_type"),
    )


class Prediction(Base):
    """Predictions with full workflow attribution."""
    __tablename__ = "predictions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False)
    protocol_id: Mapped[str] = mapped_column(ForeignKey("protocols.id"), nullable=False)
    p: Mapped[float] = mapped_column(Numeric(3,2), nullable=False)  # Probability
    horizon_hours: Mapped[Optional[int]] = mapped_column(Integer)  # How far into the future
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="predictions")
    protocol: Mapped[Protocol] = relationship(back_populates="predictions")
    attributions: Mapped[List[PredictionAttribution]] = relationship(back_populates="prediction", cascade="all, delete-orphan")
    scores: Mapped[List[PredictionScore]] = relationship(back_populates="prediction", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_predictions_workflow_run_id", "workflow_run_id"),
        Index("idx_predictions_protocol_id", "protocol_id"),
        Index("idx_predictions_created_at", "created_at"),
        Index("idx_predictions_p", "p"),
        CheckConstraint("p >= 0.0 AND p <= 1.0", name="ck_prediction_p_range"),
    )


class PredictionAttribution(Base):
    """Ranked links between predictions and supporting raw items."""
    __tablename__ = "prediction_attributions"
    
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.id"), primary_key=True)
    raw_item_id: Mapped[str] = mapped_column(ForeignKey("raw_items.id"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Ranking of importance
    relevance_score: Mapped[Optional[float]] = mapped_column(Numeric(3,2))  # AI-generated relevance score
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    prediction: Mapped[Prediction] = relationship(back_populates="attributions")
    raw_item: Mapped[RawItem] = relationship(back_populates="prediction_attributions")

    __table_args__ = (
        Index("idx_pred_attr_prediction_id", "prediction_id"),
        Index("idx_pred_attr_raw_item_id", "raw_item_id"),
        Index("idx_pred_attr_rank", "rank"),
        CheckConstraint("relevance_score >= 0.0 AND relevance_score <= 1.0", name="ck_attr_relevance_range"),
    )


# -------------------- Scoring & Outcomes --------------------
class Outcome(Base):
    """Resolved outcomes for events."""
    __tablename__ = "outcomes"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False)
    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)
    outcome_value: Mapped[Optional[str]] = mapped_column(String(20))  # 'true'/'false' or label
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_source: Mapped[Optional[str]] = mapped_column(String(50))  # edgar/press_release/manual
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    event: Mapped[Event] = relationship(back_populates="outcome")

    __table_args__ = (
        Index("idx_outcomes_event_id", "event_id"),
        Index("idx_outcomes_resolved_at", "resolved_at"),
    )


class PredictionScore(Base):
    """Performance scores for predictions."""
    __tablename__ = "prediction_scores"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.id"), nullable=False)
    score_type: Mapped[str] = mapped_column(String(20), nullable=False)  # brier/logloss/calibration
    score_value: Mapped[float] = mapped_column(Numeric(10,6), nullable=False)
    asof: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    horizon_hours: Mapped[Optional[int]] = mapped_column(Integer)

    prediction: Mapped[Prediction] = relationship(back_populates="scores")

    __table_args__ = (
        Index("idx_prediction_scores_prediction_id", "prediction_id"),
        Index("idx_prediction_scores_type", "score_type"),
        Index("idx_prediction_scores_asof", "asof"),
    )


# -------------------- Agent Models --------------------
class AgentRun(Base):
    """Agent execution records for telemetry."""
    __tablename__ = "agent_runs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)  # discovery/assessor
    input_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10,4), default=0.0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_agent_runs_type", "agent_type"),
        Index("idx_agent_runs_started_at", "started_at"),
    )
