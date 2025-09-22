"""Export modules for various monitoring systems."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from .storage import LocalStorage


class PrometheusExporter:
    """Export metrics in Prometheus format."""
    
    def __init__(self, storage: LocalStorage):
        self.storage = storage
    
    def export_to_file(self, output_path: str) -> None:
        """Export metrics to Prometheus format file."""
        metrics = self.storage.get_repository_metrics()
        
        prometheus_metrics = []
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Repository conversation counts
        for repo, data in metrics.items():
            prometheus_metrics.append(
                f'claude_conversations_total{{repository="{repo}"}} {data.get("conversation_count", 0)} {timestamp}'
            )
            prometheus_metrics.append(
                f'claude_messages_total{{repository="{repo}"}} {data.get("total_messages", 0)} {timestamp}'
            )
            prometheus_metrics.append(
                f'claude_errors_total{{repository="{repo}"}} {data.get("error_count", 0)} {timestamp}'
            )
            prometheus_metrics.append(
                f'claude_tools_used_total{{repository="{repo}"}} {data.get("tool_usage_count", 0)} {timestamp}'
            )
        
        # Pattern detection metrics
        for repo, data in metrics.items():
            pattern_summary = data.get("pattern_summary", {})
            for category, patterns in pattern_summary.items():
                for pattern_name, count in patterns.items():
                    prometheus_metrics.append(
                        f'claude_patterns_detected{{repository="{repo}",category="{category}",pattern="{pattern_name}"}} {count} {timestamp}'
                    )
        
        # Basic stats
        stats = self.storage.get_basic_stats()
        prometheus_metrics.extend([
            f'claude_total_conversations {stats.get("total_conversations", 0)} {timestamp}',
            f'claude_total_repositories {stats.get("repository_count", 0)} {timestamp}',
        ])
        
        # Write to file
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write('\n'.join(prometheus_metrics))
            f.write('\n')
    
    def push_to_grafana_cloud(self, remote_write_url: str, username: str, password: str) -> None:
        """Push metrics to Grafana Cloud via remote write (Bearer token auth)."""
        try:
            import urllib.request
            import urllib.error
            
            # Get metrics in Prometheus format
            prometheus_file = "/tmp/claude-metrics.prom"
            if not Path(prometheus_file).exists():
                self.export_to_file(prometheus_file)
            
            with open(prometheus_file, 'r') as f:
                metrics_content = f.read()
            
            # For now, try with text format since we don't have protobuf encoder
            # Use Bearer token authentication (modern Grafana Cloud format)
            request = urllib.request.Request(
                remote_write_url,
                data=metrics_content.encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {password}',  # Service account token as Bearer
                    'Content-Type': 'text/plain; version=0.0.4; charset=utf-8',
                    'User-Agent': 'claude-metrics/0.1.0'
                }
            )
            
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status not in [200, 202, 204]:
                        raise Exception(f"HTTP {response.status}: {response.read().decode()}")
                        
            except urllib.error.HTTPError as e:
                # Try fallback with Basic auth if Bearer fails
                if e.code == 401:
                    import base64
                    auth_string = f"{username}:{password}"
                    auth_b64 = base64.b64encode(auth_string.encode()).decode()
                    
                    fallback_request = urllib.request.Request(
                        remote_write_url,
                        data=metrics_content.encode('utf-8'),
                        headers={
                            'Authorization': f'Basic {auth_b64}',
                            'Content-Type': 'text/plain; version=0.0.4; charset=utf-8',
                            'User-Agent': 'claude-metrics/0.1.0'
                        }
                    )
                    
                    try:
                        with urllib.request.urlopen(fallback_request, timeout=30) as response:
                            if response.status not in [200, 202, 204]:
                                raise Exception(f"HTTP {response.status}: {response.read().decode()}")
                    except urllib.error.HTTPError as e2:
                        raise Exception(f"Authentication failed with both Bearer and Basic auth. Token may be invalid. HTTP {e2.code}: {e2.read().decode()}")
                else:
                    raise Exception(f"HTTP {e.code}: {e.read().decode()}")
                    
        except Exception as e:
            raise Exception(f"Failed to push to Grafana Cloud: {e}")


class GrafanaJSONExporter:
    """Export metrics in Grafana JSON data source format."""
    
    def __init__(self, storage: LocalStorage):
        self.storage = storage
    
    def export_to_directory(self, output_dir: str) -> None:
        """Export metrics as JSON API for Grafana JSON data source."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Main metrics endpoint
        metrics = self.storage.get_repository_metrics()
        
        # Transform for Grafana JSON format
        grafana_data = {
            "search": self._generate_search_response(),
            "query": self._generate_query_response(metrics),
            "annotations": self._generate_annotations_response(),
        }
        
        # Write main API file
        with open(output_path / "search", 'w') as f:
            json.dump(grafana_data["search"], f)
            
        with open(output_path / "query", 'w') as f:
            json.dump(grafana_data["query"], f)
            
        with open(output_path / "annotations", 'w') as f:
            json.dump(grafana_data["annotations"], f)
        
        # Create simple HTTP server script
        server_script = '''#!/usr/bin/env python3
import http.server
import socketserver
import json
from pathlib import Path

class JSONAPIHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/search':
            self.send_json_file('search')
        elif self.path == '/query':
            self.send_json_file('query')  
        elif self.path == '/annotations':
            self.send_json_file('annotations')
        else:
            self.send_error(404)
    
    def send_json_file(self, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except FileNotFoundError:
            self.send_error(404)

if __name__ == "__main__":
    PORT = 8080
    with socketserver.TCPServer(("", PORT), JSONAPIHandler) as httpd:
        print(f"Serving Grafana JSON API at http://localhost:{PORT}")
        httpd.serve_forever()
'''
        
        with open(output_path / "server.py", 'w') as f:
            f.write(server_script)
        
        os.chmod(output_path / "server.py", 0o755)
    
    def _generate_search_response(self) -> list:
        """Generate search response for available metrics."""
        return [
            {"text": "Conversations", "value": "conversations"},
            {"text": "Errors", "value": "errors"},
            {"text": "Tool Usage", "value": "tools"},
            {"text": "Repositories", "value": "repositories"},
        ]
    
    def _generate_query_response(self, metrics: Dict[str, Any]) -> list:
        """Generate query response with time series data."""
        datapoints = []
        timestamp = int(datetime.now().timestamp() * 1000)
        
        for repo, data in metrics.items():
            datapoints.extend([
                {
                    "target": f"{repo} - Conversations",
                    "datapoints": [[data.get("conversation_count", 0), timestamp]]
                },
                {
                    "target": f"{repo} - Errors", 
                    "datapoints": [[data.get("error_count", 0), timestamp]]
                },
                {
                    "target": f"{repo} - Tools",
                    "datapoints": [[data.get("tool_usage_count", 0), timestamp]]
                }
            ])
        
        return datapoints
    
    def _generate_annotations_response(self) -> list:
        """Generate annotations for significant events."""
        # Get recent scan history for annotations
        return [
            {
                "annotation": {
                    "name": "Claude Metrics Scan",
                    "enabled": True,
                    "datasource": "claude-metrics"
                },
                "title": "Metrics Updated",
                "time": int(datetime.now().timestamp() * 1000),
                "text": "Claude metrics data refreshed",
                "tags": ["claude", "scan"]
            }
        ]


