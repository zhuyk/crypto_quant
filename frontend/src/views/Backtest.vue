<!--
回测页面 - 支持参数优化
-->

<template>
  <div class="backtest-page">
    <div class="backtest-container">
      <h2>策略回测</h2>
      
      <!-- 标签页切换 -->
      <div class="tabs">
        <button :class="{ active: activeTab === 'backtest' }" @click="activeTab = 'backtest'">
          回测
        </button>
        <button :class="{ active: activeTab === 'optimize' }" @click="activeTab = 'optimize'">
          参数优化
        </button>
      </div>
      
      <!-- ==================== 回测面板 ==================== -->
      <div v-if="activeTab === 'backtest'" class="tab-content">
        <!-- 回测配置 -->
        <div class="config-section">
          <div class="form-row">
            <div class="form-group">
              <label>策略</label>
              <select v-model="config.strategy">
                <option v-for="s in strategies" :key="s.key" :value="s.key">
                  {{ s.name }}
                </option>
              </select>
              <!-- 策略说明（紧跟在下拉框下方） -->
              <div v-if="currentStrategyInfo && currentStrategyInfo.description" class="strategy-desc-inline">
                <p>{{ showFullDesc ? currentStrategyInfo.description : truncateDesc(currentStrategyInfo.description) }}</p>
                <button 
                  @click="toggleDesc" 
                  class="toggle-desc-btn"
                  :class="{ 'expanded': showFullDesc }"
                >
                  {{ showFullDesc ? '收起' : '展开' }}
                </button>
              </div>
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

          <!-- 策略参数 (强制使用当前配置,不让后端fallback) -->
          <div class="params-section">
            <h4>策略参数</h4>
            <div class="form-row params-grid">
              <div v-for="(val, key) in currentStrategyParams" :key="key" class="form-group">
                <label :title="currentStrategyParamDesc(key)">{{ paramLabel(key) }}</label>
                <input type="number" v-model="currentStrategyParams[key]" @input="updateConfigParams" />
                <span v-if="currentStrategyParamDesc(key)" class="param-hint">{{ currentStrategyParamDesc(key) }}</span>
              </div>
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
      
      <!-- ==================== 参数优化面板 ==================== -->
      <div v-if="activeTab === 'optimize'" class="tab-content">
        <div class="config-section">
          <h3>参数优化配置</h3>
          
          <div class="form-row">
            <div class="form-group">
              <label>策略</label>
              <select v-model="optimizeConfig.strategy">
                <option v-for="s in strategies" :key="s.key" :value="s.key">
                  {{ s.name }}
                </option>
              </select>
            </div>
            
            <div class="form-group">
              <label>交易对</label>
              <select v-model="optimizeConfig.symbol">
                <option v-for="symbol in tradingSymbols" :key="symbol" :value="symbol">
                  {{ symbol }}
                </option>
              </select>
            </div>
            
            <div class="form-group">
              <label>时间周期</label>
              <select v-model="optimizeConfig.timeframe">
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
              <label>优化方法</label>
              <select v-model="optimizeConfig.method">
                <option value="grid_search">网格搜索</option>
                <option value="random_search">随机搜索</option>
                <option value="genetic">遗传算法</option>
              </select>
            </div>
            
            <div class="form-group">
              <label>迭代次数</label>
              <input type="number" v-model="optimizeConfig.iterations" min="10" max="10000" />
            </div>
            
            <div class="form-group">
              <label>优化指标</label>
              <select v-model="optimizeConfig.metric">
                <option value="sharpe_ratio">Sharpe比率</option>
                <option value="total_return">总收益率</option>
              </select>
            </div>
          </div>
          
          <!-- 参数范围配置 -->
          <div class="params-section">
            <h4>参数范围</h4>
            <div class="param-range-list">
              <div v-for="(range, key) in paramRanges" :key="key" class="param-range-item">
                <span class="param-name" :title="currentOptimizeParamDesc(key)">{{ paramLabel(key) }}</span>
                <input type="number" v-model="range.min" placeholder="最小值" />
                <span class="range-sep">~</span>
                <input type="number" v-model="range.max" placeholder="最大值" />
                <input type="number" v-model="range.step" placeholder="步长" class="step-input" />
                <button @click="removeParamRange(key)" class="remove-btn">×</button>
                <span v-if="currentOptimizeParamDesc(key)" class="param-hint">{{ currentOptimizeParamDesc(key) }}</span>
              </div>
            </div>
            
            <div class="add-param">
              <select v-model="newParamName">
                <option value="">添加参数...</option>
                <option v-for="p in availableParams" :key="p" :value="p">{{ paramLabel(p) }}</option>
              </select>
              <button @click="addParamRange" :disabled="!newParamName" class="add-btn">+</button>
            </div>
          </div>
          
          <button @click="startOptimization" class="run-btn optimize-btn" :disabled="optimizing">
            {{ optimizing ? `优化中... ${optimizeProgress}%` : '开始优化' }}
          </button>
        </div>
        
        <!-- 优化进度 -->
        <div v-if="optimizing" class="progress-section">
          <div class="progress-bar">
            <div class="progress progress-optimize" :style="{ width: optimizeProgress + '%' }"></div>
          </div>
          <div class="progress-text">{{ optimizeProgress }}% | 耗时: {{ optimizeElapsed }}s | 已测试: {{ testedCount }}/{{ totalCombinations }}</div>
        </div>
        
        <!-- 优化结果 -->
        <div v-if="optimizeResult" class="optimize-result-section">
          <h3>优化结果</h3>
          
          <!-- 最佳参数 -->
          <div class="best-params-card">
            <div class="best-header">
              <span class="best-label">🏆 最佳参数</span>
              <span class="best-metric">指标值: {{ optimizeResult.best_metric?.toFixed(4) }}</span>
            </div>
            <div class="best-params-grid">
              <div v-for="(val, key) in optimizeResult.best_params" :key="key" class="best-param-item">
                <span class="param-key">{{ paramLabel(key) }}</span>
                <span class="param-val">{{ typeof val === 'number' ? val.toFixed(4) : val }}</span>
              </div>
            </div>
            <div class="best-actions">
              <button @click="useBestParams" class="use-best-btn">使用最佳参数回测</button>
            </div>
          </div>
          
          <!-- Top 10 参数组合 -->
          <div class="top10-section">
            <h4>Top 10 参数组合</h4>
            <table class="top10-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>参数组合</th>
                  <th>指标值</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in optimizeResult.top_10" :key="idx">
                  <td>{{ idx + 1 }}</td>
                  <td class="params-cell">
                    <span v-for="(val, k) in item.params" :key="k" class="param-tag">
                      {{ paramLabel(k) }}: {{ typeof val === 'number' ? val.toFixed(4) : val }}
                    </span>
                  </td>
                  <td class="metric-cell">{{ item.metric?.toFixed(4) }}</td>
                  <td>
                    <button @click="useParams(item.params)" class="use-btn">使用</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import BacktestResult from '@/components/BacktestResult.vue'
