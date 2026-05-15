"""Orchestration pipeline API router."""

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..auth.dependencies import get_current_user
from stock_datasource.models.orchestration import (
    PipelineCreate,
    PipelineExecuteRequest,
    PipelineResponse,
    PipelineUpdate,
)
from stock_datasource.services.orchestration_service import get_orchestration_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[PipelineResponse])
async def list_pipelines(
    current_user: dict = Depends(get_current_user),
):
    """List all pipelines for the current user."""
    service = get_orchestration_service()
    return service.list_pipelines(user_id=current_user["id"])


@router.post("/", response_model=PipelineResponse, status_code=201)
async def create_pipeline(
    data: PipelineCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new orchestration pipeline."""
    service = get_orchestration_service()
    return service.create_pipeline(user_id=current_user["id"], data=data)


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get pipeline details including nodes and edges."""
    service = get_orchestration_service()
    pipeline = service.get_pipeline(pipeline_id, user_id=current_user["id"])
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    data: PipelineUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a pipeline (nodes, edges, metadata)."""
    service = get_orchestration_service()
    result = service.update_pipeline(pipeline_id, user_id=current_user["id"], data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Pipeline not found or no permission")
    return result


@router.delete("/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete a pipeline."""
    service = get_orchestration_service()
    success = service.delete_pipeline(pipeline_id, user_id=current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Pipeline not found or no permission")
    return {"status": "ok", "message": "Pipeline deleted"}


@router.post("/{pipeline_id}/execute")
async def execute_pipeline(
    pipeline_id: str,
    req: PipelineExecuteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Execute a pipeline. Returns SSE stream of node-by-node progress."""
    service = get_orchestration_service()
    pipeline = service.get_pipeline(pipeline_id, user_id=current_user["id"])
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    execution = service.create_execution(
        pipeline_id=pipeline_id,
        user_id=current_user["id"],
        input_data=req.input_data,
    )

    async def stream_execution():
        start_time = time.time()
        try:
            from stock_datasource.services.orchestration_engine import (
                OrchestrationEngine,
            )

            engine = OrchestrationEngine()

            yield f"data: {json.dumps({'type': 'pipeline_start', 'execution_id': execution.id, 'pipeline_id': pipeline_id})}\n\n"

            async for event in engine.execute(pipeline, req.input_data):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            duration_ms = int((time.time() - start_time) * 1000)
            yield f"data: {json.dumps({'type': 'pipeline_end', 'execution_id': execution.id, 'duration_ms': duration_ms})}\n\n"

        except Exception as e:
            logger.error("Pipeline execution failed: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(stream_execution(), media_type="text/event-stream")


@router.get("/{pipeline_id}/executions")
async def list_executions(
    pipeline_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List past executions for a pipeline."""
    service = get_orchestration_service()
    return service.list_executions(pipeline_id, user_id=current_user["id"], limit=limit)
