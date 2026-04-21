"""Akinator service: LLM-driven question generation + predicate filtering."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
import uuid
from typing import Any

from stock_datasource.models.database import db_client
from stock_datasource.services.cache_service import get_cache_service

from .attributes import get_stock_matrix
from .schemas import Predicate, QAEntry, QuestionDTO, StockDTO

logger = logging.getLogger(__name__)

# Session config
SESSION_TTL_SECONDS = 30 * 60  # 30 min
MAX_QUESTIONS = 12
FINISH_THRESHOLD = 10  # show candidates when <= this many
SAMPLE_SIZE_FOR_LLM = 20  # how many candidates to show LLM when set is large


# ---------------------------------------------------------------------------
# LLM Prompt
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """你是"猜股票"游戏的主持人。用户心里想了一只 A 股股票，你要通过 yes/no 问题逐步锁定。

## 规则
1. 每轮选一个**能把当前候选集切得最均衡的问题**（理想 40%-60% 切分）
2. 问题必须是中文口语化的 yes/no 形式
3. 必须能在股票属性上可验证，避免主观问题
4. 不能重复已问的维度

## 可用字段
- `industry` (行业): 银行/医药/白酒/半导体/...
- `market` (板块): 主板/科创板/创业板
- `area` / `province` (地域)
- `list_date` (上市日期 YYYY-MM-DD)
- `total_mv` (总市值, 万元, 如 5000000000 = 5000亿)
- `pe_ttm` / `pb` / `dv_ratio` (估值)
- `roe` / `net_profit_margin` / `gross_profit_margin` / `debt_to_assets`
- `in_hs300` / `in_sz50` / `in_zz500` (bool, 指数成分)
- `concepts` (概念板块列表, 如 ["人工智能","白酒","新能源车"])
- `main_business` (主营业务文本)
- `name` (股票名称)

## 可用操作
- `contains`: 字段包含某关键词（`concepts` 列表元素匹配也用这个）
- `equals`: 精确等于
- `startswith`: 字符串前缀（可用于 ts_code "688" = 科创板）
- `in_list`: 值在给定列表中
- `gt`/`lt`/`gte`/`lte`: 数值比较

## 输出格式（⚠️ 严格两段式，缺一不可！）

**第一段：`<think>...</think>` 思考过程（必填，至少 80 字中文）**
要逐步、口语化地展开：
1. 现在候选集是什么样？（看关键分布数字）
2. 哪些维度能切出 50/50？列出 2-3 个候选
3. 每个候选切分的均衡度评估
4. 最终选哪个、为什么？

**第二段：紧跟 JSON，不要代码块：**
{{"question":"中文yes/no问题","predicate":{{"field":"...","op":"...","value":"..."}},"reasoning":"一句话说明"}}

## 示例（必须像这样输出两段）：
<think>
当前候选 2800 只。看分布：新能源概念占 420 只 (15%)，医药 380 (14%)，行业太碎。
试几个切分维度：
- 江浙沪地域：样本中 8/20 来自江浙沪，估算约 40-45%，挺均衡；
- 市值 > 100亿：样本有 11/20，约 55%，也不错；
- 沪深300：只有 7%，太偏了。
江浙沪更均衡，而且还没问过地域维度，选它。
</think>
{{"question":"这只股票的公司在江浙沪（上海、江苏、浙江）吗？","predicate":{{"field":"area","op":"in_list","value":["上海","江苏","浙江"]}},"reasoning":"江浙沪约占40-45%，切分均衡，地域维度尚未使用"}}

## 当前候选集信息
候选总数: {n_candidates}
{distribution_summary}

候选样本 ({sample_size} 只):
{candidates_sample}

## 已问过的问题
{history}
"""

FALLBACK_PROMPT_SUFFIX = """

## 重要提示
你上一轮给出的问题导致候选集被清空（所有股票都不满足/都满足）。请选择一个**更平衡**的切分维度，避免过于严格的条件。"""


# ---------------------------------------------------------------------------
# Candidate compression for LLM
# ---------------------------------------------------------------------------


def _num(v) -> float | None:
    """Coerce ClickHouse value (may be Decimal/str/None) to float."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _compress_for_llm(stock: dict) -> dict:
    """Extract a subset of fields for LLM context."""
    mv = _num(stock.get("total_mv"))
    pe = _num(stock.get("pe_ttm"))
    roe = _num(stock.get("roe"))
    return {
        "ts_code": stock.get("ts_code"),
        "name": stock.get("name"),
        "industry": stock.get("industry"),
        "market": stock.get("market"),
        "area": stock.get("area"),
        "total_mv_yi": round(mv / 10000, 1) if mv else None,  # 亿元
        "pe_ttm": round(pe, 1) if pe else None,
        "roe": round(roe, 1) if roe else None,
        "in_hs300": stock.get("in_hs300"),
        "concepts": (stock.get("concepts") or [])[:6],  # top 6 concepts
    }


