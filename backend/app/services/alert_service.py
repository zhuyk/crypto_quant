"""
告警通知服务
支持钉钉、邮件等多种通知方式
"""
import asyncio
import logging
import smtplib
import time
import hashlib
import hmac
import base64
import urllib.parse
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, field
from enum import Enum

import httpx

from app.core.config import settings
from app.utils.cache import get_cache, CacheKeys

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """告警类型"""
    TRADE = "trade"  # 交易相关
    RISK = "risk"  # 风险相关
    SYSTEM = "system"  # 系统相关
    PRICE = "price"  # 价格相关


@dataclass
class AlertMessage:
    """告警消息"""
    title: str
    content: str
    level: AlertLevel = AlertLevel.INFO
    alert_type: AlertType = AlertType.SYSTEM
    symbol: Optional[str] = None
    data: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "content": self.content,
            "level": self.level.value,
            "type": self.alert_type.value,
            "symbol": self.symbol,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class DingTalkNotifier:
    """钉钉机器人通知"""
    
    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        """
        初始化钉钉通知
        
        Args:
            webhook_url: 钉钉机器人 webhook URL
            secret: 加签密钥 (可选)
        """
        self.webhook_url = webhook_url
        self.secret = secret
        self._client = httpx.AsyncClient(timeout=10.0)
        
        logger.info(f"✅ 钉钉通知初始化完成")
    
    def _generate_sign(self, timestamp: str) -> str:
        """生成钉钉签名"""
        if not self.secret:
            return ""
        
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        
        hmac_code = hmac.new(
            secret_enc,
            string_to_sign_enc,
            digestmod=hashlib.sha256
        ).digest()
        
        return urllib.parse.quote_plus(base64.b64encode(hmac_code))
    
    async def send(
        self,
        title: str,
        content: str,
        level: AlertLevel = AlertLevel.INFO,
        **kwargs,
    ) -> bool:
        """
        发送钉钉消息
        
        Args:
            title: 消息标题
            content: 消息内容
            level: 告警级别
        """
        try:
            # 构建消息
            if level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
                msg_type = "markdown"
                timestamp = str(int(time.time() * 1000))
                
                markdown_content = f"""## {title}

{content}

---
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**级别**: <font color="{'red' if level == AlertLevel.CRITICAL else 'orange'}">{level.value.upper()}</font>
"""
                
                data = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": title,
                        "text": markdown_content,
                    },
                    "at": {
                        "isAtAll": level in [AlertLevel.ERROR, AlertLevel.CRITICAL],
                    },
                }
            else:
                msg_type = "text"
                data = {
                    "msgtype": "text",
                    "text": {
                        "content": f"{title}\n{content}",
                    },
                }
            
            # 添加签名参数
            url = self.webhook_url
            if self.secret:
                timestamp = str(int(time.time() * 1000))
                sign = self._generate_sign(timestamp)
                url = f"{url}&timestamp={timestamp}&sign={sign}"
            
            # 发送请求
            response = await self._client.post(url, json=data)
            result = response.json()
            
            if result.get("errcode") == 0:
                logger.info(f"✅ 钉钉消息发送成功 - {title}")
                return True
            else:
                logger.error(f"❌ 钉钉消息发送失败：{result}")
                return False
                
        except Exception as e:
            logger.error(f"钉钉通知异常：{e}")
            return False
    
    async def close(self):
        """关闭客户端"""
        await self._client.aclose()


