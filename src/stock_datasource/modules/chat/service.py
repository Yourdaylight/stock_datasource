"""Chat service implementation."""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """Chat service for handling conversations."""
    
    def __init__(self):
        # In-memory session storage (use Redis in production)
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}
    
    def create_session(self) -> str:
        """Create a new chat session.
        
        Returns:
            Session ID
        """
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = []
        return session_id
    
    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of messages
        """
        return self._sessions.get(session_id, [])
    
    def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a message to session history.
        
        Args:
            session_id: Session ID
            role: Message role (user/assistant)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Created message
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        
        message = {
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "metadata": metadata
        }
        
        self._sessions[session_id].append(message)
        return message
    
    async def process_message(
        self, 
        session_id: str, 
        content: str
    ) -> Dict[str, Any]:
        """Process a user message and generate response.
        
        Args:
            session_id: Session ID
            content: User message content
            
        Returns:
            Assistant response message
        """
        # Add user message
        self.add_message(session_id, "user", content)
        
        # Get orchestrator to process
        from stock_datasource.agents.orchestrator import OrchestratorAgent
        
        orchestrator = OrchestratorAgent()
        context = {
            "session_id": session_id,
            "history": self.get_session_history(session_id)
        }
        
        try:
            result = await orchestrator.execute(content, context)
            # AgentResult is a Pydantic model, not a dict
            response_content = result.response if result.response else "抱歉，我无法处理您的请求。"
            metadata = result.metadata.copy() if result.metadata else {}
            metadata["success"] = result.success
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            response_content = "抱歉，处理您的请求时出现了问题，请稍后重试。"
            metadata = {"error": str(e)}
        
        # Add assistant response
        response = self.add_message(session_id, "assistant", response_content, metadata)
        return response


# Global service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
