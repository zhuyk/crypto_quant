<template>
  <div class="kline-chart-container" :style="{ height: containerHeight }">
    <div v-if="loading" class="chart-loading">
      <el-skeleton :rows="10" animated />
    </div>

    <div v-else-if="hasError" class="chart-error">
      <el-icon class="error-icon"><WarningFilled /></el-icon>
      <span class="error-text">{{ errorMessage }}</span>
      <el-button type="primary" size="small" @click="loadData">重新加载</el-button>
    </div>

    <div
      v-else
      ref="chartRef"
      class="kline-chart"
      :style="{ height: chartHeight }"
    ></div>

    <div class="chart-controls" v-if="showControls">
      <div class="timeframe-selector">
        <el-radio-group v-model="currentTimeframe" size="small" @change="onTimeframeChange">
          <el-radio-button label="1m">1 分钟</el-radio-button>
          <el-radio-button label="5m">5 分钟</el-radio-button>
          <el-radio-button label="15m">15 分钟</el-radio-button>
          <el-radio-button label="1h">1 小时</el-radio-button>
          <el-radio-button label="4h">4 小时</el-radio-button>
          <el-radio-button label="1d">1 天</el-radio-button>
          <el-radio-button label="1w">1 周</el-radio-button>
        </el-radio-group>
      </div>

      <div class="chart-actions">
        <el-button
          :icon="Refresh"
          circle
          size="small"
          @click="loadData"
          :loading="loading"
        />
        <el-button
          :icon="FullScreen"
          circle
          size="small"
          @click="toggleFullscreen"
        />
        <el-dropdown @command="handleDownload" trigger="click">
          <el-button :icon="Download" circle size="small" />
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="png">导出 PNG</el-dropdown-item>
              <el-dropdown-item command="jpg">导出 JPG</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import {
  WarningFilled,
  Refresh,
  FullScreen,
  Download
} from '@element-plus/icons-vue'

const props = defineProps({
  symbol: {
    type: String,
    required: true,
    default: 'BTCUSDT'
  },
  timeframe: {
    type: String,
    default: '1h'
  },
  containerHeight: {
    type: String,
    default: '500px'
  },
  chartHeight: {
    type: String,
    default: '100%'
  },
  showControls: {
    type: Boolean,
    default: true
  },
  showVolume: {
    type: Boolean,
    default: true
  },
  apiEndpoint: {
    type: String,
    default: '/api/kline'
  },
  theme: {
    type: String,
    default: 'light'
  },
  initialData: {
    type: Array,
    default: null
  }
})

const emit = defineEmits(['dataLoaded', 'error', 'timeframeChange'])

const chartRef = ref(null)
const loading = ref(false)
const hasError = ref(false)
const errorMessage = ref('')
const currentTimeframe = ref(props.timeframe)
let chartInstance = null
let resizeObserver = null

const klineData = reactive({
  dates: [],
  open: [],
  close: [],
  low: [],
  high: [],
  volume: []
})

const upColor = '#00da3c'
const downColor = '#ec0000'

