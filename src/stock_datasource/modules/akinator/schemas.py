"""Pydantic schemas for the Akinator module."""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM question output
# ---------------------------------------------------------------------------


class Predicate(BaseModel):
    """Filter predicate produced by the LLM."""

    field: str = Field(..., description="属性字段名，如 industry / concepts / total_mv")
    op: Literal[
        "contains", "equals", "startswith", "endswith", "in_list",
        "gt", "lt", "gte", "lte",
    ]
    value: Any = Field(..., description="比较值，字符串/数字/列表")


class QuestionDTO(BaseModel):
    """A yes/no question shown to the user."""

    question: str
    predicate: Predicate
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Stock candidate (subset of attributes shown to user)
# ---------------------------------------------------------------------------


class StockDTO(BaseModel):
    ts_code: str
    name: str | None = None
    industry: str | None = None
    total_mv: float | None = None
    pe_ttm: float | None = None
    concepts: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Session Q/A log
# ---------------------------------------------------------------------------


class QAEntry(BaseModel):
    question: str
    predicate: Predicate
    answer: Literal["yes", "no", "unknown"]
    reasoning: str = ""


# ---------------------------------------------------------------------------
# API request/response
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    pass  # no body needed


class StartResponse(BaseModel):
    session_id: str
    question: QuestionDTO
    question_count: int = 1
    candidates_remaining: int


class AnswerRequest(BaseModel):
    session_id: str
    answer: Literal["yes", "no", "unknown"]


class AnswerResponse(BaseModel):
    session_id: str
    status: Literal["continue", "finished"]
    question: QuestionDTO | None = None
    final_candidates: list[StockDTO] | None = None
    question_count: int
    candidates_remaining: int
    tokens_used: int = 0


class CandidatesResponse(BaseModel):
    session_id: str
    candidates: list[StockDTO]
    candidates_remaining: int
    question_count: int


class ConfirmRequest(BaseModel):
    session_id: str
    ts_code: str


class AbandonRequest(BaseModel):
    session_id: str
