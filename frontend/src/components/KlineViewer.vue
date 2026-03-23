<!--
K 线查看器组件 - TradingView 风格
-->

<template>
  <div class="kline-viewer">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="left-section">
        <span class="symbol-title">{{ symbol }}/{{ timeframe }}</span>
      </div>
      
      <div class="center-section">
        <button @click="zoomIn" class="toolbar-btn" title="放大">➕</button>
        <button @click="zoomOut" class="toolbar-btn" title="缩小">➖</button>
        <button @click="resetZoom" class="toolbar-btn" title="重置">🔄</button>
      </div>
      
      <div class="right-section">
        <label>
          <input type="checkbox" v-model="showVolume" /> 成交量
        </label>
        <label>
          <input type="checkbox" v-model="showMA" /> MA
        </label>
      </div>
    </div>
    
    <!-- K 线图表 -->
    <div ref="chartContainer" class="chart-container"></div>
    
    <!-- 数据信息 -->
    <div class="data-info">
      <div class="info-item">
        <span class="label">O:</span>
        <span class="value">{{ currentCandle?.open || '-' }}</span>
      </div>
      <div class="info-item">
        <span class="label">H:</span>
        <span class="value">{{ currentCandle?.high || '-' }}</span>
      </div>
      <div class="info-item">
        <span class="label">L:</span>
        <span class="value">{{ currentCandle?.low || '-' }}</span>
      </div>
      <div class="info-item">
        <span class="label">C:</span>
        <span class="value" :class="currentCandle?.close >= currentCandle?.open ? 'up' : 'down'">
          {{ currentCandle?.close || '-' }}
        </span>
      </div>
      <div class="info-item">
        <span class="label">Vol:</span>
        <span class="value">{{ currentCandle?.volume || '-' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  symbol: {
    type: String,
    required: true,
  },
  timeframe: {
    type: String,
    required: true,
  },
})

const chartContainer = ref(null)
let chart = null
let klineData = ref([])
let volumeData = ref([])
let ma5Data = ref([])
let ma10Data = ref([])
let ma20Data = ref([])

const showVolume = ref(true)
const showMA = ref(true)
const currentCandle = ref(null)

// 加载 K 线数据
const loadKlineData = async () => {
  try {
    const response = await fetch(
      `/api/v1/data/klines?symbol=${props.symbol}&timeframe=${props.timeframe}&limit=1000`
    )
    const data = await response.json()
    
    klineData.value = data.klines || []
    processData()
    renderChart()
  } catch (error) {
    console.error('加载 K 线数据失败:', error)
  }
}

// 处理数据
const processData = () => {
  volumeData.value = klineData.value.map((k, i) => [
    i,
    k.volume,
    k.close >= k.open ? 1 : -1,
  ])
  
  // 计算 MA
  ma5Data.value = calculateMA(5)
  ma10Data.value = calculateMA(10)
  ma20Data.value = calculateMA(20)
}

const calculateMA = (period) => {
  return klineData.value.map((k, i) => {
    if (i < period - 1) return [i, '-']
    
    let sum = 0
    for (let j = 0; j < period; j++) {
      sum += klineData.value[i - j].close
    }
    
    return [i, (sum / period).toFixed(2)]
  })
}

// 渲染图表
const renderChart = () => {
  if (!chartContainer.value) return
  
  chart = echarts.init(chartContainer.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
      formatter: (params) => {
        const p = params[0]
        const candle = klineData.value[p.dataIndex]
        return `
          时间：${new Date(candle.time).toLocaleString()}<br/>
          开：${candle.open}<br/>
          高：${candle.high}<br/>
          低：${candle.low}<br/>
          收：${candle.close}<br/>
          量：${candle.volume}
        `
      },
    },
    grid: [
      {
        left: '10%',
        right: '10%',
        top: '10%',
        height: '60%',
      },
      {
        left: '10%',
        right: '10%',
        top: '75%',
        height: '15%',
      },
    ],
    xAxis: [
      {
        type: 'category',
        data: klineData.value.map((k, i) => i),
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
        axisLabel: {
          formatter: (i) => {
            const candle = klineData.value[i]
            return candle ? new Date(candle.time).toLocaleDateString() : ''
          },
        },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: klineData.value.map((k, i) => i),
        axisLabel: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        splitArea: {
          show: true,
        },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100,
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        bottom: '5%',
        start: 50,
        end: 100,
      },
    ],
    series: [
      {
        name: 'K 线',
        type: 'candlestick',
        data: klineData.value.map((k, i) => [
          k.open,
          k.close,
          k.low,
          k.high,
        ]),
        itemStyle: {
          color: '#28a745',
          color0: '#dc3545',
          borderColor: '#28a745',
          borderColor0: '#dc3545',
        },
      },
      {
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData.value,
        itemStyle: {
          color: (params) => {
            return params.value[2] === 1 ? '#28a745' : '#dc3545'
          },
        },
      },
      {
        name: 'MA5',
        type: 'line',
        data: ma5Data.value,
        smooth: true,
        lineStyle: {
          width: 1,
          color: '#ff6b6b',
        },
      },
      {
        name: 'MA10',
        type: 'line',
        data: ma10Data.value,
        smooth: true,
        lineStyle: {
          width: 1,
          color: '#4ecdc4',
        },
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20Data.value,
        smooth: true,
        lineStyle: {
          width: 1,
          color: '#ffe66d',
        },
      },
    ],
  }
  
  chart.setOption(option)
  
  // 点击事件
  chart.on('click', (params) => {
    if (params.seriesName === 'K 线') {
      currentCandle.value = klineData.value[params.dataIndex]
    }
  })
}

const zoomIn = () => {
  chart.dispatchAction({
    type: 'dataZoom',
    start: 40,
    end: 60,
  })
}

const zoomOut = () => {
  chart.dispatchAction({
    type: 'dataZoom',
    start: 20,
    end: 80,
  })
}

const resetZoom = () => {
  chart.dispatchAction({
    type: 'dataZoom',
    start: 0,
    end: 100,
  })
}

watch(() => [showVolume.value, showMA.value], () => {
  if (chart) {
    chart.setOption({
      series: [
        { show: true }, // K 线
        { show: showVolume.value }, // 成交量
        { show: showMA.value }, // MA5
        { show: showMA.value }, // MA10
        { show: showMA.value }, // MA20
      ],
    })
  }
})

onMounted(() => {
  loadKlineData()
  
  window.addEventListener('resize', () => {
    chart?.resize()
  })
})

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.kline-viewer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
  color: white;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background: #16213e;
  border-bottom: 1px solid #0f3460;
}

.symbol-title {
  font-size: 18px;
  font-weight: bold;
  color: #e94560;
}

.toolbar-btn {
  padding: 5px 10px;
  margin: 0 5px;
  background: #0f3460;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  font-size: 14px;
}

.toolbar-btn:hover {
  background: #1a1a2e;
}

.right-section label {
  margin-left: 15px;
  cursor: pointer;
}

.chart-container {
  flex: 1;
  min-height: 500px;
}

.data-info {
  display: flex;
  gap: 30px;
  padding: 15px 20px;
  background: #16213e;
  border-top: 1px solid #0f3460;
}

.info-item {
  display: flex;
  gap: 5px;
}

.label {
  color: #999;
}

.value {
  font-weight: bold;
  font-family: monospace;
}

.up {
  color: #28a745;
}

.down {
  color: #dc3545;
}
</style>