class InfluxDBExporter:
    """Export metrics to InfluxDB format."""
    
    def __init__(self, storage: LocalStorage):
        self.storage = storage
    
    def export_to_file(self, output_path: str) -> None:
        """Export metrics in InfluxDB line protocol format."""
        metrics = self.storage.get_repository_metrics()
        
        influx_lines = []
        timestamp = int(datetime.now().timestamp() * 1000000000)  # nanoseconds
        
        for repo, data in metrics.items():
            # Repository metrics
            influx_lines.append(
                f'claude_conversations,repository={repo} count={data.get("conversation_count", 0)}i {timestamp}'
            )
            influx_lines.append(
                f'claude_messages,repository={repo} count={data.get("total_messages", 0)}i {timestamp}'
            )
            influx_lines.append(
                f'claude_errors,repository={repo} count={data.get("error_count", 0)}i {timestamp}'
            )
            influx_lines.append(
                f'claude_tools,repository={repo} count={data.get("tool_usage_count", 0)}i {timestamp}'
            )
            
            # Pattern metrics
            pattern_summary = data.get("pattern_summary", {})
            for category, patterns in pattern_summary.items():
                for pattern_name, count in patterns.items():
                    influx_lines.append(
                        f'claude_patterns,repository={repo},category={category},pattern={pattern_name} count={count}i {timestamp}'
                    )
        
        # Write to file
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write('\n'.join(influx_lines))
            f.write('\n')