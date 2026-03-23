<!--
登录页面
-->

<template>
  <div class="login-page-wrapper">
    <div class="login-page">
      <div class="login-card">
        <div class="logo">
          <h1>CryptoQuant</h1>
          <p>量化交易系统</p>
        </div>
        
        <form @submit.prevent="handleLogin" class="login-form">
          <div class="form-group">
            <label>用户名</label>
            <input 
              type="text" 
              v-model="username"
              placeholder="请输入用户名"
              required
            />
          </div>
          
          <div class="form-group">
            <label>密码</label>
            <input 
              type="password" 
              v-model="password"
              placeholder="请输入密码"
              required
            />
          </div>
          
          <div class="form-group">
            <label>
              <input type="checkbox" v-model="rememberMe" />
              记住我
            </label>
          </div>
          
          <button type="submit" class="login-btn" :disabled="loading">
            {{ loading ? '登录中...' : '登录' }}
          </button>
          
          <div class="links">
            <router-link to="/register">注册账号</router-link>
            <a href="#">忘记密码？</a>
          </div>
        </form>
        
        <div v-if="error" class="error-message">
          {{ error }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client.js'

const router = useRouter()

const username = ref('')
const password = ref('')
const rememberMe = ref(false)
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  loading.value = true
  error.value = ''
  
  try {
    const result = await api.auth.login({
      username: username.value,
      password: password.value,
    })
    
    console.log('登录成功:', result)
    
    // 保存 session (兼容两种响应格式)
    const sessionId = result.session_id || result.sessionId
    if (!sessionId) {
      throw new Error('未返回会话 ID')
    }
    localStorage.setItem('session_id', sessionId)
    
    // 跳转到首页
    setTimeout(() => {
      router.push('/')
    }, 200)
    
  } catch (err) {
    console.error('登录失败:', err)
    error.value = err.response?.data?.detail || '登录失败，请检查网络连接'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-page {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-card {
  background: white;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.2);
  width: 100%;
  max-width: 400px;
}

.logo {
  text-align: center;
  margin-bottom: 30px;
}

.logo h1 {
  margin: 0;
  font-size: 28px;
  color: #333;
}

.logo p {
  margin: 10px 0 0 0;
  color: #666;
  font-size: 14px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-weight: bold;
  color: #333;
  font-size: 14px;
}

.form-group input[type="text"],
.form-group input[type="password"] {
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.form-group input[type="checkbox"] {
  margin-right: 8px;
}

.login-btn {
  padding: 14px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: background 0.2s;
}

.login-btn:hover {
  background: #5568d3;
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.links {
  display: flex;
  justify-content: space-between;
  gap: 15px;
  margin-top: 10px;
}

.links a {
  color: #667eea;
  text-decoration: none;
  font-size: 14px;
}

.links a:hover {
  text-decoration: underline;
}

.error-message {
  margin-top: 20px;
  padding: 12px;
  background: #f8d7da;
  color: #721c24;
  border-radius: 6px;
  text-align: center;
}
</style>
