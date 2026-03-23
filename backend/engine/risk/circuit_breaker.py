"""
熔断器 - 紧急情况下停止交易
"""

import time
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta


class CircuitState(Enum):
    """熔断状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态（测试恢复）


class CircuitBreaker:
    """
    熔断器实现
    
    当错误率达到阈值时自动熔断，停止交易
    冷却时间后进入半开状态，尝试恢复
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: int = 60,
        name: str = "default"
    ):
        """
        Args:
            failure_threshold: 触发熔断的失败次数
            success_threshold: 恢复所需的成功次数
            timeout: 熔断超时时间（秒）
            name: 熔断器名称
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_state_change = datetime.now()
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态，自动检查是否需要从 OPEN 转为 HALF_OPEN"""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and \
               datetime.now() - self._last_failure_time > timedelta(seconds=self.timeout):
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """是否可以正常交易"""
        return self.state == CircuitState.CLOSED
    
    def record_success(self):
        """记录成功"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        else:
            self._failure_count = 0
    
    def record_failure(self):
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()
        
        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self._failure_count >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.now()
        
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
    
    def get_status(self) -> dict:
        """获取熔断器状态"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "last_state_change": self._last_state_change.isoformat(),
        }
    
    def reset(self):
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._last_state_change = datetime.now()
