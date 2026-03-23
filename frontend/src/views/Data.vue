<!--
历史数据管理页面
-->

<template>
  <div class="data-page">
    <div class="data-container">
      <div class="page-header">
        <h2>历史数据管理</h2>
        <div class="actions">
          <button @click="showDownload = true" class="btn-download" :disabled="downloadStatus.downloading">
            {{ downloadStatus.downloading ? '⏳ 下载中...' : '⬇️ 下载数据' }}
          </button>
          <button @click="refreshData" class="btn-refresh">
            🔄 刷新
          </button>
        </div>
      </div>
      
      <!-- 下载进度提示 -->
      <div v-if="downloadStatus.downloading" class="download-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: downloadStatus.progress + '%' }"></div>
        </div>
        <div class="progress-info">
          <span>📊 下载进度：{{ downloadStatus.success }}/{{ downloadStatus.total }} 成功</span>
          <span v-if="downloadStatus.failed > 0" class="failed-count">❌ {{ downloadStatus.failed }} 失败</span>
        </div>
      </div>
      
      <!-- 数据概览 -->
      <div class="overview-cards">
        <div class="card">
          <div class="card-label">交易对数量</div>
          <div class="card-value">{{ symbols.length }}</div>
        </div>
        <div class="card">
          <div class="card-label">总数据量</div>
          <div class="card-value">{{ formatSize(totalSize) }}</div>
        </div>
        <div class="card">
          <div class="card-label">最早数据</div>
          <div class="card-value">{{ formatDate(earliestDate) }}</div>
        </div>
        <div class="card">
          <div class="card-label">最新数据</div>
          <div class="card-value">{{ formatDate(latestDate) }}</div>
        </div>
      </div>
      
      <!-- 交易对列表 -->
      <div class="symbols-section">
        <h3>已下载交易对</h3>
        
        <!-- 搜索和筛选 -->
        <div class="filters">
          <input 
            type="text" 
            v-model="searchQuery"
            placeholder="搜索交易对..."
            class="search-input"
          />
          <select v-model="timeframeFilter">
            <option value="">全部周期</option>
            <option value="1m">1 分钟</option>
            <option value="5m">5 分钟</option>
            <option value="15m">15 分钟</option>
            <option value="1h">1 小时</option>
            <option value="4h">4 小时</option>
            <option value="1d">1 天</option>
          </select>
        </div>
        
        <!-- 交易对表格 -->
        <div class="symbols-table">
          <table>
            <thead>
              <tr>
                <th>交易对</th>
                <th>周期</th>
                <th>K 线数量</th>
                <th>时间范围</th>
                <th>数据量</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="symbol in filteredSymbols" :key="symbol.symbol + symbol.timeframe">
                <td>
                  <span class="symbol-name">{{ symbol.symbol }}</span>
                </td>
                <td>
                  <span class="timeframe-badge">{{ symbol.timeframe }}</span>
                </td>
                <td>{{ symbol.candle_count?.toLocaleString() || 0 }}</td>
                <td>
                  {{ formatDate(symbol.start_time) }} - {{ formatDate(symbol.end_time) }}
                </td>
                <td>{{ formatSize(symbol.size) }}</td>
                <td>{{ formatRelativeTime(symbol.updated_at) }}</td>
                <td>
                  <div class="action-buttons">
                    <button @click="viewKline(symbol)" class="btn-view" title="查看 K 线">
                      📊
                    </button>
                    <button @click="downloadSymbol(symbol)" class="btn-download-small" title="更新数据">
                      ⬇️
                    </button>
                    <button @click="deleteSymbol(symbol)" class="btn-delete" title="删除">
                      🗑️
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    
    <!-- K 线查看器弹窗 -->
    <div v-if="showKlineViewer" class="modal-overlay" @click="showKlineViewer = false">
      <div class="kline-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ selectedSymbol?.symbol }} K 线图 ({{ selectedSymbol?.timeframe }})</h3>
          <button @click="showKlineViewer = false" class="close-btn">✕</button>
        </div>
        <div class="modal-body">
          <KlineViewer 
            :symbol="selectedSymbol?.symbol"
            :timeframe="selectedSymbol?.timeframe"
          />
        </div>
      </div>
    </div>
    
    <!-- 下载数据弹窗 -->
    <div v-if="showDownload" class="modal-overlay" @click="showDownload = false">
      <div class="modal" @click.stop>
        <h3>下载历史数据</h3>
        
        <div class="form-group">
          <label>交易对</label>
          <input 
            type="text" 
            v-model="downloadForm.symbols"
            placeholder="例如：BTC/USDT,ETH/USDT（多个用逗号分隔）"
          />
        </div>
        
        <div class="form-group">
          <label>时间周期</label>
          <select v-model="downloadForm.timeframe">
            <option value="1m">1 分钟</option>
            <option value="5m">5 分钟</option>
            <option value="15m">15 分钟</option>
            <option value="1h" selected>1 小时</option>
            <option value="4h">4 小时</option>
            <option value="1d">1 天</option>
          </select>
        </div>
        
        <div class="form-group">
          <label>开始时间</label>
          <input type="date" v-model="downloadForm.startTime" />
        </div>
        
        <div class="form-group">
          <label>结束时间</label>
          <input type="date" v-model="downloadForm.endTime" />
        </div>
        
        <div class="modal-actions">
          <button @click="showDownload = false" class="cancel-btn">取消</button>
          <button @click="startDownload" class="confirm-btn">开始下载</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import KlineViewer from '@/components/KlineViewer.vue'
