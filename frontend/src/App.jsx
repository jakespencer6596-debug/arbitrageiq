import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api, createWebSocket } from './api'
import Dashboard from './components/Dashboard'
import StakeCalculator from './components/StakeCalculator'

export default function App() {
  const [opportunities, setOpportunities] = useState([])
  const [discrepancies, setDiscrepancies] = useState([])
  const [markets, setMarkets] = useState([])
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [liveFeed, setLiveFeed] = useState([])
  const [showLiveFeed, setShowLiveFeed] = useState(false)
  const [selectedOpp, setSelectedOpp] = useState(null)
  const [apiConnected, setApiConnected] = useState(false)

  const wsRef = useRef(null)

  const addFeedEvent = useCallback((event) => {
    setLiveFeed((prev) => {
      const next = [...prev, { ...event, id: Date.now() + Math.random(), timestamp: new Date().toISOString() }]
      return next.slice(-50)
    })
  }, [])

  const handleWsMessage = useCallback(
    (data) => {
      switch (data.type) {
        case 'ws_connected':
          setWsConnected(true)
          addFeedEvent({ type: 'system', message: 'WebSocket connected' })
          break
        case 'ws_disconnected':
          setWsConnected(false)
          addFeedEvent({ type: 'system', message: 'WebSocket disconnected' })
          break
        case 'ws_reconnecting':
          addFeedEvent({ type: 'system', message: `Reconnecting (attempt ${data.attempt})...` })
          break
        case 'new_opportunity':
          setOpportunities((prev) => {
            const exists = prev.find((o) => o.id === data.payload?.id)
            if (exists) {
              return prev.map((o) => (o.id === data.payload.id ? data.payload : o))
            }
            return [data.payload, ...prev]
          })
          addFeedEvent({ type: 'arb', message: `New arb: ${data.payload?.event_name || 'Unknown'} (${data.payload?.profit_pct?.toFixed(2) || '?'}%)` })
          break
        case 'opportunity_expired':
          setOpportunities((prev) => prev.filter((o) => o.id !== data.payload?.id))
          addFeedEvent({ type: 'arb_expired', message: `Arb expired: ${data.payload?.event_name || 'Unknown'}` })
          break
        case 'new_discrepancy':
          addFeedEvent({ type: 'discrepancy', message: `Discrepancy: ${data.payload?.event_name || 'Unknown'} (${data.payload?.edge_pct?.toFixed(1) || '?'}% edge)` })
          break
        case 'health_update':
          setHealth(data.payload)
          break
        case 'stats_update':
          setStats(data.payload)
          break
        default:
          if (data.type && !data.type.startsWith('ws_')) {
            addFeedEvent({ type: 'info', message: data.message || `Event: ${data.type}` })
          }
      }
    },
    [addFeedEvent]
  )

  // WebSocket connection
  useEffect(() => {
    wsRef.current = createWebSocket(handleWsMessage)
    return () => {
      if (wsRef.current) wsRef.current.close()
    }
  }, [handleWsMessage])

  // Polling
  useEffect(() => {
    async function fetchAll() {
      try {
        const [opps, statsData, healthData] = await Promise.allSettled([
          api.getOpportunities(),
          api.getStats(),
          api.getHealth(),
        ])
        let anySuccess = false
        if (opps.status === 'fulfilled') {
          const data = opps.value || {}
          setOpportunities(data.arb || [])
          setDiscrepancies(data.discrepancies || [])
          anySuccess = true
        }
        if (statsData.status === 'fulfilled') { setStats(statsData.value); anySuccess = true }
        if (healthData.status === 'fulfilled') { setHealth(healthData.value); anySuccess = true }
        if (anySuccess) setApiConnected(true)
      } catch {
        setApiConnected(false)
      }
    }

    fetchAll()
    const interval = setInterval(fetchAll, 15000)
    return () => clearInterval(interval)
  }, [])

  // Fetch markets once
  useEffect(() => {
    api.getMarkets().then((data) => setMarkets(data?.markets || data || [])).catch(() => {})
  }, [])

  return (
    <>
      <Dashboard
        opportunities={opportunities}
        discrepancies={discrepancies}
        markets={markets}
        health={health}
        stats={stats}
        wsConnected={wsConnected}
        apiConnected={apiConnected}
        liveFeed={liveFeed}
        showLiveFeed={showLiveFeed}
        onToggleLiveFeed={() => setShowLiveFeed((v) => !v)}
        onSelectOpportunity={setSelectedOpp}
      />
      {selectedOpp && (
        <StakeCalculator
          opportunity={selectedOpp}
          onClose={() => setSelectedOpp(null)}
        />
      )}
    </>
  )
}
