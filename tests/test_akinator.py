"""Tests for Akinator module — predicate filtering + session flow with mocked LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from stock_datasource.modules.akinator.schemas import (
    AnswerRequest,
    Predicate,
    QAEntry,
    QuestionDTO,
)
from stock_datasource.modules.akinator import service


# ---------------------------------------------------------------------------
# Fixtures: minimal stock matrix
# ---------------------------------------------------------------------------


MOCK_MATRIX = {
    "600519.SH": {
        "ts_code": "600519.SH", "name": "贵州茅台",
        "industry": "白酒", "area": "贵州", "province": "贵州",
        "market": "主板", "list_date": "2001-08-27",
        "total_mv": 20_000_000 * 10000,  # 2 万亿
        "pe_ttm": 25.0, "pb": 10.0, "dv_ratio": 1.5,
        "roe": 32.0, "net_profit_margin": 55.0, "debt_to_assets": 20.0,
        "in_hs300": True, "in_sz50": True, "in_zz500": False,
        "concepts": ["白酒", "消费龙头"],
        "main_business": "白酒生产销售",
    },
    "300750.SZ": {
        "ts_code": "300750.SZ", "name": "宁德时代",
        "industry": "电池", "area": "福建", "province": "福建",
        "market": "创业板", "list_date": "2018-06-11",
        "total_mv": 1_200_000 * 10000,
        "pe_ttm": 30.0, "pb": 5.0, "dv_ratio": 0.5,
        "roe": 20.0, "net_profit_margin": 15.0, "debt_to_assets": 65.0,
        "in_hs300": True, "in_sz50": False, "in_zz500": False,
        "concepts": ["新能源车", "锂电池", "储能"],
        "main_business": "锂离子电池",
    },
    "601318.SH": {
        "ts_code": "601318.SH", "name": "中国平安",
        "industry": "保险", "area": "广东", "province": "广东",
        "market": "主板", "list_date": "2007-03-01",
        "total_mv": 9_000_000 * 10000,
        "pe_ttm": 8.0, "pb": 1.0, "dv_ratio": 5.0,
        "roe": 10.0, "net_profit_margin": 12.0, "debt_to_assets": 88.0,
        "in_hs300": True, "in_sz50": True, "in_zz500": False,
        "concepts": ["大金融", "保险"],
        "main_business": "综合金融服务",
    },
    "000001.SZ": {
        "ts_code": "000001.SZ", "name": "平安银行",
        "industry": "银行", "area": "广东", "province": "广东",
        "market": "主板", "list_date": "1991-04-03",
        "total_mv": 2_500_000 * 10000,
        "pe_ttm": 4.5, "pb": 0.6, "dv_ratio": 5.5,
        "roe": 11.0, "net_profit_margin": 30.0, "debt_to_assets": 92.0,
        "in_hs300": True, "in_sz50": False, "in_zz500": False,
        "concepts": ["银行", "大金融"],
        "main_business": "商业银行",
    },
    "688981.SH": {
        "ts_code": "688981.SH", "name": "中芯国际",
        "industry": "半导体", "area": "上海", "province": "上海",
        "market": "科创板", "list_date": "2020-07-16",
        "total_mv": 1_000_000 * 10000,
        "pe_ttm": 50.0, "pb": 3.0, "dv_ratio": 0.1,
        "roe": 5.0, "net_profit_margin": 8.0, "debt_to_assets": 40.0,
        "in_hs300": False, "in_sz50": False, "in_zz500": False,
        "concepts": ["半导体", "芯片", "国产替代"],
        "main_business": "集成电路晶圆代工",
    },
}


# ---------------------------------------------------------------------------
# Predicate evaluation tests
# ---------------------------------------------------------------------------


class TestPredicateEval:
    def test_contains_string(self):
        p = Predicate(field="industry", op="contains", value="银行")
        stock = MOCK_MATRIX["000001.SZ"]
        assert service._matches(stock, p) is True

    def test_contains_list(self):
        """concepts 是 list，contains 应匹配列表元素。"""
        p = Predicate(field="concepts", op="contains", value="白酒")
        assert service._matches(MOCK_MATRIX["600519.SH"], p) is True
        assert service._matches(MOCK_MATRIX["300750.SZ"], p) is False

    def test_equals(self):
        p = Predicate(field="market", op="equals", value="创业板")
        assert service._matches(MOCK_MATRIX["300750.SZ"], p) is True
        assert service._matches(MOCK_MATRIX["600519.SH"], p) is False

    def test_startswith(self):
        p = Predicate(field="ts_code", op="startswith", value="688")
        assert service._matches(MOCK_MATRIX["688981.SH"], p) is True
        assert service._matches(MOCK_MATRIX["600519.SH"], p) is False

    def test_gte_numeric(self):
        p = Predicate(field="total_mv", op="gte", value=5_000_000 * 10000)  # 5000亿
        assert service._matches(MOCK_MATRIX["600519.SH"], p) is True   # 2万亿
        assert service._matches(MOCK_MATRIX["688981.SH"], p) is False  # 1000亿

    def test_in_list(self):
        p = Predicate(field="industry", op="in_list", value=["银行", "保险"])
        assert service._matches(MOCK_MATRIX["000001.SZ"], p) is True
        assert service._matches(MOCK_MATRIX["601318.SH"], p) is True
        assert service._matches(MOCK_MATRIX["600519.SH"], p) is False

    def test_null_field_returns_false(self):
        p = Predicate(field="industry", op="contains", value="银行")
        assert service._matches({"industry": None}, p) is False

    def test_bool_equals(self):
        p = Predicate(field="in_hs300", op="equals", value=True)
        assert service._matches(MOCK_MATRIX["600519.SH"], p) is True
        assert service._matches(MOCK_MATRIX["688981.SH"], p) is False


class TestApplyPredicate:
    def test_filter_yes(self):
        p = Predicate(field="in_hs300", op="equals", value=True)
        result = service.apply_predicate(list(MOCK_MATRIX.values()), p, "yes")
        assert len(result) == 4  # 4 in HS300

    def test_filter_no(self):
        p = Predicate(field="in_hs300", op="equals", value=True)
        result = service.apply_predicate(list(MOCK_MATRIX.values()), p, "no")
        assert len(result) == 1
        assert result[0]["ts_code"] == "688981.SH"

    def test_filter_unknown_returns_all(self):
        p = Predicate(field="industry", op="equals", value="xxx")
        result = service.apply_predicate(list(MOCK_MATRIX.values()), p, "unknown")
        assert len(result) == len(MOCK_MATRIX)


# ---------------------------------------------------------------------------
# LLM JSON parsing tests
# ---------------------------------------------------------------------------


class TestLLMParsing:
    def test_parse_plain_json(self):
        data = service._parse_llm_json(
            '{"question":"Q","predicate":{"field":"industry","op":"equals","value":"银行"},"reasoning":"r"}'
        )
        assert data["question"] == "Q"

    def test_parse_markdown_wrapped(self):
        raw = '```json\n{"question":"Q","predicate":{"field":"industry","op":"equals","value":"银行"}}\n```'
        data = service._parse_llm_json(raw)
        assert data["question"] == "Q"

    def test_parse_embedded_in_text(self):
        raw = '好的，我的答案是：\n{"question":"Q","predicate":{"field":"industry","op":"equals","value":"银行"}}\n结束'
        data = service._parse_llm_json(raw)
        assert data["question"] == "Q"

    def test_parse_invalid(self):
        assert service._parse_llm_json("just plain text") is None


# ---------------------------------------------------------------------------
# Heuristic fallback test
# ---------------------------------------------------------------------------


class TestHeuristicFallback:
    def test_industry_fallback(self):
        q = service._heuristic_fallback_question(list(MOCK_MATRIX.values()), set())
        assert q.predicate.field in ("industry", "in_hs300", "total_mv", "market")

    def test_skips_asked_fields(self):
        q = service._heuristic_fallback_question(
            list(MOCK_MATRIX.values()), {"industry", "in_hs300"}
        )
        assert q.predicate.field not in ("industry", "in_hs300")


# ---------------------------------------------------------------------------
# Full session flow (with mocked LLM)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_matrix():
    """Patch get_stock_matrix to return our test fixture."""
    with patch(
        "stock_datasource.modules.akinator.service.get_stock_matrix",
        return_value=MOCK_MATRIX,
    ):
        yield


@pytest.fixture
def mock_cache():
    """In-memory cache substitute."""
    store = {}

    class FakeCache:
        def get(self, key):
            return store.get(key)

        def set(self, key, value, ttl=300):
            store[key] = value
            return True

        def delete(self, key):
            store.pop(key, None)
            return True

    with patch(
        "stock_datasource.modules.akinator.service.get_cache_service",
        return_value=FakeCache(),
    ):
        yield store


@pytest.fixture
def mock_llm_sequence():
    """Return a mock LLM that yields pre-defined questions in sequence."""
    questions = [
        QuestionDTO(
            question="是沪深300成分股吗?",
            predicate=Predicate(field="in_hs300", op="equals", value=True),
            reasoning="沪深300 切分",
        ),
        QuestionDTO(
            question="属于金融行业吗?",
            predicate=Predicate(field="industry", op="in_list", value=["银行", "保险"]),
            reasoning="金融切分",
        ),
        QuestionDTO(
            question="市值 > 5000亿?",
            predicate=Predicate(field="total_mv", op="gte", value=5_000_000 * 10000),
            reasoning="市值切分",
        ),
    ]

    call_count = {"n": 0}

    async def mock_pick(candidates, history, user_id, session_id):
        idx = min(call_count["n"], len(questions) - 1)
        call_count["n"] += 1
        return questions[idx], 100  # 100 tokens

    with patch(
        "stock_datasource.modules.akinator.service.pick_next_question",
        side_effect=mock_pick,
    ):
        yield


class TestSessionFlow:
    @pytest.mark.asyncio
    async def test_start_returns_question(self, mock_matrix, mock_cache, mock_llm_sequence):
        result = await service.start_session(user_id="u1")
        assert "session_id" in result
        assert result["candidates_remaining"] == 5  # MOCK_MATRIX size
        assert result["question"].question == "是沪深300成分股吗?"

    @pytest.mark.asyncio
    async def test_answer_filters_candidates(
        self, mock_matrix, mock_cache, mock_llm_sequence
    ):
        start = await service.start_session(user_id="u1")
        sid = start["session_id"]

        # Answer "no" to "in_hs300" → only 中芯国际 remains (688981)
        result = await service.answer_session(sid, answer="no", user_id="u1")
        assert result["candidates_remaining"] == 1
        assert result["status"] == "finished"  # <= 10
        assert result["final_candidates"][0].ts_code == "688981.SH"

    @pytest.mark.asyncio
    async def test_answer_yes_continues(
        self, mock_matrix, mock_cache, mock_llm_sequence
    ):
        start = await service.start_session(user_id="u1")
        sid = start["session_id"]

        # Answer "yes" → 4 hs300 members remain, <= 10 triggers finished
        result = await service.answer_session(sid, answer="yes", user_id="u1")
        assert result["candidates_remaining"] == 4
        assert result["status"] == "finished"

    @pytest.mark.asyncio
    async def test_rollback_on_zero_candidates(
        self, mock_matrix, mock_cache
    ):
        """If predicate filters to 0, rolled_back=True, candidates preserved."""
        # Inject a question that would eliminate all
        bad_question = QuestionDTO(
            question="属于 xyz 行业吗?",
            predicate=Predicate(field="industry", op="equals", value="xyz"),
            reasoning="bad",
        )
        async def mock_pick_bad(*args, **kwargs):
            return bad_question, 50

        with patch(
            "stock_datasource.modules.akinator.service.pick_next_question",
            side_effect=mock_pick_bad,
        ):
            start = await service.start_session(user_id="u1")
            sid = start["session_id"]
            # Answer yes → 0 candidates match → rollback
            result = await service.answer_session(sid, answer="yes", user_id="u1")
            assert result["rolled_back"] is True
            assert result["candidates_remaining"] == 5  # Preserved

    @pytest.mark.asyncio
    async def test_confirm_archives_session(
        self, mock_matrix, mock_cache, mock_llm_sequence
    ):
        start = await service.start_session(user_id="u1")
        sid = start["session_id"]

        with patch("stock_datasource.modules.akinator.service.db_client.execute"):
            result = service.confirm_session(sid, "600519.SH", user_id="u1")
            assert result["success"] is True
        # Session should be gone from cache
        assert service._load_session(sid) is None

    @pytest.mark.asyncio
    async def test_permission_enforced(
        self, mock_matrix, mock_cache, mock_llm_sequence
    ):
        start = await service.start_session(user_id="u1")
        sid = start["session_id"]
        with pytest.raises(PermissionError):
            await service.answer_session(sid, "yes", user_id="other_user")

    @pytest.mark.asyncio
    async def test_missing_session_raises(self, mock_matrix, mock_cache):
        with pytest.raises(LookupError):
            await service.answer_session("nonexistent", "yes", user_id="u1")