import { api } from '@/api/client.js'

const activeTab = ref('backtest')
const strategies = ref([])
const tradingSymbols = ref([])
const running = ref(false)
const progress = ref(0)
const result = ref(null)
const showFullDesc = ref(false)  // 控制策略说明展开/收起

// 回测配置
const config = ref({
  strategy: 'ma_cross',
  symbol: 'BTC/USDT',
  timeframe: '1h',
  startTime: '2025-01-01',
  endTime: '2025-12-31',
  initialCapital: 100000,
  params: {},
})

// 当前策略的默认参数
const currentStrategyParams = ref({})

// 优化配置
const optimizeConfig = ref({
  strategy: 'ma_cross',
  symbol: 'BTC/USDT',
  timeframe: '1h',
  method: 'grid_search',
  iterations: 100,
  metric: 'sharpe_ratio',
})

// 参数范围
const paramRanges = ref({})
const newParamName = ref('')

// 优化状态
const optimizing = ref(false)
const optimizeProgress = ref(0)
const optimizeElapsed = ref(0)
const testedCount = ref(0)
const totalCombinations = ref(0)
const optimizeResult = ref(null)

// 所有策略的默认参数
const allStrategyParams = {
  ma_cross: {
    fast_period: 20,
    slow_period: 60,
    stop_loss_pct: 0.05,
    take_profit_pct: 0.15,
  },
  breakout: {
    lookback_period: 20,
    stop_loss_pct: 0.08,
  },
  macd: {
    fast_period: 12,
    slow_period: 26,
    signal_period: 9,
  },
  bollinger: {
    bb_period: 20,
    bb_std: 2.0,
    stop_loss_pct: 0.03,
    take_profit_pct: 0.06,
    rsi_period: 14,
    rsi_oversold: 30,
    rsi_overbought: 70,
  },
  turtle: {
    entry_period: 20,
    exit_period: 10,
    atr_period: 20,
    atr_multiplier: 2.0,
    max_units: 4,
    unit_size_pct: 0.02,
  },
}

