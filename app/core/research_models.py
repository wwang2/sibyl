"""
Research and Evidence Chain Models

This module defines the data structures for research evidence chains and predictions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class EvidenceType(Enum):
    """Types of evidence that can be collected."""
    NEWS_ARTICLE = "news_article"
    OFFICIAL_STATEMENT = "official_statement"
    MARKET_DATA = "market_data"
    EXPERT_OPINION = "expert_opinion"
    HISTORICAL_DATA = "historical_data"
    SOCIAL_MEDIA = "social_media"
    RESEARCH_PAPER = "research_paper"
    GOVERNMENT_DATA = "government_data"


class EvidenceReliability(Enum):
    """Reliability levels for evidence."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PredictionConfidence(Enum):
    """Confidence levels for predictions."""
    VERY_HIGH = "very_high"  # 90-100%
    HIGH = "high"           # 70-89%
    MEDIUM = "medium"       # 50-69%
    LOW = "low"            # 30-49%
    VERY_LOW = "very_low"   # 0-29%


@dataclass
class EvidenceSource:
    """Represents a source of evidence."""
    url: str
    title: str
    domain: str
    content: str
    published_date: Optional[datetime] = None
    author: Optional[str] = None
    source_type: EvidenceType = EvidenceType.NEWS_ARTICLE
    reliability: EvidenceReliability = EvidenceReliability.MEDIUM
    relevance_score: float = 0.0  # 0.0 to 1.0
    credibility_score: float = 0.0  # 0.0 to 1.0


@dataclass
class Evidence:
    """Represents a piece of evidence in the chain."""
    id: str
    source: EvidenceSource
    extracted_fact: str
    supporting_claim: str
    evidence_type: EvidenceType
    reliability: EvidenceReliability
    relevance_to_event: float  # 0.0 to 1.0
    confidence_in_fact: float  # 0.0 to 1.0
    extracted_at: datetime = field(default_factory=datetime.utcnow)
    supporting_evidence: List[str] = field(default_factory=list)  # IDs of supporting evidence
    contradicting_evidence: List[str] = field(default_factory=list)  # IDs of contradicting evidence


@dataclass
class EvidenceChain:
    """Represents a chain of evidence leading to a conclusion."""
    event_id: str
    research_query: str
    evidence_items: List[Evidence] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence to the chain."""
        self.evidence_items.append(evidence)
        self.updated_at = datetime.utcnow()
    
    def get_high_reliability_evidence(self) -> List[Evidence]:
        """Get evidence with high reliability."""
        return [e for e in self.evidence_items if e.reliability == EvidenceReliability.HIGH]
    
    def get_contradicting_evidence(self) -> List[Evidence]:
        """Get evidence that contradicts other evidence."""
        contradicting = []
        for evidence in self.evidence_items:
            if evidence.contradicting_evidence:
                contradicting.append(evidence)
        return contradicting
    
    def calculate_evidence_strength(self) -> float:
        """Calculate overall strength of evidence chain."""
        if not self.evidence_items:
            return 0.0
        
        total_weight = 0.0
        total_score = 0.0
        
        for evidence in self.evidence_items:
            # Weight by reliability and relevance
            reliability_weight = {
                EvidenceReliability.HIGH: 1.0,
                EvidenceReliability.MEDIUM: 0.7,
                EvidenceReliability.LOW: 0.4
            }[evidence.reliability]
            
            weight = reliability_weight * evidence.relevance_to_event * evidence.confidence_in_fact
            total_weight += weight
            total_score += weight * evidence.confidence_in_fact
        
        return total_score / total_weight if total_weight > 0 else 0.0


@dataclass
class Prediction:
    """Represents a prediction with supporting evidence chain."""
    event_id: str
    prediction: str  # The actual prediction (e.g., "Yes, the event will occur")
    confidence: PredictionConfidence
    confidence_score: float  # 0.0 to 1.0
    reasoning: str  # Clear explanation of the reasoning
    evidence_chain: EvidenceChain
    key_factors: List[str] = field(default_factory=list)
    risks_and_uncertainties: List[str] = field(default_factory=list)
    alternative_scenarios: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the prediction."""
        return {
            "event_id": self.event_id,
            "prediction": self.prediction,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "evidence_count": len(self.evidence_chain.evidence_items),
            "evidence_strength": self.evidence_chain.calculate_evidence_strength(),
            "key_factors": self.key_factors,
            "risks": self.risks_and_uncertainties,
            "alternatives": self.alternative_scenarios,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ResearchSession:
    """Represents a research session for an event."""
    event_id: str
    event_description: str
    research_queries: List[str] = field(default_factory=list)
    evidence_chains: List[EvidenceChain] = field(default_factory=list)
    final_prediction: Optional[Prediction] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def add_evidence_chain(self, chain: EvidenceChain) -> None:
        """Add an evidence chain to the session."""
        self.evidence_chains.append(chain)
    
    def complete_with_prediction(self, prediction: Prediction) -> None:
        """Complete the research session with a final prediction."""
        self.final_prediction = prediction
        self.completed_at = datetime.utcnow()
    
    def get_research_summary(self) -> Dict[str, Any]:
        """Get a summary of the research session."""
        return {
            "event_id": self.event_id,
            "event_description": self.event_description,
            "research_queries_count": len(self.research_queries),
            "evidence_chains_count": len(self.evidence_chains),
            "total_evidence_items": sum(len(chain.evidence_items) for chain in self.evidence_chains),
            "has_prediction": self.final_prediction is not None,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_minutes": (
                (self.completed_at - self.started_at).total_seconds() / 60
                if self.completed_at else None
            )
        }
