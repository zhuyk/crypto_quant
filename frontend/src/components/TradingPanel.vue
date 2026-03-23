<!--
交易面板组件 - 实时行情和下单
-->

<template>
  <div class="trading-panel">
    <!-- 行情展示 -->
    <div class="market-section">
      <div class="section-header">
        <h3>实时行情</h3>
        <button @click="refreshAll" class="refresh-btn" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '刷新' }}
        </button>
      </div>
      <div class="ticker-list">
        <div 
          v-for="ticker in tickers" 
          :key="ticker.symbol"
          class="ticker-item"
          :class="{ 'active': selectedSymbol === ticker.symbol }"
          @click="selectSymbol(ticker.symbol)"
        >
          <div class="symbol">{{ ticker.symbol }}</div>
          <div class="price" :class="ticker.change >= 0 ? 'up' : 'down'">
            {{ formatPrice(ticker.last) }}
          </div>
          <div class="change" :class="ticker.change >= 0 ? 'up' : 'down'">
            {{ formatPercent(ticker.change) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 下单界面 -->
    <div class="order-section">
      <div class="section-header">
        <h3>下单</h3>
        <div class="mode-switch">
          <span :class="{ active: !isDemo }" @click="isDemo = false">实盘</span>
          <span :class="{ active: isDemo }" @click="isDemo = true">模拟盘</span>
        </div>
      </div>
      
      <!-- 买卖切换 -->
      <div class="order-type-switch">
        <button 
          :class="{ active: orderSide === 'buy' }"
          @click="orderSide = 'buy'"
        >
          买入
        </button>
        <button 
          :class="{ active: orderSide === 'sell' }"
          @click="orderSide = 'sell'"
        >
          卖出
        </button>
      </div>

      <!-- 订单类型 -->
      <div class="order-form">
        <div class="form-group">
          <label>订单类型</label>
          <select v-model="orderType">
            <option value="market">市价单</option>
            <option value="limit">限价单</option>
          </select>
        </div>

        <div class="form-group" v-if="orderType === 'limit'">
          <label>价格 (USDT)</label>
          <input 
            type="number" 
            v-model="orderPrice"
            :placeholder="currentPrice"
            step="0.01"
          />
        </div>

        <div class="form-group">
          <label>数量</label>
          <input 
            type="number" 
            v-model="orderQuantity"
            placeholder="输入数量"
            step="0.001"
          />
        </div>

        <div class="form-group">
          <label>总计 (USDT)</label>
          <div class="total">
            {{ calculateTotal }}
          </div>
        </div>

        <button 
          class="submit-btn"
          :class="orderSide"
          @click="submitOrder"
          :disabled="!canSubmit"
        >
          {{ orderSide === 'buy' ? '买入' : '卖出' }} {{ selectedSymbol }}
        </button>
      </div>
    </div>

    <!-- 持仓展示 -->
    <div class="position-section">
      <h3>当前持仓</h3>
      <div class="position-list">
        <div 
          v-for="position in positions" 
          :key="position.symbol"
          class="position-item"
        >
          <div class="pos-header">
            <span class="symbol">{{ position.symbol }}</span>
            <span class="size">{{ position.size }}</span>
          </div>
          <div class="pos-details">
            <div>入场：{{ position.entryPrice }}</div>
            <div>当前：{{ position.currentPrice }}</div>
            <div :class="position.pnl >= 0 ? 'up' : 'down'">
              盈亏：{{ position.pnl }} USDT
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'


// 状态
const tickers = ref([])
const selectedSymbol = ref('BTCUSDT')
const currentPrice = ref(0)
const orderSide = ref('buy')
const orderType = ref('market')
const orderPrice = ref(null)
const orderQuantity = ref(null)
const positions = ref([])
const refreshing = ref(false)
const isDemo = ref(true) // 默认模拟盘

// 计算属性
const canSubmit = computed(() => {
  return orderQuantity.value && orderQuantity.value > 0
})

const calculateTotal = computed(() => {
  const price = orderType.value === 'market' ? currentPrice.value : (orderPrice.value || 0)
  const quantity = orderQuantity.value || 0
  return (price * quantity).toFixed(2)
})

// 方法
const formatPrice = (price) => {
  return parseFloat(price).toFixed(2)
}

const formatPercent = (percent) => {
  return (parseFloat(percent) * 100).toFixed(2) + '%'
}

const selectSymbol = (symbol) => {
  selectedSymbol.value = symbol
  loadTicker(symbol)
}

const refreshAll = async () => {
  refreshing.value = true
  try {
    await Promise.all([
      loadTickers(),
      loadTicker(selectedSymbol.value),
      loadPositions()
    ])
  } finally {
    refreshing.value = false
  }
}

const loadTickers = async () => {
  // 加载热门交易对行情
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
  
  try {
    const promises = symbols.map(async (symbol) => {
      const response = await fetch(`/api/v1/exchanges/ticker/${symbol}`)
      return response.json()
    })
    
    const results = await Promise.all(promises)
    tickers.value = results.filter(t => t && t.last)
    
    // 设置当前选中交易对的价格
    const selected = tickers.value.find(t => t.symbol === selectedSymbol.value)
    if (selected) {
      currentPrice.value = parseFloat(selected.last)
    }
  } catch (error) {
    console.error('加载行情失败:', error)
    // 使用模拟数据
    tickers.value = [
      { symbol: 'BTCUSDT', last: 68800, change: 0.023 },
      { symbol: 'ETHUSDT', last: 3450, change: -0.015 },
      { symbol: 'SOLUSDT', last: 145, change: 0.058 },
      { symbol: 'BNBUSDT', last: 580, change: 0.012 },
      { symbol: 'XRPUSDT', last: 0.62, change: -0.008 },
    ]
  }
}

const loadTicker = async (symbol) => {
  try {
    const response = await fetch(`/api/v1/exchanges/ticker/${symbol}`)
    const data = await response.json()
    if (data && data.last) {
      currentPrice.value = parseFloat(data.last)
    }
  } catch (error) {
    console.error('加载行情失败:', error)
  }
}

const loadPositions = async () => {
  if (isDemo.value) {
    // 加载模拟持仓
    const demoPositions = JSON.parse(localStorage.getItem('demo_positions') || '[]')
    // 更新当前价格
    for (let pos of demoPositions) {
      pos.currentPrice = currentPrice.value || pos.entryPrice
      if (pos.side === 'buy') {
        pos.pnl = (pos.currentPrice - pos.entryPrice) * pos.size
      } else {
        pos.pnl = (pos.entryPrice - pos.currentPrice) * pos.size
      }
    }
    positions.value = demoPositions
  } else {
    // 加载实盘持仓
    try {
      const response = await fetch('/api/v1/trade/positions')
      const data = await response.json()
      positions.value = data.positions || []
    } catch (error) {
      console.error('加载持仓失败:', error)
    }
  }
}

const submitOrder = async () => {
  if (isDemo.value) {
    // 模拟盘模式
    await submitDemoOrder()
  } else {
    // 实盘模式
    await submitRealOrder()
  }
}

const submitDemoOrder = async () => {
  try {
    // 模拟订单提交
    const demoOrder = {
      strategy_id: 'manual',
      symbol: selectedSymbol.value,
      side: orderSide.value,
      quantity: orderQuantity.value.toString(),
      price: orderType.value === 'limit' ? orderPrice.value.toString() : currentPrice.value.toString(),
      order_type: orderType.value,
      is_demo: true,
      timestamp: new Date().toISOString(),
    }
    
    // 保存到本地存储
    const demoOrders = JSON.parse(localStorage.getItem('demo_orders') || '[]')
    demoOrders.push(demoOrder)
    localStorage.setItem('demo_orders', JSON.stringify(demoOrders))
    
    // 更新模拟持仓
    updateDemoPosition(demoOrder)
    
    alert(`✅ 模拟下单成功！\n交易对：${selectedSymbol.value}\n方向：${orderSide.value === 'buy' ? '买入' : '卖出'}\n数量：${orderQuantity.value}\n价格：${demoOrder.price}`)
    
    orderQuantity.value = null
    orderPrice.value = null
    loadPositions()
  } catch (error) {
    console.error('模拟下单失败:', error)
    alert('模拟下单失败')
  }
}

const updateDemoPosition = (order) => {
  // 简单的模拟持仓更新逻辑
  const demoPositions = JSON.parse(localStorage.getItem('demo_positions') || '[]')
  const existingPos = demoPositions.find(p => p.symbol === order.symbol)
  
  if (existingPos) {
    // 更新现有持仓
    const avgPrice = (parseFloat(existingPos.entryPrice) * parseFloat(existingPos.size) + parseFloat(order.price) * parseFloat(order.quantity)) / (parseFloat(existingPos.size) + parseFloat(order.quantity))
    existingPos.entryPrice = avgPrice.toFixed(2)
    existingPos.size = (parseFloat(existingPos.size) + parseFloat(order.quantity)).toFixed(3)
  } else {
    // 新建持仓
    demoPositions.push({
      symbol: order.symbol,
      side: order.side,
      size: order.quantity,
      entryPrice: order.price,
      currentPrice: order.price,
      pnl: 0,
    })
  }
  
  localStorage.setItem('demo_positions', JSON.stringify(demoPositions))
}

const submitRealOrder = async () => {
  try {
    const response = await fetch('/api/v1/trade/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        strategy_id: 'manual',
        symbol: selectedSymbol.value,
        side: orderSide.value,
        quantity: orderQuantity.value.toString(),
        price: orderType.value === 'limit' ? orderPrice.value.toString() : undefined,
        order_type: orderType.value,
      }),
    })
    
    const result = await response.json()
    
    if (result.success) {
      alert('订单提交成功')
      orderQuantity.value = null
      orderPrice.value = null
      loadPositions()
    } else {
      alert('订单提交失败：' + result.message)
    }
  } catch (error) {
    console.error('提交订单失败:', error)
    alert('提交订单失败')
  }
}