// 参数中文标签映射
const paramLabels = {
  // 通用
  stop_loss_pct: '止损比例',
  take_profit_pct: '止盈比例',
  // 均线
  fast_period: '快线周期',
  slow_period: '慢线周期',
  use_ema: '使用EMA',
  min_strength: '最小信号强度',
  // 突破
  lookback_period: '通道周期',
  volume_filter: '成交量过滤',
  volume_multiplier: '成交量倍数',
  use_trailing_stop: '移动止损',
  // MACD
  signal_period: '信号线周期',
  // 布林
  bb_period: '布林周期',
  bb_std: '标准差倍数',
  rsi_period: 'RSI周期',
  rsi_oversold: 'RSI超卖',
  rsi_overbought: 'RSI超买',
  position_pct: '仓位比例',
  min_bb_width: '最小布林宽度',
  // 海龟
  entry_period: '入场周期',
  exit_period: '出场周期',
  atr_period: 'ATR周期',
  atr_multiplier: 'ATR倍数',
  max_units: '最大加仓数',
  unit_size_pct: '单笔仓位比',
  use_system1_only: '只用System1',
  min_volatility: '最小波动率',
}

// 显示中文名（保留英文）如 "布林周期 (bb_period)"
function paramLabel(key) {
  return paramLabels[key] ? `${paramLabels[key]} (${key})` : key
}

// 可用于优化的参数（从 API 数据获取）
const availableParams = computed(() => {
  const s = strategies.value.find(x => x.key === optimizeConfig.value.strategy)
  const defaultParams = s && s.params ? s.params : {}
  return Object.keys(defaultParams).filter(k => !(k in paramRanges.value))
})

// 当前策略参数（从 API 数据获取）
const currentStrategyParams2 = computed(() => {
  const s = strategies.value.find(x => x.key === config.value.strategy)
  return s && s.params ? s.params : {}
})

// 当前策略的完整信息（含 description、param_descriptions）
const currentStrategyInfo = computed(() => {
  return strategies.value.find(x => x.key === config.value.strategy) || null
})

// 获取某个参数的说明文字
function currentStrategyParamDesc(key) {
  const info = currentStrategyInfo.value
  if (info && info.param_descriptions && info.param_descriptions[key]) {
    return info.param_descriptions[key]
  }
  return ''
}

// 获取优化面板中某参数的说明（使用 optimizeConfig 的策略）
function currentOptimizeParamDesc(key) {
  const info = strategies.value.find(x => x.key === optimizeConfig.value.strategy)
  if (info && info.param_descriptions && info.param_descriptions[key]) {
    return info.param_descriptions[key]
  }
  return ''
}