const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value, props.theme)

  const option = {
    backgroundColor: props.theme === 'dark' ? '#1e1e1e' : '#ffffff',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      borderWidth: 1,
      borderColor: '#ccc',
      padding: 10,
      textStyle: {
        color: '#000'
      },
      position: (pos, params, el, elRect, size) => {
        const obj = {
          top: 10,
          left: pos[0] + 20
        }
        obj[['left', 'right'][+(pos[0] < size.viewSize[0] / 2)]] = 30
        return obj
      },
      formatter: (params) => {
        const data = params[0]
        const isUp = data.value[1] >= data.value[0]
        const color = isUp ? upColor : downColor
        return `
          <div style="padding: 5px;">
            <div><strong>时间:</strong> ${data.name}</div>
            <div><strong>开盘:</strong> <span style="color: ${color}">${data.value[0]}</span></div>
            <div><strong>收盘:</strong> <span style="color: ${color}">${data.value[1]}</span></div>
            <div><strong>最低:</strong> <span style="color: ${color}">${data.value[2]}</span></div>
            <div><strong>最高:</strong> <span style="color: ${color}">${data.value[3]}</span></div>
            ${props.showVolume ? `<div><strong>成交量:</strong> ${data.value[4]}</div>` : ''}
          </div>
        `
      }
    },
    axisPointer: {
      link: { xAxisIndex: 'all' },
      label: {
        backgroundColor: '#777'
      }
    },
    grid: [
      {
        left: '10%',
        right: '8%',
        height: props.showVolume ? '60%' : '80%',
        top: '10%'
      },
      {
        left: '10%',
        right: '8%',
        top: '75%',
        height: '15%'
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: klineData.dates,
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        splitNumber: 20,
        axisLabel: {
          color: props.theme === 'dark' ? '#999' : '#666'
        },
        min: 'dataMin',
        max: 'dataMax'
      },
      {
        type: 'category',
        gridIndex: 1,
        data: klineData.dates,
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        min: 'dataMin',
        max: 'dataMax'
      }
    ],
    yAxis: [
      {
        scale: true,
        splitArea: {
          show: true,
          areaStyle: {
            color: props.theme === 'dark' ? ['#2a2a2a', '#333'] : ['#f5f5f5', '#fafafa']
          }
        },
        axisLabel: {
          color: props.theme === 'dark' ? '#999' : '#666',
          formatter: (value) => value.toFixed(2)
        }
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100,
        minValueSpan: 10
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        bottom: 0,
        start: 50,
        end: 100,
        height: 20,
        borderColor: props.theme === 'dark' ? '#555' : '#ddd',
        backgroundColor: props.theme === 'dark' ? '#333' : '#eee',
        dataBackground: {
          lineStyle: {
            color: props.theme === 'dark' ? '#666' : '#aaa'
          },
          areaStyle: {
            color: props.theme === 'dark' ? '#444' : '#ccc'
          }
        },
        selectedDataBackground: {
          lineStyle: {
            color: '#409EFF'
          },
          areaStyle: {
            color: '#409EFF'
          }
        },
        handleStyle: {
          color: '#409EFF'
        }
      }
    ],
    series: [
      {
        name: 'K 线',
        type: 'candlestick',
        data: [],
        itemStyle: {
          color: upColor,
          color0: downColor,
          borderColor: upColor,
          borderColor0: downColor
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }

  if (props.showVolume) {
    option.series.push({
      name: 'Volume',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: [],
      itemStyle: {
        color: (params) => {
          const dataIndex = params.dataIndex
          const klineData = klineData.close[dataIndex]
          const openData = klineData.open[dataIndex]
          return klineData >= openData ? upColor : downColor
        }
      }
    })
  }

  chartInstance.setOption(option)
}

const processData = (rawData) => {
  klineData.dates = []
  klineData.open = []
  klineData.close = []
  klineData.low = []
  klineData.high = []
  klineData.volume = []

  rawData.forEach((item) => {
    const [timestamp, open, high, low, close, volume] = item
    const date = new Date(timestamp)
    const dateStr = `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`

    klineData.dates.push(dateStr)
    klineData.open.push(open)
    klineData.close.push(close)
    klineData.low.push(low)
    klineData.high.push(high)
    klineData.volume.push(Math.round(volume))
  })
}

const updateChartData = () => {
  if (!chartInstance) return

  const klineSeriesData = klineData.dates.map((date, index) => [
    klineData.open[index],
    klineData.close[index],
    klineData.low[index],
    klineData.high[index]
  ])

  const volumes = klineData.volume.map((vol, index) => [
    index,
    vol,
    klineData.open[index],
    klineData.close[index]
  ])

  chartInstance.setOption({
    xAxis: [
      { data: klineData.dates },
      { data: klineData.dates }
    ],
    series: [
      {
        name: 'K 线',
        data: klineSeriesData
      },
      ...(props.showVolume ? [{
        name: 'Volume',
        data: volumes
      }] : [])
    ]
  })
}

const loadData = async () => {
  loading.value = true
  hasError.value = false

  try {
    if (props.initialData) {
      processData(props.initialData)
      updateChartData()
      emit('dataLoaded', props.initialData)
    } else if (props.apiEndpoint) {
      const response = await fetch(`http://localhost:8000${props.apiEndpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          symbol: props.symbol,
          timeframe: currentTimeframe.value
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      const klineData = data.data || data.kline || data

      processData(klineData)
      updateChartData()
      emit('dataLoaded', klineData)
    }
  } catch (error) {
    hasError.value = true
    errorMessage.value = error.message || '数据加载失败'
    emit('error', error)
  } finally {
    loading.value = false
  }
}

const onTimeframeChange = (value) => {
  emit('timeframeChange', value)
  loadData()
}

const toggleFullscreen = () => {
  if (!chartRef.value) return

  if (!document.fullscreenElement) {
    chartRef.value.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}

const handleDownload = (command) => {
  if (!chartInstance) return

  const url = chartInstance.getDataURL({
    type: command,
    pixelRatio: 2,
    backgroundColor: props.theme === 'dark' ? '#1e1e1e' : '#ffffff'
  })

  const link = document.createElement('a')
  link.download = `${props.symbol}_${currentTimeframe.value}_kline.${command}`
  link.href = url
  link.click()
}

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

watch(
  () => props.theme,
  () => {
    initChart()
    updateChartData()
  }
)

onMounted(async () => {
  await nextTick()
  initChart()
  loadData()

  resizeObserver = new ResizeObserver(handleResize)
  if (chartRef.value) {
    resizeObserver.observe(chartRef.value)
  }
})

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  if (chartInstance) {
    chartInstance.dispose()
  }
})

defineExpose({
  refresh: loadData,
  getChartInstance: () => chartInstance,
  getData: () => ({ ...klineData })
})
</script>

<style lang="scss" scoped>
.kline-chart-container {
  position: relative;
  width: 100%;
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.chart-loading,
.chart-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 500px;
  gap: 16px;
}

.chart-error {
  color: #F56C6C;
}

.error-icon {
  font-size: 48px;
}

.error-text {
  font-size: 16px;
}

.kline-chart {
  width: 100%;
}

.chart-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-top: 1px solid #EBEEF5;
  background: #fafafa;
  flex-wrap: wrap;
  gap: 12px;
}

.timeframe-selector {
  :deep(.el-radio-group) {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
}

.chart-actions {
  display: flex;
  gap: 8px;
}

:deep(.el-radio-button__inner) {
  padding: 8px 12px;
  font-size: 12px;
}
</style>
