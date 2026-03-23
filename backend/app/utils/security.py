"""
安全工具模块
API 密钥加密、数据脱敏、安全校验等
"""
import os
import base64
import hashlib
import secrets
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


class APIKeyEncryption:
    """
    API 密钥加密类
    
    使用 Fernet 对称加密存储敏感的 API 密钥
    """
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        Args:
            secret_key: 加密密钥（32 字节），为空则从配置读取
        """
        self.secret_key = secret_key or settings.SECRET_KEY
        
        if not self.secret_key or len(self.secret_key) < 32:
            # 如果密钥太短，使用 PBKDF2 派生
            self._cipher = self._derive_key(self.secret_key or "default-key")
        else:
            # 使用密钥的前 32 字节
            key = self._encode_key(self.secret_key[:32])
            self._cipher = Fernet(key)
    
    def _encode_key(self, key: str) -> bytes:
        """将密钥编码为 Fernet 兼容的 URL-safe base64"""
        key_bytes = key.encode() if isinstance(key, str) else key
        # 确保是 32 字节
        if len(key_bytes) < 32:
            key_bytes = key_bytes.ljust(32, b'\0')
        elif len(key_bytes) > 32:
            key_bytes = key_bytes[:32]
        
        # base64 编码
        return base64.urlsafe_b64encode(key_bytes)
    
    def _derive_key(self, password: str) -> Fernet:
        """从密码派生加密密钥"""
        salt = b"crypyoquant_salt_v1"  # 固定盐值（生产环境应随机生成并存储）
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密 API 密钥
        
        Args:
            plaintext: 明文 API 密钥
        
        Returns:
            加密后的密文（base64 编码）
        """
        try:
            encrypted = self._cipher.encrypt(plaintext.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"API key encryption failed: {e}")
            raise SecurityError(f"Failed to encrypt API key: {e}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        解密 API 密钥
        
        Args:
            ciphertext: 加密的密文（base64 编码）
        
        Returns:
            解密后的明文
        """
        try:
            encrypted = base64.b64decode(ciphertext.encode())
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"API key decryption failed: {e}")
            raise SecurityError(f"Failed to decrypt API key: {e}")
    
    def mask(self, api_key: str, visible_chars: int = 4) -> str:
        """
        脱敏 API 密钥（用于日志显示）
        
        Args:
            api_key: API 密钥
            visible_chars: 首尾显示的字符数
        
        Returns:
            脱敏后的字符串
        """
        if len(api_key) <= visible_chars * 2:
            return "*" * len(api_key)
        
        return f"{api_key[:visible_chars]}{'*' * (len(api_key) - visible_chars * 2)}{api_key[-visible_chars:]}"


class DataMasker:
    """数据脱敏工具"""
    
    @staticmethod
    def mask_email(email: str, visible_chars: int = 2) -> str:
        """脱敏邮箱"""
        if "@" not in email:
            return "*" * len(email)
        
        username, domain = email.split("@", 1)
        masked_username = (
            username[:visible_chars] + "*" * (len(username) - visible_chars)
            if len(username) > visible_chars
            else "*" * len(username)
        )
        return f"{masked_username}@{domain}"
    
    @staticmethod
    def mask_phone(phone: str, visible_chars: int = 3) -> str:
        """脱敏手机号"""
        # 移除所有非数字字符
        digits = "".join(c for c in phone if c.isdigit())
        
        if len(digits) <= visible_chars * 2:
            return "*" * len(digits)
        
        return f"{'*' * (len(digits) - visible_chars)}{digits[-visible_chars:]}"
    
    @staticmethod
    def mask_id(id_value: str, visible_chars: int = 4) -> str:
        """脱敏 ID"""
        if len(id_value) <= visible_chars * 2:
            return "*" * len(id_value)
        
        return f"{id_value[:visible_chars]}{'*' * (len(id_value) - visible_chars * 2)}{id_value[-visible_chars:]}"
    
    @staticmethod
    def mask_address(address: str, visible_chars: int = 5) -> str:
        """脱敏地址"""
        if len(address) <= visible_chars * 2:
            return "*" * len(address)
        
        return f"{address[:visible_chars]}...{address[-visible_chars:]}"


class TokenGenerator:
    """安全令牌生成器"""
    
    @staticmethod
    def generate_api_token(length: int = 32) -> str:
        """生成 API 访问令牌"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_refresh_token() -> str:
        """生成刷新令牌"""
        return secrets.token_hex(64)
    
    @staticmethod
    def generate_verification_code(length: int = 6) -> str:
        """生成验证码（数字）"""
        return "".join(secrets.choice("0123456789") for _ in range(length))
    
    @staticmethod
    def generate_password(length: int = 16) -> str:
        """生成随机密码"""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(length))


class RequestValidator:
    """请求校验器"""
    
    @staticmethod
    def validate_signature(
        payload: str,
        signature: str,
        secret: str,
        algorithm: str = "sha256",
    ) -> bool:
        """
        验证请求签名
        
        Args:
            payload: 请求体
            signature: 签名值
            secret: 密钥
            algorithm: 哈希算法
        
        Returns:
            签名是否有效
        """
        try:
            if algorithm == "sha256":
                expected = hashlib.sha256(
                    f"{payload}{secret}".encode()
                ).hexdigest()
            elif algorithm == "sha512":
                expected = hashlib.sha512(
                    f"{payload}{secret}".encode()
                ).hexdigest()
            else:
                logger.warning(f"Unknown signature algorithm: {algorithm}")
                return False
            
            return secrets.compare_digest(expected, signature)
        except Exception as e:
            logger.error(f"Signature validation failed: {e}")
            return False
    
    @staticmethod
    def generate_signature(
        payload: str,
        secret: str,
        algorithm: str = "sha256",
    ) -> str:
        """生成请求签名"""
        if algorithm == "sha256":
            return hashlib.sha256(f"{payload}{secret}".encode()).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(f"{payload}{secret}".encode()).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    @staticmethod
    def validate_timestamp(
        timestamp: int,
        tolerance_ms: int = 5000,
    ) -> bool:
        """
        验证时间戳（防止重放攻击）
        
        Args:
            timestamp: 请求时间戳（毫秒）
            tolerance_ms: 允许的时间偏差（毫秒）
        
        Returns:
            时间戳是否有效
        """
        import time
        
        current_ms = int(time.time() * 1000)
        diff = abs(current_ms - timestamp)
        
        return diff <= tolerance_ms


# 全局实例
api_key_encryption = APIKeyEncryption()
data_masker = DataMasker()
token_generator = TokenGenerator()
request_validator = RequestValidator()


def get_api_key_encryption() -> APIKeyEncryption:
    """获取 API 密钥加密器"""
    return api_key_encryption


def get_data_masker() -> DataMasker:
    """获取数据脱敏器"""
    return data_masker


def get_token_generator() -> TokenGenerator:
    """获取令牌生成器"""
    return token_generator


def get_request_validator() -> RequestValidator:
    """获取请求校验器"""
    return request_validator
