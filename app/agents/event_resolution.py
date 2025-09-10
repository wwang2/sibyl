"""Event Resolution Agent for fact-based event conclusion.

This agent analyzes events to determine their resolution status based on evidence
from multiple independent sources. It follows a strict protocol for evidence
evaluation and resolution determination.

RESOLUTION PROTOCOL:
==================

1. EVIDENCE REQUIREMENTS:
   - Minimum 3 independent sources required for resolution
   - Sources must be from different domains (news, official, academic, etc.)
   - More sources indicate stronger evidence
   - All sources must be high-reliability (reputable publishers)

2. RESOLUTION STATUS DETERMINATION:
   
   RESOLVED:
   - 3+ independent sources confirm the event outcome
   - No contradicting evidence from reliable sources
   - Evidence is factual and verifiable
   - Event has clear outcome (election results, sports scores, etc.)
   
   OPEN:
   - Less than 3 independent sources available
   - Event is ongoing or future-dated
   - Insufficient evidence for definitive conclusion
   - Event type not suitable for fact-based resolution
   
   CONTRADICTED:
   - 3+ sources confirm outcome BUT 1+ sources contradict
   - Conflicting evidence from reliable sources
   - Requires human review and override
   - Human can override to RESOLVED or OPEN

3. SOURCE INDEPENDENCE CRITERIA:
   - Different domains: news, government, academic, corporate, NGO
   - Different publishers: no shared ownership or editorial control
   - Different geographic regions when applicable
   - Different time periods of publication

4. EVIDENCE ANALYSIS:
   - Factual claims vs. opinions or predictions
   - Primary sources vs. secondary reporting
   - Official statements vs. speculation
   - Recent information vs. outdated data

5. AUTOMATIC RESOLUTION:
   - Past events with clear outcomes (elections, sports, etc.)
   - Events with official results or announcements
   - Historical facts with multiple confirmations
   - No human intervention required for clear cases

6. HUMAN OVERRIDE:
   - Required for CONTRADICTED status
   - Optional for RESOLVED or OPEN status
   - Human can provide override notes
   - Override decisions are logged and tracked

7. CONFIDENCE SCORING:
   - Based on number of independent sources
   - Quality of source reliability
   - Recency of information
   - Consistency of evidence

Example Usage:
    agent = EventResolutionAgent(store, research_agent)
    resolution = await agent.resolve_event(event)
    print(f"Status: {resolution.resolution_status}")
    print(f"Confirming sources: {resolution.confirming_sources_count}")
    print(f"Contradicting sources: {resolution.contradicting_sources_count}")
"""

from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from core.models import Event, EventResolution, ResolutionStatus
from core.store import Store
from agents.research import WebResearchAgent

logger = logging.getLogger(__name__)


@dataclass
class ResolutionEvidence:
    """Structured evidence for event resolution."""
    source_url: str
    source_domain: str
    source_title: str
    extracted_fact: str
    relevance_score: float
    reliability_score: float
    supports_outcome: bool
    publication_date: Optional[datetime] = None


