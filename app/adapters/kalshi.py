"""Kalshi prediction market adapter for fetching market events and data."""

import json
import ssl
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
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
        
        # Create headers for Kalshi API
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        # Create HTTP client
        self.client = httpx.Client(
            timeout=timeout,
            headers=self.headers,
            verify=False,
            follow_redirects=True
        )
    
    def close(self):
        """Close the HTTP client."""
        if self.client:
            self.client.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, ssl.SSLError))
    )
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the Kalshi API."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Error fetching from Kalshi API: {e}")
            raise e
    

    
    def fetch_markets(self, limit: int = 50, category: Optional[str] = None) -> List[RawItem]:
        """Fetch active prediction markets from Kalshi."""
        print(f"🔍 Fetching Kalshi markets (limit: {limit}, category: {category})")
        
        # Build API parameters
        params = {
            "limit": limit,
            "status": "open"
        }
        if category:
            params["category"] = category
        
        # Fetch data from API
        data = self._make_request("/markets", params)
        markets = data.get("markets", [])
        
        # Convert to RawItem objects
        raw_items = []
        for market in markets:
            try:
                raw_item = self._parse_market(market)
                raw_items.append(raw_item)
            except Exception as e:
                print(f"⚠️ Error parsing market {market.get('ticker', 'unknown')}: {e}")
                continue
        
        print(f"✅ Fetched {len(raw_items)} Kalshi markets")
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
    
    def fetch_market_by_ticker(self, ticker: str) -> Optional[RawItem]:
        """Fetch a specific market by ticker."""
        print(f"🔍 Fetching Kalshi market: {ticker}")
        
        data = self._make_request(f"/markets/{ticker}")
        market = data.get("market")
        
        if not market:
            print(f"❌ Market not found: {ticker}")
            return None
        
        try:
            return self._parse_market(market)
        except Exception as e:
            print(f"⚠️ Error parsing market {ticker}: {e}")
            return None
    
    def fetch_markets_current(self, limit: int = 100) -> List[RawItem]:
        """Fetch current Kalshi markets."""
        print(f"📊 Fetching Kalshi markets...")
        
        try:
            # Use the same approach as the original working script
            data = self._make_request("/markets")
            markets = data.get("markets", [])
            
            print(f"📈 Found {len(markets)} Kalshi markets")
            
            # Parse markets into RawItems
            raw_items = []
            for market in markets[:limit]:  # Limit the number of markets
                try:
                    raw_item = self._parse_market(market)
                    if raw_item:
                        raw_items.append(raw_item)
                except Exception as e:
                    print(f"⚠️ Error parsing market {market.get('ticker', 'unknown')}: {e}")
                    continue
            
            print(f"✅ Successfully parsed {len(raw_items)} Kalshi markets")
            return raw_items
            
        except Exception as e:
            print(f"❌ Error fetching Kalshi markets: {e}")
            return []

    def get_categories(self) -> List[str]:
        """Get available market categories by extracting from markets data."""
        try:
            # Get markets to extract categories
            data = self._make_request("/markets")
            markets = data.get("markets", [])
            
            # Extract unique categories from market data
            categories = set()
            for market in markets:
                # Look for category-like fields
                event_ticker = market.get("event_ticker", "")
                if event_ticker:
                    # Extract category from event_ticker (e.g., "SPORTS-TENNIS" -> "Tennis")
                    parts = event_ticker.split("-")
                    if len(parts) > 1:
                        category = parts[1].title()
                        categories.add(category)
                
                # Also check for other category fields
                market_type = market.get("market_type", "")
                if market_type:
                    categories.add(market_type.title())
            
            return sorted(list(categories))
        except Exception as e:
            print(f"⚠️ Error getting categories: {e}")
            return ["Sports", "Politics", "Economics"]  # Fallback categories
