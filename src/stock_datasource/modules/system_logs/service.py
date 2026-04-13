"""Service for system logs management."""

import gzip
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schemas import (
    ErrorClusterItem,
    ErrorClusterResponse,
    LogAnalysisRequest,
    LogAnalysisResponse,
    LogEntry,
    LogFileInfo,
    LogFilter,
    LogFixSuggestion,
    LogInsightFilter,
    LogListResponse,
    LogRootCause,
    LogStatsResponse,
    LogStatsTrendPoint,
    OperationTimelineItem,
    OperationTimelineResponse,
)
from .ai_diagnosis_service import get_log_ai_diagnosis_service
from .log_parser import LogFileReader

logger = logging.getLogger(__name__)


class LogService:
    """Service for managing system logs."""

    def __init__(self, log_dir: str = "logs"):
        """Initialize log service.

        Args:
            log_dir: Directory containing log files
        """
        self.log_dir = Path(log_dir)
        self.reader = LogFileReader(log_dir)
        self.ai_diagnosis_service = get_log_ai_diagnosis_service()

    @property
    def _ch_client(self):
        """Lazy-access ClickHouse client."""
        try:
            from stock_datasource.models.database import db_client
            return db_client
        except Exception:
            return None

    # ------------------------------------------------------------------
    # get_logs — ClickHouse-first with file fallback
    # ------------------------------------------------------------------
    def get_logs(self, filters: LogFilter) -> LogListResponse:
        """Get filtered logs. Queries ClickHouse first, falls back to file parsing."""
        # Try ClickHouse path
        ch_result = self._get_logs_from_clickhouse(filters)
        if ch_result is not None:
            return ch_result

        # Fallback: file parsing
        logs = self.reader.read_logs(
            log_file=None,
            start_time=filters.start_time,
            end_time=filters.end_time,
            level=filters.level,
            keyword=filters.keyword,
            request_id=filters.request_id,
            limit=filters.page_size,
            offset=(filters.page - 1) * filters.page_size,
        )

        log_entries = [LogEntry(**log) for log in logs]
        offset = (filters.page - 1) * filters.page_size
        estimated_total = offset + len(log_entries)
        if len(log_entries) == filters.page_size:
            estimated_total += 1

        return LogListResponse(
            logs=log_entries,
            total=estimated_total,
            page=filters.page,
            page_size=filters.page_size,
        )

    def _get_logs_from_clickhouse(self, filters: LogFilter) -> Optional[LogListResponse]:
        """Query logs from ClickHouse system_structured_logs table.

        Returns None if ClickHouse is unavailable (caller should fall back).
        """
        ch = self._ch_client
        if ch is None:
            return None
        try:
            conditions = []
            params: Dict[str, Any] = {}

            if filters.start_time:
                conditions.append("timestamp >= %(start_time)s")
                params["start_time"] = filters.start_time.strftime("%Y-%m-%d %H:%M:%S")
            if filters.end_time:
                conditions.append("timestamp <= %(end_time)s")
                params["end_time"] = filters.end_time.strftime("%Y-%m-%d %H:%M:%S")
            if filters.level:
                conditions.append("level = %(level)s")
                params["level"] = filters.level.upper()
            if filters.keyword:
                conditions.append("message ILIKE %(keyword)s")
                params["keyword"] = f"%{filters.keyword}%"
            if filters.request_id and filters.request_id != "-":
                conditions.append("request_id = %(request_id)s")
                params["request_id"] = filters.request_id
            if getattr(filters, 'middleware_trace_id', None) and filters.middleware_trace_id != "-":
                conditions.append("middleware_trace_id = %(middleware_trace_id)s")
                params["middleware_trace_id"] = filters.middleware_trace_id

            where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

            # Count
            count_sql = f"SELECT count() AS cnt FROM system_structured_logs{where}"
            count_row = ch.execute(count_sql, params)
            total = int(count_row[0][0]) if count_row else 0

            # Data
            offset = (filters.page - 1) * filters.page_size
            data_sql = (
                f"SELECT timestamp, level, request_id, user_id, middleware_trace_id, "
                f"module, function, line, message, exception "
                f"FROM system_structured_logs{where} "
                f"ORDER BY timestamp DESC LIMIT %(limit)s OFFSET %(offset)s"
            )
            params["limit"] = filters.page_size
            params["offset"] = offset
            rows = ch.execute(data_sql, params)

            log_entries = []
            for row in rows:
                ts, level, req_id, uid, mw_id, module, func, line_no, msg, exc = row
                log_entries.append(LogEntry(
                    timestamp=ts if isinstance(ts, datetime) else datetime.now(),
                    level=str(level),
                    module=str(module),
                    message=str(msg),
                    raw_line=f"{ts} | {level} | {req_id} | {uid} | {mw_id} | {module}:{func}:{line_no} - {msg}",
                    request_id=str(req_id),
                    user_id=str(uid),
                    middleware_trace_id=str(mw_id),
                ))

            return LogListResponse(
                logs=log_entries,
                total=total,
                page=filters.page,
                page_size=filters.page_size,
            )
        except Exception as e:
            logger.warning(f"ClickHouse log query failed, falling back to file: {e}")
            return None

    def get_stats(self, filters: LogInsightFilter) -> LogStatsResponse:
        """Get log level stats and trend in a time window."""
        # Try ClickHouse path
        ch_result = self._get_stats_from_clickhouse(filters)
        if ch_result is not None:
            return ch_result

        # Fallback: file parsing
        start_time, end_time = self._resolve_time_window(filters)
        logs = self.reader.read_logs(
            log_file=None,
            start_time=start_time,
            end_time=end_time,
            level=filters.level,
            keyword=filters.keyword,
            request_id=filters.request_id,
            limit=100000,
            offset=0,
        )

        level_counter = Counter(log.get('level', 'INFO').upper() for log in logs)
        trend_bucket: Dict[datetime, Counter] = defaultdict(Counter)

        for log in logs:
            timestamp = log.get('timestamp')
            if not isinstance(timestamp, datetime):
                continue
            bucket = timestamp.replace(minute=0, second=0, microsecond=0)
            lvl = str(log.get('level', 'INFO')).upper()
            trend_bucket[bucket][lvl] += 1

        trend = []
        for bucket in sorted(trend_bucket.keys()):
            counter = trend_bucket[bucket]
            trend.append(
                LogStatsTrendPoint(
                    timestamp=bucket,
                    total=sum(counter.values()),
                    error=counter.get('ERROR', 0),
                    warning=counter.get('WARNING', 0),
                    info=counter.get('INFO', 0),
                    debug=counter.get('DEBUG', 0),
                )
            )

        return LogStatsResponse(
            total=len(logs),
            error=level_counter.get('ERROR', 0),
            warning=level_counter.get('WARNING', 0),
            info=level_counter.get('INFO', 0),
            debug=level_counter.get('DEBUG', 0),
            by_level=dict(level_counter),
            trend=trend,
        )

    def _get_stats_from_clickhouse(self, filters: LogInsightFilter) -> Optional[LogStatsResponse]:
        """Query stats from ClickHouse. Returns None on failure."""
        ch = self._ch_client
        if ch is None:
            return None
        try:
            start_time, end_time = self._resolve_time_window(filters)
            conditions = [
                "timestamp >= %(start_time)s",
                "timestamp <= %(end_time)s",
            ]
            params: Dict[str, Any] = {
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if filters.level:
                conditions.append("level = %(level)s")
                params["level"] = filters.level.upper()
            if filters.keyword:
                conditions.append("message ILIKE %(keyword)s")
                params["keyword"] = f"%{filters.keyword}%"
            if filters.request_id and filters.request_id != "-":
                conditions.append("request_id = %(request_id)s")
                params["request_id"] = filters.request_id

            where = f" WHERE {' AND '.join(conditions)}"

            # Level counts
            count_sql = (
                f"SELECT level, count() AS cnt FROM system_structured_logs{where} "
                f"GROUP BY level"
            )
            rows = ch.execute(count_sql, params)
            level_counter = {str(row[0]): int(row[1]) for row in rows}

            # Hourly trend
            trend_sql = (
                f"SELECT toStartOfHour(timestamp) AS bucket, level, count() AS cnt "
                f"FROM system_structured_logs{where} "
                f"GROUP BY bucket, level ORDER BY bucket"
            )
            trend_rows = ch.execute(trend_sql, params)
            trend_bucket: Dict[datetime, Counter] = defaultdict(Counter)
            for row in trend_rows:
                bucket_dt = row[0] if isinstance(row[0], datetime) else start_time
                lvl = str(row[1])
                cnt = int(row[2])
                trend_bucket[bucket_dt][lvl] += cnt

            trend = []
            for bucket in sorted(trend_bucket.keys()):
                counter = trend_bucket[bucket]
                trend.append(LogStatsTrendPoint(
                    timestamp=bucket,
                    total=sum(counter.values()),
                    error=counter.get('ERROR', 0),
                    warning=counter.get('WARNING', 0),
                    info=counter.get('INFO', 0),
                    debug=counter.get('DEBUG', 0),
                ))

            total = sum(level_counter.values())
            return LogStatsResponse(
                total=total,
                error=level_counter.get('ERROR', 0),
                warning=level_counter.get('WARNING', 0),
                info=level_counter.get('INFO', 0),
                debug=level_counter.get('DEBUG', 0),
                by_level=level_counter,
                trend=trend,
            )
        except Exception as e:
            logger.warning(f"ClickHouse stats query failed, falling back: {e}")
            return None

    def get_error_clusters(self, filters: LogInsightFilter) -> ErrorClusterResponse:
        """Cluster recent errors by signature."""
        start_time, end_time = self._resolve_time_window(filters)

        # Try ClickHouse path
        ch_result = self._get_error_clusters_from_clickhouse(filters, start_time, end_time)
        if ch_result is not None:
            return ch_result

        # Fallback: file parsing
        logs = self.reader.read_logs(
            log_file=None,
            start_time=start_time,
            end_time=end_time,
            level=None,
            keyword=filters.keyword,
            request_id=filters.request_id,
            limit=100000,
            offset=0,
        )

        grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for log in logs:
            level = str(log.get('level', '')).upper()
            if level not in ('ERROR', 'WARNING'):
                continue
            if filters.level and filters.level.upper() != level:
                continue

            message = str(log.get('message', ''))
            signature = self.reader.parser.extract_error_signature(message)
            module = str(log.get('module', 'unknown'))
            key = (signature, module)

            if key not in grouped:
                grouped[key] = {
                    'signature': signature,
                    'count': 0,
                    'level': level,
                    'module': module,
                    'latest_time': log.get('timestamp') or datetime.now(),
                    'sample_message': message[:200],
                }

            grouped[key]['count'] += 1
            if (log.get('timestamp') or datetime.min) > grouped[key]['latest_time']:
                grouped[key]['latest_time'] = log.get('timestamp')
                grouped[key]['sample_message'] = message[:200]

            if level == 'ERROR':
                grouped[key]['level'] = 'ERROR'

        clusters = [ErrorClusterItem(**item) for item in grouped.values()]
        clusters.sort(key=lambda item: (item.level != 'ERROR', -item.count, item.latest_time), reverse=False)
        return ErrorClusterResponse(clusters=clusters[:filters.limit])

    def _get_error_clusters_from_clickhouse(self, filters: LogInsightFilter, start_time: datetime, end_time: datetime) -> Optional[ErrorClusterResponse]:
        """Query error clusters from ClickHouse. Returns None on failure."""
        ch = self._ch_client
        if ch is None:
            return None
        try:
            level_filter = filters.level or "ERROR,WARNING"
            level_list = [l.strip().upper() for l in level_filter.split(",")]
            # Whitelist: only allow known log levels
            allowed_levels = {"ERROR", "WARNING", "INFO", "DEBUG", "TRACE", "SUCCESS"}
            safe_levels = [l for l in level_list if l in allowed_levels]
            if not safe_levels:
                safe_levels = ["ERROR", "WARNING"]
            conditions = [
                "timestamp >= %(start_time)s",
                "timestamp <= %(end_time)s",
            ]
            params: Dict[str, Any] = {
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            # Use array parameter for level IN clause
            level_placeholders = []
            for i, lvl in enumerate(safe_levels):
                key = f"level_{i}"
                level_placeholders.append(f"%({key})s")
                params[key] = lvl
            conditions.append(f"level IN ({','.join(level_placeholders)})")
            if filters.keyword:
                conditions.append("message ILIKE %(keyword)s")
                params["keyword"] = f"%{filters.keyword}%"
            if filters.request_id and filters.request_id != "-":
                conditions.append("request_id = %(request_id)s")
                params["request_id"] = filters.request_id

            where = f" WHERE {' AND '.join(conditions)}"

            # Simple clustering by module + first 80 chars of message
            sql = (
                f"SELECT level, module, substring(message, 1, 80) AS sig, "
                f"count() AS cnt, max(timestamp) AS latest, any(message) AS sample "
                f"FROM system_structured_logs{where} "
                f"GROUP BY level, module, sig ORDER BY cnt DESC LIMIT %(limit)s"
            )
            params["limit"] = filters.limit
            rows = ch.execute(sql, params)

            clusters = []
            for row in rows:
                level, module, signature, count, latest, sample = row
                clusters.append(ErrorClusterItem(
                    signature=str(signature),
                    count=int(count),
                    level=str(level),
                    module=str(module),
                    latest_time=latest if isinstance(latest, datetime) else datetime.now(),
                    sample_message=str(sample)[:200],
                ))
            return ErrorClusterResponse(clusters=clusters)
        except Exception as e:
            logger.warning(f"ClickHouse error clusters query failed, falling back: {e}")
            return None

    def get_operation_timeline(self, filters: LogInsightFilter) -> OperationTimelineResponse:
        """Build a mixed timeline from logs and schedule execution history."""
        start_time, end_time = self._resolve_time_window(filters)

        # Try ClickHouse path for log items
        ch_items = self._get_timeline_from_clickhouse(filters, start_time, end_time)

        if ch_items is not None:
            # Merge with schedule items
            schedule_items = self._build_schedule_timeline_items(start_time=start_time, end_time=end_time)
            ch_items.extend(schedule_items)
            ch_items.sort(key=lambda item: item.timestamp, reverse=True)
            return OperationTimelineResponse(items=ch_items[:filters.limit])

        # Fallback: file parsing
        logs = self.reader.read_logs(
            log_file=None,
            start_time=start_time,
            end_time=end_time,
            level=filters.level,
            keyword=filters.keyword,
            request_id=filters.request_id,
            limit=min(2000, max(filters.limit * 8, 200)),
            offset=0,
        )

        items: List[OperationTimelineItem] = []
        for log in logs[: max(filters.limit * 4, 120)]:
            message = str(log.get('message', '')).strip()
            # Classify event type: middleware.* → 'middleware', otherwise 'log'
            event_type = 'middleware' if message.startswith('middleware.') else 'log'
            items.append(
                OperationTimelineItem(
                    timestamp=log.get('timestamp') or datetime.now(),
                    event_type=event_type,
                    level=str(log.get('level', 'INFO')).upper(),
                    module=str(log.get('module', 'unknown')),
                    summary=message[:140],
                    detail=message[:500],
                    request_id=str(log.get('request_id', '-') or '-'),
                )
            )

        schedule_items = self._build_schedule_timeline_items(start_time=start_time, end_time=end_time)
        items.extend(schedule_items)
        items.sort(key=lambda item: item.timestamp, reverse=True)
        return OperationTimelineResponse(items=items[:filters.limit])

    def _get_timeline_from_clickhouse(self, filters: LogInsightFilter, start_time: datetime, end_time: datetime) -> Optional[List[OperationTimelineItem]]:
        """Query timeline items from ClickHouse. Returns None on failure."""
        ch = self._ch_client
        if ch is None:
            return None
        try:
            conditions = [
                "timestamp >= %(start_time)s",
                "timestamp <= %(end_time)s",
            ]
            params: Dict[str, Any] = {
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if filters.level:
                conditions.append("level = %(level)s")
                params["level"] = filters.level.upper()
            if filters.keyword:
                conditions.append("message ILIKE %(keyword)s")
                params["keyword"] = f"%{filters.keyword}%"
            if filters.request_id and filters.request_id != "-":
                conditions.append("request_id = %(request_id)s")
                params["request_id"] = filters.request_id

            where = f" WHERE {' AND '.join(conditions)}"

            sql = (
                f"SELECT timestamp, level, module, message, request_id "
                f"FROM system_structured_logs{where} "
                f"ORDER BY timestamp DESC LIMIT %(limit)s"
            )
            params["limit"] = min(filters.limit * 4, 500)
            rows = ch.execute(sql, params)

            items = []
            for row in rows:
                ts, level, module, msg, request_id = row
                message = str(msg).strip()
                event_type = 'middleware' if message.startswith('middleware.') else 'log'
                items.append(OperationTimelineItem(
                    timestamp=ts if isinstance(ts, datetime) else datetime.now(),
                    event_type=event_type,
                    level=str(level),
                    module=str(module),
                    summary=message[:140],
                    detail=message[:500],
                    request_id=str(request_id or '-'),
                ))
            return items
        except Exception as e:
            logger.warning(f"ClickHouse timeline query failed, falling back: {e}")
            return None

    def get_log_files(self) -> List[LogFileInfo]:
        """Get list of all log files.

        Returns:
            List of log file info
        """
        files = self.reader.get_log_files()

        return [
            LogFileInfo(
                name=f['name'],
                size=f['size'],
                modified_time=f['modified_time'],
                line_count=f['line_count']
            )
            for f in files
        ]

    async def analyze_logs(self, request: LogAnalysisRequest, user_id: Optional[str] = None) -> LogAnalysisResponse:
        """Analyze logs with AI first and fallback to rule-based diagnosis."""
        source_entries: List[LogEntry] = request.log_entries

        if not source_entries:
            insight_filters = LogInsightFilter(
                level=request.level,
                start_time=request.start_time,
                end_time=request.end_time,
                keyword=request.query,
                window_hours=request.default_window_hours,
                limit=request.max_entries,
            )
            start_time, end_time = self._resolve_time_window(insight_filters)
            raw_logs = self.reader.read_logs(
                log_file=None,
                start_time=start_time,
                end_time=end_time,
                level=request.level,
                keyword=request.query,
                limit=request.max_entries,
                offset=0,
            )
            source_entries = [LogEntry(**item) for item in raw_logs]

        if not source_entries:
            return self._analyze_rule_based(source_entries)

        entry_dicts = [
            {
                "timestamp": item.timestamp.isoformat(),
                "level": item.level,
                "module": item.module,
                "message": item.message,
                "raw_line": item.raw_line,
            }
            for item in source_entries[: request.max_entries]
        ]

        try:
            ai_result = await self.ai_diagnosis_service.diagnose(
                log_entries=entry_dicts,
                user_query=request.user_query,
                context=request.context,
                include_code_context=request.include_code_context,
                user_id=user_id,
            )
            return self._merge_ai_result(source_entries, ai_result)
        except Exception as e:
            logger.error(f"AI diagnosis failed, fallback to rule-based analysis: {e}")
            return self._analyze_rule_based(source_entries)

    def _merge_ai_result(self, source_entries: List[LogEntry], ai_result: Dict[str, Any]) -> LogAnalysisResponse:
        """Normalize AI output into response schema."""
        base = self._analyze_rule_based(source_entries)

        root_causes_raw = ai_result.get('root_causes', [])
        root_causes = []
        for item in root_causes_raw:
            if isinstance(item, dict):
                root_causes.append(
                    LogRootCause(
                        title=str(item.get('title', '未命名根因')),
                        module=item.get('module'),
                        function=item.get('function'),
                        evidence=[str(v) for v in item.get('evidence', [])[:6]],
                        confidence=float(item.get('confidence', 0.5)),
                    )
                )

        fix_suggestions_raw = ai_result.get('fix_suggestions', [])
        fix_suggestions = []
        for item in fix_suggestions_raw:
            if isinstance(item, dict):
                priority = str(item.get('priority', 'medium')).lower()
                if priority not in ('low', 'medium', 'high'):
                    priority = 'medium'
                fix_suggestions.append(
                    LogFixSuggestion(
                        title=str(item.get('title', '修复建议')),
                        steps=[str(v) for v in item.get('steps', [])[:10]],
                        priority=priority,
                    )
                )

        risk_level = str(ai_result.get('risk_level', base.risk_level)).lower()
        if risk_level not in ('low', 'medium', 'high', 'critical'):
            risk_level = base.risk_level

        return LogAnalysisResponse(
            error_type=str(ai_result.get('error_type', base.error_type)),
            possible_causes=[str(v) for v in ai_result.get('possible_causes', base.possible_causes)[:10]],
            suggested_fixes=[str(v) for v in ai_result.get('suggested_fixes', base.suggested_fixes)[:10]],
            confidence=float(ai_result.get('confidence', base.confidence)),
            related_logs=[str(v) for v in ai_result.get('related_logs', base.related_logs)[:10]] or base.related_logs,
            summary=str(ai_result.get('summary', base.summary)),
            analysis_source='hybrid',
            root_causes=root_causes or base.root_causes,
            recent_operations=ai_result.get('recent_operations', base.recent_operations),
            fix_suggestions=fix_suggestions or base.fix_suggestions,
            risk_level=risk_level,
            impact_scope=str(ai_result.get('impact_scope', base.impact_scope)),
        )

    def _analyze_rule_based(self, source_entries: List[LogEntry]) -> LogAnalysisResponse:
        """Rule-based diagnosis used as primary fallback."""
        error_logs = [log for log in source_entries if str(log.level).upper() == 'ERROR']
        warning_logs = [log for log in source_entries if str(log.level).upper() == 'WARNING']

        if not error_logs and not warning_logs:
            return LogAnalysisResponse(
                error_type="No Error",
                possible_causes=["最近窗口未发现错误或告警日志"],
                suggested_fixes=["暂不需要额外操作，建议继续观察"],
                confidence=0.95,
                related_logs=[],
                summary="最近日志整体正常",
                analysis_source="rule_based",
                root_causes=[],
                recent_operations=[],
                fix_suggestions=[],
                risk_level="low",
                impact_scope="当前窗口未发现明显异常影响",
            )

        first_error = error_logs[0] if error_logs else warning_logs[0]
        error_type = self._extract_error_type(first_error.message)
        root_cause = LogRootCause(
            title=f"疑似{error_type}",
            module=first_error.module,
            function=None,
            evidence=[first_error.message[:240]],
            confidence=0.6 if error_logs else 0.45,
        )
        risk_level = "high" if len(error_logs) >= 5 else "medium"
        if len(error_logs) >= 10:
            risk_level = "critical"

        timeline_items = [
            {
                "timestamp": log.timestamp.isoformat(),
                "event_type": "log",
                "level": log.level,
                "module": log.module,
                "summary": log.message[:120],
            }
            for log in source_entries[:20]
        ]

        fix_items = [
            LogFixSuggestion(
                title="优先定位首个异常模块",
                steps=[
                    f"检查模块 `{first_error.module}` 最近发布与配置变更",
                    "对照错误堆栈定位异常调用路径",
                    "复现后补充单测/回归用例并验证修复",
                ],
                priority="high",
            )
        ]

        return LogAnalysisResponse(
            error_type=error_type,
            possible_causes=[
                "近期配置变更导致依赖行为不一致",
                "外部依赖超时或连接波动",
                "输入数据边界未覆盖，触发运行时异常",
            ],
            suggested_fixes=[
                "先按错误模块回放最近2小时操作与任务记录",
                "针对异常签名增加保护分支与重试/降级",
                "修复后观察同类错误频次是否下降",
            ],
            confidence=0.62,
            related_logs=[log.message[:120] for log in (error_logs or warning_logs)[:8]],
            summary=f"最近窗口发现 {len(error_logs)} 条错误、{len(warning_logs)} 条告警，重点关注 {first_error.module} 模块。",
            analysis_source="rule_based",
            root_causes=[root_cause],
            recent_operations=timeline_items,
            fix_suggestions=fix_items,
            risk_level=risk_level,
            impact_scope="可能影响最近批量任务、页面实时查询与相关接口稳定性",
        )

    def archive_logs(self, retention_days: int = 30) -> dict:
        """Archive old logs.

        Args:
            retention_days: Days to keep logs

        Returns:
            Archive result
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        archive_dir = self.log_dir / "archive"

        # Create archive directory
        archive_dir.mkdir(parents=True, exist_ok=True)

        archived_files = []

        # Get log files
        for filepath in self.log_dir.glob("*.log"):
            if filepath.is_file():
                try:
                    mtime = datetime.fromtimestamp(filepath.stat().st_mtime)

                    if mtime < cutoff_date:
                        # Archive the file
                        archive_name = f"{filepath.name}.{mtime.strftime('%Y%m%d')}.gz"
                        archive_path = archive_dir / archive_name

                        # Compress file
                        with open(filepath, 'rb') as f_in:
                            with gzip.open(archive_path, 'wb') as f_out:
                                f_out.writelines(f_in)

                        # Delete original file
                        filepath.unlink()

                        archived_files.append(archive_name)
                        logger.info(f"Archived {filepath.name} to {archive_name}")

                except Exception as e:
                    logger.error(f"Error archiving {filepath}: {e}")

        return {
            'status': 'success',
            'archived_count': len(archived_files),
            'archived_files': archived_files
        }

    def get_archives(self) -> List[LogFileInfo]:
        """Get list of archived log files.

        Returns:
            List of archive file info
        """
        archives = self.reader.get_archive_files()

        return [
            LogFileInfo(
                name=f['name'],
                size=f['size'],
                modified_time=f['modified_time'],
                line_count=f['line_count']
            )
            for f in archives
        ]

    def export_logs(
        self,
        filters: LogFilter,
        format: str = "csv"
    ) -> str:
        """Export filtered logs to file.

        Args:
            filters: Log filter parameters
            format: Export format (csv or json)

        Returns:
            Path to exported file
        """
        # Get all filtered logs
        all_logs = self.reader.read_logs(
            log_file=None,
            start_time=filters.start_time,
            end_time=filters.end_time,
            level=filters.level,
            keyword=filters.keyword,
            limit=100000  # Get all matching logs
        )

        # Create export directory
        export_dir = self.log_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs_export_{timestamp}.{format}"
        filepath = export_dir / filename

        # Export based on format
        if format.lower() == "csv":
            self._export_csv(all_logs, filepath)
        elif format.lower() == "json":
            self._export_json(all_logs, filepath)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported logs to {filepath}")
        return str(filepath)

    def _export_csv(self, logs: List[dict], filepath: Path):
        """Export logs to CSV format.

        Args:
            logs: List of log entries
            filepath: Output file path
        """
        import csv

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'level', 'module', 'message'])

            for log in logs:
                writer.writerow([
                    log['timestamp'].isoformat(),
                    log['level'],
                    log['module'],
                    log['message'].replace('\n', ' ')  # Remove newlines
                ])

    def _export_json(self, logs: List[dict], filepath: Path):
        """Export logs to JSON format.

        Args:
            logs: List of log entries
            filepath: Output file path
        """
        import json

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, default=str)

    def _resolve_time_window(self, filters: LogInsightFilter) -> Tuple[datetime, datetime]:
        """Resolve query window with fallback default window hours."""
        end_time = filters.end_time or datetime.now()
        start_time = filters.start_time or (end_time - timedelta(hours=filters.window_hours))
        if start_time > end_time:
            start_time, end_time = end_time, start_time
        return start_time, end_time

    def _build_schedule_timeline_items(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[OperationTimelineItem]:
        """Build timeline events from schedule execution history."""
        try:
            from stock_datasource.modules.datamanage.schedule_service import schedule_service
        except Exception as e:
            logger.warning(f"Failed to import schedule_service for timeline: {e}")
            return []

        total_days = max(1, min(30, (end_time.date() - start_time.date()).days + 1))
        history = schedule_service.get_history(days=total_days, limit=200)
        timeline: List[OperationTimelineItem] = []

        for record in history:
            started_at = record.get('started_at')
            if isinstance(started_at, str):
                try:
                    started_at = datetime.fromisoformat(started_at)
                except ValueError:
                    continue
            if not isinstance(started_at, datetime):
                continue

            if started_at < start_time or started_at > end_time:
                continue

            status = str(record.get('status', 'unknown')).lower()
            trigger_type = str(record.get('trigger_type', 'scheduled'))
            level = 'INFO'
            if status in ('failed', 'interrupted'):
                level = 'ERROR'
            elif status in ('skipped', 'stopping'):
                level = 'WARNING'

            summary = f"调度任务 {status}（{trigger_type}）"
            detail = (
                f"execution_id={record.get('execution_id', '')}, "
                f"plugins={record.get('completed_plugins', 0)}/{record.get('total_plugins', 0)}"
            )

            timeline.append(
                OperationTimelineItem(
                    timestamp=started_at,
                    event_type='schedule',
                    level=level,
                    module='scheduler',
                    summary=summary,
                    detail=detail,
                )
            )

        return timeline

    def _extract_error_type(self, error_message: str) -> str:
        """Extract error type from error message.

        Args:
            error_message: Error log message

        Returns:
            Error type string
        """
        # Simple heuristic: extract first line or common patterns
        message_lower = error_message.lower()

        if 'connection' in message_lower or 'timeout' in message_lower:
            return "ConnectionError"
        elif 'permission' in message_lower or 'access' in message_lower:
            return "AccessError"
        elif 'not found' in message_lower or 'missing' in message_lower:
            return "NotFoundError"
        elif 'value' in message_lower or 'type' in message_lower:
            return "ValueError"
        else:
            return "GeneralError"


# Global log service instance
_log_service: Optional[LogService] = None


def get_log_service(log_dir: str = "logs") -> LogService:
    """Get or create log service instance.

    Args:
        log_dir: Directory containing log files

    Returns:
        Log service instance
    """
    global _log_service
    if _log_service is None:
        _log_service = LogService(log_dir=log_dir)
    return _log_service
