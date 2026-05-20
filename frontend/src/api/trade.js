/**
 * 交易 API 服务
 * 
 * 使用统一的 apiClient 实例（从环境变量读取 base URL）
 */
import apiClient from './client'

// ==================== 交易 API ====================

/**
 * 获取交易状态
 */
export async function getTradingStatus() {
  return apiClient.get('/trade/status')
}

/**
 * 获取账户余额
 */
export async function getBalance() {
  return apiClient.get('/trade/balance')
}

/**
 * 获取所有持仓
 */
export async function getPositions() {
  return apiClient.get('/trade/positions')
}

/**
 * 获取指定持仓
 */
export async function getPosition(symbol) {
  return apiClient.get(`/trade/position/${symbol}`)
}

/**
 * 创建订单
 */
export async function createOrder(orderData) {
  return apiClient.post('/trade/order', orderData)
}

/**
 * 取消订单
 */
export async function cancelOrder(orderId, symbol) {
  return apiClient.post(`/trade/order/${orderId}/cancel`, null, {
    params: { symbol }
  })
}

/**
 * 平仓
 */
export async function closePosition(symbol, amount = null) {
  return apiClient.post(`/trade/position/${symbol}/close`, { amount })
}

/**
 * 获取投资组合
 */
export async function getPortfolio() {
  return apiClient.get('/trade/portfolio')
}

/**
 * 获取风险指标
 */
export async function getRiskMetrics() {
  return apiClient.get('/trade/risk-metrics')
}

/**
 * 获取交易历史
 */
export async function getTradeHistory(limit = 50) {
  return apiClient.get('/trade/history', { params: { limit } })
}

// ==================== 回测 API ====================

/**
 * 运行回测
 */
export async function runBacktest(backtestData) {
  return apiClient.post('/backtest/run', backtestData)
}

/**
 * 获取回测结果
 */
export async function getBacktestResult(backtestId) {
  return apiClient.get(`/backtest/result/${backtestId}`)
}

/**
 * 获取可用策略列表
 */
export async function getStrategies() {
  return apiClient.get('/backtest/strategies')
}

// ==================== 数据 API ====================

/**
 * 获取交易对列表
 */
export async function getSymbols() {
  return apiClient.get('/data/symbols')
}

/**
 * 获取 K 线数据
 */
export async function getKlines(symbol, timeframe, limit = 100) {
  return apiClient.get('/data/klines', {
    params: { symbol, timeframe, limit }
  })
}

/**
 * 获取可用时间周期
 */
export async function getTimeframes() {
  return apiClient.get('/data/timeframes')
}

// ==================== 策略 API ====================

/**
 * 获取策略列表
 */
export async function getStrategyList() {
  return apiClient.get('/strategy/list')
}

/**
 * 获取策略详情
 */
export async function getStrategyDetail(name) {
  return apiClient.get(`/strategy/${name}`)
}

/**
 * 验证策略参数
 */
export async function validateStrategy(name, params) {
  return apiClient.post(`/strategy/${name}/validate`, params)
}
