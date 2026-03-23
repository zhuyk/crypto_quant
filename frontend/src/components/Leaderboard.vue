<!--
交易员排行榜组件
-->

<template>
  <div class="leaderboard">
    <h3>交易员排行榜</h3>
    
    <!-- 筛选器 -->
    <div class="filters">
      <select v-model="sortBy">
        <option value="total_return">按收益</option>
        <option value="sharpe_ratio">按 Sharpe</option>
        <option value="win_rate">按胜率</option>
        <option value="follower_count">按粉丝</option>
      </select>
      
      <select v-model="timePeriod">
        <option value="all">全部时间</option>
        <option value="7d">最近 7 天</option>
        <option value="30d">最近 30 天</option>
        <option value="90d">最近 90 天</option>
      </select>
    </div>

    <!-- 排行榜列表 -->
    <div class="leaderboard-list">
      <div 
        v-for="(trader, index) in traders" 
        :key="trader.trader_id"
        class="trader-card"
        :class="{ 'top-3': index < 3 }"
      >
        <div class="rank" :class="getRankClass(index)">
          {{ getRankIcon(index) }}
        </div>
        
        <div class="trader-info">
          <div class="trader-name">{{ trader.trader_name }}</div>
          <div class="trader-stats">
            <span>收益：{{ formatPercent(trader.total_return) }}</span>
            <span>胜率：{{ formatPercent(trader.win_rate) }}</span>
            <span>粉丝：{{ trader.follower_count }}</span>
          </div>
        </div>
        
        <div class="trader-metrics">
          <div class="metric">
            <div class="metric-label">Sharpe</div>
            <div class="metric-value">{{ trader.sharpe_ratio?.toFixed(2) || '0.00' }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">回撤</div>
            <div class="metric-value down">{{ formatPercent(trader.max_drawdown) }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">AUM</div>
            <div class="metric-value">{{ formatMoney(trader.aum) }}</div>
          </div>
        </div>
        
        <button 
          class="follow-btn"
          @click="followTrader(trader.trader_id)"
        >
          {{ trader.isFollowing ? '已关注' : '+ 关注' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'

// 状态
const sortBy = ref('total_return')
const timePeriod = ref('all')
const traders = ref([])

// 方法
const formatPercent = (value) => {
  if (value === null || value === undefined) return '0.00%'
  return (value * 100).toFixed(2) + '%'
}

const formatMoney = (value) => {
  if (value === null || value === undefined) return '$0'
  if (value >= 1000000) {
    return '$' + (value / 1000000).toFixed(2) + 'M'
  }
  if (value >= 1000) {
    return '$' + (value / 1000).toFixed(2) + 'K'
  }
  return '$' + value.toFixed(2)
}

const getRankClass = (index) => {
  if (index === 0) return 'gold'
  if (index === 1) return 'silver'
  if (index === 2) return 'bronze'
  return ''
}

const getRankIcon = (index) => {
  if (index === 0) return '🥇'
  if (index === 1) return '🥈'
  if (index === 2) return '🥉'
  return `#${index + 1}`
}

const loadLeaderboard = async () => {
  try {
    const response = await fetch(`/api/v1/social/leaderboard?metric=${sortBy.value}&period=${timePeriod.value}&limit=100`)
    const data = await response.json()
    
    // 检查是否已关注
    const following = await loadFollowing()
    
    traders.value = (data.ranking || []).map((item, index) => ({
      trader_id: item[0],
      ...getTraderStats(item[0]),
      isFollowing: following.includes(item[0]),
      rank: index + 1,
    }))
  } catch (error) {
    console.error('加载排行榜失败:', error)
  }
}

const getTraderStats = (traderId) => {
  // 从 store 或缓存获取交易员详细数据
  return {
    trader_name: `Trader ${traderId.slice(0, 6)}`,
    total_return: Math.random() * 2 - 0.5,
    sharpe_ratio: Math.random() * 3,
    win_rate: Math.random() * 0.3 + 0.5,
    follower_count: Math.floor(Math.random() * 1000),
    max_drawdown: Math.random() * 0.2,
    aum: Math.random() * 1000000,
  }
}

const loadFollowing = async () => {
  // 加载已关注的交易员列表
  return []
}

const followTrader = async (traderId) => {
  try {
    const response = await fetch('/api/v1/social/follow', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        trader_id: traderId,
        copy_ratio: 0.5,
        max_position: 5000,
      }),
    })
    
    const result = await response.json()
    
    if (result.success) {
      const trader = traders.value.find(t => t.trader_id === traderId)
      if (trader) {
        trader.isFollowing = !trader.isFollowing
        trader.follower_count += trader.isFollowing ? 1 : -1
      }
    }
  } catch (error) {
    console.error('关注交易员失败:', error)
  }
}

// 监听筛选器变化
watch([sortBy, timePeriod], loadLeaderboard)

// 生命周期
onMounted(() => {
  loadLeaderboard()
})
</script>

<style scoped>
.leaderboard {
  padding: 20px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.filters select {
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.leaderboard-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.trader-card {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  transition: transform 0.2s;
}

.trader-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.trader-card.top-3 {
  background: linear-gradient(135deg, #f8f9fa 0%, #fff 100%);
  border: 1px solid #e9ecef;
}

.rank {
  font-size: 24px;
  font-weight: bold;
  width: 50px;
  text-align: center;
}

.rank.gold {
  color: #ffd700;
}

.rank.silver {
  color: #c0c0c0;
}

.rank.bronze {
  color: #cd7f32;
}

.trader-info {
  flex: 1;
}

.trader-name {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 5px;
}

.trader-stats {
  display: flex;
  gap: 15px;
  font-size: 14px;
  color: #666;
}

.trader-metrics {
  display: flex;
  gap: 20px;
}

.metric {
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 5px;
}

.metric-value {
  font-size: 16px;
  font-weight: bold;
}

.down {
  color: #dc3545;
}

.follow-btn {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  transition: background 0.2s;
}

.follow-btn:hover {
  background: #0056b3;
}

.follow-btn:disabled {
  background: #6c757d;
  cursor: not-allowed;
}
</style>
