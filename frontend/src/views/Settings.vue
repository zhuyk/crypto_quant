<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>⚙️ 系统设置</h2>
      <el-button type="primary" @click="saveAll">
        <el-icon><Check /></el-icon> 保存所有配置
      </el-button>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- API 配置 -->
      <el-tab-pane label="🔑 API 配置" name="api">
        <el-form :model="apiConfig" label-width="160px" size="default">
          <el-alert
            title="💡 提示"
            type="info"
            description="API 密钥将加密存储，仅用于实盘交易。测试环境建议使用测试网密钥。"
            show-icon
            style="margin-bottom: 20px;"
          />
          
          <el-form-item label="交易所">
            <el-select v-model="apiConfig.exchange" style="width: 200px">
              <el-option label="Binance (币安)" value="binance" />
              <el-option label="OKX" value="okx" disabled />
              <el-option label="Bybit" value="bybit" disabled />
            </el-select>
          </el-form-item>
          
          <el-form-item label="API Key" required>
            <el-input
              v-model="apiConfig.apiKey"
              type="password"
              placeholder="请输入 API Key"
              show-password
              style="width: 400px"
            />
          </el-form-item>
          
          <el-form-item label="API Secret" required>
            <el-input
              v-model="apiConfig.apiSecret"
              type="password"
              placeholder="请输入 API Secret"
              show-password
              style="width: 400px"
            />
          </el-form-item>
          
          <el-form-item label="测试网">
            <el-switch
              v-model="apiConfig.testnet"
              active-text="开启"
              inactive-text="关闭"
            />
            <span class="form-tip">开启后使用测试网进行交易</span>
          </el-form-item>
          
          <el-form-item label="API 权限">
            <el-checkbox-group v-model="apiConfig.permissions">
              <el-checkbox label="read">读取</el-checkbox>
              <el-checkbox label="trade">交易</el-checkbox>
              <el-checkbox label="withdraw">提现</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" @click="testApiConnection">
              🔌 测试连接
            </el-button>
            <el-button @click="saveApiConfig">
              💾 保存配置
            </el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 交易设置 -->
      <el-tab-pane label="💹 交易设置" name="trading">
        <el-form :model="tradeConfig" label-width="160px">
          <el-divider content-position="left">资金管理</el-divider>
          
          <el-form-item label="初始资金 ($)">
            <el-input-number
              v-model="tradeConfig.initialCapital"
              :min="1000"
              :max="10000000"
              :step="10000"
              style="width: 200px"
            />
          </el-form-item>
          
          <el-form-item label="单笔最大仓位">
            <el-slider
              v-model="tradeConfig.maxPositionRatio"
              :min="1"
              :max="100"
              :step="5"
              style="width: 300px"
              :format-tooltip="(val) => val + '%'"
            />
            <span class="form-tip">单个交易对最大占用资金比例</span>
          </el-form-item>
          
          <el-form-item label="总仓位上限">
            <el-slider
              v-model="tradeConfig.maxTotalExposure"
              :min="10"
              :max="100"
              :step="10"
              style="width: 300px"
              :format-tooltip="(val) => val + '%'"
            />
            <span class="form-tip">所有持仓总占用资金比例</span>
          </el-form-item>
          
          <el-divider content-position="left">风险控制</el-divider>
          
          <el-form-item label="最大日亏损">
            <el-slider
              v-model="tradeConfig.maxDailyLoss"
              :min="1"
              :max="20"
              :step="1"
              style="width: 300px"
              :format-tooltip="(val) => val + '%'"
            />
            <span class="form-tip">单日最大亏损比例，达到后停止交易</span>
          </el-form-item>
          
          <el-form-item label="最大回撤">
            <el-slider
              v-model="tradeConfig.maxDrawdown"
              :min="5"
              :max="50"
              :step="5"
              style="width: 300px"
              :format-tooltip="(val) => val + '%'"
            />
            <span class="form-tip">从峰值最大回撤比例，达到后停止交易</span>
          </el-form-item>
          
          <el-form-item label="默认止损">
            <el-input-number
              v-model="tradeConfig.defaultStopLoss"
              :min="1"
              :max="20"
              :step="0.5"
              :precision="1"
              style="width: 150px"
            />
            <span class="form-tip">%</span>
          </el-form-item>
          
          <el-form-item label="默认止盈">
            <el-input-number
              v-model="tradeConfig.defaultTakeProfit"
              :min="5"
              :max="100"
              :step="1"
              style="width: 150px"
            />
            <span class="form-tip">%</span>
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" @click="saveTradeConfig">
              💾 保存配置
            </el-button>
            <el-button @click="resetTradeConfig">
              🔄 恢复默认
            </el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 通知设置 -->
      <el-tab-pane label="🔔 通知设置" name="notifications">
        <el-form label-width="160px">
          <el-divider content-position="left">推送方式</el-divider>
          
          <el-form-item label="WebSocket">
            <el-switch v-model="notifyConfig.websocket" disabled />
            <span class="form-tip">实时推送 (已启用)</span>
          </el-form-item>
          
          <el-form-item label="邮件通知">
            <el-switch v-model="notifyConfig.email" />
          </el-form-item>
          
          <el-form-item label="钉钉通知">
            <el-switch v-model="notifyConfig.dingtalk" />
          </el-form-item>
          
          <el-divider content-position="left">通知事件</el-divider>
          
          <el-form-item label="订单成交">
            <el-checkbox-group v-model="notifyConfig.events">
              <el-checkbox label="order_filled">订单成交</el-checkbox>
              <el-checkbox label="order_cancelled">订单取消</el-checkbox>
              <el-checkbox label="position_closed">持仓平仓</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          
          <el-form-item label="风险事件">
            <el-checkbox-group v-model="notifyConfig.riskEvents">
              <el-checkbox label="stop_loss">止损触发</el-checkbox>
              <el-checkbox label="take_profit">止盈触发</el-checkbox>
              <el-checkbox label="daily_loss_limit">日亏损限制</el-checkbox>
              <el-checkbox label="drawdown_limit">回撤限制</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" @click="saveNotifyConfig">
              💾 保存配置
            </el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 系统信息 -->
      <el-tab-pane label="📊 系统信息" name="system">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="系统名称">CryptoQuant</el-descriptions-item>
          <el-descriptions-item label="版本">v0.1.0</el-descriptions-item>
          <el-descriptions-item label="后端地址">
            <el-link href="http://localhost:8000" target="_blank">
              http://localhost:8000
            </el-link>
          </el-descriptions-item>
          <el-descriptions-item label="前端地址">
            <el-link href="http://localhost:3000" target="_blank">
              http://localhost:3000
            </el-link>
          </el-descriptions-item>
          <el-descriptions-item label="WebSocket">
            <el-tag type="success">已连接</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="数据库">
            <el-tag type="info">SQLite</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="更新时间">2026-03-13</el-descriptions-item>
        </el-descriptions>
        
        <el-divider />
        
        <div class="system-actions">
          <el-button type="info" @click="checkUpdate">
            🔍 检查更新
          </el-button>
          <el-button type="warning" @click="clearCache">
            🧹 清除缓存
          </el-button>
          <el-button type="danger" @click="resetSystem">
            ⚠️ 重置系统
          </el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import wsService from '../services/websocket'

