"""Pattern detection engine for Claude Code conversations."""

import re
from typing import Dict, List, Set
from .scanner import Conversation, ConversationMessage


class PatternMatch:
    """A detected pattern match."""
    
    def __init__(self, pattern_name: str, pattern_category: str, weight: int, 
                 match_count: int, message_type: str, sample_text: str = ""):
        self.pattern_name = pattern_name
        self.pattern_category = pattern_category
        self.weight = weight
        self.match_count = match_count
        self.message_type = message_type  # "user" or "assistant"
        self.sample_text = sample_text


class ConversationPatterns:
    """Detected patterns for a conversation."""
    
    def __init__(self, session_id: str, repository_name: str, patterns: List[PatternMatch]):
        self.session_id = session_id
        self.repository_name = repository_name
        self.patterns = patterns
        self.total_score = sum(p.weight * p.match_count for p in patterns)


class PatternDetector:
    """Detects patterns in Claude Code conversations."""
    
    def __init__(self):
        self.patterns = self._load_default_patterns()
    
    def _load_default_patterns(self) -> Dict[str, List[Dict]]:
        """Load default pattern definitions."""
        return {
            "error_detection": [
                {
                    "name": "test_failures",
                    "regex": r"\b(test\s+fail|assertion\s+error|test.*failed|tests?\s+are\s+failing)\b",
                    "weight": 80,
                },
                {
                    "name": "build_errors", 
                    "regex": r"\b(build\s+fail|compilation\s+error|cannot\s+build|build\s+error)\b",
                    "weight": 85,
                },
                {
                    "name": "runtime_errors",
                    "regex": r"\b(error|exception|traceback|stack\s+trace|uncaught\s+exception)\b",
                    "weight": 75,
                },
                {
                    "name": "syntax_errors",
                    "regex": r"\b(syntax\s+error|parse\s+error|invalid\s+syntax|unexpected\s+token)\b",
                    "weight": 70,
                },
                {
                    "name": "type_errors",
                    "regex": r"\b(type\s+error|typescript\s+error|mypy\s+error|type\s+mismatch)\b",
                    "weight": 65,
                },
            ],
            "code_quality": [
                {
                    "name": "quick_fixes",
                    "regex": r"\b(quick\s+fix|hack|workaround|temporary\s+fix)\b",
                    "weight": 60,
                },
                {
                    "name": "todo_items",
                    "regex": r"\b(todo|fixme|hack|temporary)\b",
                    "weight": 40,
                },
                {
                    "name": "refactoring",
                    "regex": r"\b(refactor|clean\s+up|optimize|improve\s+code)\b",
                    "weight": 50,
                },
                {
                    "name": "code_review",
                    "regex": r"\b(code\s+review|peer\s+review|review\s+changes)\b",
                    "weight": 45,
                },
            ],
            "tool_usage": [
                {
                    "name": "file_operations",
                    "regex": r"\b(read|write|edit|create|delete)\s+(file|directory)\b",
                    "weight": 30,
                },
                {
                    "name": "git_operations", 
                    "regex": r"\b(git\s+commit|git\s+push|git\s+merge|git\s+branch|git\s+checkout)\b",
                    "weight": 50,
                },
                {
                    "name": "testing",
                    "regex": r"\b(run\s+test|pytest|npm\s+test|test\s+suite|unit\s+test)\b",
                    "weight": 70,
                },
                {
                    "name": "debugging",
                    "regex": r"\b(debug|debugger|breakpoint|console\.log|print\s+debug)\b",
                    "weight": 55,
                },
                {
                    "name": "package_management",
                    "regex": r"\b(npm\s+install|pip\s+install|yarn\s+add|composer\s+install)\b",
                    "weight": 40,
                },
                {
                    "name": "database_operations",
                    "regex": r"\b(database|sql|query|migration|schema)\b",
                    "weight": 45,
                },
            ],
            "development_workflow": [
                {
                    "name": "feature_development",
                    "regex": r"\b(new\s+feature|implement|add\s+functionality)\b",
                    "weight": 60,
                },
                {
                    "name": "bug_fixes",
                    "regex": r"\b(bug\s+fix|fix\s+issue|resolve\s+problem|patch)\b",
                    "weight": 75,
                },
                {
                    "name": "documentation",
                    "regex": r"\b(documentation|readme|docs|comment|docstring)\b",
                    "weight": 35,
                },
                {
                    "name": "performance_optimization",
                    "regex": r"\b(performance|optimize|speed\s+up|efficient)\b",
                    "weight": 55,
                },
                {
                    "name": "security",
                    "regex": r"\b(security|vulnerability|auth|authorization|encryption)\b",
                    "weight": 80,
                },
            ],
        }
    
    def detect_patterns(self, conversation: Conversation) -> ConversationPatterns:
        """Detect patterns in a conversation."""
        detected_patterns = []
        
        # Combine all message content for analysis
        user_content = []
        assistant_content = []
        
        for message in conversation.messages:
            if message.message_type == "user":
                user_content.append(message.content.lower())
            elif message.message_type == "assistant":
                assistant_content.append(message.content.lower())
        
        user_text = " ".join(user_content)
        assistant_text = " ".join(assistant_content)
        
        # Detect patterns in each category
        for category, patterns in self.patterns.items():
            for pattern_def in patterns:
                pattern_name = pattern_def["name"]
                regex = pattern_def["regex"]
                weight = pattern_def["weight"]
                
                # Check user messages
                user_matches = self._count_matches(regex, user_text)
                if user_matches > 0:
                    sample = self._extract_sample(regex, user_text)
                    detected_patterns.append(PatternMatch(
                        pattern_name=pattern_name,
                        pattern_category=category,
                        weight=weight,
                        match_count=user_matches,
                        message_type="user",
                        sample_text=sample,
                    ))
                
                # Check assistant messages
                assistant_matches = self._count_matches(regex, assistant_text)
                if assistant_matches > 0:
                    sample = self._extract_sample(regex, assistant_text)
                    detected_patterns.append(PatternMatch(
                        pattern_name=pattern_name,
                        pattern_category=category,
                        weight=weight,
                        match_count=assistant_matches,
                        message_type="assistant",
                        sample_text=sample,
                    ))
        
        return ConversationPatterns(
            session_id=conversation.session_id,
            repository_name=conversation.repository_name,
            patterns=detected_patterns,
        )
    
    def _count_matches(self, regex: str, text: str) -> int:
        """Count matches of a regex pattern in text."""
        try:
            pattern = re.compile(regex, re.IGNORECASE)
            return len(pattern.findall(text))
        except re.error:
            return 0
    
    def _extract_sample(self, regex: str, text: str, max_length: int = 100) -> str:
        """Extract a sample match for the pattern."""
        try:
            pattern = re.compile(regex, re.IGNORECASE)
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                sample = text[start:end].strip()
                if len(sample) > max_length:
                    sample = sample[:max_length] + "..."
                return sample
            return ""
        except re.error:
            return ""
    
    def get_repository_summary(self, conversations: List[Conversation]) -> Dict[str, Dict]:
        """Generate summary statistics for repositories."""
        repo_stats = {}
        
        for conversation in conversations:
            repo_name = conversation.repository_name
            if repo_name not in repo_stats:
                repo_stats[repo_name] = {
                    "conversation_count": 0,
                    "total_messages": 0,
                    "pattern_counts": {},
                    "last_activity": None,
                }
            
            stats = repo_stats[repo_name]
            stats["conversation_count"] += 1
            stats["total_messages"] += conversation.message_count
            
            # Update last activity
            if not stats["last_activity"] or conversation.end_time > stats["last_activity"]:
                stats["last_activity"] = conversation.end_time
            
            # Count patterns
            patterns = self.detect_patterns(conversation)
            for pattern in patterns.patterns:
                category = pattern.pattern_category
                if category not in stats["pattern_counts"]:
                    stats["pattern_counts"][category] = {}
                
                pattern_name = pattern.pattern_name
                if pattern_name not in stats["pattern_counts"][category]:
                    stats["pattern_counts"][category][pattern_name] = 0
                
                stats["pattern_counts"][category][pattern_name] += pattern.match_count
        
        return repo_stats
    
    def load_custom_patterns(self, patterns_config: Dict) -> None:
        """Load custom patterns from configuration."""
        if patterns_config:
            self.patterns.update(patterns_config)