def _distribution_summary(candidates: list[dict]) -> str:
    """Compute a textual summary of key field distributions."""
    if not candidates:
        return ""

    lines = []
    # Industry top 10
    from collections import Counter

    industries = Counter(c.get("industry") for c in candidates if c.get("industry"))
    top_inds = industries.most_common(10)
    if top_inds:
        ind_str = ", ".join(f"{ind}({cnt})" for ind, cnt in top_inds)
        lines.append(f"行业分布 (top10): {ind_str}")

    # Market distribution
    markets = Counter(c.get("market") for c in candidates if c.get("market"))
    if markets:
        mkt_str = ", ".join(f"{m}({c})" for m, c in markets.most_common())
        lines.append(f"板块分布: {mkt_str}")

    # Index membership
    hs300 = sum(1 for c in candidates if c.get("in_hs300"))
    sz50 = sum(1 for c in candidates if c.get("in_sz50"))
    zz500 = sum(1 for c in candidates if c.get("in_zz500"))
    lines.append(f"指数: 沪深300 {hs300}, 上证50 {sz50}, 中证500 {zz500}")

    # Market cap tiers
    large = sum(1 for c in candidates if (_num(c.get("total_mv")) or 0) >= 5_000_000 * 10000)  # >= 5000亿
    mid = sum(1 for c in candidates if 1_000_000 * 10000 <= (_num(c.get("total_mv")) or 0) < 5_000_000 * 10000)
    small = sum(1 for c in candidates if 0 < (_num(c.get("total_mv")) or 0) < 1_000_000 * 10000)
    lines.append(f"市值: 大盘(>5000亿) {large}, 中盘(1000-5000亿) {mid}, 小盘(<1000亿) {small}")

    # Top concepts
    all_concepts: Counter = Counter()
    for c in candidates:
        for concept in c.get("concepts") or []:
            all_concepts[concept] += 1
    top_concepts = all_concepts.most_common(15)
    if top_concepts:
        cpt_str = ", ".join(f"{c}({cnt})" for c, cnt in top_concepts)
        lines.append(f"概念分布 (top15): {cpt_str}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Predicate evaluation (pure Python, no LLM)
# ---------------------------------------------------------------------------


def _matches(stock: dict, predicate: Predicate | dict) -> bool:
    """Evaluate a predicate against a stock dict."""
    if isinstance(predicate, Predicate):
        field, op, value = predicate.field, predicate.op, predicate.value
    else:
        field, op, value = predicate["field"], predicate["op"], predicate["value"]

    v = stock.get(field)
    if v is None:
        return False

    try:
        if op == "contains":
            if isinstance(v, list):
                return any(str(value) in str(x) for x in v)
            return str(value) in str(v)
        if op == "equals":
            return v == value
        if op == "in_list":
            if not isinstance(value, list):
                return False
            return v in value
        if op == "startswith":
            return str(v).startswith(str(value))
        if op == "endswith":
            return str(v).endswith(str(value))
        if op in ("gt", "lt", "gte", "lte"):
            v_num = float(v)
            val_num = float(value)
            return {
                "gt": v_num > val_num,
                "lt": v_num < val_num,
                "gte": v_num >= val_num,
                "lte": v_num <= val_num,
            }[op]
    except Exception as e:
        logger.debug(f"Predicate eval failed: {e} (field={field}, value={value})")
        return False

    return False


def apply_predicate(
    candidates: list[dict],
    predicate: Predicate | dict,
    answer: str,
) -> list[dict]:
    """Filter candidates by predicate + user's yes/no answer."""
    if answer == "unknown":
        return candidates
    want_yes = answer == "yes"
    return [s for s in candidates if _matches(s, predicate) == want_yes]


# ---------------------------------------------------------------------------
# LLM question generation
# ---------------------------------------------------------------------------


def _strip_think(content: str) -> tuple[str, str]:
    """Split LLM content into (think_text, remainder).

    `<think>...</think>` 之外的内容是 JSON 部分。
    """
    m = re.search(r"<think>(.*?)</think>", content, re.DOTALL | re.IGNORECASE)
    if not m:
        return "", content
    think = m.group(1).strip()
    remainder = (content[: m.start()] + content[m.end():]).strip()
    return think, remainder


def _parse_llm_json(content: str) -> dict | None:
    """Parse JSON from LLM output, tolerant of markdown code blocks and <think>."""
    _, text = _strip_think(content)
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)

    # Try to find the first JSON object
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Find outermost {...}
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


async def _invoke_llm(messages: list, user_id: str, session_id: str) -> tuple[str, int]:
    """Call LLM and deduct tokens.

    Returns: (content, total_tokens_used)
    """
    from stock_datasource.agents.base_agent import get_langchain_model
    from stock_datasource.modules.token_usage.service import TokenUsageService

    model = get_langchain_model()
    # Hard cap: abort LLM call if it exceeds 45s so the user is never stuck.
    # The heuristic fallback will then kick in.
    LLM_CALL_TIMEOUT = 45.0

    async def _call():
        if hasattr(model, "ainvoke"):
            return await model.ainvoke(messages)
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.invoke(messages)
        )

    response = await asyncio.wait_for(_call(), timeout=LLM_CALL_TIMEOUT)

    content = response.content if hasattr(response, "content") else str(response)

    # Deduct tokens
    usage = getattr(response, "response_metadata", {}).get("usage", {}) or {}
    if not usage:
        # Some LangChain versions use usage_metadata
        usage_meta = getattr(response, "usage_metadata", None)
        if usage_meta:
            usage = {
                "prompt_tokens": usage_meta.get("input_tokens", 0),
                "completion_tokens": usage_meta.get("output_tokens", 0),
                "total_tokens": usage_meta.get("total_tokens", 0),
            }

    total = int(usage.get("total_tokens", 0))
    try:
        await TokenUsageService.deduct_tokens(
            user_id=user_id,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=total,
            session_id=session_id,
            agent_name="AkinatorAgent",
            model_name=getattr(response, "model", ""),
        )
    except Exception as e:
        logger.warning(f"Token deduct failed: {e}")

    return content, total


