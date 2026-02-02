"""
Arena API Router

FastAPI routes for the Multi-Agent Strategy Arena system.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Use absolute imports to avoid circular import issues
from stock_datasource.arena import (
    ArenaConfig,
    ArenaAgentConfig,
    DiscussionConfig,
    CompetitionConfig,
    EvaluationConfig,
    ArenaState,
    DiscussionMode,
    EvaluationPeriod,
)
from stock_datasource.arena.arena_manager import (
    create_arena,
    get_arena,
    list_arenas,
    delete_arena,
    MultiAgentArena,
)
from stock_datasource.arena.stream_processor import generate_sse_stream
from stock_datasource.arena.exceptions import ArenaNotFoundError, ArenaStateError
from stock_datasource.modules.auth.dependencies import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)

# Note: prefix is already added by _register_module_routes as /api/arena
router = APIRouter(tags=["arena"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateArenaRequest(BaseModel):
    """Request model for creating an arena."""
    name: str = Field(..., description="Arena name")
    description: str = Field(default="", description="Arena description")
    agent_count: int = Field(default=5, ge=3, le=10, description="Number of agents")
    symbols: List[str] = Field(default_factory=list, description="Stock symbols")
    
    # Optional detailed configs
    discussion_max_rounds: int = Field(default=3, ge=1, le=10)
    initial_capital: float = Field(default=100000.0, ge=10000)
    backtest_start_date: Optional[str] = Field(default=None)
    backtest_end_date: Optional[str] = Field(default=None)
    simulated_duration_days: int = Field(default=30, ge=1, le=365)


class ArenaResponse(BaseModel):
    """Response model for arena operations."""
    id: str
    name: str
    state: str
    active_strategies: int
    total_strategies: int
    eliminated_strategies: int
    discussion_rounds: int
    last_evaluation: Optional[str]
    duration_seconds: float
    error_count: int
    last_error: Optional[str]


class StrategyResponse(BaseModel):
    """Response model for strategy."""
    id: str
    name: str
    description: str
    agent_id: str
    agent_role: str
    stage: str
    is_active: bool
    current_score: float
    current_rank: int


class LeaderboardEntry(BaseModel):
    """Response model for leaderboard entry."""
    rank: int
    strategy_id: str
    name: str
    agent_id: str
    agent_role: str
    score: float
    stage: str


class TriggerEvaluationRequest(BaseModel):
    """Request model for triggering evaluation."""
    period: str = Field(default="daily", description="daily/weekly/monthly")


class TriggerDiscussionRequest(BaseModel):
    """Request model for triggering discussion."""
    mode: str = Field(default="debate", description="debate/collaboration/review")


# =============================================================================
# Arena Management Routes
# =============================================================================

@router.post("/create", response_model=ArenaResponse)
async def create_arena_endpoint(
    request: CreateArenaRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Create a new multi-agent arena.
    
    Creates an arena with the specified configuration and initializes
    all agents. The arena will be ready to start after creation.
    Requires authentication - arena will be owned by the current user.
    """
    try:
        # Build configuration
        config = ArenaConfig(
            name=request.name,
            description=request.description,
            agent_count=request.agent_count,
            symbols=request.symbols or ["000001.SZ", "600000.SH", "000002.SZ"],
            discussion=DiscussionConfig(
                max_rounds=request.discussion_max_rounds,
            ),
            competition=CompetitionConfig(
                initial_capital=request.initial_capital,
                backtest_start_date=request.backtest_start_date,
                backtest_end_date=request.backtest_end_date,
                simulated_duration_days=request.simulated_duration_days,
            ),
        )
        
        # Create arena with user_id for data isolation
        arena = create_arena(config, user_id=current_user["id"])
        
        # Initialize in background
        background_tasks.add_task(arena.initialize)
        
        return ArenaResponse(**arena.get_status())
        
    except Exception as e:
        logger.error(f"Failed to create arena: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{arena_id}/status", response_model=ArenaResponse)