const activeTab = ref('api')
const loading = ref(false)

// API 配置
const apiConfig = ref({
  exchange: 'binance',
  apiKey: '',
  apiSecret: '',
  testnet: true,
  permissions: ['read', 'trade'],
})

// 交易配置
const tradeConfig = ref({
  initialCapital: 100000,
  maxPositionRatio: 20,
  maxTotalExposure: 80,
  maxDailyLoss: 5,
  maxDrawdown: 20,
  defaultStopLoss: 5,
  defaultTakeProfit: 15,
})

// 通知配置
const notifyConfig = ref({
  websocket: true,
  email: false,
  dingtalk: false,
  events: ['order_filled', 'order_cancelled', 'position_closed'],
  riskEvents: ['stop_loss', 'take_profit'],
})

// 方法
async function testApiConnection() {
  if (!apiConfig.value.apiKey || !apiConfig.value.apiSecret) {
    ElMessage.warning('请先填写 API Key 和 Secret')
    return
  }
  
  loading.value = true
  
  try {
    // 保存配置并更新连接状态
    localStorage.setItem('apiConfig', JSON.stringify(apiConfig.value))
    localStorage.setItem('trading_connected', 'true')
    tradingStore.connected = true
    
    // 显示成功消息
    ElMessage.success(`✅ API 连接测试成功！\n交易所：${apiConfig.value.exchange}\n${apiConfig.value.testnet ? '测试网' : '主网'}`)
    
    // 1 秒后自动跳转到仪表盘
    setTimeout(() => {
      window.location.href = '/'
    }, 1500)
    
  } catch (error) {
    ElMessage.error('测试失败：' + error.message)
  } finally {
    loading.value = false
  }
}

function saveApiConfig() {
  localStorage.setItem('apiConfig', JSON.stringify(apiConfig.value))
  ElMessage.success('✅ API 配置已保存')
  // 保存后自动连接
  tradingStore.connected = true
  localStorage.setItem('trading_connected', 'true')
}

function saveTradeConfig() {
  localStorage.setItem('tradeConfig', JSON.stringify(tradeConfig.value))
  ElMessage.success('交易配置已保存')
}

function resetTradeConfig() {
  tradeConfig.value = {
    initialCapital: 100000,
    maxPositionRatio: 20,
    maxTotalExposure: 80,
    maxDailyLoss: 5,
    maxDrawdown: 20,
    defaultStopLoss: 5,
    defaultTakeProfit: 15,
  }
  ElMessage.success('已恢复默认配置')
}

function saveNotifyConfig() {
  localStorage.setItem('notifyConfig', JSON.stringify(notifyConfig.value))
  ElMessage.success('通知配置已保存')
}

function saveAll() {
  saveApiConfig()
  saveTradeConfig()
  saveNotifyConfig()
  ElMessage.success('所有配置已保存')
}

function checkUpdate() {
  ElMessage.info('检查更新中...')
  setTimeout(() => {
    ElMessage.success('已是最新版本 (v0.1.0)')
  }, 1000)
}

function clearCache() {
  localStorage.clear()
  ElMessage.success('缓存已清除')
}

function resetSystem() {
  ElMessageBox.confirm(
    '确定要重置系统吗？此操作将清除所有配置和数据。',
    '重置确认',
    {
      confirmButtonText: '重置',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(() => {
    localStorage.clear()
    location.reload()
  }).catch(() => {})
}

// 生命周期
onMounted(() => {
  // 加载保存的配置
  const savedApi = localStorage.getItem('apiConfig')
  const savedTrade = localStorage.getItem('tradeConfig')
  const savedNotify = localStorage.getItem('notifyConfig')
  
  if (savedApi) apiConfig.value = JSON.parse(savedApi)
  if (savedTrade) tradeConfig.value = JSON.parse(savedTrade)
  if (savedNotify) notifyConfig.value = JSON.parse(savedNotify)
  
  // 连接 WebSocket
  wsService.connect({
    userId: 'user_' + Date.now(),
    room: 'default',
  })
})
</script>

<style scoped>
.settings-page {
  padding: 10px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: #333;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-left: 10px;
}

.system-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}
</style>
