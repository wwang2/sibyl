"""LLM-based Event Judge Agent for evaluating event proposal quality."""

import asyncio
import json
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient
except ImportError:
    print("AutoGen not available. Install with: pip install autogen-agentchat autogen-ext[openai]")
    raise

try:
    from ..core.store import Store
    from ..core.models import EventProposal
    from ..core.types import AgentRun, AgentType
except ImportError:
    from core.store import Store
    from core.models import EventProposal
    from core.types import AgentRun, AgentType


class JudgmentResult(Enum):
    """Result of event judgment."""
    APPROVED = "accepted"  # Maps to ACCEPTED in ProposalStatus
    REJECTED = "rejected"
    NEEDS_REVISION = "pending"  # Maps to PENDING in ProposalStatus


@dataclass
class EventJudgment:
    """Result of judging an event proposal."""
    proposal_id: int
    result: JudgmentResult
    answerability_score: float  # 0-1, how answerable the question is
    significance_score: float   # 0-1, how significant the event is
    frequency_score: float     # 0-1, how frequently this type of event occurs (lower is better)
    temporal_score: float      # 0-1, how relevant the event is temporally (0 = already happened, 1 = future)
    overall_score: float       # 0-1, weighted overall score
    reasoning: str             # LLM reasoning for the judgment
    suggestions: List[str]     # Suggestions for improvement if rejected/needs revision
    # Consolidated tagging
    primary_tag: str           # Main category (politics, economics, crypto, etc.)
    secondary_tags: List[str]  # Additional relevant tags
    tag_confidence: float      # Confidence in the tagging (0-1)


