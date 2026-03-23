<!--
主布局组件
-->

<template>
  <div class="app-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="logo">
        <h1 v-if="!sidebarCollapsed">CryptoQuant</h1>
        <span v-else>CQ</span>
      </div>
      
      <nav class="nav-menu">
        <router-link to="/" class="nav-item">
          <span class="icon">📊</span>
          <span v-if="!sidebarCollapsed">仪表盘</span>
        </router-link>
        
        <router-link to="/trade" class="nav-item">
          <span class="icon">💹</span>
          <span v-if="!sidebarCollapsed">交易</span>
        </router-link>
        
        <router-link to="/backtest" class="nav-item">
          <span class="icon">📈</span>
          <span v-if="!sidebarCollapsed">回测</span>
        </router-link>
        
        <router-link to="/strategies" class="nav-item">
          <span class="icon">🤖</span>
          <span v-if="!sidebarCollapsed">策略</span>
        </router-link>
        
        <router-link to="/marketplace" class="nav-item">
          <span class="icon">🏪</span>
          <span v-if="!sidebarCollapsed">市场</span>
        </router-link>
        
        <router-link to="/social" class="nav-item">
          <span class="icon">👥</span>
          <span v-if="!sidebarCollapsed">社交</span>
        </router-link>
        
        <router-link to="/account" class="nav-item">
          <span class="icon">👤</span>
          <span v-if="!sidebarCollapsed">账户</span>
        </router-link>
        
        <router-link to="/exchange-keys" class="nav-item">
          <span class="icon">🔑</span>
          <span v-if="!sidebarCollapsed">交易所</span>
        </router-link>
        
        <router-link to="/data" class="nav-item">
          <span class="icon">📁</span>
          <span v-if="!sidebarCollapsed">数据</span>
        </router-link>
        
        <router-link to="/arbitrage" class="nav-item">
          <span class="icon">💰</span>
          <span v-if="!sidebarCollapsed">套利</span>
        </router-link>
      </nav>
      
      <div class="sidebar-footer">
        <button @click="toggleSidebar" class="collapse-btn">
          {{ sidebarCollapsed ? '→' : '←' }}
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 顶部导航栏 -->
      <header class="top-bar">
        <div class="left-section">
          <h2>{{ pageTitle }}</h2>
        </div>
        
        <div class="right-section">
          <!-- 通知 -->
          <div class="notification-icon" @click="showNotifications = !showNotifications">
            🔔
            <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
          </div>
          
          <!-- 用户菜单 -->
          <div class="user-menu">
            <div class="avatar" @click="showUserMenu = !showUserMenu">
              {{ userInitial }}
            </div>
            
            <div v-if="showUserMenu" class="user-dropdown">
              <div class="user-info">
                <div class="username">{{ currentUser?.username || 'User' }}</div>
                <div class="email">{{ currentUser?.email || '' }}</div>
              </div>
              
              <div class="menu-items">
                <router-link to="/account/profile">个人资料</router-link>
                <router-link to="/account/security">安全设置</router-link>
                <a @click="logout">退出登录</a>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- 内容区 -->
      <div class="content">
        <slot></slot>
      </div>
    </main>

    <!-- 通知面板 -->
    <div v-if="showNotifications" class="notification-panel" @click="showNotifications = false">
      <div class="panel-content" @click.stop>
        <h3>通知</h3>
        <div class="notification-list">
          <div v-if="notifications.length === 0" class="empty">
            暂无通知
          </div>
          <div 
            v-for="note in notifications" 
            :key="note.id"
            class="notification-item"
            :class="{ unread: !note.read }"
          >
            <div class="note-title">{{ note.title }}</div>
            <div class="note-time">{{ formatTime(note.time) }}</div>
          </div>
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

// 状态
const sidebarCollapsed = ref(false)
const showUserMenu = ref(false)
const showNotifications = ref(false)
const unreadCount = ref(0)
const notifications = ref([])
const currentUser = ref(null)

// 页面标题
const pageTitle = ref('CryptoQuant')

// 计算用户首字母
const userInitial = ref('U')

