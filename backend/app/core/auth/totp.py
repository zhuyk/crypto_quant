"""
TOTP 双因素认证完整实现
"""

import pyotp
import base64
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TOTPConfig:
    """TOTP 配置"""
    secret: str
    issuer: str
    account_name: str
    algorithm: str = "SHA1"
    digits: int = 6
    period: int = 30


class TOTPAuthenticator:
    """
    TOTP 双因素认证
    
    兼容 Google Authenticator、Authy 等
    """
    
    def __init__(
        self,
        issuer: str = "CryptoQuant",
        algorithm: str = "SHA1",
        digits: int = 6,
        period: int = 30,
    ):
        """
        Args:
            issuer: 发行者名称
            algorithm: 算法
            digits: 验证码位数
            period: 有效期（秒）
        """
        self.issuer = issuer
        self.algorithm = algorithm
        self.digits = digits
        self.period = period
    
    def generate_secret(self) -> str:
        """生成 TOTP 密钥"""
        secret = pyotp.random_base32()
        logger.info(f"生成 TOTP 密钥")
        return secret
    
    def generate_provisioning_uri(
        self,
        secret: str,
        account_name: str,
    ) -> str:
        """
        生成配置 URI（用于生成 QR 码）
        
        Args:
            secret: TOTP 密钥
            account_name: 账户名（通常是邮箱）
            
        Returns:
            str: provisioning URI
        """
        totp = pyotp.TOTP(
            secret,
            issuer=self.issuer,
            digits=self.digits,
            period=self.period,
        )
        
        uri = totp.provisioning_uri(
            name=account_name,
            issuer_name=self.issuer,
        )
        
        logger.info(f"生成配置 URI: {account_name}")
        
        return uri
    
    def generate_qr_code_data_uri(
        self,
        secret: str,
        account_name: str,
    ) -> str:
        """
        生成 QR 码 Data URI
        
        Args:
            secret: TOTP 密钥
            account_name: 账户名
            
        Returns:
            str: QR 码 Data URI (data:image/png;base64,...)
        """
        import qrcode
        import io
        
        # 生成配置 URI
        uri = self.generate_provisioning_uri(secret, account_name)
        
        # 生成 QR 码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        # 转换为图片
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 转换为 Data URI
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_data = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_data}"
    
    def verify_code(
        self,
        secret: str,
        code: str,
        window: int = 1,
    ) -> bool:
        """
        验证 TOTP 验证码
        
        Args:
            secret: TOTP 密钥
            code: 验证码（6 位数字）
            window: 允许的时间窗口（前后几个周期）
            
        Returns:
            bool: 是否有效
        """
        totp = pyotp.TOTP(
            secret,
            digits=self.digits,
            period=self.period,
        )
        
        # 验证（允许前后 1 个周期的误差）
        is_valid = totp.verify(code, valid_window=window)
        
        if is_valid:
            logger.info(f"TOTP 验证成功")
        else:
            logger.warning(f"TOTP 验证失败")
        
        return is_valid
    
    def get_current_totp(self, secret: str) -> str:
        """
        获取当前 TOTP 验证码（用于测试）
        
        Args:
            secret: TOTP 密钥
            
        Returns:
            str: 当前验证码
        """
        totp = pyotp.TOTP(
            secret,
            digits=self.digits,
            period=self.period,
        )
        
        return totp.now()
    
    def check_backup_codes(
        self,
        code: str,
        backup_codes: list,
    ) -> Tuple[bool, Optional[int]]:
        """
        检查备用码
        
        Args:
            code: 输入的验证码
            backup_codes: 备用码列表
            
        Returns:
            (是否有效，使用的备用码索引)
        """
        for i, backup_code in enumerate(backup_codes):
            if code == backup_code:
                logger.info(f"使用备用码验证成功")
                return True, i
        
        return False, None
    
    def generate_backup_codes(
        self,
        count: int = 10,
        code_length: int = 8,
    ) -> list:
        """
        生成备用码
        
        Args:
            count: 备用码数量
            code_length: 备用码长度
            
        Returns:
            list: 备用码列表
        """
        import secrets
        import string
        
        alphabet = string.ascii_uppercase + string.digits
        codes = []
        
        for _ in range(count):
            code = ''.join(secrets.choice(alphabet) for _ in range(code_length))
            codes.append(code)
        
        logger.info(f"生成 {count} 个备用码")
        
        return codes


# ========== 与 UserManager 集成 ==========

def enable_totp_for_user(user_manager, user_id: str, account_name: str) -> dict:
    """
    为用户启用 TOTP
    
    Args:
        user_manager: 用户管理器实例
        user_id: 用户 ID
        account_name: 账户名
        
    Returns:
        dict: {secret, qr_code_uri, backup_codes}
    """
    authenticator = TOTPAuthenticator()
    
    # 生成密钥
    secret = authenticator.generate_secret()
    
    # 生成 QR 码 Data URI
    qr_code_data_uri = authenticator.generate_qr_code_data_uri(
        secret,
        account_name,
    )
    
    # 生成备用码
    backup_codes = authenticator.generate_backup_codes()
    
    # 保存密钥到用户（临时，确认启用后再保存）
    user = user_manager.get_user(user_id)
    if user:
        user.two_factor_secret = secret
        user.two_factor_enabled = False  # 需要用户确认后才启用
    
    return {
        'secret': secret,
        'qr_code_data_uri': qr_code_data_uri,
        'backup_codes': backup_codes,
    }


def confirm_totp_for_user(
    user_manager,
    user_id: str,
    code: str,
) -> bool:
    """
    确认启用 TOTP
    
    Args:
        user_manager: 用户管理器实例
        user_id: 用户 ID
        code: TOTP 验证码
        
    Returns:
        bool: 是否成功
    """
    authenticator = TOTPAuthenticator()
    user = user_manager.get_user(user_id)
    
    if not user or not user.two_factor_secret:
        return False
    
    # 验证验证码
    is_valid = authenticator.verify_code(user.two_factor_secret, code)
    
    if is_valid:
        # 启用双因素认证
        user.two_factor_enabled = True
        logger.info(f"用户 {user_id} 启用 TOTP 成功")
        return True
    
    return False


def verify_totp_for_login(
    user_manager,
    user_id: str,
    code: str,
    backup_code: Optional[str] = None,
) -> bool:
    """
    登录时验证 TOTP
    
    Args:
        user_manager: 用户管理器实例
        user_id: 用户 ID
        code: TOTP 验证码或备用码
        backup_code: 备用码（可选）
        
    Returns:
        bool: 是否验证成功
    """
    authenticator = TOTPAuthenticator()
    user = user_manager.get_user(user_id)
    
    if not user or not user.two_factor_enabled:
        return True  # 未启用双因素，直接通过
    
    # 优先尝试 TOTP 验证
    if authenticator.verify_code(user.two_factor_secret, code):
        return True
    
    # 尝试备用码
    if backup_code:
        is_valid, _ = authenticator.check_backup_codes(
            backup_code,
            user.backup_codes if hasattr(user, 'backup_codes') else [],
        )
        if is_valid:
            return True
    
    return False
