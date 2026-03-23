<template>
  <div class="position-table">
    <div class="table-header">
      <div class="header-title">
        <el-icon><Wallet /></el-icon>
        <span>{{ title }}</span>
      </div>

      <div class="header-actions">
        <el-input
          v-model="searchText"
          placeholder="搜索币种..."
          prefix-icon="Search"
          clearable
          size="small"
          style="width: 200px"
        />

        <el-dropdown @command="handleFilter" trigger="click">
          <el-button size="small">
            <el-icon><Filter /></el-icon>
            筛选
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="all">全部</el-dropdown-item>
              <el-dropdown-item command="profit">盈利</el-dropdown-item>
              <el-dropdown-item command="loss">亏损</el-dropdown-item>
              <el-dropdown-item command="long">多头</el-dropdown-item>
              <el-dropdown-item command="short">空头</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-button
          :icon="Refresh"
          circle
          size="small"
          @click="loadData"
          :loading="loading"
        />

        <el-button
          :icon="Download"
          circle
          size="small"
          @click="exportData"
        />
      </div>
    </div>

    <div class="table-summary" v-if="showSummary && filteredData.length > 0">
      <el-descriptions :column="4" size="small" border>
        <el-descriptions-item label="总持仓">
          <span class="summary-value">{{ totalPositions }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="总价值">
          <span class="summary-value">{{ totalValue }} USDT</span>
        </el-descriptions-item>
        <el-descriptions-item label="总盈亏">
          <span :class="['summary-value', totalPnLClass]">
            {{ totalPnL }} USDT ({{ totalPnLPercent }}%)
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="多头/空头">
          <span class="summary-value">{{ longCount }} / {{ shortCount }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <el-table
      v-loading="loading"
      :data="filteredData"
      style="width: 100%"
      :default-sort="{ prop: 'unrealizedPnl', order: 'descending' }"
      @sort-change="handleSortChange"
      @selection-change="handleSelectionChange"
      :row-class-name="rowClassName"
      size="default"
    >
      <el-table-column type="selection" width="55" v-if="selectable" />

      <el-table-column
        prop="symbol"
        label="交易对"
        width="120"
        sortable="custom"
        :filters="symbolFilters"
        :filter-method="filterSymbol"
      >
        <template #default="{ row }">
          <div class="symbol-cell">
            <el-icon :size="18"><component :is="getAssetIcon(row.baseAsset)" /></el-icon>
            <span class="symbol-name">{{ row.symbol }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column
        prop="side"
        label="方向"
        width="80"
        sortable="custom"
      >
        <template #default="{ row }">
          <el-tag :type="row.side === 'LONG' ? 'success' : 'danger'" size="small">
            {{ row.side === 'LONG' ? '多' : '空' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column
        prop="size"
        label="持仓量"
        width="120"
        sortable="custom"
        align="right"
      >
        <template #default="{ row }">
          <span class="amount-text ">{{ row.size }}</span>
          <span class="asset-name">{{ row.baseAsset }}</span>
        </template>
      </el-table-column>

      <el-table-column
        prop="entryPrice"
        label="开仓均价"
        width="120"
        sortable="custom"
        align="right"
      >
        <template #default="{ row }">
          {{ formatPrice(row.entryPrice) }}
        </template>
      </el-table-column>

      <el-table-column
        prop="markPrice"
        label="标记价格"
        width="120"
        sortable="custom"
        align="right"
      >
        <template #default="{ row }">
          {{ formatPrice(row.markPrice) }}
        </template>
      </el-table-column>

      <el-table-column
        prop="leverage"
        label="杠杆"
        width="70"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          <el-tag effect="plain" size="small">{{ row.leverage }}x</el-tag>
        </template>
      </el-table-column>

      <el-table-column
        prop="margin"
        label="保证金"
        width="120"
        sortable="custom"
        align="right"
      >
        <template #default="{ row }">
          {{ formatNumber(row.margin) }}
        </template>
      </el-table-column>

      <el-table-column
        prop="unrealizedPnl"
        label="未实现盈亏"
        width="140"
        sortable="custom"
        align="right"
      >
        <template #default="{ row }">
          <div :class="['pnl-value', row.unrealizedPnl >= 0 ? 'pnl-profit' : 'pnl-loss']">
            {{ row.unrealizedPnl >= 0 ? '+' : '' }}{{ formatNumber(row.unrealizedPnl) }}
          </div>
          <div :class="['pnl-percent', row.unrealizedPnlPercent >= 0 ? 'pnl-profit' : 'pnl-loss']">
            {{ row.unrealizedPnlPercent >= 0 ? '+' : '' }}{{ row.unrealizedPnlPercent.toFixed(2) }}%
          </div>
        </template>
      </el-table-column>

      <el-table-column
        prop="liquidationPrice"
        label="强平价"
        width="120"
        sortable="custom"
        align="right"
        v-if="showLiquidation"
      >
        <template #default="{ row }">
          <span :class="{ 'liquidation-warning': isLiquidationClose(row) }">
            {{ formatPrice(row.liquidationPrice) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column
        label="操作"
        width="180"
        fixed="right"
        v-if="showActions"
      >
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            @click="handleAddPosition(row)"
          >
            加仓
          </el-button>
          <el-button
            type="danger"
            size="small"
            @click="handleClosePosition(row)"
          >
            平仓
          </el-button>
          <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, row)">
            <el-button size="small">
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="history">历史</el-dropdown-item>
                <el-dropdown-item command="divider" divided disabled>───</el-dropdown-item>
                <el-dropdown-item command="close-all" divided>全部平仓</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <div class="table-footer">
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>

      <div class="selected-info" v-if="selectedRows.length > 0">
        已选择 {{ selectedRows.length }} 个持仓
        <el-button type="danger" size="small" @click="handleBatchClose">批量平仓</el-button>
      </div>
    </div>

    <el-dialog
      v-model="closeDialogVisible"
      title="确认平仓"
      width="400px"
      :close-on-click-modal="false"
    >
      <div class="close-confirm-content">
        <p>您确定要平仓 <strong>{{ currentClosePosition?.symbol }}</strong> 吗？</p>
        <p>持仓量：<strong>{{ currentClosePosition?.size }} {{ currentClosePosition?.baseAsset }}</strong></p>
        <p :class="currentClosePosition?.unrealizedPnl >= 0 ? 'pnl-profit' : 'pnl-loss'">
          未实现盈亏：{{ currentClosePosition?.unrealizedPnl >= 0 ? '+' : '' }}{{ formatNumber(currentClosePosition?.unrealizedPnl) }} USDT
        </p>
      </div>
      <template #footer>
        <el-button @click="closeDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmClosePosition" :loading="closing">确认平仓</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import {
  Wallet,
  Search,
  Filter,
  Refresh,
  Download,
  MoreFilled,
  Bitcoin,
  DataAnalysis
} from '@element-plus/icons-vue'

const props = defineProps({
  title: {
    type: String,
    default: '持仓明细'
  },
  showSummary: {
    type: Boolean,
    default: true
  },
  showLiquidation: {
    type: Boolean,
    default: true
  },
  showActions: {
    type: Boolean,
    default: true
  },
  selectable: {
    type: Boolean,
    default: true
  },
  apiEndpoint: {
    type: String,
    default: '/api/positions'
  },
  initialData: {
    type: Array,
    default: null
  }
})

const emit = defineEmits(['positionClose', 'positionAdd', 'batchClose', 'dataLoaded'])

const loading = ref(false)
const searchText = ref('')
const filterType = ref('all')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const sortField = ref('unrealizedPnl')
const sortOrder = ref('descending')
const selectedRows = ref([])
const closeDialogVisible = ref(false)
const currentClosePosition = ref(null)
const closing = ref(false)

const positionsData = ref([])

const filteredData = computed(() => {
  let data = [...positionsData.value]

  if (searchText.value) {
    data = data.filter((item) =>
      item.symbol.toLowerCase().includes(searchText.value.toLowerCase())
    )
  }

  if (filterType.value !== 'all') {
    switch (filterType.value) {
      case 'profit':
        data = data.filter((item) => item.unrealizedPnl > 0)
        break
      case 'loss':
        data = data.filter((item) => item.unrealizedPnl < 0)
        break
      case 'long':
        data = data.filter((item) => item.side === 'LONG')
        break
      case 'short':
        data = data.filter((item) => item.side === 'SHORT')
        break
    }
  }

  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  total.value = data.length

  return data.slice(start, end)
})

const totalPositions = computed(() => positionsData.value.length)

const totalValue = computed(() => {
  return positionsData.value.reduce((sum, item) => sum + item.margin, 0).toFixed(2)
})

const totalPnL = computed(() => {
  return positionsData.value.reduce((sum, item) => sum + item.unrealizedPnl, 0).toFixed(2)
})

const totalPnLPercent = computed(() => {
  const totalMargin = positionsData.value.reduce((sum, item) => sum + item.margin, 0)
  if (totalMargin === 0) return 0
  return ((totalPnL.value / totalMargin) * 100).toFixed(2)
})

const totalPnLClass = computed(() => {
  return totalPnL.value >= 0 ? 'pnl-profit' : 'pnl-loss'
})

const longCount = computed(() => {
  return positionsData.value.filter((item) => item.side === 'LONG').length
})

const shortCount = computed(() => {
  return positionsData.value.filter((item) => item.side === 'SHORT').length
})

const symbolFilters = computed(() => {
  const symbols = [...new Set(positionsData.value.map((item) => item.symbol))]
  return symbols.map((symbol) => ({ text: symbol, value: symbol }))
})

const formatPrice = (price) => {
  if (!price) return '0.00'
  return price >= 1000 ? price.toFixed(2) : price.toFixed(4)
}

const formatNumber = (num) => {
  if (!num) return '0.00'
  return num.toFixed(2)
}

const getAssetIcon = (asset) => {
  const iconMap = {
    BTC: Bitcoin,
    ETH: DataAnalysis
  }
  return iconMap[asset] || Bitcoin
}

const isLiquidationClose = (row) => {
  if (!row.liquidationPrice || !row.markPrice) return false
  const diffPercent = Math.abs((row.markPrice - row.liquidationPrice) / row.markPrice) * 100
  return diffPercent < 5
}

const rowClassName = ({ row }) => {
  if (isLiquidationClose(row)) {
    return 'liquidation-warning-row'
  }
  return ''
}

const loadData = async () => {
  loading.value = true

  try {
    if (props.initialData) {
      positionsData.value = props.initialData
      emit('dataLoaded', props.initialData)
    } else {
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
      positionsData.value = data.positions || data
      emit('dataLoaded', positionsData.value)
    }
  } catch (error) {
    console.error('加载持仓数据失败:', error)
    emit('error', error)
  } finally {
    loading.value = false
  }
}

const handleFilter = (command) => {
  filterType.value = command
  currentPage.value = 1
}

const filterSymbol = (value, row) => {
  return row.symbol === value
}

const handleSortChange = ({ prop, order }) => {
  sortField.value = prop
  sortOrder.value = order
}

const handleSelectionChange = (selection) => {
  selectedRows.value = selection
}

const handleAddPosition = (row) => {
  emit('positionAdd', row)
}

const handleClosePosition = (row) => {
  currentClosePosition.value = row
  closeDialogVisible.value = true
}

const confirmClosePosition = async () => {
  if (!currentClosePosition.value) return

  closing.value = true

  try {
    const response = await fetch(`http://localhost:8000/api/order/close`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        symbol: currentClosePosition.value.symbol,
        side: currentClosePosition.value.side === 'LONG' ? 'SELL' : 'BUY'
      })
    })

    if (response.ok) {
      emit('positionClose', currentClosePosition.value)
      loadData()
      closeDialogVisible.value = false
    } else {
      throw new Error('平仓失败')
    }
  } catch (error) {
    console.error('平仓失败:', error)
  } finally {
    closing.value = false
  }
}

const handleCommand = (command, row) => {
  switch (command) {
    case 'edit':
      handleAddPosition(row)
      break
    case 'history':
      console.log('查看历史', row)
      break
    case 'close-all':
      handleClosePosition(row)
      break
  }
}

const handleBatchClose = async () => {
  if (selectedRows.value.length === 0) return

  closing.value = true

  try {
    const response = await fetch(`http://localhost:8000/api/order/batch-close`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        positions: selectedRows.value.map((item) => ({
          symbol: item.symbol,
          side: item.side === 'LONG' ? 'SELL' : 'BUY'
        }))
      })
    })

    if (response.ok) {
      emit('batchClose', selectedRows.value)
      loadData()
      selectedRows.value = []
    }
  } catch (error) {
    console.error('批量平仓失败:', error)
  } finally {
    closing.value = false
  }
}

