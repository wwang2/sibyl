"""CLI wrapper for the agentic event discovery system."""

import typer
from typing import Optional

from .run_cycle import main as run_cycle_main

app = typer.Typer(help="Agentic Event Discovery CLI")


@app.command()
def run_cycle(
    all: bool = typer.Option(False, "--all", help="Run discovery and assessment cycle"),
    max_feeds: int = typer.Option(None, "--max-feeds", help="Maximum number of RSS feeds to process"),
    max_evidence_per_feed: int = typer.Option(None, "--max-evidence-per-feed", help="Maximum number of evidence items per RSS feed"),
    max_proto_events: int = typer.Option(None, "--max-proto-events", help="Maximum number of proto events to assess"),
    offline: bool = typer.Option(False, "--offline", help="Run in offline mode using test fixtures")
):
    """Run the discovery and assessment cycle."""
    if all:
        run_cycle_main(max_feeds=max_feeds, max_evidence_per_feed=max_evidence_per_feed, max_proto_events=max_proto_events, offline_mode=offline)
    else:
        run_cycle_main(max_feeds=max_feeds, max_evidence_per_feed=max_evidence_per_feed, max_proto_events=max_proto_events, offline_mode=offline)


@app.command()
def init_db():
    """Initialize the database with required tables."""
    from .core.store import Store
    
    store = Store.from_env()
    store.create_all()
    typer.echo(f"Database initialized at {store.engine.url}")


@app.command()
def audit_llm(
    days: int = typer.Option(30, "--days", help="Number of days to analyze"),
    export: bool = typer.Option(False, "--export", help="Export detailed data to JSON"),
    output: str = typer.Option(None, "--output", help="Output file for export")
):
    """Generate LLM usage audit report."""
    from .core.store import Store
    import sys
    from pathlib import Path
    
    # Add temp_scripts to path
    temp_scripts_path = Path(__file__).parent.parent / "temp_scripts"
    sys.path.insert(0, str(temp_scripts_path))
    
    from llm_audit import LLMAuditTool
    
    store = Store.from_env()
    audit_tool = LLMAuditTool(store)
    
    # Generate and print report
    audit_tool.print_summary_report(days)
    
    # Export if requested
    if export:
        output_file = audit_tool.export_interaction_details(days, output)
        typer.echo(f"📁 Detailed data exported to: {output_file}")


if __name__ == "__main__":
    app()
