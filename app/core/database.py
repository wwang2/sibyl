"""
Database configuration and path management.
Centralizes database path logic to prevent path issues.
"""

import os
from pathlib import Path
from typing import Optional

# Project root directory (where this file is located)
# Go up from app/core/database.py to the project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
DEFAULT_DB_PATH = PROJECT_ROOT / "local.db"

def get_database_url(db_path: Optional[str] = None) -> str:
    """
    Get the database URL, ensuring it's always an absolute path.
    
    Args:
        db_path: Optional database path. If None, uses default.
        
    Returns:
        SQLite database URL with absolute path
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    elif not os.path.isabs(db_path):
        # Convert relative path to absolute
        db_path = str(PROJECT_ROOT / db_path)
    
    return f"sqlite:///{db_path}"

def validate_database_path(db_path: str) -> bool:
    """
    Validate that a database path is accessible and in the correct location.
    
    Args:
        db_path: Database path to validate
        
    Returns:
        True if path is valid, False otherwise
    """
    try:
        # Convert to absolute path
        abs_path = Path(db_path).resolve()
        
        # Check if it's in the project directory or a reasonable location
        # Allow paths that are in the project directory or its parent
        project_parent = PROJECT_ROOT.parent
        if not (abs_path.is_relative_to(PROJECT_ROOT) or abs_path.is_relative_to(project_parent)):
            print(f"⚠️ Warning: Database path {abs_path} is outside project directory")
            return False
            
        # Check if parent directory exists
        if not abs_path.parent.exists():
            print(f"⚠️ Warning: Database directory {abs_path.parent} does not exist")
            return False
            
        return True
    except Exception as e:
        print(f"⚠️ Warning: Invalid database path {db_path}: {e}")
        return False

def get_database_info() -> dict:
    """
    Get information about the current database configuration.
    
    Returns:
        Dictionary with database information
    """
    return {
        "project_root": str(PROJECT_ROOT),
        "default_db_path": str(DEFAULT_DB_PATH),
        "default_db_url": get_database_url(),
        "db_exists": DEFAULT_DB_PATH.exists(),
        "db_size": DEFAULT_DB_PATH.stat().st_size if DEFAULT_DB_PATH.exists() else 0
    }

def print_database_info():
    """Print current database configuration information."""
    info = get_database_info()
    print("🗄️ Database Configuration:")
    print(f"  Project Root: {info['project_root']}")
    print(f"  Default DB Path: {info['default_db_path']}")
    print(f"  Default DB URL: {info['default_db_url']}")
    print(f"  DB Exists: {info['db_exists']}")
    if info['db_size'] > 0:
        print(f"  DB Size: {info['db_size']:,} bytes")
    print()
