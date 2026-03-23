<!--
404 页面
-->

<template>
  <div class="not-found-page">
    <div class="content">
      <div class="error-code">404</div>
      <h1>页面未找到</h1>
      <p>抱歉，您访问的页面不存在或已被移除</p>
      <div class="actions">
        <router-link to="/" class="btn-home">返回首页</router-link>
        <button @click="goBack" class="btn-back">返回上一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.not-found-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.content {
  text-align: center;
  padding: 40px;
}

.error-code {
  font-size: 120px;
  font-weight: bold;
  margin-bottom: 20px;
  text-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

h1 {
  font-size: 32px;
  margin: 0 0 20px 0;
}

p {
  font-size: 16px;
  opacity: 0.9;
  margin-bottom: 40px;
}

.actions {
  display: flex;
  gap: 20px;
  justify-content: center;
}

.btn-home,
.btn-back {
  padding: 14px 30px;
  border-radius: 6px;
  font-size: 16px;
  font-weight: bold;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-home {
  background: white;
  color: #667eea;
}

.btn-home:hover {
  background: #f8f9fa;
  transform: translateY(-2px);
}

.btn-back {
  background: transparent;
  color: white;
  border: 2px solid white;
}

.btn-back:hover {
  background: rgba(255,255,255,0.1);
  transform: translateY(-2px);
}
</style>
