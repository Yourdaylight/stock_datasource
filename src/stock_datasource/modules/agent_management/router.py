"""Agent management API router."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..auth.dependencies import get_current_user
from stock_datasource.models.agent_config import (
    AgentConfigCreate,
    AgentConfigResponse,
    AgentConfigUpdate,
)
from stock_datasource.services.agent_config_service import get_agent_config_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[AgentConfigResponse])
async def list_agents(
    current_user: dict = Depends(get_current_user),
):
    """List all agents visible to the current user."""
    service = get_agent_config_service()
    return service.list_agents(user_id=current_user["id"])


@router.get("/runtimes/detect")
async def detect_runtimes(
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Auto-detect available runtimes on this machine."""
    import shutil
    import subprocess
    from pathlib import Path

    runtimes = []

    # 1. LangGraph (always available)
    runtimes.append({
        "id": "langgraph",
        "name": "LangGraph",
        "description": "本地LLM框架 + MCP工具调度",
        "status": "available",
        "command": "",
        "version": "内置",
        "default_working_dir": str(Path("/root/lzh/stock_datasource")),
    })

    # 2. Claude CLI
    claude_paths = [
        shutil.which("claude"),
        shutil.which("claude-internal"),
        "/root/.nvm/versions/node/v20.20.2/bin/claude-internal",
    ]
    for cp in claude_paths:
        if cp and Path(cp).exists():
            version = ""
            try:
                result = subprocess.run([cp, "--version"], capture_output=True, text=True, timeout=5)
                version = result.stdout.strip()[:50] if result.returncode == 0 else "detected"
            except Exception:
                version = "detected"
            runtimes.append({
                "id": "claude",
                "name": "Claude Code",
                "description": "Anthropic Claude CLI Agent",
                "status": "available",
                "command": cp,
                "version": version,
                "default_working_dir": str(Path("/root/lzh/stock_datasource")),
            })
            break

    # 3. CodeBuddy CLI
    codebuddy_paths = [
        shutil.which("codebuddy"),
        "/root/.nvm/versions/node/v20.20.2/bin/codebuddy",
    ]
    for cbp in codebuddy_paths:
        if cbp and Path(cbp).exists():
            runtimes.append({
                "id": "codebuddy",
                "name": "CodeBuddy",
                "description": "腾讯CodeBuddy AI编程助手",
                "status": "available",
                "command": cbp,
                "version": "detected",
                "default_working_dir": str(Path("/root/lzh/stock_datasource")),
            })
            break

    # If claude/codebuddy not found, still list them as "not_installed"
    ids_found = [r["id"] for r in runtimes]
    if "claude" not in ids_found:
        runtimes.append({
            "id": "claude",
            "name": "Claude Code",
            "description": "Anthropic Claude CLI（未检测到）",
            "status": "not_installed",
            "command": "",
            "version": "",
            "default_working_dir": "",
        })
    if "codebuddy" not in ids_found:
        runtimes.append({
            "id": "codebuddy",
            "name": "CodeBuddy",
            "description": "腾讯CodeBuddy（未检测到）",
            "status": "not_installed",
            "command": "",
            "version": "",
            "default_working_dir": "",
        })

    return runtimes


