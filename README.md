# Claude Metrics

Centralized monitoring and analysis of Claude Code conversations across multiple repositories.

## Quick Start

```bash
# Install package
pip install -e .

# Initialize configuration
claude-metrics init

# Scan existing conversations
claude-metrics scan

# View metrics report
claude-metrics report

# Check status
claude-metrics status
```

## Features

- **Conversation Scanning**: Automatically discovers and parses Claude Code conversation files from `~/.claude/projects/`
- **Pattern Detection**: Configurable regex-based detection for errors, tool usage, code quality issues, and development workflows
- **Local Storage**: SQLite database for privacy-first metrics storage
- **Reporting**: Rich CLI reports with table, JSON, and CSV output formats
- **Repository Insights**: Cross-repository analytics and trending

## Commands

### `claude-metrics init`
Initialize configuration files and database.

### `claude-metrics scan [OPTIONS]`
Scan Claude Code conversations and extract metrics.

Options:
- `--repository PATH`: Scan specific repository only
- `--since DURATION`: Scan conversations since (e.g., 7d, 1w, 30d)
- `--local-only`: Use local storage only

### `claude-metrics report [OPTIONS]`
Generate metrics report.

Options:
- `--format [table|json|csv]`: Output format (default: table)
- `--repository REPO`: Filter by repository

### `claude-metrics status`
Show current status and basic statistics.

## Configuration

Configuration is stored in `~/.claude-metrics/config.yaml` and includes:
- Data source paths
- Pattern definitions for detection
- Storage settings

## Pattern Categories

The tool detects patterns in the following categories:
- **Error Detection**: Test failures, build errors, runtime errors, syntax errors, type errors
- **Code Quality**: Quick fixes, TODO items, refactoring, code reviews
- **Tool Usage**: File operations, Git operations, testing, debugging, package management
- **Development Workflow**: Feature development, bug fixes, documentation, performance optimization, security

## Privacy

- All processing happens locally
- No conversation content is stored, only pattern matches and metadata
- Configurable pattern redaction for sensitive information