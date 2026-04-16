"""Notification service for portfolio analysis alerts and reports."""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications about portfolio analysis."""

    def __init__(self):
        self._email_config = {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "",  # Configure in production
            "password": "",  # Configure in production
            "from_email": "portfolio-analysis@example.com",
        }
        self._enabled = False  # Disable by default for demo

    async def send_analysis_notification(
        self, user_id: str, report_date: date, summary: dict[str, Any]
    ):
        """Send daily analysis notification to user."""
        if not self._enabled:
            logger.debug("Notifications disabled, skipping analysis notification")
            return

        try:
            # Get user email (mock for now)
            user_email = await self._get_user_email(user_id)

            if not user_email:
                logger.warning(f"No email found for user {user_id}")
                return

            # Generate notification content
            subject = f"每日投资组合分析报告 - {report_date}"
            content = self._generate_analysis_email_content(summary, report_date)

            # Send email
            await self._send_email(user_email, subject, content)

            logger.info(f"Analysis notification sent to {user_id} ({user_email})")

        except Exception as e:
            logger.error(f"Failed to send analysis notification: {e}")

    async def send_alert_notification(self, user_id: str, alert_data: dict[str, Any]):
        """Send alert notification to user."""
        if not self._enabled:
            logger.debug("Notifications disabled, skipping alert notification")
            return

        try:
            user_email = await self._get_user_email(user_id)

            if not user_email:
                logger.warning(f"No email found for user {user_id}")
                return

            # Generate alert content
            subject = f"持仓预警提醒 - {alert_data.get('ts_code', 'Unknown')}"
            content = self._generate_alert_email_content(alert_data)

            # Send email
            await self._send_email(user_email, subject, content)

            logger.info(f"Alert notification sent to {user_id}")

        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")

    async def send_admin_summary(self, summary: dict[str, Any]):
        """Send daily analysis summary to admin."""
        if not self._enabled:
            logger.debug("Notifications disabled, skipping admin summary")
            return

        try:
            admin_email = "admin@example.com"  # Configure in production

            subject = f"每日分析任务汇总 - {summary.get('date', 'Unknown')}"
            content = self._generate_admin_summary_content(summary)

            await self._send_email(admin_email, subject, content)

            logger.info("Admin summary sent")

        except Exception as e:
            logger.error(f"Failed to send admin summary: {e}")

    async def send_risk_warning(self, user_id: str, risk_data: dict[str, Any]):
        """Send risk warning notification."""
        if not self._enabled:
            logger.debug("Notifications disabled, skipping risk warning")
            return

        try:
            user_email = await self._get_user_email(user_id)

            if not user_email:
                return

            subject = "投资组合风险预警"
            content = self._generate_risk_warning_content(risk_data)

            await self._send_email(user_email, subject, content)

            logger.info(f"Risk warning sent to {user_id}")

        except Exception as e:
            logger.error(f"Failed to send risk warning: {e}")

    def enable_notifications(self, email_config: dict[str, str] | None = None):
        """Enable notifications with optional email configuration."""
        if email_config:
            self._email_config.update(email_config)

        self._enabled = True
        logger.info("Notifications enabled")

    def disable_notifications(self):
        """Disable notifications."""
        self._enabled = False
        logger.info("Notifications disabled")

    async def _get_user_email(self, user_id: str) -> str | None:
        """Get user email address."""
        # Mock implementation - in production, get from user service
        user_emails = {"default_user": "user@example.com"}
        return user_emails.get(user_id)

    async def _send_email(self, to_email: str, subject: str, content: str):
        """Send email notification."""
        if not self._email_config.get("username") or not self._email_config.get(
            "password"
        ):
            logger.debug(f"Email not configured, would send: {subject} to {to_email}")
            return

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self._email_config["from_email"]
            msg["To"] = to_email
            msg["Subject"] = subject

            # Add content
            msg.attach(MIMEText(content, "html", "utf-8"))

            # Send email
            with smtplib.SMTP(
                self._email_config["smtp_server"], self._email_config["smtp_port"]
            ) as server:
                server.starttls()
                server.login(
                    self._email_config["username"], self._email_config["password"]
                )
                server.send_message(msg)

            logger.info(f"Email sent to {to_email}")

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            raise

    def _generate_analysis_email_content(
        self, summary: dict[str, Any], report_date: date
    ) -> str:
        """Generate email content for analysis notification."""
        total_value = summary.get("total_value", 0)
        total_profit = summary.get("total_profit", 0)
        profit_rate = summary.get("profit_rate", 0)
        position_count = summary.get("position_count", 0)
        recommendations = summary.get("top_recommendations", [])
        ai_insights = summary.get("ai_insights", "")

        content = f"""
        <html>
        <body>
            <h2>每日投资组合分析报告</h2>
            <p><strong>分析日期：</strong>{report_date}</p>
            
            <h3>投资组合概览</h3>
            <ul>
                <li><strong>总市值：</strong>¥{total_value:,.2f}</li>
                <li><strong>总盈亏：</strong>¥{total_profit:,.2f}</li>
                <li><strong>收益率：</strong>{profit_rate:.2f}%</li>
                <li><strong>持仓数量：</strong>{position_count}只</li>
            </ul>
            
            <h3>主要建议</h3>
            <ul>
        """

        for rec in recommendations[:3]:
            content += f"<li>{rec}</li>"

        content += f"""
            </ul>
            
            <h3>AI分析洞察</h3>
            <p>{ai_insights}</p>
            
            <hr>
            <p><small>此邮件由投资组合分析系统自动发送，请勿回复。</small></p>
        </body>
        </html>
        """

        return content

    def _generate_alert_email_content(self, alert_data: dict[str, Any]) -> str:
        """Generate email content for alert notification."""
        ts_code = alert_data.get("ts_code", "Unknown")
        alert_type = alert_data.get("alert_type", "Unknown")
        condition_value = alert_data.get("condition_value", 0)
        current_value = alert_data.get("current_value", 0)
        message = alert_data.get("message", "")

        alert_type_names = {
            "price_high": "价格上限预警",
            "price_low": "价格下限预警",
            "profit_target": "止盈预警",
            "stop_loss": "止损预警",
        }

        alert_name = alert_type_names.get(alert_type, alert_type)

        content = f"""
        <html>
        <body>
            <h2>持仓预警提醒</h2>
            
            <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px;">
                <h3>⚠️ {alert_name}</h3>
                <p><strong>股票代码：</strong>{ts_code}</p>
                <p><strong>预警条件：</strong>{condition_value}</p>
                <p><strong>当前值：</strong>{current_value}</p>
                {f"<p><strong>预警消息：</strong>{message}</p>" if message else ""}
            </div>
            
            <p>请及时关注市场变化，根据投资策略做出相应调整。</p>
            
            <hr>
            <p><small>此邮件由投资组合监控系统自动发送，请勿回复。</small></p>
        </body>
        </html>
        """

        return content

    def _generate_admin_summary_content(self, summary: dict[str, Any]) -> str:
        """Generate email content for admin summary."""
        analysis_date = summary.get("date", "Unknown")
        total_users = summary.get("total_users", 0)
        successful = summary.get("successful", 0)
        failed = summary.get("failed", 0)
        results = summary.get("results", [])

        content = f"""
        <html>
        <body>
            <h2>每日分析任务汇总</h2>
            <p><strong>执行日期：</strong>{analysis_date}</p>
            
            <h3>执行统计</h3>
            <ul>
                <li><strong>总用户数：</strong>{total_users}</li>
                <li><strong>成功：</strong>{successful}</li>
                <li><strong>失败：</strong>{failed}</li>
                <li><strong>成功率：</strong>{(successful / total_users * 100):.1f}%</li>
            </ul>
            
            <h3>详细结果</h3>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr>
                    <th>用户ID</th>
                    <th>状态</th>
                    <th>备注</th>
                </tr>
        """

        for result in results:
            status_color = "green" if result["status"] == "success" else "red"
            note = result.get("report_id", result.get("error", ""))
            content += f"""
                <tr>
                    <td>{result["user_id"]}</td>
                    <td style="color: {status_color};">{result["status"]}</td>
                    <td>{note}</td>
                </tr>
            """

        content += """
            </table>
            
            <hr>
            <p><small>系统管理员邮件</small></p>
        </body>
        </html>
        """

        return content

    def _generate_risk_warning_content(self, risk_data: dict[str, Any]) -> str:
        """Generate email content for risk warning."""
        risk_level = risk_data.get("risk_level", "Unknown")
        risk_score = risk_data.get("risk_score", 0)
        warnings = risk_data.get("warnings", [])
        recommendations = risk_data.get("recommendations", [])

        content = f"""
        <html>
        <body>
            <h2>投资组合风险预警</h2>
            
            <div style="background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px;">
                <h3>🚨 风险等级：{risk_level}</h3>
                <p><strong>风险评分：</strong>{risk_score}/100</p>
            </div>
            
            <h3>风险提示</h3>
            <ul>
        """

        for warning in warnings:
            content += f"<li>{warning}</li>"

        content += """
            </ul>
            
            <h3>建议措施</h3>
            <ul>
        """

        for rec in recommendations:
            content += f"<li>{rec}</li>"

        content += """
            </ul>
            
            <p>请及时评估投资组合风险，采取适当的风险控制措施。</p>
            
            <hr>
            <p><small>此邮件由风险监控系统自动发送，请勿回复。</small></p>
        </body>
        </html>
        """

        return content


# Global service instance
_notification_service = None


def get_notification_service() -> NotificationService:
    """Get notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
