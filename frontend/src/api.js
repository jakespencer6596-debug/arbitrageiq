const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const WS_BASE = API_BASE.replace(/^http/, 'ws')

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  getSnapshot: () => request('/api/snapshot'),
  getOpportunities: () => request('/api/opportunities'),
  getMarkets: () => request('/api/markets'),
  getHealth: () => request('/api/health'),
  getStats: () => request('/api/stats'),
  testAlert: () =>
    request('/api/alerts/test', {
      method: 'POST',
    }),
}

export function createWebSocket(onMessage) {
  let ws = null
  let reconnectAttempts = 0
  let reconnectTimer = null
  let isManuallyClosed = false

  function connect() {
    const wsUrl = `${WS_BASE}/ws/live`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      reconnectAttempts = 0
      onMessage({ type: 'ws_connected' })
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch {
        onMessage({ type: 'ws_raw', payload: event.data })
      }
    }

    ws.onerror = () => {
      // error handled on close
    }

    ws.onclose = () => {
      onMessage({ type: 'ws_disconnected' })
      if (!isManuallyClosed) {
        scheduleReconnect()
      }
    }
  }

  function scheduleReconnect() {
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 60000)
    reconnectAttempts++
    reconnectTimer = setTimeout(() => {
      onMessage({ type: 'ws_reconnecting', attempt: reconnectAttempts })
      connect()
    }, delay)
  }

  function close() {
    isManuallyClosed = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) ws.close()
  }

  connect()

  return { close }
}

export { API_BASE, WS_BASE }
