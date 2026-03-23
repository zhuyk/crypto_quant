/**
 * 交易状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getTradingStatus,
  getBalance,
  getPositions,
  getPortfolio,
  createOrder,
  closePosition,
  cancelOrder,
} from '../api/trade'

export const useTradingStore = defineStore('trading', () => {
  // ==================== State ====================
  
  const connected = ref(false)
  const loading = ref(false)
  const error = ref(null)
  
  // 账户信息
  const balance = ref({
    available: 0,
    total: 0,
    locked: 0,
  })
  
  // 持仓
  const positions = ref([])
  
  // 投资组合
  const portfolio = ref({
    capital: 0,
    initial_capital: 0,
    total_pnl: 0,
    total_pnl_pct: 0,
    daily_pnl: 0,
    daily_pnl_pct: 0,
    current_drawdown: 0,
    risk_level: 'low',
  })
  
  // 订单历史
  const orders = ref([])
  
  // ==================== Getters ====================
  
  const totalExposure = computed(() => {
    return positions.value.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0)
  })
  
  const totalPnl = computed(() => {
    return portfolio.value.total_pnl || 0
  })
  
  const totalPnlPercent = computed(() => {
    return ((portfolio.value.total_pnl_pct || 0) * 100).toFixed(2)
  })
  
  const riskLevelColor = computed(() => {
    const colors = {
      low: 'success',
      medium: 'warning',
      high: 'danger',
      extreme: 'danger',
    }
    return colors[portfolio.value.risk_level] || 'info'
  })
  
  // ==================== Actions ====================
  
  /**
   * 连接交易所
   */
  async function connect() {
    loading.value = true
    error.value = null
    
    try {
      const status = await getTradingStatus()
      connected.value = status.connected || false
      
      if (connected.value) {
        await refreshAll()
      }
    } catch (err) {
      error.value = '连接失败：' + (err.response?.data?.message || err.message)
      connected.value = false
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 断开连接
   */
  function disconnect() {
    connected.value = false
    positions.value = []
    orders.value = []
  }
  
  /**
   * 刷新所有数据
   */
  async function refreshAll() {
    if (!connected.value) return
    
    await Promise.allSettled([
      refreshBalance(),
      refreshPositions(),
      refreshPortfolio(),
    ])
  }
  
  /**
   * 刷新余额
   */
  async function refreshBalance() {
    try {
      const data = await getBalance()
      balance.value = data.balance || data
    } catch (err) {
      console.error('获取余额失败:', err)
    }
  }
  
  /**
   * 刷新持仓
   */
  async function refreshPositions() {
    try {
      const data = await getPositions()
      positions.value = data.positions || []
    } catch (err) {
      console.error('获取持仓失败:', err)
    }
  }
  
  /**
   * 刷新投资组合
   */
  async function refreshPortfolio() {
    try {
      const data = await getPortfolio()
      portfolio.value = data
    } catch (err) {
      console.error('获取投资组合失败:', err)
    }
  }
  
  /**
   * 创建订单
   */
  async function placeOrder(orderData) {
    loading.value = true
    error.value = null
    
    try {
      const result = await createOrder(orderData)
      
      // 刷新数据
      await refreshPositions()
      await refreshPortfolio()
      
      // 添加订单到历史
      orders.value.unshift({
        ...result,
        created_at: new Date().toISOString(),
      })
      
      return { success: true, data: result }
    } catch (err) {
      error.value = err.response?.data?.message || '下单失败'
      return {
        success: false,
        error: error.value,
      }
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 平仓
   */
  async function close(symbol, amount = null) {
    loading.value = true
    error.value = null
    
    try {
      const result = await closePosition(symbol, amount)
      
      // 从持仓列表移除
      positions.value = positions.value.filter(p => p.symbol !== symbol)
      
      await refreshPortfolio()
      
      return { success: true, data: result }
    } catch (err) {
      error.value = err.response?.data?.message || '平仓失败'
      return {
        success: false,
        error: error.value,
      }
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 取消订单
   */
  async function cancel(orderId, symbol) {
    try {
      const result = await cancelOrder(orderId, symbol)
      
      // 更新订单状态
      const order = orders.value.find(o => o.id === orderId)
      if (order) {
        order.status = 'cancelled'
      }
      
      return { success: true, data: result }
    } catch (err) {
      error.value = err.response?.data?.message || '取消订单失败'
      return {
        success: false,
        error: error.value,
      }
    }
  }
  
  /**
   * 清空错误
   */
  function clearError() {
    error.value = null
  }
  
  return {
    // State
    connected,
    loading,
    error,
    balance,
    positions,
    portfolio,
    orders,
    
    // Getters
    totalExposure,
    totalPnl,
    totalPnlPercent,
    riskLevelColor,
    
    // Actions
    connect,
    disconnect,
    refreshAll,
    refreshBalance,
    refreshPositions,
    refreshPortfolio,
    placeOrder,
    close,
    cancel,
    clearError,
  }
})
