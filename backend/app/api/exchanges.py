"""
交易所 API 路由 - 多交易所行情与连接管理

功能:
- 多交易所支持 (Binance, OKX, Bybit, Gate, Kucoin, HTX)
- 真实 API 连接测试
- 实时行情 (ticker/orderbook)
- 智能 symbol 解析 (支持 4+ 字符币种)
- 交易所状态监控
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import ccxt
import logging
import time as _time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["交易所"])


# ============================================================
# 多交易所管理
# ============================================================

# 支持的交易所及其默认配置
SUPPORTED_EXCHANGES = {
    "binance": {"name": "币安", "class": "binance", "has_testnet": True},
    "okx": {"name": "OKX", "class": "okx", "has_testnet": True},
    "bybit": {"name": "Bybit", "class": "bybit", "has_testnet": True},
    "gate": {"name": "Gate.io", "class": "gate", "has_testnet": False},
    "kucoin": {"name": "Kucoin", "class": "kucoin", "has_testnet": True},
    "htx": {"name": "HTX (火币)", "class": "htx", "has_testnet": False},
}

# 交易所实例缓存 (只读公共行情, 无需 API Key)
_exchange_instances: Dict[str, ccxt.Exchange] = {}


def get_exchange(exchange_id: str = "binance") -> ccxt.Exchange:
    """
    获取交易所实例（公共行情用，无需认证）
    
    使用连接池复用实例
    """
    if exchange_id not in SUPPORTED_EXCHANGES:
        raise ValueError(f"不支持的交易所: {exchange_id}。支持: {list(SUPPORTED_EXCHANGES.keys())}")
    
    if exchange_id not in _exchange_instances:
        exchange_class = getattr(ccxt, SUPPORTED_EXCHANGES[exchange_id]["class"])
        _exchange_instances[exchange_id] = exchange_class({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            },
        })
        logger.info(f"初始化交易所实例: {exchange_id}")
    
    return _exchange_instances[exchange_id]


def create_authenticated_exchange(
    exchange_id: str,
    api_key: str,
    api_secret: str,
    passphrase: Optional[str] = None,
    testnet: bool = False,
) -> ccxt.Exchange:
    """
    创建认证的交易所实例（用于连接测试和交易）
    """
    if exchange_id not in SUPPORTED_EXCHANGES:
        raise ValueError(f"不支持的交易所: {exchange_id}")
    
    exchange_class = getattr(ccxt, SUPPORTED_EXCHANGES[exchange_id]["class"])
    
    config = {
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
        },
    }
    
    if passphrase:
        config['password'] = passphrase
    
    exchange = exchange_class(config)
    
    if testnet and SUPPORTED_EXCHANGES[exchange_id].get("has_testnet"):
        exchange.set_sandbox_mode(True)
    
    return exchange


# ============================================================
# Symbol 解析工具
# ============================================================

# 常见计价货币（按长度倒序，优先匹配长的）
QUOTE_CURRENCIES = ["USDT", "USDC", "BUSD", "TUSD", "USD", "BTC", "ETH", "BNB"]


def normalize_symbol(symbol: str) -> str:
    """
    智能 symbol 标准化为 ccxt 格式 (BASE/QUOTE)
    
    支持:
    - BTCUSDT → BTC/USDT
    - DOGEUSDT → DOGE/USDT
    - SHIBUSDT → SHIB/USDT
    - BTC/USDT → BTC/USDT (已是正确格式)
    - MATICBTC → MATIC/BTC
    """
    symbol = symbol.strip().upper()
    
    # 已经是 ccxt 格式
    if '/' in symbol:
        return symbol
    
    # 尝试匹配计价货币
    for quote in QUOTE_CURRENCIES:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            base = symbol[:-len(quote)]
            return f"{base}/{quote}"
    
    # 无法识别，返回原样
    return symbol


def display_symbol(ccxt_symbol: str) -> str:
    """ccxt 格式转显示格式 (BTC/USDT → BTCUSDT)"""
    return ccxt_symbol.replace("/", "")


# ============================================================
# Request/Response 模型
# ============================================================

class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    exchange: str = Field("binance", description="交易所 ID")
    api_key: str = Field(..., description="API Key")
    api_secret: str = Field(..., description="API Secret")
    passphrase: Optional[str] = Field(None, description="密码短语 (OKX/Bybit/Kucoin 需要)")
    testnet: bool = Field(True, description="是否使用测试网")


class TestConnectionResponse(BaseModel):
    """测试连接响应"""
    success: bool
    exchange: str
    exchange_name: str
    testnet: bool
    message: str
    balance: Optional[Dict[str, float]] = None
    permissions: Optional[List[str]] = None
    latency_ms: Optional[float] = None


# ============================================================
# API 端点 - 连接管理
# ============================================================

@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_exchange_connection(request: TestConnectionRequest):
    """
    测试交易所 API 连接
    
    真实调用交易所 API 验证:
    1. API Key/Secret 有效性
    2. 权限检查（读取余额）
    3. 网络连通性
    4. 响应延迟
    """
    if request.exchange not in SUPPORTED_EXCHANGES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的交易所: {request.exchange}。支持: {list(SUPPORTED_EXCHANGES.keys())}",
        )
    
    exchange_info = SUPPORTED_EXCHANGES[request.exchange]
    
    # 某些交易所需要 passphrase
    requires_passphrase = request.exchange in ["okx", "bybit", "kucoin"]
    if requires_passphrase and not request.passphrase:
        raise HTTPException(
            status_code=400,
            detail=f"{exchange_info['name']} 需要提供 passphrase",
        )
    
    start_time = _time.time()
    
    try:
        # 创建认证实例
        exchange = create_authenticated_exchange(
            exchange_id=request.exchange,
            api_key=request.api_key,
            api_secret=request.api_secret,
            passphrase=request.passphrase,
            testnet=request.testnet,
        )
        
        # 真实调用 - 获取余额
        balance = exchange.fetch_balance()
        
        latency_ms = (_time.time() - start_time) * 1000
        
        # 提取非零余额
        non_zero_balance = {}
        for currency, amount in balance.get('total', {}).items():
            if amount and float(amount) > 0:
                non_zero_balance[currency] = float(amount)
        
        # 检测权限
        permissions = ["read"]
        try:
            # 尝试获取订单（不真正下单，只读操作）
            exchange.fetch_open_orders(symbol=None, limit=1)
            permissions.append("trade")
        except ccxt.AuthenticationError:
            pass
        except Exception:
            permissions.append("trade")  # 如果不是认证错误，可能有权限
        
        logger.info(
            f"✅ 交易所连接成功: {request.exchange} "
            f"({'测试网' if request.testnet else '主网'}) "
            f"延迟={latency_ms:.0f}ms"
        )
        
        # 保存连接状态
        from app.core.trading_state import set_connected
        set_connected(request.exchange, request.testnet)
        
        return TestConnectionResponse(
            success=True,
            exchange=request.exchange,
            exchange_name=exchange_info["name"],
            testnet=request.testnet,
            message=f"连接成功 - {exchange_info['name']} ({'测试网' if request.testnet else '主网'})",
            balance=non_zero_balance if non_zero_balance else {"USDT": 0},
            permissions=permissions,
            latency_ms=round(latency_ms, 2),
        )
        
    except ccxt.AuthenticationError as e:
        latency_ms = (_time.time() - start_time) * 1000
        logger.warning(f"❌ 认证失败: {request.exchange} - {e}")
        return TestConnectionResponse(
            success=False,
            exchange=request.exchange,
            exchange_name=exchange_info["name"],
            testnet=request.testnet,
            message=f"认证失败: API Key 或 Secret 无效",
            latency_ms=round(latency_ms, 2),
        )
    
    except ccxt.NetworkError as e:
        latency_ms = (_time.time() - start_time) * 1000
        logger.warning(f"❌ 网络错误: {request.exchange} - {e}")
        return TestConnectionResponse(
            success=False,
            exchange=request.exchange,
            exchange_name=exchange_info["name"],
            testnet=request.testnet,
            message=f"网络错误: 无法连接到 {exchange_info['name']}",
            latency_ms=round(latency_ms, 2),
        )
    
    except ccxt.ExchangeError as e:
        latency_ms = (_time.time() - start_time) * 1000
        logger.warning(f"❌ 交易所错误: {request.exchange} - {e}")
        return TestConnectionResponse(
            success=False,
            exchange=request.exchange,
            exchange_name=exchange_info["name"],
            testnet=request.testnet,
            message=f"交易所返回错误: {str(e)[:100]}",
            latency_ms=round(latency_ms, 2),
        )
    
    except Exception as e:
        latency_ms = (_time.time() - start_time) * 1000
        logger.error(f"❌ 连接测试异常: {request.exchange} - {e}")
        return TestConnectionResponse(
            success=False,
            exchange=request.exchange,
            exchange_name=exchange_info["name"],
            testnet=request.testnet,
            message=f"连接失败: {str(e)[:100]}",
            latency_ms=round(latency_ms, 2),
        )


@router.get("/supported")
async def list_supported_exchanges():
    """列出所有支持的交易所"""
    return {
        "exchanges": [
            {
                "id": ex_id,
                "name": ex_info["name"],
                "has_testnet": ex_info.get("has_testnet", False),
                "requires_passphrase": ex_id in ["okx", "bybit", "kucoin"],
            }
            for ex_id, ex_info in SUPPORTED_EXCHANGES.items()
        ],
        "total": len(SUPPORTED_EXCHANGES),
    }


# ============================================================
# API 端点 - 行情数据
# ============================================================

@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    exchange_id: str = Query("binance", description="交易所"),
):
    """
    获取单个交易对行情
    
    Args:
        symbol: 交易对（如 BTCUSDT, DOGEUSDT, ETH/USDT）
        exchange_id: 交易所 ID
    """
    try:
        exchange = get_exchange(exchange_id)
        ccxt_symbol = normalize_symbol(symbol)
        
        ticker = exchange.fetch_ticker(ccxt_symbol)
        
        return {
            "symbol": display_symbol(ccxt_symbol),
            "exchange": exchange_id,
            "last": ticker['last'],
            "bid": ticker['bid'],
            "ask": ticker['ask'],
            "high": ticker['high'],
            "low": ticker['low'],
            "volume": ticker['quoteVolume'],
            "change": ticker['percentage'] / 100 if ticker['percentage'] else 0,
            "timestamp": ticker['timestamp'],
        }
        
    except ccxt.BadSymbol as e:
        raise HTTPException(status_code=400, detail=f"无效交易对: {symbol} ({e})")
    except ccxt.NetworkError as e:
        raise HTTPException(status_code=503, detail=f"网络错误: {str(e)[:100]}")
    except Exception as e:
        logger.error(f"获取行情失败 {symbol}@{exchange_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取行情失败: {str(e)[:100]}")


@router.get("/tickers")
async def get_tickers(
    symbols: Optional[str] = Query(None, description="交易对列表，逗号分隔"),
    exchange_id: str = Query("binance", description="交易所"),
):
    """
    获取多个交易对行情
    
    Args:
        symbols: 交易对列表，逗号分隔（如 BTCUSDT,ETHUSDT,DOGEUSDT）
        exchange_id: 交易所 ID
    """
    if not symbols:
        symbols = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT"
    
    symbol_list = [s.strip() for s in symbols.split(',')]
    
    try:
        exchange = get_exchange(exchange_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    results = []
    errors = []
    
    for symbol in symbol_list:
        try:
            ccxt_symbol = normalize_symbol(symbol)
            ticker = exchange.fetch_ticker(ccxt_symbol)
            
            results.append({
                "symbol": display_symbol(ccxt_symbol),
                "exchange": exchange_id,
                "last": ticker['last'],
                "bid": ticker['bid'],
                "ask": ticker['ask'],
                "high": ticker['high'],
                "low": ticker['low'],
                "volume": ticker['quoteVolume'],
                "change": ticker['percentage'] / 100 if ticker['percentage'] else 0,
                "timestamp": ticker['timestamp'],
            })
            
        except Exception as e:
            errors.append({"symbol": symbol, "error": str(e)[:80]})
            logger.warning(f"获取行情失败 {symbol}@{exchange_id}: {e}")
    
    response = {"tickers": results, "count": len(results)}
    if errors:
        response["errors"] = errors
    
    return response


@router.get("/orderbook/{symbol}")
async def get_orderbook(
    symbol: str,
    exchange_id: str = Query("binance", description="交易所"),
    limit: int = Query(20, ge=5, le=100, description="深度"),
):
    """
    获取订单簿
    
    Args:
        symbol: 交易对
        exchange_id: 交易所
        limit: 深度层数
    """
    try:
        exchange = get_exchange(exchange_id)
        ccxt_symbol = normalize_symbol(symbol)
        
        orderbook = exchange.fetch_order_book(ccxt_symbol, limit=limit)
        
        return {
            "symbol": display_symbol(ccxt_symbol),
            "exchange": exchange_id,
            "bids": orderbook['bids'][:limit],
            "asks": orderbook['asks'][:limit],
            "timestamp": orderbook.get('timestamp'),
            "bid_total_volume": sum(b[1] for b in orderbook['bids'][:limit]),
            "ask_total_volume": sum(a[1] for a in orderbook['asks'][:limit]),
        }
        
    except ccxt.BadSymbol as e:
        raise HTTPException(status_code=400, detail=f"无效交易对: {symbol}")
    except Exception as e:
        logger.error(f"获取订单簿失败 {symbol}@{exchange_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取订单簿失败: {str(e)[:100]}")


@router.get("/price/best")
async def get_best_price(
    symbol: str,
    side: str = Query(..., description="buy/sell"),
    quantity: float = Query(0, description="数量（用于计算滑点）"),
    exchange_id: str = Query("binance", description="交易所"),
):
    """
    获取最优价格（含滑点估算）
    
    对于大额交易，考虑订单簿深度计算实际成交均价
    """
    try:
        exchange = get_exchange(exchange_id)
        ccxt_symbol = normalize_symbol(symbol)
        
        orderbook = exchange.fetch_order_book(ccxt_symbol, limit=50)
        
        if side.lower() == 'buy':
            orders = orderbook['asks']
        else:
            orders = orderbook['bids']
        
        if not orders:
            raise HTTPException(status_code=404, detail="订单簿为空")
        
        best_price = orders[0][0]
        
        # 如果指定了数量，计算加权平均成交价
        avg_price = best_price
        if quantity > 0:
            filled = 0.0
            cost = 0.0
            for price, vol in orders:
                fill_amount = min(vol, quantity - filled)
                cost += fill_amount * price
                filled += fill_amount
                if filled >= quantity:
                    break
            
            if filled > 0:
                avg_price = cost / filled
        
        slippage = abs(avg_price - best_price) / best_price if best_price else 0
        
        return {
            "symbol": display_symbol(ccxt_symbol),
            "exchange": exchange_id,
            "side": side,
            "best_price": best_price,
            "avg_price": avg_price if quantity > 0 else None,
            "quantity": quantity,
            "estimated_slippage": round(slippage * 100, 4),  # 百分比
            "orderbook_depth": len(orders),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取最优价格失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API 端点 - 交易所状态
# ============================================================

@router.get("/status")
async def get_exchange_status(
    exchange_id: str = Query("binance", description="交易所"),
):
    """获取交易所状态"""
    try:
        exchange = get_exchange(exchange_id)
        
        start_time = _time.time()
        markets = exchange.load_markets()
        latency_ms = (_time.time() - start_time) * 1000
        
        # 统计交易对数量
        spot_count = sum(1 for m in markets.values() if m.get('spot'))
        futures_count = sum(1 for m in markets.values() if m.get('future') or m.get('swap'))
        
        return {
            "exchange": exchange_id,
            "exchange_name": SUPPORTED_EXCHANGES[exchange_id]["name"],
            "status": "online",
            "markets_count": len(markets),
            "spot_markets": spot_count,
            "futures_markets": futures_count,
            "latency_ms": round(latency_ms, 2),
            "timestamp": exchange.milliseconds(),
        }
        
    except Exception as e:
        logger.error(f"检查交易所状态失败 {exchange_id}: {e}")
        return {
            "exchange": exchange_id,
            "exchange_name": SUPPORTED_EXCHANGES.get(exchange_id, {}).get("name", exchange_id),
            "status": "offline",
            "error": str(e)[:100],
        }


@router.get("/status/all")
async def get_all_exchanges_status():
    """获取所有交易所状态"""
    statuses = []
    
    for exchange_id in SUPPORTED_EXCHANGES:
        try:
            exchange = get_exchange(exchange_id)
            start_time = _time.time()
            exchange.load_markets()
            latency_ms = (_time.time() - start_time) * 1000
            
            statuses.append({
                "exchange": exchange_id,
                "name": SUPPORTED_EXCHANGES[exchange_id]["name"],
                "status": "online",
                "latency_ms": round(latency_ms, 2),
            })
        except Exception as e:
            statuses.append({
                "exchange": exchange_id,
                "name": SUPPORTED_EXCHANGES[exchange_id]["name"],
                "status": "offline",
                "error": str(e)[:50],
            })
    
    online_count = sum(1 for s in statuses if s["status"] == "online")
    
    return {
        "statuses": statuses,
        "online": online_count,
        "total": len(statuses),
    }
