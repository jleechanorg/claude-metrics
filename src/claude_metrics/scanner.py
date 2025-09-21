"""Scanner for Claude Code conversation files."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Iterator
from pydantic import BaseModel


class ConversationMessage(BaseModel):
    """A single message in a Claude Code conversation."""
    
    session_id: str
    timestamp: datetime
    message_type: str  # "user" or "assistant"
    content: str
    cwd: Optional[str] = None
    git_branch: Optional[str] = None
    
    @classmethod
    def from_jsonl_line(cls, line: str) -> Optional["ConversationMessage"]:
        """Parse a JSONL line into a ConversationMessage."""
        try:
            data = json.loads(line.strip())
            
            # Extract basic fields
            session_id = data.get("sessionId", "")
            timestamp_str = data.get("timestamp", "")
            message_type = data.get("type", "")
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now()
            
            # Extract message content
            message_data = data.get("message", {})
            content = message_data.get("content", "")
            
            # Extract metadata
            cwd = data.get("cwd")
            git_branch = data.get("gitBranch")
            
            return cls(
                session_id=session_id,
                timestamp=timestamp,
                message_type=message_type,
                content=content,
                cwd=cwd,
                git_branch=git_branch,
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Skip malformed lines
            return None


class Conversation(BaseModel):
    """A complete conversation with metadata."""
    
    session_id: str
    repository_path: Optional[str]
    git_branch: Optional[str]
    start_time: datetime
    end_time: datetime
    message_count: int
    messages: List[ConversationMessage]
    
    @property
    def duration_minutes(self) -> float:
        """Calculate conversation duration in minutes."""
        return (self.end_time - self.start_time).total_seconds() / 60
    
    @property 
    def repository_name(self) -> str:
        """Extract repository name from path."""
        if not self.repository_path:
            return "unknown"
        return Path(self.repository_path).name


class ConversationScanner:
    """Scanner for Claude Code conversation files."""
    
    def __init__(self, claude_projects_path: Path):
        self.claude_projects_path = Path(claude_projects_path)
        
    def scan_conversations(
        self,
        repository_filter: Optional[str] = None,
        since: str = "7d",
    ) -> List[Conversation]:
        """Scan and parse Claude Code conversations."""
        if not self.claude_projects_path.exists():
            return []
            
        # Parse since parameter
        cutoff_time = self._parse_since(since)
        
        conversations = []
        
        # Iterate through project directories
        for project_dir in self.claude_projects_path.iterdir():
            if not project_dir.is_dir():
                continue
                
            # Each project directory contains .jsonl files
            for jsonl_file in project_dir.glob("*.jsonl"):
                try:
                    conversation = self._parse_conversation_file(jsonl_file)
                    if conversation:
                        # Apply filters
                        if cutoff_time and conversation.start_time < cutoff_time:
                            continue
                            
                        if repository_filter and repository_filter not in str(conversation.repository_path or ""):
                            continue
                            
                        conversations.append(conversation)
                        
                except Exception as e:
                    # Skip files that can't be parsed
                    continue
                    
        return sorted(conversations, key=lambda c: c.start_time, reverse=True)
    
    def _parse_conversation_file(self, file_path: Path) -> Optional[Conversation]:
        """Parse a single conversation file."""
        messages = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        message = ConversationMessage.from_jsonl_line(line)
                        if message:
                            messages.append(message)
                            
        except (IOError, UnicodeDecodeError):
            return None
            
        if not messages:
            return None
            
        # Extract conversation metadata
        session_id = messages[0].session_id
        repository_path = None
        git_branch = None
        
        # Find repository path and branch from messages
        for message in messages:
            if message.cwd and not repository_path:
                repository_path = message.cwd
            if message.git_branch and not git_branch:
                git_branch = message.git_branch
                
        start_time = min(msg.timestamp for msg in messages)
        end_time = max(msg.timestamp for msg in messages)
        
        return Conversation(
            session_id=session_id,
            repository_path=repository_path,
            git_branch=git_branch,
            start_time=start_time,
            end_time=end_time,
            message_count=len(messages),
            messages=messages,
        )
    
    def _parse_since(self, since: str) -> Optional[datetime]:
        """Parse 'since' parameter into datetime."""
        if not since:
            return None
            
        # Extract number and unit
        match = re.match(r"(\d+)([dwm])", since.lower())
        if not match:
            return None
            
        amount = int(match.group(1))
        unit = match.group(2)
        
        now = datetime.now()
        
        if unit == "d":
            return now - timedelta(days=amount)
        elif unit == "w":
            return now - timedelta(weeks=amount)
        elif unit == "m":
            return now - timedelta(days=amount * 30)  # Approximate
            
        return None
    
    def get_repository_list(self) -> List[str]:
        """Get list of unique repositories from conversations."""
        repositories = set()
        
        conversations = self.scan_conversations()
        for conversation in conversations:
            if conversation.repository_path:
                repositories.add(conversation.repository_path)
                
        return sorted(list(repositories))