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
@click.option(
    "--format",
    type=click.Choice(["prometheus", "json", "csv", "grafana-json"]),
    default="prometheus",
    help="Export format",
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help="Output file or directory",
)
@click.option(
    "--interval",
    default="5m",
    help="Update interval for continuous export",
)
@click.option(
    "--daemon",
    is_flag=True,
    help="Run as daemon for continuous export",
)
@click.option(
    "--grafana-cloud-url",
    default=None,
    help="Grafana Cloud remote write URL",
)
@click.option(
    "--grafana-cloud-user",
    default=None,
    help="Grafana Cloud username/instance ID",
)
@click.option(
    "--grafana-cloud-token",
    default=None,
    help="Grafana Cloud API token",
)
def export(format: str, output: Optional[str], interval: str, daemon: bool,
          grafana_cloud_url: Optional[str], grafana_cloud_user: Optional[str], 
          grafana_cloud_token: Optional[str]) -> None:
    """Export metrics for external monitoring systems."""
    try:
        from .exporters import PrometheusExporter, GrafanaJSONExporter
        
        config = Config.load()
        storage = LocalStorage(config.storage_path)
        
        if format == "prometheus":
            exporter = PrometheusExporter(storage)
            output_path = output or "/tmp/claude-metrics.prom"
            exporter.export_to_file(output_path)
            
            # Push to Grafana Cloud if credentials provided
            if grafana_cloud_url and grafana_cloud_user and grafana_cloud_token:
                try:
                    exporter.push_to_grafana_cloud(
                        grafana_cloud_url, grafana_cloud_user, grafana_cloud_token
                    )
                    console.print(f"✅ Pushed metrics to Grafana Cloud")
                except Exception as e:
                    console.print(f"⚠️  Failed to push to Grafana Cloud: {e}")
            
            console.print(f"✅ Exported Prometheus metrics to {output_path}")
            
        elif format == "grafana-json":
            exporter = GrafanaJSONExporter(storage)
            output_dir = output or "/tmp/claude-metrics-api"
            exporter.export_to_directory(output_dir)
            console.print(f"✅ Exported Grafana JSON API to {output_dir}")
            
        elif format == "json":
            metrics = storage.get_repository_metrics()
            output_path = output or "/tmp/claude-metrics.json"
            with open(output_path, 'w') as f:
                import json
                json.dump(metrics, f, indent=2, default=str)
            console.print(f"✅ Exported JSON metrics to {output_path}")
            
        elif format == "csv":
            metrics = storage.get_repository_metrics()
            output_path = output or "/tmp/claude-metrics.csv"
            with open(output_path, 'w') as f:
                f.write("repository,conversations,errors,tool_usage,last_activity\n")
                for repo, data in metrics.items():
                    f.write(f"{repo},{data.get('conversation_count', 0)},{data.get('error_count', 0)},{data.get('tool_usage_count', 0)},{data.get('last_activity', '')}\n")
            console.print(f"✅ Exported CSV metrics to {output_path}")
            
        if daemon:
            console.print(f"🔄 Starting daemon mode with {interval} interval...")
            # Implementation for daemon mode would go here
            
    except FileNotFoundError:
        console.print("❌ Configuration not found. Run 'claude-metrics init' first")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Error during export: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--grafana-cloud-url",
    default=None,
    help="Your Grafana Cloud remote write URL",
)
@click.option(
    "--grafana-cloud-user", 
    default=None,
    help="Your Grafana Cloud username/instance ID",
)
@click.option(
    "--grafana-cloud-token",
    default=None,
    help="Your Grafana Cloud API token",
)
def push(grafana_cloud_url: Optional[str], grafana_cloud_user: Optional[str], 
         grafana_cloud_token: Optional[str]) -> None:
    """Push metrics directly to Grafana Cloud."""
    try:
        if not all([grafana_cloud_url, grafana_cloud_user, grafana_cloud_token]):
            console.print("🔗 Grafana Cloud Setup")
            console.print("You need three pieces of information from grafana.com:")
            console.print("1. Remote Write URL (e.g., https://prometheus-prod-xx.grafana.net/api/prom/push)")
            console.print("2. Username/Instance ID (usually numbers)")
            console.print("3. API Token/Password")
            console.print("")
            console.print("Usage:")
            console.print("claude-metrics push \\")
            console.print("  --grafana-cloud-url 'https://prometheus-prod-36-prod-us-west-0.grafana.net/api/prom/push' \\")
            console.print("  --grafana-cloud-user 'YOUR_USER_ID' \\")
            console.print("  --grafana-cloud-token 'YOUR_API_TOKEN'")
            return
            
        # Scan recent data and push
        config = Config.load()
        storage = LocalStorage(config.storage_path)
        
        console.print("🔍 Scanning recent conversations...")
        scanner = ConversationScanner(config.claude_projects_path)
        detector = PatternDetector()
        
        conversations = scanner.scan_conversations(since="24h")
        if conversations:
            for conversation in conversations:
                patterns = detector.detect_patterns(conversation)
                storage.store_conversation_metrics(conversation, patterns)
        
        console.print("📤 Pushing to Grafana Cloud...")
        from .exporters import PrometheusExporter
        exporter = PrometheusExporter(storage)
        exporter.push_to_grafana_cloud(grafana_cloud_url, grafana_cloud_user, grafana_cloud_token)
        
        console.print("✅ Successfully pushed metrics to Grafana Cloud!")
        console.print("🎯 Check your dashboard at your Grafana Cloud instance")
        
    except Exception as e:
        console.print(f"❌ Error pushing to Grafana Cloud: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--setup-docker",
    is_flag=True,
    help="Set up Grafana using Docker Compose",
)
@click.option(
    "--dashboard-only",
    is_flag=True,
    help="Only generate dashboard configuration",
)
def dashboard(setup_docker: bool, dashboard_only: bool) -> None:
    """Set up Grafana dashboard for metrics visualization."""
    try:
        if dashboard_only:
            import shutil
            from pathlib import Path
            
            # Copy dashboard files to current directory
            # Get the package root directory
            package_root = Path(__file__).parent.parent.parent
            source_dir = package_root / "grafana"
            target_dir = Path.cwd() / "grafana"
            
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_dir, target_dir)
            
            console.print(f"✅ Dashboard files copied to {target_dir}")
            console.print("📊 Import claude-metrics-dashboard.json in Grafana")
            return
            
        if setup_docker:
            console.print("🐳 Setting up Grafana with Docker Compose...")
            console.print("1. Dashboard files are in ./grafana/")
            console.print("2. Run: docker-compose -f grafana/docker-compose.yml up -d")
            console.print("3. Open Grafana at http://localhost:3000 (admin/admin)")
            console.print("4. Import dashboard from grafana/claude-metrics-dashboard.json")
            return
            
        console.print("📊 Grafana Dashboard Setup")
        console.print("Choose your setup method:")
        console.print("1. Docker: claude-metrics dashboard --setup-docker")
        console.print("2. Manual: claude-metrics dashboard --dashboard-only")
        console.print("3. See full guide: grafana/README.md")
        
    except Exception as e:
        console.print(f"❌ Error setting up dashboard: {e}")
        sys.exit(1)


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