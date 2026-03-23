#!/usr/bin/env python3
"""
CryptoQuant 交易所配置 - 简化版
直接运行，无需复杂检测
"""

import requests
import getpass
import os
from pathlib import Path

API_URL = "http://localhost:8000/api/v1"

print("\n🏦 CryptoQuant 交易所配置\n")

# 测试连接
try:
    r = requests.get(f"{API_URL}/health", timeout=3)
    print("✅ 后端服务正常")
except:
    print("❌ 后端未启动，请先运行：./start.sh")
    exit(1)

# 登录
print("\n🔐 请登录")
username = input("用户名：")
password = getpass.getpass("密码：")

r = requests.post(f"{API_URL}/auth/login", json={
    "username": username,
    "password": password
})

if r.status_code != 200:
    print(f"❌ 登录失败：{r.json().get('detail', '未知错误')}")
    exit(1)

token = r.json().get("access_token")
print(f"\n✅ 登录成功！欢迎 {username}")

# 保存 token
token_file = Path.home() / ".crypto_quant" / "token"
token_file.parent.mkdir(exist_ok=True)
token_file.write_text(token)
os.chmod(token_file, 0o600)

# 添加交易所
print("\n🏦 添加交易所 API Key")
print("1. Binance (币安)")
print("2. OKX")
print("3. Bybit")
print("4. HTX (火币)")
print("5. Gate.io")

choice = input("\n选择交易所 (1-5): ").strip()

exchanges = {
    "1": "binance",
    "2": "okx",
    "3": "bybit",
    "4": "htx",
    "5": "gate",
}

if choice not in exchanges:
    print("❌ 无效选择")
    exit(1)

exchange = exchanges[choice]
name = input("名称（默认：主账户）: ").strip() or "主账户"
api_key = getpass.getpass("API Key: ").strip()
api_secret = getpass.getpass("API Secret: ").strip()

# OKX/Bybit 需要 Passphrase
passphrase = ""
if exchange in ["okx", "bybit"]:
    passphrase = getpass.getpass("API Passphrase: ").strip()

testnet = input("使用测试网？(y/n, 默认 n): ").strip().lower() == "y"

# 提交
payload = {
    "exchange": exchange,
    "name": name,
    "api_key": api_key,
    "api_secret": api_secret,
    "permissions": ["trade", "read"],
    "is_testnet": testnet,
}

if passphrase:
    payload["passphrase"] = passphrase

print("\n📡 提交中...")

r = requests.post(
    f"{API_URL}/exchange-keys",
    headers={"Authorization": f"Bearer {token}"},
    json=payload
)

if r.status_code in [200, 201]:
    data = r.json()
    print("\n✅ 添加成功！")
    print(f"   交易所：{data.get('exchange', '').upper()}")
    print(f"   名称：{data.get('name')}")
    print(f"   API Key: {data.get('api_key_prefix')}")
    print(f"   测试网：{'是' if data.get('is_testnet') else '否'}")
    
    # 测试连接
    test = input("\n🔌 测试连接？(y/n): ").strip().lower()
    if test == "y":
        print("测试中...")
        r = requests.post(
            f"{API_URL}/exchange-keys/{data['id']}/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        result = r.json()
        if result.get("success"):
            print(f"✅ 连接成功：{result.get('message')}")
            if result.get("balance"):
                print("余额:")
                for curr, amt in result.get("balance", {}).items():
                    if amt > 0:
                        print(f"  {curr}: {amt}")
        else:
            print(f"❌ 连接失败：{result.get('message')}")
    
    print("\n💡 访问 http://localhost:3000/exchange-keys 管理所有交易所")
else:
    print(f"\n❌ 添加失败：{r.json().get('detail', '未知错误')}")
