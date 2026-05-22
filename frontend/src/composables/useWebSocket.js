/**
 * WebSocket Vue Composable
 * 
 * 提供响应式的 WebSocket 连接管理，自动处理连接/断开/重连/数据更新。
 * 
 * 用法:
 *   const { connected, tickers, subscribe } = useWebSocket()
 */

import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'

// WebSocket 连接配置
const WS_RECONNECT_MAX = 10
const WS_RECONNECT_BASE_DELAY = 2000
const WS_PING_INTERVAL = 25000

/**
 * WebSocket Composable - 实时行情数据
 */
export function useWebSocket() {
  // === 响应式状态 ===
  const connected = ref(false)
  const connecting = ref(false)
  const error = ref(null)
  const messageCount = ref(0)
  const lastMessageTime = ref(null)

  // 实时行情数据 { BTCUSDT: { price, change, ... }, ... }
  const tickers = reactive({})

  // 实时 K 线数据 { "BTCUSDT:1m": { open, high, low, close, volume, ... } }
  const klines = reactive({})

  // 策略信号
  const signals = ref([])

  // 交易更新
  const tradeUpdates = ref([])

  // === 内部状态 ===
  let ws = null
  let reconnectAttempts = 0
  let reconnectTimer = null
  let pingTimer = null
  let intentionalClose = false

  // === 连接管理 ===

  function getWsUrl() {
    // 支持环境变量配置
    const apiBase = import.meta.env.VITE_API_BASE_URL || ''
    
    if (apiBase.startsWith('http')) {
      // 从 HTTP URL 推导 WS URL
      const url = new URL(apiBase)
      const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${wsProtocol}//${url.host}/api/v1/ws`
    }
    
    // 使用当前页面 host
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host || 'localhost:8000'
    return `${protocol}//${host}/api/v1/ws`
  }

  function connect(options = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      return // 已连接
    }
    
    intentionalClose = false
    connecting.value = true
    error.value = null

    const userId = options.userId || localStorage.getItem('session_id') || 'anonymous'
    const url = `${getWsUrl()}?user_id=${userId}`

    try {
      ws = new WebSocket(url)

      ws.onopen = () => {
        connected.value = true
        connecting.value = false
        reconnectAttempts = 0
        error.value = null
        console.log('✅ [WS] 实时行情连接成功')

        // 启动心跳
        startPing()

        // 订阅默认主题
        subscribe('price_update')
        subscribe('trade_update')
        subscribe('strategy_signal')
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          messageCount.value++
          lastMessageTime.value = Date.now()
          handleMessage(message)
        } catch (e) {
          console.warn('[WS] 消息解析失败:', e)
        }
      }

      ws.onclose = (event) => {
        connected.value = false
        connecting.value = false
        stopPing()

        if (!intentionalClose && event.code !== 1000) {
          console.warn(`⚠️ [WS] 连接断开 (code=${event.code})，尝试重连...`)
          scheduleReconnect(options)
        } else {
          console.log('👋 [WS] 连接已关闭')
        }
      }

      ws.onerror = (e) => {
        error.value = 'WebSocket 连接错误'
        connecting.value = false
        console.error('❌ [WS] 连接错误:', e)
      }
    } catch (e) {
      error.value = e.message
      connecting.value = false
      console.error('❌ [WS] 创建连接失败:', e)
    }
  }

  function disconnect() {
    intentionalClose = true
    stopPing()
    clearReconnectTimer()

    if (ws) {
      ws.close(1000, 'User disconnect')
      ws = null
    }
    connected.value = false
  }

  function scheduleReconnect(options) {
    if (reconnectAttempts >= WS_RECONNECT_MAX) {
      error.value = '重连次数已达上限，请刷新页面'
      console.error('[WS] 重连失败，达到最大重试次数')
      return
    }

    reconnectAttempts++
    const delay = WS_RECONNECT_BASE_DELAY * Math.pow(1.5, reconnectAttempts - 1)

    console.log(`🔄 [WS] ${(delay / 1000).toFixed(1)}s 后重连 (${reconnectAttempts}/${WS_RECONNECT_MAX})`)
    
    reconnectTimer = setTimeout(() => {
      connect(options)
    }, delay)
  }

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  // === 心跳 ===

  function startPing() {
    stopPing()
    pingTimer = setInterval(() => {
      send({ type: 'ping', timestamp: new Date().toISOString() })
    }, WS_PING_INTERVAL)
  }

  function stopPing() {
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = null
    }
  }

  // === 消息发送 ===

  function send(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
      return true
    }
    return false
  }

  function subscribe(topic) {
    return send({ type: 'subscribe', topic })
  }

  function unsubscribe(topic) {
    return send({ type: 'unsubscribe', topic })
  }

  // === 消息处理 ===

  function handleMessage(message) {
    const { type, data } = message

    switch (type) {
      case 'price_update':
        handlePriceUpdate(message)
        break
      case 'kline_update':
        handleKlineUpdate(message)
        break
      case 'trade_update':
        handleTradeUpdate(message)
        break
      case 'strategy_signal':
        handleStrategySignal(message)
        break
      case 'pong':
        // 心跳响应，忽略
        break
      case 'welcome':
        console.log('[WS] 服务端欢迎:', message.message)
        break
      default:
        // 未知消息类型
        break
    }
  }

  function handlePriceUpdate(message) {
    const { symbol, price, price_change_pct, high_24h, low_24h, volume_24h } = message
    
    if (!symbol) return

    tickers[symbol] = {
      symbol,
      price: parseFloat(price) || tickers[symbol]?.price || 0,
      change: parseFloat(price_change_pct) || 0,
      high24h: parseFloat(high_24h) || 0,
      low24h: parseFloat(low_24h) || 0,
      volume24h: parseFloat(volume_24h) || 0,
      updatedAt: Date.now(),
    }
  }

  function handleKlineUpdate(message) {
    const { symbol, interval, open, high, low, close, volume, is_closed } = message
    
    if (!symbol || !interval) return

    const key = `${symbol}:${interval}`
    klines[key] = {
      symbol,
      interval,
      open: parseFloat(open),
      high: parseFloat(high),
      low: parseFloat(low),
      close: parseFloat(close),
      volume: parseFloat(volume),
      isClosed: is_closed,
      updatedAt: Date.now(),
    }
  }

  function handleTradeUpdate(message) {
    tradeUpdates.value = [message, ...tradeUpdates.value.slice(0, 49)]
  }

  function handleStrategySignal(message) {
    signals.value = [message, ...signals.value.slice(0, 19)]
  }

  // === Computed ===

  const tickerList = computed(() => {
    return Object.values(tickers).sort((a, b) => {
      // 按交易量排序
      return (b.volume24h || 0) - (a.volume24h || 0)
    })
  })

  // === 生命周期 ===

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    // 状态
    connected,
    connecting,
    error,
    messageCount,
    lastMessageTime,

    // 数据
    tickers,
    tickerList,
    klines,
    signals,
    tradeUpdates,

    // 方法
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    send,
  }
}

export default useWebSocket
