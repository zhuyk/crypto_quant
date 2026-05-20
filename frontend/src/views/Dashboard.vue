<!--
仪表盘页面 - 集成 WebSocket 实时行情
-->

<template>
  <div class="dashboard">
    <!-- 连接状态指示器 -->
    <div class="ws-status" :class="{ connected: wsConnected }">
      <span class="status-dot"></span>
      {{ wsConnected ? '实时连接' : '正在连接...' }}
      <span v-if="wsConnected" class="msg-count">{{ messageCount }} msgs</span>
    </div>

    <!-- 概览卡片 -->
    <div class="overview-cards">
      <div class="card">
        <div class="card-label">总资产</div>
        <div class="card-value">{{ formatMoney(totalAsset) }}</div>
        <div class="card-change" :class="assetChange >= 0 ? 'up' : 'down'">
          {{ formatPercent(assetChange) }}
        </div>
      </div>
      
      <div class="card">
        <div class="card-label">日盈亏</div>
        <div class="card-value" :class="dailyPnl >= 0 ? 'up' : 'down'">
          {{ formatMoney(dailyPnl) }}
        </div>
        <div class="card-change" :class="dailyPnl >= 0 ? 'up' : 'down'">
          {{ formatPercent(dailyPnlRate) }}
        </div>
      </div>
      
      <div class="card">
        <div class="card-label">当前回撤</div>
        <div class="card-value down">{{ formatPercent(currentDrawdown) }}</div>
        <div class="card-label">最大：{{ formatPercent(maxDrawdown) }}</div>
      </div>
      
      <div class="card">
        <div class="card-label">持仓</div>
        <div class="card-value">{{ positions.length }}</div>
        <div class="card-label">个交易对</div>
      </div>
    </div>

    <!-- 实时行情面板 -->
    <div class="ticker-panel" v-if="tickerList.length > 0">
      <h3>📡 实时行情</h3>
      <div class="ticker-grid">
        <div 
          v-for="ticker in tickerList" 
          :key="ticker.symbol" 
          class="ticker-item"
          :class="{ flash: isRecentlyUpdated(ticker) }"
        >
          <div class="ticker-symbol">{{ ticker.symbol }}</div>
          <div class="ticker-price" :class="ticker.change >= 0 ? 'up' : 'down'">
            ${{ formatPrice(ticker.price) }}
          </div>
          <div class="ticker-change" :class="ticker.change >= 0 ? 'up' : 'down'">
            {{ ticker.change >= 0 ? '+' : '' }}{{ ticker.change.toFixed(2) }}%
          </div>
        </div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="charts-row">
      <div class="chart-card">
        <h3>资金曲线</h3>
        <div ref="equityChart" class="chart"></div>
      </div>
      
      <div class="chart-card">
        <h3>持仓分布</h3>
        <div ref="positionChart" class="chart"></div>
      </div>
    </div>

    <!-- 策略信号 (实时) -->
    <div class="signals-section" v-if="signals.length > 0">
      <h3>🎯 策略信号 (实时)</h3>
      <div class="signals-list">
        <div v-for="(signal, idx) in signals.slice(0, 5)" :key="idx" class="signal-item">
          <span class="signal-time">{{ formatTime(signal.timestamp) }}</span>
          <span class="signal-symbol">{{ signal.symbol }}</span>
          <span class="signal-action" :class="signal.action">{{ signal.action?.toUpperCase() }}</span>
          <span class="signal-confidence">置信度: {{ (signal.confidence * 100).toFixed(0) }}%</span>
        </div>
      </div>
    </div>

    <!-- 持仓列表 -->
    <div class="positions-section">
      <h3>当前持仓</h3>
      <div class="positions-table">
        <table>
          <thead>
            <tr>
              <th>交易对</th>
              <th>方向</th>
              <th>数量</th>
              <th>入场价</th>
              <th>当前价</th>
              <th>盈亏</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pos in positions" :key="pos.symbol">
              <td>{{ pos.symbol }}</td>
              <td :class="pos.side === 'buy' ? 'up' : 'down'">{{ pos.side.toUpperCase() }}</td>
              <td>{{ pos.size }}</td>
              <td>{{ pos.entryPrice }}</td>
              <td>{{ getRealtimePrice(pos.symbol) || pos.currentPrice }}</td>
              <td :class="pos.pnl >= 0 ? 'up' : 'down'">{{ pos.pnl }} USDT</td>
              <td>
                <button @click="closePosition(pos.symbol)" class="btn-close">平仓</button>
              </td>
            </tr>
            <tr v-if="positions.length === 0">
              <td colspan="7" class="empty">暂无持仓</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 最近交易 -->
    <div class="trades-section">
      <h3>最近交易</h3>
      <div class="trades-table">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>交易对</th>
              <th>方向</th>
              <th>数量</th>
              <th>价格</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="trade in recentTrades" :key="trade.id">
              <td>{{ formatTime(trade.time) }}</td>
              <td>{{ trade.symbol }}</td>
              <td :class="trade.side === 'buy' ? 'up' : 'down'">{{ trade.side.toUpperCase() }}</td>
              <td>{{ trade.quantity }}</td>
              <td>{{ trade.price }}</td>
              <td>
                <span class="status" :class="trade.status">
                  {{ trade.status }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { api } from '@/api/client.js'
import { useWebSocket } from '@/composables/useWebSocket.js'

// === WebSocket 实时数据 ===
const {
  connected: wsConnected,
  tickers,
  tickerList,
  signals,
  tradeUpdates,
  messageCount,
} = useWebSocket()

// === 页面状态 ===
const totalAsset = ref(100000)
const assetChange = ref(0.03)
const dailyPnl = ref(1500)
const dailyPnlRate = ref(0.015)
const currentDrawdown = ref(0.02)
const maxDrawdown = ref(0.05)
const positions = ref([])
const recentTrades = ref([])

// 图表
const equityChart = ref(null)
const positionChart = ref(null)

// === 工具方法 ===
const formatMoney = (value) => {
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

const formatPercent = (value) => {
  return (value * 100).toFixed(2) + '%'
}

const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

const formatPrice = (price) => {
  if (price >= 1000) return price.toFixed(2)
  if (price >= 1) return price.toFixed(4)
  return price.toFixed(6)
}

const isRecentlyUpdated = (ticker) => {
  return ticker.updatedAt && (Date.now() - ticker.updatedAt < 2000)
}

const getRealtimePrice = (symbol) => {
  const ticker = tickers[symbol]
  if (ticker && ticker.price) {
    return formatPrice(ticker.price)
  }
  return null
}

// === 数据加载 ===
const loadDashboard = async () => {
  try {
    // 加载账户总览
    const accountStats = await api.account.statistics()
    totalAsset.value = parseFloat(accountStats.total_balance || 100000)
    
    // 加载持仓
    const positionsData = await api.trader.positions()
    positions.value = positionsData.positions || []
    
    // 加载最近交易
    const traderStats = await api.trader.statistics()
    recentTrades.value = traderStats.recent_trades || []
    
    // 渲染图表
    renderEquityChart()
    renderPositionChart()
  } catch (error) {
    console.error('加载仪表盘失败:', error)
    // 渲染图表（使用默认数据）
    renderEquityChart()
    renderPositionChart()
  }
}

// 当收到交易更新时，刷新持仓
watch(tradeUpdates, () => {
  if (tradeUpdates.value.length > 0) {
    // 有新交易时延迟刷新持仓数据
    setTimeout(loadDashboard, 1000)
  }
}, { deep: true })

// === 图表 ===
const renderEquityChart = () => {
  if (!equityChart.value) return
  
  const chart = echarts.init(equityChart.value)
  
  // 模拟30天数据（后续接入真实equity_curve数据）
  const data = []
  const dates = []
  let value = 100000
  const now = new Date()
  
  for (let i = 29; i >= 0; i--) {
    const date = new Date(now - i * 86400000)
    dates.push(`${date.getMonth() + 1}/${date.getDate()}`)
    value += (Math.random() - 0.45) * 2000
    data.push(value.toFixed(2))
  }
  
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value', scale: true },
    series: [{
      type: 'line',
      smooth: true,
      data,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(40, 167, 69, 0.3)' },
          { offset: 1, color: 'rgba(40, 167, 69, 0.01)' },
        ]),
      },
      lineStyle: { color: '#28a745', width: 2 },
      itemStyle: { color: '#28a745' },
    }],
  })
}

