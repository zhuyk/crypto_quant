<!--
社交跟单页面
-->

<template>
  <div class="social-page">
    <div class="social-container">
      <h2>社交跟单</h2>
      
      <div class="social-content">
        <!-- 排行榜 -->
        <div class="leaderboard-section">
          <Leaderboard />
        </div>
        
        <!-- 我的跟单 -->
        <div class="my-following-section">
          <h3>我的跟单</h3>
          <div class="following-list">
            <div 
              v-for="following in myFollowings" 
              :key="following.trader_id"
              class="following-card"
            >
              <div class="trader-info">
                <div class="trader-name">{{ following.trader_name }}</div>
                <div class="copy-ratio">复制比例：{{ following.copy_ratio * 100 }}%</div>
              </div>
              
              <div class="performance">
                <div class="pnl" :class="following.total_pnl >= 0 ? 'up' : 'down'">
                  {{ following.total_pnl }} USDT
                </div>
              </div>
              
              <button @click="unfollow(following.trader_id)" class="unfollow-btn">
                取消关注
              </button>
            </div>
            <div v-if="myFollowings.length === 0" class="empty">
              暂无关注的交易员
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Leaderboard from '@/components/Leaderboard.vue'
import { api } from '@/api/client.js'

const myFollowings = ref([])

const loadMyFollowings = async () => {
  try {
    const data = await api.social.myFollowings()
    myFollowings.value = data.followings || []
  } catch (error) {
    console.error('加载关注列表失败:', error)
  }
}

const unfollow = async (traderId) => {
  if (!confirm('确定要取消关注吗？')) return
  
  try {
    await api.social.unfollow(traderId)
    await loadMyFollowings()
  } catch (error) {
    console.error('取消关注失败:', error)
  }
}

onMounted(() => {
  loadMyFollowings()
})
</script>

<style scoped>
.social-page {
  height: 100%;
}

.social-container {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.social-container h2 {
  margin: 0 0 30px 0;
  color: #333;
}

.social-content {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 30px;
}

.leaderboard-section {
  border-right: 1px solid #eee;
  padding-right: 30px;
}

.my-following-section h3 {
  margin: 0 0 20px 0;
  color: #333;
}

.following-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.following-card {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.trader-info {
  flex: 1;
}

.trader-name {
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
}

.copy-ratio {
  font-size: 12px;
  color: #666;
}

.performance {
  text-align: right;
}

.pnl {
  font-size: 18px;
  font-weight: bold;
}

.up {
  color: #28a745;
}

.down {
  color: #dc3545;
}

.unfollow-btn {
  padding: 8px 15px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.unfollow-btn:hover {
  background: #5a6268;
}

.empty {
  text-align: center;
  color: #999;
  padding: 40px;
}
</style>
