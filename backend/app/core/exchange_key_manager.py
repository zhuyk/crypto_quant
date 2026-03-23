"""
交易所 API Key 管理器
安全存储和管理用户的交易所 API Key
"""

import os
import json
import base64
import hashlib
from datetime import datetime
from typing import Optional, Dict, List
from cryptography.fernet import Fernet
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ExchangeKeyManager:
    """
    交易所 API Key 管理器
    
    功能：
    1. 加密存储 API Key（使用 Fernet 对称加密）
    2. 按用户隔离
    3. 支持多个交易所
    4. 测试连接功能
    """
    
    SUPPORTED_EXCHANGES = {
        "binance": {"name": "币安", "requires_passphrase": False},
        "okx": {"name": "OKX", "requires_passphrase": True},
        "bybit": {"name": "Bybit", "requires_passphrase": True},
        "htx": {"name": "HTX (火币)", "requires_passphrase": False},
        "gate": {"name": "Gate.io", "requires_passphrase": False},
        "kucoin": {"name": "Kucoin", "requires_passphrase": True},
    }
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化交易所 Key 管理器
        
        Args:
            data_dir: 数据存储目录，默认在 ~/.crypto_quant/exchange_keys
        """
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path.home() / ".crypto_quant" / "exchange_keys"
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 加密密钥（从环境变量或文件加载）
        self._encryption_key = self._load_or_create_key()
        self._fernet = Fernet(self._encryption_key)
        
        # 数据文件路径
        self._data_file = self.data_dir / "keys.json"
        
        # 加载数据
        self._keys = self._load_keys()
    
    def _load_or_create_key(self) -> bytes:
        """加载或创建加密密钥"""
        key_file = self.data_dir / ".encryption_key"
        
        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()
        else:
            # 生成新密钥
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            # 设置文件权限（仅所有者可读写）
            os.chmod(key_file, 0o600)
            logger.info("创建新的加密密钥")
            return key
    
    def _load_keys(self) -> Dict:
        """加载存储的 Keys"""
        if not self._data_file.exists():
            return {}
        
        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"加载 Keys 失败：{e}")
            return {}
    
    def _save_keys(self):
        """保存 Keys 到文件"""
        try:
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(self._keys, f, indent=2, ensure_ascii=False)
            # 设置文件权限
            os.chmod(self._data_file, 0o600)
        except Exception as e:
            logger.error(f"保存 Keys 失败：{e}")
            raise
    
    def _encrypt(self, value: str) -> str:
        """加密字符串"""
        return self._fernet.encrypt(value.encode()).decode()
    
    def _decrypt(self, value: str) -> str:
        """解密字符串"""
        return self._fernet.decrypt(value.encode()).decode()
    
    def _generate_key_id(self) -> str:
        """生成 Key ID"""
        return hashlib.sha256(
            datetime.utcnow().isoformat().encode()
        ).hexdigest()[:16]
    
    def create_key(
        self,
        user_id: str,
        exchange: str,
        name: str,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        is_testnet: bool = False,
    ) -> str:
        """
        创建新的交易所 API Key
        
        Returns:
            key_id: 创建的 Key ID
        """
        if exchange not in self.SUPPORTED_EXCHANGES:
            raise ValueError(f"不支持的交易所：{exchange}")
        
        key_id = self._generate_key_id()
        
        # 加密敏感信息
        encrypted_key = self._encrypt(api_key)
        encrypted_secret = self._encrypt(api_secret)
        encrypted_passphrase = self._encrypt(passphrase) if passphrase else None
        
        now = datetime.utcnow()
        
        key_data = {
            "id": key_id,
            "user_id": user_id,
            "exchange": exchange,
            "name": name,
            "api_key_encrypted": encrypted_key,
            "api_secret_encrypted": encrypted_secret,
            "api_passphrase_encrypted": encrypted_passphrase,
            "api_key_prefix": api_key[:8] + "****" if len(api_key) > 8 else "****",
            "permissions": permissions or ["trade", "read"],
            "is_active": True,
            "is_testnet": is_testnet,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "last_used": None,
        }
        
        # 存储
        if user_id not in self._keys:
            self._keys[user_id] = {}
        self._keys[user_id][key_id] = key_data
        
        self._save_keys()
        
        logger.info(f"创建交易所 API Key：{exchange} - {name} for user {user_id}")
        return key_id
    
    def get_key(self, key_id: str, user_id: str) -> Optional[Dict]:
        """获取 Key 信息（不返回加密的密钥）"""
        user_keys = self._keys.get(user_id, {})
        key_data = user_keys.get(key_id)
        
        if not key_data:
            return None
        
        # 返回脱敏后的数据
        return {
            "id": key_data["id"],
            "user_id": key_data["user_id"],
            "exchange": key_data["exchange"],
            "name": key_data["name"],
            "api_key_prefix": key_data["api_key_prefix"],
            "permissions": key_data["permissions"],
            "is_active": key_data["is_active"],
            "is_testnet": key_data["is_testnet"],
            "created_at": key_data["created_at"],
            "updated_at": key_data["updated_at"],
            "last_used": key_data["last_used"],
        }
    
    def get_key_credentials(self, key_id: str, user_id: str) -> Optional[Dict]:
        """获取解密的 API 凭证（用于实际交易）"""
        user_keys = self._keys.get(user_id, {})
        key_data = user_keys.get(key_id)
        
        if not key_data or not key_data["is_active"]:
            return None
        
        # 解密
        credentials = {
            "exchange": key_data["exchange"],
            "api_key": self._decrypt(key_data["api_key_encrypted"]),
            "api_secret": self._decrypt(key_data["api_secret_encrypted"]),
            "passphrase": self._decrypt(key_data["api_passphrase_encrypted"]) 
                         if key_data["api_passphrase_encrypted"] else None,
            "is_testnet": key_data["is_testnet"],
        }
        
        # 更新最后使用时间
        key_data["last_used"] = datetime.utcnow().isoformat()
        self._save_keys()
        
        return credentials
    
    def list_keys(self, user_id: str, exchange: Optional[str] = None) -> List[Dict]:
        """列出用户的所有 Keys"""
        user_keys = self._keys.get(user_id, {})
        
        keys = []
        for key_id, key_data in user_keys.items():
            if exchange and key_data["exchange"] != exchange:
                continue
            
            keys.append(self.get_key(key_id, user_id))
        
        return keys
    
    def update_key(
        self,
        key_id: str,
        user_id: str,
        name: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ):
        """更新 Key 配置"""
        user_keys = self._keys.get(user_id, {})
        key_data = user_keys.get(key_id)
        
        if not key_data:
            raise ValueError("Key 不存在")
        
        if name is not None:
            key_data["name"] = name
        if permissions is not None:
            key_data["permissions"] = permissions
        if is_active is not None:
            key_data["is_active"] = is_active
        
        key_data["updated_at"] = datetime.utcnow().isoformat()
        self._save_keys()
    
    def delete_key(self, key_id: str, user_id: str):
        """删除 Key（软删除）"""
        user_keys = self._keys.get(user_id, {})
        key_data = user_keys.get(key_id)
        
        if not key_data:
            raise ValueError("Key 不存在")
        
        # 标记为非活跃
        key_data["is_active"] = False
        key_data["updated_at"] = datetime.utcnow().isoformat()
        self._save_keys()
    
    async def test_connection(self, key_id: str, user_id: str) -> Dict:
        """测试交易所连接"""
        credentials = self.get_key_credentials(key_id, user_id)
        if not credentials:
            return {"success": False, "message": "Key 不存在或未激活"}
        
        try:
            import ccxt
            exchange_id = credentials["exchange"]
            exchange_class = getattr(ccxt, exchange_id)
            
            exchange = exchange_class({
                "apiKey": credentials["api_key"],
                "secret": credentials["api_secret"],
                "enableRateLimit": True,
            })
            
            if credentials.get("passphrase"):
                exchange.password = credentials["passphrase"]
            
            if credentials["is_testnet"]:
                exchange.set_sandbox_mode(True)
            
            # 测试获取余额
            balance = await exchange.fetch_balance()
            
            # 更新最后使用时间
            user_keys = self._keys.get(user_id, {})
            key_data = user_keys.get(key_id)
            if key_data:
                key_data["last_used"] = datetime.utcnow().isoformat()
                self._save_keys()
            
            return {
                "success": True,
                "message": f"连接成功 - {self.SUPPORTED_EXCHANGES[exchange_id]['name']}",
                "balance": {
                    "USDT": balance.get("total", {}).get("USDT", 0),
                    "BTC": balance.get("total", {}).get("BTC", 0),
                }
            }
            
        except Exception as e:
            logger.error(f"测试连接失败：{e}")
            return {
                "success": False,
                "message": f"连接失败：{str(e)}",
            }
    
    def get_user_stats(self, user_id: str) -> Dict:
        """获取用户统计信息"""
        user_keys = self._keys.get(user_id, {})
        
        stats = {
            "total_keys": 0,
            "active_keys": 0,
            "exchanges": {},
        }
        
        for key_data in user_keys.values():
            stats["total_keys"] += 1
            if key_data["is_active"]:
                stats["active_keys"] += 1
            
            exchange = key_data["exchange"]
            if exchange not in stats["exchanges"]:
                stats["exchanges"][exchange] = {
                    "name": self.SUPPORTED_EXCHANGES[exchange]["name"],
                    "count": 0,
                }
            stats["exchanges"][exchange]["count"] += 1
        
        return stats


# 全局单例
_exchange_key_manager: Optional[ExchangeKeyManager] = None


def get_exchange_key_manager() -> ExchangeKeyManager:
    """获取 ExchangeKeyManager 单例"""
    global _exchange_key_manager
    if _exchange_key_manager is None:
        _exchange_key_manager = ExchangeKeyManager()
    return _exchange_key_manager