// 方法
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const loadUser = async () => {
  // 避免重复请求
  if (currentUser.value) return
  
  // 检查是否有 session
  const sessionId = localStorage.getItem('session_id')
  if (!sessionId) {
    console.log('未登录，跳过用户信息加载')
    return
  }
  
  try {
    console.log('加载用户信息...')
    currentUser.value = await api.auth.me()
    userInitial.value = currentUser.value?.username?.charAt(0).toUpperCase() || 'U'
    console.log('用户信息加载成功:', currentUser.value)
  } catch (error) {
    console.error('加载用户信息失败:', error)
    // 401 说明 session 失效，清除本地存储
    if (error.response?.status === 401) {
      localStorage.removeItem('session_id')
      router.push('/login')
    }
  }
}

const loadNotifications = async () => {
  // TODO: 加载通知
  notifications.value = [
    { id: 1, title: '订单成交：BTCUSDT 买入 0.1', time: Date.now() - 60000, read: false },
    { id: 2, title: '风控告警：回撤达到 5%', time: Date.now() - 3600000, read: false },
  ]
  unreadCount.value = notifications.value.filter(n => !n.read).length
}

const logout = async () => {
  try {
    await api.auth.logout()
    localStorage.removeItem('session_id')
    router.push('/login')
  } catch (error) {
    console.error('登出失败:', error)
    localStorage.removeItem('session_id')
    router.push('/login')
  }
}

const formatTime = (timestamp) => {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  return `${days}天前`
}

// 生命周期 - 确保只执行一次
const hasLoaded = ref(false)
onMounted(() => {
  // 确保只加载一次
  if (hasLoaded.value) return
  hasLoaded.value = true
  
  loadUser()
  loadNotifications()
  
  // 点击外部关闭菜单
  document.addEventListener('click', () => {
    showUserMenu.value = false
    showNotifications.value = false
  })
})
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}

.sidebar {
  width: 240px;
  background: #1a1a2e;
  color: white;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
}

.sidebar.collapsed {
  width: 60px;
}

.logo {
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.logo h1 {
  font-size: 20px;
  margin: 0;
}

.nav-menu {
  flex: 1;
  padding: 20px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  color: rgba(255,255,255,0.7);
  text-decoration: none;
  transition: all 0.2s;
}

.nav-item:hover {
  background: rgba(255,255,255,0.1);
  color: white;
}

.nav-item.router-link-active {
  background: #007bff;
  color: white;
}

.nav-item .icon {
  font-size: 20px;
  margin-right: 15px;
  width: 24px;
  text-align: center;
}

.sidebar.collapsed .nav-item span:not(.icon) {
  display: none;
}

.sidebar-footer {
  padding: 20px;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.collapse-btn {
  width: 100%;
  padding: 10px;
  background: rgba(255,255,255,0.1);
  border: none;
  color: white;
  cursor: pointer;
  border-radius: 4px;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.top-bar {
  height: 60px;
  background: white;
  border-bottom: 1px solid #e9ecef;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 30px;
}

.left-section h2 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.right-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.notification-icon {
  position: relative;
  font-size: 20px;
  cursor: pointer;
}

.notification-icon .badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background: #dc3545;
  color: white;
  font-size: 10px;
  padding: 2px 5px;
  border-radius: 10px;
}

.user-menu {
  position: relative;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #007bff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  cursor: pointer;
}

.user-dropdown {
  position: absolute;
  top: 50px;
  right: 0;
  width: 200px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  padding: 15px;
  z-index: 1000;
}

.user-info {
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
  margin-bottom: 10px;
}

.username {
  font-weight: bold;
  color: #333;
}

.email {
  font-size: 12px;
  color: #999;
}

.menu-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.menu-items a {
  color: #333;
  text-decoration: none;
  padding: 5px 0;
}

.menu-items a:hover {
  color: #007bff;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 30px;
}

.notification-panel {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  z-index: 999;
  display: flex;
  justify-content: flex-end;
}

.panel-content {
  width: 350px;
  background: white;
  padding: 20px;
  overflow-y: auto;
}

.panel-content h3 {
  margin: 0 0 20px 0;
}

.notification-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.notification-item {
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  cursor: pointer;
}

.notification-item.unread {
  background: #e7f3ff;
}

.note-title {
  font-size: 14px;
  color: #333;
  margin-bottom: 5px;
}

.note-time {
  font-size: 12px;
  color: #999;
}

.empty {
  text-align: center;
  color: #999;
  padding: 40px;
}
</style>
