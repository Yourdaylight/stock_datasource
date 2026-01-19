"""AI工作流API路由。

提供工作流的CRUD操作、执行和AI生成能力。
"""

import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from stock_datasource.models.workflow import (
    AIWorkflow,
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
    WorkflowExecuteRequest,
    WorkflowGenerateRequest,
    WorkflowListResponse,
    ToolInfo,
)
from stock_datasource.services.workflow_service import get_workflow_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ============================================================================
# 工作流CRUD API
# ============================================================================

@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(include_templates: bool = Query(True, description="是否包含模板")):
    """获取工作流列表。"""
    try:
        service = get_workflow_service()
        workflows = service.list_workflows(include_templates=include_templates)
        return WorkflowListResponse(
            workflows=workflows,
            total=len(workflows)
        )
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=AIWorkflow)
async def create_workflow(request: WorkflowCreateRequest):
    """创建工作流。"""
    try:
        service = get_workflow_service()
        workflow = service.create_workflow(request)
        return workflow
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=List[AIWorkflow])
async def get_templates():
    """获取预置模板列表。"""
    try:
        service = get_workflow_service()
        return service.get_templates()
    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools", response_model=List[ToolInfo])
async def get_available_tools():
    """获取可用工具列表。"""
    try:
        service = get_workflow_service()
        return service.get_available_tools()
    except Exception as e:
        logger.error(f"Failed to get tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", response_model=AIWorkflow)
async def get_workflow(workflow_id: str):
    """获取工作流详情。"""
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
async def update_workflow(workflow_id: str, request: WorkflowUpdateRequest):
    """更新工作流。"""
    try:
        service = get_workflow_service()
        workflow = service.update_workflow(workflow_id, request)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"工作流不存在或不可编辑: {workflow_id}")
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """删除工作流。"""
    try:
        service = get_workflow_service()
        success = service.delete_workflow(workflow_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"工作流不存在或不可删除: {workflow_id}")
        return {"success": True, "message": "工作流已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/clone")
async def clone_from_template(template_id: str, name: str = Query(..., description="新工作流名称")):
    """从模板创建工作流副本。"""
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
async def execute_workflow(workflow_id: str, request: WorkflowExecuteRequest):
    """执行工作流（流式）。"""
    try:
        service = get_workflow_service()
        workflow = service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")
        
        if request.stream:
            return StreamingResponse(
                _execute_workflow_stream(workflow, request.variables),
                media_type="text/event-stream"
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


async def _execute_workflow_stream(workflow: AIWorkflow, variables: Dict[str, Any]):
    """流式执行工作流。"""
    from stock_datasource.agents.workflow_agent import create_workflow_agent
    
    agent = create_workflow_agent(workflow)
    
    try:
        async for event in agent.execute_workflow(variables):
            event_type = event.get("type", "unknown")
            
            # 格式化为SSE
            if event_type == "thinking":
                yield f"event: thinking\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif event_type == "content":
                yield f"event: content\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif event_type == "done":
                yield f"event: done\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif event_type == "error":
                yield f"event: error\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
    except Exception as e:
        logger.error(f"Workflow execution error: {e}")
        yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"


async def _execute_workflow_sync(workflow: AIWorkflow, variables: Dict[str, Any]) -> Dict[str, Any]:
    """同步执行工作流。"""
    from stock_datasource.agents.workflow_agent import create_workflow_agent
    
    agent = create_workflow_agent(workflow)
    
    full_content = ""
    tool_calls = []
    
    async for event in agent.execute_workflow(variables):
        event_type = event.get("type", "")
        
        if event_type == "content":
            full_content += event.get("content", "")
        elif event_type == "thinking" and event.get("tool"):
            tool_calls.append(event.get("tool"))
        elif event_type == "error":
            return {"success": False, "error": event.get("error")}
    
    return {
        "success": True,
        "content": full_content,
        "tool_calls": tool_calls
    }


# ============================================================================
# AI生成工作流API
# ============================================================================

@router.post("/generate")
async def generate_workflow(request: WorkflowGenerateRequest):
    """AI根据描述生成工作流配置（流式）。"""
    try:
        if request.stream:
            return StreamingResponse(
                _generate_workflow_stream(request.description),
                media_type="text/event-stream"
            )
        else:
            result = await _generate_workflow_sync(request.description)
            return result
            
    except Exception as e:
        logger.error(f"Failed to generate workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_workflow_stream(description: str):
    """流式生成工作流。"""
    from stock_datasource.agents.workflow_generator_agent import get_workflow_generator
    from stock_datasource.services.workflow_service import get_workflow_service
    
    generator = get_workflow_generator()
    service = get_workflow_service()
    
    # 设置可用工具
    tools = service.get_available_tools()
    generator.set_available_tools(tools)
    
    try:
        async for event in generator.generate_workflow(description):
            event_type = event.get("type", "unknown")
            
            if event_type == "thinking":
                yield f"event: thinking\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif event_type == "generating":
                yield f"event: generating\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif event_type == "workflow":
                yield f"event: workflow\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif event_type == "done":
                yield f"event: done\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif event_type == "error":
                yield f"event: error\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
    except Exception as e:
        logger.error(f"Workflow generation error: {e}")
        yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"


async def _generate_workflow_sync(description: str) -> Dict[str, Any]:
    """同步生成工作流。"""
    from stock_datasource.agents.workflow_generator_agent import get_workflow_generator
    from stock_datasource.services.workflow_service import get_workflow_service
    
    generator = get_workflow_generator()
    service = get_workflow_service()
    
    # 设置可用工具
    tools = service.get_available_tools()
    generator.set_available_tools(tools)
    
    workflow_config = None
    
    async for event in generator.generate_workflow(description):
        event_type = event.get("type", "")
        
        if event_type == "workflow":
            workflow_config = event.get("workflow")
        elif event_type == "error":
            return {"success": False, "error": event.get("error")}
    
    if workflow_config:
        return {"success": True, "workflow": workflow_config}
    else:
        return {"success": False, "error": "生成失败"}
