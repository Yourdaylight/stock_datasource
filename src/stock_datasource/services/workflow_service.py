"""AI工作流服务。

提供工作流的CRUD操作和执行能力。
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator

from stock_datasource.models.workflow import (
    AIWorkflow, 
    WorkflowVariable,
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
    ToolInfo,
)

logger = logging.getLogger(__name__)

# 工作流存储目录
WORKFLOW_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "workflows"


class WorkflowService:
    """工作流服务类。"""
    
    def __init__(self):
        """初始化工作流服务。"""
        self._ensure_data_dir()
        self._templates = self._load_templates()
    
    def _ensure_data_dir(self):
        """确保数据目录存在。"""
        WORKFLOW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    def _get_workflow_path(self, workflow_id: str) -> Path:
        """获取工作流文件路径。"""
        return WORKFLOW_DATA_DIR / f"{workflow_id}.json"
    
    def _load_templates(self) -> List[AIWorkflow]:
        """加载预置模板。"""
        templates = []
        
        # 单股分析模板
        templates.append(AIWorkflow(
            id="template_single_stock",
            name="单股深度分析",
            description="对单只股票进行全面分析，包括行情、估值、技术面等",
            system_prompt="""你是一位专业的A股分析师。请对用户指定的股票进行全面深度分析，包括：
1. 基本面分析：获取股票基本信息和估值数据
2. 技术面分析：计算均线、趋势等技术指标
3. 综合评估：结合以上数据给出投资建议

分析要求：
- 数据要准确，先调用工具获取最新数据
- 分析要有逻辑，先数据后结论
- 给出明确的投资建议和风险提示""",
            user_prompt_template="请对股票 {{stock_code}} 进行深度分析，包括基本面、技术面，并给出投资建议。",
            selected_tools=[
                "tushare_daily_get_latest_daily",
                "tushare_valuation_get_latest_valuation",
            ],
            variables=[
                WorkflowVariable(
                    name="stock_code",
                    label="股票代码",
                    type="stock_code",
                    required=True,
                    description="输入股票代码，如 600519.SH"
                )
            ],
            is_template=True,
            category="analysis",
            tags=["个股分析", "基本面", "技术面"]
        ))
        
        # 股票对比模板
        templates.append(AIWorkflow(
            id="template_stock_compare",
            name="股票对比分析",
            description="对比多只股票的估值和财务指标，找出最优选择",
            system_prompt="""你是一位专业的股票分析师，擅长对比分析。请对用户指定的多只股票进行横向对比分析：

对比维度：
1. 估值对比：PE、PB、市值
2. 涨跌表现：近期涨跌幅

分析要求：
- 制作对比表格，直观展示差异
- 分析各股票的优劣势
- 给出相对投资价值的排序建议""",
            user_prompt_template="请对比分析以下股票：{{stock_list}}，从估值、涨跌等方面进行对比，给出投资价值排序。",
            selected_tools=[
                "tushare_daily_get_latest_daily",
                "tushare_valuation_get_latest_valuation",
            ],
            variables=[
                WorkflowVariable(
                    name="stock_list",
                    label="股票列表",
                    type="stock_list",
                    required=True,
                    description="输入多个股票代码，用逗号分隔，如：600519.SH,000858.SZ,002304.SZ"
                )
            ],
            is_template=True,
            category="comparison",
            tags=["对比分析", "估值对比"]
        ))
        
        # 价值投资筛选模板
        templates.append(AIWorkflow(
            id="template_value_investing",
            name="价值投资筛选",
            description="基于价值投资理念筛选低估值高质量股票",
            system_prompt="""你是一位价值投资专家，深谙巴菲特的投资理念。请帮助用户筛选价值投资标的：

筛选标准：
1. 估值合理：PE在行业平均以下
2. 盈利稳定：关注ROE、净利润率
3. 财务健康：资产负债率合理