async def _stream_llm(messages: list, user_id: str, session_id: str):
    """Stream LLM output token-by-token, deduct tokens at end.

    Yields str chunks. Final yield's accumulated content can be captured by caller.
    Caller should wrap the call with asyncio.wait_for for hard timeout.
    """
    from stock_datasource.agents.base_agent import get_langchain_model
    from stock_datasource.modules.token_usage.service import TokenUsageService

    model = get_langchain_model()

    if not hasattr(model, "astream"):
        # Fallback: non-streaming, yield whole content at once
        content, _tokens = await _invoke_llm(messages, user_id, session_id)
        yield content
        return

    accumulated = ""
    last_chunk = None
    async for chunk in model.astream(messages):
        piece = getattr(chunk, "content", "") or ""
        if piece:
            accumulated += piece
            yield piece
        last_chunk = chunk

    # Deduct tokens from last chunk metadata (if available)
    try:
        usage = {}
        if last_chunk is not None:
            meta = getattr(last_chunk, "response_metadata", {}) or {}
            usage = meta.get("usage", {}) or {}
            if not usage:
                usage_meta = getattr(last_chunk, "usage_metadata", None)
                if usage_meta:
                    usage = {
                        "prompt_tokens": usage_meta.get("input_tokens", 0),
                        "completion_tokens": usage_meta.get("output_tokens", 0),
                        "total_tokens": usage_meta.get("total_tokens", 0),
                    }
        if usage:
            await TokenUsageService.deduct_tokens(
                user_id=user_id,
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
                session_id=session_id,
                agent_name="AkinatorAgent",
                model_name="",
            )
    except Exception as e:
        logger.warning(f"Stream token deduct failed: {e}")


def _build_prompt(
    candidates: list[dict],
    history: list[QAEntry],
    with_fallback_hint: bool = False,
) -> str:
    n = len(candidates)
    if n > SAMPLE_SIZE_FOR_LLM:
        sample = random.sample(candidates, SAMPLE_SIZE_FOR_LLM)
    else:
        sample = candidates

    sample_compressed = [_compress_for_llm(s) for s in sample]
    history_json = [
        {"q": h.question, "a": h.answer, "predicate": h.predicate.model_dump()}
        for h in history
    ]

    prompt = SYSTEM_PROMPT.format(
        n_candidates=n,
        distribution_summary=_distribution_summary(candidates),
        sample_size=len(sample_compressed),
        candidates_sample=json.dumps(sample_compressed, ensure_ascii=False, indent=2),
        history=json.dumps(history_json, ensure_ascii=False, indent=2) if history else "（无）",
    )
    if with_fallback_hint:
        prompt += FALLBACK_PROMPT_SUFFIX
    return prompt


def _heuristic_fallback_question(candidates: list[dict], asked_fields: set[str]) -> QuestionDTO:
    """Fallback when LLM fails — pick the most common industry not yet asked."""
    from collections import Counter

    # Try industry split
    if "industry" not in asked_fields:
        industries = Counter(c.get("industry") for c in candidates if c.get("industry"))
        if industries:
            top_ind, cnt = industries.most_common(1)[0]
            if 0 < cnt < len(candidates):
                return QuestionDTO(
                    question=f"这只股票属于{top_ind}行业吗？",
                    predicate=Predicate(field="industry", op="equals", value=top_ind),
                    reasoning=f"启发式兜底：{top_ind}行业占 {cnt}/{len(candidates)} 只",
                )

    # Try index membership
    if "in_hs300" not in asked_fields:
        in_hs300 = sum(1 for c in candidates if c.get("in_hs300"))
        if 0 < in_hs300 < len(candidates):
            return QuestionDTO(
                question="这只股票是沪深300成分股吗？",
                predicate=Predicate(field="in_hs300", op="equals", value=True),
                reasoning="启发式兜底：沪深300 切分",
            )

    # Market cap
    if "total_mv" not in asked_fields:
        large = sum(
            1 for c in candidates if (_num(c.get("total_mv")) or 0) >= 1_000_000 * 10000
        )
        if 0 < large < len(candidates):
            return QuestionDTO(
                question="这只股票的市值超过1000亿吗？",
                predicate=Predicate(field="total_mv", op="gte", value=1_000_000 * 10000),
                reasoning="启发式兜底：市值切分",
            )

    # Last resort: ask about market (主板/创业板/科创板)
    from collections import Counter

    markets = Counter(c.get("market") for c in candidates if c.get("market"))
    if markets and "market" not in asked_fields:
        top_market, _ = markets.most_common(1)[0]
        return QuestionDTO(
            question=f"这只股票是{top_market}吗？",
            predicate=Predicate(field="market", op="equals", value=top_market),
            reasoning=f"启发式兜底：板块切分",
        )

    # Truly nothing useful
    return QuestionDTO(
        question="这只股票是银行股吗？",
        predicate=Predicate(field="industry", op="contains", value="银行"),
        reasoning="兜底默认问题",
    )


