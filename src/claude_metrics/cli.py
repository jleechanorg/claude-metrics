"""Command-line interface for claude-metrics."""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .config import Config
from .scanner import ConversationScanner
from .storage import LocalStorage
from .patterns import PatternDetector

console = Console()


@click.group()
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Claude Metrics - Monitor and analyze Claude Code conversations."""
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    "--config-dir",
    type=click.Path(),
    default=None,
    help="Directory for configuration files",
)
def init(config_dir: Optional[str]) -> None:
    """Initialize claude-metrics configuration."""
    try:
        config = Config.create_default(config_dir)
        console.print(f"✅ Initialized configuration at: {config.config_dir}")
        console.print(f"📁 Claude projects path: {config.claude_projects_path}")
        console.print("🚀 Run 'claude-metrics scan' to start analyzing conversations")
    except Exception as e:
        console.print(f"❌ Error initializing: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--repository",
    type=click.Path(exists=True),
    default=None,
    help="Specific repository to scan",
)
@click.option(
    "--since",
    default="7d",
    help="Scan conversations since (e.g., 7d, 1w, 30d)",
)
@click.option(
    "--local-only",
    is_flag=True,
    help="Use local storage only",
)
def scan(repository: Optional[str], since: str, local_only: bool) -> None:
    """Scan Claude Code conversations and extract metrics."""
    try:
        config = Config.load()
        storage = LocalStorage(config.storage_path)
        scanner = ConversationScanner(config.claude_projects_path)
        detector = PatternDetector()
        
        # Load custom patterns from config
        patterns_config = config.get_patterns()
        detector.load_custom_patterns(patterns_config)
        
        console.print("🔍 Scanning Claude Code conversations...")
        
        conversations = scanner.scan_conversations(
            repository_filter=repository,
            since=since
        )
        
        if not conversations:
            console.print("📭 No conversations found")
            return
            
        console.print(f"📄 Found {len(conversations)} conversations")
        
        from datetime import datetime
        scan_start = datetime.now()
        
        processed = 0
        repositories = set()
        
        for conversation in conversations:
            try:
                patterns = detector.detect_patterns(conversation)
                storage.store_conversation_metrics(conversation, patterns)
                processed += 1
                repositories.add(conversation.repository_name)
                
                if processed % 10 == 0:
                    console.print(f"⏳ Processed {processed}/{len(conversations)} conversations")
                    
            except Exception as e:
                console.print(f"⚠️  Error processing conversation {conversation.session_id}: {e}")
                continue
        
        scan_end = datetime.now()
        storage.record_scan(scan_start, scan_end, processed, len(repositories))
        
        console.print(f"✅ Successfully processed {processed} conversations")
        console.print(f"📁 Found {len(repositories)} repositories")
        console.print("📊 Run 'claude-metrics report' to view insights")
        
    except FileNotFoundError:
        console.print("❌ Configuration not found. Run 'claude-metrics init' first")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Error during scan: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.option(
    "--repository",
    default=None,
    help="Filter by repository",
)
def report(format: str, repository: Optional[str]) -> None:
    """Generate metrics report."""
    try:
        config = Config.load()
        storage = LocalStorage(config.storage_path)
        
        metrics = storage.get_repository_metrics(repository_filter=repository)
        
        if format == "table":
            _display_table_report(metrics)
        elif format == "json":
            import json
            click.echo(json.dumps(metrics, indent=2, default=str))
        elif format == "csv":
            _display_csv_report(metrics)
            
    except FileNotFoundError:
        console.print("❌ No data found. Run 'claude-metrics scan' first")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Error generating report: {e}")
        sys.exit(1)


def _display_table_report(metrics: dict) -> None:
    """Display metrics in a table format."""
    table = Table(title="Claude Code Metrics Summary")
    
    table.add_column("Repository", style="cyan")
    table.add_column("Conversations", justify="right")
    table.add_column("Errors", justify="right", style="red")
    table.add_column("Tool Usage", justify="right", style="green")
    table.add_column("Last Activity", style="dim")
    
    for repo, data in metrics.items():
        table.add_row(
            repo,
            str(data.get("conversation_count", 0)),
            str(data.get("error_count", 0)),
            str(data.get("tool_usage_count", 0)),
            str(data.get("last_activity", "N/A"))
        )
    
    console.print(table)


def _display_csv_report(metrics: dict) -> None:
    """Display metrics in CSV format."""
    click.echo("repository,conversations,errors,tool_usage,last_activity")
    for repo, data in metrics.items():
        click.echo(f"{repo},{data.get('conversation_count', 0)},{data.get('error_count', 0)},{data.get('tool_usage_count', 0)},{data.get('last_activity', '')}")


@cli.command()
def status() -> None:
    """Show claude-metrics status."""
    try:
        config = Config.load()
        storage = LocalStorage(config.storage_path)
        
        console.print("📊 Claude Metrics Status")
        console.print(f"Config: {config.config_dir}")
        console.print(f"Storage: {config.storage_path}")
        console.print(f"Claude Projects: {config.claude_projects_path}")
        
        # Basic stats
        stats = storage.get_basic_stats()
        console.print(f"Total Conversations: {stats.get('total_conversations', 0)}")
        console.print(f"Repositories: {stats.get('repository_count', 0)}")
        console.print(f"Last Scan: {stats.get('last_scan', 'Never')}")
        
    except FileNotFoundError:
        console.print("❌ Configuration not found. Run 'claude-metrics init' first")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Error checking status: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()