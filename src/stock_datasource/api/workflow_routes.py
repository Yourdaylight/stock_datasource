"""AI工作流API路由。

提供工作流的CRUD操作、执行和AI生成能力。
所有操作需要用户登录，删除操作需要管理员权限。
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from stock_datasource.models.workflow import (
    AIWorkflow,
    ToolInfo,
    WorkflowCreateRequest,
    WorkflowExecuteRequest,
    WorkflowGenerateRequest,
    WorkflowListResponse,
    WorkflowUpdateRequest,
)
from stock_datasource.modules.auth.dependencies import get_current_user, require_admin
from stock_datasource.services.workflow_service import get_workflow_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ============================================================================
# 工作流CRUD API
# ============================================================================


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    include_templates: bool = Query(True, description="是否包含模板"),
    current_user: dict = Depends(get_current_user),
):
    """获取工作流列表。需要登录。"""
    try:
        service = get_workflow_service()
        workflows = service.list_workflows(include_templates=include_templates)
        return WorkflowListResponse(workflows=workflows, total=len(workflows))
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=AIWorkflow)
async def create_workflow(
    request: WorkflowCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """创建工作流。需要登录。"""
    try:
        service = get_workflow_service()
        workflow = service.create_workflow(request)
        return workflow
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=list[AIWorkflow])
async def get_templates(
    current_user: dict = Depends(get_current_user),
):
    """获取预置模板列表。需要登录。"""
    try:
        service = get_workflow_service()
        return service.get_templates()
    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools", response_model=list[ToolInfo])
async def get_available_tools(
    current_user: dict = Depends(get_current_user),
):
    """获取可用工具列表。需要登录。"""
    try:
        service = get_workflow_service()
        return service.get_available_tools()
    except Exception as e:
        logger.error(f"Failed to get tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", response_model=AIWorkflow)
async def get_workflow(
    workflow_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取工作流详情。需要登录。"""
    try:
        service = get_workflow_service()
        workflow = service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workflow_id}", response_model=AIWorkflow)
async def update_workflow(
    workflow_id: str,
    request: WorkflowUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新工作流。需要登录。"""
    try:
        service = get_workflow_service()
        workflow = service.update_workflow(workflow_id, request)
        if not workflow:
            raise HTTPException(
                status_code=404, detail=f"工作流不存在或不可编辑: {workflow_id}"
            )
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    admin_user: dict = Depends(require_admin),
):
    """删除工作流。需要管理员权限。"""
    try:
        service = get_workflow_service()
        success = service.delete_workflow(workflow_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"工作流不存在或不可删除: {workflow_id}"
            )
        return {"success": True, "message": "工作流已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/clone")
async def clone_from_template(
    template_id: str,
    name: str = Query(..., description="新工作流名称"),
    current_user: dict = Depends(get_current_user),
):
    """从模板创建工作流副本。需要登录。"""
    try:
        service = get_workflow_service()
        workflow = service.clone_from_template(template_id, name)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"模板不存在: {template_id}")
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clone template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 工作流执行API
# ============================================================================


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    current_user: dict = Depends(get_current_user),
):
    """执行工作流（流式）。需要登录。"""
    try:
        service = get_workflow_service()
        workflow = service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

        if request.stream:
            return StreamingResponse(
                _execute_workflow_stream(workflow, request.variables),
                media_type="text/event-stream",
            )
        else:
            # 非流式执行
            result = await _execute_workflow_sync(workflow, request.variables)
            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _execute_workflow_stream(workflow: AIWorkflow, variables: dict[str, Any]):
    """Deprecated workflow execution stream."""
    event = {
        "type": "error",
        "error": "AI工作流执行已迁移到Agent编排系统，请使用新的编排入口。",
        "workflow_id": workflow.id,
    }
    yield f"event: error\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _execute_workflow_sync(
    workflow: AIWorkflow, variables: dict[str, Any]
) -> dict[str, Any]:
    """Deprecated workflow execution response."""
    return {
        "success": False,
        "error": "AI工作流执行已迁移到Agent编排系统，请使用新的编排入口。",
        "workflow_id": workflow.id,
    }


# ============================================================================
# AI生成工作流API
# ============================================================================


@router.post("/generate")
async def generate_workflow(
    request: WorkflowGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """AI根据描述生成工作流配置（流式）。需要登录。"""
    try:
        if request.stream:
            return StreamingResponse(
                _generate_workflow_stream(request.description),
                media_type="text/event-stream",
            )
        else:
            result = await _generate_workflow_sync(request.description)
            return result

    except Exception as e:
        logger.error(f"Failed to generate workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_workflow_stream(description: str):
    """Deprecated workflow generation stream."""
    event = {
        "type": "error",
        "error": "AI工作流生成已迁移到Agent管理UI，请直接配置Agent提示词与技能。",
    }
    yield f"event: error\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _generate_workflow_sync(description: str) -> dict[str, Any]:
    """Deprecated workflow generation response."""
    return {
        "success": False,
        "error": "AI工作流生成已迁移到Agent管理UI，请直接配置Agent提示词与技能。",
    }
