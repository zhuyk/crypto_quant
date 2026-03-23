<template>
  <div class="order-form">
    <div class="form-header">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="买入" name="buy">
          <template #label>
            <span class="tab-label buy-label">
              <el-icon><Top /></el-icon>
              买入
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane label="卖出" name="sell">
          <template #label>
            <span class="tab-label sell-label">
              <el-icon><Bottom /></el-icon>
              卖出
            </span>
          </template>
        </el-tab-pane>
      </el-tabs>
    </div>

    <div class="form-body">
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="70px"
        size="default"
      >
        <el-form-item label="订单类型">
          <el-radio-group v-model="formData.orderType" size="small">
            <el-radio-button label="limit">限价</el-radio-button>
            <el-radio-button label="market">市价</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="价格" v-if="formData.orderType === 'limit'">
          <el-input-number
            v-model="formData.price"
            :min="0"
            :precision="pricePrecision"
            :step="priceStep"
            :controls="true"
            placeholder="请输入价格"
            style="width: 100%"
            @change="calculateTotal"
          >
            <template #suffix>
              <span class="input-suffix">{{ quoteAsset }}</span>
            </template>
          </el-input-number>
        </el-form-item>

        <el-form-item label="数量">
          <el-input-number
            v-model="formData.amount"
            :min="0"
            :precision="amountPrecision"
            :step="amountStep"
            :controls="true"
            placeholder="请输入数量"
            style="width: 100%"
            @change="calculateTotal"
          >
            <template #suffix>
              <span class="input-suffix">{{ baseAsset }}</span>
            </template>
          </el-input-number>
        </el-form-item>

        <el-form-item label="成交额" v-if="formData.orderType === 'limit'">
          <el-input
            v-model="formData.total"
            readonly
            :disabled="true"
          >
            <template #suffix>
              <span class="input-suffix">{{ quoteAsset }}</span>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="止盈止损" v-if="showStopLoss">
          <el-checkbox-group v-model="formData.stopLossTypes">
            <el-checkbox label="takeProfit">止盈</el-checkbox>
            <el-checkbox label="stopLoss">止损</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="止盈价" v-if="formData.stopLossTypes.includes('takeProfit')">
          <el-input-number
            v-model="formData.takeProfitPrice"
            :min="0"
            :precision="pricePrecision"
            placeholder="止盈价格"
            style="width: 100%"
          >
            <template #suffix>
              <span class="input-suffix">{{ quoteAsset }}</span>
            </template>
          </el-input-number>
        </el-form-item>

        <el-form-item label="止损价" v-if="formData.stopLossTypes.includes('stopLoss')">
          <el-input-number
            v-model="formData.stopLossPrice"
            :min="0"
            :precision="pricePrecision"
            placeholder="止损价格"
            style="width: 100%"
          >
            <template #suffix>
              <span class="input-suffix">{{ quoteAsset }}</span>
            </template>
          </el-input-number>
        </el-form-item>

        <el-form-item label="杠杆倍数" v-if="isFutures">
          <el-slider
            v-model="formData.leverage"
            :min="1"
            :max="maxLeverage"
            :step="1"
            :marks="leverageMarks"
            :format-tooltip="(val) => val + 'x'"
          />
        </el-form-item>

        <div class="balance-info">
          <div class="balance-item">
            <span class="balance-label">可用余额:</span>
            <span class="balance-value">{{ availableBalance }} {{ activeTab === 'buy' ? quoteAsset : baseAsset }}</span>
          </div>
          <div class="balance-item">
            <span class="balance-label">最新价:</span>
            <span class="balance-value" :class="priceChangeClass">{{ latestPrice }} {{ quoteAsset }}</span>
          </div>
        </div>

        <div class="percentage-selector" v-if="formData.orderType === 'market' || formData.orderType === 'limit'">
          <el-button
            v-for="percent in [25, 50, 75, 100]"
            :key="percent"
            size="small"
            :type="selectedPercent === percent ? 'primary' : ''"
            plain
            @click="setPercentage(percent)"
          >
            {{ percent }}%
          </el-button>
        </div>

        <el-form-item>
          <el-button
            type="primary"
            :class="activeTab"
            size="large"
            style="width: 100%"
            :loading="submitting"
            @click="submitOrder"
          >
            {{ activeTab === 'buy' ? '买入' : '卖出' }} {{ baseAsset }}
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="order-info" v-if="lastOrder">
      <el-alert
        :title="lastOrder.success ? '订单提交成功' : '订单提交失败'"
        :type="lastOrder.success ? 'success' : 'error'"
        :closable="true"
        show-icon
        @close="lastOrder = null"
      >
        <template #default>
          <div class="order-details">
            <p>订单号：{{ lastOrder.orderId }}</p>
            <p>{{ activeTab === 'buy' ? '买入' : '卖出' }} {{ lastOrder.amount }} {{ baseAsset }}</p>
            <p v-if="lastOrder.price">价格：{{ lastOrder.price }} {{ quoteAsset }}</p>
          </div>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { Top, Bottom } from '@element-plus/icons-vue'

