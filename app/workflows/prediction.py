"""
Prediction Workflow

This workflow handles the routine operation of:
- Fetching events from database
- Making predictions based on search and analysis
- Saving predictions to database
- Running the AutoGenAssessorAgent for event assessment
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..core.store import Store
from ..core.types import AgentRun, AgentType, Event, Prediction
from ..agents.predict import AutoGenAssessorAgent

logger = logging.getLogger(__name__)

@dataclass
class PredictionConfig:
    """Configuration for prediction workflow."""
    max_events_per_run: int = 5
    prediction_horizon_days: int = 30
    schedule_interval_hours: int = 8
    database_url: str = "sqlite:///./local.db"
    confidence_threshold: float = 0.6

class PredictionWorkflow:
    """Workflow for making predictions on events."""
    
    def __init__(self, config: PredictionConfig):
        self.config = config
        self.store = Store(config.database_url)
        self.assessor_agent = None
        
    async def initialize(self):
        """Initialize assessor agent and database."""
        logger.info("Initializing prediction workflow...")
        self.store.create_all()
        
        # Initialize the AutoGenAssessorAgent
        self.assessor_agent = AutoGenAssessorAgent()
        
        logger.info("Prediction workflow initialized")
    
    async def make_predictions(self) -> Dict[str, Any]:
        """Run the prediction process on available events."""
        logger.info("Starting prediction process...")
        
        try:
            # Get events that need predictions
            events = await self._get_events_for_prediction()
            
            if not events:
                logger.info("No events found for prediction")
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "events_processed": 0,
                    "predictions_created": 0,
                    "total_cost": 0.0
                }
            
            predictions_created = 0
            total_cost = 0.0
            processed_events = []
            
            for event in events:
                try:
                    # Make prediction for this event
                    prediction_result = await self._make_event_prediction(event)
                    
                    if prediction_result:
                        predictions_created += 1
                        total_cost += prediction_result.get("cost_usd", 0.0)
                        processed_events.append({
                            "event_id": event.id,
                            "event_key": event.key,
                            "prediction_confidence": prediction_result.get("confidence", 0.0)
                        })
                        
                except Exception as e:
                    logger.error(f"Error making prediction for event {event.id}: {e}")
                    continue
            
            results = {
                "timestamp": datetime.utcnow().isoformat(),
                "events_processed": len(processed_events),
                "predictions_created": predictions_created,
                "total_cost": total_cost,
                "processed_events": processed_events
            }
            
            logger.info(f"Prediction process completed: {predictions_created} predictions created for {len(processed_events)} events")
            return results
            
        except Exception as e:
            logger.error(f"Error in prediction process: {e}")
            raise
    
    async def _get_events_for_prediction(self) -> List[Event]:
        """Get events that need predictions."""
        # TODO: Implement logic to get events that need predictions
        # This should query the database for events that:
        # 1. Don't have recent predictions
        # 2. Are within the prediction horizon
        # 3. Meet the confidence threshold criteria
        return []
    
    async def _make_event_prediction(self, event: Event) -> Optional[Dict[str, Any]]:
        """Make a prediction for a specific event."""
        logger.info(f"Making prediction for event: {event.key}")
        
        try:
            # Run the assessor agent on this event
            result = await self.assessor_agent.run(event)
            
            # Save the agent run to database
            agent_run = AgentRun(
                agent_type=AgentType.ASSESSOR,
                input_json={"event_id": event.id, "event_key": event.key},
                output_json=result.output_json,
                meta_json=result.meta_json,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
                started_at=result.started_at,
                ended_at=result.ended_at
            )
            
            self.store.save_agent_run(agent_run)
            
            # Create prediction record
            prediction = Prediction(
                event_id=event.id,
                confidence_score=result.output_json.get("confidence", 0.0),
                probability=result.output_json.get("probability", 0.0),
                reasoning=result.output_json.get("reasoning", ""),
                agent_run_id=agent_run.id,
                created_at=datetime.utcnow()
            )
            
            self.store.save_prediction(prediction)
            
            return {
                "confidence": result.output_json.get("confidence", 0.0),
                "probability": result.output_json.get("probability", 0.0),
                "cost_usd": result.cost_usd,
                "agent_run_id": agent_run.id
            }
            
        except Exception as e:
            logger.error(f"Error making prediction for event {event.id}: {e}")
            return None
    
    async def run_scheduled(self):
        """Run the prediction workflow on a schedule."""
        logger.info(f"Starting scheduled predictions (every {self.config.schedule_interval_hours} hours)")
        
        while True:
            try:
                await self.make_predictions()
                await asyncio.sleep(self.config.schedule_interval_hours * 3600)
            except Exception as e:
                logger.error(f"Error in scheduled predictions: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.assessor_agent:
            await self.assessor_agent.cleanup()

# CLI interface for the workflow
async def main():
    """Main entry point for prediction workflow."""
    config = PredictionConfig(
        max_events_per_run=5,
        prediction_horizon_days=30,
        confidence_threshold=0.6
    )
    
    workflow = PredictionWorkflow(config)
    
    try:
        await workflow.initialize()
        results = await workflow.make_predictions()
        print(f"Prediction process completed: {results}")
    finally:
        await workflow.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