const handleSizeChange = () => {
  currentPage.value = 1
}

const handleCurrentChange = () => {
  // 分页变化时重新计算
}

const exportData = () => {
  const csvContent = [
    ['交易对', '方向', '持仓量', '开仓价', '标记价', '杠杆', '保证金', '未实现盈亏', '盈亏率'],
    ...positionsData.value.map((item) => [
      item.symbol,
      item.side,
      item.size,
      item.entryPrice,
      item.markPrice,
      item.leverage,
      item.margin,
      item.unrealizedPnl,
      item.unrealizedPnlPercent
    ])
  ]
    .map((row) => row.join(','))
    .join('\n')

  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `positions_${new Date().toISOString().split('T')[0]}.csv`
  link.click()
}

onMounted(() => {
  loadData()
})

defineExpose({
  refresh: loadData,
  getData: () => positionsData.value,
  getSelectedRows: () => selectedRows.value
})
</script>

<style lang="scss" scoped>
.position-table {
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #EBEEF5;
  flex-wrap: wrap;
  gap: 12px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.table-summary {
  padding: 16px 20px;
  background: #fafafa;
  border-bottom: 1px solid #EBEEF5;
}

.summary-value {
  font-weight: 600;
  font-size: 14px;
}

.pnl-profit {
  color: #00da3c;
}

.pnl-loss {
  color: #ec0000;
}

:deep(.el-table) {
  .cell {
    padding: 8px 0;
  }

  th.el-table__cell {
    background: #f5f7fa;
    color: #606266;
    font-weight: 600;
  }
}

.symbol-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.symbol-name {
  font-weight: 500;
}

.amount {
  font-family: 'Roboto Mono', monospace;
}

.asset-name {
  font-size: 12px;
  color: #909399;
  margin-left: 4px;
}

.pnl-value {
  font-weight: 600;
  font-family: 'Roboto Mono', monospace;
}

.pnl-percent {
  font-size: 12px;
  margin-top: 2px;
}

.liquidation-warning {
  color: #E6A23C;
  font-weight: 600;
}

:deep(.liquidation-warning-row) {
  background: rgba(230, 162, 60, 0.1);

  &:hover {
    background: rgba(230, 162, 60, 0.2) !important;
  }
}

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid #EBEEF5;
  flex-wrap: wrap;
  gap: 12px;
}

.pagination-wrapper {
  flex: 1;
}

.selected-info {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #606266;
  font-size: 14px;
}

.close-confirm-content {
  p {
    margin: 12px 0;
    font-size: 14px;
    color: #606266;

    strong {
      color: #303133;
    }
  }
}
</style>