import { api } from '@/api/client.js'

const symbols = ref([])
const searchQuery = ref('')
const timeframeFilter = ref('')
const showKlineViewer = ref(false)
const showDownload = ref(false)
const selectedSymbol = ref(null)

const totalSize = ref(0)
const earliestDate = ref(null)
const latestDate = ref(null)

const downloadForm = ref({
  symbols: '',
  timeframe: '1h',
  startTime: '',
  endTime: '',
})

const downloadStatus = ref({
  downloading: false,
  progress: 0,
  total: 0,
  success: 0,
  failed: 0,
  results: [],
})

const filteredSymbols = computed(() => {
  let result = [...symbols.value]
  
  // 搜索
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(s => 
      s.symbol.toLowerCase().includes(query)
    )
  }
  
  // 周期筛选
  if (timeframeFilter.value) {
    result = result.filter(s => s.timeframe === timeframeFilter.value)
  }
  
  return result
})

const loadSymbols = async () => {
  try {
    const response = await fetch('/api/v1/data/symbols')
    const data = await response.json()
    // 后端返回的是数组，不是对象
    symbols.value = Array.isArray(data) ? data : (data.symbols || [])
    
    // 计算统计
    if (symbols.value.length > 0) {
      totalSize.value = symbols.value.reduce((sum, s) => sum + (s.size || 0), 0)
      
      const startTimes = symbols.value.map(s => s.start_time).filter(Boolean)
      const endTimes = symbols.value.map(s => s.end_time).filter(Boolean)
      
      earliestDate.value = startTimes.length > 0 ? Math.min(...startTimes) : null
      latestDate.value = endTimes.length > 0 ? Math.max(...endTimes) : null
    }
  } catch (error) {
    console.error('加载数据失败:', error)
  }
}

const refreshData = () => {
  loadSymbols()
}

const viewKline = (symbol) => {
  // 确保 symbol 格式正确（使用 / 分隔）
  if (!symbol.symbol.includes('/')) {
    // 如果是 BTCUSDT 格式，转换为 BTC/USDT
    if (symbol.symbol.length === 6) {
      symbol.symbol = symbol.symbol.slice(0, 3) + '/' + symbol.symbol.slice(3)
    }
  }
  selectedSymbol.value = symbol
  showKlineViewer.value = true
}

