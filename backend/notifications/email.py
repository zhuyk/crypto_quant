"""
邮件通知
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """邮件配置"""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    from_email: str
    use_tls: bool = True


class EmailNotifier:
    """
    邮件通知
    
    支持:
    - 文本邮件
    - HTML 邮件
    - 附件
    - 批量发送
    """
    
    def __init__(self, config: EmailConfig):
        """
        Args:
            config: 邮件配置
        """
        self.config = config
    
    def send_text(
        self,
        to_emails: List[str],
        subject: str,
        content: str,
        cc_emails: Optional[List[str]] = None,
    ) -> bool:
        """
        发送文本邮件
        
        Args:
            to_emails: 收件人列表
            subject: 主题
            content: 内容
            cc_emails: 抄送列表
            
        Returns:
            bool: 是否成功
        """
        return self._send_email(to_emails, subject, content, html=False, cc_emails=cc_emails)
    
    def send_html(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        cc_emails: Optional[List[str]] = None,
    ) -> bool:
        """
        发送 HTML 邮件
        
        Args:
            to_emails: 收件人列表
            subject: 主题
            html_content: HTML 内容
            cc_emails: 抄送列表
            
        Returns:
            bool: 是否成功
        """
        return self._send_email(to_emails, subject, html_content, html=True, cc_emails=cc_emails)
    
    def send_trade_notification(
        self,
        to_emails: List[str],
        symbol: str,
        action: str,
        price: float,
        quantity: float,
        pnl: Optional[float] = None,
        strategy: Optional[str] = None,
    ) -> bool:
        """发送交易通知邮件"""
        subject = f"[CryptoQuant] 交易执行 - {symbol} {action.upper()}"
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: {'#28a745' if action == 'buy' else '#dc3545'}; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .info {{ margin: 10px 0; }}
                .footer {{ background-color: #f8f9fa; padding: 10px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{'✅' if action == 'buy' else '❌'} 交易执行通知</h2>
            </div>
            <div class="content">
                <div class="info"><strong>交易对:</strong> {symbol}</div>
                <div class="info"><strong>操作:</strong> {action.upper()}</div>
                <div class="info"><strong>价格:</strong> {price}</div>
                <div class="info"><strong>数量:</strong> {quantity}</div>
                {'<div class="info"><strong>盈亏:</strong> ' + ('📈' if pnl > 0 else '📉') + f' {pnl:.2f} USDT</div>' if pnl else ''}
                {'<div class="info"><strong>策略:</strong> ' + strategy + '</div>' if strategy else ''}
            </div>
            <div class="footer">
                CryptoQuant 交易系统
            </div>
        </body>
        </html>
        """
        
        return self.send_html(to_emails, subject, html)
    
    def send_risk_alert(
        self,
        to_emails: List[str],
        alert_type: str,
        message: str,
        level: str = "warning",
    ) -> bool:
        """发送风控告警邮件"""
        subject = f"[CryptoQuant] 风控告警 - {alert_type}"
        
        colors = {
            'info': '#17a2b8',
            'warning': '#ffc107',
            'critical': '#dc3545',
        }
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: {colors.get(level, '#ffc107')}; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .alert {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid {colors.get(level, '#ffc107')}; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>⚠️ 风控告警</h2>
            </div>
            <div class="content">
                <div><strong>类型:</strong> {alert_type}</div>
                <div><strong>级别:</strong> {level.upper()}</div>
                <div class="alert">
                    <strong>内容:</strong><br>
                    {message}
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_html(to_emails, subject, html)
    
    def send_daily_report(
        self,
        to_emails: List[str],
        pnl: float,
        trades: int,
        win_rate: float,
        positions: List[Dict],
    ) -> bool:
        """发送日报邮件"""
        subject = f"[CryptoQuant] 交易日报 - {__import__('time').strftime('%Y-%m-%d')}"
        
        pnl_color = '#28a745' if pnl > 0 else '#dc3545'
        
        positions_html = ""
        if positions:
            positions_html = "<h3>当前持仓</h3><table border='1' cellpadding='5'>"
            positions_html += "<tr><th>交易对</th><th>数量</th><th>价格</th></tr>"
            for pos in positions:
                positions_html += f"<tr><td>{pos['symbol']}</td><td>{pos['size']}</td><td>{pos['price']}</td></tr>"
            positions_html += "</table>"
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #007bff; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .stat {{ display: inline-block; margin: 10px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }}
                .pnl {{ color: {pnl_color}; font-size: 24px; font-weight: bold; }}
                table {{ border-collapse: collapse; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>📊 交易日报</h2>
            </div>
            <div class="content">
                <div class="stat">
                    <div>日盈亏</div>
                    <div class="pnl">{'📈' if pnl > 0 else '📉'} {pnl:.2f} USDT</div>
                </div>
                <div class="stat">
                    <div>交易次数</div>
                    <div style="font-size: 24px;">{trades}</div>
                </div>
                <div class="stat">
                    <div>胜率</div>
                    <div style="font-size: 24px;">{win_rate:.2%}</div>
                </div>
                {positions_html}
            </div>
        </body>
        </html>
        """
        
        return self.send_html(to_emails, subject, html)
    
    def _send_email(
        self,
        to_emails: List[str],
        subject: str,
        content: str,
        html: bool = False,
        cc_emails: Optional[List[str]] = None,
    ) -> bool:
        """发送邮件"""
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.config.from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # 添加内容
            msg_type = 'html' if html else 'plain'
            msg.attach(MIMEText(content, msg_type, 'utf-8'))
            
            # 连接服务器
            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            
            if self.config.use_tls:
                server.starttls()
            
            server.login(self.config.username, self.config.password)
            
            # 发送邮件
            all_recipients = to_emails + (cc_emails or [])
            server.sendmail(self.config.from_email, all_recipients, msg.as_string())
            
            server.quit()
            
            logger.info(f"邮件发送成功：{to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败：{e}")
            return False
