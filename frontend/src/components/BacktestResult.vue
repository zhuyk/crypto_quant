<!--
回测结果展示组件
-->

<template>
  <div class="backtest-result">
    <!-- 回测概览 -->
    <div class="overview-section">
      <h3>回测概览</h3>
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">总收益率</div>
          <div class="metric-value" :class="metrics.totalReturn >= 0 ? 'up' : 'down'">
            {{ formatPercent(metrics.totalReturn) }}
          </div>
        </div>
        
        <div class="metric-card">
          <div class="metric-label">Sharpe 比率</div>
          <div class="metric-value">{{ metrics.sharpeRatio?.toFixed(2) || '0.00' }}</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-label">最大回撤</div>
          <div class="metric-value down">{{ formatPercent(metrics.maxDrawdown) }}</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-label">胜率</div>
          <div class="metric-value">{{ formatPercent(metrics.winRate) }}</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-label">交易次数</div>
          <div class="metric-value">{{ metrics.totalTrades }}</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-label">盈亏比</div>
          <div class="metric-value">{{ metrics.profitFactor?.toFixed(2) || '0.00' }}</div>
        </div>
      </div>
    </div>

    <!-- 资金曲线 -->
    <div class="chart-section">
      <h3>资金曲线</h3>
      <div ref="equityChartContainer" class="chart-container"></div>
    </div>

    <!-- 回撤曲线 -->
    <div class="chart-section">
      <h3>回撤曲线</h3>
      <div ref="drawdownChartContainer" class="chart-container"></div>
    </div>

    <!-- 月度收益 -->
    <div class="chart-section">
      <h3>月度收益</h3>
      <div ref="monthlyChartContainer" class="chart-container"></div>
    </div>

    <!-- 交易记录 -->
    <div class="trades-section">
      <h3>交易记录</h3>
      <div class="trades-table">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>交易对</th>
              <th>方向</th>
              <th>数量</th>
              <th>入场价</th>
              <th>出场价</th>
              <th>盈亏</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="trade in trades" :key="trade.id">
              <td>{{ formatDate(trade.time) }}</td>
              <td>{{ trade.symbol }}</td>
              <td :class="trade.side === 'buy' ? 'up' : 'down'">{{ trade.side.toUpperCase() }}</td>
              <td>{{ trade.quantity }}</td>
              <td>{{ trade.entryPrice }}</td>
              <td>{{ trade.exitPrice }}</td>
              <td :class="trade.pnl >= 0 ? 'up' : 'down'">{{ trade.pnl }}</td>
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

const props = defineProps({
  result: {
    type: Object,
    required: true,
  },
})

// 状态
const metrics = ref({
  totalReturn: 0,
  sharpeRatio: 0,
  maxDrawdown: 0,
  winRate: 0,
  totalTrades: 0,
  profitFactor: 0,
})

const trades = ref([])

// 图表容器
const equityChartContainer = ref(null)
const drawdownChartContainer = ref(null)
const monthlyChartContainer = ref(null)

// 图表实例
let equityChart = null
let drawdownChart = null
let monthlyChart = null

// 方法
const formatPercent = (value) => {
  if (value === null || value === undefined) return '0.00%'
  return (value * 100).toFixed(2) + '%'
}

const formatDate = (timestamp) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}

const loadResult = () => {
  if (!props.result) return
  
  metrics.value = {
    totalReturn: props.result.total_return || 0,
    sharpeRatio: props.result.sharpe_ratio || 0,
    maxDrawdown: props.result.max_drawdown || 0,
    winRate: props.result.win_rate || 0,
    totalTrades: props.result.total_trades || 0,
    profitFactor: props.result.profit_factor || 0,
  }
  
  trades.value = props.result.trades || []
  
  // 渲染图表
  renderEquityChart()
  renderDrawdownChart()
  renderMonthlyChart()
}

const renderEquityChart = () => {
  if (!equityChartContainer.value) return
  
  equityChart = echarts.init(equityChartContainer.value)
  
  const equityCurve = props.result.equity_curve || []
  
  const option = {
    tooltip: {
      trigger: 'axis',
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: equityCurve.map(p => formatDate(p.time)),
    },
    yAxis: {
      type: 'value',
    },
    series: [{
      name: '权益',
      type: 'line',
      smooth: true,
      data: equityCurve.map(p => p.value),
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(40, 167, 69, 0.3)' },
          { offset: 1, color: 'rgba(40, 167, 69, 0.01)' },
        ]),
      },
      lineStyle: {
        color: '#28a745',
      },
    }],
  }
  
  equityChart.setOption(option)
}

const renderDrawdownChart = () => {
  if (!drawdownChartContainer.value) return
  
  drawdownChart = echarts.init(drawdownChartContainer.value)
  
  const equityCurve = props.result.equity_curve || []
  
  // 计算回撤
  let peak = 0
  const drawdowns = equityCurve.map(p => {
    if (p.value > peak) peak = p.value
    const dd = peak > 0 ? (peak - p.value) / peak : 0
    return { time: p.time, drawdown: dd }
  })
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>回撤：${(p.value * 100).toFixed(2)}%`
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: drawdowns.map(p => formatDate(p.time)),
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value) => `${(value * 100).toFixed(0)}%`,
      },
    },
    series: [{
      name: '回撤',
      type: 'line',
      smooth: true,
      data: drawdowns.map(p => -p.drawdown),
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(220, 53, 69, 0.3)' },
          { offset: 1, color: 'rgba(220, 53, 69, 0.01)' },
        ]),
      },
      lineStyle: {
        color: '#dc3545',
      },
    }],
  }
  
  drawdownChart.setOption(option)
}

const renderMonthlyChart = () => {
  if (!monthlyChartContainer.value) return
  
  monthlyChart = echarts.init(monthlyChartContainer.value)
  
  // 按月统计收益
  const monthlyData = {}
  trades.value.forEach(trade => {
    const month = new Date(trade.time).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit' })
    if (!monthlyData[month]) monthlyData[month] = 0
    monthlyData[month] += trade.pnl || 0
  })
  
  const months = Object.keys(monthlyData)
  const returns = Object.values(monthlyData)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: months,
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value) => `${value} USDT`,
      },
    },
    series: [{
      name: '月度收益',
      type: 'bar',
      data: returns.map((r, i) => ({
        value: r,
        itemStyle: {
          color: r >= 0 ? '#28a745' : '#dc3545',
        },
      })),
    }],
  }
  
  monthlyChart.setOption(option)
}

// 监听
watch(() => props.result, loadResult, { immediate: true })

// 生命周期
onMounted(() => {
  window.addEventListener('resize', () => {
    equityChart?.resize()
    drawdownChart?.resize()
    monthlyChart?.resize()
  })
})
</script>

<style scoped>
.backtest-result {
  padding: 20px;
}

.overview-section {
  margin-bottom: 30px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.metric-card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.metric-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.up {
  color: #28a745;
}

.down {
  color: #dc3545;
}

.chart-section {
  margin-bottom: 30px;
}

.chart-container {
  height: 300px;
  margin-top: 20px;
}

.trades-section {
  margin-top: 30px;
}

.trades-table {
  overflow-x: auto;
  margin-top: 20px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

th {
  background: #f8f9fa;
  font-weight: bold;
}

tr:hover {
  background: #f8f9fa;
}
</style>
