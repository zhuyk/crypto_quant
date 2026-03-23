/**
 * 交易 API 服务
 */
import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 添加请求 ID
    config.headers['X-Request-ID'] = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    // 记录响应时间
    const duration = response.headers['x-response-time'] || 'unknown'
    console.log(`✅ ${response.config.method.toUpperCase()} ${response.config.url} - ${duration}`)
    return response
  },
  (error) => {
    // 统一错误处理
    if (error.response) {
      const { status, data } = error.response
      console.error(`❌ API 错误 [${status}]:`, data)
      
      // 限流错误
      if (status === 429) {
        const retryAfter = data.retry_after || 1
        console.warn(`⏱️  请求过于频繁，请 ${retryAfter.toFixed(1)} 秒后重试`)
      }
    } else if (error.request) {
      console.error('❌ 网络错误：无法连接到服务器')
    } else {
      console.error('❌ 请求错误:', error.message)
    }
    
    return Promise.reject(error)
  }
)

// ==================== 交易 API ====================

/**
 * 获取交易状态
 */
export async function getTradingStatus() {
  const response = await api.get('/api/v1/trade/status')
  return response.data
}

/**
 * 获取账户余额
 */
export async function getBalance() {
  const response = await api.get('/api/v1/trade/balance')
  return response.data
}

/**
 * 获取所有持仓
 */
export async function getPositions() {
  const response = await api.get('/api/v1/trade/positions')
  return response.data
}

/**
 * 获取指定持仓
 */
export async function getPosition(symbol) {
  const response = await api.get(`/api/v1/trade/position/${symbol}`)
  return response.data
}

/**
 * 创建订单
 */
export async function createOrder(orderData) {
  const response = await api.post('/api/v1/trade/order', orderData)
  return response.data
}

/**
 * 取消订单
 */
export async function cancelOrder(orderId, symbol) {
  const response = await api.post(`/api/v1/trade/order/${orderId}/cancel`, null, {
    params: { symbol }
  })
  return response.data
}

/**
 * 平仓
 */
export async function closePosition(symbol, amount = null) {
  const response = await api.post(`/api/v1/trade/position/${symbol}/close`, {
    amount
  })
  return response.data
}

/**
 * 获取投资组合
 */
export async function getPortfolio() {
  const response = await api.get('/api/v1/trade/portfolio')
  return response.data
}

// ==================== 回测 API ====================

/**
 * 运行回测
 */
export async function runBacktest(backtestData) {
  const response = await api.post('/api/v1/backtest/run', backtestData)
  return response.data
}

/**
 * 获取回测结果
 */
export async function getBacktestResult(backtestId) {
  const response = await api.get(`/api/v1/backtest/result/${backtestId}`)
  return response.data
}

/**
 * 获取可用策略列表
 */
export async function getStrategies() {
  const response = await api.get('/api/v1/backtest/strategies')
  return response.data
}

// ==================== 数据 API ====================

/**
 * 获取交易对列表
 */
export async function getSymbols() {
  const response = await api.get('/api/v1/data/symbols')
  return response.data
}

/**
 * 获取 K 线数据
 */
export async function getKlines(symbol, timeframe, limit = 100) {
  const response = await api.get('/api/v1/data/klines', {
    params: { symbol, timeframe, limit }
  })
  return response.data
}

/**
 * 获取可用时间周期
 */
export async function getTimeframes() {
  const response = await api.get('/api/v1/data/timeframes')
  return response.data
}

// ==================== 策略 API ====================

/**
 * 获取策略列表
 */
export async function getStrategyList() {
  const response = await api.get('/api/v1/strategy/list')
  return response.data
}

/**
 * 获取策略详情
 */
export async function getStrategyDetail(name) {
  const response = await api.get(`/api/v1/strategy/${name}`)
  return response.data
}

/**
 * 验证策略参数
 */
export async function validateStrategy(name, params) {
  const response = await api.post(`/api/v1/strategy/${name}/validate`, params)
  return response.data
}

export default api
