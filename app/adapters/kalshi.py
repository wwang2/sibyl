"""Kalshi prediction market adapter for fetching market events and data."""

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


class KalshiAdapter:
    """Adapter for fetching data from Kalshi prediction markets."""
    
    def __init__(self, timeout: int = 30):
        """Initialize the Kalshi adapter."""
        self.timeout = timeout
        self.base_url = "https://api.elections.kalshi.com/trade-api/v2"
        
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
    
    def _iso(self, dt_obj: datetime) -> str:
        """Convert datetime to ISO format with Z suffix."""
        return dt_obj.replace(microsecond=0).isoformat() + "Z"
    
    def _parse_iso_z(self, s: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string with Z suffix."""
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    

    
    def kalshi_paginate_filtered(
        self,
        endpoint: str,
        *,
        status: Optional[str],
        min_close: Optional[datetime],
        max_close: Optional[datetime],
        limit: int,
        max_pages: int = 6,
    ) -> Dict[str, Any]:
        """Paginate through Kalshi API with filtering."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        cursor: Optional[str] = None
        items: List[Dict[str, Any]] = []
        pages = 0

        while True:
            params: Dict[str, Any] = {"limit": limit}
            if status:
                params["status"] = status  # e.g., "open"
            if min_close:
                params["min_close_date"] = self._iso(min_close)
            if max_close:
                params["max_close_date"] = self._iso(max_close)
            if cursor:
                params["cursor"] = cursor

            data = self._get_json(url, params=params)
            key = "markets" if "markets" in data else ("events" if "events" in data else None)
            if not key:
                raise RuntimeError(f"Unexpected Kalshi payload keys: {list(data.keys())}")

            items.extend(data.get(key, []) or [])
            cursor = data.get("cursor")
            pages += 1

            if not cursor or pages >= max_pages:
                break

        return {"items": items, "pages": pages}
    
    def fetch_markets_current(self, days_ahead: int = 90, include_archived: bool = False, 
                             limit: int = 1000, max_pages: int = 10) -> List[RawItem]:
        """Fetch current Kalshi markets with filtering."""
        now = datetime.utcnow()
        min_close = None if include_archived else now
        max_close = now + timedelta(days=days_ahead) if days_ahead > 0 else None
        status = None if include_archived else "open"
        
        result = self.kalshi_paginate_filtered(
            "markets", status=status, min_close=min_close, max_close=max_close, 
            limit=limit, max_pages=max_pages
        )
        
        # Convert to RawItem objects
        raw_items = []
        for market in result["items"]:
            try:
                raw_item = self._parse_market(market)
                raw_items.append(raw_item)
            except Exception as e:
                print(f"⚠️ Error parsing market {market.get('ticker', 'unknown')}: {e}")
                continue
        
        print(f"✅ Fetched {len(raw_items)} Kalshi markets (pages={result['pages']})")
        return raw_items
    
    def fetch_markets(self, limit: int = 50, category: Optional[str] = None) -> List[RawItem]:
        """Fetch markets with optional category filtering (for compatibility with mining scripts)."""
        # For now, just fetch current markets and filter by category if specified
        markets = self.fetch_markets_current(limit=limit)
        
        if category:
            # Filter by category based on event_ticker prefix
            filtered_markets = []
            for market in markets:
                meta = market.meta_json
                market_category = meta.get('category', '')
                if category.lower() in market_category.lower():
                    filtered_markets.append(market)
            markets = filtered_markets[:limit]
        
        return markets
    
    def fetch_events_current(self, days_ahead: int = 90, include_archived: bool = False, 
                            max_pages: int = 6) -> List[RawItem]:
        """Fetch current Kalshi events with filtering."""
        now = datetime.utcnow()
        min_close = None if include_archived else now
        max_close = now + timedelta(days=days_ahead) if days_ahead > 0 else None
        status = None if include_archived else "open"
        
        # events endpoint has a stricter limit cap → use 100 to avoid 400 invalid_parameters
        result = self.kalshi_paginate_filtered(
            "events", status=status, min_close=min_close, max_close=max_close, 
            limit=100, max_pages=max_pages
        )
        
        # Convert to RawItem objects
        raw_items = []
        for event in result["items"]:
            try:
                raw_item = self._parse_event(event)
                raw_items.append(raw_item)
            except Exception as e:
                print(f"⚠️ Error parsing event {event.get('ticker', 'unknown')}: {e}")
                continue
        
        print(f"✅ Fetched {len(raw_items)} Kalshi events (pages={result['pages']})")
        return raw_items
    
    def _parse_market(self, market: Dict[str, Any]) -> RawItem:
        """Parse a Kalshi market into a RawItem."""
        # Create comprehensive content text
        content_parts = [
            f"Title: {market.get('title', 'No title')}",
            f"Description: {market.get('description', 'No description')}",
            f"Ticker: {market.get('ticker', 'No ticker')}",
            f"Status: {market.get('status', 'Unknown')}",
            f"Close Time: {market.get('close_time', 'Unknown')}",
            f"Category: {market.get('category', 'Unknown')}",
            f"Subcategory: {market.get('subcategory', 'Unknown')}",
        ]
        
        # Add market data if available
        if 'yes_bid' in market and 'yes_ask' in market:
            content_parts.append(f"Current Price: {market['yes_bid']:.3f} - {market['yes_ask']:.3f}")
        
        if 'volume' in market:
            content_parts.append(f"Volume: {market['volume']:,}")
        
        content_text = "\n".join(content_parts)
        
        # Create meta information
        meta_json = {
            "source": "kalshi",
            "ticker": market.get('ticker'),
            "status": market.get('status'),
            "close_time": market.get('close_time'),
            "category": market.get('category'),
            "subcategory": market.get('subcategory'),
            "yes_bid": market.get('yes_bid'),
            "yes_ask": market.get('yes_ask'),
            "volume": market.get('volume'),
            "market_type": "prediction_market",
            "platform": "kalshi",
            "fetched_at": datetime.utcnow().isoformat(),
            "raw_market_data": market
        }
        
        # Create hash
        content_hash = hash_content(content_text)
        
        # Create RawItem
        return RawItem(
            source_id="kalshi_api",
            external_id=market.get('ticker'),
            raw_url=f"https://kalshi.com/markets/{market.get('ticker', 'unknown')}",
            title=market.get('title', 'Kalshi Market'),
            content_text=content_text,
            raw_content_hash=content_hash,
            fetched_at=datetime.utcnow(),
            meta_json=meta_json
        )
    
    def _parse_event(self, event: Dict[str, Any]) -> RawItem:
        """Parse a Kalshi event into a RawItem."""
        # Create comprehensive content text
        content_parts = [
            f"Title: {event.get('title', 'No title')}",
            f"Description: {event.get('description', 'No description')}",
            f"Ticker: {event.get('ticker', 'No ticker')}",
            f"Status: {event.get('status', 'Unknown')}",
            f"Close Time: {event.get('close_time', 'Unknown')}",
            f"Category: {event.get('category', 'Unknown')}",
            f"Subcategory: {event.get('subcategory', 'Unknown')}",
        ]
        
        content_text = "\n".join(content_parts)
        
        # Create meta information
        meta_json = {
            "source": "kalshi",
            "ticker": event.get('ticker'),
            "status": event.get('status'),
            "close_time": event.get('close_time'),
            "category": event.get('category'),
            "subcategory": event.get('subcategory'),
            "market_type": "prediction_event",
            "platform": "kalshi",
            "fetched_at": datetime.utcnow().isoformat(),
            "raw_event_data": event
        }
        
        # Create hash
        content_hash = hash_content(content_text)
        
        # Create RawItem
        return RawItem(
            source_id="kalshi_api",
            external_id=event.get('ticker'),
            raw_url=f"https://kalshi.com/events/{event.get('ticker', 'unknown')}",
            title=event.get('title', 'Kalshi Event'),
            content_text=content_text,
            raw_content_hash=content_hash,
            fetched_at=datetime.utcnow(),
            meta_json=meta_json
        )
    
    def fetch_market_by_ticker(self, ticker: str) -> Optional[RawItem]:
        """Fetch a specific market by ticker."""
        print(f"🔍 Fetching Kalshi market: {ticker}")
        
        url = f"{self.base_url}/markets/{ticker}"
        data = self._get_json(url)
        market = data.get("market")
        
        if not market:
            print(f"❌ Market not found: {ticker}")
            return None
        
        try:
            return self._parse_market(market)
        except Exception as e:
            print(f"⚠️ Error parsing market {ticker}: {e}")
            return None
    
    def get_categories(self) -> List[str]:
        """Get available market categories from markets data."""
        try:
            # Since /categories endpoint doesn't exist, extract categories from markets
            url = f"{self.base_url}/markets"
            data = self._get_json(url, params={"limit": 500})
            markets = data.get("markets", [])
            
            # Extract unique categories from event_ticker prefixes
            categories = set()
            for market in markets:
                event_ticker = market.get("event_ticker", "")
                if event_ticker:
                    # Extract category from event ticker (e.g., "KXATPMATCH" -> "Tennis")
                    prefix = event_ticker.split("-")[0] if "-" in event_ticker else event_ticker
                    if prefix.startswith("KX"):
                        # Map Kalshi prefixes to categories based on actual data
                        if "ETHD" in prefix or "ETH" in prefix:
                            categories.add("Crypto")
                        elif "DOGE" in prefix:
                            categories.add("Crypto")
                        elif "BTC" in prefix or "BITCOIN" in prefix:
                            categories.add("Crypto")
                        elif "ATP" in prefix or "WTA" in prefix or "TENNIS" in prefix:
                            categories.add("Tennis")
                        elif "UFC" in prefix or "FIGHT" in prefix:
                            categories.add("UFC")
                        elif "SPOTIFY" in prefix:
                            categories.add("Music")
                        elif "HIGH" in prefix:
                            categories.add("Weather")
                        elif "NBA" in prefix or "BASKETBALL" in prefix:
                            categories.add("Basketball")
                        elif "NFL" in prefix or "FOOTBALL" in prefix:
                            categories.add("Football")
                        elif "POLITICS" in prefix or "ELECTION" in prefix:
                            categories.add("Politics")
                        elif "ECONOMY" in prefix or "ECON" in prefix:
                            categories.add("Economics")
                        elif "TECH" in prefix or "TECHNOLOGY" in prefix:
                            categories.add("Technology")
                        else:
                            categories.add("Sports")  # Default for sports-related
                    else:
                        categories.add("Other")
            
            # If no categories found, return defaults
            if not categories:
                categories = {"Sports", "Politics", "Economics", "Technology", "Entertainment"}
            
            return sorted(list(categories))
        except Exception as e:
            print(f"Warning: Could not fetch categories from Kalshi: {e}")
            # Return some default categories
            return ["Politics", "Economics", "Sports", "Technology", "Entertainment"]
