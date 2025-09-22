"""Storage backend for claude-metrics."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .scanner import Conversation
from .patterns import ConversationPatterns, PatternMatch


class LocalStorage:
    """SQLite-based local storage for metrics."""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    session_id TEXT PRIMARY KEY,
                    repository_path TEXT,
                    repository_name TEXT,
                    git_branch TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration_minutes REAL,
                    message_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    pattern_name TEXT,
                    pattern_category TEXT,
                    weight INTEGER,
                    match_count INTEGER,
                    message_type TEXT,
                    sample_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES conversations (session_id)
                );
                
                CREATE TABLE IF NOT EXISTS repository_metrics (
                    repository_name TEXT PRIMARY KEY,
                    conversation_count INTEGER,
                    total_messages INTEGER,
                    error_count INTEGER,
                    tool_usage_count INTEGER,
                    last_activity TIMESTAMP,
                    pattern_summary TEXT,  -- JSON blob
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_start TIMESTAMP,
                    scan_end TIMESTAMP,
                    conversations_processed INTEGER,
                    repositories_found INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_conversations_repo ON conversations(repository_name);
                CREATE INDEX IF NOT EXISTS idx_patterns_session ON patterns(session_id);
                CREATE INDEX IF NOT EXISTS idx_patterns_category ON patterns(pattern_category);
                CREATE INDEX IF NOT EXISTS idx_conversations_time ON conversations(start_time);
            """)
    
    def store_conversation_metrics(
        self, 
        conversation: Conversation, 
        patterns: ConversationPatterns
    ) -> None:
        """Store conversation and its detected patterns."""
        with sqlite3.connect(self.db_path) as conn:
            # Store conversation
            conn.execute("""
                INSERT OR REPLACE INTO conversations (
                    session_id, repository_path, repository_name, git_branch,
                    start_time, end_time, duration_minutes, message_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conversation.session_id,
                conversation.repository_path,
                conversation.repository_name,
                conversation.git_branch,
                conversation.start_time,
                conversation.end_time,
                conversation.duration_minutes,
                conversation.message_count,
            ))
            
            # Clear existing patterns for this conversation
            conn.execute("DELETE FROM patterns WHERE session_id = ?", (conversation.session_id,))
            
            # Store patterns
            for pattern in patterns.patterns:
                conn.execute("""
                    INSERT INTO patterns (
                        session_id, pattern_name, pattern_category, weight,
                        match_count, message_type, sample_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    conversation.session_id,
                    pattern.pattern_name,
                    pattern.pattern_category,
                    pattern.weight,
                    pattern.match_count,
                    pattern.message_type,
                    pattern.sample_text,
                ))
            
            # Update repository metrics
            self._update_repository_metrics(conn, conversation.repository_name)
    
    def _update_repository_metrics(self, conn: sqlite3.Connection, repository_name: str) -> None:
        """Update aggregated repository metrics."""
        # Calculate metrics for this repository
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as conversation_count,
                SUM(message_count) as total_messages,
                MAX(end_time) as last_activity
            FROM conversations 
            WHERE repository_name = ?
        """, (repository_name,))
        
        result = cursor.fetchone()
        conversation_count, total_messages, last_activity = result
        
        # Count error and tool usage patterns
        cursor = conn.execute("""
            SELECT pattern_category, SUM(match_count) as total_matches
            FROM patterns p
            JOIN conversations c ON p.session_id = c.session_id
            WHERE c.repository_name = ?
            GROUP BY pattern_category
        """, (repository_name,))
        
        pattern_counts = dict(cursor.fetchall())
        error_count = pattern_counts.get("error_detection", 0)
        tool_usage_count = pattern_counts.get("tool_usage", 0)
        
        # Get detailed pattern summary
        cursor = conn.execute("""
            SELECT pattern_name, pattern_category, SUM(match_count) as total_matches
            FROM patterns p
            JOIN conversations c ON p.session_id = c.session_id
            WHERE c.repository_name = ?
            GROUP BY pattern_name, pattern_category
            ORDER BY total_matches DESC
        """, (repository_name,))
        
        pattern_details = {}
        for pattern_name, category, matches in cursor.fetchall():
            if category not in pattern_details:
                pattern_details[category] = {}
            pattern_details[category][pattern_name] = matches
        
        # Store aggregated metrics
        conn.execute("""
            INSERT OR REPLACE INTO repository_metrics (
                repository_name, conversation_count, total_messages,
                error_count, tool_usage_count, last_activity, pattern_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            repository_name,
            conversation_count,
            total_messages or 0,
            error_count,
            tool_usage_count,
            last_activity,
            json.dumps(pattern_details),
        ))
    
    def get_repository_metrics(self, repository_filter: Optional[str] = None) -> Dict[str, Dict]:
        """Get aggregated metrics for repositories."""
        with sqlite3.connect(self.db_path) as conn:
            if repository_filter:
                cursor = conn.execute("""
                    SELECT repository_name, conversation_count, total_messages,
                           error_count, tool_usage_count, last_activity, pattern_summary
                    FROM repository_metrics 
                    WHERE repository_name LIKE ?
                    ORDER BY conversation_count DESC
                """, (f"%{repository_filter}%",))
            else:
                cursor = conn.execute("""
                    SELECT repository_name, conversation_count, total_messages,
                           error_count, tool_usage_count, last_activity, pattern_summary
                    FROM repository_metrics 
                    ORDER BY conversation_count DESC
                """)
            
            results = {}
            for row in cursor.fetchall():
                repo_name, conv_count, total_msgs, errors, tools, last_activity, pattern_json = row
                
                pattern_summary = {}
                if pattern_json:
                    try:
                        pattern_summary = json.loads(pattern_json)
                    except json.JSONDecodeError:
                        pass
                
                results[repo_name] = {
                    "conversation_count": conv_count,
                    "total_messages": total_msgs,
                    "error_count": errors,
                    "tool_usage_count": tools,
                    "last_activity": last_activity,
                    "pattern_summary": pattern_summary,
                }
            
            return results
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """Get basic statistics about stored data."""
        with sqlite3.connect(self.db_path) as conn:
            # Total conversations
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            total_conversations = cursor.fetchone()[0]
            
            # Repository count
            cursor = conn.execute("SELECT COUNT(DISTINCT repository_name) FROM conversations")
            repository_count = cursor.fetchone()[0]
            
            # Last scan
            cursor = conn.execute("SELECT MAX(scan_end) FROM scan_history")
            last_scan = cursor.fetchone()[0]
            
            # Most active repository
            cursor = conn.execute("""
                SELECT repository_name, conversation_count 
                FROM repository_metrics 
                ORDER BY conversation_count DESC 
                LIMIT 1
            """)
            most_active = cursor.fetchone()
            
            return {
                "total_conversations": total_conversations,
                "repository_count": repository_count,
                "last_scan": last_scan or "Never",
                "most_active_repository": most_active[0] if most_active else "None",
                "most_active_count": most_active[1] if most_active else 0,
            }
    
    def record_scan(self, start_time: datetime, end_time: datetime, 
                   conversations_processed: int, repositories_found: int) -> None:
        """Record a scan operation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO scan_history (
                    scan_start, scan_end, conversations_processed, repositories_found
                ) VALUES (?, ?, ?, ?)
            """, (start_time, end_time, conversations_processed, repositories_found))
    
    def get_conversation_history(self, repository_name: Optional[str] = None, 
                               limit: int = 50) -> List[Dict]:
        """Get conversation history."""
        with sqlite3.connect(self.db_path) as conn:
            if repository_name:
                cursor = conn.execute("""
                    SELECT session_id, repository_name, git_branch, start_time, 
                           end_time, duration_minutes, message_count
                    FROM conversations 
                    WHERE repository_name = ?
                    ORDER BY start_time DESC 
                    LIMIT ?
                """, (repository_name, limit))
            else:
                cursor = conn.execute("""
                    SELECT session_id, repository_name, git_branch, start_time, 
                           end_time, duration_minutes, message_count
                    FROM conversations 
                    ORDER BY start_time DESC 
                    LIMIT ?
                """, (limit,))
            
            conversations = []
            for row in cursor.fetchall():
                conversations.append({
                    "session_id": row[0],
                    "repository_name": row[1],
                    "git_branch": row[2],
                    "start_time": row[3],
                    "end_time": row[4],
                    "duration_minutes": row[5],
                    "message_count": row[6],
                })
            
            return conversations
    
    def get_pattern_trends(self, repository_name: Optional[str] = None, 
                          days: int = 30) -> Dict[str, List]:
        """Get pattern trends over time."""
        with sqlite3.connect(self.db_path) as conn:
            if repository_name:
                cursor = conn.execute("""
                    SELECT DATE(c.start_time) as date, p.pattern_category, 
                           SUM(p.match_count) as total_matches
                    FROM patterns p
                    JOIN conversations c ON p.session_id = c.session_id
                    WHERE c.repository_name = ? 
                    AND DATE(c.start_time) >= DATE('now', '-{} days')
                    GROUP BY DATE(c.start_time), p.pattern_category
                    ORDER BY date
                """.format(days), (repository_name,))
            else:
                cursor = conn.execute("""
                    SELECT DATE(c.start_time) as date, p.pattern_category, 
                           SUM(p.match_count) as total_matches
                    FROM patterns p
                    JOIN conversations c ON p.session_id = c.session_id
                    WHERE DATE(c.start_time) >= DATE('now', '-{} days')
                    GROUP BY DATE(c.start_time), p.pattern_category
                    ORDER BY date
                """.format(days))
            
            trends = {}
            for date, category, matches in cursor.fetchall():
                if category not in trends:
                    trends[category] = []
                trends[category].append({"date": date, "matches": matches})
            
            return trends