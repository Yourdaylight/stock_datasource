"""AI diagnosis service for system logs."""

import json
import logging
from typing import Any, Dict, List, Optional

from stock_datasource.agents.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


class LogAIDiagnosisService:
    """Build prompt and call orchestrator for log diagnosis."""

    def _build_log_context(self, log_entries: List[Dict[str, Any]], max_entries: int = 40) -> str:
        recent = log_entries[:max_entries]
        lines: List[str] = []
        for idx, item in enumerate(recent, start=1):
            timestamp = item.get("timestamp", "")
            level = str(item.get("level", "INFO")).upper()
            module = item.get("module", "unknown")
            message = str(item.get("message", "")).strip().replace("\n", " | ")
            lines.append(f"{idx}. [{timestamp}] [{level}] [{module}] {message[:300]}")
        return "\n".join(lines)

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None

        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < 0 or end <= start:
            return None

        json_text = text[start:end + 1]
        try:
            value = json.loads(json_text)
            if isinstance(value, dict):
                return value
        except Exception as e:
            logger.warning(f"Failed to parse diagnosis JSON: {e}")
        return None

    async def diagnose(
        self,
        log_entries: List[Dict[str, Any]],
        user_query: Optional[str] = None,
        context: Optional[str] = None,
        include_code_context: bool = True,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run AI diagnosis and return structured result dict."""
        orchestrator = get_orchestrator()
        log_context = self._build_log_context(log_entries=log_entries)
        prompt = (
            "你是系统故障诊断助手。请仅输出 JSON。"
            "JSON 必须包含字段: "
            "summary(string), error_type(string), risk_level(string), impact_scope(string), "
            "possible_causes(string[]), suggested_fixes(string[]), "
            "root_causes(array of {title,module,function,evidence,confidence}), "
            "recent_operations(array of {timestamp,event_type,level,module,summary}), "
            "fix_suggestions(array of {title,steps,priority}), confidence(number)。\n\n"
            f"用户问题: {user_query or '请分析最近日志异常并给出修复建议'}\n"
            f"补充上下文: {context or '无'}\n"
            f"要求代码线索: {'是' if include_code_context else '否'}\n"
            f"日志片段:\n{log_context}"
        )

        result = await orchestrator.execute(
            query=prompt,
            context={
                "intent": "system_log_diagnosis",
                "user_id": user_id or "admin",
                "source": "system_logs",
            },
        )

        parsed = self._extract_json(result.response)
        if parsed:
            return parsed

        logger.warning("AI diagnosis response is not JSON, fallback to text wrapping")
        return {
            "summary": result.response[:500],
            "error_type": "GeneralError",
            "risk_level": "medium",
            "impact_scope": "可能影响近期任务执行与接口稳定性",
            "possible_causes": ["AI 返回非结构化结果，请结合日志明细复核"],
            "suggested_fixes": ["检查最近错误日志并按模块逐项排查"],
            "root_causes": [],
            "recent_operations": [],
            "fix_suggestions": [],
            "confidence": 0.45,
        }


_ai_diagnosis_service: Optional[LogAIDiagnosisService] = None


def get_log_ai_diagnosis_service() -> LogAIDiagnosisService:
    """Get singleton AI diagnosis service."""
    global _ai_diagnosis_service
    if _ai_diagnosis_service is None:
        _ai_diagnosis_service = LogAIDiagnosisService()
    return _ai_diagnosis_service
