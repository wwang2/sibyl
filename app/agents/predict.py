"""AutoGen-based assessor agent for evaluating events and making predictions using workflow pattern."""

import asyncio
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

try:
    from ..core.store import Store
    from ..core.types import (
        AgentRun, AgentType, Event, Protocol, ProtocolKind, RawItem, WorkflowRun, ToolCall, 
        ToolCallType, Prediction, CreateWorkflowRunRequest, CreatePredictionRequest,
        AddToolCallRequest
    )
except ImportError:
    from core.store import Store
    from core.types import (
        AgentRun, AgentType, Event, Protocol, ProtocolKind, RawItem, WorkflowRun, ToolCall, 
        ToolCallType, Prediction, CreateWorkflowRunRequest, CreatePredictionRequest,
        AddToolCallRequest
    )


class AutoGenAssessorAgent:
    """AutoGen-based agent responsible for assessing events and making predictions using workflow pattern."""
    
    def __init__(self, store: Store, max_events: Optional[int] = None, model_name: str = "gemini-1.5-flash-8b"):
        """Initialize the AutoGen assessor agent."""
        self.store = store
        self.max_events = max_events
        self.model_name = model_name
        
        # Initialize AutoGen components
        self.model_client = None
        self.assistant_agent = None
    
    async def _initialize_autogen(self):
        """Initialize AutoGen components."""
        if not self.model_client:
            self.model_client = OpenAIChatCompletionClient(model=self.model_name)
            self.assistant_agent = AssistantAgent("assessor_assistant", model_client=self.model_client)
    
    async def _cleanup_autogen(self):
        """Clean up AutoGen components."""
        if self.model_client:
            await self.model_client.close()
            self.model_client = None
            self.assistant_agent = None
    
    def run(self, events: List[Event]) -> AgentRun:
        """Run the AutoGen assessor agent on a list of events."""
        return asyncio.run(self._run_async(events))
    
    async def _run_async(self, events: List[Event]) -> AgentRun:
        """Async version of the run method."""
        start_time = datetime.utcnow()
        
        # Apply events limit if specified
        if self.max_events and len(events) > self.max_events:
            events = events[:self.max_events]
            print(f"Limited to {len(events)} events for assessment")
        
        # Initialize agent run
        agent_run = AgentRun(
            agent_type=AgentType.ASSESSOR,
            input_json={"events_count": len(events), "model": self.model_name},
            started_at=start_time
        )
        
        try:
            # Initialize AutoGen
            await self._initialize_autogen()
            
            # Get or create agent protocol
            protocol = self._get_or_create_agent_protocol()
            
            predictions_created = 0
            
            for event in events:
                print(f"Assessing event: {event.title}")
                
                # Create workflow run for this event
                workflow_request = CreateWorkflowRunRequest(
                    event_id=event.id,
                    protocol_id=protocol.id,
                    meta_json={"autogen_assessor_agent_run": True, "model": self.model_name}
                )
                workflow_run = self.store.create_workflow_run(workflow_request)
                
                try:
                    # Execute workflow steps with AutoGen
                    prediction = await self._execute_assessment_workflow_with_autogen(workflow_run, event, protocol)
                    
                    if prediction:
                        predictions_created += 1
                        print(f"Created prediction for event {event.id}: p={prediction.prediction.p:.3f}")
                    
                    # Complete workflow run
                    self.store.complete_workflow_run(workflow_run.id)
                    
                except Exception as e:
                    print(f"Error in workflow for event {event.id}: {e}")
                    # Mark workflow as failed
                    workflow_run.status = "failed"
                    workflow_run.ended_at = datetime.utcnow()
                    with self.store.get_session() as session:
                        session.commit()
                    continue
            
            # Update agent run with results
            agent_run.output_json = {
                "events_processed": len(events),
                "predictions_created": predictions_created,
                "model_used": self.model_name
            }
            
            agent_run.ended_at = datetime.utcnow()
            agent_run.latency_ms = int((agent_run.ended_at - start_time).total_seconds() * 1000)
            
            # Save agent run to database
            saved_run = self.store.add_agent_run(agent_run)
            
            return saved_run
            
        except Exception as e:
            # Handle errors
            agent_run.ended_at = datetime.utcnow()
            agent_run.output_json = {"error": str(e)}
            agent_run.latency_ms = int((agent_run.ended_at - start_time).total_seconds() * 1000)
            
            # Save error run to database
            saved_run = self.store.add_agent_run(agent_run)
            raise e
        finally:
            # Clean up AutoGen resources
            await self._cleanup_autogen()
    
    def _get_or_create_agent_protocol(self) -> Protocol:
        """Get or create the agent protocol."""
        with self.store.get_session() as session:
            try:
                from ..core.models import Protocol as ProtocolModel
            except ImportError:
                from core.models import Protocol as ProtocolModel
            
            # Look for existing agent protocol
            existing_protocol = session.query(ProtocolModel).filter_by(
                name="AutoGen Assessor Protocol",
                version="1.0.0"
            ).first()
            
            if existing_protocol:
                return Protocol(
                    id=existing_protocol.id,
                    name=existing_protocol.name,
                    kind=ProtocolKind(existing_protocol.kind),
                    version=existing_protocol.version,
                    description=existing_protocol.description,
                    created_at=existing_protocol.created_at
                )
            
            # Create new agent protocol
            protocol_model = ProtocolModel(
                name="AutoGen Assessor Protocol",
                kind=ProtocolKind.AGENT,
                version="1.0.0",
                description="AutoGen-based prediction protocol using LLM reasoning"
            )
            
            session.add(protocol_model)
            session.commit()
            session.refresh(protocol_model)
            
            return Protocol(
                id=protocol_model.id,
                name=protocol_model.name,
                kind=ProtocolKind(protocol_model.kind),
                version=protocol_model.version,
                description=protocol_model.description,
                created_at=protocol_model.created_at
            )
    
    async def _execute_assessment_workflow_with_autogen(self, workflow_run: WorkflowRun, event: Event, protocol: Protocol) -> Optional[Prediction]:
        """Execute the assessment workflow for an event using AutoGen."""
        
        # Step 1: Gather relevant raw items
        print(f"  Step 1: Gathering relevant raw items for event {event.id}")
        raw_items = self._gather_relevant_raw_items(event)
        
        tool_call_1 = ToolCall(
            workflow_run_id=workflow_run.id,
            step_number=1,
            tool_type=ToolCallType.DATA_FETCH,
            tool_name="gather_raw_items",
            args_json={"event_id": event.id, "event_title": event.title},
            result_json={"raw_items_count": len(raw_items), "raw_item_ids": [item.id for item in raw_items]},
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=100,
            success=True
        )
        self.store.add_tool_call(tool_call_1)
        
        if not raw_items:
            print(f"  No raw items found for event {event.id}")
            return None
        
        # Step 2: Analyze with AutoGen
        print(f"  Step 2: Analyzing {len(raw_items)} raw items with AutoGen")
        llm_response, llm_interaction = await self._analyze_with_autogen(raw_items, event, workflow_run.id)
        
        # Store LLM interaction as tool call
        tool_call_2 = ToolCall(
            workflow_run_id=workflow_run.id,
            step_number=2,
            tool_type=ToolCallType.LLM,
            tool_name=self.model_name,
            args_json={
                "prompt": f"Analyze the probability of event: {event.title}",
                "raw_items_count": len(raw_items)
            },
            result_json={
                "probability": llm_response.p,
                "rationale": llm_response.rationale,
                "used_evidence_ids": llm_response.used_evidence_ids
            },
            tokens_in=llm_interaction.tokens_in,
            tokens_out=llm_interaction.tokens_out,
            cost_usd=llm_interaction.cost_usd,
            latency_ms=llm_interaction.latency_ms,
            success=llm_interaction.success,
            error_message=llm_interaction.error_message
        )
        self.store.add_tool_call(tool_call_2)
        
        # Step 3: Create prediction with attributions
        print(f"  Step 3: Creating prediction with attributions")
        prediction_request = CreatePredictionRequest(
            workflow_run_id=workflow_run.id,
            protocol_id=protocol.id,
            p=llm_response.p,
            horizon_hours=24,  # Default 24-hour horizon
            rationale=llm_response.rationale,
            attribution_raw_item_ids=llm_response.used_evidence_ids or [item.id for item in raw_items[:3]]  # Top 3 items
        )
        
        prediction_with_attrs = self.store.create_prediction(prediction_request)
        
        # Step 4: Record calculation step
        tool_call_3 = ToolCall(
            workflow_run_id=workflow_run.id,
            step_number=3,
            tool_type=ToolCallType.CALCULATION,
            tool_name="create_prediction",
            args_json={
                "probability": llm_response.p,
                "horizon_hours": 24,
                "attribution_count": len(prediction_request.attribution_raw_item_ids)
            },
            result_json={
                "prediction_id": prediction_with_attrs.prediction.id,
                "attributions_created": len(prediction_with_attrs.attributions)
            },
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=50,
            success=True
        )
        self.store.add_tool_call(tool_call_3)
        
        return prediction_with_attrs
    
    async def _analyze_with_autogen(self, raw_items: List[RawItem], event: Event, workflow_run_id: str) -> tuple:
        """Analyze raw items with AutoGen and return prediction response."""
        try:
            from ..core.types import LLMResponse, LLMInteraction
        except ImportError:
            from core.types import LLMResponse, LLMInteraction
        
        # Prepare content for AutoGen analysis
        content_for_analysis = []
        for item in raw_items:
            content_for_analysis.append({
                "id": item.id,
                "title": item.title or "Untitled",
                "content": item.content_text or "No content",
                "url": item.raw_url,
                "fetched_at": item.fetched_at.isoformat()
            })
        
        # Create prompt for AutoGen
        prompt = self._create_assessment_prompt(event, content_for_analysis)
        
        start_time = datetime.utcnow()
        
        try:
            # Get AutoGen analysis
            print(f"    Sending assessment prompt to AutoGen ({self.model_name})...")
            response = await self.assistant_agent.run(task=prompt)
            print(f"    AutoGen assessment response received")
            
            # Extract the actual content from the AutoGen response
            response_content = None
            if hasattr(response, 'messages') and response.messages:
                print(f"    Found {len(response.messages)} messages in response")
                # Check all messages to find the assistant response
                for i, message in enumerate(response.messages):
                    print(f"    Message {i}: source={getattr(message, 'source', 'unknown')}")
                    if hasattr(message, 'source') and message.source != 'user':
                        response_content = message.content
                        print(f"    Found assistant message: {message.content[:100]}...")
                        break
            
            if response_content:
                print(f"    Extracted assessment content: {response_content[:200]}...")
                analysis_result = self._parse_autogen_assessment_response(response_content)
            else:
                print(f"    Could not extract content from response: {str(response)[:200]}...")
                analysis_result = self._parse_autogen_assessment_response(str(response))
            
            print(f"    Parsed assessment result: p={analysis_result.get('probability', 'N/A')}")
            
            end_time = datetime.utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Create LLM response
            llm_response = LLMResponse(
                p=analysis_result.get("probability", 0.5),
                ttc_hours=analysis_result.get("time_to_completion_hours", 24),
                rationale=analysis_result.get("rationale", "AutoGen analysis completed"),
                used_evidence_ids=analysis_result.get("used_evidence_ids", [item.id for item in raw_items[:3]])
            )
            
            # Create LLM interaction record
            llm_interaction = LLMInteraction(
                agent_run_id=workflow_run_id,
                model_name=self.model_name,
                prompt_text=prompt,
                response_text=str(response),
                tokens_in=analysis_result.get("tokens_in", 0),
                tokens_out=analysis_result.get("tokens_out", 0),
                cost_usd=analysis_result.get("cost_usd", 0.0),
                latency_ms=latency_ms,
                success=True
            )
            
            return llm_response, llm_interaction
            
        except Exception as e:
            end_time = datetime.utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Create fallback response
            llm_response = LLMResponse(
                p=0.5,  # Default probability
                ttc_hours=24,
                rationale=f"AutoGen analysis failed: {str(e)}",
                used_evidence_ids=[item.id for item in raw_items[:3]]
            )
            
            llm_interaction = LLMInteraction(
                agent_run_id=workflow_run_id,
                model_name=self.model_name,
                prompt_text=prompt,
                response_text=f"Error: {str(e)}",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=False,
                error_message=str(e)
            )
            
            return llm_response, llm_interaction
    
    def _create_assessment_prompt(self, event: Event, content_items: List[Dict[str, Any]]) -> str:
        """Create a prompt for AutoGen to assess event probability."""
        prompt = f"""You are a prediction expert. Analyze the following event and supporting evidence to provide a probability assessment.

EVENT TO PREDICT:
Title: {event.title}
Description: {event.description}

SUPPORTING EVIDENCE:
"""
        
        for i, item in enumerate(content_items, 1):
            prompt += f"""
Evidence {i}:
- Title: {item['title']}
- Content: {item['content'][:300]}...
- Source: {item['url']}
- Fetched: {item['fetched_at']}
"""
        
        prompt += f"""

Based on the evidence above, provide your assessment in the following JSON format:
{{
  "probability": 0.75,
  "time_to_completion_hours": 24,
  "rationale": "Detailed explanation of your reasoning, including which evidence supports your assessment and why",
  "used_evidence_ids": ["{content_items[0]['id'] if content_items else ''}", "..."],
  "tokens_in": 0,
  "tokens_out": 0,
  "cost_usd": 0.0
}}

Consider:
- How strong is the evidence for this event?
- What are the key factors that influence the probability?
- Which pieces of evidence are most relevant?
- What could prevent this event from happening?

Provide a probability between 0.0 and 1.0, where 0.0 means the event will definitely not happen and 1.0 means it will definitely happen.
"""
        
        return prompt
    
    def _parse_autogen_assessment_response(self, response: str) -> Dict[str, Any]:
        """Parse AutoGen response and extract assessment results."""
        try:
            import json
            import re
            
            # Convert response to string if it's not already
            response_str = str(response)
            print(f"    Parsing assessment response: {response_str[:300]}...")
            
            # Try multiple extraction methods
            json_str = None
            
            # Method 1: Look for ```json blocks
            if "```json" in response_str:
                json_start = response_str.find("```json") + 7
                json_end = response_str.find("```", json_start)
                if json_end > json_start:
                    json_str = response_str[json_start:json_end]
                    # Clean the extracted JSON string
                    json_str = json_str.strip()
                    # Remove any leading whitespace/newlines
                    while json_str.startswith(('\n', '\r', ' ', '\t')):
                        json_str = json_str[1:]
                    print(f"    Found JSON block: {json_str[:100]}...")
            
            # Method 2: Look for JSON objects
            if not json_str:
                json_pattern = r'\{.*\}'
                matches = re.findall(json_pattern, response_str, re.DOTALL)
                for match in matches:
                    try:
                        # Try to parse to validate it's valid JSON
                        test_parse = json.loads(match)
                        if isinstance(test_parse, dict):
                            json_str = match
                            print(f"    Found JSON object: {json_str[:100]}...")
                            break
                    except:
                        continue
            
            if json_str:
                # Clean the JSON string - remove leading/trailing whitespace and newlines
                json_str = json_str.strip()
                # More aggressive cleaning - remove any leading whitespace/newlines
                while json_str.startswith(('\n', '\r', ' ', '\t')):
                    json_str = json_str[1:]
                print(f"    Attempting to parse assessment JSON: {json_str[:200]}...")
                result = json.loads(json_str)
                print(f"    Successfully parsed assessment result")
                return result
            else:
                print(f"    No JSON found in assessment response")
                return self._create_fallback_assessment(response_str)
            
        except Exception as e:
            print(f"    Assessment JSON parsing failed with error: {e}")
            print(f"    Full stack trace:")
            import traceback
            traceback.print_exc()
            print(f"    Raw assessment response that failed to parse: {str(response)[:500]}...")
            return self._create_fallback_assessment(str(response))
    
    def _create_fallback_assessment(self, response: str) -> Dict[str, Any]:
        """Create fallback assessment when JSON parsing fails."""
        response_str = str(response)
        
        # Try to extract some useful information from the response
        probability = 0.5
        time_to_completion_hours = 24
        rationale = "AutoGen analysis completed but parsing failed"
        used_evidence_ids = []
        
        # Look for common patterns in the response
        import re
        
        if "probability" in response_str.lower():
            prob_matches = re.findall(r'"probability":\s*([0-9.]+)', response_str, re.IGNORECASE)
            if prob_matches:
                try:
                    probability = float(prob_matches[0])
                except:
                    pass
        
        if "time_to_completion" in response_str.lower():
            time_matches = re.findall(r'"time_to_completion_hours":\s*([0-9]+)', response_str, re.IGNORECASE)
            if time_matches:
                try:
                    time_to_completion_hours = int(time_matches[0])
                except:
                    pass
        
        if "rationale" in response_str.lower():
            rationale_matches = re.findall(r'"rationale":\s*"([^"]+)"', response_str, re.IGNORECASE)
            if rationale_matches:
                rationale = rationale_matches[0]
        
        return {
            "probability": probability,
            "time_to_completion_hours": time_to_completion_hours,
            "rationale": f"Fallback assessment: {rationale}",
            "used_evidence_ids": used_evidence_ids,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0
        }
    
    def _gather_relevant_raw_items(self, event: Event) -> List[RawItem]:
        """Gather raw items relevant to an event."""
        # For now, get recent raw items
        # In a more sophisticated implementation, this would use semantic search
        # or other methods to find the most relevant raw items
        
        with self.store.get_session() as session:
            try:
                from ..core.models import RawItem as RawItemModel
            except ImportError:
                from core.models import RawItem as RawItemModel
            
            # Get recent raw items (simplified approach)
            recent_items = session.query(RawItemModel).order_by(
                RawItemModel.fetched_at.desc()
            ).limit(10).all()
            
            # Convert to Pydantic models
            raw_items = []
            for item in recent_items:
                raw_items.append(RawItem(
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
            
            return raw_items
    
    def get_autogen_assessment_summary(self) -> Dict[str, Any]:
        """Get a summary of AutoGen assessment results from recent predictions."""
        try:
            from ..core.types import Prediction
        except ImportError:
            from core.types import Prediction
            
        # Get recent predictions
        recent_predictions = self.store.get_recent_predictions(limit=10)
        
        assessment_summary = {
            "total_predictions": len(recent_predictions),
            "autogen_assessed": 0,
            "assessments": []
        }
        
        for prediction_with_attrs in recent_predictions:
            prediction = prediction_with_attrs.prediction
            if prediction.rationale and "AutoGen" in prediction.rationale:
                assessment_summary["autogen_assessed"] += 1
                assessment_summary["assessments"].append({
                    "prediction_id": prediction.id,
                    "event_id": prediction.workflow_run_id,  # This is actually workflow_run_id
                    "probability": prediction.p,
                    "rationale": prediction.rationale,
                    "horizon_hours": prediction.horizon_hours,
                    "created_at": prediction.created_at
                })
        
        return assessment_summary
    
    def print_autogen_assessment_summary(self):
        """Print a formatted summary of AutoGen assessment results."""
        summary = self.get_autogen_assessment_summary()
        
        print("\n" + "="*60)
        print("AUTOGEN ASSESSMENT SUMMARY")
        print("="*60)
        print(f"Total Predictions: {summary['total_predictions']}")
        print(f"AutoGen Assessed: {summary['autogen_assessed']}")
        print()
        
        for i, assessment in enumerate(summary['assessments'], 1):
            print(f"Assessment {i}:")
            print(f"  Prediction ID: {assessment['prediction_id']}")
            print(f"  Probability: {assessment['probability']:.3f}")
            print(f"  Horizon: {assessment['horizon_hours']} hours")
            print(f"  Rationale: {assessment['rationale'][:150]}...")
            print(f"  Created: {assessment['created_at']}")
            print()
