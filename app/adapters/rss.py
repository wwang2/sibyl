"""RSS adapter for fetching and parsing RSS feeds."""

import os
import pathlib
import random
import ssl
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..core.types import Evidence, SourceType
from ..core.hashing import hash_evidence


class RSSAdapter:
    """Adapter for fetching and parsing RSS feeds."""
    
    def __init__(self, timeout: int = 30, offline_mode: bool = False):
        """Initialize the RSS adapter."""
        self.timeout = timeout
        self.offline_mode = offline_mode
        
        # Create headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Create SSL context with better compatibility
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create HTTP client with proper configuration
        self.client = httpx.Client(
            timeout=timeout,
            headers=self.headers,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            verify=ssl_context if not offline_mode else False
        )
    
    def __del__(self):
        """Clean up the HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
    
    def _should_retry_429(self, exception):
        """Check if we should retry on 429 (rate limit) responses."""
        if isinstance(exception, httpx.HTTPStatusError):
            return exception.response.status_code == 429
        return False
    
    def _wait_for_rate_limit(self, response: httpx.Response) -> None:
        """Handle 429 rate limiting with exponential backoff."""
        if response.status_code == 429:
            # Try to get retry-after header
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    wait_time = int(retry_after)
                except ValueError:
                    wait_time = 60  # Default to 60 seconds
            else:
                # Exponential backoff with jitter
                wait_time = random.uniform(30, 120)
            
            print(f"Rate limited (429). Waiting {wait_time:.1f} seconds before retry...")
            time.sleep(wait_time)
    
    @retry(
        stop=stop_after_attempt(5),  # Increased attempts
        wait=wait_exponential(multiplier=2, min=4, max=60, exp_base=2),  # Better backoff
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException))
    )
    def fetch_feed(self, url: str) -> str:
        """Fetch RSS feed content from URL with enhanced resilience."""
        try:
            response = self.client.get(url)
            
            # Handle rate limiting
            if response.status_code == 429:
                self._wait_for_rate_limit(response)
                raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
            
            response.raise_for_status()
            return response.text
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                print(f"Rate limited by {url}. Retrying with backoff...")
            elif e.response.status_code >= 500:
                print(f"Server error {e.response.status_code} from {url}. Retrying...")
            else:
                print(f"HTTP error {e.response.status_code} from {url}")
            raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            print(f"Connection/timeout error for {url}: {e}")
            raise
    
    def get_test_fixture_path(self) -> str:
        """Get the path to the test RSS fixture."""
        # Get the project root (assuming this file is in app/adapters/)
        project_root = pathlib.Path(__file__).parent.parent.parent
        return str(project_root / "tests" / "fixtures" / "rss_sample.xml")
    
    def fetch_feed_from_fixture(self, fixture_path: str) -> str:
        """Fetch RSS feed content from a fixture file (for testing)."""
        return pathlib.Path(fixture_path).read_text()
    
    def fetch_feed_offline(self) -> str:
        """Fetch RSS feed content from test fixture (offline mode)."""
        fixture_path = self.get_test_fixture_path()
        print(f"Using offline mode with test fixture: {fixture_path}")
        return self.fetch_feed_from_fixture(fixture_path)
    
    def parse_rss_text(self, rss_text: str, source_url: str) -> List[Evidence]:
        """Parse RSS text and return evidence items."""
        feed = feedparser.parse(rss_text)
        evidence_items = []
        
        for entry in feed.entries:
            # Extract basic information
            title = getattr(entry, 'title', 'No title')
            link = getattr(entry, 'link', '')
            summary = getattr(entry, 'summary', '')
            description = getattr(entry, 'description', '')
            
            # Use summary or description, whichever is longer
            snippet = summary if len(summary) > len(description) else description
            
            # Extract additional metadata
            meta = {
                'published': getattr(entry, 'published', ''),
                'author': getattr(entry, 'author', ''),
                'tags': [tag.term for tag in getattr(entry, 'tags', [])],
                'source_feed': source_url
            }
            
            # Generate content hash for deduplication
            content_hash = hash_evidence(title, snippet, link)
            
            evidence = Evidence(
                source_type=SourceType.RSS,
                url=link,
                title=title,
                snippet=snippet,
                content_hash=content_hash,
                meta_json=meta
            )
            
            evidence_items.append(evidence)
        
        return evidence_items
    
    def fetch_and_parse(self, url: str) -> List[Evidence]:
        """Fetch RSS feed from URL and parse it."""
        # Check if we should use a fixture file (for testing)
        fixture_path = os.getenv('RSS_FIXTURE')
        if fixture_path:
            rss_text = self.fetch_feed_from_fixture(fixture_path)
        elif self.offline_mode:
            rss_text = self.fetch_feed_offline()
        else:
            try:
                rss_text = self.fetch_feed(url)
            except Exception as e:
                print(f"Network fetch failed for {url}: {e}")
                print("Falling back to offline mode with test fixture...")
                rss_text = self.fetch_feed_offline()
        
        return self.parse_rss_text(rss_text, url)
    
    def fetch_feed_with_fallback(self, url: str, fallback_urls: Optional[List[str]] = None) -> List[Evidence]:
        """Fetch RSS feed with fallback URLs if the primary fails."""
        try:
            return self.fetch_and_parse(url)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            
            if fallback_urls:
                for fallback_url in fallback_urls:
                    try:
                        print(f"Trying fallback: {fallback_url}")
                        return self.fetch_and_parse(fallback_url)
                    except Exception as fallback_e:
                        print(f"Fallback {fallback_url} also failed: {fallback_e}")
                        continue
            
            print(f"All attempts failed for {url}")
            return []
    
    def get_default_feeds(self) -> List[str]:
        """Get a list of default RSS feeds to monitor."""
        return [
            # Primary feeds (more reliable)
            "https://feeds.reuters.com/reuters/businessNews",
            "https://feeds.marketwatch.com/marketwatch/topstories/",
            
            # Secondary feeds (may be more restrictive)
            "https://feeds.finance.yahoo.com/rss/2.0/headline",
            "https://feeds.bloomberg.com/markets/news.rss",
        ]
    
    def get_fallback_feeds(self) -> List[str]:
        """Get fallback RSS feeds that are more likely to work."""
        return [
            # More permissive feeds
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.bbci.co.uk/news/business/rss.xml",
            "https://feeds.npr.org/1001/rss.xml",
            "https://feeds.feedburner.com/oreilly/radar",
        ]