// 切换策略说明展开/收起
function toggleDesc() {
  showFullDesc.value = !showFullDesc.value
}

// 截断描述文本（保留前2行）
function truncateDesc(desc) {
  if (!desc) return ''
  // 按句号、分号、逗号分割，取前2-3个句子
  const sentences = desc.split(/[。；;，,]/)
  if (sentences.length <= 2) return desc
  
  let truncated = sentences[0] + '。'
  if (sentences[1]) truncated += sentences[1] + '。'
  return truncated + '...'
}

// 监听策略变化，更新参数
watch(() => config.value.strategy, (newStrategy) => {
  // 从 API 返回的策略数据中获取 params
  const s = strategies.value.find(x => x.key === newStrategy)
  currentStrategyParams.value = s && s.params ? { ...s.params } : {}
  updateConfigParams()
}, { immediate: true })

watch(() => optimizeConfig.value.strategy, (newStrategy) => {
  // 从 API 数据预填 param_ranges
  const s = strategies.value.find(x => x.key === newStrategy)
  if (s && s.param_ranges) {
    // 转换为 { paramName: { min, max, step } } 格式
    const ranges = {}
    for (const [key, values] of Object.entries(s.param_ranges)) {
      if (Array.isArray(values) && values.length >= 2) {
        ranges[key] = {
          min: values[0],
          max: values[values.length - 1],
          step: values.length > 2 ? (values[1] - values[0]) : 1,
        }
      }
    }
    paramRanges.value = ranges
  } else {
    paramRanges.value = {}
  }
}, { immediate: true })

// 更新 config.params
function updateConfigParams() {
  config.value.params = { ...currentStrategyParams.value }
}

const loadStrategies = async () => {
  try {
    const data = await api.backtest.strategies()
    const raw = data.strategies || {}
    strategies.value = Object.entries(raw).map(([key, val]) => ({ key, ...val }))
    
    // 加载完成后初始化当前策略参数（修复首次加载参数不显示的问题）
    const s = strategies.value.find(x => x.key === config.value.strategy)
    if (s && s.params) {
      currentStrategyParams.value = { ...s.params }
      updateConfigParams()
    }
  } catch (error) {
    console.error('加载策略失败:', error)
  }
}

const loadTradingSymbols = async () => {
  tradingSymbols.value = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT',
    'LINK/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ETC/USDT',
  ]
}

const runBacktest = async () => {
  running.value = true
  progress.value = 0
  result.value = null
  
  try {
    // 确保使用当前参数（强制带参数，不让后端fallback）
    const params = { ...currentStrategyParams.value }
    
    const response = await api.backtest.run({
      strategy_name: config.value.strategy,
      symbol: config.value.symbol.replace('/', ''),  // BTC/USDT -> BTCUSDT
      timeframe: config.value.timeframe,
      start_time: new Date(config.value.startTime).getTime(),
      end_time: new Date(config.value.endTime).getTime(),
      initial_capital: config.value.initialCapital,
      params: params,  // 强制传递当前参数
    })
    
    if (!response.success) {
      throw new Error(response.error || '回测失败')
    }
    
    progress.value = 100
    result.value = response.report
    running.value = false
    
  } catch (error) {
    console.error('回测失败:', error)
    alert('回测失败：' + error.message)
    running.value = false
  }
}

// 添加参数范围
function addParamRange() {
  if (!newParamName.value) return
  const defaultVal = currentStrategyParams2.value[newParamName.value] || 10
  paramRanges.value[newParamName.value] = {
    min: defaultVal * 0.5,
    max: defaultVal * 2,
    step: defaultVal * 0.1,
  }
  newParamName.value = ''
}

// 移除参数范围
function removeParamRange(key) {
  delete paramRanges.value[key]
  paramRanges.value = { ...paramRanges.value }
}

