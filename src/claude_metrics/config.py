"""Configuration management for claude-metrics."""

import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel


class Config(BaseModel):
    """Configuration settings for claude-metrics."""
    
    config_dir: Path
    claude_projects_path: Path
    storage_path: Path
    scan_interval: str = "5m"
    
    @classmethod
    def create_default(cls, config_dir: Optional[str] = None) -> "Config":
        """Create default configuration and save to disk."""
        if config_dir is None:
            config_dir = Path.home() / ".claude-metrics"
        else:
            config_dir = Path(config_dir)
            
        config_dir.mkdir(exist_ok=True, parents=True)
        
        # Default Claude Code projects path
        claude_projects_path = Path.home() / ".claude" / "projects"
        storage_path = config_dir / "metrics.db"
        
        config = cls(
            config_dir=config_dir,
            claude_projects_path=claude_projects_path,
            storage_path=storage_path,
        )
        
        # Save configuration
        config_file = config_dir / "config.yaml"
        config_data = {
            "data_sources": {
                "claude_projects_path": str(claude_projects_path),
                "scan_interval": config.scan_interval,
            },
            "storage": {
                "type": "sqlite",
                "path": str(storage_path),
            },
            "patterns": {
                "error_detection": [
                    {
                        "name": "test_failures",
                        "regex": r"\b(test\s+fail|assertion\s+error|test.*failed)\b",
                        "weight": 80,
                    },
                    {
                        "name": "build_errors", 
                        "regex": r"\b(build\s+fail|compilation\s+error|cannot\s+build)\b",
                        "weight": 85,
                    },
                    {
                        "name": "runtime_errors",
                        "regex": r"\b(error|exception|traceback|stack\s+trace)\b",
                        "weight": 75,
                    },
                ],
                "code_quality": [
                    {
                        "name": "quick_fixes",
                        "regex": r"\b(quick\s+fix|hack|workaround|temporary)\b",
                        "weight": 60,
                    },
                    {
                        "name": "todo_items",
                        "regex": r"\b(todo|fixme|hack|temporary)\b",
                        "weight": 40,
                    },
                ],
                "tool_usage": [
                    {
                        "name": "file_operations",
                        "regex": r"\b(read|write|edit|create)\s+(file|directory)\b",
                        "weight": 30,
                    },
                    {
                        "name": "git_operations", 
                        "regex": r"\b(git\s+commit|git\s+push|git\s+merge|git\s+branch)\b",
                        "weight": 50,
                    },
                    {
                        "name": "testing",
                        "regex": r"\b(run\s+test|pytest|npm\s+test|test\s+suite)\b",
                        "weight": 70,
                    },
                ],
            },
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)
            
        return config
    
    @classmethod
    def load(cls, config_dir: Optional[str] = None) -> "Config":
        """Load configuration from disk."""
        if config_dir is None:
            config_dir = Path.home() / ".claude-metrics"
        else:
            config_dir = Path(config_dir)
            
        config_file = config_dir / "config.yaml"
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration not found at {config_file}")
            
        with open(config_file) as f:
            config_data = yaml.safe_load(f)
            
        claude_projects_path = Path(config_data["data_sources"]["claude_projects_path"])
        storage_path = Path(config_data["storage"]["path"])
        
        return cls(
            config_dir=config_dir,
            claude_projects_path=claude_projects_path,
            storage_path=storage_path,
            scan_interval=config_data["data_sources"].get("scan_interval", "5m"),
        )
    
    def get_patterns(self) -> dict:
        """Load patterns from configuration file."""
        config_file = self.config_dir / "config.yaml"
        
        with open(config_file) as f:
            config_data = yaml.safe_load(f)
            
        return config_data.get("patterns", {})