class EmailNotifier:
    """邮件通知"""
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: List[str],
    ):
        """
        初始化邮件通知
        
        Args:
            smtp_server: SMTP 服务器
            smtp_port: SMTP 端口
            username: 用户名
            password: 密码
            from_addr: 发件人
            to_addrs: 收件人列表
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        
        logger.info(f"✅ 邮件通知初始化完成 - {from_addr}")
    
    def send(
        self,
        subject: str,
        content: str,
        html: bool = False,
    ) -> bool:
        """
        发送邮件
        
        Args:
            subject: 邮件主题
            content: 邮件内容
            html: 是否为 HTML 格式
        """
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)
            msg['Subject'] = subject
            
            # 添加内容
            msg_type = 'html' if html else 'plain'
            msg.attach(MIMEText(content, msg_type, 'utf-8'))
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"✅ 邮件发送成功 - {subject}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败：{e}")
            return False


class AlertService:
    """告警服务"""
    
    def __init__(self):
        self._notifiers: Dict[str, Any] = {}
        self._alert_history: List[AlertMessage] = []
        self._alert_filters: Dict[AlertType, List[AlertLevel]] = {}
        self._rate_limit: Dict[str, float] = {}  # 速率限制 {key: last_send_time}
        self._rate_limit_window = 60  # 60 秒
        self._cache = get_cache()
        
        logger.info("✅ 告警服务初始化完成")
    
    def add_dingtalk(
        self,
        name: str = "default",
        webhook_url: Optional[str] = None,
        secret: Optional[str] = None,
    ):
        """添加钉钉通知"""
        url = webhook_url or settings.__dict__.get("DINGTALK_WEBHOOK", "")
        if not url:
            logger.warning("⚠️  钉钉 Webhook 未配置")
            return
        
        self._notifiers[f"dingtalk_{name}"] = DingTalkNotifier(url, secret)
        logger.info(f"✅ 钉钉通知已添加 - {name}")
    
    def add_email(
        self,
        name: str = "default",
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_addr: Optional[str] = None,
        to_addrs: Optional[List[str]] = None,
    ):
        """添加邮件通知"""
        # 从配置或环境变量获取
        server = smtp_server or settings.__dict__.get("SMTP_SERVER", "")
        if not server:
            logger.warning("⚠️  SMTP 服务器未配置")
            return
        
        notifier = EmailNotifier(
            smtp_server=server,
            smtp_port=smtp_port or settings.__dict__.get("SMTP_PORT", 587),
            username=username or settings.__dict__.get("SMTP_USERNAME", ""),
            password=password or settings.__dict__.get("SMTP_PASSWORD", ""),
            from_addr=from_addr or settings.__dict__.get("SMTP_FROM", ""),
            to_addrs=to_addrs or settings.__dict__.get("SMTP_TO", []),
        )
        
        self._notifiers[f"email_{name}"] = notifier
        logger.info(f"✅ 邮件通知已添加 - {name}")
    
    def set_alert_filter(self, alert_type: AlertType, levels: List[AlertLevel]):
        """设置告警过滤"""
        self._alert_filters[alert_type] = levels
        logger.debug(f"📝 设置告警过滤 - {alert_type.value}: {[l.value for l in levels]}")
    
    def _check_rate_limit(self, key: str) -> bool:
        """检查速率限制"""
        now = time.time()
        last_send = self._rate_limit.get(key, 0)
        
        if now - last_send < self._rate_limit_window:
            return False  # 频率过高
        
        self._rate_limit[key] = now
        return True
    
    async def send_alert(
        self,
        alert: AlertMessage,
        use_rate_limit: bool = True,
    ) -> Dict[str, bool]:
        """
        发送告警
        
        Args:
            alert: 告警消息
            use_rate_limit: 是否启用速率限制
        
        Returns:
            {notifier_name: success}
        """
        results = {}
        
        # 检查过滤
        allowed_levels = self._alert_filters.get(alert.alert_type, list(AlertLevel))
        if alert.level not in allowed_levels:
            logger.debug(f"🚫 告警被过滤 - {alert.title}")
            return results
        
        # 速率限制
        if use_rate_limit:
            rate_key = f"{alert.alert_type.value}:{alert.title}"
            if not self._check_rate_limit(rate_key):
                logger.warning(f"⏰ 告警频率过高 - {alert.title}")
                return results
        
        # 发送通知
        for name, notifier in self._notifiers.items():
            try:
                if isinstance(notifier, DingTalkNotifier):
                    success = await notifier.send(
                        title=alert.title,
                        content=alert.content,
                        level=alert.level,
                    )
                elif isinstance(notifier, EmailNotifier):
                    success = notifier.send(
                        subject=f"[{alert.level.value.upper()}] {alert.title}",
                        content=alert.content,
                        html=True,
                    )
                else:
                    success = False
                
                results[name] = success
                
            except Exception as e:
                logger.error(f"通知发送失败 - {name}: {e}")
                results[name] = False
        
        # 记录历史
        self._alert_history.append(alert)
        if len(self._alert_history) > 1000:
            self._alert_history = self._alert_history[-1000:]
        
        # 缓存告警
        cache_key = CacheKeys.make_key(
            "alert",
            alert.alert_type.value,
            str(int(time.time() / 300)),  # 5 分钟窗口
        )
        self._cache.set(cache_key, alert.to_dict(), expire=600)
        
        logger.info(
            f"📢 告警已发送 - {alert.title} "
            f"(成功：{sum(results.values())}/{len(results)})"
        )
        
        return results
    
    async def send_trade_alert(
        self,
        action: str,
        symbol: str,
        price: float,
        amount: float,
        **kwargs,
    ):
        """发送交易告警"""
        alert = AlertMessage(
            title=f"{'✅' if action == 'buy' else '💰'} 交易通知",
            content=f"""