# ---------------------------------------------------------------------------
# Pre-LLM heuristic: balanced split across well-known coarse dimensions
# ---------------------------------------------------------------------------

# Threshold: 候选集大于此值时，优先用启发式（快、省 token）
LLM_CANDIDATE_THRESHOLD = 300
# 前 N 轮问题不调 LLM（交易所/板块/市值这类粗切分，启发式完全够用）
HEURISTIC_FIRST_N_ROUNDS = 4


def _balance_score(yes_count: int, total: int) -> float:
    """越接近 50/50 越高（1.0），极端切分低。"""
    if total == 0 or yes_count == 0 or yes_count == total:
        return 0.0
    ratio = yes_count / total
    return 1.0 - abs(ratio - 0.5) * 2  # 0.5 → 1.0, 0 或 1 → 0


def _heuristic_balanced_question(
    candidates: list[dict], asked_predicates: set[tuple]
) -> QuestionDTO | None:
    """从已知粗切分维度中挑选最接近 50/50 的问题（不调 LLM）。

    候选维度：交易所/创业板/科创板/沪深300/中证500/市值档位/上市年限/江浙沪/ROE/行业。
    只在至少一个维度能取得较均衡切分（balance>=0.3）时返回；否则返回 None 让 LLM 决策。

    `asked_predicates` 是 `(field, op, json_value)` 的集合，按照具体谓词级去重（而不是只按字段名）。
    """
    total = len(candidates)
    if total == 0:
        return None

    def not_asked(field: str, op: str, value) -> bool:
        key = (field, op, json.dumps(value, sort_keys=True, default=str))
        return key not in asked_predicates

    def count(pred_fn) -> int:
        return sum(1 for c in candidates if pred_fn(c))

    candidate_questions: list[tuple[float, QuestionDTO]] = []

    # 交易所
    if not_asked("ts_code", "endswith", ".SH"):
        yes = count(lambda c: (c.get("ts_code") or "").endswith(".SH"))
        s = _balance_score(yes, total)
        if s >= 0.3:
            candidate_questions.append((s, QuestionDTO(
                question="这只股票是在上海证券交易所上市的吗？",
                predicate=Predicate(field="ts_code", op="endswith", value=".SH"),
                reasoning=f"启发式：沪市占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 创业板（300 开头）
    if not_asked("ts_code", "startswith", "300"):
        yes = count(lambda c: (c.get("ts_code") or "").startswith("300"))
        s = _balance_score(yes, total)
        if s >= 0.3:
            candidate_questions.append((s, QuestionDTO(
                question="这只股票是创业板股票（代码以 300 开头）吗？",
                predicate=Predicate(field="ts_code", op="startswith", value="300"),
                reasoning=f"启发式：创业板占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 科创板（688 开头）
    if not_asked("ts_code", "startswith", "688"):
        yes = count(lambda c: (c.get("ts_code") or "").startswith("688"))
        s = _balance_score(yes, total)
        if s >= 0.25:
            candidate_questions.append((s, QuestionDTO(
                question="这只股票是科创板股票（代码以 688 开头）吗？",
                predicate=Predicate(field="ts_code", op="startswith", value="688"),
                reasoning=f"启发式：科创板占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 沪深300
    if not_asked("in_hs300", "equals", True):
        yes = count(lambda c: bool(c.get("in_hs300")))
        s = _balance_score(yes, total)
        if s >= 0.3:
            candidate_questions.append((s, QuestionDTO(
                question="这只股票是沪深300成分股吗？",
                predicate=Predicate(field="in_hs300", op="equals", value=True),
                reasoning=f"启发式：沪深300 占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 市值 > N 亿（遍历多档位，每个可用档位都加进候选）
    for yi, label in [(50, "50亿"), (100, "100亿"), (200, "200亿"), (500, "500亿"), (1000, "1000亿")]:
        threshold = yi * 10000  # 转 万元
        if not not_asked("total_mv", "gte", threshold):
            continue
        yes = count(lambda c, t=threshold: (_num(c.get("total_mv")) or 0) >= t)
        s = _balance_score(yes, total)
        if s >= 0.3:
            candidate_questions.append((s, QuestionDTO(
                question=f"这只股票的总市值超过{label}吗？",
                predicate=Predicate(field="total_mv", op="gte", value=threshold),
                reasoning=f"启发式：市值>{label} 占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 中证500
    if not_asked("in_zz500", "equals", True):
        yes = count(lambda c: bool(c.get("in_zz500")))
        s = _balance_score(yes, total)
        if s >= 0.3:
            candidate_questions.append((s, QuestionDTO(
                question="这只股票是中证500成分股吗？",
                predicate=Predicate(field="in_zz500", op="equals", value=True),
                reasoning=f"启发式：中证500 占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 上市年限（2015-01-01 为界，约 10 年）
    if not_asked("list_date", "lt", "2015-01-01"):
        yes = count(lambda c: (c.get("list_date") or "") < "2015-01-01")
        s = _balance_score(yes, total)
        if s >= 0.3:
            candidate_questions.append((s, QuestionDTO(
                question="这只股票是2015年前上市的（上市超过10年）吗？",
                predicate=Predicate(field="list_date", op="lt", value="2015-01-01"),
                reasoning=f"启发式：老股(>10年) 占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 地域：江浙沪
    if not_asked("area", "in_list", ["上海", "江苏", "浙江"]):
        yes = count(lambda c: (c.get("area") or "") in {"上海", "江苏", "浙江"})
        s = _balance_score(yes, total)
        if s >= 0.3:
            candidate_questions.append((s, QuestionDTO(
                question="这只股票的公司位于江浙沪（上海、江苏、浙江）吗？",
                predicate=Predicate(field="area", op="in_list", value=["上海", "江苏", "浙江"]),
                reasoning=f"启发式：江浙沪 占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 盈利能力：ROE > 10%
    if not_asked("roe", "gte", 10):
        yes = count(lambda c: (_num(c.get("roe")) or 0) >= 10)
        s = _balance_score(yes, total)
        if s >= 0.3:
            candidate_questions.append((s, QuestionDTO(
                question="这只股票的 ROE（净资产收益率）超过10%吗？",
                predicate=Predicate(field="roe", op="gte", value=10),
                reasoning=f"启发式：ROE>10% 占 {yes}/{total} (均衡度 {s:.2f})",
            )))

    # 行业 top-1
    from collections import Counter as _C
    inds = _C(c.get("industry") for c in candidates if c.get("industry"))
    if inds:
        top_ind, cnt = inds.most_common(1)[0]
        if not_asked("industry", "equals", top_ind):
            s = _balance_score(cnt, total)
            if s >= 0.3:
                candidate_questions.append((s, QuestionDTO(
                    question=f"这只股票属于{top_ind}行业吗？",
                    predicate=Predicate(field="industry", op="equals", value=top_ind),
                    reasoning=f"启发式：{top_ind}行业 占 {cnt}/{total} (均衡度 {s:.2f})",
                )))

    if not candidate_questions:
        return None

    # 取均衡度最高的那个
    candidate_questions.sort(key=lambda x: x[0], reverse=True)
    return candidate_questions[0][1]


async def pick_next_question(
    candidates: list[dict],
    history: list[QAEntry],
    user_id: str,
    session_id: str,
) -> tuple[QuestionDTO, int]:
    """Pick the next question.

    策略：
    1. 前 HEURISTIC_FIRST_N_ROUNDS 轮 或 候选数 > LLM_CANDIDATE_THRESHOLD 时，
       优先用启发式均衡切分（交易所/创业板/沪深300/市值档位），省 token、快。
    2. 启发式找不到足够均衡的维度时，才调 LLM 做精细决策（概念/行业/估值/地域等）。
    3. LLM 失败最终兜底 `_heuristic_fallback_question`。
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    asked_fields = {h.predicate.field for h in history}
    asked_predicates = {
        (h.predicate.field, h.predicate.op, json.dumps(h.predicate.value, sort_keys=True, default=str))
        for h in history
    }
    round_idx = len(history)

    # Step 1: early rounds or large candidate set → try heuristic first
    use_heuristic_first = (
        round_idx < HEURISTIC_FIRST_N_ROUNDS
        or len(candidates) > LLM_CANDIDATE_THRESHOLD
    )
    if use_heuristic_first:
        q = _heuristic_balanced_question(candidates, asked_predicates)
        if q is not None:
            logger.info(
                f"Round {round_idx + 1}: using heuristic question "
                f"(candidates={len(candidates)}, field={q.predicate.field})"
            )
            return q, 0

    # Step 2: call LLM for fine-grained decision
    for attempt in range(2):
        try:
            prompt = _build_prompt(candidates, history, with_fallback_hint=(attempt > 0))
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content="请给出下一个问题（严格 JSON 输出）。"),
            ]
            content, tokens = await _invoke_llm(messages, user_id, session_id)
            data = _parse_llm_json(content)

            if not data:
                logger.warning(f"LLM output not JSON parseable: {content[:200]}")
                continue

            question = data.get("question", "").strip()
            pred_data = data.get("predicate") or {}
            if not question or not pred_data.get("field"):
                logger.warning(f"LLM output missing fields: {data}")
                continue

            try:
                predicate = Predicate(**pred_data)
            except Exception as e:
                logger.warning(f"Invalid predicate: {e}, data={pred_data}")
                continue

            # Don't allow repeating the exact same field
            if predicate.field in asked_fields and attempt == 0:
                logger.info(f"LLM repeated asked field {predicate.field}, retrying")
                continue

            # Sanity check the split
            yes_count = sum(1 for c in candidates if _matches(c, predicate))
            no_count = len(candidates) - yes_count
            if yes_count == 0 or no_count == 0:
                logger.info(
                    f"LLM split is 0/{len(candidates)} — retrying with fallback hint"
                )
                continue

            return QuestionDTO(
                question=question,
                predicate=predicate,
                reasoning=data.get("reasoning", ""),
            ), tokens
        except Exception as e:
            logger.error(f"LLM call error (attempt {attempt}): {e}", exc_info=True)

    # All attempts failed — heuristic fallback
    logger.warning("Falling back to heuristic question")
    return _heuristic_fallback_question(candidates, asked_fields), 0


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def _session_key(session_id: str) -> str:
    return f"akinator:session:{session_id}"


def _save_session(session_id: str, state: dict) -> None:
    cache = get_cache_service()
    cache.set(_session_key(session_id), json.dumps(state), ttl=SESSION_TTL_SECONDS)


def _load_session(session_id: str) -> dict | None:
    cache = get_cache_service()
    raw = cache.get(_session_key(session_id))
    if not raw:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None


def _delete_session(session_id: str) -> None:
    cache = get_cache_service()
    cache.delete(_session_key(session_id))


def _stock_to_dto(stock: dict) -> StockDTO:
    return StockDTO(
        ts_code=stock.get("ts_code", ""),
        name=stock.get("name"),
        industry=stock.get("industry"),
        total_mv=_num(stock.get("total_mv")),
        pe_ttm=_num(stock.get("pe_ttm")),
        concepts=(stock.get("concepts") or [])[:10],
    )


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------


async def start_session(user_id: str) -> dict:
    """Start a new Akinator session.

    Returns dict with keys: session_id, question (QuestionDTO dict),
    question_count, candidates_remaining, tokens_used.
    """
    matrix = get_stock_matrix()
    if not matrix:
        raise RuntimeError("Stock matrix is empty")

    session_id = str(uuid.uuid4())
    candidates = list(matrix.values())

    question, tokens = await pick_next_question(candidates, [], user_id, session_id)

    state = {
        "user_id": user_id,
        "started_at": time.time(),
        "candidate_codes": [s["ts_code"] for s in candidates],
        "history": [],
        "pending_question": question.model_dump(),
        "total_tokens": tokens,
    }
    _save_session(session_id, state)

    return {
        "session_id": session_id,
        "question": question,
        "question_count": 1,
        "candidates_remaining": len(candidates),
        "tokens_used": tokens,
    }


async def answer_session(session_id: str, answer: str, user_id: str) -> dict:
    """Process user's answer and advance the session."""
    state = _load_session(session_id)
    if not state:
        raise LookupError("Session not found or expired")

    if state["user_id"] != user_id:
        raise PermissionError("Session belongs to another user")

    pending = state.get("pending_question")
    if not pending:
        raise RuntimeError("No pending question in session")

    matrix = get_stock_matrix()
    candidates = [matrix[code] for code in state["candidate_codes"] if code in matrix]

    predicate = Predicate(**pending["predicate"])
    new_candidates = apply_predicate(candidates, predicate, answer)

    history = [QAEntry(**h) for h in state.get("history", [])]

    # Handle 0-candidate case: roll back, treat as unknown
    rolled_back = False
    if not new_candidates and answer != "unknown":
        logger.info(f"Session {session_id}: answer '{answer}' eliminated all, rolling back")
        new_candidates = candidates
        effective_answer = "unknown"
        rolled_back = True
    else:
        effective_answer = answer

    # Append to history
    history.append(QAEntry(
        question=pending["question"],
        predicate=predicate,
        answer=effective_answer,
        reasoning=pending.get("reasoning", ""),
    ))
    question_count = len(history)

    # Termination check
    if len(new_candidates) <= FINISH_THRESHOLD or question_count >= MAX_QUESTIONS:
        # Sort final candidates by market cap (most prominent first)
        new_candidates.sort(key=lambda s: s.get("total_mv") or 0, reverse=True)
        final = [_stock_to_dto(s) for s in new_candidates[:FINISH_THRESHOLD]]

        # Update state one last time (finished)
        state["candidate_codes"] = [s["ts_code"] for s in new_candidates]
        state["history"] = [h.model_dump() for h in history]
        state["pending_question"] = None
        _save_session(session_id, state)

        return {
            "session_id": session_id,
            "status": "finished",
            "question": None,
            "final_candidates": final,
            "question_count": question_count,
            "candidates_remaining": len(new_candidates),
            "tokens_used": 0,
            "rolled_back": rolled_back,
        }

    # Generate next question
    question, tokens = await pick_next_question(new_candidates, history, user_id, session_id)

    state["candidate_codes"] = [s["ts_code"] for s in new_candidates]
    state["history"] = [h.model_dump() for h in history]
    state["pending_question"] = question.model_dump()
    state["total_tokens"] = state.get("total_tokens", 0) + tokens
    _save_session(session_id, state)

    return {
        "session_id": session_id,
        "status": "continue",
        "question": question,
        "final_candidates": None,
        "question_count": question_count,
        "candidates_remaining": len(new_candidates),
        "tokens_used": tokens,
        "rolled_back": rolled_back,
    }


async def pick_next_question_stream(
    candidates: list[dict],
    history: list[QAEntry],
    user_id: str,
    session_id: str,
):
    """Streaming variant. Yields dict events:

    - {"type": "heuristic", "question": QuestionDTO-dict}   # used heuristic, no LLM
    - {"type": "llm_start"}                                   # LLM begins generating
    - {"type": "think_delta", "text": str}                    # incremental thinking text
    - {"type": "think_end"}                                   # </think> closed
    - {"type": "question", "question": QuestionDTO-dict}     # parsed final question
    - {"type": "error", "message": str}                       # final error, will fallback
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    asked_predicates = {
        (h.predicate.field, h.predicate.op, json.dumps(h.predicate.value, sort_keys=True, default=str))
        for h in history
    }
    round_idx = len(history)

    # Heuristic shortcut
    use_heuristic_first = (
        round_idx < HEURISTIC_FIRST_N_ROUNDS
        or len(candidates) > LLM_CANDIDATE_THRESHOLD
    )
    if use_heuristic_first:
        q = _heuristic_balanced_question(candidates, asked_predicates)
        if q is not None:
            yield {"type": "heuristic", "question": q.model_dump()}
            return

    # LLM streaming path
    prompt = _build_prompt(candidates, history, with_fallback_hint=False)
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="现在请给出下一个问题。请务必严格按照两段式输出：先用 `<think>` 标签包含至少80字的思考过程，然后紧跟 JSON。不要省略 <think> 标签。"),
    ]

    yield {"type": "llm_start"}

    accumulated = ""

    try:
        async with asyncio.timeout(60.0):
            async for piece in _stream_llm(messages, user_id, session_id):
                if not piece:
                    continue
                accumulated += piece
                # Stream every chunk so the user sees the LLM is actually
                # working. We forward the raw chunk; the frontend decides how
                # to present it. (Even if the model skips <think> and emits
                # JSON directly, the user still sees live typing.)
                yield {"type": "think_delta", "text": piece}
    except asyncio.TimeoutError:
        yield {"type": "error", "message": "LLM 思考超时 (>60s)"}
        return
    except Exception as e:
        logger.error(f"LLM stream error: {e}", exc_info=True)
        yield {"type": "error", "message": f"LLM 调用异常: {e}"}
        return

    yield {"type": "think_end"}

    # Parse final JSON
    data = _parse_llm_json(accumulated)
    if not data:
        logger.warning(f"Stream output not JSON parseable: {accumulated[:200]}")
        yield {"type": "error", "message": "LLM 输出无法解析为 JSON"}
        return

    question_text = (data.get("question") or "").strip()
    pred_data = data.get("predicate") or {}
    if not question_text or not pred_data.get("field"):
        yield {"type": "error", "message": "LLM 输出缺少必要字段"}
        return

    try:
        predicate = Predicate(**pred_data)
    except Exception as e:
        yield {"type": "error", "message": f"谓词无效: {e}"}
        return

    # Sanity check split
    yes_count = sum(1 for c in candidates if _matches(c, predicate))
    if yes_count == 0 or yes_count == len(candidates):
        yield {"type": "error", "message": "LLM 问题切分为 0/全，已兜底"}
        return

    q = QuestionDTO(
        question=question_text,
        predicate=predicate,
        reasoning=data.get("reasoning", ""),
    )
    yield {"type": "question", "question": q.model_dump()}


async def answer_session_stream(session_id: str, answer: str, user_id: str):
    """Streaming variant of answer_session.

    Yields dict events:
    - meta events mirroring pick_next_question_stream
    - {"type": "progress", "candidates_remaining": int, "question_count": int, "rolled_back": bool}
    - {"type": "final", ...full AnswerResponse-compatible payload...}
    """
    state = _load_session(session_id)
    if not state:
        raise LookupError("Session not found or expired")
    if state["user_id"] != user_id:
        raise PermissionError("Session belongs to another user")

    pending = state.get("pending_question")
    if not pending:
        raise RuntimeError("No pending question in session")

    matrix = get_stock_matrix()
    candidates = [matrix[code] for code in state["candidate_codes"] if code in matrix]
    predicate = Predicate(**pending["predicate"])
    new_candidates = apply_predicate(candidates, predicate, answer)

    history = [QAEntry(**h) for h in state.get("history", [])]

    rolled_back = False
    if not new_candidates and answer != "unknown":
        logger.info(f"Session {session_id}: '{answer}' eliminated all, rolling back")
        new_candidates = candidates
        effective_answer = "unknown"
        rolled_back = True
    else:
        effective_answer = answer

    history.append(QAEntry(
        question=pending["question"],
        predicate=predicate,
        answer=effective_answer,
        reasoning=pending.get("reasoning", ""),
    ))
    question_count = len(history)

    yield {
        "type": "progress",
        "candidates_remaining": len(new_candidates),
        "question_count": question_count,
        "rolled_back": rolled_back,
    }

    # Termination
    if len(new_candidates) <= FINISH_THRESHOLD or question_count >= MAX_QUESTIONS:
        new_candidates.sort(key=lambda s: _num(s.get("total_mv")) or 0, reverse=True)
        final = [_stock_to_dto(s).model_dump() for s in new_candidates[:FINISH_THRESHOLD]]

        state["candidate_codes"] = [s["ts_code"] for s in new_candidates]
        state["history"] = [h.model_dump() for h in history]
        state["pending_question"] = None
        _save_session(session_id, state)

        yield {
            "type": "final",
            "session_id": session_id,
            "status": "finished",
            "question": None,
            "final_candidates": final,
            "question_count": question_count,
            "candidates_remaining": len(new_candidates),
            "rolled_back": rolled_back,
        }
        return

    # Stream next question
    question_dict = None
    async for ev in pick_next_question_stream(new_candidates, history, user_id, session_id):
        # Relay event to client
        yield ev
        if ev.get("type") == "question" or ev.get("type") == "heuristic":
            question_dict = ev["question"]
        elif ev.get("type") == "error":
            # Fallback to heuristic
            asked_predicates = {
                (h.predicate.field, h.predicate.op, json.dumps(h.predicate.value, sort_keys=True, default=str))
                for h in history
            }
            fallback = _heuristic_balanced_question(new_candidates, asked_predicates) \
                or _heuristic_fallback_question(
                    new_candidates, {h.predicate.field for h in history}
                )
            question_dict = fallback.model_dump()
            yield {"type": "heuristic", "question": question_dict}

    if question_dict is None:
        # Last-resort fallback
        fallback = _heuristic_fallback_question(
            new_candidates, {h.predicate.field for h in history}
        )
        question_dict = fallback.model_dump()
        yield {"type": "heuristic", "question": question_dict}

    state["candidate_codes"] = [s["ts_code"] for s in new_candidates]
    state["history"] = [h.model_dump() for h in history]
    state["pending_question"] = question_dict
    _save_session(session_id, state)

    yield {
        "type": "final",
        "session_id": session_id,
        "status": "continue",
        "question": question_dict,
        "final_candidates": None,
        "question_count": question_count,
        "candidates_remaining": len(new_candidates),
        "rolled_back": rolled_back,
    }


def get_candidates(session_id: str, user_id: str) -> dict:
    """Get current candidates for UI progress display."""
    state = _load_session(session_id)
    if not state:
        raise LookupError("Session not found or expired")
    if state["user_id"] != user_id:
        raise PermissionError("Session belongs to another user")

    matrix = get_stock_matrix()
    candidates = [matrix[code] for code in state["candidate_codes"] if code in matrix]
    candidates.sort(key=lambda s: s.get("total_mv") or 0, reverse=True)

    return {
        "session_id": session_id,
        "candidates": [_stock_to_dto(s) for s in candidates[:20]],
        "candidates_remaining": len(candidates),
        "question_count": len(state.get("history", [])),
    }


def _archive_session(session_id: str, final_status: str, guessed_ts_code: str = "") -> None:
    """Archive session to ClickHouse."""
    state = _load_session(session_id)
    if not state:
        return

    try:
        db_client.execute(
            """
            INSERT INTO akinator_session
            (session_id, user_id, started_at, ended_at, question_count,
             final_status, guessed_ts_code, qa_log, candidates_final, total_tokens)
            VALUES
            (%(session_id)s, %(user_id)s, %(started_at)s, %(ended_at)s, %(question_count)s,
             %(final_status)s, %(guessed_ts_code)s, %(qa_log)s, %(candidates_final)s, %(total_tokens)s)
            """,
            {
                "session_id": session_id,
                "user_id": state["user_id"],
                "started_at": int(state["started_at"]),
                "ended_at": int(time.time()),
                "question_count": len(state.get("history", [])),
                "final_status": final_status,
                "guessed_ts_code": guessed_ts_code,
                "qa_log": json.dumps(state.get("history", []), ensure_ascii=False),
                "candidates_final": json.dumps(
                    state.get("candidate_codes", [])[:20], ensure_ascii=False
                ),
                "total_tokens": state.get("total_tokens", 0),
            },
        )
    except Exception as e:
        logger.warning(f"Failed to archive session {session_id}: {e}")


def confirm_session(session_id: str, ts_code: str, user_id: str) -> dict:
    """User confirms a stock guess — archive and close session."""
    state = _load_session(session_id)
    if not state:
        raise LookupError("Session not found or expired")
    if state["user_id"] != user_id:
        raise PermissionError("Session belongs to another user")

    _archive_session(session_id, "success", ts_code)
    _delete_session(session_id)
    return {"success": True, "message": f"已确认 {ts_code}"}


def abandon_session(session_id: str, user_id: str) -> dict:
    """User gives up — archive as abandoned."""
    state = _load_session(session_id)
    if not state:
        return {"success": True, "message": "会话已结束"}
    if state["user_id"] != user_id:
        raise PermissionError("Session belongs to another user")

    _archive_session(session_id, "abandoned", "")
    _delete_session(session_id)
    return {"success": True, "message": "已放弃本局"}


def ensure_schema() -> None:
    """Create the archive table if it doesn't exist."""
    import os

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        return
    with open(schema_path) as f:
        sql_content = f.read()
    for stmt in sql_content.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                db_client.execute(stmt)
            except Exception as e:
                logger.warning(f"Schema stmt failed: {e}")
