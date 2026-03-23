"""
回测报告
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any
import json


@dataclass
class BacktestReport:
    """回测报告"""
    
    # 策略信息
    strategy_name: str
    
    # 资金信息
    initial_capital: float
    final_capital: float
    
    # 收益指标
    total_return: float  # 总收益率
    annual_return: float  # 年化收益率
    sharpe_ratio: float  # 夏普比率
    max_drawdown: float  # 最大回撤
    
    # 交易统计
    win_rate: float  # 胜率
    profit_factor: float  # 盈亏比
    total_trades: int  # 总交易次数
    winning_trades: int  # 盈利交易次数
    losing_trades: int  # 亏损交易次数
    avg_trade_pnl: float  # 平均盈亏
    
    # 详细数据
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "strategy_name": self.strategy_name,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_pnl": self.avg_trade_pnl,
            "equity_curve": self.equity_curve,
            "trades_summary": self._summarize_trades(),
        }
    
    def _summarize_trades(self) -> list:
        """简化交易记录 (用于 JSON 序列化)"""
        summary = []
        for trade in self.trades:
            if 'pnl' in trade:  # 只保留平仓记录
                summary.append({
                    "symbol": trade.get("symbol", ""),
                    "side": trade.get("side", ""),
                    "entry_price": trade.get("entry_price", 0),
                    "exit_price": trade.get("exit_price", 0),
                    "pnl": trade.get("pnl", 0),
                    "pnl_pct": trade.get("pnl_pct", 0),
                    "exit_reason": trade.get("exit_reason", ""),
                })
        return summary
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent)
    
    def print_summary(self):
        """打印回测摘要"""
        print("\n" + "="*60)
        print(f"回测报告 - {self.strategy_name}")
        print("="*60)
        print(f"初始资金：     ${self.initial_capital:,.2f}")
        print(f"最终资金：     ${self.final_capital:,.2f}")
        print(f"总收益率：     {self.total_return:>10.2%}")
        print(f"年化收益率：   {self.annual_return:>10.2%}")
        print(f"夏普比率：     {self.sharpe_ratio:>10.2f}")
        print(f"最大回撤：     {self.max_drawdown:>10.2%}")
        print(f"胜率：         {self.win_rate:>10.2%}")
        print(f"盈亏比：       {self.profit_factor:>10.2f}")
        print(f"总交易次数：   {self.total_trades:>10d}")
        print(f"盈利交易：     {self.winning_trades:>10d}")
        print(f"亏损交易：     {self.losing_trades:>10d}")
        print(f"平均盈亏：     ${self.avg_trade_pnl:>10,.2f}")
        print("="*60 + "\n")
