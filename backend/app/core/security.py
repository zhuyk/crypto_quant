"""
安全模块
API 密钥加密存储、数据加密解密
"""
import os
import base64
import logging
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """安全操作异常"""
    pass


class CryptoManager:
    """加密管理器"""
    
    def __init__(self, key: Optional[str] = None):
        """
        初始化加密管理器
        
        Args:
            key: 加密密钥 (可选，不提供则从 SECRET_KEY 派生)
        """
        self._fernet: Optional[Fernet] = None
        
        if key:
            # 使用提供的密钥
            self._init_with_key(key)
        else:
            # 从 SECRET_KEY 派生密钥
            self._init_from_secret()
    
    def _init_with_key(self, key: str):
        """使用提供的密钥初始化"""
        try:
            # 确保密钥是有效的 Fernet 密钥
            if len(key) < 32:
                # 密钥太短，派生一个
                self._derive_key(key)
            else:
                # 使用现成密钥
                key_bytes = key.encode() if isinstance(key, str) else key
                if len(key_bytes) == 32:
                    key_bytes = base64.urlsafe_b64encode(key_bytes)
                self._fernet = Fernet(key_bytes)
                logger.info("✅ 加密管理器初始化成功 (使用提供的密钥)")
        except Exception as e:
            logger.error(f"初始化加密密钥失败：{e}")
            self._derive_key(settings.SECRET_KEY)
    
    def _init_from_secret(self):
        """从 SECRET_KEY 派生密钥"""
        self._derive_key(settings.SECRET_KEY)
    
    def _derive_key(self, secret: str):
        """
        从密钥派生 Fernet 密钥
        
        使用 PBKDF2HMAC 派生一个 32 字节的密钥
        """
        try:
            # 从环境变量获取 salt，如果未配置则生成并存储到文件
            salt = self._get_or_create_salt()
            
            # 派生密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
            
            self._fernet = Fernet(key)
            logger.info("✅ 加密管理器初始化成功 (从 SECRET_KEY 派生)")
        except Exception as e:
            logger.error(f"派生加密密钥失败：{e}")
            # 安全降级：仍然使用 PBKDF2 但基于机器相关信息派生
            # 而不是使用已知的硬编码密钥
            raise SecurityError(
                f"加密密钥初始化失败，请确保 SECRET_KEY 配置正确：{e}"
            )
    
    @staticmethod
    def _get_or_create_salt() -> bytes:
        """
        获取或创建 salt
        
        优先从环境变量 CRYPTO_SALT 获取；
        如果不存在，则生成随机 salt 并持久化到 .salt 文件。
        """
        # 优先从环境变量获取
        env_salt = os.environ.get("CRYPTO_SALT")
        if env_salt:
            return env_salt.encode()
        
        # 尝试从文件加载
        salt_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".crypto_salt"
        )
        if os.path.exists(salt_file):
            with open(salt_file, "rb") as f:
                return f.read()
        
        # 生成新的随机 salt 并持久化
        salt = os.urandom(32)
        try:
            os.makedirs(os.path.dirname(salt_file), exist_ok=True)
            with open(salt_file, "wb") as f:
                f.write(salt)
            logger.info("🔑 已生成并保存新的加密 salt")
        except OSError as e:
            logger.warning(f"⚠️  无法持久化 salt 文件：{e}，salt 将在重启后变更")
        
        return salt
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密字符串
        
        Args:
            plaintext: 明文
        
        Returns:
            密文 (base64 编码)
        """
        if not self._fernet:
            raise SecurityError("加密管理器未初始化")
        
        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"加密失败：{e}")
            raise SecurityError(f"加密失败：{str(e)}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        解密字符串
        
        Args:
            ciphertext: 密文 (base64 编码)
        
        Returns:
            明文
        """
        if not self._fernet:
            raise SecurityError("加密管理器未初始化")
        
        try:
            # 解码 base64
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"解密失败：{e}")
            raise SecurityError(f"解密失败：{str(e)}")
    
    def encrypt_api_key(self, api_key: str) -> str:
        """加密 API 密钥"""
        return self.encrypt(api_key)
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """解密 API 密钥"""
        return self.decrypt(encrypted_key)
    
    def hash_sensitive_data(self, data: str) -> str:
        """
        哈希敏感数据 (用于日志脱敏)
        
        Args:
            data: 原始数据
        
        Returns:
            哈希值 (前 8 位)
        """
        import hashlib
        return hashlib.sha256(data.encode()).hexdigest()[:8]