const renderPositionChart = () => {
  if (!positionChart.value) return
  
  const chart = echarts.init(positionChart.value)
  
  const chartData = positions.value.length > 0
    ? positions.value.map(p => ({
        name: p.symbol,
        value: parseFloat(p.size) * parseFloat(p.currentPrice || 0),
      }))
    : [{ name: '无持仓', value: 1 }]
  
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: ${c}' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: chartData,
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' },
      },
      label: { show: true, formatter: '{b}\n{d}%' },
    }],
  })
}

const closePosition = async (symbol) => {
  if (!confirm(`确定要平仓 ${symbol} 吗？`)) return
  
  try {
    await api.trader.execute({
      symbol,
      side: 'sell',
      quantity: 'all',
      order_type: 'market',
    })
    
    alert('平仓成功')
    loadDashboard()
  } catch (error) {
    alert('平仓失败：' + error.message)
  }
}

// === 生命周期 ===
onMounted(() => {
  loadDashboard()
  
  window.addEventListener('resize', () => {
    echarts.getInstanceByDom(equityChart.value)?.resize()
    echarts.getInstanceByDom(positionChart.value)?.resize()
  })
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* WebSocket 连接状态 */
.ws-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #999;
  padding: 6px 12px;
  background: #f8f9fa;
  border-radius: 20px;
  width: fit-content;
}

.ws-status.connected {
  color: #28a745;
  background: #d4edda;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
  animation: pulse 2s infinite;
}

.ws-status.connected .status-dot {
  background: #28a745;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.msg-count {
  margin-left: 8px;
  opacity: 0.7;
}

/* 实时行情面板 */
.ticker-panel {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.ticker-panel h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #333;
}

.ticker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.ticker-item {
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.ticker-item.flash {
  background: #e8f5e9;
  animation: tickFlash 0.5s ease;
}

@keyframes tickFlash {
  0% { background: #fff9c4; }
  100% { background: #f8f9fa; }
}

.ticker-symbol {
  font-size: 12px;
  color: #666;
  font-weight: 600;
  margin-bottom: 4px;
}

.ticker-price {
  font-size: 18px;
  font-weight: bold;
}

.ticker-change {
  font-size: 13px;
  font-weight: 600;
  margin-top: 2px;
}

/* 策略信号 */
.signals-section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.signals-section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #333;
}

.signal-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}

.signal-time { color: #999; }
.signal-symbol { font-weight: 600; color: #333; }
.signal-action { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
.signal-action.buy { background: #d4edda; color: #155724; }
.signal-action.sell { background: #f8d7da; color: #721c24; }
.signal-action.hold { background: #fff3cd; color: #856404; }
.signal-confidence { color: #666; margin-left: auto; }

/* 原有样式 */
.overview-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.card {
  background: white;
  padding: 25px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.card-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}

.card-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
}

.card-change {
  font-size: 14px;
  font-weight: bold;
}

.up { color: #28a745; }
.down { color: #dc3545; }

.charts-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}

.chart-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.chart-card h3 {
  margin: 0 0 20px 0;
  font-size: 16px;
  color: #333;
}

.chart { height: 300px; }

.positions-section, .trades-section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.positions-section h3, .trades-section h3 {
  margin: 0 0 20px 0;
  font-size: 16px;
  color: #333;
}

.positions-table, .trades-table { overflow-x: auto; }

table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: bold; color: #333; }
tr:hover { background: #f8f9fa; }

.btn-close {
  padding: 5px 15px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-close:hover { background: #c82333; }
.empty { text-align: center; color: #999; padding: 40px !important; }

.status { padding: 3px 8px; border-radius: 4px; font-size: 12px; }
.status.filled { background: #d4edda; color: #155724; }
.status.pending { background: #fff3cd; color: #856404; }
.status.cancelled { background: #f8d7da; color: #721c24; }

@media (max-width: 768px) {
  .charts-row { grid-template-columns: 1fr; }
  .ticker-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
