#!/usr/bin/env python3
"""
API 接口测试脚本
测试 FastAPI 应用的各个端点
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / ".env")

import pytest
from fastapi.testclient import TestClient


def test_import_app():
    """测试能否导入应用"""
    print("\n" + "="*60)
    print("测试：导入 FastAPI 应用")
    print("="*60)
    
    try:
        from app.main import app
        print("✅ 成功导入应用")
        print(f"📊 应用名称：{app.title}")
        print(f"📊 版本：{app.version}")
        return True
    except Exception as e:
        print(f"❌ 导入失败：{e}")
        return False


def test_health_endpoint():
    """测试健康检查端点"""
    print("\n" + "="*60)
    print("测试：健康检查端点")
    print("="*60)
    
    try:
        from app.main import app
        client = TestClient(app)
        
        response = client.get("/health")
        
        if response.status_code == 200:
            print(f"✅ 健康检查通过")
            print(f"📊 响应：{response.json()}")
            return True
        else:
            print(f"❌ 健康检查失败：{response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        return False


def test_strategy_list():
    """测试策略列表端点"""
    print("\n" + "="*60)
    print("测试：策略列表端点")
    print("="*60)
    
    try:
        from app.main import app
        client = TestClient(app)
        
        response = client.get("/api/v1/strategy/list")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 策略列表获取成功")
            print(f"📊 策略数量：{len(data.get('strategies', []))}")
            for strategy in data.get('strategies', []):
                print(f"   - {strategy.get('name', 'Unknown')}")
            return True
        else:
            print(f"❌ 请求失败：{response.status_code}")
            print(f"   响应：{response.text}")
            return False
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        return False


def test_data_symbols():
    """测试交易对数据端点"""
    print("\n" + "="*60)
    print("测试：交易对数据端点")
    print("="*60)
    
    try:
        from app.main import app
        client = TestClient(app)
        
        response = client.get("/api/v1/data/symbols")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 交易对数据获取成功")
            symbols = data.get('symbols', [])
            print(f"📊 交易对数量：{len(symbols)}")
            if symbols:
                # 处理符号可能是字典的情况
                symbol_names = []
                for s in symbols[:5]:
                    if isinstance(s, dict):
                        symbol_names.append(s.get('symbol', str(s)))
                    else:
                        symbol_names.append(str(s))
                print(f"   示例：{', '.join(symbol_names)}")
            return True
        else:
            print(f"❌ 请求失败：{response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        return False


def test_backtest_strategies():
    """测试回测策略列表端点"""
    print("\n" + "="*60)
    print("测试：回测策略列表端点")
    print("="*60)
    
    try:
        from app.main import app
        client = TestClient(app)
        
        response = client.get("/api/v1/backtest/strategies")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 回测策略列表获取成功")
            strategies = data.get('strategies', [])
            print(f"📊 可用策略：{len(strategies)}")
            for s in strategies:
                print(f"   - {s}")
            return True
        else:
            print(f"❌ 请求失败：{response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "🚀"*30)
    print(" CryptoQuant API 接口测试")
    print("🚀"*30)
    
    # 先测试导入
    if not test_import_app():
        print("\n❌ 应用导入失败，无法继续测试")
        return False
    
    results = {
        "健康检查": test_health_endpoint(),
        "策略列表": test_strategy_list(),
        "交易对数据": test_data_symbols(),
        "回测策略": test_backtest_strategies(),
    }
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 所有 API 测试通过！")
    else:
        print("\n⚠️  部分测试失败")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
