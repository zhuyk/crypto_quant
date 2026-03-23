<!--
账户页面
-->

<template>
  <div class="account-page">
    <div class="account-container">
      <h2>账户设置</h2>
      
      <div class="account-content">
        <!-- 个人信息 -->
        <div class="section">
          <h3>个人信息</h3>
          <div class="info-grid">
            <div class="info-item">
              <label>用户名</label>
              <div>{{ user?.username || '-' }}</div>
            </div>
            <div class="info-item">
              <label>邮箱</label>
              <div>{{ user?.email || '-' }}</div>
            </div>
            <div class="info-item">
              <label>注册时间</label>
              <div>{{ formatDate(user?.created_at) }}</div>
            </div>
            <div class="info-item">
              <label>双因素认证</label>
              <div>
                <span :class="user?.two_factor_enabled ? 'enabled' : 'disabled'">
                  {{ user?.two_factor_enabled ? '已启用' : '未启用' }}
                </span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- API Key 管理 -->
        <div class="section">
          <h3>API Key 管理</h3>
          <button @click="showCreateKey = true" class="create-btn">
            + 创建 API Key
          </button>
          
          <div class="api-keys-list">
            <div 
              v-for="key in apiKeys" 
              :key="key.id"
              class="api-key-card"
            >
              <div class="key-info">
                <div class="key-name">{{ key.name }}</div>
                <div class="key-prefix">{{ key.key_prefix }}</div>
              </div>
              <div class="key-meta">
                <div>创建：{{ formatDate(key.created_at) }}</div>
                <div>状态：{{ key.status }}</div>
              </div>
              <button @click="revokeKey(key.id)" class="revoke-btn">
                撤销
              </button>
            </div>
            <div v-if="apiKeys.length === 0" class="empty">
              暂无 API Key
            </div>
          </div>
        </div>
        
        <!-- 账户统计 -->
        <div class="section">
          <h3>账户统计</h3>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-label">总资产</div>
              <div class="stat-value">{{ formatMoney(stats?.total_balance || 0) }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">总充值</div>
              <div class="stat-value">{{ formatMoney(stats?.total_deposits || 0) }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">总盈亏</div>
              <div class="stat-value" :class="stats?.total_pnl >= 0 ? 'up' : 'down'">
                {{ formatMoney(stats?.total_pnl || 0) }}
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-label">交易次数</div>
              <div class="stat-value">{{ stats?.total_trades || 0 }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 创建 API Key 弹窗 -->
    <div v-if="showCreateKey" class="modal-overlay" @click="showCreateKey = false">
      <div class="modal" @click.stop>
        <h3>创建 API Key</h3>
        
        <div class="form-group">
          <label>名称</label>
          <input type="text" v-model="newKey.name" placeholder="例如：交易机器人" />
        </div>
        
        <div class="form-group">
          <label>权限</label>
          <div class="checkbox-group">
            <label>
              <input type="checkbox" v-model="newKey.permissions" value="trade:execute" />
              交易执行
            </label>
            <label>
              <input type="checkbox" v-model="newKey.permissions" value="trade:view" />
              查看交易
            </label>
            <label>
              <input type="checkbox" v-model="newKey.permissions" value="account:view" />
              查看账户
            </label>
          </div>
        </div>
        
        <div class="form-group">
          <label>过期天数</label>
          <input type="number" v-model="newKey.expiresDays" placeholder="30" />
        </div>
        
        <div class="modal-actions">
          <button @click="showCreateKey = false" class="cancel-btn">取消</button>
          <button @click="createApiKey" class="confirm-btn">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/api/client.js'

const user = ref(null)
const apiKeys = ref([])
const stats = ref(null)
const showCreateKey = ref(false)

const newKey = ref({
  name: '',
  permissions: [],
  expiresDays: 30,
})

const loadUser = async () => {
  try {
    user.value = await api.auth.me()
  } catch (error) {
    console.error('加载用户失败:', error)
  }
}

const loadApiKeys = async () => {
  try {
    const data = await api.auth.apiKeys()
    apiKeys.value = data.api_keys || []
  } catch (error) {
    console.error('加载 API Key 失败:', error)
  }
}

const loadStats = async () => {
  try {
    stats.value = await api.account.statistics()
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const createApiKey = async () => {
  try {
    await api.auth.createApiKey({
      name: newKey.value.name,
      permissions: newKey.value.permissions,
      expires_days: parseInt(newKey.value.expiresDays),
    })
    
    showCreateKey.value = false
    await loadApiKeys()
  } catch (error) {
    alert('创建失败：' + error.message)
  }
}

const revokeKey = async (keyId) => {
  if (!confirm('确定要撤销此 API Key 吗？')) return
  
  try {
    await api.auth.revokeApiKey(keyId)
    await loadApiKeys()
  } catch (error) {
    alert('撤销失败：' + error.message)
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatMoney = (value) => {
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

onMounted(() => {
  loadUser()
  loadApiKeys()
  loadStats()
})
</script>

<style scoped>
.account-page {
  height: 100%;
}

.account-container {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.account-container h2 {
  margin: 0 0 30px 0;
  color: #333;
}

.account-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.section {
  padding-bottom: 30px;
  border-bottom: 1px solid #eee;
}

.section:last-child {
  border-bottom: none;
}

.section h3 {
  margin: 0 0 20px 0;
  color: #333;
  font-size: 16px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.info-item label {
  display: block;
  font-size: 12px;
  color: #999;
  margin-bottom: 5px;
}

.info-item div {
  font-size: 14px;
  color: #333;
}

.enabled {
  color: #28a745;
  font-weight: bold;
}

.disabled {
  color: #dc3545;
}

.create-btn {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 20px;
}

.api-keys-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.api-key-card {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.key-info {
  flex: 1;
}

.key-name {
  font-weight: bold;
  color: #333;
}

.key-prefix {
  font-size: 12px;
  color: #666;
  font-family: monospace;
}

.key-meta {
  font-size: 12px;
  color: #999;
}

.revoke-btn {
  padding: 6px 12px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-card {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 10px;
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

.empty {
  text-align: center;
  color: #999;
  padding: 40px;
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
  max-width: 400px;
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
.form-group input[type="number"] {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
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
</style>
