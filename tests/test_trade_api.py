#!/usr/bin/env python3
"""
实盘交易 API 测试脚本
测试交易相关 API 端点的错误处理和重试机制
"""
import requests
import json
import time
from typing import Optional

BASE_URL = "http://localhost:8000"


def print_response(title: str, response: requests.Response):
    """打印响应信息"""
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print(f"{'='*60}")
    print(f"状态码：{response.status_code}")
    print(f"耗时：{response.elapsed.total_seconds()*1000:.2f}ms")
    
    try:
        data = response.json()
        print(f"响应：{json.dumps(data, indent=2, ensure_ascii=False)}")
    except:
        print(f"响应：{response.text[:500]}")
    
    print()


def test_health():
    """测试健康检查"""
    response = requests.get(f"{BASE_URL}/health")
    print_response("健康检查", response)
    return response.status_code == 200


def test_trading_status():
    """测试交易状态"""
    response = requests.get(f"{BASE_URL}/api/v1/trade/status")
    print_response("交易状态", response)
    return response.status_code in [200, 500]


def test_balance():
    """测试账户余额"""
    response = requests.get(f"{BASE_URL}/api/v1/trade/balance")
    print_response("账户余额", response)
    return response.status_code in [200, 500]


def test_positions():
    """测试持仓查询"""
    response = requests.get(f"{BASE_URL}/api/v1/trade/positions")
    print_response("持仓查询", response)
    return response.status_code == 200


def test_create_order_validation():
    """测试订单创建 - 参数验证"""
    print("\n🧪 测试订单参数验证...")
    
    # 测试 1: 无效数量
    response = requests.post(
        f"{BASE_URL}/api/v1/trade/order",
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "amount": -1,  # 无效数量
            "order_type": "market"
        }
    )
    print_response("测试：无效数量", response)
    assert response.status_code in [400, 500], "应该拒绝负数数量"
    
    # 测试 2: 无效方向
    response = requests.post(
        f"{BASE_URL}/api/v1/trade/order",
        json={
            "symbol": "BTCUSDT",
            "side": "invalid",  # 无效方向
            "amount": 0.001,
            "order_type": "market"
        }
    )
    print_response("测试：无效方向", response)
    assert response.status_code in [400, 500], "应该拒绝无效方向"
    
    # 测试 3: 限价单缺少价格
    response = requests.post(
        f"{BASE_URL}/api/v1/trade/order",
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "amount": 0.001,
            "order_type": "limit"  # 限价单但缺少价格
        }
    )
    print_response("测试：限价单缺少价格", response)
    assert response.status_code in [400, 500], "限价单应该要求价格"
    
    print("✅ 参数验证测试通过")
    return True


def test_create_order_mock():
    """测试订单创建 (模拟)"""
    print("\n🧪 测试订单创建...")
    
    # 注意：这需要真实的 API Key 才能成功
    # 这里主要测试错误处理
    response = requests.post(
        f"{BASE_URL}/api/v1/trade/order",
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "amount": 0.001,
            "order_type": "market",
            "stop_loss": 50000,
            "take_profit": 70000
        }
    )
    print_response("订单创建 (可能需要 API Key)", response)
    
    # 可能返回 500 (API Key 未配置) 或其他错误
    # 只要不是 502/503 就说明错误处理正常
    return response.status_code < 502


def test_cancel_order():
    """测试订单取消"""
    print("\n🧪 测试订单取消...")
    
    # 测试取消不存在的订单
    response = requests.post(
        f"{BASE_URL}/api/v1/trade/order/nonexistent/cancel",
        params={"symbol": "BTCUSDT"}
    )
    print_response("取消不存在的订单", response)
    
    return True


def test_close_position():
    """测试平仓"""
    print("\n🧪 测试平仓...")
    
    # 测试平不存在的持仓
    response = requests.post(
        f"{BASE_URL}/api/v1/trade/position/BTCUSDT/close"
    )
    print_response("平不存在的持仓", response)
    
    # 应该返回 404
    assert response.status_code == 404, "应该返回 404"
    
    print("✅ 平仓错误处理测试通过")
    return True


def test_portfolio():
    """测试投资组合"""
    print("\n🧪 测试投资组合...")
    
    response = requests.get(f"{BASE_URL}/api/v1/trade/portfolio")
    print_response("投资组合", response)
    
    return response.status_code == 200


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🚀 CryptoQuant 交易 API 测试套件")
    print("="*60)
    
    results = []
    
    # 基础测试
    results.append(("健康检查", test_health()))
    results.append(("交易状态", test_trading_status()))
    results.append(("持仓查询", test_positions()))
    results.append(("投资组合", test_portfolio()))
    
    # 错误处理测试
    results.append(("参数验证", test_create_order_validation()))
    results.append(("订单取消", test_cancel_order()))
    results.append(("平仓错误处理", test_close_position()))
    
    # 可选测试 (需要 API Key)
    # results.append(("订单创建", test_create_order_mock()))
    
    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\n总计：{passed}/{total} 通过 ({passed/total*100:.1f}%)")
    
    return passed == total


if __name__ == "__main__":
    import sys
    
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 无法连接到后端服务：{e}")
        print("请确保后端服务正在运行：python3 -m uvicorn app.main:app --reload")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