const props = defineProps({
  symbol: {
    type: String,
    required: true,
    default: 'BTCUSDT'
  },
  baseAsset: {
    type: String,
    default: 'BTC'
  },
  quoteAsset: {
    type: String,
    default: 'USDT'
  },
  pricePrecision: {
    type: Number,
    default: 2
  },
  amountPrecision: {
    type: Number,
    default: 6
  },
  priceStep: {
    type: Number,
    default: 0.01
  },
  amountStep: {
    type: Number,
    default: 0.001
  },
  isFutures: {
    type: Boolean,
    default: false
  },
  maxLeverage: {
    type: Number,
    default: 20
  },
  showStopLoss: {
    type: Boolean,
    default: true
  },
  apiEndpoint: {
    type: String,
    default: '/api/order'
  },
  initialBalance: {
    type: Number,
    default: 10000
  }
})

const emit = defineEmits(['orderSubmitted', 'balanceUpdate'])

const formRef = ref(null)
const activeTab = ref('buy')
const submitting = ref(false)
const selectedPercent = ref(null)
const availableBalance = ref(props.initialBalance)
const latestPrice = ref(0)
const lastOrder = ref(null)

const formData = reactive({
  orderType: 'limit',
  price: 0,
  amount: 0,
  total: 0,
  stopLossTypes: [],
  takeProfitPrice: 0,
  stopLossPrice: 0,
  leverage: 1
})

const formRules = computed(() => ({
  amount: [
    { required: true, message: '请输入数量', trigger: 'blur' },
    { type: 'number', min: 0, message: '数量必须大于 0', trigger: 'blur' }
  ],
  price: formData.orderType === 'limit' ? [
    { required: true, message: '请输入价格', trigger: 'blur' },
    { type: 'number', min: 0, message: '价格必须大于 0', trigger: 'blur' }
  ] : []
}))

const leverageMarks = computed(() => {
  const marks = {}
  for (let i = 1; i <= props.maxLeverage; i += 5) {
    marks[i] = `${i}x`
  }
  marks[props.maxLeverage] = `${props.maxLeverage}x`
  return marks
})

const priceChangeClass = computed(() => {
  return {
    'price-up': latestPrice.value > 0,
    'price-down': latestPrice.value < 0
  }
})

const calculateTotal = () => {
  if (formData.orderType === 'limit' && formData.price && formData.amount) {
    formData.total = (formData.price * formData.amount).toFixed(2)
  }
}

const setPercentage = (percent) => {
  selectedPercent.value = percent === selectedPercent.value ? null : percent

  if (selectedPercent.value) {
    if (activeTab.value === 'buy') {
      const usableAmount = (availableBalance.value * (percent / 100)) / (formData.price || latestPrice.value || 1)
      formData.amount = parseFloat(usableAmount.toFixed(props.amountPrecision))
    } else {
      formData.amount = parseFloat((formData.amount * (percent / 100)).toFixed(props.amountPrecision))
    }
    calculateTotal()
  }
}

const onTabChange = (tab) => {
  selectedPercent.value = null
  formData.amount = 0
  formData.total = 0
}

