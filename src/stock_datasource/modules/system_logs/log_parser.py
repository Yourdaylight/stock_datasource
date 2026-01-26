"""Log parser for parsing various log formats."""

import re
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LogParser:
    """Parser for system logs in various formats."""

    # Common log format patterns
    PATTERNS = [
        # Loguru format: 2026-01-26 10:30:45 | INFO     | name:function:line - message
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
        if not line or not line.strip():
            return None

        # Remove ANSI color codes
        cleaned_line = self._remove_ansi_codes(line)

        # Try each pattern
        for pattern in self.PATTERNS:
            match = pattern.match(cleaned_line)
            if match:
                return self._extract_fields(match, line, filename)

        # If no pattern matched, treat as raw message
        return {
            'timestamp': datetime.now(),
            'level': 'INFO',
            'module': self._get_module_from_filename(filename),
            'message': line,
            'raw_line': line
        }

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
        entries = []
        path = Path(filepath)

        if not path.exists():
            logger.warning(f"Log file not found: {filepath}")
            return entries

        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if max_lines and i >= max_lines:
                        break

                    entry = self.parse_line(line, path.name)
                    if entry:
                        entries.append(entry)

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

        # Pattern with timestamp, level, location, message (loguru format)
        if len(groups) == 4 and groups[1].strip().upper() in ('INFO', 'WARNING', 'ERROR', 'DEBUG'):
            timestamp_str, level, location, message = groups
            timestamp = self._parse_timestamp(timestamp_str)
            # Extract module from location (name:function:line)
            module = self._extract_module_from_location(location.strip())
            return {
                'timestamp': timestamp,
                'level': level.strip().upper(),
                'module': module,
                'message': message,
                'raw_line': line
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
                'raw_line': line
            }

        # Pattern with level, message only
        elif len(groups) == 2:
            level, message = groups
            return {
                'timestamp': datetime.now(),
                'level': level.upper(),
                'module': self._get_module_from_filename(filename),
                'message': message,
                'raw_line': line
            }

        return {
            'timestamp': datetime.now(),
            'level': 'INFO',
            'module': self._get_module_from_filename(filename),
            'message': line,
            'raw_line': line
        }

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
        all_logs = []

        # Get log files to read
        if log_file:
            log_files = [self.log_dir / log_file]
        else:
            log_files = list(self.log_dir.glob("*.log"))

        # Read all logs
        for filepath in log_files:
            if filepath.is_file():
                logs = self.parser.parse_file(str(filepath))
                all_logs.extend(logs)

        # Apply filters
        filtered = self._apply_filters(
            all_logs,
            start_time=start_time,
            end_time=end_time,
            level=level,
            keyword=keyword
        )

        # Sort by timestamp descending
        filtered.sort(key=lambda x: x['timestamp'], reverse=True)

        # Apply pagination
        return filtered[offset:offset + limit]

    def _apply_filters(
        self,
        logs: List[dict],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        keyword: Optional[str] = None
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

        if start_time:
            filtered = [log for log in filtered if log['timestamp'] >= start_time]

        if end_time:
            filtered = [log for log in filtered if log['timestamp'] <= end_time]

        if level:
            level_upper = level.upper()
            filtered = [log for log in filtered if log['level'] == level_upper]

        if keyword:
            keyword_lower = keyword.lower()
            filtered = [log for log in filtered if keyword_lower in log['message'].lower()]

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
