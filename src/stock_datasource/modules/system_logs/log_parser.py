"""Log parser for parsing various log formats."""

import re
import logging
from datetime import datetime
from datetime import timedelta
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LogParser:
    """Parser for system logs in various formats."""

    # Common log format patterns
    PATTERNS = [
        # NEW Loguru format with request_id, user_id & middleware_trace_id:
        # 2026-01-26 10:30:45.123 | INFO | abc123 | user1 | mwid123 | name:function:line - message
        re.compile(
            r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+\|\s*(\w+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*-\s*(.*)$'
        ),
        # OLD Loguru format with request_id & user_id (6 groups):
        # 2026-01-26 10:30:45.123 | INFO | abc123 | user1 | name:function:line - message
        re.compile(
            r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+\|\s*(\w+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*-\s*(.*)$'
        ),
        # OLDER Loguru format: 2026-01-26 10:30:45 | INFO     | name:function:line - message
        re.compile(
            r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\|\s*(\w+)\s*\|\s*([^|]+?)\s*-\s*(.*)$'
        ),
        # Python logging format: 2026-01-26 10:30:45,123 INFO module:message
        re.compile(
            r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+(\w+)\s+(\w+?):\s*(.*)$'
        ),
        # Standard format: 2026-01-26 10:30:45 [INFO] module - message
        re.compile(
            r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+(\w+)\s*-\s*(.*)$'
        ),
        # Simple format: [INFO] message
        re.compile(r'^\[(\w+)\]\s+(.*)$'),
    ]

    # Timestamp formats to try
    TIMESTAMP_FORMATS = [
        "%Y-%m-%d %H:%M:%S,%f",  # 2026-01-26 10:30:45,123
        "%Y-%m-%d %H:%M:%S",     # 2026-01-26 10:30:45
        "%Y-%m-%d %H:%M:%S.%f",  # 2026-01-26 10:30:45.123
    ]

    ERROR_SIGNATURE_PATTERNS = [
        re.compile(r'(\w+(?:Error|Exception|Timeout|Refused|Unavailable))'),
        re.compile(r'\b(Traceback)\b'),
    ]

    def __init__(self):
        self.module_mapping = {
            'backend.log': 'backend',
            'worker.log': 'worker',
            'server.log': 'server',
            'application.log': 'application',
        }

    def parse_line(self, line: str, filename: str = "unknown") -> Optional[dict]:
        """Parse a single log line.

        Args:
            line: Raw log line
            filename: Name of the log file (for module detection)

        Returns:
            Dict with keys: timestamp, level, module, message, raw_line
            or None if line cannot be parsed
        """
        parsed = self._parse_line_strict(line, filename)
        if parsed:
            return parsed

        if not line or not line.strip():
            return None

        return {
            'timestamp': datetime.now(),
            'level': 'INFO',
            'module': self._get_module_from_filename(filename),
            'message': line.strip(),
            'raw_line': line,
            'request_id': '-',
            'user_id': '-',
            'middleware_trace_id': '-',
        }

    def _parse_line_strict(self, line: str, filename: str = "unknown") -> Optional[dict]:
        """Parse line only when line matches known log patterns."""
        if not line or not line.strip():
            return None

        cleaned_line = self._remove_ansi_codes(line)

        for pattern in self.PATTERNS:
            match = pattern.match(cleaned_line)
            if match:
                return self._extract_fields(match, line, filename)

        return None

    def parse_file(
        self,
        filepath: str,
        max_lines: Optional[int] = None
    ) -> List[dict]:
        """Parse entire log file.

        Args:
            filepath: Path to log file
            max_lines: Maximum number of lines to parse (None for all)

        Returns:
            List of parsed log entries
        """
        entries: List[dict] = []
        path = Path(filepath)

        if not path.exists():
            logger.warning(f"Log file not found: {filepath}")
            return entries

        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if max_lines and i >= max_lines:
                        break

                    strict_entry = self._parse_line_strict(line, path.name)
                    if strict_entry:
                        entries.append(strict_entry)
                        continue

                    if self._is_continuation_line(line) and entries:
                        entries[-1]['message'] = f"{entries[-1]['message']}\n{line.rstrip()}"
                        entries[-1]['raw_line'] = f"{entries[-1]['raw_line']}\n{line.rstrip()}"
                        continue

                    fallback_entry = self.parse_line(line, path.name)
                    if fallback_entry:
                        entries.append(fallback_entry)

        except Exception as e:
            logger.error(f"Error parsing log file {filepath}: {e}")

        return entries

    def _extract_fields(self, match: re.Match, line: str, filename: str) -> dict:
        """Extract fields from regex match.

        Args:
            match: Regex match object
            line: Original log line
            filename: Log filename

        Returns:
            Parsed log entry dict
        """
        groups = match.groups()

        # NEWEST format with request_id, user_id & middleware_trace_id: 7 groups
        # timestamp, level, request_id, user_id, middleware_trace_id, location, message
        if len(groups) == 7 and groups[1].strip().upper() in ('INFO', 'WARNING', 'ERROR', 'DEBUG', 'TRACE', 'SUCCESS'):
            timestamp_str, level, request_id, user_id, middleware_trace_id, location, message = groups
            timestamp = self._parse_timestamp(timestamp_str)
            module = self._extract_module_from_location(location.strip())
            return {
                'timestamp': timestamp,
                'level': level.strip().upper(),
                'module': module,
                'message': message,
                'raw_line': line,
                'request_id': request_id.strip(),
                'user_id': user_id.strip(),
                'middleware_trace_id': middleware_trace_id.strip(),
            }

        # OLD format with request_id & user_id: 6 groups
        # timestamp, level, request_id, user_id, location, message
        if len(groups) == 6 and groups[1].strip().upper() in ('INFO', 'WARNING', 'ERROR', 'DEBUG', 'TRACE', 'SUCCESS'):
            timestamp_str, level, request_id, user_id, location, message = groups
            timestamp = self._parse_timestamp(timestamp_str)
            module = self._extract_module_from_location(location.strip())
            return {
                'timestamp': timestamp,
                'level': level.strip().upper(),
                'module': module,
                'message': message,
                'raw_line': line,
                'request_id': request_id.strip(),
                'user_id': user_id.strip(),
                'middleware_trace_id': '-',
            }

        # OLD Loguru format: 4 groups — timestamp, level, location, message
        if len(groups) == 4 and groups[1].strip().upper() in ('INFO', 'WARNING', 'ERROR', 'DEBUG', 'TRACE', 'SUCCESS'):
            timestamp_str, level, location, message = groups
            timestamp = self._parse_timestamp(timestamp_str)
            module = self._extract_module_from_location(location.strip())
            return {
                'timestamp': timestamp,
                'level': level.strip().upper(),
                'module': module,
                'message': message,
                'raw_line': line,
                'request_id': '-',
                'user_id': '-',
                'middleware_trace_id': '-',
            }

        # Pattern with timestamp, level, module, message
        if len(groups) == 4 and groups[1].upper() in ('INFO', 'WARNING', 'ERROR', 'DEBUG'):
            timestamp_str, level, module, message = groups
            timestamp = self._parse_timestamp(timestamp_str)
            return {
                'timestamp': timestamp,
                'level': level.upper(),
                'module': module,
                'message': message,
                'raw_line': line,
                'request_id': '-',
                'user_id': '-',
                'middleware_trace_id': '-',
            }

        # Pattern with level, message only
        elif len(groups) == 2:
            level, message = groups
            return {
                'timestamp': datetime.now(),
                'level': level.upper(),
                'module': self._get_module_from_filename(filename),
                'message': message,
                'raw_line': line,
                'request_id': '-',
                'user_id': '-',
                'middleware_trace_id': '-',
            }

        return {
            'timestamp': datetime.now(),
            'level': 'INFO',
            'module': self._get_module_from_filename(filename),
            'message': line,
            'raw_line': line,
            'request_id': '-',
            'user_id': '-',
            'middleware_trace_id': '-',
        }

    def _is_continuation_line(self, line: str) -> bool:
        """Check whether a line is likely a continuation (stack trace/details)."""
        stripped = line.lstrip()
        if not stripped:
            return False

        if line.startswith(" ") or line.startswith("\t"):
            return True

        return stripped.startswith("File ") or stripped.startswith("Traceback") or stripped.startswith("During handling")

    def extract_error_signature(self, message: str) -> str:
        """Extract stable error signature for clustering."""
        if not message:
            return "UnknownError"

        first_line = message.splitlines()[0]
        for pattern in self.ERROR_SIGNATURE_PATTERNS:
            match = pattern.search(message)
            if match:
                return match.group(1)

        compact = first_line.strip()
        return compact[:120] if compact else "UnknownError"

    def _extract_module_from_location(self, location: str) -> str:
        """Extract module name from location string.

        Args:
            location: Location string in format "name:function:line"

        Returns:
            Module name
        """
        # Split by colon to get the name part
        parts = location.split(':')
        if parts:
            name = parts[0]
            # Extract the last part (e.g., "stock_datasource.services.task_queue" -> "task_queue")
            module_parts = name.split('.')
            if module_parts:
                return module_parts[-1]
        return 'unknown'

    def _remove_ansi_codes(self, text: str) -> str:
        """Remove ANSI color codes from text.

        Args:
            text: Text with ANSI codes

        Returns:
            Text without ANSI codes
        """
        # ANSI escape sequences: \x1B[ followed by any characters until m
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string.

        Args:
            timestamp_str: Timestamp string

        Returns:
            datetime object (or current time if parsing fails)
        """
        for fmt in self.TIMESTAMP_FORMATS:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        # If all formats fail, return current time
        return datetime.now()

    def _get_module_from_filename(self, filename: str) -> str:
        """Extract module name from filename.

        Args:
            filename: Log filename

        Returns:
            Module name or 'unknown'
        """
        return self.module_mapping.get(filename, 'unknown')


class LogFileReader:
    """Reader for log files with caching."""

    def __init__(self, log_dir: str = "logs"):
        """Initialize log file reader.

        Args:
            log_dir: Directory containing log files
        """
        self.log_dir = Path(log_dir)
        self.parser = LogParser()
        self.cache = {}  # Simple in-memory cache

    def read_logs(
        self,
        log_file: str = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        request_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """Read and filter logs.

        Args:
            log_file: Specific log file to read (None for all)
            start_time: Filter logs after this time
            end_time: Filter logs before this time
            level: Filter by log level
            keyword: Filter by keyword in message
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            Filtered list of log entries
        """
        matched_logs = []

        for filepath in self._resolve_log_files(
            log_file=log_file,
            start_time=start_time,
            end_time=end_time,
        ):
            if filepath.is_file():
                logs = self.parser.parse_file(str(filepath))
                for log in logs:
                    if self._matches_filters(
                        log,
                        start_time=start_time,
                        end_time=end_time,
                        level=level,
                        keyword=keyword,
                        request_id=request_id,
                    ):
                        matched_logs.append(log)

        # Sort by timestamp descending
        matched_logs.sort(key=lambda x: x['timestamp'], reverse=True)

        # Apply pagination
        return matched_logs[offset:offset + limit]

    def _resolve_log_files(
        self,
        log_file: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Path]:
        """Return candidate log files ordered from newest to oldest."""
        if log_file:
            return [self.log_dir / log_file]

        if not self.log_dir.exists():
            return []

        candidates = []
        oldest_relevant_mtime = start_time - timedelta(days=1) if start_time else None

        for filepath in self.log_dir.glob("*.log"):
            if not filepath.is_file():
                continue
            try:
                modified_time = datetime.fromtimestamp(filepath.stat().st_mtime)
            except OSError:
                continue

            if oldest_relevant_mtime and modified_time < oldest_relevant_mtime:
                continue

            candidates.append((modified_time, filepath))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [filepath for _, filepath in candidates]

    def _matches_filters(
        self,
        log: dict,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> bool:
        """Check whether a single log entry matches the given filters."""
        if start_time and log['timestamp'] < start_time:
            return False

        if end_time and log['timestamp'] > end_time:
            return False

        if level and log['level'] != level.upper():
            return False

        if keyword and keyword.lower() not in log['message'].lower():
            return False

        if request_id and str(log.get('request_id', '-')).strip() != request_id.strip():
            return False

        return True

    def _apply_filters(
        self,
        logs: List[dict],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[dict]:
        """Apply filters to log list.

        Args:
            logs: List of log entries
            start_time: Filter logs after this time
            end_time: Filter logs before this time
            level: Filter by log level
            keyword: Filter by keyword in message

        Returns:
            Filtered list of log entries
        """
        filtered = logs

        filtered = [
            log for log in filtered
            if self._matches_filters(
                log,
                start_time=start_time,
                end_time=end_time,
                level=level,
                keyword=keyword,
                request_id=request_id,
            )
        ]

        return filtered

    def get_log_files(self) -> List[dict]:
        """Get list of all log files.

        Returns:
            List of file info dicts
        """
        files = []

        if not self.log_dir.exists():
            return files

        for filepath in self.log_dir.glob("*.log"):
            if filepath.is_file():
                try:
                    stat = filepath.stat()
                    # Estimate line count (rough estimate: average 200 chars per line)
                    estimated_lines = stat.st_size // 200

                    files.append({
                        'name': filepath.name,
                        'size': stat.st_size,
                        'modified_time': datetime.fromtimestamp(stat.st_mtime),
                        'line_count': estimated_lines
                    })
                except Exception as e:
                    logger.error(f"Error getting file info for {filepath}: {e}")

        # Sort by modified time descending
        files.sort(key=lambda x: x['modified_time'], reverse=True)

        return files

    def get_archive_files(self) -> List[dict]:
        """Get list of archived log files.

        Returns:
            List of archive file info dicts
        """
        archive_dir = self.log_dir / "archive"
        files = []

        if not archive_dir.exists():
            return files

        for filepath in archive_dir.glob("*.gz"):
            if filepath.is_file():
                try:
                    stat = filepath.stat()
                    files.append({
                        'name': filepath.name,
                        'size': stat.st_size,
                        'modified_time': datetime.fromtimestamp(stat.st_mtime),
                        'line_count': 0  # Cannot estimate without decompressing
                    })
                except Exception as e:
                    logger.error(f"Error getting archive info for {filepath}: {e}")

        # Sort by modified time descending
        files.sort(key=lambda x: x['modified_time'], reverse=True)

        return files
