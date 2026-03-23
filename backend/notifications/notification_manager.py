"""
通知管理器 - 统一管理所有通知渠道
"""

from typing import Dict, List, Optional, Any
from enum import Enum
import logging
import asyncio

from .dingtalk import DingTalkNotifier
from .email import EmailNotifier, EmailConfig
from .telegram import TelegramNotifier

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """通知渠道"""
    DINGTALK = "dingtalk"
    EMAIL = "email"
    TELEGRAM = "telegram"
    ALL = "all"


class NotificationManager:
    """
    通知管理器
    
    统一管理多个通知渠道，支持：
    - 多渠道发送
    - 通知模板
    - 频率限制
    - 通知历史
    """
    
    def __init__(self):
        """初始化通知管理器"""
        self._notifiers: Dict[NotificationChannel, Any] = {}
        
        # 通知历史
        self._notification_history = []
        
        # 频率限制
        self._rate_limits = {}
    
    def add_dingtalk(
        self,
        webhook: str,
        secret: Optional[str] = None,
    ):
        """添加钉钉通知"""
        self._notifiers[NotificationChannel.DINGTALK] = DingTalkNotifier(webhook, secret)
        logger.info("添加钉钉通知渠道")
    
    def add_email(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: List[str],
    ):
        """添加邮件通知"""
        config = EmailConfig(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            username=username,
            password=password,
            from_email=from_email,
        )
        
        self._notifiers[NotificationChannel.EMAIL] = {
            'notifier': EmailNotifier(config),
            'to_emails': to_emails,
        }
        
        logger.info("添加邮件通知渠道")
    
    def add_telegram(
        self,
        bot_token: str,
        chat_ids: List[str],
    ):
        """添加 Telegram 通知"""
        self._notifiers[NotificationChannel.TELEGRAM] = TelegramNotifier(bot_token, chat_ids)
        logger.info("添加 Telegram 通知渠道")
    
    async def send_trade_notification(
        self,
        symbol: str,
        action: str,
        price: float,
        quantity: float,
        pnl: Optional[float] = None,
        strategy: Optional[str] = None,
        channels: Optional[List[NotificationChannel]] = None,
    ):
        """
        发送交易通知
        
        Args:
            symbol: 交易对
            action: 操作
            price: 价格
            quantity: 数量
            pnl: 盈亏
            strategy: 策略
            channels: 通知渠道
        """
        channels = channels or [NotificationChannel.ALL]
        
        tasks = []
        
        for channel in channels:
            if channel == NotificationChannel.ALL:
                for ch in self._notifiers:
                    tasks.append(self._send_trade_notification(ch, symbol, action, price, quantity, pnl, strategy))
            else:
                tasks.append(self._send_trade_notification(channel, symbol, action, price, quantity, pnl, strategy))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_trade_notification(
        self,
        channel: NotificationChannel,
        symbol: str,
        action: str,
        price: float,
        quantity: float,
        pnl: Optional[float],
        strategy: Optional[str],
    ):
        """发送交易通知到指定渠道"""
        notifier = self._notifiers.get(channel)
        if not notifier:
            return
        
        try:
            if channel == NotificationChannel.DINGTALK:
                await notifier.send_trade_notification(symbol, action, price, quantity, pnl, strategy)
            
            elif channel == NotificationChannel.EMAIL:
                await notifier['notifier'].send_trade_notification(
                    notifier['to_emails'],
                    symbol, action, price, quantity, pnl, strategy,
                )
            
            elif channel == NotificationChannel.TELEGRAM:
                await notifier.send_trade_notification(symbol, action, price, quantity, pnl, strategy)
            
            self._record_notification(channel, 'trade', symbol)
            
        except Exception as e:
            logger.error(f"{channel.value} 发送交易通知失败：{e}")
    
    async def send_risk_alert(
        self,
        alert_type: str,
        message: str,
        level: str = "warning",
        channels: Optional[List[NotificationChannel]] = None,
    ):
        """发送风控告警"""
        channels = channels or [NotificationChannel.ALL]
        
        tasks = []
        
        for channel in channels:
            if channel == NotificationChannel.ALL:
                for ch in self._notifiers:
                    tasks.append(self._send_risk_alert(ch, alert_type, message, level))
            else:
                tasks.append(self._send_risk_alert(channel, alert_type, message, level))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_risk_alert(
        self,
        channel: NotificationChannel,
        alert_type: str,
        message: str,
        level: str,
    ):
        """发送风控告警到指定渠道"""
        notifier = self._notifiers.get(channel)
        if not notifier:
            return
        
        try:
            if channel == NotificationChannel.DINGTALK:
                await notifier.send_risk_alert(alert_type, message, level)
            
            elif channel == NotificationChannel.EMAIL:
                await notifier['notifier'].send_risk_alert(
                    notifier['to_emails'],
                    alert_type, message, level,
                )
            
            elif channel == NotificationChannel.TELEGRAM:
                await notifier.send_risk_alert(alert_type, message, level)
            
            self._record_notification(channel, 'risk_alert', alert_type)
            
        except Exception as e:
            logger.error(f"{channel.value} 发送风控告警失败：{e}")
    
    async def send_daily_report(
        self,
        pnl: float,
        trades: int,
        win_rate: float,
        positions: List[Dict],
        channels: Optional[List[NotificationChannel]] = None,
    ):
        """发送日报"""
        channels = channels or [NotificationChannel.EMAIL]
        
        for channel in channels:
            notifier = self._notifiers.get(channel)
            if not notifier:
                continue
            
            try:
                if channel == NotificationChannel.DINGTALK:
                    await notifier.send_daily_report(pnl, trades, win_rate, positions)
                
                elif channel == NotificationChannel.EMAIL:
                    await notifier['notifier'].send_daily_report(
                        notifier['to_emails'],
                        pnl, trades, win_rate, positions,
                    )
                
                self._record_notification(channel, 'daily_report', None)
                
            except Exception as e:
                logger.error(f"{channel.value} 发送日报失败：{e}")
    
    def _record_notification(
        self,
        channel: NotificationChannel,
        notification_type: str,
        subject: Optional[str],
    ):
        """记录通知历史"""
        import time
        
        self._notification_history.append({
            'channel': channel.value,
            'type': notification_type,
            'subject': subject,
            'timestamp': int(time.time() * 1000),
        })
        
        # 保持历史记录
        if len(self._notification_history) > 1000:
            self._notification_history = self._notification_history[-1000:]
    
    def get_statistics(self) -> dict:
        """获取通知统计"""
        stats = {
            'total_notifications': len(self._notification_history),
            'channels': {ch.value: 0 for ch in NotificationChannel if ch != NotificationChannel.ALL},
            'types': {},
        }
        
        for record in self._notification_history:
            if record['channel'] in stats['channels']:
                stats['channels'][record['channel']] += 1
            
            type_key = record['type']
            stats['types'][type_key] = stats['types'].get(type_key, 0) + 1
        
        return stats
    
    async def close(self):
        """关闭所有通知器"""
        for channel, notifier in self._notifiers.items():
            try:
                if hasattr(notifier, 'close'):
                    await notifier.close()
                elif isinstance(notifier, dict) and 'notifier' in notifier:
                    if hasattr(notifier['notifier'], 'close'):
                        await notifier['notifier'].close()
            except Exception as e:
                logger.error(f"关闭 {channel.value} 通知器失败：{e}")
