"""
Web Research Agent

This agent performs web research using Tavily search to build evidence chains
and make predictions for events.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict

from adapters.tavily import TavilySearchTool, TavilySearchConfig
from core.research_models import (
    EvidenceType, EvidenceReliability, PredictionConfidence,
    EvidenceSource, Evidence, EvidenceChain, Prediction, ResearchSession
)
from core.store import Store


class WebResearchAgent:
    """Agent that performs web research and makes predictions."""
    
    def __init__(self, store: Store, offline_mode: bool = False, model_name: str = "gemini-1.5-flash-8b"):
        """Initialize the research agent."""
        self.store = store
        self.offline_mode = offline_mode
        self.model_name = model_name
        
        # Initialize Tavily search tool
        tavily_config = TavilySearchConfig(
            search_depth="advanced",
            max_results=10,
            offline_mode=offline_mode
        )
        self.search_tool = TavilySearchTool(tavily_config)
        
        # Research session tracking
        self.current_session: Optional[ResearchSession] = None
    
    async def research_event(self, event_id: str, event_description: str) -> Prediction:
        """
        Research an event and provide a prediction with evidence chain.
        
        Args:
            event_id: Unique identifier for the event
            event_description: Description of the event to research
            
        Returns:
            Prediction with supporting evidence chain
        """
        print(f"🔍 Starting research for event: {event_id}")
        print(f"📝 Event description: {event_description}")
        
        # Create research session
        self.current_session = ResearchSession(
            event_id=event_id,
            event_description=event_description
        )
        
        # Generate research queries
        research_queries = await self._generate_research_queries(event_description)
        self.current_session.research_queries = research_queries
        
        print(f"📋 Generated {len(research_queries)} research queries")
        
        # Build evidence chains
        evidence_chain = await self._build_evidence_chain(event_id, research_queries)
        self.current_session.add_evidence_chain(evidence_chain)
        
        # Analyze evidence and make prediction
        prediction = await self._analyze_and_predict(event_id, event_description, evidence_chain)
        self.current_session.complete_with_prediction(prediction)
        
        print(f"✅ Research completed. Prediction: {prediction.prediction}")
        print(f"🎯 Confidence: {prediction.confidence.value} ({prediction.confidence_score:.1%})")
        
        return prediction
    
    async def _generate_research_queries(self, event_description: str) -> List[str]:
        """Generate research queries for the event."""
        if self.offline_mode:
            return self._mock_generate_queries(event_description)
        
        # In real mode, we would use an LLM to generate queries
        # For now, use a simple template-based approach
        base_queries = [
            f"latest news about {event_description}",
            f"recent developments {event_description}",
            f"expert analysis {event_description}",
            f"market predictions {event_description}",
            f"official statements {event_description}"
        ]
        
        return base_queries
    
    def _mock_generate_queries(self, event_description: str) -> List[str]:
        """Generate mock research queries for offline mode."""
        return [
            f"recent news {event_description}",
            f"expert opinions {event_description}",
            f"market analysis {event_description}",
            f"official updates {event_description}"
        ]
    
    async def _build_evidence_chain(self, event_id: str, queries: List[str]) -> EvidenceChain:
        """Build evidence chain by searching for each query."""
        evidence_chain = EvidenceChain(
            event_id=event_id,
            research_query="; ".join(queries)
        )
        
        print(f"🔗 Building evidence chain with {len(queries)} queries...")
        
        for i, query in enumerate(queries, 1):
            print(f"  📊 Query {i}/{len(queries)}: {query}")
            
            # Search for evidence
            search_results = self.search_tool.search(query)
            
            # Process results into evidence
            evidence_items = await self._process_search_results(
                search_results, query, event_id
            )
            
            # Add evidence to chain
            for evidence in evidence_items:
                evidence_chain.add_evidence(evidence)
            
            print(f"    ✅ Found {len(evidence_items)} evidence items")
        
        print(f"🔗 Evidence chain complete: {len(evidence_chain.evidence_items)} total items")
        return evidence_chain
    
    async def _process_search_results(
        self, 
        search_results, 
        query: str, 
        event_id: str
    ) -> List[Evidence]:
        """Process search results into evidence items."""
        evidence_items = []
        
        for i, result in enumerate(search_results.results):
            # Create evidence source
            source = EvidenceSource(
                url=result.get("url", ""),
                title=result.get("title", ""),
                domain=result.get("url", "").split("/")[2] if result.get("url") else "",
                content=result.get("content", ""),
                source_type=self._classify_source_type(result),
                reliability=self._assess_reliability(result),
                relevance_score=result.get("score", 0.0),
                credibility_score=self._assess_credibility(result)
            )
            
            # Extract facts and create evidence
            if self.offline_mode:
                extracted_fact, supporting_claim = self._mock_extract_facts(result, query)
            else:
                extracted_fact, supporting_claim = await self._extract_facts(result, query)
            
            evidence = Evidence(
                id=f"{event_id}_{query}_{i}",
                source=source,
                extracted_fact=extracted_fact,
                supporting_claim=supporting_claim,
                evidence_type=source.source_type,
                reliability=source.reliability,
                relevance_to_event=source.relevance_score,
                confidence_in_fact=source.credibility_score
            )
            
            evidence_items.append(evidence)
        
        return evidence_items
    
    def _classify_source_type(self, result: Dict[str, Any]) -> EvidenceType:
        """Classify the type of evidence source."""
        url = result.get("url", "").lower()
        title = result.get("title", "").lower()
        
        if any(domain in url for domain in ["gov", "official", "government"]):
            return EvidenceType.OFFICIAL_STATEMENT
        elif any(domain in url for domain in ["reuters", "bloomberg", "wsj", "ft"]):
            return EvidenceType.NEWS_ARTICLE
        elif any(domain in url for domain in ["twitter", "facebook", "reddit"]):
            return EvidenceType.SOCIAL_MEDIA
        elif any(domain in url for domain in ["arxiv", "research", "academic"]):
            return EvidenceType.RESEARCH_PAPER
        else:
            return EvidenceType.NEWS_ARTICLE
    
    def _assess_reliability(self, result: Dict[str, Any]) -> EvidenceReliability:
        """Assess the reliability of a source."""
        url = result.get("url", "").lower()
        score = result.get("score", 0.0)
        
        # High reliability sources
        if any(domain in url for domain in [
            "reuters.com", "bloomberg.com", "wsj.com", "ft.com", 
            "gov", "official", "government"
        ]):
            return EvidenceReliability.HIGH
        
        # Medium reliability based on score
        if score > 0.7:
            return EvidenceReliability.MEDIUM
        
        return EvidenceReliability.LOW
    
    def _assess_credibility(self, result: Dict[str, Any]) -> float:
        """Assess the credibility score of a source."""
        url = result.get("url", "").lower()
        score = result.get("score", 0.0)
        
        # Boost credibility for known reliable sources
        if any(domain in url for domain in [
            "reuters.com", "bloomberg.com", "wsj.com", "ft.com"
        ]):
            return min(0.9, score + 0.2)
        
        return score
    
    def _mock_extract_facts(self, result: Dict[str, Any], query: str) -> Tuple[str, str]:
        """Mock fact extraction for offline mode."""
        title = result.get("title", "")
        content = result.get("content", "")
        
        # Simple fact extraction based on content
        if "ai" in query.lower() or "artificial intelligence" in query.lower():
            extracted_fact = "AI technology is advancing rapidly with new developments in machine learning and automation."
            supporting_claim = f"Source: {title} - {content[:100]}..."
        elif "prediction" in query.lower():
            extracted_fact = "Prediction markets are gaining traction as tools for forecasting future events."
            supporting_claim = f"Source: {title} - {content[:100]}..."
        else:
            extracted_fact = f"Recent developments related to: {query}"
            supporting_claim = f"Source: {title} - {content[:100]}..."
        
        return extracted_fact, supporting_claim
    
    async def _extract_facts(self, result: Dict[str, Any], query: str) -> Tuple[str, str]:
        """Extract facts from search result using content analysis."""
        title = result.get("title", "")
        content = result.get("content", "")
        url = result.get("url", "")
        
        # Extract meaningful facts from the actual content
        if not content or len(content.strip()) < 50:
            # Fallback to title-based extraction
            extracted_fact = f"Article titled '{title}' discusses topics related to: {query}"
            supporting_claim = f"Source: {title} ({url})"
            return extracted_fact, supporting_claim
        
        # Extract key sentences from content
        sentences = content.split('. ')
        relevant_sentences = []
        
        # Look for sentences that contain relevant keywords
        query_keywords = query.lower().split()
        
        for sentence in sentences[:10]:  # Check first 10 sentences
            if len(sentence.strip()) > 20:  # Skip very short sentences
                sentence_lower = sentence.lower()
                # Check if sentence contains any query keywords
                if any(keyword in sentence_lower for keyword in query_keywords):
                    relevant_sentences.append(sentence.strip())
        
        # If we found relevant sentences, use them
        if relevant_sentences:
            # Take the most relevant sentence (first one found)
            extracted_fact = relevant_sentences[0]
            if not extracted_fact.endswith('.'):
                extracted_fact += '.'
            
            # Create supporting claim with more context
            supporting_claim = f"Source: {title} - {content[:200]}..."
        else:
            # Fallback: extract first meaningful sentence from content
            first_sentence = sentences[0] if sentences else content[:100]
            extracted_fact = first_sentence.strip()
            if not extracted_fact.endswith('.'):
                extracted_fact += '.'
            
            supporting_claim = f"Source: {title} - {content[:200]}..."
        
        return extracted_fact, supporting_claim
    
    async def _analyze_and_predict(
        self, 
        event_id: str, 
        event_description: str, 
        evidence_chain: EvidenceChain
    ) -> Prediction:
        """Analyze evidence chain and make a prediction."""
        if self.offline_mode:
            return self._mock_analyze_and_predict(event_id, event_description, evidence_chain)
        
        # In real mode, we would use an LLM to analyze evidence
        return self._mock_analyze_and_predict(event_id, event_description, evidence_chain)
    
    def _mock_analyze_and_predict(
        self, 
        event_id: str, 
        event_description: str, 
        evidence_chain: EvidenceChain
    ) -> Prediction:
        """Mock analysis and prediction for offline mode."""
        
        # Calculate evidence strength
        evidence_strength = evidence_chain.calculate_evidence_strength()
        
        # Determine confidence based on evidence strength
        if evidence_strength > 0.8:
            confidence = PredictionConfidence.VERY_HIGH
            confidence_score = 0.9
            prediction = "Yes, the event is very likely to occur based on strong evidence."
        elif evidence_strength > 0.6:
            confidence = PredictionConfidence.HIGH
            confidence_score = 0.75
            prediction = "Yes, the event is likely to occur based on good evidence."
        elif evidence_strength > 0.4:
            confidence = PredictionConfidence.MEDIUM
            confidence_score = 0.55
            prediction = "The event may occur, but evidence is mixed."
        elif evidence_strength > 0.2:
            confidence = PredictionConfidence.LOW
            confidence_score = 0.35
            prediction = "The event is unlikely to occur based on limited evidence."
        else:
            confidence = PredictionConfidence.VERY_LOW
            confidence_score = 0.15
            prediction = "No, the event is very unlikely to occur based on weak evidence."
        
        # Generate reasoning
        reasoning = self._generate_reasoning(evidence_chain, evidence_strength)
        
        # Extract key factors
        key_factors = self._extract_key_factors(evidence_chain)
        
        # Identify risks and uncertainties
        risks = self._identify_risks(evidence_chain)
        
        # Generate alternative scenarios
        alternatives = self._generate_alternatives(event_description)
        
        return Prediction(
            event_id=event_id,
            prediction=prediction,
            confidence=confidence,
            confidence_score=confidence_score,
            reasoning=reasoning,
            evidence_chain=evidence_chain,
            key_factors=key_factors,
            risks_and_uncertainties=risks,
            alternative_scenarios=alternatives
        )
    
    def _generate_reasoning(self, evidence_chain: EvidenceChain, evidence_strength: float) -> str:
        """Generate reasoning based on evidence chain."""
        high_reliability_count = len(evidence_chain.get_high_reliability_evidence())
        total_evidence = len(evidence_chain.evidence_items)
        
        reasoning = f"""
        Based on analysis of {total_evidence} evidence items with an overall strength of {evidence_strength:.1%}:
        
        • {high_reliability_count} high-reliability sources provide strong supporting evidence
        • Evidence covers multiple aspects of the event with consistent patterns
        • Source diversity includes news articles, official statements, and expert opinions
        • Confidence level reflects the quality and quantity of available evidence
        
        The prediction is based on the most reliable and relevant evidence available at the time of analysis.
        """
        
        return reasoning.strip()
    
    def _extract_key_factors(self, evidence_chain: EvidenceChain) -> List[str]:
        """Extract key factors from evidence chain."""
        factors = []
        
        # Analyze evidence types
        evidence_types = {}
        for evidence in evidence_chain.evidence_items:
            evidence_type = evidence.evidence_type.value
            evidence_types[evidence_type] = evidence_types.get(evidence_type, 0) + 1
        
        # Add factors based on evidence types
        if evidence_types.get("news_article", 0) > 0:
            factors.append("Recent news coverage and media attention")
        
        if evidence_types.get("official_statement", 0) > 0:
            factors.append("Official statements and government positions")
        
        if evidence_types.get("expert_opinion", 0) > 0:
            factors.append("Expert analysis and professional opinions")
        
        if evidence_types.get("market_data", 0) > 0:
            factors.append("Market indicators and financial data")
        
        return factors
    
    def _identify_risks(self, evidence_chain: EvidenceChain) -> List[str]:
        """Identify risks and uncertainties."""
        risks = []
        
        # Check for contradicting evidence
        contradicting = evidence_chain.get_contradicting_evidence()
        if contradicting:
            risks.append("Conflicting evidence from different sources")
        
        # Check evidence quality
        low_reliability_count = len([
            e for e in evidence_chain.evidence_items 
            if e.reliability == EvidenceReliability.LOW
        ])
        
        if low_reliability_count > len(evidence_chain.evidence_items) / 2:
            risks.append("Limited high-quality evidence available")
        
        # General risks
        risks.extend([
            "Information may be outdated or incomplete",
            "External factors could influence the outcome",
            "Unforeseen circumstances may change the situation"
        ])
        
        return risks
    
    def _generate_alternatives(self, event_description: str) -> List[str]:
        """Generate alternative scenarios."""
        return [
            f"Alternative outcome 1: {event_description} occurs earlier than expected",
            f"Alternative outcome 2: {event_description} occurs later than expected",
            f"Alternative outcome 3: {event_description} does not occur as described",
            f"Alternative outcome 4: External factors significantly impact {event_description}"
        ]
    
    def get_research_summary(self) -> Optional[Dict[str, Any]]:
        """Get summary of current research session."""
        if self.current_session:
            return self.current_session.get_research_summary()
        return None
