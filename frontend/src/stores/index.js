/**
 * Pinia Store - 应用状态管理
 * 
 * 注意: Trading store 在 stores/trading.js 中独立定义，
 * 避免命名冲突。
 */

import { defineStore } from 'pinia'
import { api } from '@/api/client.js'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null,
    session_id: localStorage.getItem('session_id'),
    api_key: localStorage.getItem('api_key'),
  }),
  
  getters: {
    isAuthenticated: (state) => !!state.session_id || !!state.api_key,
    username: (state) => state.user?.username || 'User',
    email: (state) => state.user?.email || '',
  },
  
  actions: {
    async fetchUser() {
      try {
        this.user = await api.auth.me()
      } catch (error) {
        this.user = null
      }
    },
    
    setSession(sessionId) {
      this.session_id = sessionId
      localStorage.setItem('session_id', sessionId)
    },
    
    setApiKey(apiKey) {
      this.api_key = apiKey
      localStorage.setItem('api_key', apiKey)
    },
    
    logout() {
      this.user = null
      this.session_id = null
      this.api_key = null
      localStorage.removeItem('session_id')
      localStorage.removeItem('api_key')
    },
  },
})

export const useAccountStore = defineStore('account', {
  state: () => ({
    balances: {},
    totalBalance: 0,
    statistics: null,
  }),
  
  getters: {
    availableBalance: (state) => {
      return state.balances['USDT']?.free || 0
    },
  },
  
  actions: {
    async fetchBalances() {
      try {
        const data = await api.account.balances()
        this.balances = data.balances || {}
      } catch (error) {
        console.error('加载余额失败:', error)
      }
    },
    
    async fetchStatistics() {
      try {
        this.statistics = await api.account.statistics()
      } catch (error) {
        console.error('加载统计失败:', error)
      }
    },
  },
})

// 从 stores/trading.js 重新导出（确保导入路径统一）
export { useTradingStore } from './trading'
