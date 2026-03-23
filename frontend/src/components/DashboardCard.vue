<template>
  <div class="dashboard-card" :class="{ 'is-loading': loading, 'is-error': hasError }">
    <div class="card-header">
      <div class="card-title">
        <el-icon v-if="icon" class="card-icon" :style="{ color: iconColor }">
          <component :is="icon" />
        </el-icon>
        <span class="title-text">{{ title }}</span>
      </div>
      <div class="card-actions">
        <el-button
          v-if="refreshable"
          :icon="Refresh"
          circle
          size="small"
          @click="handleRefresh"
          :loading="loading"
        />
        <el-tooltip :content="tooltip" placement="top" v-if="tooltip">
          <el-button :icon="QuestionFilled" circle size="small" />
        </el-tooltip>
      </div>
    </div>

    <div class="card-body">
      <div v-if="hasError" class="error-state">
        <el-icon class="error-icon"><WarningFilled /></el-icon>
        <span class="error-text">{{ errorMessage }}</span>
        <el-button type="primary" size="small" @click="handleRefresh">重试</el-button>
      </div>

      <div v-else-if="loading" class="loading-state">
        <el-skeleton :rows="3" animated />
      </div>

      <div v-else class="content-wrapper">
        <slot name="content">
          <div class="default-content">
            <div class="value-display" :style="{ color: valueColor }">
              <span class="value-prefix" v-if="prefix">{{ prefix }}</span>
              <span class="main-value">{{ displayValue }}</span>
              <span class="value-suffix" v-if="suffix">{{ suffix }}</span>
            </div>
            <div v-if="change !== undefined" class="change-display" :class="changeClass">
              <el-icon><component :is="change >= 0 ? 'CaretTop' : 'CaretBottom'" /></el-icon>
              <span>{{ Math.abs(change).toFixed(2) }}%</span>
            </div>
          </div>
        </slot>
      </div>
    </div>

    <div v-if="footerText || $slots.footer" class="card-footer">
      <slot name="footer">
        <span class="footer-text">{{ footerText }}</span>
      </slot>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  Refresh,
  QuestionFilled,
  WarningFilled,
  CaretTop,
  CaretBottom,
  Money,
  TrendCharts,
  Wallet,
  DataAnalysis
} from '@element-plus/icons-vue'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  icon: {
    type: String,
    default: ''
  },
  iconColor: {
    type: String,
    default: '#409EFF'
  },
  value: {
    type: [String, Number],
    default: ''
  },
  prefix: {
    type: String,
    default: ''
  },
  suffix: {
    type: String,
    default: ''
  },
  change: {
    type: Number,
    default: undefined
  },
  footerText: {
    type: String,
    default: ''
  },
  tooltip: {
    type: String,
    default: ''
  },
  refreshable: {
    type: Boolean,
    default: false
  },
  apiEndpoint: {
    type: String,
    default: ''
  },
  autoRefresh: {
    type: Boolean,
    default: false
  },
  refreshInterval: {
    type: Number,
    default: 30000
  },
  valueFormatter: {
    type: Function,
    default: null
  }
})

const emit = defineEmits(['refresh', 'update:value', 'error'])

const loading = ref(false)
const hasError = ref(false)
const errorMessage = ref('')
const internalValue = ref(props.value)
let refreshTimer = null

const displayValue = computed(() => {
  if (props.valueFormatter && internalValue.value !== '') {
    return props.valueFormatter(internalValue.value)
  }
  return internalValue.value
})

const valueColor = computed(() => {
  if (props.change === undefined) return '#303133'
  return props.change >= 0 ? '#67C23A' : '#F56C6C'
})

const changeClass = computed(() => {
  return {
    'change-up': props.change >= 0,
    'change-down': props.change < 0
  }
})

const fetchData = async () => {
  if (!props.apiEndpoint) return

  loading.value = true
  hasError.value = false

  try {
    const response = await fetch(`http://localhost:8000${props.apiEndpoint}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    internalValue.value = data.value !== undefined ? data.value : data
    emit('update:value', internalValue.value)
  } catch (error) {
    hasError.value = true
    errorMessage.value = error.message || '数据加载失败'
    emit('error', error)
  } finally {
    loading.value = false
  }
}

const handleRefresh = () => {
  emit('refresh')
  fetchData()
}

const setupAutoRefresh = () => {
  if (props.autoRefresh && props.apiEndpoint) {
    if (refreshTimer) {
      clearInterval(refreshTimer)
    }
    refreshTimer = setInterval(() => {
      fetchData()
    }, props.refreshInterval)
  }
}

watch(
  () => props.value,
  (newValue) => {
    internalValue.value = newValue
  }
)

onMounted(() => {
  if (props.apiEndpoint) {
    fetchData()
  }
  setupAutoRefresh()
})

defineExpose({
  refresh: handleRefresh,
  getValue: () => internalValue.value
})
</script>

<style lang="scss" scoped>
.dashboard-card {
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: 20px;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;

  &:hover {
    box-shadow: 0 4px 16px 0 rgba(0, 0, 0, 0.15);
    transform: translateY(-2px);
  }

  &.is-loading {
    opacity: 0.7;
    pointer-events: none;
  }

  &.is-error {
    border: 1px solid #F56C6C;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #EBEEF5;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-icon {
  font-size: 20px;
}

.title-text {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.card-body {
  min-height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #F56C6C;
}

.error-icon {
  font-size: 32px;
}

.error-text {
  font-size: 14px;
}

.loading-state {
  width: 100%;
}

.content-wrapper {
  width: 100%;
}

.default-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.value-display {
  font-size: 28px;
  font-weight: bold;
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.value-prefix,
.value-suffix {
  font-size: 14px;
  color: #909399;
}

.change-display {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;

  &.change-up {
    color: #67C23A;
  }

  &.change-down {
    color: #F56C6C;
  }
}

.card-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #EBEEF5;
  text-align: center;
}

.footer-text {
  font-size: 12px;
  color: #909399;
}
</style>
