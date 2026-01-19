"""AI工作流数据模型。

定义AI工作流的配置结构，包括工具选择、提示词模板、变量定义等。
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WorkflowVariable(BaseModel):
    """工作流变量定义。"""
    name: str = Field(..., description="变量名，如 stock_code")
    label: str = Field(..., description="显示标签")
    type: str = Field(default="string", description="类型: string, number, date, stock_code, stock_list")
    required: bool = Field(default=True, description="是否必填")
    default: Optional[str] = Field(default=None, description="默认值")
    description: Optional[str] = Field(default=None, description="变量说明")


class AIWorkflow(BaseModel):
    """AI工作流配置。"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="工作流唯一ID")
    name: str = Field(..., description="工作流名称")
    description: str = Field(default="", description="工作流描述")
    system_prompt: str = Field(default="", description="系统提示词（定义AI角色和行为）")
    user_prompt_template: str = Field(default="", description="用户提示词模板（支持变量替换）")
    selected_tools: List[str] = Field(default_factory=list, description="选中的MCP工具名称列表")
    variables: List[WorkflowVariable] = Field(default_factory=list, description="工作流变量定义")
    is_template: bool = Field(default=False, description="是否为模板")
    category: str = Field(default="custom", description="工作流分类")
    tags: List[str] = Field(default_factory=list, description="标签")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求。"""
    variables: Dict[str, Any] = Field(default_factory=dict, description="变量值映射")
    stream: bool = Field(default=True, description="是否流式返回")


class WorkflowGenerateRequest(BaseModel):
    """AI生成工作流请求。"""
    description: str = Field(..., description="用户描述的分析策略或交易方式")
    stream: bool = Field(default=True, description="是否流式返回")


class ToolInfo(BaseModel):
    """MCP工具信息。"""
    name: str = Field(..., description="工具名称")
    description: str = Field(default="", description="工具描述")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="参数定义")
    category: str = Field(default="data", description="工具分类")


class WorkflowCreateRequest(BaseModel):
    """创建工作流请求。"""
    name: str = Field(..., description="工作流名称")
    description: str = Field(default="", description="工作流描述")
    system_prompt: str = Field(default="", description="系统提示词")
    user_prompt_template: str = Field(default="", description="用户提示词模板")
    selected_tools: List[str] = Field(default_factory=list, description="选中的工具")
    variables: List[WorkflowVariable] = Field(default_factory=list, description="变量定义")
    is_template: bool = Field(default=False, description="是否为模板")
    category: str = Field(default="custom", description="分类")
    tags: List[str] = Field(default_factory=list, description="标签")


class WorkflowUpdateRequest(BaseModel):
    """更新工作流请求。"""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    selected_tools: Optional[List[str]] = None
    variables: Optional[List[WorkflowVariable]] = None
    is_template: Optional[bool] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class WorkflowListResponse(BaseModel):
    """工作流列表响应。"""
    workflows: List[AIWorkflow]
    total: int


class WorkflowExecuteEvent(BaseModel):
    """工作流执行事件（用于流式返回）。"""
    type: str = Field(..., description="事件类型: thinking, content, tool_call, done, error")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")
