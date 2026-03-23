#!/bin/bash

# ============================================================================
# CryptoQuant 前后端交互测试脚本
# ============================================================================
# 用途：系统测试前端与后端的 API 交互
# 作者：小助 🤖
# 日期：2026-03-17
# ============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# API 基础地址
API_BASE="http://localhost:8000/api/v1"

# 测试结果统计
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# ============================================================================
# 辅助函数
# ============================================================================

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_test() {
    echo -e "${YELLOW}📍 测试：${NC}$1"
}

print_success() {
    echo -e "${GREEN}✅ 通过：${NC}$1"
    ((PASSED_TESTS++))
    ((TOTAL_TESTS++))
}

print_failure() {
    echo -e "${RED}❌ 失败：${NC}$1"
    ((FAILED_TESTS++))
    ((TOTAL_TESTS++))
}

# API 测试函数（带错误处理）
test_api() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    print_test "$description"
    
    local response
    local http_code
    
    if [ "$method" == "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "${API_BASE}${endpoint}" 2>&1)
    elif [ "$method" == "POST" ]; then
        response=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "${API_BASE}${endpoint}" 2>&1)
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        print_success "$description (HTTP $http_code)"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
        return 0
    else
        print_failure "$description (HTTP $http_code)"
        echo "响应内容：$body"
        return 1
    fi
}

# ============================================================================
# 测试用例
# ============================================================================

test_health_check() {
    print_header "1️⃣  健康检查测试"
    
    test_api "GET" "/health" "" "后端健康检查"
    test_api "GET" "/health/detailed" "" "详细健康检查（包含数据库、缓存状态）"
}

test_auth_flow() {
    print_header "2️⃣  认证流程测试"
    
    # 注册测试用户
    local register_data='{
        "username": "test_user_20260317",
        "email": "test@example.com",
        "password": "Test123456!"
    }'
    
    test_api "POST" "/auth/register" "$register_data" "用户注册"
    
    # 登录测试
    local login_data='{
        "username": "test_user_20260317",
        "password": "Test123456!"
    }'
    
    test_api "POST" "/auth/login" "$login_data" "用户登录"
    
    # 注意：实际测试中需要保存 token 用于后续认证测试
}

test_backtest_api() {
    print_header "3️⃣  回测 API 测试"
    
    test_api "GET" "/backtest/strategies" "" "获取策略列表"
    
    # 运行回测测试
    local backtest_data='{
        "strategy_name": "ma_cross",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "params": {
            "fast_period": 20,
            "slow_period": 60,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.15
        },
        "initial_capital": 100000
    }'
    
    test_api "POST" "/backtest/run" "$backtest_data" "运行单策略回测"
    
    # 参数优化测试
    local optimize_data='{
        "strategy_name": "ma_cross",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "param_ranges": {
            "fast_period": [10, 20, 30],
            "slow_period": [50, 60, 70]
        },
        "method": "grid_search",
        "iterations": 5
    }'
    
    test_api "POST" "/backtest/optimize" "$optimize_data" "策略参数优化"
}

test_account_api() {
    print_header "4️⃣  账户 API 测试"
    
    test_api "GET" "/account/balances" "" "获取账户余额"
    test_api "GET" "/account/total?asset=USDT" "" "获取总资产（USDT）"
    test_api "GET" "/account/statistics" "" "获取账户统计信息"
    test_api "GET" "/account/transactions?limit=10" "" "获取交易记录"
}

test_exchange_api() {
    print_header "5️⃣  交易所 API 测试"
    
    test_api "GET" "/exchanges/ticker/BTCUSDT" "" "获取 BTCUSDT 行情"
    test_api "GET" "/exchanges/price/best?symbol=BTCUSDT" "" "获取最优价格"
    test_api "GET" "/exchanges/status" "" "获取交易所状态"
}

test_marketplace_api() {
    print_header "6️⃣  策略市场 API 测试"
    
    test_api "GET" "/marketplace/strategies?limit=10" "" "获取策略市场列表"
}

test_social_api() {
    print_header "7️⃣  社交跟单 API 测试"
    
    test_api "GET" "/social/leaderboard?limit=10" "" "获取跟单排行榜"
    test_api "GET" "/social/portfolios?limit=10" "" "获取投资组合"
}

test_data_api() {
    print_header "8️⃣  数据 API 测试"
    
    test_api "GET" "/data/symbols" "" "获取交易对列表"
    test_api "GET" "/data/kline?symbol=BTCUSDT&timeframe=1h&limit=100" "" "获取 K 线数据"
}

test_trader_api() {
    print_header "9️⃣  交易引擎 API 测试"
    
    test_api "GET" "/trader/status" "" "获取交易引擎状态"
    test_api "GET" "/trader/positions" "" "获取当前仓位"
    test_api "GET" "/trader/orders/active" "" "获取活动订单"
    test_api "GET" "/trader/statistics" "" "获取交易统计"
}

# ============================================================================
# 前端连接测试
# ============================================================================

test_frontend_connection() {
    print_header "🌐 前端连接测试"
    
    print_test "检查前端开发服务器"
    
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        print_success "前端开发服务器运行正常 (port 5173)"
    else
        print_failure "前端开发服务器未响应 (port 5173)"
        echo -e "${YELLOW}💡 提示：可能需要启动前端服务${NC}"
        echo "   cd crypto_quant/frontend"
        echo "   npm run dev"
    fi
    
    print_test "检查前端 API 客户端配置"
    
    if [ -f "crypto_quant/frontend/.env" ]; then
        local api_url=$(grep "VITE_API_BASE_URL" crypto_quant/frontend/.env 2>/dev/null || echo "")
        if [ -n "$api_url" ]; then
            print_success "前端 API 配置存在：$api_url"
        else
            print_failure "前端 API 配置缺失"
        fi
    else
        print_failure "前端 .env 文件不存在"
    fi
}

# ============================================================================
# 主测试流程
# ============================================================================

run_all_tests() {
    print_header "🚀 CryptoQuant 前后端交互测试开始"
    
    echo "测试时间：$(date '+%Y-%m-%d %H:%M:%S')"
    echo "API 地址：$API_BASE"
    echo ""
    
    # 基础测试
    test_health_check
    test_frontend_connection
    
    # 核心功能测试
    test_auth_flow
    test_backtest_api
    test_account_api
    test_exchange_api
    test_data_api
    test_trader_api
    
    # 高级功能测试
    test_marketplace_api
    test_social_api
    
    # 测试结果汇总
    print_header "📊 测试结果汇总"
    
    echo "总测试数：$TOTAL_TESTS"
    echo -e "${GREEN}通过：$PASSED_TESTS${NC}"
    echo -e "${RED}失败：$FAILED_TESTS${NC}"
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}🎉 所有测试通过！${NC}"
        exit 0
    else
        echo -e "\n${YELLOW}⚠️  部分测试失败，请检查日志${NC}"
        exit 1
    fi
}

# ============================================================================
# 入口
# ============================================================================

# 检查是否在正确的目录
if [ ! -d "crypto_quant" ]; then
    echo -e "${RED}错误：请在项目根目录运行此脚本${NC}"
    exit 1
fi

# 运行测试
run_all_tests