const downloadSymbol = async (symbol) => {
  if (!confirm(`确定要更新 ${symbol.symbol} 的数据吗？`)) return
  
  downloadStatus.value = {
    downloading: true,
    progress: 0,
    total: 1,
    success: 0,
    failed: 0,
    results: [],
  }
  
  try {
    const response = await fetch('/api/v1/data/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbols: [symbol.symbol],
        timeframe: symbol.timeframe,
      }),
    })
    
    const data = await response.json()
    
    // 处理结果
    data.results.forEach(result => {
      if (result.success) {
        downloadStatus.value.success++
      } else {
        downloadStatus.value.failed++
      }
      downloadStatus.value.results.push(result)
    })
    
    downloadStatus.value.progress = 100
    downloadStatus.value.downloading = false
    
    // 显示结果通知
    showDownloadResult(data.results)
    
    // 刷新列表
    await loadSymbols()
    
  } catch (error) {
    downloadStatus.value.downloading = false
    alert('下载失败：' + error.message)
  }
}

const deleteSymbol = async (symbol) => {
  if (!confirm(`确定要删除 ${symbol.symbol} 的数据吗？`)) return
  
  try {
    await fetch(`/api/v1/data/symbols/${symbol.symbol}?timeframe=${symbol.timeframe}`, {
      method: 'DELETE',
    })
    
    await loadSymbols()
  } catch (error) {
    alert('删除失败：' + error.message)
  }
}

const startDownload = async () => {
  const symbolList = downloadForm.value.symbols
    .split(',')
    .map(s => s.trim().toUpperCase())
    .filter(Boolean)
  
  if (symbolList.length === 0) {
    alert('请输入交易对')
    return
  }
  
  // 初始化下载状态
  downloadStatus.value = {
    downloading: true,
    progress: 0,
    total: symbolList.length,
    success: 0,
    failed: 0,
    results: [],
  }
  
  showDownload.value = false
  
  try {
    const response = await fetch('/api/v1/data/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbols: symbolList,
        timeframe: downloadForm.value.timeframe,
        start_time: downloadForm.value.startTime ? new Date(downloadForm.value.startTime).getTime() : null,
        end_time: downloadForm.value.endTime ? new Date(downloadForm.value.endTime).getTime() : null,
      }),
    })
    
    const data = await response.json()
    
    // 处理结果
    data.results.forEach(result => {
      if (result.success) {
        downloadStatus.value.success++
      } else {
        downloadStatus.value.failed++
      }
      downloadStatus.value.results.push(result)
    })
    
    downloadStatus.value.progress = 100
    downloadStatus.value.downloading = false
    
    // 显示结果通知
    showDownloadResult(data.results)
    
    // 刷新列表
    await loadSymbols()
    
  } catch (error) {
    downloadStatus.value.downloading = false
    alert('下载失败：' + error.message)
  }
}

const showDownloadResult = (results) => {
  const successCount = results.filter(r => r.success).length
  const failedCount = results.filter(r => !r.success).length
  
  let message = `✅ 下载完成！\n\n`
  message += `成功：${successCount} 个\n`
  message += `失败：${failedCount} 个\n\n`
  
  results.forEach(result => {
    if (result.success) {
      message += `✅ ${result.symbol}: ${result.count} 条 K 线\n`
    } else {
      message += `❌ ${result.symbol}: ${result.error}\n`
    }
  })
  
  // 使用自定义通知而不是 alert
  showNotification(message, results.every(r => r.success) ? 'success' : 'warning')
}