// 开始优化
const startOptimization = async () => {
  if (Object.keys(paramRanges.value).length === 0) {
    alert('请先配置参数范围')
    return
  }
  
  optimizing.value = true
  optimizeProgress.value = 0
  optimizeElapsed.value = 0
  testedCount.value = 0
  optimizeResult.value = null
  
  const startTime = Date.now()
  const timer = setInterval(() => {
    optimizeElapsed.value = Math.floor((Date.now() - startTime) / 1000)
  }, 1000)
  
  try {
    // 转换参数范围格式
    const paramRangesConverted = {}
    for (const [key, range] of Object.entries(paramRanges.value)) {
      paramRangesConverted[key] = []
      let val = range.min
      while (val <= range.max) {
        paramRangesConverted[key].push(val)
        val += range.step
      }
      // 计算总组合数
      if (totalCombinations.value === 0) {
        totalCombinations.value = paramRangesConverted[key].length
      } else {
        totalCombinations.value *= paramRangesConverted[key].length
      }
    }
    
    // 分批执行，避免超时
    const batchSize = 20
    const totalBatches = Math.ceil(totalCombinations.value / batchSize)
    let allResults = []
    
    for (let batch = 0; batch < Math.min(totalBatches, 50); batch++) {
      const response = await api.backtest.optimize({
        strategy_name: optimizeConfig.value.strategy,
        symbol: optimizeConfig.value.symbol.replace('/', ''),
        timeframe: optimizeConfig.value.timeframe,
        param_ranges: paramRangesConverted,
        method: optimizeConfig.value.method,
        iterations: optimizeConfig.value.iterations,
      })
      
      if (response.success && response.top_10) {
        allResults = [...allResults, ...response.top_10]
        // 按指标排序
        allResults.sort((a, b) => b.metric - a.metric)
        allResults = allResults.slice(0, 100)  // 保留前100
        optimizeResult.value = {
          best_params: allResults[0]?.params,
          best_metric: allResults[0]?.metric,
          top_10: allResults.slice(0, 10),
        }
      }
      
      optimizeProgress.value = Math.min(100, Math.round((batch + 1) / totalBatches * 100))
      testedCount.value = Math.min(totalCombinations.value, (batch + 1) * batchSize)
    }
    
    clearInterval(timer)
    optimizing.value = false
    
  } catch (error) {
    console.error('优化失败:', error)
    alert('优化失败：' + error.message)
    clearInterval(timer)
    optimizing.value = false
  }
}

// 使用最佳参数
function useBestParams() {
  if (!optimizeResult.value?.best_params) return
  useParams(optimizeResult.value.best_params)
}

// 使用指定参数
function useParams(params) {
  // 切换到回测标签
  activeTab.value = 'backtest'
  // 设置策略
  config.value.strategy = optimizeConfig.value.strategy
  // 设置参数
  currentStrategyParams.value = { ...params }
  updateConfigParams()
  // 自动运行回测
  setTimeout(() => runBacktest(), 100)
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
  margin: 0 0 20px 0;
  color: #333;
}

/* 标签页 */
.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 25px;
  border-bottom: 2px solid #eee;
  padding-bottom: 10px;
}

.tabs button {
  padding: 10px 24px;
  border: none;
  background: transparent;
  color: #666;
  font-size: 15px;
  font-weight: bold;
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  transition: all 0.2s;
}

.tabs button:hover {
  background: #f0f0f0;
}

.tabs button.active {
  background: #007bff;
  color: white;
}

.tab-content {
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}

.config-section {
  background: #f8f9fa;
  padding: 25px;
  border-radius: 8px;
  margin-bottom: 30px;
}

