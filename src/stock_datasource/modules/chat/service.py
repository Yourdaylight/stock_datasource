"""Chat service implementation with database persistence."""

import uuid
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)


class ChatService:
    """Chat service for handling conversations with database persistence."""
    
    def __init__(self):
        self.client = db_client
        self._tables_initialized = False
        # In-memory cache for hot sessions
        self._session_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    def _ensure_tables(self) -> None:
        """Ensure chat tables exist (lazy initialization)."""
        if self._tables_initialized:
            return
        
        schema_file = Path(__file__).parent / "schema.sql"
        if schema_file.exists():
            sql_content = schema_file.read_text()
            for statement in sql_content.split(";"):
                statement = statement.strip()
                if statement:
                    try:
                        self.client.primary.execute(statement)
                    except Exception as e:
                        logger.warning(f"Failed to execute chat schema statement: {e}")
                    if self.client.backup:
                        try:
                            self.client.backup.execute(statement)
                        except Exception as e:
                            logger.warning(f"Failed to execute chat schema on backup: {e}")
        
        self._tables_initialized = True
    
    def create_session(self, user_id: str, title: Optional[str] = None) -> str:
        """Create a new chat session for a user.
        
        Args:
            user_id: User ID
            title: Optional session title
            
        Returns:
            Session ID
        """
        self._ensure_tables()
        
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        now = datetime.now()
        
        insert_query = """
            INSERT INTO chat_sessions (session_id, user_id, title, created_at, updated_at, last_message_at, message_count)
            VALUES (%(session_id)s, %(user_id)s, %(title)s, %(created_at)s, %(updated_at)s, %(last_message_at)s, 0)
        """
        
        params = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title or "",
            "created_at": now,
            "updated_at": now,
            "last_message_at": now,
        }
        
        try:
            self.client.execute(insert_query, params)
            self._session_cache[session_id] = []
            logger.info(f"Created chat session {session_id} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            # Fallback to memory-only mode
            self._session_cache[session_id] = []
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session info by ID."""
        self._ensure_tables()
        
        query = """
            SELECT session_id, user_id, title, created_at, updated_at, last_message_at, message_count
            FROM chat_sessions FINAL
            WHERE session_id = %(session_id)s
            LIMIT 1
        """
        
        try:
            result = self.client.execute(query, {"session_id": session_id})
            if result:
                row = result[0]
                return {
                    "session_id": row[0],
                    "user_id": row[1],
                    "title": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                    "last_message_at": row[5],
                    "message_count": row[6],
                }
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
        
        return None
    
    def verify_session_ownership(self, session_id: str, user_id: str) -> bool:
        """Verify that a session belongs to the specified user."""
        session = self.get_session(session_id)
        if not session:
            return False
        return session["user_id"] == user_id
    
    def get_user_sessions(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all sessions for a user.
        
        Args:
            user_id: User ID
            limit: Max sessions to return
            offset: Offset for pagination
            
        Returns:
            List of session summaries
        """
        self._ensure_tables()
        
        query = """
            SELECT session_id, title, created_at, last_message_at, message_count
            FROM chat_sessions FINAL
            WHERE user_id = %(user_id)s
            ORDER BY last_message_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        
        try:
            result = self.client.execute(query, {
                "user_id": user_id,
                "limit": limit,
                "offset": offset,
            })
            
            return [
                {
                    "session_id": row[0],
                    "title": row[1],
                    "created_at": row[2],
                    "last_message_at": row[3],
                    "message_count": row[4],
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []
    
    def count_user_sessions(self, user_id: str) -> int:
        """Count total sessions for a user."""
        self._ensure_tables()
        
        query = """
            SELECT count() FROM chat_sessions FINAL
            WHERE user_id = %(user_id)s
        """
        
        try:
            result = self.client.execute(query, {"user_id": user_id})
            return result[0][0] if result else 0
        except Exception as e:
            logger.error(f"Failed to count user sessions: {e}")
            return 0
    
    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session from database.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of messages
        """
        # Check cache first
        if session_id in self._session_cache:
            cached = self._session_cache[session_id]
            if cached:
                return cached
        
        self._ensure_tables()
        
        query = """
            SELECT id, role, content, metadata, created_at
            FROM chat_messages
            WHERE session_id = %(session_id)s
            ORDER BY created_at ASC
        """
        
        try:
            result = self.client.execute(query, {"session_id": session_id})
            messages = []
            for row in result:
                metadata = {}
                if row[3]:
                    try:
                        metadata = json.loads(row[3])
                    except json.JSONDecodeError:
                        pass
                
                messages.append({
                    "id": row[0],
                    "role": row[1],
                    "content": row[2],
                    "timestamp": row[4].strftime("%H:%M:%S") if row[4] else "",
                    "metadata": metadata,
                })
            
            # Update cache
            self._session_cache[session_id] = messages
            return messages
        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return self._session_cache.get(session_id, [])
    
    def add_message(
        self, 
        session_id: str, 
        user_id: str,
        role: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a message to session history.
        
        Args:
            session_id: Session ID
            user_id: User ID
            role: Message role (user/assistant)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Created message
        """
        self._ensure_tables()
        
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        
        message = {
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "metadata": metadata,
        }
        
        # Insert into database
        insert_query = """
            INSERT INTO chat_messages (id, session_id, user_id, role, content, metadata, created_at)
            VALUES (%(id)s, %(session_id)s, %(user_id)s, %(role)s, %(content)s, %(metadata)s, %(created_at)s)
        """
        
        params = {
            "id": msg_id,
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "metadata": json.dumps(metadata or {}),
            "created_at": now,
        }
        
        try:
            self.client.execute(insert_query, params)
            
            # Update session stats
            update_query = """
                INSERT INTO chat_sessions (session_id, user_id, title, created_at, updated_at, last_message_at, message_count)
                SELECT 
                    session_id, user_id, title, created_at, 
                    %(updated_at)s as updated_at,
                    %(last_message_at)s as last_message_at,
                    message_count + 1 as message_count
                FROM chat_sessions FINAL
                WHERE session_id = %(session_id)s
            """
            self.client.execute(update_query, {
                "session_id": session_id,
                "updated_at": now,
                "last_message_at": now,
            })
        except Exception as e:
            logger.error(f"Failed to save message to database: {e}")
        
        # Update cache
        if session_id not in self._session_cache:
            self._session_cache[session_id] = []
        self._session_cache[session_id].append(message)
        
        return message
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a session and its messages.
        
        Args:
            session_id: Session ID
            user_id: User ID (for ownership verification)
            
        Returns:
            True if deleted, False otherwise
        """
        # Verify ownership
        if not self.verify_session_ownership(session_id, user_id):
            return False
        
        self._ensure_tables()
        
        try:
            # Delete messages (using ALTER TABLE DELETE for MergeTree)
            delete_messages = """
                ALTER TABLE chat_messages DELETE 
                WHERE session_id = %(session_id)s
            """
            self.client.execute(delete_messages, {"session_id": session_id})
            
            # Delete session
            delete_session = """
                ALTER TABLE chat_sessions DELETE 
                WHERE session_id = %(session_id)s
            """
            self.client.execute(delete_session, {"session_id": session_id})
            
            # Clear cache
            if session_id in self._session_cache:
                del self._session_cache[session_id]
            
            logger.info(f"Deleted session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False
    
    def update_session_title(self, session_id: str, user_id: str, title: str) -> bool:
        """Update session title.
        
        Args:
            session_id: Session ID
            user_id: User ID (for ownership verification)
            title: New title
            
        Returns:
            True if updated, False otherwise
        """
        if not self.verify_session_ownership(session_id, user_id):
            return False
        
        self._ensure_tables()
        
        try:
            now = datetime.now()
            # Insert with updated title (ReplacingMergeTree will merge)
            update_query = """
                INSERT INTO chat_sessions (session_id, user_id, title, created_at, updated_at, last_message_at, message_count)
                SELECT 
                    session_id, user_id, %(title)s as title, created_at, 
                    %(updated_at)s as updated_at,
                    last_message_at,
                    message_count
                FROM chat_sessions FINAL
                WHERE session_id = %(session_id)s
            """
            self.client.execute(update_query, {
                "session_id": session_id,
                "title": title,
                "updated_at": now,
            })
            return True
        except Exception as e:
            logger.error(f"Failed to update session title: {e}")
            return False
    
    async def process_message(
        self, 
        session_id: str,
        user_id: str,
        content: str
    ) -> Dict[str, Any]:
        """Process a user message and generate response.
        
        Args:
            session_id: Session ID
            user_id: User ID
            content: User message content
            
        Returns:
            Assistant response message
        """
        # Add user message
        self.add_message(session_id, user_id, "user", content)
        
        # Get orchestrator to process
        from stock_datasource.agents.orchestrator import get_orchestrator
        
        orchestrator = get_orchestrator()
        context = {
            "session_id": session_id,
            "user_id": user_id,
            "history": self.get_session_history(session_id)
        }
        
        try:
            result = await orchestrator.execute(content, context)
            response_content = result.response if result.response else "抱歉，我无法处理您的请求。"
            metadata = result.metadata.copy() if result.metadata else {}
            metadata["success"] = result.success
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            response_content = "抱歉，处理您的请求时出现了问题，请稍后重试。"
            metadata = {"error": str(e)}
        
        # Add assistant response
        response = self.add_message(session_id, user_id, "assistant", response_content, metadata)
        return response


# Global service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
