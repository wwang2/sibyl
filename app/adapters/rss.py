"""RSS adapter for fetching and parsing RSS feeds with event sourcing."""

import os
import pathlib
import random
import ssl
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from ..core.types import RawItem, SourceType
    from ..core.hashing import hash_content
except ImportError:
    from core.types import RawItem, SourceType
    from core.hashing import hash_content


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
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        # Create HTTP client with proper configuration
        self.client = httpx.Client(
            timeout=timeout,
            headers=self.headers,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            verify=ssl_context if not offline_mode else False
        )
    
    def get_default_feeds(self) -> List[str]:
        """Get default RSS feeds for testing."""
        if self.offline_mode:
            return ["https://example.com/test-feed"]
        
        return [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.npr.org/1001/rss.xml",
            "https://feeds.feedburner.com/oreilly/radar"
        ]
    
    def get_fallback_feeds(self) -> List[str]:
        """Get fallback RSS feeds."""
        return [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss"
        ]
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, ssl.SSLError))
    )
    def fetch_feed_with_fallback(self, primary_url: str, fallback_urls: List[str]) -> List[RawItem]:
        """Fetch RSS feed with fallback URLs."""
        urls_to_try = [primary_url] + fallback_urls
        
        for url in urls_to_try:
            try:
                print(f"Trying to fetch: {url}")
                raw_items = self.fetch_feed(url)
                if raw_items:
                    print(f"Successfully fetched {len(raw_items)} items from {url}")
                    return raw_items
                else:
                    print(f"No items found from {url}")
            except Exception as e:
                print(f"Failed to fetch {url}: {e}")
                continue
        
        print(f"All URLs failed for primary: {primary_url}")
        return []
    
    def fetch_feed(self, url: str) -> List[RawItem]:
        """Fetch and parse a single RSS feed."""
        if self.offline_mode:
            return self._get_offline_feed_data()
        
        try:
            response = self.client.get(url)
            response.raise_for_status()
            
            # Parse the feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                print(f"Warning: Feed parsing issues for {url}: {feed.bozo_exception}")
            
            raw_items = []
            for entry in feed.entries[:10]:  # Limit to 10 items per feed
                raw_item = self._parse_entry(entry, url)
                if raw_item:
                    raw_items.append(raw_item)
            
            return raw_items
            
        except Exception as e:
            print(f"Error fetching feed {url}: {e}")
            return []
    
    def _parse_entry(self, entry: Any, source_url: str) -> Optional[RawItem]:
        """Parse a single RSS entry into a RawItem with comprehensive audit information."""
        try:
            # Extract basic information
            title = getattr(entry, 'title', 'Untitled')
            link = getattr(entry, 'link', '')
            description = getattr(entry, 'description', '')
            published = getattr(entry, 'published_parsed', None)
            guid = getattr(entry, 'guid', link)
            
            # Extract additional fields for comprehensive auditing
            author = getattr(entry, 'author', '')
            author_detail = getattr(entry, 'author_detail', {})
            summary = getattr(entry, 'summary', '')
            content = getattr(entry, 'content', [])
            enclosures = getattr(entry, 'enclosures', [])
            comments = getattr(entry, 'comments', '')
            tags = getattr(entry, 'tags', [])
            categories = getattr(entry, 'categories', [])
            
            # Extract feed-level information
            feed_title = getattr(entry, 'feed', {}).get('title', '') if hasattr(entry, 'feed') else ''
            feed_link = getattr(entry, 'feed', {}).get('link', '') if hasattr(entry, 'feed') else ''
            feed_description = getattr(entry, 'feed', {}).get('description', '') if hasattr(entry, 'feed') else ''
            
            # Create comprehensive content for hashing (include all text fields)
            full_content = f"{title}\n{description}\n{summary}"
            if content:
                if isinstance(content, list):
                    full_content += "\n" + "\n".join([str(c) for c in content])
                else:
                    full_content += f"\n{content}"
            
            content_hash = hash_content(full_content)
            
            # Create comprehensive meta information for auditing
            meta_json = {
                # Basic identification
                "guid": guid,
                "external_id": guid,
                "source_url": source_url,
                "raw_url": link,
                
                # Publication information
                "published": time.strftime('%Y-%m-%dT%H:%M:%S', published) if published else None,
                "published_parsed": list(published) if published else None,
                "updated": getattr(entry, 'updated', ''),
                "updated_parsed": list(getattr(entry, 'updated_parsed', None)) if getattr(entry, 'updated_parsed', None) else None,
                
                # Author information
                "author": author,
                "author_detail": {
                    "name": getattr(author_detail, 'name', '') if hasattr(author_detail, 'name') else '',
                    "email": getattr(author_detail, 'email', '') if hasattr(author_detail, 'email') else '',
                    "href": getattr(author_detail, 'href', '') if hasattr(author_detail, 'href') else ''
                } if author_detail else {},
                
                # Content information
                "title": title,
                "description": description,
                "summary": summary,
                "content": content if isinstance(content, (str, list)) else str(content),
                "content_length": len(full_content),
                "word_count": len(full_content.split()),
                
                # Classification
                "tags": [tag.term for tag in tags] if tags else [],
                "tag_details": [{"term": tag.term, "label": getattr(tag, 'label', ''), "scheme": getattr(tag, 'scheme', '')} for tag in tags] if tags else [],
                "categories": [cat for cat in categories] if categories else [],
                
                # Media and enclosures
                "enclosures": [{
                    "href": getattr(enc, 'href', ''),
                    "type": getattr(enc, 'type', ''),
                    "length": getattr(enc, 'length', ''),
                    "title": getattr(enc, 'title', '')
                } for enc in enclosures] if enclosures else [],
                
                # Comments and interaction
                "comments": comments,
                "comment_count": getattr(entry, 'comment_count', None),
                
                # Feed information
                "feed_title": feed_title,
                "feed_link": feed_link,
                "feed_description": feed_description,
                
                # Technical metadata
                "language": getattr(entry, 'language', ''),
                "rights": getattr(entry, 'rights', ''),
                "source": getattr(entry, 'source', {}),
                
                # Parsing metadata
                "parsed_at": datetime.utcnow().isoformat(),
                "parser_version": "enhanced_rss_adapter_v1",
                "content_hash": content_hash,
                "fetch_method": "rss_adapter",
                
                # Quality indicators
                "has_title": bool(title and title.strip()),
                "has_description": bool(description and description.strip()),
                "has_author": bool(author and author.strip()),
                "has_tags": bool(tags),
                "has_categories": bool(categories),
                "has_enclosures": bool(enclosures),
                "content_quality_score": self._calculate_content_quality(title, description, summary, author, tags)
            }
            
            # Create RawItem with comprehensive content
            raw_item = RawItem(
                source_id="",  # Will be set by caller
                external_id=guid,
                raw_url=link,
                title=title,
                content_text=full_content,  # Use comprehensive content instead of just description
                raw_content_hash=content_hash,
                meta_json=meta_json
            )
            
            return raw_item
            
        except Exception as e:
            print(f"Error parsing entry: {e}")
            return None
    
    def _calculate_content_quality(self, title: str, description: str, summary: str, author: str, tags: list) -> float:
        """Calculate a quality score for the content (0.0-1.0)."""
        score = 0.0
        
        # Title quality (30% weight)
        if title and title.strip():
            score += 0.3
            if len(title) > 10:  # More descriptive titles
                score += 0.1
        
        # Description quality (40% weight)
        if description and description.strip():
            score += 0.4
            if len(description) > 100:  # Substantial content
                score += 0.1
            if len(description) > 500:  # Very detailed content
                score += 0.1
        
        # Summary quality (20% weight)
        if summary and summary.strip():
            score += 0.2
        
        # Author quality (5% weight)
        if author and author.strip():
            score += 0.05
        
        # Tags quality (5% weight)
        if tags and len(tags) > 0:
            score += 0.05
            if len(tags) > 3:  # Well-tagged content
                score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _get_offline_feed_data(self) -> List[RawItem]:
        """Get offline test data with comprehensive audit information."""
        test_items = [
            {
                "title": "Tech Company Announces Major AI Breakthrough",
                "description": "A leading technology company has announced a significant breakthrough in artificial intelligence that could revolutionize the industry. The breakthrough involves advanced neural network architectures that can process complex data patterns with unprecedented accuracy.",
                "summary": "Major AI breakthrough announced by tech company with potential industry-wide impact.",
                "link": "https://example.com/ai-breakthrough",
                "guid": "test-ai-001",
                "author": "Tech Reporter",
                "published": "2025-08-31T10:00:00Z",
                "tags": ["AI", "Technology", "Breakthrough", "Neural Networks"],
                "categories": ["Technology", "Innovation"]
            },
            {
                "title": "Economic Indicators Show Mixed Signals",
                "description": "Recent economic data shows conflicting signals about the direction of the economy, with some sectors showing growth while others decline. Manufacturing output increased by 2.3% while consumer spending decreased by 1.1%.",
                "summary": "Conflicting economic data shows mixed signals across different sectors.",
                "link": "https://example.com/economic-indicators",
                "guid": "test-econ-002",
                "author": "Economic Analyst",
                "published": "2025-08-31T09:30:00Z",
                "tags": ["Economy", "GDP", "Manufacturing", "Consumer Spending"],
                "categories": ["Economics", "Business"]
            },
            {
                "title": "Climate Summit Reaches Historic Agreement",
                "description": "World leaders have reached a historic agreement on climate change measures at the latest international summit. The agreement includes commitments to reduce carbon emissions by 50% by 2030 and achieve net-zero emissions by 2050.",
                "summary": "Historic climate agreement reached with ambitious emission reduction targets.",
                "link": "https://example.com/climate-summit",
                "guid": "test-climate-003",
                "author": "Environmental Correspondent",
                "published": "2025-08-31T08:15:00Z",
                "tags": ["Climate", "Environment", "Carbon Emissions", "Net Zero"],
                "categories": ["Environment", "Politics", "International"]
            }
        ]
        
        raw_items = []
        for item in test_items:
            # Create comprehensive content
            full_content = f"{item['title']}\n{item['description']}\n{item['summary']}"
            content_hash = hash_content(full_content)
            
            # Create comprehensive meta information
            meta_json = {
                # Basic identification
                "guid": item["guid"],
                "external_id": item["guid"],
                "source_url": "https://example.com/test-feed",
                "raw_url": item["link"],
                
                # Publication information
                "published": item["published"],
                "author": item["author"],
                "author_detail": {
                    "name": item["author"],
                    "email": "",
                    "href": ""
                },
                
                # Content information
                "title": item["title"],
                "description": item["description"],
                "summary": item["summary"],
                "content": item["description"],
                "content_length": len(full_content),
                "word_count": len(full_content.split()),
                
                # Classification
                "tags": item["tags"],
                "tag_details": [{"term": tag, "label": tag, "scheme": ""} for tag in item["tags"]],
                "categories": item["categories"],
                
                # Test data indicators
                "test_data": True,
                "source": "offline_test",
                "parsed_at": datetime.utcnow().isoformat(),
                "parser_version": "enhanced_rss_adapter_v1",
                "content_hash": content_hash,
                "fetch_method": "offline_test",
                
                # Quality indicators
                "has_title": True,
                "has_description": True,
                "has_author": True,
                "has_tags": True,
                "has_categories": True,
                "has_enclosures": False,
                "content_quality_score": self._calculate_content_quality(
                    item["title"], item["description"], item["summary"], item["author"], item["tags"]
                )
            }
            
            raw_item = RawItem(
                source_id="",  # Will be set by caller
                external_id=item["guid"],
                raw_url=item["link"],
                title=item["title"],
                content_text=full_content,  # Use comprehensive content
                raw_content_hash=content_hash,
                meta_json=meta_json
            )
            raw_items.append(raw_item)
        
        return raw_items
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()