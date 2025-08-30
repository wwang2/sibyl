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


@app.command()
def visualize_llm(
    days: int = typer.Option(30, "--days", help="Number of days to analyze"),
    output_dir: str = typer.Option("temp_scripts", "--output-dir", help="Output directory for charts"),
    dashboard: bool = typer.Option(False, "--dashboard", help="Create usage dashboard"),
    timeline: bool = typer.Option(False, "--timeline", help="Create performance timeline"),
    comparison: bool = typer.Option(False, "--comparison", help="Create model comparison"),
    all_charts: bool = typer.Option(False, "--all", help="Create all visualizations")
):
    """Create LLM performance visualizations."""
    from .core.store import Store
    import sys
    from pathlib import Path
    
    # Add temp_scripts to path
    temp_scripts_path = Path(__file__).parent.parent / "temp_scripts"
    sys.path.insert(0, str(temp_scripts_path))
    
    from llm_visualizer import LLMVisualizer
    
    store = Store.from_env()
    visualizer = LLMVisualizer(store)
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if all_charts or dashboard:
        dashboard_file = output_path / f"llm_dashboard_{timestamp}.png"
        visualizer.create_usage_dashboard(days, str(dashboard_file))
        typer.echo(f"📊 Dashboard saved to: {dashboard_file}")
    
    if all_charts or timeline:
        timeline_file = output_path / f"llm_timeline_{timestamp}.png"
        visualizer.create_performance_timeline(min(days, 7), str(timeline_file))
        typer.echo(f"📈 Timeline saved to: {timeline_file}")
    
    if all_charts or comparison:
        comparison_file = output_path / f"llm_comparison_{timestamp}.png"
        visualizer.create_model_comparison(days, str(comparison_file))
        typer.echo(f"🔍 Model comparison saved to: {comparison_file}")
    
    if not any([dashboard, timeline, comparison, all_charts]):
        typer.echo("No visualization type specified. Use --help for options.")
        typer.echo("Example: python -m app.cli visualize-llm --all --days 30")


if __name__ == "__main__":
    app()