@router.post("/", response_model=AgentConfigResponse, status_code=201)
async def create_agent(
    data: AgentConfigCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new agent configuration."""
    service = get_agent_config_service()
    return service.create_agent(user_id=current_user["id"], data=data)


@router.get("/skills/catalog")
async def list_skills(
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all available skills/tools from the skill registry and MCP server."""
    catalog = []

    # Try to get tools from MCP server's tool manager
    try:
        from stock_datasource.services.mcp_server import create_mcp_server
        mcp_server, tool_map = create_mcp_server()
        for tool_name, tool_info in tool_map.items():
            catalog.append({
                "id": tool_name,
                "name": tool_name,
                "description": tool_info.get("description", "") if isinstance(tool_info, dict) else str(tool_info),
                "category": _infer_category(tool_name),
                "parameters_schema": {},
            })
    except Exception as e:
        logger.debug("MCP server tool loading skipped: %s", e)

    # Fallback: try SkillRegistry
    if not catalog:
        try:
            from stock_datasource.services.skill_registry import SkillRegistry
            registry = SkillRegistry()
            skills = registry.list_skills()
            for s in skills:
                catalog.append({
                    "id": s.name,
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "parameters_schema": {},
                })
        except Exception:
            pass

    # If still empty, provide some built-in skill names
    if not catalog:
        default_skills = [
            ("stock_daily_price", "获取股票日线行情", "行情数据"),
            ("stock_basic_info", "获取股票基本信息", "股票基础"),
            ("financial_indicator", "获取财务指标", "财务数据"),
            ("income_statement", "获取利润表", "财务数据"),
            ("balance_sheet", "获取资产负债表", "财务数据"),
            ("cashflow_statement", "获取现金流量表", "财务数据"),
            ("index_daily", "获取指数日线", "指数数据"),
            ("news_search", "搜索新闻", "新闻资讯"),
            ("stock_screen", "股票筛选", "选股工具"),
            ("technical_indicator", "计算技术指标", "行情数据"),
        ]
        for sid, desc, cat in default_skills:
            catalog.append({
                "id": sid,
                "name": sid,
                "description": desc,
                "category": cat,
                "parameters_schema": {},
            })

    return catalog


@router.get("/skills/user-skills")
async def list_user_skills(
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Scan ~/.claude/skills/ and ~/.codebuddy/skills/ for user skills."""
    import os
    import yaml
    from pathlib import Path

    skills = []
    scan_dirs = [
        (Path.home() / ".claude" / "skills", "claude"),
        (Path.home() / ".codebuddy" / "skills-marketplace" / "skills", "codebuddy"),
        (Path.home() / ".codebuddy" / "skills", "codebuddy"),
    ]

    for base_dir, source in scan_dirs:
        if not base_dir.exists():
            continue
        for skill_dir in base_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            # Parse frontmatter
            name = skill_dir.name
            description = ""
            metadata = {}
            try:
                content = skill_md.read_text(encoding="utf-8", errors="ignore")
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        try:
                            metadata = yaml.safe_load(parts[1]) or {}
                        except Exception:
                            pass
                        description = metadata.get("description", "")
                        if not description:
                            # Use first non-empty line after frontmatter
                            for line in parts[2].strip().split("\n"):
                                line = line.strip().lstrip("#").strip()
                                if line:
                                    description = line[:100]
                                    break
                name = metadata.get("name", skill_dir.name)
            except Exception:
                pass

            skills.append({
                "id": f"{source}:{skill_dir.name}",
                "name": name,
                "description": description,
                "source": source,
                "path": str(skill_dir),
                "emoji": metadata.get("metadata", {}).get("emoji", "") if isinstance(metadata.get("metadata"), dict) else "",
            })

    return skills


@router.get("/skills/project-skills")
async def list_project_skills(
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Scan project skills/ directory."""
    import yaml
    from pathlib import Path

    skills = []
    project_skills_dir = Path("/root/lzh/stock_datasource/skills")
    if not project_skills_dir.exists():
        return []

    for skill_dir in project_skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        name = skill_dir.name
        description = ""
        metadata = {}
        try:
            content = skill_md.read_text(encoding="utf-8", errors="ignore")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        metadata = yaml.safe_load(parts[1]) or {}
                    except Exception:
                        pass
                    description = metadata.get("description", "")
            if not description:
                for line in content.split("\n"):
                    line = line.strip().lstrip("#").strip()
                    if line and not line.startswith("---"):
                        description = line[:100]
                        break
            name = metadata.get("name", skill_dir.name)
        except Exception:
            pass

        skills.append({
            "id": f"project:{skill_dir.name}",
            "name": name,
            "description": description,
            "source": "project",
            "path": str(skill_dir),
        })

    return skills


@router.get("/{agent_id}", response_model=AgentConfigResponse)
async def get_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get agent details by ID."""
    service = get_agent_config_service()
    agent = service.get_agent(agent_id, user_id=current_user["id"])
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentConfigResponse)
async def update_agent(
    agent_id: str,
    data: AgentConfigUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update an agent configuration."""
    service = get_agent_config_service()
    result = service.update_agent(agent_id, user_id=current_user["id"], data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not found or no permission")
    return result


@router.get("/{agent_id}/history")
async def get_agent_history(
    agent_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get agent call history from chat messages."""
    try:
        from stock_datasource.models.database import db_client
        from stock_datasource.services.agent_config_service import get_agent_config_service

        # 先获取agent名称，用于在metadata里搜索
        service = get_agent_config_service()
        agent = service.get_agent(agent_id, user_id=current_user["id"])
        if not agent:
            return []

        # 用agent的中文名映射回代码里的agent class名
        NAME_TO_CODE = {
            "通用对话助手": "ChatAgent",
            "行情分析师": "MarketAgent",
            "选股专家": "ScreenerAgent",
            "财报分析师": "ReportAgent",
            "ETF分析师": "EtfAgent",
            "指数分析师": "IndexAgent",
            "新闻分析师": "NewsAnalystAgent",
            "价值投资专家": "ScreenerAgent",
            "技术面专家": "MarketAgent",
            "板块轮动分析师": "OverviewAgent",
        }
        code_name = NAME_TO_CODE.get(agent.name, agent.name)

        # 从chat_messages查包含此agent的assistant消息
        df = db_client.execute_query(f"""
            SELECT session_id, content, metadata, created_at
            FROM chat_messages
            WHERE user_id = '{current_user["id"]}'
              AND role = 'assistant'
              AND metadata LIKE '%"{code_name}"%'
            ORDER BY created_at DESC
            LIMIT {limit}
        """)
        if df.empty:
            return []

        import json
        records = []
        for _, row in df.iterrows():
            meta = {}
            try:
                meta = json.loads(str(row.get("metadata", "{}")))
            except Exception:
                pass
            content = str(row.get("content", ""))
            records.append({
                "time": str(row.get("created_at", "")),
                "input": content[:100] + ("..." if len(content) > 100 else ""),
                "success": True,
                "duration": 0,
                "session_id": str(row.get("session_id", "")),
                "agent": meta.get("agent", ""),
                "tools_used": meta.get("tool_calls", []),
            })
        return records
    except Exception as e:
        logger.warning("Failed to get agent history: %s", e)
        return []


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete an agent."""
    service = get_agent_config_service()
    success = service.delete_agent(agent_id, user_id=current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found or no permission")
    return {"status": "ok", "message": "Agent deleted"}


@router.post("/{agent_id}/test")
async def test_agent(
    agent_id: str,
    message: str = Query(..., description="Test message to send to the agent"),
    current_user: dict = Depends(get_current_user),
):
    """Quick test: send a message to an agent and get streaming response."""
    service = get_agent_config_service()
    agent = service.get_agent(agent_id, user_id=current_user["id"])
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    async def generate():
        try:
            from stock_datasource.llm import get_llm_client

            client = get_llm_client()
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": message},
            ]
            # Use streaming if available, otherwise single call
            try:
                async for chunk in client.stream(
                    messages=messages,
                    temperature=agent.model_config_data.temperature,
                    max_tokens=agent.model_config_data.max_tokens,
                ):
                    if isinstance(chunk, dict):
                        content = chunk.get("content", "")
                    else:
                        content = str(chunk)
                    if content:
                        yield f"data: {content}\n\n"
            except (AttributeError, TypeError):
                # Fallback to non-streaming
                response = await client.chat(
                    messages=messages,
                    temperature=agent.model_config_data.temperature,
                    max_tokens=agent.model_config_data.max_tokens,
                )
                content = response.get("content", str(response)) if isinstance(response, dict) else str(response)
                yield f"data: {content}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _infer_category(tool_name: str) -> str:
    """Infer tool category from name prefix."""
    prefixes = {
        "tushare_daily": "行情数据",
        "tushare_index": "指数数据",
        "tushare_fund": "基金数据",
        "tushare_fina": "财务数据",
        "tushare_valuation": "估值数据",
        "tushare_income": "财务数据",
        "tushare_balance": "财务数据",
        "tushare_cashflow": "财务数据",
        "tushare_stock": "股票基础",
        "tushare_news": "新闻资讯",
        "tushare_top": "龙虎榜",
        "news_": "新闻资讯",
        "screen_": "选股工具",
        "market_": "行情数据",
        "portfolio_": "持仓工具",
    }
    for prefix, category in prefixes.items():
        if tool_name.startswith(prefix):
            return category
    return "其他工具"
