# Commands Directory

This directory contains utility scripts for the claude-metrics project development workflow.

## Available Scripts

### Core Development
- **`integrate.sh`** - Integration workflow (also available in project root)
- **`run_tests_with_coverage.sh`** - Run tests with coverage analysis
- **`run_lint.sh`** - Code linting and formatting

### Code Analysis
- **`loc.sh`** - Comprehensive GitHub statistics and lines of code analysis
- **`loc_simple.sh`** - Simple lines of code counter
- **`codebase_loc.sh`** - Codebase analysis
- **`coverage.sh`** - Coverage analysis

### Git Workflow
- **`push.sh`** - Enhanced git push workflow
- **`sync_branch.sh`** - Branch synchronization
- **`resolve_conflicts.sh`** - Conflict resolution helper
- **`create_worktree.sh`** - Git worktree management

### Development Tools
- **`claude_start.sh`** - Claude Code startup helper
- **`claude_mcp.sh`** - Claude MCP integration
- **`create_snapshot.sh`** - Create development snapshots
- **`schedule_branch_work.sh`** - Branch work scheduling

### Setup Scripts
- **`setup_email.sh`** - Git email configuration
- **`setup-github-runner.sh`** - GitHub Actions runner setup

## Usage

All scripts are executable and can be run from the project root:

```bash
# Run tests with coverage
./commands/run_tests_with_coverage.sh

# Get code statistics  
./commands/loc.sh

# Integration workflow (also available as ./integrate.sh)
./commands/integrate.sh
```

## Adaptation Notes

These scripts have been adapted from the [claude-commands](https://github.com/jleechanorg/claude-commands) repository for use with the claude-metrics project. Project-specific references have been updated accordingly.