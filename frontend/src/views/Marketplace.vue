<!--
策略市场页面
-->

<template>
  <div class="marketplace-page">
    <div class="marketplace-container">
      <h2>策略市场</h2>
      
      <!-- 筛选器 -->
      <div class="filters">
        <select v-model="filters.category">
          <option value="">全部分类</option>
          <option value="trend">趋势策略</option>
          <option value="mean_reversion">均值回归</option>
          <option value="arbitrage">套利策略</option>
          <option value="ml">机器学习</option>
        </select>
        
        <select v-model="filters.pricing">
          <option value="">全部价格</option>
          <option value="free">免费</option>
          <option value="paid">付费</option>
        </select>
        
        <select v-model="sortBy">
          <option value="rating">评分</option>
          <option value="downloads">下载量</option>
          <option value="created_at">最新</option>
        </select>
        
        <input 
          type="text" 
          v-model="searchQuery"
          placeholder="搜索策略..."
          class="search-input"
        />
      </div>
      
      <!-- 策略列表 -->
      <div class="strategies-grid">
        <div 
          v-for="strategy in filteredStrategies" 
          :key="strategy.id"
          class="strategy-card"
          @click="viewStrategy(strategy)"
        >
          <div class="strategy-header">
            <h3>{{ strategy.name }}</h3>
            <span class="category">{{ strategy.category }}</span>
          </div>
          
          <div class="strategy-description">
            {{ strategy.description }}
          </div>
          
          <div class="strategy-stats">
            <div class="stat">
              <span class="label">收益</span>
              <span class="value up">{{ formatPercent(strategy.performance?.total_return || 0) }}</span>
            </div>
            <div class="stat">
              <span class="label">Sharpe</span>
              <span class="value">{{ (strategy.performance?.sharpe_ratio || 0).toFixed(2) }}</span>
            </div>
            <div class="stat">
              <span class="label">回撤</span>
              <span class="value down">{{ formatPercent(strategy.performance?.max_drawdown || 0) }}</span>
            </div>
          </div>
          
          <div class="strategy-footer">
            <div class="strategy-meta">
              <span>⭐ {{ strategy.rating?.toFixed(1) || '0.0' }}</span>
              <span>📥 {{ strategy.downloads }}</span>
            </div>
            <div class="strategy-price">
              <span v-if="strategy.pricing_model === 'free'" class="free">免费</span>
              <span v-else class="paid">${{ strategy.price }}/月</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client.js'

const router = useRouter()

const strategies = ref([])
const searchQuery = ref('')
const sortBy = ref('rating')
const filters = ref({
  category: '',
  pricing: '',
})

const filteredStrategies = computed(() => {
  let result = [...strategies.value]
  
  // 搜索
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(s => 
      s.name.toLowerCase().includes(query) ||
      s.description.toLowerCase().includes(query)
    )
  }
  
  // 分类筛选
  if (filters.value.category) {
    result = result.filter(s => s.category === filters.value.category)
  }
  
  // 价格筛选
  if (filters.value.pricing) {
    if (filters.value.pricing === 'free') {
      result = result.filter(s => s.pricing_model === 'free')
    } else {
      result = result.filter(s => s.pricing_model !== 'free')
    }
  }
  
  // 排序
  if (sortBy.value === 'rating') {
    result.sort((a, b) => (b.rating || 0) - (a.rating || 0))
  } else if (sortBy.value === 'downloads') {
    result.sort((a, b) => (b.downloads || 0) - (a.downloads || 0))
  } else if (sortBy.value === 'created_at') {
    result.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  }
  
  return result
})

const loadStrategies = async () => {
  try {
    const data = await api.marketplace.strategies()
    strategies.value = data.strategies || []
  } catch (error) {
    console.error('加载策略失败:', error)
  }
}

const formatPercent = (value) => {
  return (value * 100).toFixed(2) + '%'
}

const viewStrategy = (strategy) => {
  router.push(`/marketplace/${strategy.id}`)
}

onMounted(() => {
  loadStrategies()
})
</script>

<style scoped>
.marketplace-page {
  height: 100%;
}

.marketplace-container {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.marketplace-container h2 {
  margin: 0 0 30px 0;
  color: #333;
}

.filters {
  display: flex;
  gap: 15px;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.filters select {
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.search-input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  min-width: 200px;
}

.strategies-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.strategy-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.strategy-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0,0,0,0.1);
}

.strategy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.strategy-header h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.category {
  padding: 4px 8px;
  background: #007bff;
  color: white;
  border-radius: 4px;
  font-size: 12px;
}

.strategy-description {
  color: #666;
  font-size: 14px;
  margin-bottom: 20px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.strategy-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}

.stat {
  text-align: center;
  padding: 10px;
  background: white;
  border-radius: 6px;
}

.stat .label {
  display: block;
  font-size: 12px;
  color: #999;
  margin-bottom: 5px;
}

.stat .value {
  display: block;
  font-size: 16px;
  font-weight: bold;
}

.up {
  color: #28a745;
}

.down {
  color: #dc3545;
}

.strategy-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 15px;
  border-top: 1px solid #dee2e6;
}

.strategy-meta {
  display: flex;
  gap: 15px;
  font-size: 14px;
  color: #666;
}

.strategy-price {
  font-weight: bold;
}

.strategy-price .free {
  color: #28a745;
}

.strategy-price .paid {
  color: #007bff;
}
</style>
