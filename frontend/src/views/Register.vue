<!--
注册页面
-->

<template>
  <div class="register-page">
    <div class="register-card">
      <div class="logo">
        <h1>CryptoQuant</h1>
        <p>量化交易系统</p>
      </div>
      
      <form @submit.prevent="handleRegister" class="register-form">
        <div class="form-group">
          <label>用户名</label>
          <input 
            type="text" 
            v-model="username"
            placeholder="请输入用户名"
            required
            minlength="3"
          />
        </div>
        
        <div class="form-group">
          <label>邮箱</label>
          <input 
            type="email" 
            v-model="email"
            placeholder="请输入邮箱"
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
            minlength="6"
          />
        </div>
        
        <div class="form-group">
          <label>确认密码</label>
          <input 
            type="password" 
            v-model="confirmPassword"
            placeholder="请再次输入密码"
            required
            minlength="6"
          />
        </div>
        
        <div class="form-group">
          <label>
            <input type="checkbox" v-model="agreeTerms" required />
            我已阅读并同意 <a href="#">服务条款</a> 和 <a href="#">隐私政策</a>
          </label>
        </div>
        
        <button type="submit" class="register-btn" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
        
        <div class="links">
          已有账号？<router-link to="/login">立即登录</router-link>
        </div>
      </form>
      
      <div v-if="error" class="error-message">
        {{ error }}
      </div>
      
      <div v-if="success" class="success-message">
        注册成功！即将跳转到登录页面...
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
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const agreeTerms = ref(false)
const loading = ref(false)
const error = ref('')
const success = ref(false)

const handleRegister = async () => {
  // 验证密码
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    await api.auth.register({
      username: username.value,
      email: email.value,
      password: password.value,
    })
    
    success.value = true
    
    // 3 秒后跳转到登录
    setTimeout(() => {
      router.push('/login')
    }, 3000)
    
  } catch (err) {
    error.value = err.response?.data?.detail || '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-card {
  background: white;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.2);
  width: 100%;
  max-width: 450px;
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

.register-form {
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
.form-group input[type="email"],
.form-group input[type="password"] {
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.form-group input[type="checkbox"] {
  margin-right: 8px;
}

.form-group a {
  color: #667eea;
  text-decoration: none;
}

.form-group a:hover {
  text-decoration: underline;
}

.register-btn {
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

.register-btn:hover {
  background: #5568d3;
}

.register-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.links {
  text-align: center;
  margin-top: 10px;
  color: #666;
  font-size: 14px;
}

.links a {
  color: #667eea;
  text-decoration: none;
  font-weight: bold;
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

.success-message {
  margin-top: 20px;
  padding: 12px;
  background: #d4edda;
  color: #155724;
  border-radius: 6px;
  text-align: center;
}
</style>