const showNotification = (message, type = 'info') => {
  // 创建一个临时的通知元素
  const notification = document.createElement('div')
  notification.className = `download-notification ${type}`
  notification.innerHTML = `
    <div class="notification-content">
      <div class="notification-icon">${type === 'success' ? '✅' : type === 'warning' ? '⚠️' : 'ℹ️'}</div>
      <div class="notification-message">${message.replace(/\n/g, '<br>')}</div>
      <button class="notification-close" onclick="this.parentElement.parentElement.remove()">✕</button>
    </div>
  `
  
  // 添加样式
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: ${type === 'success' ? '#d4edda' : type === 'warning' ? '#fff3cd' : '#d1ecf1'};
    border: 1px solid ${type === 'success' ? '#c3e6cb' : type === 'warning' ? '#ffeeba' : '#bee5eb'};
    border-radius: 8px;
    padding: 15px 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 9999;
    max-width: 500px;
    animation: slideIn 0.3s ease-out;
  `
  
  document.body.appendChild(notification)
  
  // 5 秒后自动消失
  setTimeout(() => {
    if (notification.parentElement) {
      notification.style.animation = 'slideOut 0.3s ease-out'
      setTimeout(() => notification.remove(), 300)
    }
  }, 5000)
}

const formatSize = (bytes) => {
  if (!bytes) return '0 B'
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  const gb = mb / 1024
  return `${gb.toFixed(2)} GB`
}

const formatDate = (timestamp) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleDateString('zh-CN')
}

const formatRelativeTime = (timestamp) => {
  if (!timestamp) return '-'
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  return `${days}天前`
}

onMounted(() => {
  loadSymbols()
})
</script>

<style scoped>
.data-page {
  height: 100%;
}

.data-container {
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

.actions {
  display: flex;
  gap: 10px;
}

.btn-download,
.btn-refresh {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}

.btn-download {
  background: #28a745;
  color: white;
}

.btn-refresh {
  background: #007bff;
  color: white;
}

.overview-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 30px;
}

.card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.card-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.card-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.symbols-section h3 {
  margin: 0 0 20px 0;
  color: #333;
}

.filters {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
}

.search-input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
}

.filters select {
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
}

.symbols-table {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

th {
  background: #f8f9fa;
  font-weight: bold;
  color: #333;
}

tr:hover {
  background: #f8f9fa;
}

.symbol-name {
  font-weight: bold;
  color: #007bff;
}

.timeframe-badge {
  padding: 4px 8px;
  background: #007bff;
  color: white;
  border-radius: 4px;
  font-size: 12px;
}

.action-buttons {
  display: flex;
  gap: 5px;
}

.action-buttons button {
  padding: 5px 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-view {
  background: #007bff;
  color: white;
}

.btn-download-small {
  background: #28a745;
  color: white;
}

.btn-delete {
  background: #dc3545;
  color: white;
}

.kline-modal {
  background: white;
  border-radius: 12px;
  width: 95%;
  max-width: 1400px;
  height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
}

.close-btn {
  padding: 5px 15px;
  background: transparent;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 18px;
}

.modal-body {
  flex: 1;
  overflow: hidden;
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
.form-group select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
}

.modal-actions {
  display: flex;
  gap: 15px;
  justify-content: flex-end;
}

.cancel-btn,
.confirm-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}

.cancel-btn {
  background: #6c757d;
  color: white;
}

.confirm-btn {
  background: #007bff;
  color: white;
}

.download-progress {
  background: #e7f3ff;
  border: 1px solid #b3d9ff;
  border-radius: 8px;
  padding: 15px 20px;
  margin-bottom: 20px;
}

.progress-bar {
  background: #fff;
  border-radius: 10px;
  height: 20px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-fill {
  background: linear-gradient(90deg, #007bff, #0056b3);
  height: 100%;
  transition: width 0.3s ease;
  border-radius: 10px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #333;
}

.failed-count {
  color: #dc3545;
  font-weight: bold;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes slideOut {
  from {
    transform: translateX(0);
    opacity: 1;
  }
  to {
    transform: translateX(100%);
    opacity: 0;
  }
}

.download-notification {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.download-notification .notification-content {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.download-notification .notification-icon {
  font-size: 20px;
  line-height: 1;
}

.download-notification .notification-message {
  flex: 1;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-line;
}

.download-notification .notification-close {
  background: transparent;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 0;
  margin-left: 10px;
  opacity: 0.6;
}

.download-notification .notification-close:hover {
  opacity: 1;
}
</style>
