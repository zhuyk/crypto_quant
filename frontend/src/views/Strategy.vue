<template>
  <div class="strategy-page">
    <div class="page-header">
      <h2>🤖 策略管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon> 新建策略
      </el-button>
    </div>

    <!-- 策略列表 -->
    <el-card shadow="hover" class="strategies-card">
      <template #header>
        <div class="card-header">
          <span>策略列表</span>
          <el-input
            v-model="searchText"
            placeholder="搜索策略..."
            prefix-icon="Search"
            style="width: 200px"
            clearable
          />
        </div>
      </template>
      
      <el-table 
        :data="filteredStrategies" 
        stripe 
        style="width: 100%"
        @row-click="viewStrategyDetail"
      >
        <el-table-column prop="name" label="策略名称" width="150">
          <template #default="{ row }">
            <div class="strategy-name">
              <el-icon><Setting /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="category" label="类别" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getCategoryType(row.category)">
              {{ row.category }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="description" label="描述" min-width="200" />
        
        <el-table-column prop="author" label="作者" width="100" />
        
        <el-table-column label="参数" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ Object.keys(row.params || {}).length }} 个</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              :loading="row.loading"
              @change="toggleStrategy(row)"
              @click.stop
              active-text="运行"
              inactive-text="停止"
            />
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button 
              type="primary" 
              size="small" 
              @click.stop="viewStrategyDetail(row)"
            >
              详情
            </el-button>
            <el-button 
              type="success" 
              size="small" 
              @click.stop="runBacktest(row)"
            >
              回测
            </el-button>
            <el-button 
              type="warning" 
              size="small" 
              @click.stop="editStrategy(row)"
            >
              编辑
            </el-button>
            <el-dropdown @command="(cmd) => handleCommand(cmd, row)" trigger="click">
              <el-button size="small">
                更多 <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="duplicate">复制策略</el-dropdown-item>
                  <el-dropdown-item command="export">导出配置</el-dropdown-item>
                  <el-dropdown-item command="delete" divided style="color: #f56c6c">
                    删除策略
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 策略详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      title="策略详情"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-descriptions :column="2" border v-if="selectedStrategy">
        <el-descriptions-item label="策略名称">{{ selectedStrategy.name }}</el-descriptions-item>
        <el-descriptions-item label="类别">
          <el-tag size="small" :type="getCategoryType(selectedStrategy.category)">
            {{ selectedStrategy.category }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="作者">{{ selectedStrategy.author }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ selectedStrategy.version || '1.0.0' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ selectedStrategy.description }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ selectedStrategy.created_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ selectedStrategy.updated_at || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider>策略参数</el-divider>
      
      <el-table :data="paramList" style="width: 100%" size="small">
        <el-table-column prop="name" label="参数名" width="150" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="default" label="默认值" width="120" />
        <el-table-column prop="min" label="最小值" width="100" />
        <el-table-column prop="max" label="最大值" width="100" />
        <el-table-column prop="description" label="说明" />
      </el-table>
      
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
        <el-button type="primary" @click="runBacktest(selectedStrategy)">
          运行回测
        </el-button>
      </template>
    </el-dialog>

    <!-- 新建策略对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建策略"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="newStrategy" label-width="100px">
        <el-form-item label="策略名称" required>
          <el-input v-model="newStrategy.name" placeholder="例如：my_ma_strategy" />
        </el-form-item>
        
        <el-form-item label="策略类别" required>
          <el-select v-model="newStrategy.category" placeholder="请选择类别" style="width: 100%">
            <el-option label="趋势跟踪" value="趋势" />
            <el-option label="均值回归" value="均值回归" />
            <el-option label="突破策略" value="突破" />
            <el-option label="套利策略" value="套利" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="策略描述" required>
          <el-input
            v-model="newStrategy.description"
            type="textarea"
            :rows="3"
            placeholder="简要描述策略逻辑"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createStrategy">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

// 搜索文本
const searchText = ref('')

// 对话框状态
const showDetailDialog = ref(false)
const showCreateDialog = ref(false)

// 选中的策略
const selectedStrategy = ref(null)

// 新建策略表单
const newStrategy = ref({
  name: '',
  category: '趋势',
  description: '',
})

// 策略列表
const strategies = ref([
  {
    name: 'ma_cross',
    category: '趋势',
    description: '双均线交叉策略，快线上穿慢线做多，下穿做空',
    author: 'System',
    is_active: false,
    loading: false,
    params: { fast_period: 10, slow_period: 30 },
    created_at: '2026-03-08',
    updated_at: '2026-03-12',
  },
  {
    name: 'macd',
    category: '趋势',
    description: 'MACD 动量策略，基于 MACD 金叉死叉信号',
    author: 'System',
    is_active: false,
    loading: false,
    params: { fast_period: 12, slow_period: 26, signal_period: 9 },
    created_at: '2026-03-08',
    updated_at: '2026-03-12',
  },
  {
    name: 'breakout',
    category: '突破',
    description: '通道突破策略，Donchian 通道上下轨突破交易',
    author: 'System',
    is_active: false,
    loading: false,
    params: { lookback_period: 20, volume_filter: true },
    created_at: '2026-03-08',
    updated_at: '2026-03-12',
  },
  {
    name: 'rsi_reversal',
    category: '均值回归',
    description: 'RSI 超买超卖反转策略',
    author: 'System',
    is_active: false,
    loading: false,
    params: { rsi_period: 14, overbought: 70, oversold: 30 },
    created_at: '2026-03-09',
    updated_at: '2026-03-12',
  },
])

// 参数列表 (详情对话框用)
const paramList = ref([
  { name: 'fast_period', type: 'int', default: 10, min: 5, max: 50, description: '快线周期' },
  { name: 'slow_period', type: 'int', default: 30, min: 20, max: 200, description: '慢线周期' },
])

// 计算属性
const filteredStrategies = computed(() => {
  if (!searchText.value) return strategies.value
  const text = searchText.value.toLowerCase()
  return strategies.value.filter(s =>
    s.name.toLowerCase().includes(text) ||
    s.description.toLowerCase().includes(text) ||
    s.category.toLowerCase().includes(text)
  )
})

// 方法
function getCategoryType(category) {
  const typeMap = {
    '趋势': 'primary',
    '均值回归': 'success',
    '突破': 'warning',
    '套利': 'info',
    '其他': 'info',
  }
  return typeMap[category] || 'info'
}

function viewStrategyDetail(strategy) {
  selectedStrategy.value = strategy
  showDetailDialog.value = true
  
  // 加载参数列表
  paramList.value = Object.entries(strategy.params || {}).map(([name, value]) => ({
    name,
    type: typeof value,
    default: value,
    min: '-',
    max: '-',
    description: '-',
  }))
}

async function toggleStrategy(strategy) {
  strategy.loading = true
  
  try {
    // 模拟 API 调用
    await new Promise(resolve => setTimeout(resolve, 500))
    
    const action = strategy.is_active ? '启动' : '停止'
    ElMessage.success(`${action}策略 "${strategy.name}" 成功`)
  } catch (error) {
    strategy.is_active = !strategy.is_active
    ElMessage.error('操作失败：' + error.message)
  } finally {
    strategy.loading = false
  }
}

function editStrategy(strategy) {
  ElMessage.info('编辑功能开发中...')
  console.log('编辑策略:', strategy)
}

function runBacktest(strategy) {
  ElMessage.success('正在跳转到回测页面...')
  // 跳转到回测页面并预填参数
  router.push({
    path: '/backtest',
    query: {
      strategy: strategy.name,
      params: JSON.stringify(strategy.params || {}),
    },
  })
}

function handleCommand(command, strategy) {
  switch (command) {
    case 'duplicate':
      duplicateStrategy(strategy)
      break
    case 'export':
      exportStrategy(strategy)
      break
    case 'delete':
      deleteStrategy(strategy)
      break
  }
}

function duplicateStrategy(strategy) {
  newStrategy.value = {
    name: strategy.name + '_copy',
    category: strategy.category,
    description: strategy.description,
  }
  showCreateDialog.value = true
  ElMessage.info('请修改策略名称')
}

function exportStrategy(strategy) {
  const config = JSON.stringify(strategy, null, 2)
  console.log('导出策略配置:', config)
  ElMessage.success('策略配置已导出到控制台')
}

async function deleteStrategy(strategy) {
  try {
    await ElMessageBox.confirm(
      `确定要删除策略 "${strategy.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    // 模拟删除
    const index = strategies.value.findIndex(s => s.name === strategy.name)
    if (index !== -1) {
      strategies.value.splice(index, 1)
      ElMessage.success('删除成功')
    }
  } catch {
    // 取消删除
  }
}

async function createStrategy() {
  if (!newStrategy.value.name || !newStrategy.value.description) {
    ElMessage.warning('请填写完整信息')
    return
  }
  
  try {
    // 模拟创建
    await new Promise(resolve => setTimeout(resolve, 500))
    
    strategies.value.unshift({
      name: newStrategy.value.name,
      category: newStrategy.value.category,
      description: newStrategy.value.description,
      author: 'User',
      is_active: false,
      loading: false,
      params: {},
      created_at: new Date().toISOString().split('T')[0],
      updated_at: '-',
    })
    
    ElMessage.success('策略创建成功')
    showCreateDialog.value = false
    newStrategy.value = { name: '', category: '趋势', description: '' }
  } catch (error) {
    ElMessage.error('创建失败：' + error.message)
  }
}
</script>

<style scoped>
.strategy-page {
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e6e6e6;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
  color: #1a1a2e;
  font-weight: 600;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.strategies-card {
  border: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

:deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e6e6e6;
  padding: 16px 20px;
}

.strategy-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: #1a1a2e;
}

:deep(.el-table) {
  font-size: 14px;
}

:deep(.el-table th) {
  background: #fafafa;
  color: #666;
  font-weight: 600;
}

:deep(.el-table td) {
  padding: 12px 0;
}

:deep(.el-tag) {
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
}

:deep(.el-button) {
  border-radius: 4px;
  font-size: 13px;
  padding: 8px 16px;
}

:deep(.el-button + .el-button) {
  margin-left: 8px;
}

:deep(.el-switch) {
  --el-switch-on-color: #67c23a;
  --el-switch-off-color: #909399;
}
</style>
