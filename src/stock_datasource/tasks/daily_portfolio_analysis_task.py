"""Daily portfolio analysis task for automated portfolio analysis."""

import logging
import asyncio
from datetime import datetime, date, time
from typing import List, Optional
import schedule
import threading
import time as time_module

logger = logging.getLogger(__name__)


class DailyPortfolioAnalysisTask:
    """Daily portfolio analysis task scheduler."""
    
    def __init__(self):
        self._is_running = False
        self._scheduler_thread = None
        self._analysis_service = None
        self._notification_service = None
        
        # Default schedule: 18:30 every day
        self.schedule_time = "18:30"
        self.enabled = True
    
    @property
    def analysis_service(self):
        """Lazy load analysis service."""
        if self._analysis_service is None:
            try:
                from stock_datasource.services.daily_analysis_service import get_daily_analysis_service
                self._analysis_service = get_daily_analysis_service()
            except Exception as e:
                logger.error(f"Failed to get analysis service: {e}")
        return self._analysis_service
    
    @property
    def notification_service(self):
        """Lazy load notification service."""
        if self._notification_service is None:
            try:
                from stock_datasource.services.notification_service import get_notification_service
                self._notification_service = get_notification_service()
            except Exception as e:
                logger.warning(f"Failed to get notification service: {e}")
        return self._notification_service
    
    def start(self):
        """Start the daily analysis task scheduler."""
        if self._is_running:
            logger.warning("Daily analysis task is already running")
            return
        
        logger.info(f"Starting daily portfolio analysis task (scheduled at {self.schedule_time})")
        
        # Clear any existing schedules
        schedule.clear()
        
        # Schedule daily analysis
        if self.enabled:
            schedule.every().day.at(self.schedule_time).do(self._run_daily_analysis_job)
            logger.info(f"Daily analysis scheduled at {self.schedule_time}")
        
        # Start scheduler thread
        self._is_running = True
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        
        logger.info("Daily portfolio analysis task started successfully")
    
    def stop(self):
        """Stop the daily analysis task scheduler."""
        if not self._is_running:
            logger.warning("Daily analysis task is not running")
            return
        
        logger.info("Stopping daily portfolio analysis task...")
        
        self._is_running = False
        schedule.clear()
        
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        
        logger.info("Daily portfolio analysis task stopped")
    
    def _run_scheduler(self):
        """Run the scheduler in a separate thread."""
        logger.info("Scheduler thread started")
        
        while self._is_running:
            try:
                schedule.run_pending()
                time_module.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time_module.sleep(60)
        
        logger.info("Scheduler thread stopped")
    
    def _run_daily_analysis_job(self):
        """Run daily analysis job (called by scheduler)."""
        logger.info("Daily analysis job triggered")
        
        try:
            # Run analysis in async context
            asyncio.run(self._execute_daily_analysis())
        except Exception as e:
            logger.error(f"Daily analysis job failed: {e}")
    
    async def _execute_daily_analysis(self):
        """Execute daily analysis for all users."""
        if not self.analysis_service:
            logger.error("Analysis service not available")
            return
        
        # Get list of users (for now, just default user)
        users = ["default_user"]  # In production, get from user service
        
        analysis_results = []
        
        for user_id in users:
            try:
                logger.info(f"Running daily analysis for user: {user_id}")
                
                # Run analysis
                report = await self.analysis_service.run_daily_analysis(user_id)
                
                if report.status == 'completed':
                    logger.info(f"Daily analysis completed for user {user_id}")
                    analysis_results.append({
                        "user_id": user_id,
                        "status": "success",
                        "report_id": report.id
                    })
                    
                    # Send notification if available
                    await self._send_analysis_notification(user_id, report)
                    
                else:
                    logger.warning(f"Daily analysis failed for user {user_id}: {report.status}")
                    analysis_results.append({
                        "user_id": user_id,
                        "status": "failed",
                        "error": f"Analysis status: {report.status}"
                    })
                
            except Exception as e:
                logger.error(f"Failed to run daily analysis for user {user_id}: {e}")
                analysis_results.append({
                    "user_id": user_id,
                    "status": "error",
                    "error": str(e)
                })
        
        # Log summary
        successful = len([r for r in analysis_results if r["status"] == "success"])
        total = len(analysis_results)
        logger.info(f"Daily analysis completed: {successful}/{total} users successful")
        
        # Send summary notification to admin if needed
        if total > 0:
            await self._send_admin_summary(analysis_results)
    
    async def _send_analysis_notification(self, user_id: str, report):
        """Send analysis notification to user."""
        if not self.notification_service:
            logger.debug("Notification service not available")
            return
        
        try:
            # Extract key insights from report
            summary = self._extract_report_summary(report)
            
            # Send notification
            await self.notification_service.send_analysis_notification(
                user_id=user_id,
                report_date=report.report_date,
                summary=summary
            )
            
            logger.info(f"Analysis notification sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send analysis notification to {user_id}: {e}")
    
    async def _send_admin_summary(self, analysis_results: List[dict]):
        """Send analysis summary to admin."""
        if not self.notification_service:
            return
        
        try:
            successful = len([r for r in analysis_results if r["status"] == "success"])
            failed = len([r for r in analysis_results if r["status"] != "success"])
            
            summary = {
                "date": date.today().isoformat(),
                "total_users": len(analysis_results),
                "successful": successful,
                "failed": failed,
                "results": analysis_results
            }
            
            await self.notification_service.send_admin_summary(summary)
            logger.info("Admin summary sent")
            
        except Exception as e:
            logger.error(f"Failed to send admin summary: {e}")
    
    def _extract_report_summary(self, report) -> dict:
        """Extract key summary from analysis report."""
        try:
            import json
            
            # Parse portfolio summary
            portfolio_summary = {}
            if report.portfolio_summary:
                try:
                    portfolio_summary = json.loads(report.portfolio_summary)
                except:
                    pass
            
            # Parse recommendations
            recommendations = []
            if report.recommendations:
                try:
                    recs = json.loads(report.recommendations)
                    if isinstance(recs, list):
                        recommendations = [r.get("description", "") for r in recs[:3]]  # Top 3
                except:
                    pass
            
            return {
                "total_value": portfolio_summary.get("total_value", 0),
                "total_profit": portfolio_summary.get("total_profit", 0),
                "profit_rate": portfolio_summary.get("profit_rate", 0),
                "position_count": portfolio_summary.get("position_count", 0),
                "top_recommendations": recommendations,
                "ai_insights": report.ai_insights[:200] + "..." if len(report.ai_insights) > 200 else report.ai_insights
            }
            
        except Exception as e:
            logger.error(f"Failed to extract report summary: {e}")
            return {"error": "Failed to parse report"}
    
    async def run_manual_analysis(self, user_id: str = "default_user", 
                                 analysis_date: Optional[date] = None) -> dict:
        """Run manual analysis (for testing or on-demand execution)."""
        if not self.analysis_service:
            return {"error": "Analysis service not available"}
        
        try:
            logger.info(f"Running manual analysis for user: {user_id}")
            
            report = await self.analysis_service.run_daily_analysis(user_id, analysis_date)
            
            return {
                "status": "success",
                "user_id": user_id,
                "report_id": report.id,
                "report_status": report.status,
                "analysis_date": report.report_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Manual analysis failed for user {user_id}: {e}")
            return {
                "status": "error",
                "user_id": user_id,
                "error": str(e)
            }
    
    def update_schedule(self, schedule_time: str):
        """Update analysis schedule time."""
        try:
            # Validate time format
            datetime.strptime(schedule_time, "%H:%M")
            
            self.schedule_time = schedule_time
            
            # Restart scheduler if running
            if self._is_running:
                self.stop()
                self.start()
            
            logger.info(f"Analysis schedule updated to {schedule_time}")
            
        except ValueError:
            logger.error(f"Invalid time format: {schedule_time}. Use HH:MM format.")
            raise
    
    def enable_task(self):
        """Enable the daily analysis task."""
        self.enabled = True
        logger.info("Daily analysis task enabled")
    
    def disable_task(self):
        """Disable the daily analysis task."""
        self.enabled = False
        schedule.clear()
        logger.info("Daily analysis task disabled")
    
    def get_status(self) -> dict:
        """Get current task status."""
        return {
            "is_running": self._is_running,
            "enabled": self.enabled,
            "schedule_time": self.schedule_time,
            "next_run": self._get_next_run_time(),
            "thread_alive": self._scheduler_thread.is_alive() if self._scheduler_thread else False
        }
    
    def _get_next_run_time(self) -> Optional[str]:
        """Get next scheduled run time."""
        try:
            jobs = schedule.jobs
            if jobs:
                next_run = min(job.next_run for job in jobs)
                return next_run.isoformat()
        except:
            pass
        return None


# Global task instance
_daily_analysis_task = None


def get_daily_analysis_task() -> DailyPortfolioAnalysisTask:
    """Get daily analysis task instance."""
    global _daily_analysis_task
    if _daily_analysis_task is None:
        _daily_analysis_task = DailyPortfolioAnalysisTask()
    return _daily_analysis_task


# Convenience functions
async def start_daily_analysis_scheduler():
    """Start the daily analysis scheduler."""
    task = get_daily_analysis_task()
    task.start()


async def stop_daily_analysis_scheduler():
    """Stop the daily analysis scheduler."""
    task = get_daily_analysis_task()
    task.stop()


async def run_manual_analysis(user_id: str = "default_user") -> dict:
    """Run manual analysis for testing."""
    task = get_daily_analysis_task()
    return await task.run_manual_analysis(user_id)