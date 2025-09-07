"""Polymarket prediction market adapter for fetching market events and data."""

import json
import ssl
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from ..core.types import RawItem, SourceType
    from ..core.hashing import hash_content
except ImportError:
    from core.types import RawItem, SourceType
    from core.hashing import hash_content


class PolymarketAdapter:
    """Adapter for fetching data from Polymarket prediction markets."""
    
    def __init__(self, timeout: int = 30, use_main_api: bool = True):
        """Initialize the Polymarket adapter."""
        self.timeout = timeout
        self.use_main_api = use_main_api
        self.base_url = "https://clob.polymarket.com" if use_main_api else "https://gamma-api.polymarket.com"
        
        # Create session with headers
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json", 
            "User-Agent": "sybil-fetch/0.5"
        })
    
    def close(self):
        """Close the HTTP session."""
        if self.session:
            self.session.close()
    
    def _get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 25,
        max_retries: int = 3,
        backoff: float = 1.5,
    ) -> Any:
        """Make HTTP request with retries and error handling."""
        last_exc = None
        for attempt in range(max_retries):
            try:
                r = self.session.get(url, params=params, timeout=timeout)
                ct = r.headers.get("content-type", "")
                if r.status_code != 200:
                    snippet = r.text[:300].replace("\n", " ")
                    raise RuntimeError(f"HTTP {r.status_code} for {url}; ct={ct}; body[:300]={snippet}")
                if "application/json" not in ct:
                    snippet = r.text[:300].replace("\n", " ")
                    raise RuntimeError(f"Non-JSON for {url}; ct={ct}; body[:300]={snippet}")
                return r.json()
            except Exception as e:
                last_exc = e
                if attempt < max_retries - 1:
                    time.sleep(backoff * (attempt + 1))
                else:
                    raise last_exc
    
    def _parse_iso_z(self, s: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string with Z suffix."""
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    

    
    def _has_featured_signal(self, m: Dict[str, Any]) -> bool:
        """Check if market has featured signal."""
        # direct boolean flags
        if isinstance(m.get("featured"), bool) and m["featured"]:
            return True
        if isinstance(m.get("isFeatured"), bool) and m["isFeatured"]:
            return True
        # tags / collections sometimes carry "featured"
        tags = m.get("tags") or []
        collections = m.get("collections") or []
        def _contains_featured(xs):
            try:
                return any(str(x).lower() == "featured" for x in xs)
            except Exception:
                return False
        if _contains_featured(tags) or _contains_featured(collections):
            return True
        return False
    
    def fetch_markets(self, limit: int = 50, category: Optional[str] = None, 
                     exclude_past: bool = True, min_days_future: int = 1) -> List[RawItem]:
        """Fetch markets with optional category filtering and time filtering."""
        url = f"{self.base_url}/markets"
        data = self._get_json(url)
        
        # Handle different API response structures
        if self.use_main_api:
            # Main API returns {"data": [...], "next_cursor": ..., "limit": ..., "count": ...}
            markets = data.get("data", [])
        else:
            # Gamma API returns list or {"markets": [...]}
            markets = data if isinstance(data, list) else data.get("markets", [])

        # Filter by category if specified
        if category:
            filtered_markets = []
            for market in markets:
                # Check if market belongs to the category
                market_category = market.get("category", "")
                if market_category and category.lower() in market_category.lower():
                    filtered_markets.append(market)
            markets = filtered_markets

        # Filter by time if requested
        if exclude_past:
            now = datetime.utcnow()
            future_markets = []
            for market in markets:
                # Handle different date field names
                end_date_str = market.get("endDate") or market.get("end_date_iso")
                end_dt = self._parse_iso_z(end_date_str)
                if end_dt and end_dt > now + timedelta(days=min_days_future):
                    future_markets.append(market)
            markets = future_markets
            print(f"🕒 Filtered to {len(markets)} future markets (excluding past events)")

        # Limit results
        markets = markets[:limit]
        
        # Convert to RawItem objects
        raw_items = []
        for market in markets:
            try:
                raw_item = self._parse_market(market)
                raw_items.append(raw_item)
            except Exception as e:
                print(f"⚠️ Error parsing market {market.get('id', 'unknown')}: {e}")
                continue
        
        print(f"✅ Fetched {len(raw_items)} Polymarket markets")
        return raw_items
    
    def fetch_markets_impactful(self, closing_hours: int = 72, include_archived: bool = False,
                               min_liquidity: float = 2000.0, min_open_interest: float = 5000.0) -> List[RawItem]:
        """Fetch impactful Polymarket markets (featured or high liquidity/OI)."""
        url = f"{self.base_url}/markets"
        data = self._get_json(url)
        markets = data if isinstance(data, list) else data.get("markets", [])

        now = datetime.utcnow()
        horizon = now + timedelta(hours=closing_hours) if closing_hours > 0 else None

        impactful = []
        fallbacks = []
        for m in markets:
            # Normalize fields
            active = bool(m.get("active"))
            end_dt = self._parse_iso_z(m.get("endDate"))
            closed_bool = m.get("closed")
            closed = bool(closed_bool) if isinstance(closed_bool, bool) else False

            # Time filters unless browsing archive
            if not include_archived:
                if not active:
                    continue
                if end_dt is None or end_dt <= now:
                    continue
                if horizon and end_dt > horizon:
                    continue

            # Featured signal or fallback by liquidity/OI
            is_featured = self._has_featured_signal(m)
            liq = float(m.get("liquidity") or 0)
            oi = float(m.get("openInterest") or 0)

            if not closed and is_featured:
                impactful.append(m)
            elif not closed and (liq >= min_liquidity or oi >= min_open_interest):
                fallbacks.append(m)

        # Sort by soonest endDate
        def end_key(x): 
            d = self._parse_iso_z(x.get("endDate"))
            return d if d else (now + timedelta(days=3650))

        impactful.sort(key=end_key)
        fallbacks.sort(key=end_key)

        # Prefer featured; append high-liquidity/OI as secondary
        all_markets = impactful + fallbacks
        
        # Convert to RawItem objects
        raw_items = []
        for market in all_markets:
            try:
                raw_item = self._parse_market(market)
                raw_items.append(raw_item)
            except Exception as e:
                print(f"⚠️ Error parsing market {market.get('id', 'unknown')}: {e}")
                continue
        
        print(f"✅ Fetched {len(raw_items)} impactful Polymarket markets")
        return raw_items
    
    def fetch_events_raw(self) -> List[RawItem]:
        """Fetch raw Polymarket events for metadata inspection."""
        url = f"{self.base_url}/events"
        data = self._get_json(url)
        events = data if isinstance(data, list) else data.get("events", [])
        
        # Convert to RawItem objects
        raw_items = []
        for event in events:
            try:
                raw_item = self._parse_event(event)
                raw_items.append(raw_item)
            except Exception as e:
                print(f"⚠️ Error parsing event {event.get('id', 'unknown')}: {e}")
                continue
        
        print(f"✅ Fetched {len(raw_items)} Polymarket events")
        return raw_items
    
    def _parse_market(self, market: Dict[str, Any]) -> RawItem:
        """Parse a Polymarket market into a RawItem."""
        # Handle different API field names
        market_id = market.get('id') or market.get('question_id', 'No ID')
        end_date = market.get('endDate') or market.get('end_date_iso', 'Unknown')
        
        # Create comprehensive content text
        content_parts = [
            f"Question: {market.get('question', 'No question')}",
            f"Description: {market.get('description', 'No description')}",
            f"Market ID: {market_id}",
            f"End Date: {end_date}",
            f"Category: {market.get('category', 'Unknown')}",
            f"Subcategory: {market.get('subcategory', 'Unknown')}",
        ]
        
        # Add market data if available
        if 'volume' in market and market['volume'] is not None:
            try:
                volume = float(market['volume'])
                content_parts.append(f"Volume: {volume:,.0f}")
            except (ValueError, TypeError):
                content_parts.append(f"Volume: {market['volume']}")
        
        if 'liquidity' in market and market['liquidity'] is not None:
            try:
                liquidity = float(market['liquidity'])
                content_parts.append(f"Liquidity: {liquidity:,.0f}")
            except (ValueError, TypeError):
                content_parts.append(f"Liquidity: {market['liquidity']}")
        
        if 'openInterest' in market and market['openInterest'] is not None:
            try:
                open_interest = float(market['openInterest'])
                content_parts.append(f"Open Interest: {open_interest:,.0f}")
            except (ValueError, TypeError):
                content_parts.append(f"Open Interest: {market['openInterest']}")
        
        # Add outcome token prices
        outcome_tokens = market.get('outcome_tokens', [])
        if outcome_tokens:
            content_parts.append("Outcome Prices:")
            for token in outcome_tokens:
                outcome = token.get('outcome', 'Unknown')
                price = token.get('price', 0)
                volume = token.get('volume', 0)
                try:
                    volume_num = float(volume)
                    content_parts.append(f"  {outcome}: {price:.3f} (volume: {volume_num:,.0f})")
                except (ValueError, TypeError):
                    content_parts.append(f"  {outcome}: {price:.3f} (volume: {volume})")
        
        # Add tags if available
        tags = market.get('tags', [])
        if tags:
            content_parts.append(f"Tags: {', '.join(tags)}")
        
        # Add featured status
        if self._has_featured_signal(market):
            content_parts.append("Featured: Yes")
        
        content_text = "\n".join(content_parts)
        
        # Create meta information
        meta_json = {
            "source": "polymarket",
            "market_id": market_id,
            "end_date": end_date,
            "category": market.get('category'),
            "subcategory": market.get('subcategory'),
            "volume": market.get('volume'),
            "liquidity": market.get('liquidity'),
            "open_interest": market.get('openInterest'),
            "outcome_tokens": outcome_tokens,
            "tags": tags,
            "featured": self._has_featured_signal(market),
            "active": market.get('active'),
            "closed": market.get('closed'),
            "market_type": "prediction_market",
            "platform": "polymarket",
            "api_source": "main" if self.use_main_api else "gamma",
            "fetched_at": datetime.utcnow().isoformat(),
            "raw_market_data": market
        }
        
        # Create hash
        content_hash = hash_content(content_text)
        
        # Create RawItem
        return RawItem(
            source_id="polymarket_api",
            external_id=market_id,
            raw_url=f"https://polymarket.com/market/{market_id}",
            title=market.get('question', 'Polymarket Market'),
            content_text=content_text,
            raw_content_hash=content_hash,
            fetched_at=datetime.utcnow(),
            meta_json=meta_json
        )
    
    def _parse_event(self, event: Dict[str, Any]) -> RawItem:
        """Parse a Polymarket event into a RawItem."""
        # Create comprehensive content text
        content_parts = [
            f"Title: {event.get('title', 'No title')}",
            f"Description: {event.get('description', 'No description')}",
            f"Event ID: {event.get('id', 'No ID')}",
            f"End Date: {event.get('endDate', 'Unknown')}",
            f"Category: {event.get('category', 'Unknown')}",
        ]
        
        content_text = "\n".join(content_parts)
        
        # Create meta information
        meta_json = {
            "source": "polymarket",
            "event_id": event.get('id'),
            "end_date": event.get('endDate'),
            "category": event.get('category'),
            "market_type": "prediction_event",
            "platform": "polymarket",
            "fetched_at": datetime.utcnow().isoformat(),
            "raw_event_data": event
        }
        
        # Create hash
        content_hash = hash_content(content_text)
        
        # Create RawItem
        return RawItem(
            source_id="polymarket_api",
            external_id=event.get('id'),
            raw_url=f"https://polymarket.com/event/{event.get('id', 'unknown')}",
            title=event.get('title', 'Polymarket Event'),
            content_text=content_text,
            raw_content_hash=content_hash,
            fetched_at=datetime.utcnow(),
            meta_json=meta_json
        )
    
    def fetch_market_by_id(self, market_id: str) -> Optional[RawItem]:
        """Fetch a specific market by ID."""
        print(f"🔍 Fetching Polymarket market: {market_id}")
        
        url = f"{self.base_url}/markets/{market_id}"
        data = self._get_json(url)
        market = data.get("market")
        
        if not market:
            print(f"❌ Market not found: {market_id}")
            return None
        
        try:
            return self._parse_market(market)
        except Exception as e:
            print(f"⚠️ Error parsing market {market_id}: {e}")
            return None
    
    def get_categories(self) -> List[str]:
        """Get available market categories."""
        if self.use_main_api:
            # Main API doesn't have categories endpoint, extract from markets
            try:
                url = f"{self.base_url}/markets"
                data = self._get_json(url)
                markets = data.get("data", [])
                
                # Extract unique categories from markets
                categories = set()
                for market in markets:
                    tags = market.get("tags", [])
                    if tags:
                        categories.update(tags)
                
                return sorted(list(categories))
            except Exception as e:
                print(f"⚠️ Error getting categories from main API: {e}")
                return ["All"]  # Fallback
        else:
            # Gamma API has categories endpoint
            try:
                url = f"{self.base_url}/categories"
                data = self._get_json(url)
                
                # Handle both list and dict responses
                if isinstance(data, list):
                    # Direct list of categories
                    categories = []
                    for cat in data:
                        if isinstance(cat, dict):
                            # Extract label from the category dict
                            label = cat.get("label", "")
                            if label:
                                categories.append(label)
                        elif isinstance(cat, str):
                            # Handle string categories
                            categories.append(cat)
                    return categories
                elif isinstance(data, dict):
                    # Dictionary with categories key
                    return [cat.get("name") for cat in data.get("categories", [])]
                else:
                    return []
            except Exception as e:
                print(f"⚠️ Error getting categories from gamma API: {e}")
                return ["All"]  # Fallback
