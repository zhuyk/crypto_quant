"""
Telegram 通知
"""

from typing import Optional, List, Dict
import aiohttp
import logging

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Telegram Bot 通知
    
    支持:
    - 文本消息
    - Markdown
    - HTML
    - 图片
    """
    
    def __init__(
        self,
        bot_token: str,
        chat_ids: List[str],
    ):
        """
        Args:
            bot_token: Bot Token
            chat_ids: 聊天 ID 列表
        """
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def send_text(
        self,
        message: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "Markdown",
    ) -> bool:
        """
        发送文本消息
        
        Args:
            message: 消息内容
            chat_id: 聊天 ID（可选，默认发送给所有）
            parse_mode: 解析模式
            
        Returns:
            bool: 是否成功
        """
        return await self._send_message(message, chat_id, parse_mode)
    
    async def send_trade_notification(
        self,
        symbol: str,
        action: str,
        price: float,
        quantity: float,
        pnl: Optional[float] = None,
        strategy: Optional[str] = None,
    ) -> bool:
        """发送交易通知"""
        icon = '✅' if action == 'buy' else '❌'
        
        message = f"{icon} *交易执行通知*\n\n"
        message += f"*交易对*: `{symbol}`\n"
        message += f"*操作*: *{action.upper()}*\n"
        message += f"*价格*: `{price}`\n"
        message += f"*数量*: `{quantity}`\n"
        
        if pnl is not None:
            pnl_icon = '📈' if pnl > 0 else '📉'
            message += f"*盈亏*: {pnl_icon} `{pnl:.2f} USDT`\n"
        
        if strategy:
            message += f"*策略*: `{strategy}`\n"
        
        import time
        message += f"\n_时间：{time.strftime('%Y-%m-%d %H:%M:%S')}_ "
        
        return await self.send_text(message)
    
    async def send_risk_alert(
        self,
        alert_type: str,
        message: str,
        level: str = "warning",
    ) -> bool:
        """发送风控告警"""
        icons = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'critical': '🚨',
        }
        
        text = f"{icons.get(level, '⚠️')} *风控告警*\n\n"
        text += f"*类型*: `{alert_type}`\n"
        text += f"*级别*: *{level.upper()}*\n"
        text += f"*内容*: {message}\n"
        
        import time
        text += f"\n_时间：{time.strftime('%Y-%m-%d %H:%M:%S')}_ "
        
        return await self.send_text(text)
    
    async def _send_message(
        self,
        message: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "Markdown",
    ) -> bool:
        """发送消息"""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        target_chat_ids = [chat_id] if chat_id else self.chat_ids
        
        success = True
        
        for cid in target_chat_ids:
            try:
                url = f"{self.base_url}/sendMessage"
                data = {
                    'chat_id': cid,
                    'text': message,
                    'parse_mode': parse_mode,
                }
                
                async with self._session.post(url, json=data) as response:
                    result = await response.json()
                    
                    if not result.get('ok'):
                        logger.error(f"Telegram 发送失败：{result}")
                        success = False
                        
            except Exception as e:
                logger.error(f"Telegram 发送异常：{e}")
                success = False
        
        return success
    
    async def close(self):
        """关闭会话"""
        if self._session:
            await self._session.close()
