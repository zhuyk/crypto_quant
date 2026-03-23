#!/usr/bin/env python3
"""
快速配置交易所 API Key - 命令行版本
用于快速添加交易所到 CryptoQuant 系统
"""

import os
import sys
import json
import requests
import getpass
from pathlib import Path

# API 基础 URL
API_BASE_URL = "http://localhost:8000/api/v1"

# 支持的交易所
SUPPORTED_EXCHANGES = {
    "1": {"name": "Binance (币安)", "id": "binance", "requires_passphrase": False},
    "2": {"name": "OKX", "id": "okx", "requires_passphrase": True},
    "3": {"name": "Bybit", "id": "bybit", "requires_passphrase": True},
    "4": {"name": "HTX (火币)", "id": "htx", "requires_passphrase": False},
    "5": {"name": "Gate.io", "id": "gate", "requires_passphrase": False},
}

def get_auth_token():
    """获取认证 Token"""
    # 尝试从环境变量获取
    token = os.environ.get("CRYPTO_QUANT_TOKEN")
    if token:
        return token
    
    # 尝试从文件获取
    token_file = Path.home() / ".crypto_quant" / "token"
    if token_file.exists():
        with open(token_file, "r") as f:
            return f.read().strip()
    
    return None

def login():
    """登录获取 Token"""
    print("\n🔐 用户登录")
    print("-" * 40)
    
    username = input("用户名：").strip()
    password = getpass.getpass("密码：").strip()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            
            # 保存 Token
            token_dir = Path.home() / ".crypto_quant"
            token_dir.mkdir(parents=True, exist_ok=True)
            
            token_file = token_dir / "token"
            with open(token_file, "w") as f:
                f.write(token)
            os.chmod(token_file, 0o600)
            
            print(f"\n✅ 登录成功！欢迎 {username}")
            return token
        else:
            print(f"\n❌ 登录失败：{response.json().get('detail', '未知错误')}")
            return None
            
    except Exception as e:
        print(f"\n❌ 请求失败：{e}")
        return None

def add_exchange_key(token):
    """添加交易所 API Key"""
    print("\n" + "=" * 60)
    print("🏦 添加交易所 API Key")
    print("=" * 60)
    
    # 选择交易所
    print("\n选择交易所:")
    for key, info in SUPPORTED_EXCHANGES.items():
        print(f"  {key}. {info['name']}")
    
    while True:
        choice = input("\n请输入交易所编号 (1-5): ").strip()
        if choice in SUPPORTED_EXCHANGES:
            break
        print("❌ 无效选择，请重试")
    
    exchange_info = SUPPORTED_EXCHANGES[choice]
    exchange_id = exchange_info['id']
    
    print(f"\n✓ 已选择：{exchange_info['name']}")
    
    # 输入配置
    print("\n请输入 API 凭证")
    print("(提示：输入时不会显示，按 Enter 确认)")
    
    name = input("名称（例如：主账户）: ").strip()
    if not name:
        name = f"{exchange_info['name']}主账户"
    
    api_key = getpass.getpass("API Key: ").strip()
    api_secret = getpass.getpass("API Secret: ").strip()
    
    if not api_key or not api_secret:
        print("❌ API Key 和 Secret 不能为空")
        return
    
    # OKX/Bybit 需要 Passphrase
    passphrase = None
    if exchange_info['requires_passphrase']:
        print("\n⚠️ 此交易所需要 Passphrase（创建 API Key 时设置）")
        passphrase = getpass.getpass("API Passphrase: ").strip()
    
    # 是否测试网
    testnet_input = input("\n使用测试网？(y/n, 默认 n): ").strip().lower()
    is_testnet = testnet_input == 'y'
    
    # 权限选择
    print("\n选择权限（输入数字，多个用逗号分隔）:")
    print("  1. 交易执行 (trade)")
    print("  2. 读取行情 (read)")
    print("  3. 提现 (withdraw) - 不推荐")
    
    perm_input = input("权限（默认 1,2）: ").strip()
    if not perm_input:
        permissions = ["trade", "read"]
    else:
        perm_map = {
            "1": "trade",
            "2": "read",
            "3": "withdraw",
        }
        permissions = []
        for p in perm_input.split(","):
            p = p.strip()
            if p in perm_map:
                permissions.append(perm_map[p])
        if not permissions:
            permissions = ["trade", "read"]
    
    # 构建请求
    payload = {
        "exchange": exchange_id,
        "name": name,
        "api_key": api_key,
        "api_secret": api_secret,
        "permissions": permissions,
        "is_testnet": is_testnet,
    }
    
    if passphrase:
        payload["passphrase"] = passphrase
    
    # 发送请求
    print("\n📡 正在提交...")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/exchange-keys",
            headers={"Authorization": f"Bearer {token}"},
            json=payload
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            print("\n" + "=" * 60)
            print("✅ 添加成功！")
            print("=" * 60)
            print(f"\n交易所：{exchange_info['name']}")
            print(f"名称：{data.get('name')}")
            print(f"API Key: {data.get('api_key_prefix')}")
            print(f"权限：{', '.join(data.get('permissions', []))}")
            print(f"测试网：{'是' if data.get('is_testnet') else '否'}")
            print(f"状态：{'✓ 活跃' if data.get('is_active') else '✗ 停用'}")
            
            # 询问是否测试连接
            test = input("\n🔌 是否立即测试连接？(y/n): ").strip().lower()
            if test == 'y':
                test_connection(token, data['id'])
            
            print("\n💡 提示：")
            print(f"   - 访问 http://localhost:3000/exchange-keys 管理所有交易所")
            print(f"   - 在页面中可以编辑、测试、删除交易所配置")
            
        else:
            error_data = response.json()
            print(f"\n❌ 添加失败：{error_data.get('detail', '未知错误')}")
            
    except Exception as e:
        print(f"\n❌ 请求失败：{e}")

