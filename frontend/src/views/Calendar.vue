<!--
日历提醒页面
支持: 月历视图、提醒列表、快捷创建、价格/费率提醒模板
-->

<template>
  <div class="calendar-page">
    <div class="page-header">
      <h2>📅 日历提醒</h2>
      <div class="header-actions">
        <button class="btn btn-primary" @click="showCreateModal = true">+ 新建提醒</button>
        <button class="btn btn-outline" @click="showPriceAlert = true">💰 价格提醒</button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ stats.active }}</span>
        <span class="stat-label">活跃提醒</span>
      </div>
      <div class="stat-card warning">
        <span class="stat-value">{{ stats.upcoming_24h }}</span>
        <span class="stat-label">24h 内到期</span>
      </div>
      <div class="stat-card success">
        <span class="stat-value">{{ stats.triggered_today }}</span>
        <span class="stat-label">今日已触发</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ stats.total }}</span>
        <span class="stat-label">总计</span>
      </div>
    </div>


    <!-- 月历 + 列表 双栏布局 -->
    <div class="calendar-layout">
      <!-- 左: 月历 -->
      <div class="calendar-panel">
        <div class="cal-header">
          <button @click="prevMonth">&lt;</button>
          <h3>{{ currentYear }}年 {{ currentMonth }}月</h3>
          <button @click="nextMonth">&gt;</button>
        </div>
        <div class="cal-weekdays">
          <span v-for="d in weekdays" :key="d">{{ d }}</span>
        </div>
        <div class="cal-grid">
          <div
            v-for="(day, idx) in calendarDays"
            :key="idx"
            class="cal-day"
            :class="{
              'other-month': !day.currentMonth,
              'today': day.isToday,
              'has-reminder': day.reminders > 0,
              'selected': day.dateStr === selectedDate,
            }"
            @click="selectDate(day)"
          >
            <span class="day-num">{{ day.day }}</span>
            <span v-if="day.reminders > 0" class="day-dot">{{ day.reminders }}</span>
          </div>
        </div>
      </div>

      <!-- 右: 提醒列表 -->
      <div class="reminder-panel">
        <h3>{{ selectedDate || '即将到来' }} 的提醒</h3>
        <div class="reminder-list">
          <div v-if="filteredReminders.length === 0" class="empty">暂无提醒</div>
          <div
            v-for="r in filteredReminders"
            :key="r.id"
            class="reminder-item"
            :class="[r.priority, { triggered: r.is_triggered }]"
          >
            <div class="reminder-icon">{{ typeIcon(r.reminder_type) }}</div>
            <div class="reminder-body">
              <div class="reminder-title">{{ r.title }}</div>
              <div class="reminder-meta">
                <span>{{ formatTime(r.remind_at) }}</span>
                <span class="tag" :class="r.priority">{{ r.priority }}</span>
                <span v-if="r.repeat_rule !== 'none'" class="tag repeat">🔁 {{ r.repeat_rule }}</span>
              </div>
            </div>
            <div class="reminder-actions">
              <button v-if="!r.is_triggered" @click="dismissReminder(r.id)" title="关闭">✓</button>
              <button @click="deleteReminder(r.id)" title="删除">✕</button>
            </div>
          </div>
        </div>
      </div>
    </div>


    <!-- 创建提醒弹窗 -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <h3>新建提醒</h3>
        <form @submit.prevent="createReminder">
          <div class="form-group">
            <label>标题</label>
            <input v-model="form.title" required placeholder="输入提醒标题" />
          </div>
          <div class="form-group">
            <label>提醒时间</label>
            <input v-model="form.remind_at" type="datetime-local" required />
          </div>
          <div class="form-group">
            <label>类型</label>
            <select v-model="form.reminder_type">
              <option value="custom">自定义</option>
              <option value="rebalance">再平衡</option>
              <option value="expiry">合约到期</option>
              <option value="report">报告</option>
            </select>
          </div>
          <div class="form-group">
            <label>优先级</label>
            <select v-model="form.priority">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="critical">紧急</option>
            </select>
          </div>
          <div class="form-group">
            <label>重复</label>
            <select v-model="form.repeat_rule">
              <option value="none">不重复</option>
              <option value="daily">每天</option>
              <option value="weekly">每周</option>
              <option value="monthly">每月</option>
            </select>
          </div>
          <div class="form-group">
            <label>描述 (可选)</label>
            <textarea v-model="form.description" rows="2" placeholder="备注..."></textarea>
          </div>
          <div class="modal-actions">
            <button type="button" @click="showCreateModal = false">取消</button>
            <button type="submit" class="btn-primary">创建</button>
          </div>
        </form>
      </div>
    </div>


    <!-- 价格提醒弹窗 -->
    <div v-if="showPriceAlert" class="modal-overlay" @click.self="showPriceAlert = false">
      <div class="modal">
        <h3>💰 创建价格提醒</h3>
        <form @submit.prevent="createPriceAlert">
          <div class="form-group">
            <label>交易对</label>
            <select v-model="priceForm.symbol">
              <option value="BTCUSDT">BTC/USDT</option>
              <option value="ETHUSDT">ETH/USDT</option>
              <option value="BNBUSDT">BNB/USDT</option>
              <option value="SOLUSDT">SOL/USDT</option>
              <option value="XRPUSDT">XRP/USDT</option>
            </select>
          </div>
          <div class="form-group">
            <label>目标价格 (USDT)</label>
            <input v-model.number="priceForm.target_price" type="number" step="0.01" required />
          </div>
          <div class="form-group">
            <label>条件</label>
            <select v-model="priceForm.condition">
              <option value="above">价格突破 (≥)</option>
              <option value="below">价格跌破 (≤)</option>
            </select>
          </div>
          <div class="modal-actions">
            <button type="button" @click="showPriceAlert = false">取消</button>
            <button type="submit" class="btn-primary">创建</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import apiClient from '@/api/client'

