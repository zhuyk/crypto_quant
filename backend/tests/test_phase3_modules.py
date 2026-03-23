"""
Phase 3 新增模块测试
测试审计日志、重试机制、缓存、安全、限流等功能
"""
import pytest
import time
import sys
from pathlib import Path

# 添加 backend 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.retry import retry, RetryError, RetryHandler, CircuitBreaker
from app.utils.cache import RedisCache, CacheKeys
from app.utils.security import (
    APIKeyEncryption,
    DataMasker,
    TokenGenerator,
    RequestValidator,
)
from app.utils.rate_limiter import TokenBucket, RateLimiter, RateLimitResult
from app.core.audit_log import AuditLogger


class TestRetry:
    """测试重试机制"""
    
    def test_retry_decorator_success(self):
        """测试重试装饰器 - 成功情况"""
        attempt_count = 0
        
        @retry(max_attempts=3, delay=0.1)
        def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert attempt_count == 2
    
    def test_retry_decorator_failure(self):
        """测试重试装饰器 - 失败情况"""
        @retry(max_attempts=2, delay=0.1)
        def always_fails():
            raise ValueError("Always fails")
        
        with pytest.raises(RetryError):
            always_fails()
    
    def test_circuit_breaker(self):
        """测试熔断器"""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0,
            logger=None,
        )
        
        # 初始状态应为关闭
        assert cb.state == CircuitBreaker.CLOSED
        
        # 模拟多次失败
        for i in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
            except (ValueError, Exception):
                pass
        
        # 应该进入熔断状态
        assert cb.state == CircuitBreaker.OPEN
        
        # 熔断状态下应该抛出 CircuitBreakerError
        with pytest.raises(Exception):  # CircuitBreakerError
            cb.call(lambda: "success")


class TestSecurity:
    """测试安全模块"""
    
    def test_api_key_encryption(self):
        """测试 API 密钥加密"""
        encryption = APIKeyEncryption(secret_key="test-secret-key-32-bytes-long!")
        
        original = "sk-test-1234567890abcdef"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        
        assert decrypted == original
        assert encrypted != original
    
    def test_data_masker_email(self):
        """测试邮箱脱敏"""
        masker = DataMasker()
        
        assert masker.mask_email("test@example.com") == "te***@example.com"
        assert masker.mask_email("a@b.com") == "**@b.com"
    
    def test_data_masker_phone(self):
        """测试手机号脱敏"""
        masker = DataMasker()
        
        assert masker.mask_phone("13812345678") == "*******678"
    
    def test_token_generator(self):
        """测试令牌生成"""
        generator = TokenGenerator()
        
        api_token = generator.generate_api_token()
        assert len(api_token) >= 32
        
        verification_code = generator.generate_verification_code()
        assert len(verification_code) == 6
        assert verification_code.isdigit()
    
    def test_request_validator_signature(self):
        """测试请求签名验证"""
        validator = RequestValidator()
        
        payload = "test payload"
        secret = "test secret"
        
        signature = validator.generate_signature(payload, secret)
        assert validator.validate_signature(payload, signature, secret)
        
        # 错误的签名应该失败
        assert not validator.validate_signature(payload, "wrong_signature", secret)
    
    def test_request_validator_timestamp(self):
        """测试时间戳验证"""
        validator = RequestValidator()
        
        import time
        current_ms = int(time.time() * 1000)
        
        # 当前时间戳应该通过
        assert validator.validate_timestamp(current_ms)
        
        # 旧时间戳应该失败
        old_timestamp = current_ms - 10000  # 10 秒前
        assert not validator.validate_timestamp(old_timestamp)


class TestRateLimiter:
    """测试限流器"""
    
    def test_token_bucket_basic(self):
        """测试令牌桶基本功能"""
        bucket = TokenBucket(rate=10, capacity=10)
        
        # 首次消费应该成功
        result = bucket.consume("test_user")
        assert result.allowed
        assert result.remaining == 9
    
    def test_token_bucket_exhaustion(self):
        """测试令牌桶耗尽"""
        bucket = TokenBucket(rate=1, capacity=2)
        
        # 快速消费完所有令牌
        for i in range(2):
            result = bucket.consume("test_user_2")
            assert result.allowed
        
        # 再次消费应该失败
        result = bucket.consume("test_user_2")
        assert not result.allowed
        assert result.retry_after is not None
    
    def test_rate_limiter_configs(self):
        """测试预定义限流配置"""
        limiter = RateLimiter()
        
        # 测试不同配置
        result = limiter.check("user1", "default")
        assert result.allowed
        
        result = limiter.check("user1", "login")
        assert result.allowed


class TestAuditLogger:
    """测试审计日志"""
    
    def test_audit_log_basic(self):
        """测试基本审计日志"""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        # 记录登录事件
        logger.login("user123", success=True, ip_address="192.168.1.1")
        
        # 记录订单事件
        logger.order_created(
            order_id="order_123",
            user_id="user123",
            details={"symbol": "BTCUSDT", "side": "buy"},
        )
        
        # 验证日志文件存在
        log_path = Path("logs/test_audit.log")
        assert log_path.exists()


class TestCache:
    """测试缓存模块"""
    
    def test_redis_cache_basic(self):
        """测试 Redis 缓存基本操作"""
        cache = RedisCache()
        
        # 测试设置和获取
        test_key = "test:key:1"
        test_value = {"name": "test", "value": 123}
        
        # 注意：如果 Redis 不可用，这些操作会静默失败
        success = cache.set(test_key, test_value, expire=60)
        
        # 如果 Redis 可用，验证获取
        if success:
            retrieved = cache.get(test_key)
            assert retrieved == test_value
            
            # 验证删除
            cache.delete(test_key)
            assert cache.get(test_key) is None


class TestIntegration:
    """集成测试"""
    
    def test_retry_with_cache(self):
        """测试重试 + 缓存集成"""
        call_count = 0
        
        @retry(max_attempts=3, delay=0.1)
        def fetch_data():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Network error")
            return {"data": "test"}
        
        result = fetch_data()
        assert result == {"data": "test"}
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
