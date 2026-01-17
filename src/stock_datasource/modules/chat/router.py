"""Chat module router."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import logging

from .schemas import (
    SendMessageRequest,
    SendMessageResponse,
    ChatHistoryResponse,
    CreateSessionResponse,
    ChatMessage
)
from .service import get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/session", response_model=CreateSessionResponse)
async def create_session():
    """Create a new chat session."""
    service = get_chat_service()
    session_id = service.create_session()
    return CreateSessionResponse(session_id=session_id)


@router.post("/message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """Send a message and get response."""
    service = get_chat_service()
    
    try:
        response = await service.process_message(
            session_id=request.session_id,
            content=request.content
        )
        return SendMessageResponse(**response)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(session_id: str):
    """Get chat history for a session."""
    service = get_chat_service()
    messages = service.get_session_history(session_id)
    
    return ChatHistoryResponse(
        session_id=session_id,
        messages=[ChatMessage(**m) for m in messages]
    )


@router.get("/stream")
async def stream_message(session_id: str, content: str):
    """Stream a message response using SSE (GET method for simple queries)."""
    return await _stream_response(session_id, content)


@router.post("/stream")
async def stream_message_post(request: SendMessageRequest):
    """Stream a message response using SSE (POST method for longer messages)."""
    return await _stream_response(request.session_id, request.content)


async def _stream_response(session_id: str, content: str):
    """Internal function to handle streaming response using OrchestratorAgent."""
    import json
    from stock_datasource.agents.orchestrator import get_orchestrator
    
    service = get_chat_service()
    service.add_message(session_id, "user", content)
    
    orchestrator = get_orchestrator()
    context = {
        "session_id": session_id,
        "history": service.get_session_history(session_id),
    }
    
    async def generate():
        full_response = ""
        tool_calls = []
        
        try:
            async for event in orchestrator.execute_stream(content, context):
                event_type = event.get("type", "")
                
                if event_type == "thinking":
                    if event.get("tool"):
                        tool_data = json.dumps({
                            "type": "tool",
                            "tool": event.get("tool"),
                            "args": event.get("args"),
                            "agent": event.get("agent"),
                            "status": event.get("status"),
                        }, ensure_ascii=False)
                        yield f"data: {tool_data}\n\n"
                        tool_calls.append(event.get("tool"))
                    thinking_data = json.dumps({
                        "type": "thinking",
                        "intent": event.get("intent", ""),
                        "agent": event.get("agent", "OrchestratorAgent"),
                        "status": event.get("status", "分析中..."),
                        "tool": event.get("tool"),
                        "stock_codes": event.get("stock_codes", [])
                    }, ensure_ascii=False)
                    yield f"data: {thinking_data}\n\n"
                
                elif event_type == "tool":
                    tool_data = json.dumps({
                        "type": "tool",
                        "tool": event.get("tool"),
                        "args": event.get("args"),
                        "agent": event.get("agent"),
                        "status": event.get("status"),
                    }, ensure_ascii=False)
                    yield f"data: {tool_data}\n\n"
                    if event.get("tool"):
                        tool_calls.append(event.get("tool"))
                
                elif event_type == "content":
                    chunk = event.get("content", "")
                    if chunk:
                        full_response += chunk
                        data = json.dumps({
                            "type": "content",
                            "content": chunk
                        }, ensure_ascii=False)
                        yield f"data: {data}\n\n"
                
                elif event_type == "done":
                    if full_response:
                        service.add_message(session_id, "assistant", full_response)
                    metadata = event.get("metadata", {})
                    metadata.setdefault("tool_calls", tool_calls)
                    
                    done_data = json.dumps({
                        "type": "done",
                        "metadata": metadata
                    }, ensure_ascii=False)
                    yield f"data: {done_data}\n\n"
                
                elif event_type == "error":
                    error_data = json.dumps({
                        "type": "error",
                        "error": event.get("error", "未知错误")
                    }, ensure_ascii=False)
                    yield f"data: {error_data}\n\n"
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            if full_response:
                service.add_message(session_id, "assistant", full_response)
            
            error_data = json.dumps({
                "type": "error",
                "error": str(e)
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
