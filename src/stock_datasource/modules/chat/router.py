"""Chat module router with user authentication."""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
import logging

from .schemas import (
    SendMessageRequest,
    SendMessageResponse,
    ChatHistoryResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    SessionListResponse,
    ChatMessage,
    ChatSessionSummary,
)
from .service import get_chat_service
from ..auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/session", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest = None,
    current_user: dict = Depends(get_current_user),
):
    """Create a new chat session for the authenticated user."""
    service = get_chat_service()
    title = request.title if request else None
    session_id = service.create_session(user_id=current_user["id"], title=title)
    return CreateSessionResponse(session_id=session_id)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Get all chat sessions for the authenticated user."""
    service = get_chat_service()
    sessions = service.get_user_sessions(
        user_id=current_user["id"],
        limit=limit,
        offset=offset,
    )
    total = service.count_user_sessions(current_user["id"])
    
    return SessionListResponse(
        sessions=[
            ChatSessionSummary(
                session_id=s["session_id"],
                title=s["title"],
                created_at=s["created_at"],
                last_message_at=s["last_message_at"],
                message_count=s["message_count"],
            )
            for s in sessions
        ],
        total=total,
    )


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a chat session (only if owned by current user)."""
    service = get_chat_service()
    success = service.delete_session(session_id, user_id=current_user["id"])
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此会话或会话不存在",
        )
    
    return {"success": True, "message": "会话已删除"}


@router.put("/session/{session_id}/title")
async def update_session_title(
    session_id: str,
    title: str,
    current_user: dict = Depends(get_current_user),
):
    """Update session title."""
    service = get_chat_service()
    success = service.update_session_title(session_id, current_user["id"], title)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此会话或会话不存在",
        )
    
    return {"success": True, "message": "标题已更新"}


