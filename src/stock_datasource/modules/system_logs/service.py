"""Service for system logs management."""

import gzip
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .schemas import (
    LogEntry,
    LogFilter,
    LogFileInfo,
    LogAnalysisRequest,
    LogAnalysisResponse,
    LogListResponse,
)
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

    def get_logs(self, filters: LogFilter) -> LogListResponse:
        """Get filtered logs.

        Args:
            filters: Log filter parameters

        Returns:
            Log list response
        """
        # Get filtered logs
        logs = self.reader.read_logs(
            log_file=None,  # Read all log files
            start_time=filters.start_time,
            end_time=filters.end_time,
            level=filters.level,
            keyword=filters.keyword,
            limit=filters.page_size,
            offset=(filters.page - 1) * filters.page_size
        )

        # Get total count
        total_logs = self.reader.read_logs(
            start_time=filters.start_time,
            end_time=filters.end_time,
            level=filters.level,
            keyword=filters.keyword,
            limit=100000  # Large limit for count
        )

        # Convert to LogEntry objects
        log_entries = [
            LogEntry(**log) for log in logs
        ]

        return LogListResponse(
            logs=log_entries,
            total=len(total_logs),
            page=filters.page,
            page_size=filters.page_size
        )

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

    def analyze_logs(self, request: LogAnalysisRequest) -> LogAnalysisResponse:
        """Analyze logs using AI.

        Args:
            request: Analysis request with log entries

        Returns:
            Analysis response
        """
        # For now, return a simple response
        # TODO: Integrate with AI agent
        error_logs = [log for log in request.log_entries if log.level == 'ERROR']

        if not error_logs:
            return LogAnalysisResponse(
                error_type="No Error",
                possible_causes=["No error logs found"],
                suggested_fixes=["No action needed"],
                confidence=1.0,
                related_logs=[]
            )

        # Extract first error as sample
        first_error = error_logs[0]
        error_type = self._extract_error_type(first_error.message)

        return LogAnalysisResponse(
            error_type=error_type,
            possible_causes=[
                "Check system logs for more details",
                "Verify service dependencies",
                "Review recent configuration changes"
            ],
            suggested_fixes=[
                "Restart affected service",
                "Check system resources",
                "Review error logs for specific actions"
            ],
            confidence=0.5,
            related_logs=[log.message[:100] + "..." for log in error_logs[:5]]
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
