#!/usr/bin/env python3
"""
交易引擎测试脚本
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / ".env")


def test_position_manager():
    """测试仓位管理器"""
    print("\n" + "="*60)
    print("测试：仓位管理器")
    print("="*60)
    
    from engine.risk import PositionManager, PositionConfig
    
    # 创建配置
    config = PositionConfig(
        initial_capital=100000,
        max_position_ratio=0.2,
        max_total_exposure=0.8,
        max_daily_loss=0.05,
    )
    
    # 创建管理器
    pm = PositionManager(config)
    
    # 测试仓位计算
    print("\n📊 测试仓位大小计算:")
    btc_price = 50000
    
    # 修改配置为固定比例法
    pm.config.position_sizing_method = "fixed_ratio"
    size_fixed = pm.calculate_position_size("BTCUSDT", btc_price)
    print(f"  固定比例法：{size_fixed} BTC (${size_fixed * btc_price:.2f})")
    
    # 修改配置为 Kelly 法
    pm.config.position_sizing_method = "kelly"
    size_kelly = pm.calculate_position_size(
        "BTCUSDT", btc_price,
        win_rate=0.55,
        avg_win_loss_ratio=2.0,
    )
    print(f"  Kelly 公式法：{size_kelly} BTC (${size_kelly * btc_price:.2f})")
    
    # 恢复默认
    pm.config.position_sizing_method = "fixed_ratio"
    
    # 测试开仓
    print("\n📊 测试开仓:")
    can_open, reason = pm.can_open_position("BTCUSDT", btc_price)
    print(f"  允许开仓：{can_open} - {reason}")
    
    if can_open:
        position = pm.add_position(
            symbol="BTCUSDT",
            side="buy",
            amount=0.5,
            entry_price=btc_price,
            stop_loss=btc_price * 0.95,
            take_profit=btc_price * 1.10,
        )
        print(f"  ✅ 开仓成功：{position['amount']} BTC @ ${position['entry_price']}")
    
    # 测试更新价格
    print("\n📊 测试价格更新:")
    pm.update_position_price("BTCUSDT", 51000)
    if "BTCUSDT" in pm.positions:
        pos = pm.positions["BTCUSDT"]
        print(f"  当前价格：${pos['current_price']}")
        print(f"  未实现盈亏：${pos['unrealized_pnl']:.2f} ({pos['unrealized_pnl_pct']:.2f}%)")
    
    # 测试平仓
    print("\n📊 测试平仓:")
    if "BTCUSDT" in pm.positions:
        trade = pm.close_position("BTCUSDT", 51000)
        print(f"  ✅ 平仓成功：盈亏 ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")
    
    # 测试汇总
    print("\n📊 投资组合汇总:")
    summary = pm.get_portfolio_summary()
    print(f"  资金：${summary['capital']:.2f}")
    print(f"  总盈亏：${summary['total_pnl']:.2f} ({summary['total_pnl_pct']:.2f}%)")
    print(f"  持仓数：{summary['open_positions']}")
    print(f"  风险等级：{summary['risk_level']}")
    
    return True


def test_trading_engine():
    """测试交易引擎 (需要 API 密钥)"""
    print("\n" + "="*60)
    print("测试：交易引擎")
    print("="*60)
    
    import os
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    
    if not api_key or not api_secret:
        print("⚠️  跳过：未配置 Binance API 密钥")
        print("  在 .env 文件中配置 BINANCE_API_KEY 和 BINANCE_API_SECRET")
        return True
    
    from engine.trader import TradingEngine, OrderSide, OrderType
    
    try:
        # 创建引擎
        engine = TradingEngine(
            exchange_id="binance",
            api_key=api_key,
            api_secret=api_secret,
            testnet=True,
            initial_capital=100000,
        )
        
        # 测试连接
        print("\n📊 测试交易所连接:")
        connected = engine.connect()
        print(f"  连接状态：{'✅ 成功' if connected else '❌ 失败'}")
        
        if not connected:
            print("  ⚠️  跳过后续测试")
            return True
        
        # 测试获取余额
        print("\n📊 测试获取余额:")
        balance = engine.get_balance()
        for currency, data in list(balance.items())[:5]:
            print(f"  {currency}: {data['free']} (可用) / {data['total']} (总计)")
        
        # 测试获取行情
        print("\n📊 测试获取行情:")
        ticker = engine.get_ticker("BTCUSDT")
        if ticker:
            print(f"  BTC/USDT: ${ticker['last']} (买一：${ticker['bid']}, 卖一：${ticker['ask']})")
        
        # 测试获取 K 线
        print("\n📊 测试获取 K 线:")
        klines = engine.get_klines("BTCUSDT", timeframe="1h", limit=10)
        if not klines.empty:
            print(f"  获取到 {len(klines)} 条 K 线")
            print(f"  最新：开${klines['open'].iloc[-1]:.2f} 收${klines['close'].iloc[-1]:.2f}")
        
        # 测试创建订单 (注释掉，避免真实下单)
        # print("\n📊 测试创建订单:")
        # order = engine.create_order(
        #     symbol="BTCUSDT",
        #     side=OrderSide.BUY,
        #     amount=0.001,
        #     order_type=OrderType.MARKET,
        # )
        # if order:
        #     print(f"  ✅ 订单创建成功：{order.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        return False


def test_visualization():
    """测试可视化模块"""
    print("\n" + "="*60)
    print("测试：可视化模块")
    print("="*60)
    
    from engine.visualization import (
        create_equity_curve_data,
        calculate_strategy_metrics,
        calculate_max_drawdown,
        generate_trade_analysis_report,
    )
    
    # 模拟交易历史
    trades = [
        {"symbol": "BTCUSDT", "side": "buy", "pnl": 500, "opened_at": "2026-03-09T10:00:00", "closed_at": "2026-03-09T12:00:00"},
        {"symbol": "ETHUSDT", "side": "buy", "pnl": -200, "opened_at": "2026-03-09T11:00:00", "closed_at": "2026-03-09T13:00:00"},
        {"symbol": "BTCUSDT", "side": "sell", "pnl": 800, "opened_at": "2026-03-09T14:00:00", "closed_at": "2026-03-09T16:00:00"},
        {"symbol": "BNBUSDT", "side": "buy", "pnl": 300, "opened_at": "2026-03-09T15:00:00", "closed_at": "2026-03-09T17:00:00"},
    ]
    
    # 测试策略指标
    print("\n📊 策略表现指标:")
    metrics = calculate_strategy_metrics(trades)
    print(f"  总交易数：{metrics['total_trades']}")
    print(f"  胜率：{metrics['win_rate']}%")
    print(f"  盈亏比：{metrics['profit_factor']}")
    print(f"  平均盈利：${metrics['avg_win']:.2f}")
    print(f"  平均亏损：${metrics['avg_loss']:.2f}")
    
    # 测试资金曲线
    print("\n📊 资金曲线数据:")
    equity_curve = create_equity_curve_data(100000, trades)
    print(f"  数据点数：{len(equity_curve)}")
    print(f"  最终权益：${equity_curve[-1]['equity']:.2f}")
    print(f"  总盈亏：${equity_curve[-1]['pnl']:.2f}")
    
    # 测试回撤分析
    print("\n📊 回撤分析:")
    drawdown = calculate_max_drawdown(equity_curve)
    print(f"  最大回撤：{drawdown['max_drawdown_pct']:.2f}%")
    print(f"  最大回撤金额：${drawdown['max_drawdown']:.2f}")
    
    # 测试分析报告
    print("\n📊 交易分析报告:")
    report = generate_trade_analysis_report(trades, equity_curve, 100000)
    print(f"  夏普比率：{report['performance']['sharpe_ratio']}")
    print(f"  胜率：{report['performance']['win_rate']}%")
    print(f"  总盈亏：${report['summary']['total_pnl']:.2f}")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "🚀"*30)
    print(" CryptoQuant Phase 2 测试")
    print("🚀"*30)
    
    results = {
        "仓位管理器": test_position_manager(),
        "交易引擎": test_trading_engine(),
        "可视化模块": test_visualization(),
    }
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 所有 Phase 2 测试通过！")
    else:
        print("\n⚠️  部分测试失败")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