@router.post("/message", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """Send a message and get response."""
    service = get_chat_service()
    
    # Verify session ownership
    if not service.verify_session_ownership(request.session_id, current_user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此会话",
        )
    
    try:
        response = await service.process_message(
            session_id=request.session_id,
            user_id=current_user["id"],
            content=request.content,
        )
        return SendMessageResponse(**response)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get chat history for a session (only if owned by current user)."""
    service = get_chat_service()
    
    # Verify session ownership
    if not service.verify_session_ownership(session_id, current_user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此会话",
        )
    
    messages = service.get_session_history(session_id)
    
    return ChatHistoryResponse(
        session_id=session_id,
        messages=[ChatMessage(**m) for m in messages]
    )


@router.get("/stream")
async def stream_message(
    session_id: str, 
    content: str,
    current_user: dict = Depends(get_current_user),
):
    """Stream a message response using SSE (GET method for simple queries)."""
    return await _stream_response(session_id, content, current_user)


@router.post("/stream")
async def stream_message_post(
    request: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """Stream a message response using SSE (POST method for longer messages)."""
    return await _stream_response(request.session_id, request.content, current_user)


async def _stream_response(session_id: str, content: str, current_user: dict):
    """Internal function to handle streaming response using OrchestratorAgent."""
    import json
    import traceback
    from stock_datasource.agents.orchestrator import get_orchestrator
    
    service = get_chat_service()
    
    # Verify session ownership
    if not service.verify_session_ownership(session_id, current_user["id"]):
        async def error_gen():
            error_data = json.dumps({
                "type": "error",
                "error": "无权访问此会话"
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
        
        return StreamingResponse(
            error_gen(),
            media_type="text/event-stream",
            status_code=403,
        )
    
    user_id = current_user["id"]
    
    # Log incoming request
    logger.info(f"[Chat] New message from user {user_id}, session {session_id}: {content[:100]}...")
    
    service.add_message(session_id, user_id, "user", content)
    
    orchestrator = get_orchestrator()
    context = {
        "session_id": session_id,
        "user_id": user_id,
        "history": service.get_session_history(session_id),
    }
    
    async def generate():
        full_response = ""
        tool_calls = []
        tool_errors = []
        debug_events = []
        visualizations = []
        event_count = 0
        terminal_sent = False
        
        try:
            async for event in orchestrator.execute_stream(content, context):
                event_type = event.get("type", "")
                event_count += 1
                
                # Log each event for debugging
                logger.debug(f"[Chat] Event #{event_count}: type={event_type}, agent={event.get('agent')}, status={event.get('status', '')[:50]}")
                
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
                
                elif event_type == "debug":
                    # Forward debug events to frontend and collect for persistence
                    debug_events.append(event)
                    debug_data = json.dumps(event, ensure_ascii=False)
                    yield f"data: {debug_data}\n\n"
                
                elif event_type == "visualization":
                    # Forward visualization events to frontend and collect for persistence
                    viz_payload = event.get("visualization", {})
                    visualizations.append(viz_payload)
                    viz_data = json.dumps({
                        "type": "visualization",
                        "visualization": viz_payload,
                        "agent": event.get("agent"),
                        "tool": event.get("tool"),
                    }, ensure_ascii=False)
                    yield f"data: {viz_data}\n\n"
                
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
                    if tool_errors:
                        failure_note = "\n\n> ⚠️ 工具调用失败摘要: " + "; ".join(tool_errors[:3])
                        if len(tool_errors) > 3:
                            failure_note += f" 等共{len(tool_errors)}个错误"
                        full_response += failure_note
                    metadata = event.get("metadata", {})
                    metadata.setdefault("tool_calls", tool_calls)
                    if tool_errors:
                        metadata["tool_errors"] = tool_errors
                    # Attach collected debug events for persistence
                    if debug_events:
                        metadata["debug_events"] = debug_events
                    # Attach visualization data for history re-rendering
                    if visualizations:
                        metadata["visualizations"] = visualizations
                    if full_response:
                        service.add_message(session_id, user_id, "assistant", full_response, metadata=metadata)
                    
                    logger.info(f"[Chat] Completed - events: {event_count}, response length: {len(full_response)}, tools: {tool_calls}, debug_events: {len(debug_events)}")
                    
                    done_data = json.dumps({
                        "type": "done",
                        "metadata": metadata
                    }, ensure_ascii=False)
                    yield f"data: {done_data}\n\n"
                    terminal_sent = True
                
                elif event_type == "error":
                    error_msg = event.get("error", "未知错误")
                    logger.error(f"[Chat] Agent error: {error_msg}")
                    tool_errors.append(error_msg)
                    error_data = json.dumps({
                        "type": "error",
                        "error": error_msg
                    }, ensure_ascii=False)
                    yield f"data: {error_data}\n\n"
                    
        except Exception as e:
            # Log full traceback for debugging
            error_traceback = traceback.format_exc()
            logger.error(f"[Chat] Streaming error for session {session_id}:\n{error_traceback}")
            
            if full_response:
                if tool_errors:
                    failure_note = "\n\n> ⚠️ 工具调用失败摘要: " + "; ".join(tool_errors[:3])
                    if len(tool_errors) > 3:
                        failure_note += f" 等共{len(tool_errors)}个错误"
                    full_response += failure_note
                service.add_message(session_id, user_id, "assistant", full_response)
            
            error_data = json.dumps({
                "type": "error",
                "error": f"处理请求时发生错误: {str(e)}"
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
        finally:
            # Always guarantee a terminal 'done' event so the frontend
            # does not report "SSE stream closed without terminal event"
            if not terminal_sent:
                logger.warning(f"[Chat] Stream ended without done event for session {session_id}, sending fallback done")
                done_data = json.dumps({
                    "type": "done",
                    "metadata": {
                        "agent": "OrchestratorAgent",
                        "tool_calls": tool_calls,
                        "error": tool_errors[-1] if tool_errors else None,
                    }
                }, ensure_ascii=False)
                yield f"data: {done_data}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
