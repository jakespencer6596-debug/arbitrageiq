const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const WS_BASE = API_BASE.replace(/^http/, 'ws')

// Auth token management
let _token = localStorage.getItem('aiq_token') || null

export function setToken(token) {
  _token = token
  if (token) {
    localStorage.setItem('aiq_token', token)
  } else {
    localStorage.removeItem('aiq_token')
  }
}

export function getToken() {
  return _token
}

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const headers = { 'Content-Type': 'application/json', ...options.headers }

  // Attach auth token if available
  if (_token) {
    headers['Authorization'] = `Bearer ${_token}`
  }

  const res = await fetch(url, { headers, ...options })

  if (res.status === 401) {
    // Token expired or invalid — clear and let app handle redirect
    setToken(null)
    throw new Error('Session expired. Please log in again.')
  }

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  // Auth
  register: (email, password) =>
    request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  login: (email, password) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  getMe: () => request('/api/auth/me'),
  getPricing: () => request('/api/auth/pricing'),

  // Data
  getSnapshot: () => request('/api/snapshot'),
  getOpportunities: () => request('/api/opportunities'),
  getMarkets: () => request('/api/markets'),
  getHealth: () => request('/api/health'),
  getStats: () => request('/api/stats'),
  getCategories: () => request('/api/categories'),
  getCategory: () => request('/api/category'),
  setCategory: (category) =>
    request('/api/category', {
      method: 'POST',
      body: JSON.stringify({ category }),
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

    ws.onerror = () => {}

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
