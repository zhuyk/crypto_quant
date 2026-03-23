<!--
策略管理页面
-->

<template>
  <div class="strategies-page">
    <div class="strategies-container">
      <div class="page-header">
        <h2>我的策略</h2>
        <button @click="showCreateStrategy = true" class="create-btn">
          + 创建策略
        </button>
      </div>
      
      <!-- 策略列表 -->
      <div class="strategies-list">
        <div 
          v-for="strategy in strategies" 
          :key="strategy.id"
          class="strategy-card"
        >
          <div class="strategy-header">
            <div class="strategy-info">
              <h3>{{ strategy.name }}</h3>
              <span class="status" :class="strategy.status">
                {{ strategy.status }}
              </span>
            </div>
            <div class="strategy-actions">
              <button @click="editStrategy(strategy)" class="btn-edit">编辑</button>
              <button @click="backtestStrategy(strategy)" class="btn-backtest">回测</button>
              <button @click="toggleStrategy(strategy)" class="btn-toggle">
                {{ strategy.enabled ? '停止' : '启动' }}
              </button>
            </div>
          </div>
          
          <div class="strategy-description">
            {{ strategy.description }}
          </div>
          
          <div class="strategy-stats">
            <div class="stat">
              <div class="stat-label">总收益</div>
              <div class="stat-value" :class="strategy.performance?.total_return >= 0 ? 'up' : 'down'">
                {{ formatPercent(strategy.performance?.total_return || 0) }}
              </div>
            </div>
            <div class="stat">
              <div class="stat-label">Sharpe</div>
              <div class="stat-value">{{ (strategy.performance?.sharpe_ratio || 0).toFixed(2) }}</div>
            </div>
            <div class="stat">
              <div class="stat-label">胜率</div>
              <div class="stat-value">{{ formatPercent(strategy.performance?.win_rate || 0) }}</div>
            </div>
            <div class="stat">
              <div class="stat-label">交易次数</div>
              <div class="stat-value">{{ strategy.performance?.total_trades || 0 }}</div>
            </div>
          </div>
          
          <div class="strategy-footer">
            <div class="strategy-meta">
              <span>更新时间：{{ formatDate(strategy.updated_at) }}</span>
            </div>
          </div>
        </div>
        
        <div v-if="strategies.length === 0" class="empty-state">
          <div class="empty-icon">🤖</div>
          <h3>暂无策略</h3>
          <p>创建你的第一个量化策略吧</p>
          <button @click="showCreateStrategy = true" class="create-btn-large">
            + 创建策略
          </button>
        </div>
      </div>
    </div>
    
    <!-- 创建策略弹窗 -->
    <div v-if="showCreateStrategy" class="modal-overlay" @click="showCreateStrategy = false">
      <div class="modal" @click.stop>
        <h3>创建策略</h3>
        
        <div class="form-group">
          <label>策略名称</label>
          <input type="text" v-model="newStrategy.name" placeholder="例如：双均线策略" />
        </div>
        
        <div class="form-group">
          <label>策略类型</label>
          <select v-model="newStrategy.type">
            <option value="trend">趋势策略</option>
            <option value="mean_reversion">均值回归</option>
            <option value="breakout">突破策略</option>
            <option value="ml">机器学习</option>
          </select>
        </div>
        
        <div class="form-group">
          <label>描述</label>
          <textarea v-model="newStrategy.description" rows="3" placeholder="策略描述..."></textarea>
        </div>
        
        <div class="modal-actions">
          <button @click="showCreateStrategy = false" class="cancel-btn">取消</button>
          <button @click="createStrategy" class="confirm-btn">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client.js'

const router = useRouter()

const strategies = ref([])
const showCreateStrategy = ref(false)

const newStrategy = ref({
  name: '',
  type: 'trend',
  description: '',
})

const loadStrategies = async () => {
  try {
    const data = await api.backtest.strategies()
    strategies.value = data.strategies || []
  } catch (error) {
    console.error('加载策略失败:', error)
  }
}

const createStrategy = async () => {
  try {
    // TODO: 实现创建策略 API
    alert('策略创建功能开发中...')
    showCreateStrategy.value = false
  } catch (error) {
    alert('创建失败：' + error.message)
  }
}

const editStrategy = (strategy) => {
  router.push(`/strategies/${strategy.id}/edit`)
}

const backtestStrategy = (strategy) => {
  router.push(`/backtest?strategy=${strategy.name}`)
}

const toggleStrategy = async (strategy) => {
  try {
    // TODO: 实现启动/停止策略 API
    alert('策略控制功能开发中...')
  } catch (error) {
    alert('操作失败：' + error.message)
  }
}

const formatPercent = (value) => {
  return (value * 100).toFixed(2) + '%'
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadStrategies()
})
</script>

<style scoped>
.strategies-page {
  height: 100%;
}

.strategies-container {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.page-header h2 {
  margin: 0;
  color: #333;
}

.create-btn {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}

.strategies-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.strategy-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid #e9ecef;
}

.strategy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.strategy-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.strategy-info h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
}

.status.active {
  background: #d4edda;
  color: #155724;
}

.status.inactive {
  background: #e9ecef;
  color: #6c757d;
}

.strategy-actions {
  display: flex;
  gap: 10px;
}

.strategy-actions button {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-edit {
  background: #6c757d;
  color: white;
}

.btn-backtest {
  background: #007bff;
  color: white;
}

.btn-toggle {
  background: #28a745;
  color: white;
}

.strategy-description {
  color: #666;
  margin-bottom: 20px;
  line-height: 1.6;
}

.strategy-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin-bottom: 20px;
}

.stat {
  text-align: center;
  padding: 15px;
  background: white;
  border-radius: 6px;
}

.stat-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 20px;
  font-weight: bold;
  color: #333;
}

.up {
  color: #28a745;
}

.down {
  color: #dc3545;
}

.strategy-footer {
  padding-top: 15px;
  border-top: 1px solid #dee2e6;
  font-size: 12px;
  color: #999;
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.empty-state h3 {
  margin: 0 0 10px 0;
  color: #333;
}

.empty-state p {
  color: #666;
  margin-bottom: 30px;
}

.create-btn-large {
  padding: 14px 40px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  padding: 30px;
  border-radius: 12px;
  width: 100%;
  max-width: 500px;
}

.modal h3 {
  margin: 0 0 20px 0;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 8px;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
}

.modal-actions {
  display: flex;
  gap: 15px;
  justify-content: flex-end;
}

.cancel-btn {
  padding: 10px 20px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.confirm-btn {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
</style>
