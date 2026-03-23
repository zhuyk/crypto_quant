<!--
交易页面
-->

<template>
  <div class="trade-page">
    <div class="trade-container">
      <TradingPanel />
    </div>
  </div>
</template>

<script setup>
import TradingPanel from '@/components/TradingPanel.vue'
</script>

<style scoped>
.trade-page {
  height: 100%;
}

.trade-container {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
</style>