async def get_arena_status(
    arena_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get arena status.
    
    Returns current state, strategy counts, and evaluation info.
    Only returns arenas owned by the current user.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        return ArenaResponse(**arena.get_status())
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get arena status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{arena_id}/start")
async def start_arena(
    arena_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Start arena competition.
    
    Begins the competition process in the background.
    Use the thinking-stream endpoint to monitor progress.
    Only arena owner can start it.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权操作此竞技场")
        background_tasks.add_task(arena.start)
        return {"status": "started", "arena_id": arena_id}
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except ArenaStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start arena: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{arena_id}/pause")
async def pause_arena(
    arena_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Pause arena competition.
    Only arena owner or admin can pause it.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权操作此竞技场")
        await arena.pause()
        return {"status": "paused", "arena_id": arena_id}
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except ArenaStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to pause arena: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{arena_id}/resume")
async def resume_arena(
    arena_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Resume paused arena.
    Only arena owner or admin can resume it.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权操作此竞技场")
        background_tasks.add_task(arena.resume)
        return {"status": "resumed", "arena_id": arena_id}
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except ArenaStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to resume arena: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{arena_id}")
async def delete_arena_endpoint(
    arena_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete an arena.
    Only arena owner or admin can delete it.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权删除此竞技场")
        await arena.stop()
        delete_arena(arena_id)
        return {"status": "deleted", "arena_id": arena_id}
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to delete arena: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_arenas_endpoint(
    state: Optional[str] = Query(None, description="Filter by state"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """List all arenas owned by the current user.
    Admins can see all arenas.
    """
    try:
        # Filter by user unless admin
        user_id_filter = None if current_user.get("is_admin", False) else current_user["id"]
        arenas = list_arenas(user_id=user_id_filter)
        
        if state:
            arenas = [a for a in arenas if a["state"] == state]
        
        return {
            "total": len(arenas),
            "arenas": arenas[:limit],
        }
    except Exception as e:
        logger.error(f"Failed to list arenas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Thinking Stream Routes
# =============================================================================

@router.get("/{arena_id}/thinking-stream")
async def thinking_stream(
    arena_id: str,
    round_id: Optional[str] = Query(None, description="Filter by round"),
    current_user: dict = Depends(get_current_user),
):
    """SSE endpoint for real-time thinking stream.
    
    Returns a Server-Sent Events stream of agent thinking messages.
    Use this to display real-time progress in the UI.
    Only arena owner or admin can access.
    """
    try:
        # Verify arena exists and user has access
        arena = get_arena(arena_id)
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        
        return StreamingResponse(
            generate_sse_stream(arena_id=arena_id, round_id=round_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to start thinking stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{arena_id}/discussions")
async def get_discussions(
    arena_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """Get discussion history. Only arena owner or admin can access."""
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        history = arena.get_discussion_history()
        return {
            "total": len(history),
            "discussions": history[:limit],
        }
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get discussions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{arena_id}/discussions/{round_id}")
async def get_discussion_detail(
    arena_id: str,
    round_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific discussion round.
    Only arena owner or admin can access.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        history = arena.get_discussion_history()
        
        for discussion in history:
            if discussion["id"] == round_id:
                return discussion
        
        raise HTTPException(status_code=404, detail=f"Discussion round not found: {round_id}")
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get discussion detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Strategy Routes
# =============================================================================

@router.get("/{arena_id}/strategies")
async def get_strategies(
    arena_id: str,
    active_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """Get strategies in the arena. Only arena owner or admin can access."""
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        strategies = arena.get_strategies(active_only=active_only)
        return {
            "total": len(strategies),
            "strategies": strategies,
        }
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{arena_id}/strategies/{strategy_id}")
async def get_strategy_detail(
    arena_id: str,
    strategy_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific strategy.
    Only arena owner or admin can access.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        strategies = arena.get_strategies()
        
        for strategy in strategies:
            if strategy["id"] == strategy_id:
                return strategy
        
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get strategy detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{arena_id}/leaderboard")
async def get_leaderboard(
    arena_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """Get current strategy leaderboard.
    Only arena owner or admin can access.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        leaderboard = arena.get_leaderboard()
        return {
            "total": len(leaderboard),
            "leaderboard": leaderboard[:limit],
        }
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Evaluation Routes
# =============================================================================

@router.post("/{arena_id}/evaluate")
async def trigger_evaluation(
    arena_id: str,
    request: TriggerEvaluationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Trigger manual evaluation.
    
    Manually trigger a periodic evaluation (daily/weekly/monthly).
    Only arena owner or admin can trigger evaluation.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权操作此竞技场")
        
        period_map = {
            "daily": EvaluationPeriod.DAILY,
            "weekly": EvaluationPeriod.WEEKLY,
            "monthly": EvaluationPeriod.MONTHLY,
        }
        
        period = period_map.get(request.period.lower())
        if not period:
            raise HTTPException(status_code=400, detail=f"Invalid period: {request.period}")
        
        background_tasks.add_task(arena._perform_evaluation, period)
        
        return {
            "status": "evaluation_triggered",
            "period": request.period,
            "arena_id": arena_id,
        }
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to trigger evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{arena_id}/history")
async def get_competition_history(
    arena_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Get full competition history including evaluations.
    Only arena owner or admin can access.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        arena_dict = arena.to_dict()
        
        return {
            "arena_id": arena_id,
            "state": arena_dict["state"],
            "discussion_rounds": arena_dict["discussion_rounds"],
            "evaluations": arena_dict["evaluations"][:limit],
            "eliminated_strategies": arena_dict["eliminated_strategies"],
            "duration_seconds": arena_dict["duration_seconds"],
        }
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get competition history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Discussion Control Routes
# =============================================================================

@router.post("/{arena_id}/discussion/start")
async def start_discussion(
    arena_id: str,
    request: TriggerDiscussionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger a discussion round.
    Only arena owner or admin can start discussion.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权操作此竞技场")
        
        mode_map = {
            "debate": DiscussionMode.DEBATE,
            "collaboration": DiscussionMode.COLLABORATION,
            "review": DiscussionMode.REVIEW,
        }
        
        mode = mode_map.get(request.mode.lower())
        if not mode:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
        
        # Run discussion in background
        async def run_discussion():
            market_context = await arena._get_market_context()
            await arena.discussion_orchestrator.run_discussion(
                strategies=arena.arena.strategies,
                mode=mode,
                market_context=market_context,
            )
        
        background_tasks.add_task(run_discussion)
        
        return {
            "status": "discussion_started",
            "mode": request.mode,
            "arena_id": arena_id,
        }
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to start discussion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{arena_id}/discussion/current")
async def get_current_discussion(
    arena_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get current discussion status.
    Only arena owner or admin can access.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        current_round_id = arena.arena.current_round_id
        
        if not current_round_id:
            return {"status": "no_active_discussion"}
        
        history = arena.get_discussion_history()
        for discussion in history:
            if discussion["id"] == current_round_id:
                return {
                    "status": "active" if not discussion.get("completed_at") else "completed",
                    "round": discussion,
                }
        
        return {"status": "unknown", "round_id": current_round_id}
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get current discussion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Human Intervention Routes
# =============================================================================

class InterventionRequest(BaseModel):
    """Request model for human intervention."""
    action: str = Field(..., description="intervention action: inject_message/adjust_score/eliminate_strategy/add_strategy")
    target_strategy_id: Optional[str] = Field(default=None, description="Target strategy ID for score adjustment or elimination")
    message: Optional[str] = Field(default=None, description="Message to inject into discussion")
    score_adjustment: Optional[float] = Field(default=None, description="Score adjustment value (-50 to +50)")
    reason: Optional[str] = Field(default=None, description="Reason for intervention")
    new_strategy_config: Optional[Dict[str, Any]] = Field(default=None, description="Config for new strategy to add")


@router.post("/{arena_id}/discussion/intervention")
async def intervention(
    arena_id: str,
    request: InterventionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Human intervention in arena discussion.
    
    Allows manual intervention in the arena competition:
    - inject_message: Inject a message into current discussion
    - adjust_score: Manually adjust a strategy's score
    - eliminate_strategy: Force eliminate a strategy
    - add_strategy: Add a new strategy to the arena
    
    Only arena owner or admin can intervene.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权操作此竞技场")
        
        result = {
            "status": "intervention_applied",
            "action": request.action,
            "arena_id": arena_id,
            "timestamp": datetime.now().isoformat(),
        }
        
        if request.action == "inject_message":
            if not request.message:
                raise HTTPException(status_code=400, detail="Message is required for inject_message action")
            
            # Inject message into thinking stream
            from stock_datasource.arena.stream_processor import ThinkingStreamProcessor
            from stock_datasource.arena.models import MessageType
            processor = ThinkingStreamProcessor(arena_id)
            await processor.publish(
                agent_id="human_operator",
                agent_role="human",
                content=request.message,
                message_type=MessageType.INTERVENTION,
                round_id=arena.arena.current_round_id or "intervention",
                metadata={"reason": request.reason or "Human intervention"},
            )
            result["message"] = "Message injected successfully"
            
        elif request.action == "adjust_score":
            if not request.target_strategy_id:
                raise HTTPException(status_code=400, detail="target_strategy_id is required for adjust_score action")
            if request.score_adjustment is None:
                raise HTTPException(status_code=400, detail="score_adjustment is required for adjust_score action")
            if not -50 <= request.score_adjustment <= 50:
                raise HTTPException(status_code=400, detail="score_adjustment must be between -50 and +50")
            
            # Find and adjust strategy score
            for strategy in arena.arena.strategies:
                if strategy.id == request.target_strategy_id:
                    old_score = strategy.current_score
                    strategy.current_score = max(0, min(100, strategy.current_score + request.score_adjustment))
                    result["old_score"] = old_score
                    result["new_score"] = strategy.current_score
                    result["strategy_id"] = request.target_strategy_id
                    break
            else:
                raise HTTPException(status_code=404, detail=f"Strategy not found: {request.target_strategy_id}")
                
        elif request.action == "eliminate_strategy":
            if not request.target_strategy_id:
                raise HTTPException(status_code=400, detail="target_strategy_id is required for eliminate_strategy action")
            
            # Find and eliminate strategy
            for strategy in arena.arena.strategies:
                if strategy.id == request.target_strategy_id:
                    strategy.is_active = False
                    arena.arena.eliminated_strategies.append({
                        "strategy_id": strategy.id,
                        "strategy_name": strategy.name,
                        "eliminated_at": datetime.now().isoformat(),
                        "reason": request.reason or "Human intervention",
                        "final_score": strategy.current_score,
                    })
                    result["strategy_id"] = request.target_strategy_id
                    result["message"] = f"Strategy {strategy.name} eliminated"
                    break
            else:
                raise HTTPException(status_code=404, detail=f"Strategy not found: {request.target_strategy_id}")
                
        elif request.action == "add_strategy":
            if not request.new_strategy_config:
                raise HTTPException(status_code=400, detail="new_strategy_config is required for add_strategy action")
            
            # Create new strategy from config
            import uuid
            new_strategy_id = f"manual_{uuid.uuid4().hex[:8]}"
            new_strategy = {
                "id": new_strategy_id,
                "name": request.new_strategy_config.get("name", f"Manual Strategy {new_strategy_id}"),
                "description": request.new_strategy_config.get("description", "Manually added strategy"),
                "agent_id": "human_operator",
                "agent_role": "human",
                "stage": "backtest",
                "is_active": True,
                "current_score": 50.0,
                "current_rank": len(arena.arena.strategies) + 1,
                "logic": request.new_strategy_config.get("logic", ""),
                "rules": request.new_strategy_config.get("rules", {}),
            }
            # Note: In real implementation, this would create a proper Strategy object
            result["new_strategy_id"] = new_strategy_id
            result["message"] = f"New strategy {new_strategy_id} added"
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")
        
        return result
        
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply intervention: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Elimination History Routes  
# =============================================================================

@router.get("/{arena_id}/elimination-history")
async def get_elimination_history(
    arena_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Get elimination history timeline events.
    Only arena owner or admin can access.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        arena_dict = arena.to_dict()
        
        events = []
        
        # Add elimination events
        for elim in arena_dict.get("eliminated_strategies", []):
            events.append({
                "id": f"elim_{elim.get('strategy_id', '')}",
                "type": "elimination",
                "timestamp": elim.get("eliminated_at", ""),
                "period": elim.get("period", "manual"),
                "strategy_name": elim.get("strategy_name", "Unknown"),
                "strategy_id": elim.get("strategy_id"),
                "score": elim.get("final_score"),
                "reason": elim.get("reason", "Performance below threshold"),
            })
        
        # Add evaluation events
        for eval_record in arena_dict.get("evaluations", []):
            events.append({
                "id": f"eval_{eval_record.get('id', '')}",
                "type": "evaluation",
                "timestamp": eval_record.get("completed_at", ""),
                "period": eval_record.get("period", "daily"),
                "total_strategies": eval_record.get("total_strategies", 0),
                "eliminated_count": eval_record.get("eliminated_count", 0),
            })
        
        # Sort by timestamp descending
        events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return {
            "total": len(events),
            "events": events[:limit],
        }
        
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get elimination history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{arena_id}/strategies/{strategy_id}/score-breakdown")
async def get_strategy_score_breakdown(
    arena_id: str,
    strategy_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get detailed score breakdown for a strategy.
    Only arena owner or admin can access.
    """
    try:
        arena = get_arena(arena_id)
        # Check user ownership
        if arena.user_id and arena.user_id != current_user["id"] and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="无权访问此竞技场")
        strategies = arena.get_strategies()
        
        for strategy in strategies:
            if strategy["id"] == strategy_id:
                # Mock score breakdown - in real implementation, this would come from evaluation records
                total_score = strategy.get("current_score", 50.0)
                return {
                    "strategy_id": strategy_id,
                    "total_score": total_score,
                    "breakdown": {
                        "profitability": min(100, total_score * 1.2),
                        "risk_control": min(100, total_score * 0.9),
                        "stability": min(100, total_score * 1.0),
                        "adaptability": min(100, total_score * 0.85),
                    },
                    "weights": {
                        "profitability": 0.30,
                        "risk_control": 0.30,
                        "stability": 0.20,
                        "adaptability": 0.20,
                    },
                }
        
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
        
    except ArenaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Arena not found: {arena_id}")
    except Exception as e:
        logger.error(f"Failed to get score breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))
