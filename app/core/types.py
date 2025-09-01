"""Core data types and Pydantic models for the event sourcing prediction system.

This module provides Pydantic models for API serialization and validation.
The canonical data model is defined in models_v2.py using SQLAlchemy ORM.

Key Changes from v1:
- Removed Evidence layer - predictions link directly to RawItems via PredictionAttribution
- Added Event Sourcing pattern: RawItems → EventProposals → Events
- Added WorkflowRun and ToolCall for full reasoning transparency
- Added MarketListing for external market integration
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Types of data sources."""
    RSS = "rss"
    PRWIRES = "prwires"
    EDGAR = "edgar"
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
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


class AgentType(str, Enum):
    """Types of agents."""
    DISCOVERY = "discovery"
    ASSESSOR = "assessor"


# -------------------- Core Event Sourcing Models --------------------
class Source(BaseModel):
    """Data source configuration."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    name: str
    source_type: SourceType
    endpoint: str
    fetch_config_json: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    last_fetch_at: Optional[datetime] = None
    health_status: Optional[str] = "ok"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RawItem(BaseModel):
    """Raw data item from a source."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    external_id: Optional[str] = None
    raw_url: str
    title: Optional[str] = None
    content_text: Optional[str] = None
    raw_content_hash: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    meta_json: Dict[str, Any] = Field(default_factory=dict)


class EventProposal(BaseModel):
    """Candidate event mined from raw items by agents."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    raw_item_id: str
    event_key: str  # Canonical key for grouping
    title: str
    description: str
    proposed_by: str  # agent_name or "human"
    status: ProposalStatus = ProposalStatus.PENDING
    confidence_score: Optional[float] = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    meta_json: Dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    """Canonical event after moderation and acceptance."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    event_proposal_id: Optional[str] = None
    key: str  # Canonical key
    title: str
    description: str
    state: EventState = EventState.DRAFT
    resolution_criteria: Optional[str] = None  # How to determine outcome
    expected_resolution_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    meta_json: Dict[str, Any] = Field(default_factory=dict)


class MarketListing(BaseModel):
    """External market representation of an event."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    event_id: str
    market_name: str  # "kalshi", "polymarket"
    market_id: str  # External market ID
    market_url: str
    current_price: Optional[float] = Field(ge=0.0, le=1.0)
    volume: Optional[int] = Field(ge=0)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_sync_at: Optional[datetime] = None
    meta_json: Dict[str, Any] = Field(default_factory=dict)


# -------------------- Prediction Workflow Models --------------------
class Protocol(BaseModel):
    """Prediction protocol definition."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    name: str
    kind: ProtocolKind
    version: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowRun(BaseModel):
    """Full reasoning trace for producing predictions."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    event_id: str
    protocol_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    status: str = "running"  # running/completed/failed
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    meta_json: Dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Individual step in workflow execution."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    workflow_run_id: str
    step_number: int = Field(ge=1)
    tool_type: ToolCallType
    tool_name: str
    args_json: Dict[str, Any] = Field(default_factory=dict)
    result_json: Dict[str, Any] = Field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Prediction(BaseModel):
    """A prediction about an event with full workflow attribution."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    workflow_run_id: str
    protocol_id: str
    p: float = Field(ge=0.0, le=1.0)  # Probability
    horizon_hours: Optional[int] = Field(ge=0)  # How far into the future
    rationale: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PredictionAttribution(BaseModel):
    """Ranked link between prediction and supporting raw item."""
    prediction_id: str
    raw_item_id: str
    rank: int = 0  # Ranking of importance
    relevance_score: Optional[float] = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# -------------------- Scoring & Outcomes --------------------
class Outcome(BaseModel):
    """Resolved outcome for an event."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    event_id: str
    resolved: bool = False
    outcome_value: Optional[str] = None  # 'true'/'false' or label
    resolved_at: Optional[datetime] = None
    resolution_source: Optional[str] = None  # edgar/press_release/manual
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PredictionScore(BaseModel):
    """Performance score for a prediction."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    prediction_id: str
    score_type: str  # brier/logloss/calibration
    score_value: float
    asof: datetime = Field(default_factory=datetime.utcnow)
    horizon_hours: Optional[int] = Field(ge=0)


# -------------------- API Request/Response Models --------------------
class CreateEventProposalRequest(BaseModel):
    """Request to create a new event proposal."""
    raw_item_id: str
    event_key: str
    title: str
    description: str
    proposed_by: str
    confidence_score: Optional[float] = Field(ge=0.0, le=1.0)
    meta_json: Dict[str, Any] = Field(default_factory=dict)


class ReviewEventProposalRequest(BaseModel):
    """Request to review an event proposal."""
    proposal_id: str
    status: ProposalStatus
    reviewed_by: str
    review_notes: Optional[str] = None


class CreateWorkflowRunRequest(BaseModel):
    """Request to create a new workflow run."""
    event_id: str
    protocol_id: str
    meta_json: Dict[str, Any] = Field(default_factory=dict)


class AddToolCallRequest(BaseModel):
    """Request to add a tool call to a workflow run."""
    workflow_run_id: str
    step_number: int = Field(ge=1)
    tool_type: ToolCallType
    tool_name: str
    args_json: Dict[str, Any] = Field(default_factory=dict)
    result_json: Dict[str, Any] = Field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error_message: Optional[str] = None


class CreatePredictionRequest(BaseModel):
    """Request to create a new prediction."""
    workflow_run_id: str
    protocol_id: str
    p: float = Field(ge=0.0, le=1.0)
    horizon_hours: Optional[int] = Field(ge=0)
    rationale: str
    attribution_raw_item_ids: List[str] = Field(default_factory=list)  # Raw items to attribute


class ResolveOutcomeRequest(BaseModel):
    """Request to resolve an event outcome."""
    event_id: str
    outcome_value: str
    resolution_source: str
    notes: Optional[str] = None


# -------------------- Response Models --------------------
class EventWithProposals(BaseModel):
    """Event with its associated proposals."""
    event: Event
    proposals: List[EventProposal]


class PredictionWithAttributions(BaseModel):
    """Prediction with its supporting raw item attributions."""
    prediction: Prediction
    attributions: List[PredictionAttribution]
    raw_items: List[RawItem]


class WorkflowRunWithDetails(BaseModel):
    """Workflow run with all its tool calls and predictions."""
    workflow_run: WorkflowRun
    tool_calls: List[ToolCall]
    predictions: List[PredictionWithAttributions]


class EventWithMarketData(BaseModel):
    """Event with its market listings."""
    event: Event
    market_listings: List[MarketListing]
    outcome: Optional[Outcome] = None


# -------------------- Agent Models --------------------
class AgentRun(BaseModel):
    """Record of an agent execution."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    input_json: Dict[str, Any] = Field(default_factory=dict)
    output_json: Dict[str, Any] = Field(default_factory=dict)
    meta_json: Dict[str, Any] = Field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


class LLMResponse(BaseModel):
    """Response from LLM for prediction assessment."""
    p: float = Field(ge=0.0, le=1.0)
    ttc_hours: Optional[int] = Field(ge=0)
    rationale: str
    used_evidence_ids: List[str] = Field(default_factory=list)


class LLMInteraction(BaseModel):
    """Detailed record of an LLM interaction for audit purposes."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    agent_run_id: str
    model_name: str
    prompt_text: str
    response_text: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    meta_json: Dict[str, Any] = Field(default_factory=dict)