class APIKeyManager:
    """API 密钥管理器"""
    
    def __init__(self):
        self.crypto = CryptoManager()
        # 内存缓存 (格式：{exchange: {api_key_encrypted: api_secret_encrypted}})
        self._cache: dict = {}
    
    def store_api_key(
        self,
        exchange: str,
        api_key: str,
        api_secret: str,
        encrypt: bool = True,
    ) -> Tuple[str, str]:
        """
        存储 API 密钥
        
        Args:
            exchange: 交易所名称
            api_key: API Key
            api_secret: API Secret
            encrypt: 是否加密
        
        Returns:
            (加密后的 api_key, 加密后的 api_secret)
        """
        if encrypt:
            encrypted_key = self.crypto.encrypt(api_key)
            encrypted_secret = self.crypto.encrypt(api_secret)
        else:
            encrypted_key = api_key
            encrypted_secret = api_secret
        
        # 存储到内存缓存
        if exchange not in self._cache:
            self._cache[exchange] = {}
        self._cache[exchange][encrypted_key] = encrypted_secret
        
        logger.info(f"✅ API 密钥已存储 - 交易所：{exchange}")
        
        return encrypted_key, encrypted_secret
    
    def get_api_key(
        self,
        exchange: str,
        encrypted_key: str,
    ) -> Optional[Tuple[str, str]]:
        """
        获取 API 密钥
        
        Args:
            exchange: 交易所名称
            encrypted_key: 加密的 API Key
        
        Returns:
            (api_key, api_secret) 或 None
        """
        if exchange not in self._cache:
            return None
        
        encrypted_secret = self._cache[exchange].get(encrypted_key)
        if not encrypted_secret:
            return None
        
        try:
            # 解密
            api_key = self.crypto.decrypt(encrypted_key)
            api_secret = self.crypto.decrypt(encrypted_secret)
            return api_key, api_secret
        except Exception as e:
            logger.error(f"获取 API 密钥失败：{e}")
            return None
    
    def remove_api_key(self, exchange: str, encrypted_key: str) -> bool:
        """
        移除 API 密钥
        
        Args:
            exchange: 交易所名称
            encrypted_key: 加密的 API Key
        
        Returns:
            是否成功移除
        """
        if exchange not in self._cache:
            return False
        
        if encrypted_key in self._cache[exchange]:
            del self._cache[exchange][encrypted_key]
            logger.info(f"✅ API 密钥已移除 - 交易所：{exchange}")
            return True
        
        return False
    
    def list_exchanges(self) -> list:
        """列出所有已存储的交易所"""
        return list(self._cache.keys())
    
    def mask_api_key(self, api_key: str) -> str:
        """
        脱敏 API Key (用于日志)
        
        Example: "abc123xyz789" -> "abc*********789"
        """
        if len(api_key) <= 8:
            return "*" * len(api_key)
        
        return f"{api_key[:3]}{'*' * (len(api_key) - 6)}{api_key[-3:]}"


# 全局 API 密钥管理器实例
api_key_manager = APIKeyManager()


def get_api_key_manager() -> APIKeyManager:
    """获取 API 密钥管理器"""
    return api_key_manager


def encrypt_sensitive_data(data: str) -> str:
    """加密敏感数据"""
    crypto = CryptoManager()
    return crypto.encrypt(data)


def decrypt_sensitive_data(data: str) -> str:
    """解密敏感数据"""
    crypto = CryptoManager()
    return crypto.decrypt(data)


def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 3) -> str:
    """
    脱敏敏感数据
    
    Args:
        data: 原始数据
        mask_char: 掩码字符
        visible_chars: 首尾可见字符数
    
    Returns:
        脱敏后的数据
    """
    if len(data) <= visible_chars * 2:
        return mask_char * len(data)
    
    return f"{data[:visible_chars]}{mask_char * (len(data) - visible_chars * 2)}{data[-visible_chars:]}"
