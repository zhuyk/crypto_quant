<!--
交易所 API Key 管理页面
-->

<template>
  <div class="exchange-keys-page">
    <div class="page-header">
      <h2>🏦 交易所 API Key 管理</h2>
      <button @click="showAddModal = true" class="add-btn">
        + 添加交易所
      </button>
    </div>
    
    <!-- 统计卡片 -->
    <div class="stats-row" v-if="stats">
      <div class="stat-card">
        <div class="stat-label">总交易所</div>
        <div class="stat-value">{{ stats.total_keys }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃中</div>
        <div class="stat-value active">{{ stats.active_keys }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">支持交易所</div>
        <div class="stat-value">{{ Object.keys(supportedExchanges).length }}</div>
      </div>
    </div>
    
    <!-- 交易所列表 -->
    <div class="exchange-list">
      <div 
        v-for="key in exchangeKeys" 
        :key="key.id"
        class="exchange-card"
        :class="{ inactive: !key.is_active }"
      >
        <div class="exchange-header">
          <div class="exchange-info">
            <div class="exchange-logo">
              {{ getExchangeLogo(key.exchange) }}
            </div>
            <div class="exchange-details">
              <div class="exchange-name">
                {{ getExchangeName(key.exchange) }}
                <span v-if="key.is_testnet" class="testnet-badge">测试网</span>
              </div>
              <div class="exchange-key-name">{{ key.name }}</div>
              <div class="exchange-key-prefix">Key: {{ key.api_key_prefix }}</div>
            </div>
          </div>
          <div class="exchange-status">
            <span :class="['status-badge', key.is_active ? 'active' : 'inactive']">
              {{ key.is_active ? '✓ 活跃' : '✗ 停用' }}
            </span>
          </div>
        </div>
        
        <div class="exchange-body">
          <div class="permissions">
            <span 
              v-for="perm in key.permissions" 
              :key="perm"
              class="permission-tag"
            >
              {{ getPermissionLabel(perm) }}
            </span>
          </div>
          
          <div class="exchange-meta">
            <span>创建：{{ formatDate(key.created_at) }}</span>
            <span v-if="key.last_used">使用：{{ formatDate(key.last_used) }}</span>
          </div>
        </div>
        
        <div class="exchange-actions">
          <button @click="testConnection(key)" class="action-btn test-btn">
            🔌 测试连接
          </button>
          <button @click="editKey(key)" class="action-btn edit-btn">
            ✏️ 编辑
          </button>
          <button @click="toggleStatus(key)" class="action-btn toggle-btn">
            {{ key.is_active ? '🚫 停用' : '✅ 启用' }}
          </button>
          <button @click="deleteKey(key)" class="action-btn delete-btn">
            🗑️ 删除
          </button>
        </div>
      </div>
      
      <div v-if="exchangeKeys.length === 0" class="empty-state">
        <div class="empty-icon">🏦</div>
        <div class="empty-text">暂无交易所 API Key</div>
        <div class="empty-hint">点击右上角"添加交易所"开始配置</div>
      </div>
    </div>
    
    <!-- 添加/编辑弹窗 -->
    <div v-if="showAddModal || showEditModal" class="modal-overlay" @click="closeModals">
      <div class="modal" @click.stop>
        <h3>{{ showAddModal ? '添加交易所' : '编辑交易所' }}</h3>
        
        <div class="form-group">
          <label>交易所 *</label>
          <select v-model="formData.exchange" :disabled="showEditModal">
            <option v-for="(info, key) in supportedExchanges" :key="key" :value="key">
              {{ info.name }}
            </option>
          </select>
        </div>
        
        <div class="form-group">
          <label>名称 *</label>
          <input 
            type="text" 
            v-model="formData.name" 
            placeholder="例如：主账户交易 Key"
          />
        </div>
        
        <div class="form-group" v-if="showAddModal">
          <label>API Key *</label>
          <input 
            type="text" 
            v-model="formData.api_key" 
            placeholder="输入 API Key"
          />
        </div>
        
        <div class="form-group" v-if="showAddModal">
          <label>API Secret *</label>
          <input 
            type="password" 
            v-model="formData.api_secret" 
            placeholder="输入 API Secret"
          />
        </div>
        
        <div class="form-group" v-if="showAddModal && requiresPassphrase(formData.exchange)">
          <label>API Passphrase</label>
          <input 
            type="password" 
            v-model="formData.passphrase" 
            placeholder="OKX/Bybit 需要"
          />
        </div>
        
        <div class="form-group">
          <label>权限</label>
          <div class="checkbox-group">
            <label>
              <input type="checkbox" v-model="formData.permissions" value="trade" />
              交易执行
            </label>
            <label>
              <input type="checkbox" v-model="formData.permissions" value="read" />
              读取行情
            </label>
            <label>
              <input type="checkbox" v-model="formData.permissions" value="withdraw" />
              提现（谨慎开启）
            </label>
          </div>
        </div>
        
        <div class="form-group">
          <label>
            <input type="checkbox" v-model="formData.is_testnet" />
            使用测试网（Simulated Trading）
          </label>
        </div>
        
        <div class="modal-actions">
          <button @click="closeModals" class="cancel-btn">取消</button>
          <button @click="submitForm" class="confirm-btn">
            {{ showAddModal ? '添加' : '保存' }}
          </button>
        </div>
      </div>
    </div>
    
    <!-- 测试结果弹窗 -->
    <div v-if="testResult" class="modal-overlay" @click="testResult = null">
      <div class="modal" @click.stop>
        <h3>🔌 连接测试</h3>
        <div class="test-result" :class="testResult.success ? 'success' : 'error'">
          {{ testResult.message }}
        </div>
        <div v-if="testResult.balance" class="balance-info">
          <div v-for="(amount, currency) in testResult.balance" :key="currency">
            {{ currency }}: {{ amount }}
          </div>
        </div>
        <button @click="testResult = null" class="close-btn">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '@/api/client.js'

const exchangeKeys = ref([])
const stats = ref(null)
const showAddModal = ref(false)
const showEditModal = ref(false)
const testResult = ref(null)
const editingKey = ref(null)

const supportedExchanges = {
  binance: { name: '币安 (Binance)' },
  okx: { name: 'OKX' },
  bybit: { name: 'Bybit' },
  htx: { name: 'HTX (火币)' },
  gate: { name: 'Gate.io' },
  kucoin: { name: 'Kucoin' },
}

const formData = ref({
  exchange: 'binance',
  name: '',
  api_key: '',
  api_secret: '',
  passphrase: '',
  permissions: ['trade', 'read'],
  is_testnet: false,
})

const requiresPassphrase = (exchange) => {
  return ['okx', 'bybit', 'kucoin'].includes(exchange)
}

const getExchangeName = (exchange) => {
  return supportedExchanges[exchange]?.name || exchange
}

const getExchangeLogo = (exchange) => {
  const logos = {
    binance: '🟡',
    okx: '⚫',
    bybit: '🟠',
    htx: '🔵',
    gate: '🟢',
    kucoin: '🟣',
  }
  return logos[exchange] || '🏦'
}

const getPermissionLabel = (perm) => {
  const labels = {
    trade: '交易',
    read: '读取',
    withdraw: '提现',
  }
  return labels[perm] || perm
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadExchangeKeys = async () => {
  try {
    const data = await api.exchangeKeys.list()
    exchangeKeys.value = data
  } catch (error) {
    console.error('加载交易所 Keys 失败:', error)
  }
}

const loadStats = async () => {
  try {
    stats.value = await api.exchangeKeys.stats()
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const testConnection = async (key) => {
  try {
    testResult.value = await api.exchangeKeys.test(key.id)
  } catch (error) {
    testResult.value = {
      success: false,
      message: error.message,
    }
  }
}

const editKey = (key) => {
  editingKey.value = key
  formData.value = {
    exchange: key.exchange,
    name: key.name,
    permissions: [...key.permissions],
    is_testnet: key.is_testnet,
  }
  showEditModal.value = true
}

const toggleStatus = async (key) => {
  try {
    await api.exchangeKeys.update(key.id, {
      is_active: !key.is_active,
    })
    await loadExchangeKeys()
  } catch (error) {
    alert('操作失败：' + error.message)
  }
}

const deleteKey = async (key) => {
  if (!confirm(`确定要删除 ${getExchangeName(key.exchange)} - ${key.name} 吗？`)) return
  
  try {
    await api.exchangeKeys.delete(key.id)
    await loadExchangeKeys()
    await loadStats()
  } catch (error) {
    alert('删除失败：' + error.message)
  }
}

const submitForm = async () => {
  if (!formData.value.name) {
    alert('请输入名称')
    return
  }
  
  if (showAddModal.value && (!formData.value.api_key || !formData.value.api_secret)) {
    alert('请输入 API Key 和 Secret')
    return
  }
  
  try {
    if (showAddModal.value) {
      await api.exchangeKeys.create(formData.value)
    } else if (showEditModal.value && editingKey.value) {
      await api.exchangeKeys.update(editingKey.value.id, {
        name: formData.value.name,
        permissions: formData.value.permissions,
        is_testnet: formData.value.is_testnet,
      })
    }
    
    closeModals()
    await loadExchangeKeys()
    await loadStats()
  } catch (error) {
    alert('操作失败：' + error.message)
  }
}

const closeModals = () => {
  showAddModal.value = false
  showEditModal.value = false
  editingKey.value = null
  formData.value = {
    exchange: 'binance',
    name: '',
    api_key: '',
    api_secret: '',
    passphrase: '',
    permissions: ['trade', 'read'],
    is_testnet: false,
  }
}

onMounted(() => {
  loadExchangeKeys()
  loadStats()
})
</script>

<style scoped>
.exchange-keys-page {
  height: 100%;
  padding: 20px;
  background: #f5f7fa;
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

.add-btn {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.stat-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.stat-value.active {
  color: #28a745;
}

.exchange-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.exchange-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  border-left: 4px solid #28a745;
}

.exchange-card.inactive {
  border-left-color: #6c757d;
  opacity: 0.7;
}

.exchange-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 15px;
}

.exchange-info {
  display: flex;
  gap: 15px;
  align-items: center;
}

.exchange-logo {
  font-size: 32px;
}

.exchange-details {
  flex: 1;
}

.exchange-name {
  font-size: 18px;
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
}

.testnet-badge {
  display: inline-block;
  padding: 2px 8px;
  background: #ffc107;
  color: #333;
  border-radius: 4px;
  font-size: 12px;
  margin-left: 8px;
}

.exchange-key-name {
  font-size: 14px;
  color: #666;
  margin-bottom: 3px;
}

.exchange-key-prefix {
  font-size: 12px;
  color: #999;
  font-family: monospace;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
}

.status-badge.active {
  background: #d4edda;
  color: #155724;
}

.status-badge.inactive {
  background: #f8d7da;
  color: #721c24;
}

.exchange-body {
  margin-bottom: 15px;
}

.permissions {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.permission-tag {
  padding: 4px 10px;
  background: #e9ecef;
  color: #495057;
  border-radius: 4px;
  font-size: 12px;
}

.exchange-meta {
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: #999;
}

.exchange-actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.test-btn {
  background: #17a2b8;
  color: white;
}

.edit-btn {
  background: #ffc107;
  color: #333;
}

.toggle-btn {
  background: #6c757d;
  color: white;
}

.delete-btn {
  background: #dc3545;
  color: white;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: white;
  border-radius: 12px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 15px;
}

.empty-text {
  font-size: 18px;
  color: #333;
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 14px;
  color: #999;
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
  max-height: 90vh;
  overflow-y: auto;
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

.form-group input[type="text"],
.form-group input[type="password"],
.form-group select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: normal;
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

.close-btn {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  margin-top: 15px;
}

.test-result {
  padding: 15px;
  border-radius: 6px;
  margin-bottom: 15px;
}

.test-result.success {
  background: #d4edda;
  color: #155724;
}

.test-result.error {
  background: #f8d7da;
  color: #721c24;
}

.balance-info {
  padding: 10px;
  background: #f8f9fa;
  border-radius: 6px;
  font-family: monospace;
}
</style>