class EventJudgeAgent:
    """LLM-based agent for judging event proposal quality."""
    
    def __init__(
        self, 
        store: Store, 
        model_name: str = "gemini-1.5-flash-8b",
        approval_threshold: float = 0.7,
        offline_mode: bool = False
    ):
        """Initialize the event judge agent."""
        self.store = store
        self.model_name = model_name
        self.approval_threshold = approval_threshold
        self.offline_mode = offline_mode
        
        # AutoGen components
        self.model_client = None
        self.assistant_agent = None
        
        # Judgment criteria weights
        self.weights = {
            'answerability': 0.3,  # Important - can we answer this?
            'significance': 0.3,   # Important - is this significant?
            'frequency': 0.2,      # Less important - but still relevant
            'temporal': 0.2        # Important - is this event still relevant?
        }
    
    async def _initialize_autogen(self):
        """Initialize AutoGen components."""
        if not self.model_client and not self.offline_mode:
            self.model_client = OpenAIChatCompletionClient(model=self.model_name)
            self.assistant_agent = AssistantAgent("event_judge", model_client=self.model_client)
    
    async def _cleanup_autogen(self):
        """Clean up AutoGen components."""
        if self.model_client:
            await self.model_client.close()
            self.model_client = None
            self.assistant_agent = None
    
    def _extract_temporal_info(self, proposal: EventProposal) -> Dict[str, Any]:
        """Extract temporal information from the proposal."""
        import re
        from datetime import datetime, timezone
        
        current_time = datetime.now(timezone.utc)
        title = proposal.title.lower()
        description = (proposal.description or "").lower()
        text = f"{title} {description}"
        
        # Look for date patterns
        date_patterns = [
            r'(\d{4})',  # Year
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2})',  # Month day
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'before\s+(\w+\s+\d{1,2},?\s+\d{4})',  # "before Jan 1, 2021"
            r'by\s+(\w+\s+\d{1,2},?\s+\d{4})',  # "by Jan 1, 2021"
            r'on\s+(\w+\s+\d{1,2},?\s+\d{4})',  # "on Jan 1, 2021"
        ]
        
        extracted_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            extracted_dates.extend(matches)
        
        # Look for relative time indicators
        relative_indicators = [
            'before', 'by', 'on', 'after', 'until', 'through',
            'end of year', 'eoy', 'end of 2020', 'end of 2021',
            'election', 'november', 'december'
        ]
        
        has_relative_time = any(indicator in text for indicator in relative_indicators)
        
        # Determine if event is likely in the past
        is_past_event = False
        temporal_confidence = 0.5  # Default neutral
        
        # Check for obvious past events
        past_indicators = [
            '2020', '2019', '2018', '2017', '2016',
            'last year', 'previous year', 'past',
            'already happened', 'occurred'
        ]
        
        future_indicators = [
            '2025', '2026', '2027', '2028', '2029',
            'next year', 'upcoming', 'future',
            'will happen', 'will occur'
        ]
        
        if any(indicator in text for indicator in past_indicators):
            is_past_event = True
            temporal_confidence = 0.9
        elif any(indicator in text for indicator in future_indicators):
            is_past_event = False
            temporal_confidence = 0.9
        elif has_relative_time:
            # If it has relative time but we can't determine past/future, be conservative
            temporal_confidence = 0.3
        
        return {
            'extracted_dates': extracted_dates,
            'has_relative_time': has_relative_time,
            'is_past_event': is_past_event,
            'temporal_confidence': temporal_confidence,
            'current_time': current_time.isoformat()
        }
    
    def _create_judgment_prompt(self, proposal: EventProposal) -> str:
        """Create a prompt for judging an event proposal."""
        temporal_info = self._extract_temporal_info(proposal)
        
        return f"""
You are an expert event judge evaluating prediction market event proposals. Your task is to assess whether an event proposal is worth including in a prediction market system.

EVENT PROPOSAL TO EVALUATE:
Title: {proposal.title}
Description: {proposal.description or "No description provided"}
Proposed by: {proposal.proposed_by}
Created: {proposal.created_at}

TEMPORAL ANALYSIS:
Current Time: {temporal_info['current_time']}
Extracted Dates: {temporal_info['extracted_dates']}
Has Relative Time: {temporal_info['has_relative_time']}
Likely Past Event: {temporal_info['is_past_event']}
Temporal Confidence: {temporal_info['temporal_confidence']}

EVALUATION CRITERIA:

1. ANSWERABILITY (Weight: 40%):
   - Can this question be answered with high confidence via search/verification?
   - Is the outcome clearly defined and measurable?
   - Are there objective criteria for resolution?
   - Examples of GOOD answerable questions:
     * "Will [specific person] win the [specific election] on [specific date]?"
     * "Will [specific company] release [specific product] before [specific date]?"
     * "Will [specific cryptocurrency] reach $[specific price] by [specific date]?"
   - Examples of BAD unanswerable questions:
     * "Will the economy improve?" (too vague)
     * "Will AI change everything?" (too broad, no clear criteria)
     * "Will there be a war?" (too vague, no specific conflict)

2. SIGNIFICANCE (Weight: 40%):
   - Does this event have significant impact or importance?
   - Would many people care about the outcome?
   - Is this a major event that affects many people or important systems?
   - Examples of SIGNIFICANT events:
     * Elections, major policy changes, economic indicators
     * Major product launches, company acquisitions, market milestones
     * Natural disasters, major technological breakthroughs
     * Major sporting events, entertainment milestones
   - Examples of INSIGNIFICANT events:
     * Minor personal events, trivial predictions
     * Events that affect very few people
     * Routine, everyday occurrences

3. FREQUENCY (Weight: 20%):
   - How frequently does this type of event occur?
   - Lower frequency is generally better (more unique/interesting)
   - Examples of LOW frequency (good):
     * Presidential elections (every 4 years)
     * Major product launches (occasional)
     * Major economic events (occasional)
   - Examples of HIGH frequency (bad):
     * Daily stock price movements
     * Routine weather events
     * Common social media milestones

4. TEMPORAL RELEVANCE (Weight: 20%):
   - Is this event still relevant for prediction markets?
   - Has the event already happened or is it in the future?
   - Score 0.0 if event has already occurred (no prediction value)
   - Score 1.0 if event is clearly in the future
   - Score 0.5 if temporal status is unclear
   - Consider the current time: {temporal_info['current_time']}
   - Past events (2020, 2021, etc.) should generally score 0.0
   - Future events (2025, 2026, etc.) should generally score 1.0

5. OPTIONS MARKET DETECTION (Special Rule):
   - Identify if this is a binary bet on numerical ranges (options-style market)
   - These are typically low-impact, derivative-like predictions
   - Examples of OPTIONS-STYLE markets (should be REJECTED):
     * "Will the President's approval rating be between 46.1 and 46.5?"
     * "Will gas prices be above $3.19?"
     * "Will the temperature be between 70-77°?"
     * "Will Tesla stock be above $200?"
     * "Will Bitcoin be between $50,000-$60,000?"
   - These markets are:
     - Low significance (just numerical ranges)
     - High frequency (many similar bets exist)
     - More like financial derivatives than meaningful predictions
   - If you identify an options-style market, set significance_score to 0.1 and frequency_score to 0.1

EVALUATION INSTRUCTIONS:
1. Rate each criterion on a scale of 0.0 to 1.0
2. Provide detailed reasoning for each score
3. Calculate an overall weighted score
4. Make a final judgment: APPROVED, REJECTED, or NEEDS_REVISION
5. If rejected or needs revision, provide specific suggestions for improvement
6. Assign appropriate tags to categorize this event

TAGGING CATEGORIES:
- politics: Government, elections, policy, political events
- economics: Economic indicators, financial markets, monetary policy
- crypto: Cryptocurrency, blockchain, digital assets
- stock_market: Stock prices, company performance, market movements
- technology: Tech companies, software, hardware, innovation
- ai: Artificial intelligence, machine learning, automation
- science: Scientific discoveries, research, space exploration
- sports: Athletic events, competitions, sports leagues
- entertainment: Movies, music, TV, celebrity events
- international: Global events, geopolitics, international relations
- weather: Weather events, natural disasters, climate
- health: Healthcare, medical events, public health
- other: Events that don't fit other categories

RESPONSE FORMAT (JSON):
{{
    "answerability_score": 0.0-1.0,
    "answerability_reasoning": "Detailed explanation of answerability assessment",
    "significance_score": 0.0-1.0,
    "significance_reasoning": "Detailed explanation of significance assessment", 
    "frequency_score": 0.0-1.0,
    "frequency_reasoning": "Detailed explanation of frequency assessment",
    "temporal_score": 0.0-1.0,
    "temporal_reasoning": "Detailed explanation of temporal relevance assessment",
    "overall_score": 0.0-1.0,
    "judgment": "APPROVED|REJECTED|NEEDS_REVISION",
    "reasoning": "Overall reasoning for the judgment",
    "suggestions": ["Specific suggestion 1", "Specific suggestion 2", ...],
    "primary_tag": "main_category",
    "secondary_tags": ["tag1", "tag2", ...],
    "tag_confidence": 0.0-1.0
}}

Be thorough and objective in your evaluation. Focus on practical considerations for prediction market viability.
"""
    
    async def judge_proposal(self, proposal: EventProposal) -> EventJudgment:
        """Judge a single event proposal."""
        if self.offline_mode:
            return self._mock_judgment(proposal)
        
        await self._initialize_autogen()
        
        try:
            prompt = self._create_judgment_prompt(proposal)
            
            # Get LLM response
            response = await self.assistant_agent.run(task=prompt)
            
            # Parse JSON response
            try:
                # Extract content from AutoGen TaskResult
                if hasattr(response, 'messages') and response.messages:
                    # Get the last message (should be the assistant's response)
                    last_message = response.messages[-1]
                    if hasattr(last_message, 'content'):
                        response_text = last_message.content
                    else:
                        response_text = str(last_message)
                else:
                    response_text = response.content if hasattr(response, 'content') else str(response)
                
                # Debug output removed for cleaner interface
                
                # Clean the response text by removing markdown code blocks
                if response_text.startswith('```json'):
                    response_text = response_text[7:]  # Remove ```json
                if response_text.endswith('```'):
                    response_text = response_text[:-3]  # Remove ```
                response_text = response_text.strip()
                
                # Try to find the complete JSON by looking for the closing brace
                try:
                    judgment_data = json.loads(response_text)
                except json.JSONDecodeError as json_err:
                    # If JSON is incomplete, try to extract just the JSON part
                    # Look for the first complete JSON object
                    start_idx = response_text.find('{')
                    if start_idx != -1:
                        # Find the matching closing brace
                        brace_count = 0
                        end_idx = start_idx
                        for i, char in enumerate(response_text[start_idx:], start_idx):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        if brace_count == 0:
                            json_part = response_text[start_idx:end_idx]
                            judgment_data = json.loads(json_part)
                        else:
                            raise json_err
                    else:
                        raise json_err
            except json.JSONDecodeError as e:
                # Fallback if JSON parsing fails
                if hasattr(response, 'messages') and response.messages:
                    last_message = response.messages[-1]
                    response_text = last_message.content if hasattr(last_message, 'content') else str(last_message)
                else:
                    response_text = response.content if hasattr(response, 'content') else str(response)
                
                # Clean the response text by removing markdown code blocks
                if response_text.startswith('```json'):
                    response_text = response_text[7:]  # Remove ```json
                if response_text.endswith('```'):
                    response_text = response_text[:-3]  # Remove ```
                response_text = response_text.strip()
                
                # JSON parsing failed, using fallback
                judgment_data = self._parse_text_response(response_text)
            
            # Create judgment object
            judgment_value = judgment_data.get("judgment", "REJECTED").upper()
            # Map LLM responses to enum values
            if judgment_value == "NEEDS_REVISION":
                result = JudgmentResult.NEEDS_REVISION
            elif judgment_value == "APPROVED":
                result = JudgmentResult.APPROVED
            else:
                result = JudgmentResult.REJECTED
                
            judgment = EventJudgment(
                proposal_id=proposal.id,
                result=result,
                answerability_score=float(judgment_data.get("answerability_score", 0.0)),
                significance_score=float(judgment_data.get("significance_score", 0.0)),
                frequency_score=float(judgment_data.get("frequency_score", 0.0)),
                temporal_score=float(judgment_data.get("temporal_score", 0.0)),
                overall_score=float(judgment_data.get("overall_score", 0.0)),
                reasoning=judgment_data.get("reasoning", "No reasoning provided"),
                suggestions=judgment_data.get("suggestions", []),
                # Consolidated tagging
                primary_tag=judgment_data.get("primary_tag", "other"),
                secondary_tags=judgment_data.get("secondary_tags", []),
                tag_confidence=float(judgment_data.get("tag_confidence", 0.5))
            )
            
            # Save judgment metadata to database
            self._save_judgment_metadata(proposal, judgment)
            
            return judgment
            
        except Exception as e:
            print(f"Error judging proposal {proposal.id}: {e}")
            # Return a conservative judgment on error
            return EventJudgment(
                proposal_id=proposal.id,
                result=JudgmentResult.REJECTED,
                answerability_score=0.0,
                significance_score=0.0,
                frequency_score=1.0,
                temporal_score=0.0,
                overall_score=0.0,
                reasoning=f"Error during judgment: {str(e)}",
                suggestions=["Fix technical issues and re-evaluate"]
            )
    
    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """Parse a text response when JSON parsing fails."""
        # Simple fallback parsing
        return {
            "answerability_score": 0.5,
            "answerability_reasoning": "Unable to parse detailed response",
            "significance_score": 0.5,
            "significance_reasoning": "Unable to parse detailed response",
            "frequency_score": 0.5,
            "frequency_reasoning": "Unable to parse detailed response",
            "temporal_score": 0.5,
            "temporal_reasoning": "Unable to parse detailed response",
            "overall_score": 0.5,
            "judgment": "NEEDS_REVISION",
            "reasoning": "Parsing error. Unable to parse LLM response format.",
            "suggestions": ["Improve response format", "Re-evaluate with clearer criteria"]
        }
    
    def _mock_judgment(self, proposal: EventProposal) -> EventJudgment:
        """Create a mock judgment for offline mode."""
        # Simple heuristic-based judgment
        title_lower = proposal.title.lower()
        temporal_info = self._extract_temporal_info(proposal)
        
        # Answerability assessment
        answerability_score = 0.5
        if any(word in title_lower for word in ['will', 'by', 'before', 'on']):
            answerability_score += 0.2
        if any(word in title_lower for word in ['specific', 'exact', 'precise']):
            answerability_score += 0.2
        if '?' in proposal.title:
            answerability_score += 0.1
        
        # Check for options-style markets (binary bets on numerical ranges)
        is_options_market = any(phrase in title_lower for phrase in [
            'between', 'above', 'below', 'be >', 'be <', 'be at least', 'be at most',
            'be between', 'be above', 'be below', 'be over', 'be under'
        ]) and any(word in title_lower for word in [
            'rating', 'price', 'temperature', 'stock', 'bitcoin', 'ethereum', 'approval'
        ])
        
        # Significance assessment
        significance_score = 0.5
        if is_options_market:
            significance_score = 0.1  # Options markets are low significance
        else:
            significant_keywords = ['election', 'president', 'covid', 'war', 'crisis', 'major', 'important', 'significant']
            if any(word in title_lower for word in significant_keywords):
                significance_score += 0.3
            if any(word in title_lower for word in ['trump', 'biden', 'bitcoin', 'ethereum']):
                significance_score += 0.2
        
        # Frequency assessment (lower is better)
        frequency_score = 0.5
        if is_options_market:
            frequency_score = 0.1  # Options markets are high frequency (many similar bets)
        else:
            frequent_keywords = ['daily', 'weekly', 'monthly', 'regular', 'routine']
            if any(word in title_lower for word in frequent_keywords):
                frequency_score += 0.3
        
        # Temporal assessment
        temporal_score = 1.0 - (0.5 if temporal_info['is_past_event'] else 0.0)
        if temporal_info['is_past_event']:
            temporal_score = 0.0  # Past events get 0 temporal score
        elif any(year in title_lower for year in ['2025', '2026', '2027', '2028', '2029']):
            temporal_score = 1.0  # Future events get 1.0 temporal score
        else:
            temporal_score = 0.5  # Unclear temporal status
        
        # Calculate overall score
        overall_score = (
            answerability_score * self.weights['answerability'] +
            significance_score * self.weights['significance'] +
            (1.0 - frequency_score) * self.weights['frequency'] +  # Invert frequency score
            temporal_score * self.weights['temporal']
        )
        
        # Determine result
        if overall_score >= self.approval_threshold:
            result = JudgmentResult.APPROVED
        elif overall_score >= 0.5:
            result = JudgmentResult.NEEDS_REVISION
        else:
            result = JudgmentResult.REJECTED
        
        # Generate reasoning
        reasoning_parts = [f"Mock judgment based on keyword analysis. Overall score: {overall_score:.2f}"]
        if is_options_market:
            reasoning_parts.append("Detected as options-style market (binary bet on numerical range) - low significance and high frequency")
        reasoning_parts.append(f"Temporal: {temporal_score:.2f}")
        
        # Mock tagging based on keywords
        primary_tag = "other"
        secondary_tags = []
        
        if any(word in title_lower for word in ['election', 'president', 'congress', 'government', 'policy']):
            primary_tag = "politics"
            secondary_tags = ["government"]
        elif any(word in title_lower for word in ['bitcoin', 'ethereum', 'crypto', 'blockchain']):
            primary_tag = "crypto"
            secondary_tags = ["finance"]
        elif any(word in title_lower for word in ['stock', 'market', 'company', 'earnings']):
            primary_tag = "stock_market"
            secondary_tags = ["economics"]
        elif any(word in title_lower for word in ['ai', 'artificial intelligence', 'machine learning']):
            primary_tag = "ai"
            secondary_tags = ["technology"]
        elif any(word in title_lower for word in ['tech', 'software', 'hardware', 'innovation']):
            primary_tag = "technology"
            secondary_tags = []
        
        judgment = EventJudgment(
            proposal_id=proposal.id,
            result=result,
            answerability_score=answerability_score,
            significance_score=significance_score,
            frequency_score=frequency_score,
            temporal_score=temporal_score,
            overall_score=overall_score,
            reasoning=". ".join(reasoning_parts),
            suggestions=["Review for more specific criteria", "Consider significance factors"] if result != JudgmentResult.APPROVED else [],
            # Consolidated tagging
            primary_tag=primary_tag,
            secondary_tags=secondary_tags,
            tag_confidence=0.7  # Mock confidence
        )
        
        # Save judgment metadata to database
        self._save_judgment_metadata(proposal, judgment)
        
        return judgment
    
    def _save_judgment_metadata(self, proposal: EventProposal, judgment: EventJudgment):
        """Save judgment metadata to the proposal's meta_json."""
        try:
            with self.store.get_session() as session:
                # Get current meta_json
                current_meta = proposal.meta_json.copy() if proposal.meta_json else {}
                
                # Add judgment metadata
                judgment_meta = {
                    "judgment": {
                        "result": judgment.result.value,
                        "answerability_score": judgment.answerability_score,
                        "significance_score": judgment.significance_score,
                        "frequency_score": judgment.frequency_score,
                        "temporal_score": judgment.temporal_score,
                        "overall_score": judgment.overall_score,
                        "reasoning": judgment.reasoning,
                        "suggestions": judgment.suggestions,
                        "judged_at": datetime.utcnow().isoformat()
                    },
                    # Consolidated tagging
                    "primary_tag": judgment.primary_tag,
                    "secondary_tags": judgment.secondary_tags,
                    "tag_confidence": judgment.tag_confidence,
                    "tagged_at": datetime.utcnow().isoformat(),
                    "tagged_by": "judge_agent"
                }
                
                # Merge with existing metadata
                current_meta.update(judgment_meta)
                
                # Update the proposal in the database
                session.query(EventProposal).filter_by(id=proposal.id).update({
                    "meta_json": current_meta
                })
                session.commit()
                
        except Exception as e:
            print(f"Warning: Failed to save judgment metadata: {e}")
    
    async def judge_proposals(
        self, 
        proposals: List[EventProposal], 
        max_proposals: Optional[int] = None
    ) -> List[EventJudgment]:
        """Judge multiple event proposals."""
        if max_proposals:
            proposals = proposals[:max_proposals]
        
        judgments = []
        for i, proposal in enumerate(proposals):
            print(f"Judging proposal {i+1}/{len(proposals)}: {proposal.title[:60]}...")
            judgment = await self.judge_proposal(proposal)
            judgments.append(judgment)
            
            # Small delay to avoid rate limiting
            if not self.offline_mode:
                await asyncio.sleep(0.5)
        
        return judgments
    
    async def run_judgment_workflow(
        self, 
        max_proposals: Optional[int] = None,
        status_filter: str = "PENDING"
    ) -> Dict[str, Any]:
        """Run the complete judgment workflow."""
        start_time = time.time()
        
        try:
            # Get pending proposals
            with self.store.get_session() as session:
                if status_filter:
                    # Use raw SQL to avoid enum comparison issues
                    from sqlalchemy import text
                    limit_clause = f"LIMIT {max_proposals}" if max_proposals else ""
                    query_sql = f"""
                        SELECT * FROM event_proposals 
                        WHERE status = '{status_filter}' 
                        ORDER BY created_at DESC 
                        {limit_clause}
                    """
                    result = session.execute(text(query_sql))
                    proposals = [EventProposal(**dict(row._mapping)) for row in result]
                else:
                    query = session.query(EventProposal)
                    proposals = query.limit(max_proposals).all() if max_proposals else query.all()
            
            print(f"Found {len(proposals)} proposals to judge")
            
            if not proposals:
                return {
                    "success": True,
                    "proposals_judged": 0,
                    "approved": 0,
                    "rejected": 0,
                    "needs_revision": 0,
                    "execution_time": time.time() - start_time
                }
            
            # Judge proposals
            judgments = await self.judge_proposals(proposals)
            
            # Update proposal statuses based on judgments
            with self.store.get_session() as session:
                approved_count = 0
                rejected_count = 0
                needs_revision_count = 0
                
                for judgment in judgments:
                    # Get proposal using raw SQL to avoid enum issues
                    proposal_result = session.execute(text(f"SELECT * FROM event_proposals WHERE id = '{judgment.proposal_id}'")).first()
                    
                    if proposal_result:
                        # Create a simple object with the needed attributes
                        class SimpleProposal:
                            def __init__(self, row):
                                self.id = row.id
                                self.meta_json = row.meta_json
                        
                        proposal = SimpleProposal(proposal_result)
                        # Update proposal status using raw SQL to avoid enum issues
                        from sqlalchemy import text
                        if judgment.result == JudgmentResult.APPROVED:
                            session.execute(text("UPDATE event_proposals SET status = 'accepted' WHERE id = :proposal_id"), {"proposal_id": proposal.id})
                            approved_count += 1
                        elif judgment.result == JudgmentResult.REJECTED:
                            session.execute(text("UPDATE event_proposals SET status = 'rejected' WHERE id = :proposal_id"), {"proposal_id": proposal.id})
                            rejected_count += 1
                        else:  # NEEDS_REVISION
                            session.execute(text("UPDATE event_proposals SET status = 'pending' WHERE id = :proposal_id"), {"proposal_id": proposal.id})
                            needs_revision_count += 1
                        
                        # Store judgment metadata using raw SQL
                        judgment_meta = {
                            "judgment": {
                                "result": judgment.result.value,
                                "answerability_score": judgment.answerability_score,
                                "significance_score": judgment.significance_score,
                                "frequency_score": judgment.frequency_score,
                                "temporal_score": judgment.temporal_score,
                                "overall_score": judgment.overall_score,
                                "reasoning": judgment.reasoning,
                                "suggestions": judgment.suggestions,
                                "judged_at": datetime.utcnow().isoformat()
                            },
                            # Consolidated tagging
                            "primary_tag": judgment.primary_tag,
                            "secondary_tags": judgment.secondary_tags,
                            "tag_confidence": judgment.tag_confidence,
                            "tagged_at": datetime.utcnow().isoformat(),
                            "tagged_by": "judge_agent"
                        }
                        
                        # Update metadata using raw SQL
                        import json
                        meta_json_str = json.dumps(judgment_meta)
                        session.execute(text("""
                            UPDATE event_proposals 
                            SET meta_json = :meta_json 
                            WHERE id = :proposal_id
                        """), {"meta_json": meta_json_str, "proposal_id": proposal.id})
                
                session.commit()
            
            return {
                "success": True,
                "proposals_judged": len(judgments),
                "approved": approved_count,
                "rejected": rejected_count,
                "needs_revision": needs_revision_count,
                "execution_time": time.time() - start_time,
                "judgments": judgments
            }
            
        except Exception as e:
            print(f"Error in judgment workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
        
        finally:
            await self._cleanup_autogen()