**交易对**: {symbol}
**方向**: {'买入' if action == 'buy' else '卖出'}
**价格**: ${price:,.2f}
**数量**: {amount}
**金额**: ${price * amount:,.2f}
            """.strip(),
            level=AlertLevel.INFO,
            alert_type=AlertType.TRADE,
            symbol=symbol,
            data={"action": action, "price": price, "amount": amount, **kwargs},
        )
        
        return await self.send_alert(alert)
    
    async def send_risk_alert(
        self,
        risk_type: str,
        symbol: Optional[str] = None,
        value: Optional[float] = None,
        threshold: Optional[float] = None,
    ):
        """发送风险告警"""
        alert = AlertMessage(
            title=f"⚠️  风险告警 - {risk_type}",
            content=f"""
**交易对**: {symbol or 'N/A'}
**风险类型**: {risk_type}
**当前值**: {value}
**阈值**: {threshold}
            """.strip(),
            level=AlertLevel.WARNING,
            alert_type=AlertType.RISK,
            symbol=symbol,
            data={"risk_type": risk_type, "value": value, "threshold": threshold},
        )
        
        return await self.send_alert(alert)
    
    async def send_price_alert(
        self,
        symbol: str,
        price: float,
        change_pct: float,
        threshold_pct: float,
    ):
        """发送价格告警"""
        direction = "📈" if change_pct > 0 else "📉"
        alert = AlertMessage(
            title=f"{direction} 价格波动告警",
            content=f"""
**交易对**: {symbol}
**当前价格**: ${price:,.2f}
**24h 涨跌**: {change_pct:+.2f}%
**告警阈值**: {threshold_pct:.2f}%
            """.strip(),
            level=AlertLevel.INFO,
            alert_type=AlertType.PRICE,
            symbol=symbol,
            data={"price": price, "change_pct": change_pct, "threshold_pct": threshold_pct},
        )
        
        return await self.send_alert(alert)
    
    async def send_system_alert(
        self,
        title: str,
        content: str,
        level: AlertLevel = AlertLevel.INFO,
    ):
        """发送系统告警"""
        alert = AlertMessage(
            title=title,
            content=content,
            level=level,
            alert_type=AlertType.SYSTEM,
        )
        
        return await self.send_alert(alert)
    
    def get_alert_history(
        self,
        limit: int = 50,
        alert_type: Optional[AlertType] = None,
    ) -> List[Dict]:
        """获取告警历史"""
        history = self._alert_history
        
        if alert_type:
            history = [a for a in history if a.alert_type == alert_type]
        
        return [a.to_dict() for a in history[-limit:]]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "notifiers": list(self._notifiers.keys()),
            "total_alerts": len(self._alert_history),
            "rate_limit_window": self._rate_limit_window,
            "filters": {
                k.value: [l.value for l in levels]
                for k, levels in self._alert_filters.items()
            },
        }
    
    async def close(self):
        """关闭所有通知器"""
        for notifier in self._notifiers.values():
            if hasattr(notifier, 'close'):
                await notifier.close()


# 全局告警服务实例
_alert_service: Optional[AlertService] = None


def get_alert_service() -> Optional[AlertService]:
    """获取告警服务"""
    return _alert_service


def create_alert_service() -> AlertService:
    """创建告警服务"""
    global _alert_service
    _alert_service = AlertService()
    return _alert_service
