"""Google AI SDK client for LLM calls."""

import json
import random
import time
from typing import Any, Dict, List
import re
import google.generativeai as genai


from ..config import settings
from ..core.types import Evidence, LLMInteraction, LLMResponse


class ADKClient:
    """Google AI SDK client for making LLM calls."""
    
    def __init__(self):
        """Initialize the ADK client."""
        self.model_name = settings.model
        self.api_key = settings.google_api_key
        self.llm_mode = settings.llm_mode
        self.mock_seed = settings.mock_seed
        
        if self.llm_mode == "live":
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            # Set random seed for deterministic mock responses
            random.seed(self.mock_seed)
    
    def reason_prediction(self, evidence_list: List[Evidence], agent_run_id: str = None) -> tuple[LLMResponse, LLMInteraction]:
        """Reason about evidence and return a prediction with detailed interaction record."""
        if self.llm_mode == "mock":
            return self._mock_reason_prediction(evidence_list, agent_run_id)
        else:
            return self._live_reason_prediction(evidence_list, agent_run_id)
    
    def _mock_reason_prediction(self, evidence_list: List[Evidence], agent_run_id: str = None) -> tuple[LLMResponse, LLMInteraction]:
        """Generate a mock prediction for testing."""
        start_time = time.time()
        
        # Use evidence length and seed to generate deterministic but varied responses
        evidence_count = len(evidence_list)
        
        # Generate probability based on evidence count and seed
        base_prob = 0.3 + (evidence_count * 0.1)
        noise = random.uniform(-0.2, 0.2)
        p = max(0.0, min(1.0, base_prob + noise))
        
        # Generate TTC based on evidence recency and count
        ttc_hours = random.randint(1, 168)  # 1 hour to 1 week
        
        # Generate rationale based on evidence
        rationale = f"Based on {evidence_count} pieces of evidence, "
        if evidence_count > 3:
            rationale += "there is strong indication of an upcoming event. "
        elif evidence_count > 1:
            rationale += "there are some signs pointing to a potential event. "
        else:
            rationale += "there is limited evidence but some indicators suggest a possible event. "
        
        rationale += f"The probability is estimated at {p:.2f} with expected time to completion of {ttc_hours} hours."
        
        # Select evidence IDs to use
        used_evidence_ids = [e.id for e in evidence_list[:min(3, len(evidence_list))]]
        
        # Create mock prompt and response
        prompt_text = f"Analyze {evidence_count} pieces of evidence and provide prediction."
        response_text = f'{{"p": {p:.3f}, "ttc_hours": {ttc_hours}, "rationale": "{rationale}", "used_evidence_ids": {used_evidence_ids}}}'
        
        # Calculate mock metrics
        latency_ms = int((time.time() - start_time) * 1000)
        tokens_in = len(prompt_text.split())
        tokens_out = len(response_text.split())
        cost_usd = 0.0  # Mock mode is free
        
        # Create interaction record
        interaction = LLMInteraction(
            agent_run_id=agent_run_id or "mock_run",
            model_name=f"{self.model_name}_mock",
            prompt_text=prompt_text,
            response_text=response_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=True,
            metadata={
                "mode": "mock",
                "seed": self.mock_seed,
                "evidence_count": evidence_count
            }
        )
        
        response = LLMResponse(
            p=p,
            ttc_hours=ttc_hours,
            rationale=rationale,
            used_evidence_ids=used_evidence_ids
        )
        
        return response, interaction
    
    def _parse_json_response(self, s: str) -> Dict[str, Any]:
        # 1) If wrapped in matching quotes, strip them
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
            s = s[1:-1]

        # 2) If there's a fenced code block, extract the JSON inside
        m = re.search(r"```(?:json)?\s*(\{.*?\}|$begin:math:display$.*?$end:math:display$)\s*```", s, re.DOTALL)
        if m:
            s = m.group(1)

        # 3) Trim and load
        s = s.strip()
        return json.loads(s)
    
    def _live_reason_prediction(self, evidence_list: List[Evidence], agent_run_id: str = None) -> tuple[LLMResponse, LLMInteraction]:
        """Generate a live prediction using Google AI."""
        start_time = time.time()
        
        # Prepare the prompt
        evidence_text = self._format_evidence_for_prompt(evidence_list)
        
        prompt = f"""
You are an expert analyst tasked with predicting future events based on evidence from news sources.

Evidence:
{evidence_text}

Please analyze this evidence and provide a prediction in the following JSON format:
{{
    "p": <probability between 0.0 and 1.0>,
    "ttc_hours": <time to completion in hours, or null if uncertain>,
    "rationale": "<explanation of your reasoning>",
    "used_evidence_ids": ["<list of evidence IDs that were most relevant>"]
}}

Consider:
- The credibility and recency of the sources
- The specificity and clarity of the information
- Any patterns or trends in the evidence
- The likelihood of the event occurring based on the available information

Respond only with valid JSON.
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse the JSON response
            result = self._parse_json_response(response_text)

            print(result)
            
            # Validate and create LLMResponse
            llm_response = LLMResponse(
                p=float(result.get("p", 0.5)),
                ttc_hours=result.get("ttc_hours"),
                rationale=result.get("rationale", "No rationale provided"),
                used_evidence_ids=result.get("used_evidence_ids", [])
            )
            
            # Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)
            tokens_in = len(prompt.split())
            tokens_out = len(response_text.split())
            
            # Estimate cost based on Gemini pricing (approximate)
            # Gemini 1.5 Flash: $0.075 per 1M input tokens, $0.30 per 1M output tokens
            cost_per_input_token = 0.075 / 1_000_000
            cost_per_output_token = 0.30 / 1_000_000
            cost_usd = (tokens_in * cost_per_input_token) + (tokens_out * cost_per_output_token)
            
            # Create interaction record
            interaction = LLMInteraction(
                agent_run_id=agent_run_id or "live_run",
                model_name=self.model_name,
                prompt_text=prompt,
                response_text=response_text,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                success=True,
                metadata={
                    "mode": "live",
                    "evidence_count": len(evidence_list),
                    "parsed_result": result
                }
            )
            
            return llm_response, interaction
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # Create error interaction record
            latency_ms = int((time.time() - start_time) * 1000)
            error_interaction = LLMInteraction(
                agent_run_id=agent_run_id or "error_run",
                model_name=self.model_name,
                prompt_text=prompt,
                response_text="",
                tokens_in=len(prompt.split()),
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=False,
                error_message=str(e),
                metadata={
                    "mode": "live",
                    "error_type": type(e).__name__,
                    "evidence_count": len(evidence_list)
                }
            )
            
            # Fallback to mock response if live call fails
            print(f"Live LLM call failed: {e}. Falling back to mock response.")
            mock_response, mock_interaction = self._mock_reason_prediction(evidence_list, agent_run_id)
            return mock_response, error_interaction
    
    def _format_evidence_for_prompt(self, evidence_list: List[Evidence]) -> str:
        """Format evidence for the LLM prompt."""
        formatted_evidence = []
        
        for i, evidence in enumerate(evidence_list, 1):
            formatted_evidence.append(f"""
Evidence {i} (ID: {evidence.id}):
- Source: {evidence.source_type.value}
- Title: {evidence.title}
- URL: {evidence.url}
- Snippet: {evidence.snippet}
- Published: {evidence.meta_json.get('published', 'Unknown')}
""")
        
        return "\n".join(formatted_evidence)