def test_connection(token, key_id):
    """测试连接"""
    print("\n🔌 测试连接中...")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/exchange-keys/{key_id}/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        data = response.json()
        
        if data.get("success"):
            print("\n✅ 连接成功！")
            print(f"消息：{data.get('message')}")
            if data.get("balance"):
                print("\n账户余额:")
                for currency, amount in data.get("balance", {}).items():
                    if amount > 0:
                        print(f"  {currency}: {amount}")
        else:
            print(f"\n❌ 连接失败：{data.get('message')}")
            
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")

def list_exchange_keys(token):
    """列出所有交易所"""
    print("\n" + "=" * 60)
    print("📋 当前交易所列表")
    print("=" * 60)
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/exchange-keys",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            keys = response.json()
            
            if not keys:
                print("\n暂无交易所配置")
                return
            
            for key in keys:
                print(f"\n🏦 {key.get('exchange', '').upper()}")
                print(f"   名称：{key.get('name')}")
                print(f"   API Key: {key.get('api_key_prefix')}")
                print(f"   状态：{'✓ 活跃' if key.get('is_active') else '✗ 停用'}")
                print(f"   测试网：{'是' if key.get('is_testnet') else '否'}")
                print(f"   权限：{', '.join(key.get('permissions', []))}")
        else:
            print(f"\n❌ 获取失败：{response.json().get('detail', '未知错误')}")
            
    except Exception as e:
        print(f"\n❌ 请求失败：{e}")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🏦 CryptoQuant - 交易所 API Key 配置工具")
    print("=" * 60)
    
    # 检查后端是否可访问
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code != 200:
            print("❌ 后端服务未响应，请检查是否启动")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 无法连接到后端：{e}")
        print("\n请确保后端已启动:")
        print("   cd ~/.openclaw/workspace/crypto_quant/backend")
        print("   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    print("✅ 后端服务正常")
    
    # 获取认证
    token = get_auth_token()
    
    if not token:
        print("\n⚠️ 未找到认证 Token，需要登录")
        token = login()
        
        if not token:
            print("\n❌ 登录失败，退出")
            sys.exit(1)
    else:
        print("✅ 已找到认证 Token")
        
        # 验证 Token 是否有效
        try:
            response = requests.get(
                f"{API_BASE_URL}/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code != 200:
                print("\n⚠️ Token 已过期，需要重新登录")
                token = login()
                if not token:
                    sys.exit(1)
            else:
                user = response.json()
                print(f"✅ 欢迎，{user.get('username')}")
        except:
            print("\n⚠️ Token 验证失败，需要重新登录")
            token = login()
            if not token:
                sys.exit(1)
    
    # 主菜单
    while True:
        print("\n" + "=" * 60)
        print("请选择操作:")
        print("  1. 添加交易所 API Key")
        print("  2. 查看交易所列表")
        print("  3. 重新登录")
        print("  0. 退出")
        
        choice = input("\n输入选项 (0-3): ").strip()
        
        if choice == '1':
            add_exchange_key(token)
        elif choice == '2':
            list_exchange_keys(token)
        elif choice == '3':
            token = login()
            if not token:
                print("❌ 登录失败")
        elif choice == '0':
            print("\n👋 再见！")
            break
        else:
            print("❌ 无效选项")

if __name__ == '__main__':
    main()
