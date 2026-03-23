"""
Prometheus 监控指标
"""
from prometheus_client import Counter, Gauge, Histogram, Summary, start_http_server
from typing import Optional
import time


# ============================================
# 计数器 (Counter) - 只增不减
# ============================================

# API 请求计数
api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

# 订单计数
orders_total = Counter(
    'orders_total',
    'Total orders executed',
    ['exchange', 'symbol', 'side', 'type', 'status']
)

# 交易计数
trades_total = Counter(
    'trades_total',
    'Total trades completed',
    ['exchange', 'symbol', 'side']
)

# 错误计数
errors_total = Counter(
    'errors_total',
    'Total errors',
    ['module', 'error_type']
)

# 策略信号计数
strategy_signals_total = Counter(
    'strategy_signals_total',
    'Total strategy signals',
    ['strategy', 'symbol', 'signal_type']
)


# ============================================
# 仪表 (Gauge) - 可增可减
# ============================================

# 账户余额
account_balance = Gauge(
    'account_balance',
    'Account balance',
    ['exchange', 'currency']
)

# 持仓
position_size = Gauge(
    'position_size',
    'Current position size',
    ['symbol', 'side']
)

# 未实现盈亏
unrealized_pnl = Gauge(
    'unrealized_pnl',
    'Unrealized PnL',
    ['symbol']
)

# 风险指标
risk_metrics = Gauge(
    'risk_metrics',
    'Risk metrics',
    ['metric_type']
)

# 系统状态
system_status = Gauge(
    'system_status',
    'System status (1=up, 0=down)',
    ['component']
)

# 活跃策略数量
active_strategies = Gauge(
    'active_strategies',
    'Number of active strategies'
)


# ============================================
# 直方图 (Histogram) - 分布统计
# ============================================

# API 响应时间
api_request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# 订单执行时间
order_execution_duration = Histogram(
    'order_execution_duration_seconds',
    'Order execution duration in seconds',
    ['exchange', 'type'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

# 回测执行时间
backtest_duration = Histogram(
    'backtest_duration_seconds',
    'Backtest execution duration in seconds',
    ['strategy'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0)
)


# ============================================
# 摘要 (Summary) - 分位数统计
# ============================================

# 交易盈亏分布
trade_pnl = Summary(
    'trade_pnl',
    'Trade PnL distribution',
    ['symbol', 'side']
)

# 策略收益率
strategy_returns = Summary(
    'strategy_returns',
    'Strategy returns',
    ['strategy']
)


# ============================================
# 工具函数
# ============================================

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, port: int = 9090):
        self.port = port
        self.started = False
    
    def start_server(self):
        """启动 Prometheus 指标服务器"""
        if not self.started:
            try:
                start_http_server(self.port)
                self.started = True
                print(f"📊 Prometheus metrics server started on port {self.port}")
            except OSError as e:
                if "Address already in use" in str(e):
                    print(f"⚠️  Port {self.port} already in use, skipping metrics server")
                else:
                    raise
    
    def record_api_request(self, method: str, endpoint: str, status: int, duration: float):
        """记录 API 请求"""
        api_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status
        ).inc()
        
        api_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        order_type: str,
        status: str,
        duration: float,
    ):
        """记录订单"""
        orders_total.labels(
            exchange=exchange,
            symbol=symbol,
            side=side,
            type=order_type,
            status=status
        ).inc()
        
        order_execution_duration.labels(
            exchange=exchange,
            type=order_type
        ).observe(duration)
    
    def record_trade(self, exchange: str, symbol: str, side: str, pnl: float):
        """记录交易"""
        trades_total.labels(
            exchange=exchange,
            symbol=symbol,
            side=side
        ).inc()
        
        trade_pnl.labels(
            symbol=symbol,
            side=side
        ).observe(pnl)
    
    def record_error(self, module: str, error_type: str):
        """记录错误"""
        errors_total.labels(
            module=module,
            error_type=error_type
        ).inc()
    
    def update_balance(self, exchange: str, currency: str, balance: float):
        """更新余额"""
        account_balance.labels(
            exchange=exchange,
            currency=currency
        ).set(balance)
    
    def update_position(self, symbol: str, side: str, size: float, pnl: float):
        """更新持仓"""
        position_size.labels(
            symbol=symbol,
            side=side
        ).set(size)
        
        unrealized_pnl.labels(
            symbol=symbol
        ).set(pnl)
    
    def update_risk_metric(self, metric_type: str, value: float):
        """更新风险指标"""
        risk_metrics.labels(
            metric_type=metric_type
        ).set(value)
    
    def set_system_status(self, component: str, status: bool):
        """设置系统状态"""
        system_status.labels(
            component=component
        ).set(1 if status else 0)
    
    def update_active_strategies(self, count: int):
        """更新活跃策略数量"""
        active_strategies.set(count)
    
    def record_strategy_signal(self, strategy: str, symbol: str, signal_type: str):
        """记录策略信号"""
        strategy_signals_total.labels(
            strategy=strategy,
            symbol=symbol,
            signal_type=signal_type
        ).inc()
    
    def record_backtest(self, strategy: str, duration: float):
        """记录回测"""
        backtest_duration.labels(
            strategy=strategy
        ).observe(duration)


# 全局指标收集器实例
metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """获取指标收集器"""
    return metrics
