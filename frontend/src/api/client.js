/**
 * API 客户端 - 统一 API 调用
 * 
 * 特性:
 * - 路由切换时自动取消上一页面的未完成请求 (防止 pending 堆积)
 * - 请求超时 10s (避免永久 pending)
 * - 认证 token 自动注入
 * - 统一错误处理
 */

import axios from 'axios'

// ============================================================
// 请求取消管理器
// 路由切换时调用 cancelPendingRequests() 清理所有未完成请求
// ============================================================

const pendingRequests = new Map()

function getRequestKey(config) {
  return `${config.method}:${config.url}`
}

function addPendingRequest(config) {
  const key = getRequestKey(config)
  if (!config.signal) {
    const controller = new AbortController()
    config.signal = controller.signal
    pendingRequests.set(key, controller)
  }
}

function removePendingRequest(config) {
  const key = getRequestKey(config)
  pendingRequests.delete(key)
}

/**
 * 取消所有未完成的请求
 * 在路由切换时调用此函数
 */
export function cancelPendingRequests() {
  for (const [key, controller] of pendingRequests) {
    controller.abort()
  }
  pendingRequests.clear()
}


// ============================================================
// 创建 axios 实例
// ============================================================

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,  // 10 秒超时 (原来 30s 太长)
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 取消同一接口的上一次未完成请求 (去重)
    const key = getRequestKey(config)
    if (pendingRequests.has(key)) {
      pendingRequests.get(key).abort()
      pendingRequests.delete(key)
    }

    // 注册新的取消控制器
    addPendingRequest(config)

    // 添加认证
    const token = localStorage.getItem('session_id')
    const apiKey = localStorage.getItem('api_key')
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    } else if (apiKey) {
      config.headers['X-API-Key'] = apiKey
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    // 请求完成，从 pending 列表移除
    removePendingRequest(response.config)
    return response.data
  },
  (error) => {
    // 请求失败也要移除
    if (error.config) {
      removePendingRequest(error.config)
    }

    // 被取消的请求静默处理 (不弹错误)
    if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
      return Promise.reject({ __canceled: true })
    }

    if (error.response) {
      // 401 - 未授权
      if (error.response.status === 401) {
        localStorage.removeItem('session_id')
        window.location.href = '/login'
      }
      
      // 403 - 权限不足
      if (error.response.status === 403) {
        console.error('权限不足')
      }
      
      // 500 - 服务器错误
      if (error.response.status === 500) {
        console.error('服务器错误')
      }
    } else if (error.code === 'ECONNABORTED') {
      console.warn('⏱️ 请求超时')
    }
    
    return Promise.reject(error)
  }
)

// ============================================================
// API 方法封装
// ============================================================

export const api = {
  // 认证
  auth: {
    login: (data) => apiClient.post('/auth/login', data),
    logout: () => apiClient.post('/auth/logout'),
    register: (data) => apiClient.post('/auth/register', data),
    me: () => apiClient.get('/auth/me'),
    changePassword: (data) => apiClient.post('/auth/password/change', data),
    apiKeys: () => apiClient.get('/auth/api-keys'),
  },
  
  // 交易
  trader: {
    execute: (data) => apiClient.post('/trade/execute', data),
    status: () => apiClient.get('/trade/status'),
    positions: () => apiClient.get('/trade/positions'),
    orders: (params) => apiClient.get('/trade/orders/active', { params }),
    cancelOrder: (id) => apiClient.post(`/trade/orders/${id}/cancel`),
    statistics: () => apiClient.get('/trade/statistics'),
  },
  
  // 交易所
  exchanges: {
    ticker: (symbol) => apiClient.get(`/exchanges/ticker/${symbol}`),
    bestPrice: (params) => apiClient.get('/exchanges/price/best', { params }),
    balance: (params) => apiClient.get('/exchanges/balance', { params }),
    status: () => apiClient.get('/exchanges/status'),
  },
  
  // 交易所 API Key 管理
  exchangeKeys: {
    list: (exchange) => apiClient.get('/exchange-keys', { params: { exchange } }),
    create: (data) => apiClient.post('/exchange-keys', data),
    update: (id, data) => apiClient.put(`/exchange-keys/${id}`, data),
    delete: (id) => apiClient.delete(`/exchange-keys/${id}`),
    test: (id) => apiClient.post(`/exchange-keys/${id}/test`),
    stats: () => apiClient.get('/exchange-keys/stats/summary'),
  },
  
  // 回测
  backtest: {
    run: (data) => apiClient.post('/backtest/run', data),
    status: (taskId) => apiClient.get(`/backtest/status/${taskId}`),
    result: (taskId) => apiClient.get(`/backtest/result/${taskId}`),
    strategies: () => apiClient.get('/backtest/strategies'),
    optimize: (data) => apiClient.post('/backtest/optimize', data),
  },
  
  // 账户
  account: {
    balances: () => apiClient.get('/account/balances'),
    total: (asset) => apiClient.get('/account/total', { params: { asset } }),
    transactions: (params) => apiClient.get('/account/transactions', { params }),
    statistics: () => apiClient.get('/account/statistics'),
  },
  
  // 策略市场
  marketplace: {
    strategies: (params) => apiClient.get('/marketplace/strategies', { params }),
    detail: (id) => apiClient.get(`/marketplace/strategies/${id}`),
    subscribe: (id) => apiClient.post(`/marketplace/strategies/${id}/subscribe`),
    mySubscriptions: () => apiClient.get('/marketplace/my-subscriptions'),
  },
  
  // 社交跟单
  social: {
    leaderboard: (params) => apiClient.get('/social/leaderboard', { params }),
    follow: (data) => apiClient.post('/social/follow', data),
    unfollow: (id) => apiClient.post(`/social/unfollow/${id}`),
    myFollowings: () => apiClient.get('/social/my-followings'),
    portfolios: (params) => apiClient.get('/social/portfolios', { params }),
  },
  
  // 健康检查
  health: {
    status: () => apiClient.get('/health'),
    detailed: () => apiClient.get('/health/detailed'),
  },
  
  // 套利策略
  arbitrage: {
    startFundingRateArbitrage: (config) => apiClient.post('/arbitrage/funding_rate/start', config),
    stopFundingRateArbitrage: (strategyId) => apiClient.post('/arbitrage/funding_rate/stop', { strategy_id: strategyId }),
    getFundingRateSignals: (minRate) => apiClient.get('/arbitrage/funding_rate/signals', { params: { min_rate: minRate } }),
    getFundingRatePositions: () => apiClient.get('/arbitrage/funding_rate/positions'),
    closePosition: (symbol) => apiClient.post(`/arbitrage/funding_rate/close/${symbol}`),
    getStrategyStatus: () => apiClient.get('/arbitrage/funding_rate/status'),
    getFundingRates: (exchange) => apiClient.get('/arbitrage/funding_rate/rates', { params: { exchange } }),
  },
}

export default apiClient
