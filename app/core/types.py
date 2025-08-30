"""Core data types and models for the agentic event discovery system."""

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


class ProtoEventState(str, Enum):
    """States of proto events."""
    NEW = "new"
    UPDATED = "updated"
    STABLE = "stable"
    ARCHIVED = "archived"


class AgentType(str, Enum):
    """Types of agents."""
    DISCOVERY = "discovery"
    ASSESSOR = "assessor"


class Evidence(BaseModel):
    """Evidence from a data source."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    source_type: SourceType
    url: str
    title: str
    snippet: str
    content_hash: str
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    meta_json: Dict[str, Any] = Field(default_factory=dict)


class ProtoEvent(BaseModel):
    """A proto event that may become a prediction."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    key: str  # Canonical key for grouping related evidence
    state: ProtoEventState = ProtoEventState.NEW
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_update_at: datetime = Field(default_factory=datetime.utcnow)


class Prediction(BaseModel):
    """A prediction about a proto event."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    proto_event_id: str
    p: float = Field(ge=0.0, le=1.0)  # Probability
    ttc_hours: Optional[int] = Field(ge=0)  # Time to completion in hours
    rationale: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRun(BaseModel):
    """Record of an agent execution."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    input_json: Dict[str, Any] = Field(default_factory=dict)
    output_json: Dict[str, Any] = Field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


class PredictionEvidence(BaseModel):
    """Link between predictions and evidence."""
    prediction_id: str
    evidence_id: str
    rank: int = 0


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
    metadata: Dict[str, Any] = Field(default_factory=dict)