class EventResolutionAgent:
    """Agent for resolving events based on evidence from multiple independent sources.
    
    This agent implements the resolution protocol to determine event outcomes
    through systematic evidence gathering and analysis.
    """
    
    def __init__(
        self, 
        store: Store, 
        research_agent: WebResearchAgent,
        resolution_threshold: int = 3,
        min_reliability_score: float = 0.7
    ):
        """Initialize the Event Resolution Agent.
        
        Args:
            store: Database store for persistence
            research_agent: Agent for web research and fact extraction
            resolution_threshold: Minimum independent sources needed for resolution
            min_reliability_score: Minimum reliability score for sources
        """
        self.store = store
        self.research_agent = research_agent
        self.resolution_threshold = resolution_threshold
        self.min_reliability_score = min_reliability_score
        
        # Domain categories for source independence
        self.domain_categories = {
            'news': ['cnn.com', 'bbc.com', 'reuters.com', 'ap.org', 'npr.org'],
            'government': ['.gov', '.mil', 'whitehouse.gov', 'congress.gov'],
            'academic': ['.edu', 'scholar.google.com', 'researchgate.net'],
            'corporate': ['.com', '.org', 'bloomberg.com', 'wsj.com'],
            'international': ['.uk', '.ca', '.au', '.de', '.fr', '.jp']
        }
    
    async def resolve_event(self, event: Event) -> EventResolution:
        """Resolve an event based on evidence analysis.
        
        Args:
            event: The event to resolve
            
        Returns:
            EventResolution object with status and evidence summary
        """
        logger.info(f"Starting resolution for event: {event.title}")
        
        try:
            # Generate targeted search queries
            queries = self._generate_resolution_queries(event)
            logger.info(f"Generated {len(queries)} search queries")
            
            # Search for evidence
            all_evidence = []
            for query in queries:
                try:
                    evidence = await self.research_agent.search_and_extract_facts(query)
                    all_evidence.extend(evidence)
                except Exception as e:
                    logger.warning(f"Failed to search query '{query}': {e}")
                    continue
            
            logger.info(f"Collected {len(all_evidence)} total evidence items")
            
            # Analyze evidence for event resolution
            resolution_evidence = self._analyze_evidence_for_resolution(event, all_evidence)
            
            # Categorize evidence
            confirming_evidence = [e for e in resolution_evidence if e.supports_outcome]
            contradicting_evidence = [e for e in resolution_evidence if not e.supports_outcome]
            
            # Ensure source independence
            independent_confirming = self._ensure_source_independence(confirming_evidence)
            independent_contradicting = self._ensure_source_independence(contradicting_evidence)
            
            logger.info(f"Independent confirming sources: {len(independent_confirming)}")
            logger.info(f"Independent contradicting sources: {len(independent_contradicting)}")
            
            # Make resolution decision
            resolution_status = self._determine_resolution_status(
                independent_confirming, 
                independent_contradicting
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                independent_confirming, 
                independent_contradicting
            )
            
            # Create resolution summary
            resolution_summary = self._create_resolution_summary(
                event, 
                resolution_status, 
                independent_confirming, 
                independent_contradicting
            )
            
            # Create EventResolution object
            resolution = EventResolution(
                event_id=event.id,
                resolution_status=resolution_status,
                resolution_date=datetime.utcnow() if resolution_status == ResolutionStatus.RESOLVED else None,
                confidence_score=confidence_score,
                confirming_sources_count=len(independent_confirming),
                contradicting_sources_count=len(independent_contradicting),
                total_sources_checked=len(all_evidence),
                resolution_summary=resolution_summary,
                key_evidence=self._serialize_evidence(independent_confirming),
                contradicting_evidence=self._serialize_evidence(independent_contradicting),
                resolved_by="EventResolutionAgent"
            )
            
            # Save to database
            with self.store.get_session() as session:
                session.add(resolution)
                session.commit()
            
            logger.info(f"Resolution completed: {resolution_status.value} (confidence: {confidence_score:.2f})")
            return resolution
            
        except Exception as e:
            logger.error(f"Failed to resolve event {event.id}: {e}")
            # Create a failed resolution record
            resolution = EventResolution(
                event_id=event.id,
                resolution_status=ResolutionStatus.OPEN,
                confidence_score=0.0,
                confirming_sources_count=0,
                contradicting_sources_count=0,
                total_sources_checked=0,
                resolution_summary=f"Resolution failed: {str(e)}",
                resolved_by="EventResolutionAgent"
            )
            with self.store.get_session() as session:
                session.add(resolution)
                session.commit()
            return resolution
    
    def _generate_resolution_queries(self, event: Event) -> List[str]:
        """Generate targeted search queries for event resolution.
        
        Args:
            event: The event to generate queries for
            
        Returns:
            List of search query strings
        """
        queries = []
        title = event.title.lower()
        
        # Direct outcome queries
        if any(word in title for word in ['elected', 'won', 'defeated', 'beat']):
            queries.append(f"{event.title} result outcome")
            queries.append(f"who won {event.title}")
            queries.append(f"{event.title} winner")
        
        # Date-specific queries
        if event.expected_resolution_date:
            date_str = event.expected_resolution_date.strftime("%Y-%m-%d")
            queries.append(f"{event.title} {date_str} result")
            queries.append(f"{event.title} outcome {date_str}")
        
        # Fact-checking queries
        queries.append(f"did {event.title} happen")
        queries.append(f"{event.title} confirmed verified")
        queries.append(f"{event.title} official result")
        
        # Historical fact queries
        if any(word in title for word in ['was', 'were', 'did', 'happened']):
            queries.append(f"{event.title} fact check")
            queries.append(f"{event.title} true false")
        
        # Remove duplicates and limit to reasonable number
        return list(set(queries))[:10]
    
    def _analyze_evidence_for_resolution(self, event: Event, evidence: List) -> List[ResolutionEvidence]:
        """Analyze evidence to determine if it supports event resolution.
        
        Args:
            event: The event being resolved
            evidence: List of evidence from research agent
            
        Returns:
            List of ResolutionEvidence objects
        """
        resolution_evidence = []
        
        for item in evidence:
            try:
                # Extract domain from URL
                source_domain = self._extract_domain(item.get('url', ''))
                
                # Create ResolutionEvidence object
                res_evidence = ResolutionEvidence(
                    source_url=item.get('url', ''),
                    source_domain=source_domain,
                    source_title=item.get('title', ''),
                    extracted_fact=item.get('extracted_fact', ''),
                    relevance_score=item.get('relevance_score', 0.0),
                    reliability_score=item.get('reliability_score', 0.0),
                    supports_outcome=self._evidence_supports_outcome(event, item)
                )
                
                # Only include high-reliability evidence
                if res_evidence.reliability_score >= self.min_reliability_score:
                    resolution_evidence.append(res_evidence)
                    
            except Exception as e:
                logger.warning(f"Failed to analyze evidence item: {e}")
                continue
        
        return resolution_evidence
    
    def _evidence_supports_outcome(self, event: Event, evidence_item: Dict) -> bool:
        """Determine if evidence supports the event outcome.
        
        This is a simplified implementation. In practice, you might want to use
        an LLM to analyze the evidence more sophisticatedly.
        
        Args:
            event: The event being resolved
            evidence_item: Evidence item from research
            
        Returns:
            True if evidence supports the event outcome
        """
        fact = evidence_item.get('extracted_fact', '').lower()
        title = event.title.lower()
        
        # Simple keyword matching - can be enhanced with LLM analysis
        if any(word in title for word in ['elected', 'won', 'defeated']):
            # For election/competition events
            if any(word in fact for word in ['won', 'victory', 'defeated', 'elected']):
                return True
            if any(word in fact for word in ['lost', 'defeat', 'not elected']):
                return False
        
        # For general events
        if any(word in fact for word in ['confirmed', 'verified', 'happened', 'occurred']):
            return True
        if any(word in fact for word in ['denied', 'false', 'did not happen']):
            return False
        
        # Default to supporting if relevance is high
        return evidence_item.get('relevance_score', 0.0) > 0.7
    
    def _ensure_source_independence(self, evidence: List[ResolutionEvidence]) -> List[ResolutionEvidence]:
        """Ensure sources are independent by domain diversity.
        
        Args:
            evidence: List of evidence to filter
            
        Returns:
            List of evidence with independent sources only
        """
        if not evidence:
            return []
        
        # Group by domain category
        domain_groups = {}
        for item in evidence:
            category = self._get_domain_category(item.source_domain)
            if category not in domain_groups:
                domain_groups[category] = []
            domain_groups[category].append(item)
        
        # Select best evidence from each domain category
        independent_evidence = []
        for category, items in domain_groups.items():
            # Sort by reliability score and take the best
            best_item = max(items, key=lambda x: x.reliability_score)
            independent_evidence.append(best_item)
        
        return independent_evidence
    
    def _get_domain_category(self, domain: str) -> str:
        """Categorize domain for independence checking.
        
        Args:
            domain: Domain string
            
        Returns:
            Category string
        """
        domain_lower = domain.lower()
        
        for category, patterns in self.domain_categories.items():
            for pattern in patterns:
                if pattern in domain_lower:
                    return category
        
        return 'other'
    
    def _determine_resolution_status(
        self, 
        confirming_evidence: List[ResolutionEvidence], 
        contradicting_evidence: List[ResolutionEvidence]
    ) -> ResolutionStatus:
        """Determine resolution status based on evidence.
        
        Args:
            confirming_evidence: Evidence that supports the outcome
            contradicting_evidence: Evidence that contradicts the outcome
            
        Returns:
            ResolutionStatus enum value
        """
        confirming_count = len(confirming_evidence)
        contradicting_count = len(contradicting_evidence)
        
        if confirming_count >= self.resolution_threshold:
            if contradicting_count == 0:
                return ResolutionStatus.RESOLVED
            else:
                return ResolutionStatus.CONTRADICTED
        else:
            return ResolutionStatus.OPEN
    
    def _calculate_confidence_score(
        self, 
        confirming_evidence: List[ResolutionEvidence], 
        contradicting_evidence: List[ResolutionEvidence]
    ) -> float:
        """Calculate confidence score based on evidence quality and quantity.
        
        Args:
            confirming_evidence: Evidence that supports the outcome
            contradicting_evidence: Evidence that contradicts the outcome
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not confirming_evidence:
            return 0.0
        
        # Base score from number of sources
        base_score = min(len(confirming_evidence) / self.resolution_threshold, 1.0)
        
        # Quality adjustment based on reliability scores
        avg_reliability = sum(e.reliability_score for e in confirming_evidence) / len(confirming_evidence)
        quality_multiplier = avg_reliability
        
        # Penalty for contradicting evidence
        contradiction_penalty = min(len(contradicting_evidence) * 0.1, 0.5)
        
        confidence = (base_score * quality_multiplier) - contradiction_penalty
        return max(0.0, min(1.0, confidence))
    
    def _create_resolution_summary(
        self, 
        event: Event, 
        status: ResolutionStatus, 
        confirming_evidence: List[ResolutionEvidence], 
        contradicting_evidence: List[ResolutionEvidence]
    ) -> str:
        """Create a human-readable resolution summary.
        
        Args:
            event: The resolved event
            status: Resolution status
            confirming_evidence: Evidence supporting the outcome
            contradicting_evidence: Evidence contradicting the outcome
            
        Returns:
            Summary string
        """
        if status == ResolutionStatus.RESOLVED:
            return f"Event resolved with {len(confirming_evidence)} independent sources confirming the outcome. No contradicting evidence found."
        elif status == ResolutionStatus.CONTRADICTED:
            return f"Conflicting evidence found: {len(confirming_evidence)} sources confirm, {len(contradicting_evidence)} sources contradict. Human review required."
        else:
            return f"Insufficient evidence for resolution: {len(confirming_evidence)} confirming sources (need {self.resolution_threshold}), {len(contradicting_evidence)} contradicting sources."
    
    def _serialize_evidence(self, evidence: List[ResolutionEvidence]) -> Dict:
        """Serialize evidence for database storage.
        
        Args:
            evidence: List of evidence to serialize
            
        Returns:
            Dictionary representation
        """
        return {
            'sources': [
                {
                    'url': e.source_url,
                    'domain': e.source_domain,
                    'title': e.source_title,
                    'fact': e.extracted_fact,
                    'relevance_score': e.relevance_score,
                    'reliability_score': e.reliability_score
                }
                for e in evidence
            ],
            'count': len(evidence)
        }
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL.
        
        Args:
            url: URL string
            
        Returns:
            Domain string
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return url.lower()
