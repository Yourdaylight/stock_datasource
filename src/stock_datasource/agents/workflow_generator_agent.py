"""工作流生成Agent。

根据用户的自然语言描述自动生成AI工作流配置。
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, AsyncGenerator

from .base_agent import LangGraphAgent, AgentConfig
from stock_datasource.models.workflow import AIWorkflow, WorkflowVariable, ToolInfo

logger = logging.getLogger(__name__)


class WorkflowGeneratorAgent(LangGraphAgent):
    """AI工作流生成器。
    
    根据用户描述的分析策略或交易方式，自动生成工作流配置。
    """
    
    def __init__(self):
        """初始化工作流生成Agent。"""
        config = AgentConfig(
            name="workflow_generator",
            description="根据用户描述生成AI工作流配置",
            recursion_limit=20,
        )
        super().__init__(config)
        self._available_tools: Optional[List[ToolInfo]] = None
    
    def get_tools(self) -> List:
        """生成器不需要工具，直接生成配置。"""
        return []
    
    def set_available_tools(self, tools: List[ToolInfo]):
        """设置可用工具列表。"""
        self._available_tools = tools
    
    def _format_tools_description(self) -> str:
        """格式化工具列表描述。"""
        if not self._available_tools:
            return "暂无可用工具信息"
        
        lines = []
        # 按分类分组
        categories: Dict[str, List[ToolInfo]] = {}
        for tool in self._available_tools:
            cat = tool.category or "其他"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tool)
        
        for cat, tools in categories.items():
            lines.append(f"\n### {cat}")
            for tool in tools:
                lines.append(f"- **{tool.name}**: {tool.description}")
        
        return "\n".join(lines)
    
    def get_system_prompt(self) -> str:
        """获取系统提示词。"""
        tools_desc = self._format_tools_description()
        
        return f"""你是一个AI工作流配置生成器。用户会描述他们想要的股票分析策略或交易方式，
你需要根据描述生成合适的工作流配置。

## 可用的MCP工具
{tools_desc}

## 输出格式
你必须生成以下JSON格式的工作流配置（用```json和```包裹）：

```json
{{
    "name": "工作流名称（简洁明了）",
    "description": "工作流描述（一句话说明用途）",
    "system_prompt": "系统提示词（定义AI角色和分析方法，150-300字）",
    "user_prompt_template": "用户提示词模板（使用{{{{变量名}}}}表示变量）",
    "selected_tools": ["工具1", "工具2"],
    "variables": [
        {{"name": "变量名", "label": "显示标签", "type": "类型", "required": true, "default": "默认值", "description": "说明"}}
    ],
    "category": "分类",
    "tags": ["标签1", "标签2"]
}}
```

## 变量类型
- string: 普通文本
- number: 数字
- date: 日期 (YYYYMMDD格式)
- stock_code: 股票代码 (如 600519.SH)
- stock_list: 多个股票代码 (逗号分隔)

## 分类选项
- analysis: 个股分析
- comparison: 对比分析
- screening: 条件筛选
- technical: 技术分析
- sector: 板块分析
- custom: 自定义

## 生成原则
1. **工具选择**：根据用户描述选择最相关的工具，通常2-4个工具即可
2. **系统提示词**：清晰定义AI的分析角色、分析框架和输出要求
3. **用户提示词模板**：包含具体的分析任务，使用变量占位符
4. **变量设计**：提取用户需要输入的参数，设置合理的默认值
5. **专业性**：为投资分析场景提供专业的分析框架

## 常见策略类型对应的工具组合
- 价值投资：估值数据(valuation) + 财务数据(financial)
- 技术分析：日线数据(daily) + 历史数据
- 行业对比：日线数据 + 估值数据
- 趋势跟踪：日线数据

请直接输出JSON配置，不要有多余的解释。"""
    
    async def generate_workflow(
        self, 
        description: str,
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """根据用户描述生成工作流配置（流式）。
        
        Args:
            description: 用户描述的分析策略或交易方式
            context: 执行上下文
            
        Yields:
            生成事件
        """
        context = context or {}
        
        # 构建生成请求
        user_message = f"""请根据以下需求生成AI工作流配置：

{description}

请生成完整的工作流JSON配置。"""
        
        full_response = ""
        
        # 使用父类的流式执行
        async for event in self.execute_stream(user_message, context):
            event_type = event.get("type", "")
            
            if event_type == "thinking":
                yield {
                    "type": "thinking",
                    "content": event.get("status", "思考中...")
                }
            
            elif event_type == "content":
                content = event.get("content", "")
                full_response += content
                yield {
                    "type": "generating",
                    "content": content
                }
            
            elif event_type == "done":
                # 解析生成的配置
                try:
                    workflow_config = self._parse_workflow_config(full_response)
                    if workflow_config:
                        yield {
                            "type": "workflow",
                            "workflow": workflow_config
                        }
                    else:
                        yield {
                            "type": "error",
                            "error": "无法解析生成的工作流配置"
                        }
                except Exception as e:
                    logger.error(f"Failed to parse workflow config: {e}")
                    yield {
                        "type": "error",
                        "error": f"解析配置失败: {str(e)}"
                    }
                
                yield {"type": "done"}
            
            elif event_type == "error":
                yield event
    
    def _parse_workflow_config(self, response: str) -> Optional[Dict[str, Any]]:
        """解析AI生成的工作流配置。"""
        # 尝试从Markdown代码块中提取JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析整个响应
            json_str = response
        
        try:
            # 清理可能的问题
            json_str = json_str.strip()
            
            # 解析JSON
            config = json.loads(json_str)
            
            # 验证必需字段
            required_fields = ['name', 'system_prompt', 'user_prompt_template', 'selected_tools']
            for field in required_fields:
                if field not in config:
                    logger.warning(f"Missing required field: {field}")
                    config[field] = "" if field != "selected_tools" else []
            
            # 处理variables字段
            if 'variables' in config:
                variables = []
                for var in config['variables']:
                    variables.append({
                        'name': var.get('name', ''),
                        'label': var.get('label', var.get('name', '')),
                        'type': var.get('type', 'string'),
                        'required': var.get('required', True),
                        'default': var.get('default'),
                        'description': var.get('description')
                    })
                config['variables'] = variables
            else:
                config['variables'] = []
            
            # 设置默认值
            config.setdefault('description', '')
            config.setdefault('category', 'custom')
            config.setdefault('tags', [])
            config.setdefault('is_template', False)
            
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.debug(f"Raw response: {json_str[:500]}")
            return None


# 单例
_generator_agent: Optional[WorkflowGeneratorAgent] = None


def get_workflow_generator() -> WorkflowGeneratorAgent:
    """获取工作流生成器单例。"""
    global _generator_agent
    if _generator_agent is None:
        _generator_agent = WorkflowGeneratorAgent()
    return _generator_agent