// 生命周期
onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.trading-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  padding: 20px;
}

.market-section, .order-section, .position-section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

.mode-switch {
  display: flex;
  background: #f0f0f0;
  border-radius: 20px;
  padding: 3px;
  gap: 3px;
}

.mode-switch span {
  padding: 5px 15px;
  border-radius: 17px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
  color: #666;
}

.mode-switch span.active {
  background: #409EFF;
  color: white;
  font-weight: bold;
}

.mode-switch span:hover:not(.active) {
  background: #e0e0e0;
}

.refresh-btn {
  padding: 6px 16px;
  background: #409EFF;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.refresh-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.refresh-btn:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.position-section {
  grid-column: 1 / -1;
}

.ticker-item {
  display: flex;
  justify-content: space-between;
  padding: 10px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}

.ticker-item:hover {
  background: #f5f5f5;
}

.ticker-item.active {
  background: #e6f7ff;
}

.up {
  color: #28a745;
}

.down {
  color: #dc3545;
}

.order-type-switch {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.order-type-switch button {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.order-type-switch button.active.buy {
  background: #28a745;
  color: white;
}

.order-type-switch button.active.sell {
  background: #dc3545;
  color: white;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.submit-btn {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
}

.submit-btn.buy {
  background: #28a745;
  color: white;
}

.submit-btn.sell {
  background: #dc3545;
  color: white;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.position-item {
  padding: 15px;
  border: 1px solid #eee;
  border-radius: 4px;
  margin-bottom: 10px;
}

.pos-header {
  display: flex;
  justify-content: space-between;
  font-weight: bold;
  margin-bottom: 10px;
}

.pos-details {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  font-size: 14px;
}
</style>
