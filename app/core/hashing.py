"""Content hashing utilities for deduplication."""

import hashlib
from typing import Any, Dict


def hash_content(content: str) -> str:
    """Generate a SHA-256 hash of content for deduplication."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def hash_evidence(title: str, snippet: str, url: str) -> str:
    """Generate a hash for evidence based on title, snippet, and URL."""
    content = f"{title}|{snippet}|{url}"
    return hash_content(content)


def generate_proto_event_key(title: str, source_type: str, meta: Dict[str, Any]) -> str:
    """Generate a canonical key for grouping evidence into proto events."""
    # Use the actual title as the key for better readability
    # Clean up the title for use as a key
    clean_title = title.lower().strip()
    # Remove special characters and normalize spaces
    import re
    clean_title = re.sub(r'[^\w\s]', '', clean_title)
    clean_title = re.sub(r'\s+', '_', clean_title)
    return f"{source_type}_{clean_title}"
