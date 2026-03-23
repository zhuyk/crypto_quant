/**
 * WebSocket 服务
 * 提供实时推送功能
 */

class WebSocketService {
  constructor() {
    this.ws = null
    this.url = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 1000
    this.messageHandlers = new Map()
    this.connected = false
    this.pingInterval = null
  }

  /**
   * 连接 WebSocket
   * @param {Object} options - 连接选项
   * @param {string} options.userId - 用户 ID
   * @param {string} options.room - 房间名
   * @param {string} options.token - 认证令牌
   */
  connect(options = {}) {
    const { userId = null, room = null, token = null } = options
    
    // 构建 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const baseUrl = `${protocol}//${window.location.host || 'localhost:8000'}`
    const params = new URLSearchParams()
    
    if (userId) params.append('user_id', userId)
    if (room) params.append('room', room)
    if (token) params.append('token', token)
    
    this.url = `${baseUrl}/ws?${params.toString()}`
    
    console.log('🔌 连接 WebSocket:', this.url)
    
    try {
      this.ws = new WebSocket(this.url)
      
      this.ws.onopen = () => {
        console.log('✅ WebSocket 连接成功')
        this.connected = true
        this.reconnectAttempts = 0
        
        // 启动心跳
        this.startPing()
        
        // 触发连接成功回调
        this.emit('connected', { url: this.url })
      }
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          console.log('📨 收到消息:', message)
          
          // 触发对应类型的回调
          this.emit(message.type, message)
          
          // 触发通用消息回调
          this.emit('message', message)
        } catch (error) {
          console.error('解析消息失败:', error, event.data)
        }
      }
      
      this.ws.onclose = (event) => {
        console.log('👋 WebSocket 连接关闭:', event.code, event.reason)
        this.connected = false
        
        // 停止心跳
        this.stopPing()
        
        // 触发断开连接回调
        this.emit('disconnected', { code: event.code, reason: event.reason })
        
        // 尝试重连
        this.attemptReconnect(options)
      }
      
      this.ws.onerror = (error) => {
        console.error('❌ WebSocket 错误:', error)
        this.emit('error', { error })
      }
    } catch (error) {
      console.error('创建 WebSocket 连接失败:', error)
      this.emit('error', { error })
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    if (this.ws) {
      console.log('🔌 主动断开 WebSocket 连接')
      this.ws.close(1000, 'User disconnected')
      this.ws = null
    }
    
    this.stopPing()
    this.connected = false
  }

  /**
   * 尝试重连
   */
  attemptReconnect(options) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('❌ 重连次数已达上限')
      this.emit('maxReconnectAttemptsReached', { attempts: this.reconnectAttempts })
      return
    }
    
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    
    console.log(`⏳ ${delay}ms 后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
    
    setTimeout(() => {
      console.log('🔄 尝试重连...')
      this.connect(options)
    }, delay)
  }

  /**
   * 发送消息
   * @param {Object} message - 消息内容
   */
  send(message) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('❌ WebSocket 未连接，无法发送消息')
      return false
    }
    
    try {
      const messageStr = JSON.stringify(message)
      console.log('📤 发送消息:', message)
      this.ws.send(messageStr)
      return true
    } catch (error) {
      console.error('发送消息失败:', error)
      return false
    }
  }

  /**
   * 发送心跳
   */
  ping() {
    return this.send({
      type: 'ping',
      timestamp: new Date().toISOString(),
    })
  }

  /**
   * 启动心跳定时器
   */
  startPing() {
    this.stopPing() // 先停止已有的
    
    this.pingInterval = setInterval(() => {
      this.ping()
    }, 30000) // 30 秒心跳
    
    console.log('💓 心跳已启动 (30s)')
  }

  /**
   * 停止心跳定时器
   */
  stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
      console.log('⏹️ 心跳已停止')
    }
  }

  /**
   * 订阅主题
   * @param {string} topic - 主题名
   */
  subscribe(topic) {
    return this.send({
      type: 'subscribe',
      topic,
    })
  }

  /**
   * 取消订阅主题
   * @param {string} topic - 主题名
   */
  unsubscribe(topic) {
    return this.send({
      type: 'unsubscribe',
      topic,
    })
  }

  /**
   * 发送交易指令
   * @param {Object} orderData - 订单数据
   */
  sendTradeOrder(orderData) {
    return this.send({
      type: 'trade',
      ...orderData,
    })
  }

  /**
   * 注册消息处理器
   * @param {string} type - 消息类型
   * @param {Function} handler - 处理函数
   */
  on(type, handler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set())
    }
    this.messageHandlers.get(type).add(handler)
    
    // 返回取消订阅函数
    return () => {
      this.off(type, handler)
    }
  }

  /**
   * 移除消息处理器
   * @param {string} type - 消息类型
   * @param {Function} handler - 处理函数
   */
  off(type, handler) {
    const handlers = this.messageHandlers.get(type)
    if (handlers) {
      handlers.delete(handler)
    }
  }

  /**
   * 触发事件
   * @param {string} type - 事件类型
   * @param {any} data - 事件数据
   */
  emit(type, data) {
    const handlers = this.messageHandlers.get(type)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data)
        } catch (error) {
          console.error(`消息处理器执行失败 [${type}]:`, error)
        }
      })
    }
  }

  /**
   * 获取连接状态
   */
  getStatus() {
    return {
      connected: this.connected,
      url: this.url,
      reconnectAttempts: this.reconnectAttempts,
      readyState: this.ws?.readyState,
    }
  }
}

// 创建全局单例
const wsService = new WebSocketService()

// 快捷方法
export function connectWebSocket(options) {
  return wsService.connect(options)
}

export function disconnectWebSocket() {
  return wsService.disconnect()
}

export function sendWebSocketMessage(message) {
  return wsService.send(message)
}

export function onWebSocketMessage(type, handler) {
  return wsService.on(type, handler)
}

export function offWebSocketMessage(type, handler) {
  return wsService.off(type, handler)
}

export function getWebSocketStatus() {
  return wsService.getStatus()
}

// 导出单例
export { wsService }
export default wsService