分析方法：
- 先获取满足条件的股票
- 分析每只股票的投资价值
- 给出优先级排序和买入建议""",
            user_prompt_template="请筛选PE低于{{max_pe}}、PB低于{{max_pb}}的股票，分析其价值投资潜力。",
            selected_tools=[
                "tushare_valuation_get_latest_valuation",
                "tushare_daily_get_latest_daily",
            ],
            variables=[
                WorkflowVariable(
                    name="max_pe",
                    label="最大PE",
                    type="number",
                    required=True,
                    default="20",
                    description="PE上限"
                ),
                WorkflowVariable(
                    name="max_pb",
                    label="最大PB",
                    type="number",
                    required=True,
                    default="3",
                    description="PB上限"
                )
            ],
            is_template=True,
            category="screening",
            tags=["价值投资", "低估值", "筛选"]
        ))
        
        # 技术面分析模板
        templates.append(AIWorkflow(
            id="template_technical_analysis",
            name="技术面分析",
            description="分析股票的技术指标和趋势",
            system_prompt="""你是一位技术分析专家，精通各种技术指标。请对股票进行技术面分析：

分析内容：
1. 趋势分析：判断当前是上涨、下跌还是震荡趋势
2. 均线系统：MA5、MA10、MA20的排列关系
3. 量价关系：成交量与价格的配合情况

给出建议：
- 短期操作建议
- 重要支撑位和压力位
- 风险提示""",
            user_prompt_template="请分析股票 {{stock_code}} 最近 {{days}} 个交易日的技术走势，给出操作建议。",
            selected_tools=[
                "tushare_daily_get_daily_data",
                "tushare_daily_get_latest_daily",
            ],
            variables=[
                WorkflowVariable(
                    name="stock_code",
                    label="股票代码",
                    type="stock_code",
                    required=True,
                    description="输入股票代码"
                ),
                WorkflowVariable(
                    name="days",
                    label="分析天数",
                    type="number",
                    required=False,
                    default="30",
                    description="分析最近多少个交易日"
                )
            ],
            is_template=True,
            category="technical",
            tags=["技术分析", "趋势", "均线"]
        ))
        
        # 板块扫描模板
        templates.append(AIWorkflow(
            id="template_sector_scan",
            name="板块扫描",
            description="扫描特定行业板块的股票表现",
            system_prompt="""你是一位行业分析师，擅长板块轮动分析。请对指定行业进行扫描分析：

分析内容：
1. 板块整体表现
2. 龙头股分析
3. 估值水平对比

