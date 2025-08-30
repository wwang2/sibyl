"""Assessor agent for evaluating evidence and making predictions."""

import time
from datetime import datetime
from typing import List, Optional

from ..core.store import Store
from ..core.types import AgentRun, AgentType, Prediction, ProtoEvent
from ..llm.adk_client import ADKClient


class AssessorAgent:
    """Agent responsible for assessing evidence and making predictions."""
    
    def __init__(self, store: Store, max_proto_events: Optional[int] = None):
        """Initialize the assessor agent."""
        self.store = store
        self.llm_client = ADKClient()
        self.max_proto_events = max_proto_events
    
    def run(self, proto_events: List[ProtoEvent]) -> AgentRun:
        """Run the assessor agent on a list of proto events."""
        start_time = datetime.utcnow()
        
        # Apply proto events limit if specified
        if self.max_proto_events and len(proto_events) > self.max_proto_events:
            proto_events = proto_events[:self.max_proto_events]
            print(f"Limited to {len(proto_events)} proto events for assessment")
        
        # Initialize agent run
        agent_run = AgentRun(
            agent_type=AgentType.ASSESSOR,
            input_json={"proto_events_count": len(proto_events)},
            started_at=start_time
        )
        
        try:
            predictions_created = 0
            
            for proto_event in proto_events:
                # Get recent evidence for this proto event
                evidence_list = self.store.get_recent_evidence_for_proto_event(
                    proto_event.id, limit=10
                )
                
                if not evidence_list:
                    print(f"No evidence found for proto event {proto_event.id}")
                    continue
                
                # Get LLM prediction with detailed tracking
                llm_response, llm_interaction = self.llm_client.reason_prediction(evidence_list, agent_run.id)
                
                # Store the LLM interaction for audit
                self.store.add_llm_interaction(llm_interaction)
                
                # Create prediction
                prediction = Prediction(
                    proto_event_id=proto_event.id,
                    p=llm_response.p,
                    ttc_hours=llm_response.ttc_hours,
                    rationale=llm_response.rationale
                )
                
                # Save prediction to database
                saved_prediction = self.store.add_prediction(prediction)
                
                # Link prediction to evidence
                if llm_response.used_evidence_ids:
                    self.store.link_prediction_evidence(
                        saved_prediction.id,
                        llm_response.used_evidence_ids
                    )
                
                predictions_created += 1
                print(f"Created prediction for proto event {proto_event.id}: p={llm_response.p:.3f}")
            
            # Update agent run with results
            agent_run.output_json = {
                "proto_events_processed": len(proto_events),
                "predictions_created": predictions_created
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
