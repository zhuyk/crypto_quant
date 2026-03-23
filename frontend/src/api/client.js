/**
 * API 客户端 - 统一 API 调用
 */

import axios from 'axios'

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器 - 添加认证
apiClient.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 token
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

// 响应拦截器 - 处理错误
apiClient.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
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
    }
    
    return Promise.reject(error)
  }
)

// API 方法封装
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
}

export default apiClient
