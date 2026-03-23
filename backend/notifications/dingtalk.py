"""
钉钉通知
"""

import hashlib
import hmac
import base64
import time
from typing import Optional, List, Dict
import aiohttp
import logging

logger = logging.getLogger(__name__)


class DingTalkNotifier:
    """
    钉钉机器人通知
    
    支持:
    - 文本消息
    - Markdown 消息
    - 卡片消息
    - @指定用户
    """
    
    def __init__(
        self,
        webhook: str,
        secret: Optional[str] = None,
    ):
        """
        Args:
            webhook: 钉钉机器人 webhook
            secret: 加签密钥
        """
        self.webhook = webhook
        self.secret = secret
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _generate_sign(self) -> str:
        """生成签名"""
        if not self.secret:
            return ""
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        
        hmac_code = hmac.new(
            secret_enc,
            string_to_sign_enc,
            digestmod=hashlib.sha256
        ).digest()
        
        sign = base64.b64encode(hmac_code).decode('utf-8')
        
        return f"&timestamp={timestamp}&sign={sign}"
    
    async def send_text(
        self,
        content: str,
        at_user_ids: Optional[List[str]] = None,
        is_at_all: bool = False,
    ) -> bool:
        """
        发送文本消息
        
        Args:
            content: 消息内容
            at_user_ids: @的用户 ID 列表
            is_at_all: 是否@所有人
            
        Returns:
            bool: 是否成功
        """
        message = {
            "msgtype": "text",
            "text": {
                "content": content
            },
            "at": {
                "atUserIds": at_user_ids or [],
                "isAtAll": is_at_all,
            }
        }
        
        return await self._send_message(message)
    
    async def send_markdown(
        self,
        title: str,
        content: str,
        at_user_ids: Optional[List[str]] = None,
        is_at_all: bool = False,
    ) -> bool:
        """
        发送 Markdown 消息
        
        Args:
            title: 标题
            content: Markdown 内容
            at_user_ids: @的用户 ID 列表
            is_at_all: 是否@所有人
            
        Returns:
            bool: 是否成功
        """
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            },
            "at": {
                "atUserIds": at_user_ids or [],
                "isAtAll": is_at_all,
            }
        }
        
        return await self._send_message(message)
    
    async def send_trade_notification(
        self,
        symbol: str,
        action: str,
        price: float,
        quantity: float,
        pnl: Optional[float] = None,
        strategy: Optional[str] = None,
    ) -> bool:
        """
        发送交易通知
        
        Args:
            symbol: 交易对
            action: 操作
            price: 价格
            quantity: 数量
            pnl: 盈亏
            strategy: 策略
            
        Returns:
            bool: 是否成功
        """
        title = f"{'✅' if action == 'buy' else '❌'} 交易执行通知"
        
        content = f"## {title}\n\n"
        content += f"**交易对**: {symbol}\n\n"
        content += f"**操作**: {action.upper()}\n\n"
        content += f"**价格**: {price}\n\n"
        content += f"**数量**: {quantity}\n\n"
        
        if pnl is not None:
            pnl_icon = '📈' if pnl > 0 else '📉'
            content += f"**盈亏**: {pnl_icon} {pnl:.2f} USDT\n\n"
        
        if strategy:
            content += f"**策略**: {strategy}\n\n"
        
        content += f"> 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return await self.send_markdown(title, content)
    
    async def send_risk_alert(
        self,
        alert_type: str,
        message: str,
        level: str = "warning",
    ) -> bool:
        """
        发送风控告警
        
        Args:
            alert_type: 告警类型
            message: 告警内容
            level: 级别 (info/warning/critical)
            
        Returns:
            bool: 是否成功
        """
        icons = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'critical': '🚨',
        }
        
        title = f"{icons.get(level, '⚠️')} 风控告警"
        content = f"## {title}\n\n"
        content += f"**类型**: {alert_type}\n\n"
        content += f"**级别**: {level.upper()}\n\n"
        content += f"**内容**: {message}\n\n"
        content += f"> 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return await self.send_markdown(title, content, is_at_all=(level == 'critical'))
    
    async def send_daily_report(
        self,
        pnl: float,
        trades: int,
        win_rate: float,
        positions: List[Dict],
    ) -> bool:
        """
        发送日报
        
        Args:
            pnl: 日盈亏
            trades: 交易次数
            win_rate: 胜率
            positions: 持仓列表
            
        Returns:
            bool: 是否成功
        """
        pnl_icon = '📈' if pnl > 0 else '📉'
        
        title = f"{pnl_icon} 交易日报"
        content = f"## {title} - {time.strftime('%Y-%m-%d')}\n\n"
        
        content += f"**日盈亏**: {pnl_icon} {pnl:.2f} USDT\n\n"
        content += f"**交易次数**: {trades}\n\n"
        content += f"**胜率**: {win_rate:.2%}\n\n"
        
        if positions:
            content += "**当前持仓**:\n"
            for pos in positions:
                content += f"- {pos['symbol']}: {pos['size']} @ {pos['price']}\n"
        
        content += f"\n> 报告时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return await self.send_markdown(title, content)
    
    async def _send_message(self, message: dict) -> bool:
        """发送消息"""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        url = self.webhook
        if self.secret:
            url += self._generate_sign()
        
        try:
            async with self._session.post(
                url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                result = await response.json()
                
                if result.get('errcode') == 0:
                    logger.info("钉钉消息发送成功")
                    return True
                else:
                    logger.error(f"钉钉消息发送失败：{result}")
                    return False
                    
        except Exception as e:
            logger.error(f"钉钉消息发送异常：{e}")
            return False
    
    async def close(self):
        """关闭会话"""
        if self._session:
            await self._session.close()
            self._session = None
