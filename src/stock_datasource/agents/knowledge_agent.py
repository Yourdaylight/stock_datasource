"""Knowledge Base Agent — RAG-enhanced analysis via WeKnora.

This agent is only instantiated when WEKNORA_ENABLED=true and the WeKnora
service is reachable. It provides two tools:
  - search_knowledge: Semantic search across configured knowledge bases
  - list_knowledge_bases: List available knowledge bases

The agent generates answers with source citations based on retrieved chunks.
"""

import json
import logging
from typing import List, Callable, Optional

from .base_agent import LangGraphAgent, AgentConfig
from stock_datasource.services.weknora_client import get_weknora_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
KNOWLEDGE_SYSTEM_PROMPT = """你是一个知识库检索与问答专家。你可以通过知识库检索相关文档片段，基于检索结果为用户提供有据可依的回答。

## 你的工作流程

1. 理解用户问题，调用 `search_knowledge` 工具检索知识库
2. 分析检索结果，筛选最相关的内容
3. 基于检索结果生成完整、有条理的回答

## 回答规范

### 必须遵守：
- **引用来源**: 在回答中引用文档来源，格式: `[来源: 文件名]`
- **忠实原文**: 严格基于检索结果回答，不捏造检索结果中不存在的内容
- **明确告知**: 如果检索结果为空或不相关，明确告知用户"知识库中未找到相关信息"
- **结构化输出**: 使用 Markdown 格式，合理使用标题、列表、引用等

### 回答模板（检索到内容时）：

**关于 [问题主题] 的分析**

根据知识库中的相关文档：

1. **[要点一]**
   - 具体内容... [来源: xxx.pdf]

2. **[要点二]**
   - 具体内容... [来源: yyy.docx]

**综合总结**: ...

### 回答模板（未检索到内容时）：

知识库中未找到与"[用户问题]"相关的信息。建议：
- 检查知识库中是否已上传相关文档
- 尝试使用不同的关键词进行检索
- 通过 WeKnora Web UI 上传需要的文档

## 注意事项
- 你只负责基于知识库文档的检索问答
- 如果用户询问实时行情或技术分析，告知需要使用行情分析功能
- 每次回答结尾标注引用的来源文件列表
"""


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------
def search_knowledge(query: str) -> dict:
    """在知识库中搜索与查询相关的文档片段。

    Args:
        query: 搜索关键词或问题，例如"贵州茅台2024年年报营收数据"

    Returns:
        检索结果列表，包含文档片段、来源、相关性评分
    """
    client = get_weknora_client()
    if client is None:
        return {
            "results": [],
            "total": 0,
            "query": query,
            "error": "知识库服务未配置",
        }

    results = client.knowledge_search(query)

    formatted = []
    for item in results:
        formatted.append({
            "content": item.get("content", ""),
            "source": item.get("knowledge_filename") or item.get("knowledge_title") or "未知来源",
            "score": item.get("score", 0),
            "chunk_type": item.get("chunk_type", "text"),
        })

    return {
        "results": formatted,
        "total": len(formatted),
        "query": query,
        "_hint": "请基于以上知识库检索结果回答用户问题，引用时标注来源文件名。",
    }


def list_knowledge_bases() -> dict:
    """列出所有可用的知识库。

    Returns:
        知识库列表，包含名称、描述、文档数量等信息
    """
    client = get_weknora_client()
    if client is None:
        return {
            "knowledge_bases": [],
            "total": 0,
            "error": "知识库服务未配置",
        }

    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            kbs = pool.submit(asyncio.run, client.list_knowledge_bases()).result()
    else:
        kbs = asyncio.run(client.list_knowledge_bases())

    formatted = []
    for kb in kbs:
        formatted.append({
            "id": kb.get("id", ""),
            "name": kb.get("name", ""),
            "description": kb.get("description", ""),
        })

    return {
        "knowledge_bases": formatted,
        "total": len(formatted),
    }


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------
class KnowledgeAgent(LangGraphAgent):
    """Knowledge base retrieval agent using WeKnora."""

    def __init__(self):
        config = AgentConfig(
            name="KnowledgeAgent",
            description="负责知识库文档检索与问答，可搜索研报、公告、财报、政策文档等，提供有据可依的分析回答",
            temperature=0.3,
            max_tokens=4000,
        )
        super().__init__(config)

    def get_tools(self) -> List[Callable]:
        return [search_knowledge, list_knowledge_bases]

    def get_system_prompt(self) -> str:
        return KNOWLEDGE_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Singleton factory (conditional)
# ---------------------------------------------------------------------------
_knowledge_agent: Optional[KnowledgeAgent] = None


def get_knowledge_agent() -> Optional[KnowledgeAgent]:
    """Get the KnowledgeAgent singleton.

    Returns None if WeKnora is not configured.
    """
    global _knowledge_agent
    if _knowledge_agent is not None:
        return _knowledge_agent

    client = get_weknora_client()
    if client is None:
        return None

    _knowledge_agent = KnowledgeAgent()
    logger.info("[KnowledgeAgent] Initialized with WeKnora integration")
    return _knowledge_agent