const fetchBalance = async () => {
  try {
    const response = await fetch(`http://localhost:8000/api/balance`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (response.ok) {
      const data = await response.json()
      availableBalance.value = activeTab.value === 'buy'
        ? (data.quoteBalance || props.initialBalance)
        : (data.baseBalance || 0)
    }
  } catch (error) {
    console.error('获取余额失败:', error)
  }
}

const fetchLatestPrice = async () => {
  try {
    const response = await fetch(`http://localhost:8000/api/price?symbol=${props.symbol}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (response.ok) {
      const data = await response.json()
      latestPrice.value = data.price || 0

      if (formData.orderType === 'limit' && !formData.price) {
        formData.price = parseFloat(latestPrice.value.toFixed(props.pricePrecision))
      }
    }
  } catch (error) {
    console.error('获取价格失败:', error)
  }
}

const submitOrder = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true

    try {
      const orderData = {
        symbol: props.symbol,
        side: activeTab.value,
        type: formData.orderType,
        amount: formData.amount,
        price: formData.orderType === 'limit' ? formData.price : undefined,
        leverage: props.isFutures ? formData.leverage : undefined,
        takeProfitPrice: formData.stopLossTypes.includes('takeProfit') ? formData.takeProfitPrice : undefined,
        stopLossPrice: formData.stopLossTypes.includes('stopLoss') ? formData.stopLossPrice : undefined
      }

      const response = await fetch(`http://localhost:8000${props.apiEndpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(orderData)
      })

      const result = await response.json()

      if (response.ok) {
        lastOrder.value = {
          success: true,
          orderId: result.orderId,
          amount: formData.amount,
          price: formData.price
        }

        emit('orderSubmitted', {
          success: true,
          data: result
        })

        formData.amount = 0
        formData.total = 0
        selectedPercent.value = null
        fetchBalance()
      } else {
        throw new Error(result.message || '订单提交失败')
      }
    } catch (error) {
      lastOrder.value = {
        success: false,
        message: error.message
      }

      emit('orderSubmitted', {
        success: false,
        error: error.message
      })
    } finally {
      submitting.value = false
    }
  })
}

watch(
  () => activeTab.value,
  () => {
    fetchBalance()
  }
)

onMounted(() => {
  fetchBalance()
  fetchLatestPrice()

  setInterval(() => {
    fetchLatestPrice()
  }, 5000)
})

defineExpose({
  submitOrder,
  resetForm: () => {
    formData.amount = 0
    formData.total = 0
    formData.price = latestPrice.value
    selectedPercent.value = null
    formRef.value?.clearValidate()
  }
})
</script>

<style lang="scss" scoped>
.order-form {
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.form-header {
  border-bottom: 1px solid #EBEEF5;

  :deep(.el-tabs__header) {
    margin: 0;
    padding: 0 16px;
  }

  :deep(.el-tabs__item) {
    padding: 16px 24px;
    font-size: 16px;
    font-weight: 600;
  }
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 6px;

  &.buy-label {
    color: #00da3c;
  }

  &.sell-label {
    color: #ec0000;
  }
}

.form-body {
  padding: 20px;
}

.input-suffix {
  font-size: 12px;
  color: #909399;
  padding: 0 8px;
}

.balance-info {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 16px;
}

.balance-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;

  &:last-child {
    margin-bottom: 0;
  }
}

.balance-label {
  font-size: 13px;
  color: #909399;
}

.balance-value {
  font-size: 14px;
  font-weight: 600;
  color: #303133;

  &.price-up {
    color: #00da3c;
  }

  &.price-down {
    color: #ec0000;
  }
}

.percentage-selector {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

:deep(.el-button.buy) {
  background: linear-gradient(135deg, #00da3c 0%, #00b832 100%);
  border: none;

  &:hover {
    background: linear-gradient(135deg, #00f044 0%, #00c937 100%);
  }
}

:deep(.el-button.sell) {
  background: linear-gradient(135deg, #ec0000 0%, #c90000 100%);
  border: none;

  &:hover {
    background: linear-gradient(135deg, #ff0000 0%, #e00000 100%);
  }
}

.order-info {
  padding: 0 20px 20px;
}

.order-details {
  p {
    margin: 4px 0;
    font-size: 13px;
    color: #606266;
  }
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #606266;
}

:deep(.el-slider__marks-text) {
  font-size: 10px;
  color: #909399;
}
</style>
