"""Smart AutoGen discovery agent with dynamic source fetching."""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient
except ImportError:
    print("AutoGen not available. Install with: pip install autogen-agentchat autogen-ext[openai]")
    raise

try:
    from ..adapters.rss import RSSAdapter
    from ..adapters.kalshi import KalshiAdapter
    from ..adapters.polymarket import PolymarketAdapter
    from ..core.store import Store
    from ..core.types import AgentRun, EventProposal, RawItem, SourceType
except ImportError:
    from adapters.rss import RSSAdapter
    from adapters.kalshi import KalshiAdapter
    from adapters.polymarket import PolymarketAdapter
    from core.store import Store
    from core.types import AgentRun, EventProposal, RawItem, SourceType


class SmartDiscoveryAgent:
    """Smart AutoGen discovery agent with dynamic source fetching."""
    
    def __init__(
        self, 
        store: Store, 
        max_feeds: int = 5, 
        max_items_per_feed: int = 10,
        offline_mode: bool = False,
        model_name: str = "gemini-1.5-flash-8b"
    ):
        """Initialize the smart discovery agent."""
        self.store = store
        self.max_feeds = max_feeds
        self.max_items_per_feed = max_items_per_feed
        self.offline_mode = offline_mode
        self.model_name = model_name
        
        # Components
        self.assistant_agent = None
        self.rss_adapter = None
        self.kalshi_adapter = None
        self.polymarket_adapter = None
        self.llm_client = None
        
        # Tracking
        self.fetched_sources: List[str] = []
        self.fetched_items: List[RawItem] = []
        self.analysis_results: List[Dict[str, Any]] = []
        
        # Available data sources
        self.available_feeds = [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.npr.org/1001/rss.xml",
            "https://feeds.feedburner.com/oreilly/radar"
        ]
        
        # Available prediction market sources
        self.available_markets = [
            "kalshi_politics",
            "kalshi_economics", 
            "kalshi_technology",
            "polymarket_politics",
            "polymarket_crypto",
            "polymarket_ai"
        ]

    async def _initialize_autogen(self):
        """Initialize AutoGen components."""
        if self.assistant_agent is not None:
            return
            
        # Initialize LLM client
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
            
        self.llm_client = OpenAIChatCompletionClient(
            model=self.model_name,
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta"
        )
        
        # Initialize adapters
        self.rss_adapter = RSSAdapter(offline_mode=self.offline_mode)
        self.kalshi_adapter = KalshiAdapter()
        self.polymarket_adapter = PolymarketAdapter()
        
        # Initialize AutoGen assistant
        self.assistant_agent = AssistantAgent(
            name="smart_discovery_assistant",
            model_client=self.llm_client,
            system_message=self._get_system_message()
        )
        
    def _get_system_message(self) -> str:
        """Get the system message for the assistant agent."""
        feeds_list = "\n".join([f"- {feed}" for feed in self.available_feeds])
        markets_list = "\n".join([f"- {market}" for market in self.available_markets])
        
        return f"""You are an intelligent event discovery agent. Your job is to:

1. **Analyze available data sources** and strategically choose which ones to fetch
2. **Analyze fetched content** to identify potential predictable events
3. **Generate structured event proposals** with clear reasoning

**Available RSS Feeds:**
{feeds_list}

**Available Prediction Markets:**
{markets_list}

**Process:**
1. First, tell me which RSS feeds you want to fetch and why
2. I will fetch the content for you
3. Then analyze the content to identify potential predictable events
4. For each potential event, provide:
   - Clear, specific event title
   - Detailed description of what could happen
   - Confidence score (0.0-1.0)
   - Reasoning for why this is predictable

**Focus on events that are:**
- Specific and measurable
- Have clear timelines or milestones
- Can be tracked through public information
- Have reasonable probability of occurring

**IMPORTANT:** After analyzing content, provide your final analysis in this exact JSON format:

```json
{{
  "items": [
    {{
      "title": "Specific Event Title",
      "description": "Detailed description of what could happen",
      "confidence": 0.8,
      "reasoning": "Why this is predictable and trackable"
    }}
  ]
}}
```"""

    async def _cleanup_autogen(self):
        """Clean up AutoGen resources."""
        if self.rss_adapter:
            self.rss_adapter.close()
        if self.kalshi_adapter:
            self.kalshi_adapter.close()
        if self.polymarket_adapter:
            self.polymarket_adapter.close()
        self.rss_adapter = None
        self.kalshi_adapter = None
        self.polymarket_adapter = None
        self.assistant_agent = None
        self.llm_client = None
    
    def _fetch_rss_feed(self, url: str, max_items: int = 10) -> Dict[str, Any]:
        """Fetch RSS feed and return summary."""
        try:
            print(f"🔍 Fetching RSS feed: {url} (max {max_items} items)")
            
            # Fetch the feed
            raw_items = self.rss_adapter.fetch_feed(url)
            
            # Limit items
            if len(raw_items) > max_items:
                raw_items = raw_items[:max_items]
            
            # Save raw items to database
            saved_items = []
            for raw_item in raw_items:
                raw_item.source_id = url
                try:
                    saved_item = self.store.add_raw_item(raw_item)
                    saved_items.append(saved_item)
                    print(f"💾 Saved raw item: {raw_item.title[:50]}...")
                except Exception as e:
                    print(f"⚠️ Failed to save raw item: {e}")
                    saved_items.append(raw_item)
            
            # Track fetched sources and items
            if url not in self.fetched_sources:
                self.fetched_sources.append(url)
            self.fetched_items.extend(saved_items)
            
            # Create summary for the agent
            items_summary = []
            for item in raw_items:
                items_summary.append({
                    "title": item.title,
                    "description": item.content_text[:200] + "..." if len(item.content_text) > 200 else item.content_text,
                    "published": getattr(item, 'fetched_at', 'Unknown')
                })
            
            return {
                "success": True,
                "url": url,
                "items_fetched": len(raw_items),
                "items": items_summary
            }
            
        except Exception as e:
            print(f"❌ Error fetching {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "items_fetched": 0,
                "items": []
            }
    
    def _fetch_prediction_market(self, market_source: str, max_items: int = 10) -> Dict[str, Any]:
        """Fetch prediction market data and return summary."""
        try:
            print(f"🔍 Fetching prediction market: {market_source} (max {max_items} items)")
            
            # Parse market source
            if market_source.startswith("kalshi_"):
                category = market_source.replace("kalshi_", "")
                raw_items = self.kalshi_adapter.fetch_markets(limit=max_items, category=category.title())
            elif market_source.startswith("polymarket_"):
                category = market_source.replace("polymarket_", "")
                raw_items = self.polymarket_adapter.fetch_markets(limit=max_items, category=category.title())
            else:
                raise ValueError(f"Unknown market source: {market_source}")
            
            # Save raw items to database
            saved_items = []
            for raw_item in raw_items:
                raw_item.source_id = market_source
                try:
                    saved_item = self.store.add_raw_item(raw_item)
                    saved_items.append(saved_item)
                    print(f"💾 Saved market item: {raw_item.title[:50]}...")
                except Exception as e:
                    print(f"⚠️ Failed to save market item: {e}")
                    saved_items.append(raw_item)
            
            # Track fetched sources and items
            if market_source not in self.fetched_sources:
                self.fetched_sources.append(market_source)
            self.fetched_items.extend(saved_items)
            
            # Create summary for the agent
            items_summary = []
            for item in raw_items:
                items_summary.append({
                    "title": item.title,
                    "description": item.content_text[:200] + "..." if len(item.content_text) > 200 else item.content_text,
                    "published": getattr(item, 'fetched_at', 'Unknown'),
                    "market_type": item.meta_json.get('market_type', 'unknown')
                })
            
            return {
                "success": True,
                "source": market_source,
                "items_fetched": len(raw_items),
                "items": items_summary
            }
            
        except Exception as e:
            print(f"❌ Error fetching {market_source}: {e}")
            return {
                "success": False,
                "source": market_source,
                "error": str(e),
                "items_fetched": 0,
                "items": []
            }
    
    async def _run_async(self) -> AgentRun:
        """Run the discovery agent asynchronously."""
        try:
            await self._initialize_autogen()
            
            print(f"🚀 Starting smart discovery agent...")
            print(f"📊 Configuration: max_feeds={self.max_feeds}, max_items_per_feed={self.max_items_per_feed}")
            print(f"🤖 Model: {self.model_name}")
            print(f"🔧 Offline mode: {self.offline_mode}")
            
            # Step 1: Ask agent which sources to fetch
            source_selection_task = f"""I need you to help me discover predictable events. 

You can choose from RSS feeds and prediction markets:

**RSS Feeds:**
{chr(10).join([f"- {feed}" for feed in self.available_feeds])}

**Prediction Markets:**
{chr(10).join([f"- {market}" for market in self.available_markets])}

Please tell me which 2-3 sources you want to fetch and why you think they'll have good content for event discovery. 
- For RSS feeds, just list the URLs
- For prediction markets, list the market names (e.g., "kalshi_politics", "polymarket_crypto")"""

            print("🤖 Asking agent to select sources...")
            response1 = await self.assistant_agent.run(task=source_selection_task)
            
            # Extract sources from response
            sources_to_fetch = self._extract_sources_from_response(response1)
            print(f"📋 Agent selected {len(sources_to_fetch)} sources: {sources_to_fetch}")
            
            # Step 2: Fetch the selected sources
            fetched_content = []
            for source in sources_to_fetch[:self.max_feeds]:
                if source.startswith("http"):
                    # RSS feed
                    result = self._fetch_rss_feed(source, self.max_items_per_feed)
                else:
                    # Prediction market
                    result = self._fetch_prediction_market(source, self.max_items_per_feed)
                
                if result["success"]:
                    fetched_content.append(result)
            
            if not fetched_content:
                print("❌ No content was successfully fetched")
                return self._create_empty_result()
            
            # Step 3: Ask agent to analyze the fetched content
            content_summary = self._create_content_summary(fetched_content)
            analysis_task = f"""Now I've fetched content from the RSS feeds you selected. Here's what I found:

{content_summary}

Please analyze this content and identify potential predictable events. For each event you identify, provide:
- Clear, specific event title
- Detailed description of what could happen  
- Confidence score (0.0-1.0)
- Reasoning for why this is predictable

Provide your analysis in the exact JSON format I specified in your system message."""

            print("🧠 Asking agent to analyze content...")
            response2 = await self.assistant_agent.run(task=analysis_task)
            
            # Extract analysis from response
            self._extract_analysis_from_response(response2)
            
            # Generate final event proposals
            event_proposals = await self._generate_event_proposals()
            
            # Create agent run result
            result = AgentRun(
                agent_type="discovery",
                status="completed",
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                input_json={
                    "max_feeds": self.max_feeds,
                    "max_items_per_feed": self.max_items_per_feed,
                    "offline_mode": self.offline_mode,
                    "model_name": self.model_name
                },
                output_json={
                    "sources_fetched": len(self.fetched_sources),
                    "items_fetched": len(self.fetched_items),
                    "event_proposals_created": len(event_proposals),
                    "model_used": self.model_name
                },
                meta_json={
                    "fetched_sources": self.fetched_sources,
                    "analysis_results": self.analysis_results
                }
            )
            
            print(f"✅ Smart discovery completed: {result.output_json}")
            return result
            
        finally:
            await self._cleanup_autogen()
    
    def _extract_urls_from_response(self, response) -> List[str]:
        """Extract URLs from agent response."""
        urls = []
        if hasattr(response, 'messages') and response.messages:
            for message in response.messages:
                if hasattr(message, 'source') and message.source != 'user':
                    content = message.content
                    # Extract URLs using regex
                    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                    found_urls = re.findall(url_pattern, content)
                    urls.extend(found_urls)
        
        # Remove duplicates and return
        return list(set(urls))
    
    def _extract_sources_from_response(self, response) -> List[str]:
        """Extract sources (URLs and market names) from agent response."""
        sources = []
        if hasattr(response, 'messages') and response.messages:
            for message in response.messages:
                if hasattr(message, 'source') and message.source != 'user':
                    content = message.content
                    
                    # Extract URLs using regex
                    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                    found_urls = re.findall(url_pattern, content)
                    sources.extend(found_urls)
                    
                    # Extract market names (kalshi_* or polymarket_*)
                    market_pattern = r'(kalshi_\w+|polymarket_\w+)'
                    found_markets = re.findall(market_pattern, content)
                    sources.extend(found_markets)
        
        # Remove duplicates and return
        return list(set(sources))
    
    def _create_content_summary(self, fetched_content: List[Dict[str, Any]]) -> str:
        """Create a summary of fetched content for the agent."""
        summary_parts = []
        
        for content in fetched_content:
            source_name = content.get('url') or content.get('source', 'Unknown')
            summary_parts.append(f"\n**From {source_name}:**")
            summary_parts.append(f"Fetched {content['items_fetched']} items:")
            
            for item in content['items']:
                summary_parts.append(f"- {item['title']}")
                summary_parts.append(f"  {item['description']}")
                summary_parts.append(f"  Published: {item['published']}")
                if 'market_type' in item:
                    summary_parts.append(f"  Type: {item['market_type']}")
                summary_parts.append("")
        
        return "\n".join(summary_parts)
    
    def _extract_analysis_from_response(self, response):
        """Extract analysis results from agent response."""
        try:
            if hasattr(response, 'messages') and response.messages:
                for message in response.messages:
                    if hasattr(message, 'source') and message.source != 'user':
                        content = message.content
                        print(f"📝 Agent analysis: {content[:200]}...")
                        
                        # Look for JSON blocks in the response
                        json_pattern = r'```json\s*(\{.*?\})\s*```'
                        matches = re.findall(json_pattern, content, re.DOTALL)
                        
                        for match in matches:
                            try:
                                analysis = json.loads(match)
                                if isinstance(analysis, dict) and "items" in analysis:
                                    self.analysis_results.append(analysis)
                                    print(f"📊 Extracted analysis with {len(analysis.get('items', []))} items")
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            print(f"⚠️ Error extracting analysis: {e}")
    
    async def _generate_event_proposals(self) -> List[EventProposal]:
        """Generate event proposals from the analysis results."""
        proposals = []
        
        # Process analysis results
        for analysis in self.analysis_results:
            items = analysis.get("items", [])
            for item in items:
                try:
                    # Create event proposal request
                    try:
                        from ..core.types import CreateEventProposalRequest
                    except ImportError:
                        from core.types import CreateEventProposalRequest
                        
                    request = CreateEventProposalRequest(
                        raw_item_id="",  # Will be set by store
                        event_key=f"smart_{len(proposals)}_{int(datetime.utcnow().timestamp())}",
                        title=item.get("title", "Untitled Event"),
                        description=item.get("description", "No description provided"),
                        proposed_by="smart_discovery_agent",
                        confidence_score=float(item.get("confidence", 0.5)),
                        meta_json={
                            "model_used": self.model_name,
                            "analysis_source": "smart_discovery",
                            "fetched_sources": self.fetched_sources,
                            "reasoning": item.get("reasoning", "No reasoning provided")
                        }
                    )
                    
                    # Save to database
                    saved_proposal = self.store.create_event_proposal(request)
                    proposals.append(saved_proposal)
                    
                    print(f"📋 Created event proposal: {saved_proposal.title} (confidence: {saved_proposal.confidence_score:.2f})")
                    
                except Exception as e:
                    print(f"⚠️ Error creating proposal: {e}")
                    continue
        
        return proposals
    
    def _create_empty_result(self) -> AgentRun:
        """Create an empty result when no content is fetched."""
        return AgentRun(
            agent_type="discovery",
            status="completed",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            input_json={
                "max_feeds": self.max_feeds,
                "max_items_per_feed": self.max_items_per_feed,
                "offline_mode": self.offline_mode,
                "model_name": self.model_name
            },
            output_json={
                "sources_fetched": 0,
                "items_fetched": 0,
                "event_proposals_created": 0,
                "model_used": self.model_name
            },
            meta_json={
                "fetched_sources": [],
                "analysis_results": []
            }
        )
    
    def run(self) -> AgentRun:
        """Run the discovery agent (synchronous wrapper)."""
        try:
            # Check if we're already in an event loop
            loop = asyncio.get_running_loop()
            # If we are, run in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._run_async())
                return future.result()
        except RuntimeError:
            # No event loop running, we can use asyncio.run
            return asyncio.run(self._run_async())
    
    def get_pending_proposals(self) -> List[EventProposal]:
        """Get pending event proposals."""
        return self.store.get_pending_proposals()
    
    def print_discovery_summary(self):
        """Print a summary of the discovery process."""
        print("\n" + "="*60)
        print("SMART DISCOVERY SUMMARY")
        print("="*60)
        print(f"Sources Fetched: {len(self.fetched_sources)}")
        for source in self.fetched_sources:
            print(f"  - {source}")
        
        print(f"\nItems Fetched: {len(self.fetched_items)}")
        for item in self.fetched_items[:5]:  # Show first 5
            print(f"  - {item.title[:50]}...")
        if len(self.fetched_items) > 5:
            print(f"  ... and {len(self.fetched_items) - 5} more")
        
        print(f"\nAnalysis Results: {len(self.analysis_results)}")
        for i, analysis in enumerate(self.analysis_results):
            items = analysis.get("items", [])
            print(f"  Analysis {i+1}: {len(items)} items")
        
        print(f"\nModel Used: {self.model_name}")
        print("="*60)