给出建议：
- 板块投资价值评估
- 重点关注标的
- 风险提示""",
            user_prompt_template="请扫描 {{sector}} 行业的股票，分析板块整体表现和投资机会。",
            selected_tools=[
                "tushare_daily_get_latest_daily",
                "tushare_valuation_get_latest_valuation",
            ],
            variables=[
                WorkflowVariable(
                    name="sector",
                    label="行业名称",
                    type="string",
                    required=True,
                    description="输入行业名称，如：白酒、银行、医药"
                )
            ],
            is_template=True,
            category="sector",
            tags=["板块分析", "行业扫描"]
        ))
        
        return templates
    
    # CRUD Operations
    
    def create_workflow(self, request: WorkflowCreateRequest) -> AIWorkflow:
        """创建工作流。"""
        workflow = AIWorkflow(
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            user_prompt_template=request.user_prompt_template,
            selected_tools=request.selected_tools,
            variables=request.variables,
            is_template=request.is_template,
            category=request.category,
            tags=request.tags,
        )
        
        # 保存到文件
        self._save_workflow(workflow)
        logger.info(f"Created workflow: {workflow.id} - {workflow.name}")
        
        return workflow
    
    def get_workflow(self, workflow_id: str) -> Optional[AIWorkflow]:
        """获取工作流。"""
        # 先检查模板
        for template in self._templates:
            if template.id == workflow_id:
                return template
        
        # 再检查用户工作流
        path = self._get_workflow_path(workflow_id)
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return AIWorkflow(**data)
            except Exception as e:
                logger.error(f"Failed to load workflow {workflow_id}: {e}")
        
        return None
    
    def list_workflows(self, include_templates: bool = True) -> List[AIWorkflow]:
        """列出所有工作流。"""
        workflows = []
        
        # 加载模板
        if include_templates:
            workflows.extend(self._templates)
        
        # 加载用户工作流
        for path in WORKFLOW_DATA_DIR.glob("*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                workflow = AIWorkflow(**data)
                # 排除模板（模板已单独加载）
                if not workflow.is_template:
                    workflows.append(workflow)
            except Exception as e:
                logger.warning(f"Failed to load workflow from {path}: {e}")
        
        # 按更新时间排序
        workflows.sort(key=lambda w: w.updated_at, reverse=True)
        
        return workflows
    
    def update_workflow(self, workflow_id: str, request: WorkflowUpdateRequest) -> Optional[AIWorkflow]:
        """更新工作流。"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None
        
        # 不允许更新模板
        if workflow.is_template:
            logger.warning(f"Cannot update template: {workflow_id}")
            return None
        
        # 更新字段
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(workflow, key, value)
        
        workflow.updated_at = datetime.now()
        
        # 保存
        self._save_workflow(workflow)
        logger.info(f"Updated workflow: {workflow_id}")
        
        return workflow
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流。"""
        # 不允许删除模板
        for template in self._templates:
            if template.id == workflow_id:
                logger.warning(f"Cannot delete template: {workflow_id}")
                return False
        
        path = self._get_workflow_path(workflow_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted workflow: {workflow_id}")
            return True
        
        return False
    
    def clone_from_template(self, template_id: str, new_name: str) -> Optional[AIWorkflow]:
        """从模板创建工作流副本。"""
        template = self.get_workflow(template_id)
        if not template:
            return None
        
        # 创建副本
        workflow = AIWorkflow(
            name=new_name,
            description=template.description,
            system_prompt=template.system_prompt,
            user_prompt_template=template.user_prompt_template,
            selected_tools=template.selected_tools.copy(),
            variables=[WorkflowVariable(**v.model_dump()) for v in template.variables],
            is_template=False,
            category=template.category,
            tags=template.tags.copy(),
        )
        
        self._save_workflow(workflow)
        logger.info(f"Cloned workflow from template {template_id}: {workflow.id}")
        
        return workflow
    
    def _save_workflow(self, workflow: AIWorkflow):
        """保存工作流到文件。"""
        path = self._get_workflow_path(workflow.id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(workflow.model_dump(), f, ensure_ascii=False, indent=2, default=str)
    
    # Tool Management
    
    def get_available_tools(self) -> List[ToolInfo]:
        """获取所有可用的MCP工具。"""
        tools = []
        
        try:
            from stock_datasource.services.mcp_server import create_mcp_server
            
            mcp_server, service_generators = create_mcp_server()
            
            # 从 service_generators 获取工具信息
            for prefix, generator in service_generators.items():
                mcp_tools = generator.generate_mcp_tools()
                
                for tool_def in mcp_tools:
                    tool_name = f"{prefix}_{tool_def['name']}"
                    tools.append(ToolInfo(
                        name=tool_name,
                        description=tool_def.get("description", ""),
                        parameters=tool_def.get("parameters", {}),
                        category=self._categorize_tool(prefix)
                    ))
            
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            # 返回一些默认工具
            tools = self._get_default_tools()
        
        return tools
    
    def _categorize_tool(self, prefix: str) -> str:
        """根据前缀分类工具。"""
        category_map = {
            "tushare_daily": "行情数据",
            "tushare_valuation": "估值数据",
            "tushare_financial": "财务数据",
            "tushare_index": "指数数据",
            "etf": "ETF数据",
        }
        return category_map.get(prefix, "其他")
    
    def _get_default_tools(self) -> List[ToolInfo]:
        """获取默认工具列表。"""
        return [
            ToolInfo(
                name="tushare_daily_get_latest_daily",
                description="获取股票最新日线行情数据",
                category="行情数据"
            ),
            ToolInfo(
                name="tushare_daily_get_daily_data",
                description="获取股票历史日线数据",
                category="行情数据"
            ),
            ToolInfo(
                name="tushare_valuation_get_latest_valuation",
                description="获取股票最新估值数据（PE、PB等）",
                category="估值数据"
            ),
        ]
    
    def get_templates(self) -> List[AIWorkflow]:
        """获取所有预置模板。"""
        return self._templates.copy()


# 单例
_workflow_service: Optional[WorkflowService] = None


def get_workflow_service() -> WorkflowService:
    """获取工作流服务单例。"""
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowService()
    return _workflow_service