// === State ===
const stats = ref({ active: 0, upcoming_24h: 0, triggered_today: 0, total: 0 })
const reminders = ref([])
const calendarData = ref({})
const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth() + 1)
const selectedDate = ref(null)
const showCreateModal = ref(false)
const showPriceAlert = ref(false)

const form = ref({
  title: '', description: '', remind_at: '',
  reminder_type: 'custom', priority: 'medium', repeat_rule: 'none',
})
const priceForm = ref({ symbol: 'BTCUSDT', target_price: 0, condition: 'above' })

const weekdays = ['日', '一', '二', '三', '四', '五', '六']

// === Computed ===
const calendarDays = computed(() => {
  const days = []
  const firstDay = new Date(currentYear.value, currentMonth.value - 1, 1)
  const lastDay = new Date(currentYear.value, currentMonth.value, 0)
  const startWeekday = firstDay.getDay()
  const totalDays = lastDay.getDate()
  const today = new Date().toISOString().slice(0, 10)

  // 上月填充
  const prevLast = new Date(currentYear.value, currentMonth.value - 1, 0).getDate()
  for (let i = startWeekday - 1; i >= 0; i--) {
    const d = prevLast - i
    days.push({ day: d, currentMonth: false, dateStr: null, reminders: 0, isToday: false })
  }
  // 当月
  for (let d = 1; d <= totalDays; d++) {
    const dateStr = `${currentYear.value}-${String(currentMonth.value).padStart(2,'0')}-${String(d).padStart(2,'0')}`
    const dayReminders = calendarData.value[dateStr] || []
    days.push({
      day: d, currentMonth: true, dateStr,
      reminders: dayReminders.length, isToday: dateStr === today,
    })
  }
  // 下月填充
  const remaining = 42 - days.length
  for (let d = 1; d <= remaining; d++) {
    days.push({ day: d, currentMonth: false, dateStr: null, reminders: 0, isToday: false })
  }
  return days
})

const filteredReminders = computed(() => {
  if (selectedDate.value) {
    return calendarData.value[selectedDate.value] || []
  }
  return reminders.value.slice(0, 10)
})


// === Methods ===
const loadStats = async () => {
  try {
    const data = await apiClient.get('/reminders/stats')
    stats.value = data.stats || data
  } catch (e) { console.error('加载统计失败:', e) }
}

const loadCalendar = async () => {
  try {
    const data = await apiClient.get('/reminders/calendar', {
      params: { year: currentYear.value, month: currentMonth.value }
    })
    calendarData.value = data.days || {}
  } catch (e) { console.error('加载日历失败:', e) }
}

const loadUpcoming = async () => {
  try {
    const data = await apiClient.get('/reminders/upcoming', { params: { hours: 72 } })
    reminders.value = data.reminders || []
  } catch (e) { console.error('加载提醒失败:', e) }
}

const createReminder = async () => {
  try {
    const remindAt = new Date(form.value.remind_at).toISOString()
    await apiClient.post('/reminders/create', { ...form.value, remind_at: remindAt })
    showCreateModal.value = false
    form.value = { title: '', description: '', remind_at: '', reminder_type: 'custom', priority: 'medium', repeat_rule: 'none' }
    await refresh()
  } catch (e) { alert('创建失败: ' + (e.message || e)) }
}

const createPriceAlert = async () => {
  try {
    await apiClient.post('/reminders/template/price_alert', priceForm.value)
    showPriceAlert.value = false
    await refresh()
  } catch (e) { alert('创建失败: ' + (e.message || e)) }
}

