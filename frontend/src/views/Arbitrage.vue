<!--
资金费率套利页面
-->

<template>
  <div class="arbitrage-page">
    <div class="page-header">
      <h1>💰 资金费率套利</h1>
      <p class="description">
        通过永续合约资金费率进行套利，现货和合约对冲，赚取稳定收益
      </p>
    </div>

    <!-- 策略控制 -->
    <div class="strategy-control">
      <div class="control-panel" v-if="!strategyRunning">
        <h3>启动策略</h3>
        <div class="form-row">
          <div class="form-group">
            <label>最小费率阈值 (%)</label>
            <input 
              type="number" 
              v-model="config.min_funding_rate"
              step="0.0001"
              :min="0"
            />
          </div>
          <div class="form-group">
            <label>单笔仓位 (USDT)</label>
            <input 
              type="number" 
              v-model="config.max_position_size"
              :min="100"
            />
          </div>
          <div class="form-group">
            <label>最大持仓数</label>
            <input 
              type="number" 
              v-model="config.max_positions"
              :min="1"
              :max="20"
            />
          </div>
        </div>
        <button @click="startStrategy" class="btn-start">
          启动套利策略
        </button>
      </div>

      <div class="running-status" v-else>
        <div class="status-header">
          <span class="status-indicator running"></span>
          <h3>策略运行中</h3>
          <button @click="stopStrategy" class="btn-stop">
            停止策略
          </button>
        </div>
        <div class="status-stats">
          <div class="stat-item">
            <div class="stat-label">活跃持仓</div>
            <div class="stat-value">{{ activePositions }}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">累计收益</div>
            <div class="stat-value earned">{{ formatMoney(totalEarned) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 费率机会</div> -->
    <div class="opportunities-section">
      <div class="section-header">
        <h3>🎯 套利机会</h3>
        <button @click="refreshRates" :disabled="loading" class="btn-refresh">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <div class="rates-table">
        <table>
          <thead>
            <tr>
              <th>交易对</th>
              <th>交易所</th>
              <th>资金费率</th>
              <th>年化收益率</th>
              <th>方向</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rate in arbitrageOpportunities" :key="rate.symbol + rate.exchange">
              <td class="symbol">{{ rate.symbol }}</td>
              <td>{{ rate.exchange }}</td>
              <td :class="rate.funding_rate >= 0 ? 'positive' : 'negative'">
                {{ formatRate(rate.funding_rate) }}
              </td>
              <td class="annual">{{ formatPercent(rate.annual_rate) }}</td>
              <td>
                <span class="side" :class="rate.side">
                  {{ rate.side === 'SHORT' ? '做空合约' : '做多合约' }}
                </span>
              </td>
              <td>
                <button 
                  @click="executeArbitrage(rate)" 
                  class="btn-execute"
                  :disabled="strategyRunning"
                >
                  执行
                </button>
              </td>
            </tr>
            <tr v-if="arbitrageOpportunities.length === 0">
              <td colspan="6" class="empty">暂无套利机会</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 当前持仓 -->
    <div class="positions-section">
      <h3>📊 当前持仓</h3>
      <div class="positions-table">
        <table>
          <thead>
            <tr>
              <th>交易对</th>
              <th>方向</th>
              <th>入场价</th>
              <th>数量</th>
              <th>累计收益</th>
              <th>开仓时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pos in positions" :key="pos.symbol">
              <td class="symbol">{{ pos.symbol }}</td>
              <td>
                <span class="side" :class="pos.side">
                  {{ pos.side === 'SHORT' ? '做空' : '做多' }}
                </span>
              </td>
              <td>{{ pos.entry_price }}</td>
              <td>{{ pos.quantity }}</td>
              <td :class="pos.funding_earned >= 0 ? 'positive' : 'negative'">
                {{ formatMoney(pos.funding_earned) }}
              </td>
              <td>{{ formatTime(pos.open_time) }}</td>
              <td>
                <button @click="closePosition(pos.symbol)" class="btn-close">
                  平仓
                </button>
              </td>
            </tr>
            <tr v-if="positions.length === 0">
              <td colspan="7" class="empty">暂无持仓</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 策略说明 -->
    <div class="info-section">
      <h3>📖 策略说明</h3>
      <div class="info-content">
        <div class="info-card">
          <h4>💡 策略原理</h4>
          <p>
            永续合约通过资金费率机制锚定现货价格。当费率为正时，多头支付空头；
            当费率为负时，空头支付多头。通过同时持有现货和反向合约，
            可以对冲价格波动风险，稳定赚取资金费收益。
          </p>
        </div>
        <div class="info-card">
          <h4>⚠️ 风险提示</h4>
          <ul>
            <li>资金费率可能反转，导致收益下降或亏损</li>
            <li>交易所风险：平台跑路、黑客攻击等</li>
            <li>流动性风险：极端行情下可能无法及时平仓</li>
            <li>基差风险：现货和合约价格可能出现较大偏离</li>
          </ul>
        </div>
        <div class="info-card">
          <h4>📈 收益计算</h4>
          <p>
            年化收益率 ≈ 资金费率 × 3 (每天 3 次) × 365<br/>
            例如：0.01% 的费率 → 年化约 10.95%
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client.js'

// 状态
const loading = ref(false)
const strategyRunning = ref(false)
const activePositions = ref(0)
const totalEarned = ref(0)
const arbitrageOpportunities = ref([])
const positions = ref([])

// 配置
const config = ref({
  min_funding_rate: 0.0001,
  max_position_size: 1000,
  max_positions: 5,
  exchanges: ['binance', 'bybit'],
})

// 方法
const formatMoney = (value) => {
  return value.toFixed(2) + ' USDT'
}

const formatRate = (rate) => {
  return (rate * 100).toFixed(4) + '%'
}

const formatPercent = (rate) => {
  return (rate * 100).toFixed(2) + '%'
}

const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

const loadRates = async () => {
  try {
    loading.value = true
    const data = await api.arbitrage.getFundingRates()
    arbitrageOpportunities.value = data.rates || []
  } catch (error) {
    console.error('加载费率失败:', error)
    // 模拟数据
    arbitrageOpportunities.value = [
      {
        symbol: 'BTCUSDT',
        exchange: 'binance',
        funding_rate: 0.0001,
        annual_rate: 0.1095,
        side: 'SHORT',
      },
      {
        symbol: 'ETHUSDT',
        exchange: 'binance',
        funding_rate: 0.00015,
        annual_rate: 0.1642,
        side: 'SHORT',
      },
    ]
  } finally {
    loading.value = false
  }
}

const loadPositions = async () => {
  try {
    const data = await api.arbitrage.getFundingRatePositions()
    positions.value = data.positions || []
    activePositions.value = data.active_count || 0
    totalEarned.value = data.total_earned || 0
  } catch (error) {
    console.error('加载持仓失败:', error)
  }
}

const loadStrategyStatus = async () => {
  try {
    const data = await api.arbitrage.getStrategyStatus()
    strategyRunning.value = data.running || false
  } catch (error) {
    console.error('加载策略状态失败:', error)
  }
}

const startStrategy = async () => {
  try {
    await api.arbitrage.startFundingRateArbitrage(config.value)
    strategyRunning.value = true
    alert('策略启动成功！')
    loadStrategyStatus()
  } catch (error) {
    alert('策略启动失败：' + error.message)
  }
}

const stopStrategy = async () => {
  if (!confirm('确定要停止策略吗？将会平掉所有持仓。')) return
  
  try {
    await api.arbitrage.stopFundingRateArbitrage()
    strategyRunning.value = false
    alert('策略已停止')
    loadStrategyStatus()
    loadPositions()
  } catch (error) {
    alert('停止策略失败：' + error.message)
  }
}

const refreshRates = async () => {
  await loadRates()
}

const executeArbitrage = async (opportunity) => {
  if (!confirm(`确定要执行 ${opportunity.symbol} 的套利吗？`)) return
  
  try {
    // TODO: 实现一键执行
    alert('功能开发中...')
  } catch (error) {
    alert('执行失败：' + error.message)
  }
}

const closePosition = async (symbol) => {
  if (!confirm(`确定要平仓 ${symbol} 吗？`)) return
  
  try {
    await api.arbitrage.closePosition(symbol)
    alert('平仓成功')
    loadPositions()
  } catch (error) {
    alert('平仓失败：' + error.message)
  }
}

// 生命周期
onMounted(() => {
  loadRates()
  loadPositions()
  loadStrategyStatus()
  
  // 定时刷新
  setInterval(() => {
    loadRates()
    loadPositions()
  }, 60000) // 每分钟刷新
})
</script>

<style scoped>
.arbitrage-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 30px 20px;
}

.page-header {
  margin-bottom: 30px;
}

.page-header h1 {
  font-size: 32px;
  color: #333;
  margin-bottom: 10px;
}

.description {
  color: #666;
  font-size: 16px;
}

.strategy-control {
  background: white;
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.control-panel h3 {
  margin-bottom: 20px;
  color: #333;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
  color: #555;
}

.form-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.btn-start {
  padding: 12px 30px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: background 0.3s;
}

.btn-start:hover {
  background: #218838;
}

.running-status {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 20px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #6c757d;
}

.status-indicator.running {
  background: #28a745;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-header h3 {
  margin: 0;
  flex: 1;
}

.btn-stop {
  padding: 8px 20px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-stop:hover {
  background: #c82333;
}

.status-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 20px;
}

.stat-item {
  padding: 15px;
  background: white;
  border-radius: 8px;
  text-align: center;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-value.earned {
  color: #28a745;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h3 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.btn-refresh {
  padding: 8px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-refresh:hover:not(:disabled) {
  background: #0056b3;
}

.btn-refresh:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.rates-table, .positions-table {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-bottom: 30px;
  overflow-x: auto;
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
  color: #333;
}

tr:hover {
  background: #f8f9fa;
}

.symbol {
  font-weight: bold;
  color: #007bff;
}

.positive {
  color: #28a745;
  font-weight: bold;
}

.negative {
  color: #dc3545;
  font-weight: bold;
}

.annual {
  color: #28a745;
  font-weight: bold;
}

.side {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
}

.side.SHORT {
  background: #f8d7da;
  color: #721c24;
}

.side.LONG {
  background: #d4edda;
  color: #155724;
}

.btn-execute {
  padding: 6px 16px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-execute:hover:not(:disabled) {
  background: #218838;
}

.btn-execute:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.btn-close {
  padding: 6px 16px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-close:hover {
  background: #c82333;
}

.empty {
  text-align: center;
  color: #999;
  padding: 40px !important;
}

.info-section {
  background: white;
  border-radius: 12px;
  padding: 25px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.info-section h3 {
  margin-bottom: 20px;
  color: #333;
}

.info-content {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.info-card {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.info-card h4 {
  margin-bottom: 15px;
  color: #333;
}

.info-card p,
.info-card ul {
  color: #666;
  line-height: 1.6;
}

.info-card ul {
  padding-left: 20px;
}

.info-card li {
  margin-bottom: 8px;
}
</style>
