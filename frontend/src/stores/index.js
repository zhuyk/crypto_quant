/**
 * Pinia Store - 应用状态管理
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

export const useTradingStore = defineStore('trading', {
  state: () => ({
    positions: [],
    recentTrades: [],
    tickers: {},
  }),
  
  getters: {
    totalPositionValue: (state) => {
      return state.positions.reduce((sum, pos) => {
        return sum + (parseFloat(pos.size) * parseFloat(pos.currentPrice))
      }, 0)
    },
    
    totalUnrealizedPnl: (state) => {
      return state.positions.reduce((sum, pos) => {
        return sum + (parseFloat(pos.pnl) || 0)
      }, 0)
    },
  },
  
  actions: {
    async fetchPositions() {
      try {
        const data = await api.trader.positions()
        this.positions = data.positions || []
      } catch (error) {
        console.error('加载持仓失败:', error)
      }
    },
    
    async fetchRecentTrades(limit = 20) {
      try {
        const data = await api.trader.statistics()
        this.recentTrades = data.recent_trades || []
      } catch (error) {
        console.error('加载交易记录失败:', error)
      }
    },
    
    updateTicker(symbol, ticker) {
      this.tickers[symbol] = ticker
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