const dismissReminder = async (id) => {
  try {
    await apiClient.post(`/reminders/${id}/dismiss`)
    await refresh()
  } catch (e) { console.error('关闭提醒失败:', e) }
}

const deleteReminder = async (id) => {
  if (!confirm('确定删除此提醒？')) return
  try {
    await apiClient.delete(`/reminders/${id}`)
    await refresh()
  } catch (e) { console.error('删除失败:', e) }
}

const selectDate = (day) => {
  if (day.currentMonth && day.dateStr) selectedDate.value = day.dateStr
}
const prevMonth = () => {
  if (currentMonth.value === 1) { currentMonth.value = 12; currentYear.value-- }
  else currentMonth.value--
}
const nextMonth = () => {
  if (currentMonth.value === 12) { currentMonth.value = 1; currentYear.value++ }
  else currentMonth.value++
}
const formatTime = (iso) => iso ? new Date(iso).toLocaleString('zh-CN') : '-'
const typeIcon = (type) => {
  const icons = { price_alert: '💰', funding_rate: '📊', rebalance: '⚖️', expiry: '⏰', report: '📧', custom: '📌' }
  return icons[type] || '📌'
}
const refresh = async () => { await Promise.all([loadStats(), loadCalendar(), loadUpcoming()]) }

// === Lifecycle ===
watch([currentYear, currentMonth], () => { loadCalendar() })
onMounted(() => { refresh() })
</script>


<style scoped>
.calendar-page { display: flex; flex-direction: column; gap: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h2 { margin: 0; font-size: 22px; }
.header-actions { display: flex; gap: 10px; }

.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card { background: white; padding: 18px; border-radius: 10px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.stat-card .stat-value { display: block; font-size: 28px; font-weight: bold; color: #333; }
.stat-card .stat-label { font-size: 13px; color: #888; }
.stat-card.warning .stat-value { color: #f0ad4e; }
.stat-card.success .stat-value { color: #28a745; }

.calendar-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }

/* 月历 */
.calendar-panel { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.cal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.cal-header h3 { margin: 0; font-size: 16px; }
.cal-header button { background: none; border: 1px solid #ddd; border-radius: 4px; padding: 4px 10px; cursor: pointer; }
.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; font-size: 12px; color: #999; margin-bottom: 8px; }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cal-day { position: relative; aspect-ratio: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 8px; cursor: pointer; font-size: 14px; transition: all 0.2s; }
.cal-day:hover { background: #f0f7ff; }
.cal-day.other-month { color: #ccc; }
.cal-day.today { background: #e8f5e9; font-weight: bold; }
.cal-day.selected { background: #1976d2; color: white; }
.cal-day.has-reminder .day-dot { position: absolute; bottom: 4px; background: #f0ad4e; color: white; font-size: 10px; width: 16px; height: 16px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }


/* 提醒列表 */
.reminder-panel { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.reminder-panel h3 { margin: 0 0 16px; font-size: 16px; }
.reminder-list { display: flex; flex-direction: column; gap: 10px; max-height: 500px; overflow-y: auto; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.reminder-item { display: flex; align-items: center; gap: 12px; padding: 12px; border-radius: 8px; background: #fafafa; transition: all 0.2s; }
.reminder-item:hover { background: #f0f7ff; }
.reminder-item.triggered { opacity: 0.5; text-decoration: line-through; }
.reminder-icon { font-size: 20px; }
.reminder-body { flex: 1; }
.reminder-title { font-weight: 600; font-size: 14px; color: #333; }
.reminder-meta { display: flex; gap: 8px; margin-top: 4px; font-size: 12px; color: #888; align-items: center; }
.tag { padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.tag.high { background: #fff3cd; color: #856404; }
.tag.critical { background: #f8d7da; color: #721c24; }
.tag.medium { background: #d1ecf1; color: #0c5460; }
.tag.low { background: #d4edda; color: #155724; }
.tag.repeat { background: #e2e3e5; color: #383d41; }
.reminder-actions button { background: none; border: none; cursor: pointer; font-size: 16px; opacity: 0.5; }
.reminder-actions button:hover { opacity: 1; }

/* 弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; padding: 28px; border-radius: 14px; width: 420px; max-width: 90vw; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.modal h3 { margin: 0 0 20px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; color: #666; margin-bottom: 4px; }
.form-group input, .form-group select, .form-group textarea { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

/* 按钮 */
.btn { padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-size: 14px; }
.btn-primary, button.btn-primary { background: #1976d2; color: white; }
.btn-primary:hover { background: #1565c0; }
.btn-outline { background: white; border: 1px solid #ddd; color: #333; }
.btn-outline:hover { background: #f5f5f5; }

@media (max-width: 768px) {
  .calendar-layout { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
