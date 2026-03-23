<!--
回测页面
-->

<template>
  <div class="backtest-page">
    <div class="backtest-container">
      <h2>策略回测</h2>
      
      <!-- 回测配置 -->
      <div class="config-section">
        <div class="form-row">
          <div class="form-group">
            <label>策略</label>
            <select v-model="config.strategy">
              <option v-for="s in strategies" :key="s.name" :value="s.name">
                {{ s.name }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>交易对</label>
            <select v-model="config.symbol">
              <option v-for="symbol in tradingSymbols" :key="symbol" :value="symbol">
                {{ symbol }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>时间周期</label>
            <select v-model="config.timeframe">
              <option value="1m">1 分钟</option>
              <option value="5m">5 分钟</option>
              <option value="15m">15 分钟</option>
              <option value="1h">1 小时</option>
              <option value="4h">4 小时</option>
              <option value="1d">1 天</option>
            </select>
          </div>
        </div>
        
        <div class="form-row">
          <div class="form-group">
            <label>开始时间</label>
            <input type="date" v-model="config.startTime" />
          </div>
          
          <div class="form-group">
            <label>结束时间</label>
            <input type="date" v-model="config.endTime" />
          </div>
          
          <div class="form-group">
            <label>初始资金</label>
            <input type="number" v-model="config.initialCapital" placeholder="100000" />
          </div>
        </div>
        
        <button @click="runBacktest" class="run-btn" :disabled="running">
          {{ running ? '回测中...' : '开始回测' }}
        </button>
      </div>
      
      <!-- 回测进度 -->
      <div v-if="running" class="progress-section">
        <div class="progress-bar">
          <div class="progress" :style="{ width: progress + '%' }"></div>
        </div>
        <div class="progress-text">{{ progress }}%</div>
      </div>
      
      <!-- 回测结果 -->
      <div v-if="result" class="result-section">
        <BacktestResult :result="result" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import BacktestResult from '@/components/BacktestResult.vue'
import { api } from '@/api/client.js'

const strategies = ref([])
const tradingSymbols = ref([])
const running = ref(false)
const progress = ref(0)
const result = ref(null)

const config = ref({
  strategy: 'ma_cross',
  symbol: 'BTCUSDT',
  timeframe: '1h',
  startTime: '2025-01-01',
  endTime: '2025-12-31',
  initialCapital: 100000,
  params: {},
})

const loadStrategies = async () => {
  try {
    const data = await api.backtest.strategies()
    strategies.value = data.strategies || []
  } catch (error) {
    console.error('加载策略失败:', error)
  }
}

const loadTradingSymbols = async () => {
  try {
    // 从交易所获取热门交易对
    const symbols = [
      'BTC/USDT',
      'ETH/USDT',
      'SOL/USDT',
      'BNB/USDT',
      'XRP/USDT',
      'ADA/USDT',
      'DOGE/USDT',
      'AVAX/USDT',
      'DOT/USDT',
      'MATIC/USDT',
      'LINK/USDT',
      'UNI/USDT',
      'ATOM/USDT',
      'LTC/USDT',
      'ETC/USDT',
    ]
    tradingSymbols.value = symbols
  } catch (error) {
    console.error('加载交易对失败:', error)
    // 默认交易对
    tradingSymbols.value = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
  }
}

const runBacktest = async () => {
  running.value = true
  progress.value = 0
  result.value = null
  
  try {
    // 提交回测任务
    const task = await api.backtest.run({
      strategy_name: config.value.strategy,
      symbol: config.value.symbol,
      timeframe: config.value.timeframe,
      start_time: new Date(config.value.startTime).getTime(),
      end_time: new Date(config.value.endTime).getTime(),
      initial_capital: config.value.initialCapital,
      params: config.value.params,
    })
    
    const taskId = task.task_id
    
    // 轮询任务状态
    const pollInterval = setInterval(async () => {
      const status = await api.backtest.status(taskId)
      progress.value = status.progress || 0
      
      if (status.status === 'completed') {
        clearInterval(pollInterval)
        result.value = await api.backtest.result(taskId)
        running.value = false
      } else if (status.status === 'failed') {
        clearInterval(pollInterval)
        alert('回测失败：' + status.error)
        running.value = false
      }
    }, 1000)
    
  } catch (error) {
    console.error('回测失败:', error)
    alert('回测失败：' + error.message)
    running.value = false
  }
}

onMounted(() => {
  loadStrategies()
  loadTradingSymbols()
})
</script>

<style scoped>
.backtest-page {
  height: 100%;
}

.backtest-container {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.backtest-container h2 {
  margin: 0 0 30px 0;
  color: #333;
}

.config-section {
  background: #f8f9fa;
  padding: 25px;
  border-radius: 8px;
  margin-bottom: 30px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-weight: bold;
  color: #333;
  font-size: 14px;
}

.form-group input,
.form-group select {
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.run-btn {
  padding: 12px 30px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: background 0.2s;
}

.run-btn:hover {
  background: #0056b3;
}

.run-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.progress-section {
  margin-bottom: 30px;
}

.progress-bar {
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress {
  height: 100%;
  background: linear-gradient(90deg, #007bff, #0056b3);
  transition: width 0.3s;
}

.progress-text {
  text-align: center;
  font-weight: bold;
  color: #666;
}

.result-section {
  margin-top: 30px;
}
</style>
