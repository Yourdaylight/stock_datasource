"""Akinator module router — 猜你所想 A股版 API."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..auth.dependencies import get_current_user
from ..auth.quota_guard import require_quota
from . import service
from .schemas import (
    AbandonRequest,
    AnswerRequest,
    AnswerResponse,
    CandidatesResponse,
    ConfirmRequest,
    QuestionDTO,
    StartResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=StartResponse, summary="开始新的猜股票会话")
async def start(current_user: dict = Depends(require_quota)):
    """启动新会话，返回 session_id 和首个问题。消耗 token。"""
    # Lazy-init ClickHouse archive table
    service.ensure_schema()

    try:
        result = await service.start_session(user_id=current_user["id"])
    except RuntimeError as e:
        raise HTTPException(500, f"启动游戏失败: {e}")

    return StartResponse(
        session_id=result["session_id"],
        question=result["question"],
        question_count=result["question_count"],
        candidates_remaining=result["candidates_remaining"],
    )


@router.post("/answer", response_model=AnswerResponse, summary="提交答案，获取下一题")
async def answer(
    body: AnswerRequest, current_user: dict = Depends(require_quota)
):
    """提交 yes/no/unknown 答案，返回下一题或最终候选列表。消耗 token。"""
    try:
        result = await service.answer_session(
            session_id=body.session_id,
            answer=body.answer,
            user_id=current_user["id"],
        )
    except LookupError:
        raise HTTPException(404, "会话不存在或已过期")
    except PermissionError:
        raise HTTPException(403, "无权访问该会话")
    except Exception as e:
        logger.error(f"answer_session failed: {e}", exc_info=True)
        raise HTTPException(500, f"处理答案失败: {e}")

    return AnswerResponse(
        session_id=result["session_id"],
        status=result["status"],
        question=result.get("question"),
        final_candidates=result.get("final_candidates"),
        question_count=result["question_count"],
        candidates_remaining=result["candidates_remaining"],
        tokens_used=result.get("tokens_used", 0),
    )


@router.get(
    "/candidates/{session_id}",
    response_model=CandidatesResponse,
    summary="获取当前候选集",
)
async def candidates(
    session_id: str, current_user: dict = Depends(get_current_user)
):
    """查看当前候选股票（用于进度展示）。不消耗 token。"""
    try:
        result = service.get_candidates(session_id, user_id=current_user["id"])
    except LookupError:
        raise HTTPException(404, "会话不存在或已过期")
    except PermissionError:
        raise HTTPException(403, "无权访问该会话")

    return CandidatesResponse(
        session_id=result["session_id"],
        candidates=result["candidates"],
        candidates_remaining=result["candidates_remaining"],
        question_count=result["question_count"],
    )


@router.post("/confirm", summary="确认猜中的股票")
async def confirm(
    body: ConfirmRequest, current_user: dict = Depends(get_current_user)
):
    """用户从最终候选中选定一只 → 归档 success。不消耗 token。"""
    try:
        return service.confirm_session(
            body.session_id, body.ts_code, user_id=current_user["id"]
        )
    except LookupError:
        raise HTTPException(404, "会话不存在或已过期")
    except PermissionError:
        raise HTTPException(403, "无权访问该会话")


@router.post("/abandon", summary="放弃本局")
async def abandon(
    body: AbandonRequest, current_user: dict = Depends(get_current_user)
):
    """用户主动放弃 → 归档 abandoned。不消耗 token。"""
    try:
        return service.abandon_session(body.session_id, user_id=current_user["id"])
    except PermissionError:
        raise HTTPException(403, "无权访问该会话")


@router.post("/answer/stream", summary="流式提交答案（SSE）")
async def answer_stream(
    body: AnswerRequest, current_user: dict = Depends(require_quota)
):
    """SSE 流式端点 — 前端可实时看到 LLM 思考过程 (`<think>...</think>`)。

    事件类型：
    - `heuristic` {question}     启发式命中，直接给下一题
    - `llm_start`                LLM 开始生成
    - `think_delta` {text}       LLM 思考文本增量
    - `think_end`                思考结束，开始生成 JSON
    - `question` {question}      解析出的下一题
    - `progress` {...}           候选集缩减进度
    - `final` {...}              最终结果（continue/finished）
    - `error` {message}          异常（前端应降级到启发式）
    """
    async def gen():
        try:
            async for ev in service.answer_session_stream(
                session_id=body.session_id,
                answer=body.answer,
                user_id=current_user["id"],
            ):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except LookupError:
            err = {"type": "error", "message": "会话不存在或已过期", "status_code": 404}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
        except PermissionError:
            err = {"type": "error", "message": "无权访问该会话", "status_code": 403}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"answer_stream failed: {e}", exc_info=True)
            err = {"type": "error", "message": f"处理答案失败: {e}"}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