.config-section h3 {
  margin: 0 0 20px 0;
  color: #333;
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

/* 策略说明（紧凑版） */
.strategy-desc-inline {
  margin-top: 8px;
  padding: 10px 12px;
  background: #f8fafc;
  border-left: 3px solid #3b82f6;
  border-radius: 4px;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}

.strategy-desc-inline p {
  margin: 0 0 6px 0;
}

.toggle-desc-btn {
  padding: 2px 8px;
  font-size: 11px;
  color: #3b82f6;
  background: transparent;
  border: 1px solid #3b82f6;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-desc-btn:hover {
  background: #3b82f6;
  color: white;
}

.toggle-desc-btn.expanded {
  background: #3b82f6;
  color: white;
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

/* 策略说明 */
.strategy-desc {
  margin: 10px 0;
  padding: 12px 16px;
  background: #f0f7ff;
  border-left: 4px solid #3b82f6;
  border-radius: 6px;
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}

.strategy-desc p {
  margin: 0;
}

/* 参数提示 */
.param-hint {
  font-size: 11px;
  color: #6b7280;
  line-height: 1.4;
  margin-top: 2px;
}

/* 策略参数 */
.params-section {
  margin: 20px 0;
  padding: 15px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}

.params-section h4 {
  margin: 0 0 15px 0;
  color: #333;
}

.params-grid {
  grid-template-columns: repeat(4, 1fr);
}

/* 优化参数范围 */
.param-range-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 15px;
}

.param-range-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #ddd;
}

.param-name {
  font-weight: bold;
  min-width: 120px;
  color: #333;
}

.param-range-item input {
  padding: 6px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
  width: 80px;
}

.step-input {
  width: 60px !important;
}

.range-sep {
  color: #999;
}

.remove-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: #ff4444;
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}

.add-param {
  display: flex;
  gap: 10px;
  align-items: center;
}

.add-param select {
  flex: 1;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 6px;
}

.add-btn {
  padding: 8px 16px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 18px;
  font-weight: bold;
}

.add-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
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

.optimize-btn {
  background: #6f42c1;
}

.optimize-btn:hover {
  background: #5a2d91;
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

.progress-optimize {
  background: linear-gradient(90deg, #6f42c1, #5a2d91);
}

.progress-text {
  text-align: center;
  font-weight: bold;
  color: #666;
  font-size: 14px;
}

.result-section {
  margin-top: 30px;
}

/* 优化结果 */
.optimize-result-section {
  margin-top: 30px;
}

.optimize-result-section h3 {
  margin: 0 0 20px 0;
  color: #333;
}

.optimize-result-section h4 {
  margin: 20px 0 15px 0;
  color: #333;
}

.best-params-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 20px;
  color: white;
}

.best-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.best-label {
  font-size: 18px;
  font-weight: bold;
}

.best-metric {
  font-size: 16px;
  opacity: 0.9;
}

.best-params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 20px;
}

.best-param-item {
  background: rgba(255,255,255,0.2);
  padding: 10px;
  border-radius: 6px;
}

.param-key {
  display: block;
  font-size: 12px;
  opacity: 0.8;
}

.param-val {
  display: block;
  font-size: 18px;
  font-weight: bold;
}

.best-actions {
  text-align: center;
}

.use-best-btn {
  padding: 12px 30px;
  background: white;
  color: #667eea;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: transform 0.2s;
}

.use-best-btn:hover {
  transform: scale(1.05);
}

/* Top 10 表格 */
.top10-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.top10-table th {
  background: #f8f9fa;
  padding: 12px;
  text-align: left;
  font-weight: bold;
  color: #333;
}

.top10-table td {
  padding: 12px;
  border-bottom: 1px solid #eee;
}

.top10-table tr:hover {
  background: #f8f9fa;
}

.params-cell {
  max-width: 400px;
}

.param-tag {
  display: inline-block;
  background: #e9ecef;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
  margin: 2px;
}

.metric-cell {
  font-weight: bold;
  color: #28a745;
}

.use-btn {
  padding: 6px 12px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.use-btn:hover {
  background: #0056b3;
}
</style>
