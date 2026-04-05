import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api, createWebSocket } from './api'
import Dashboard from './components/Dashboard'
import StakeCalculator from './components/StakeCalculator'
import CategorySelector from './components/CategorySelector'

export default function App() {
  const [activeCategory, setActiveCategory] = useState(null)
  const [categoryLoading, setCategoryLoading] = useState(false)
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
  const pollRef = useRef(null)

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
        case 'arb':
          // New arb detected via WebSocket
          addFeedEvent({ type: 'arb', message: `New arb detected` })
          break
        case 'health_update':
          setHealth(data.payload)
          break
        case 'stats_update':
          setStats(data.payload)
          break
        default:
          if (data.type && !data.type.startsWith('ws_') && data.type !== 'connected' && data.type !== 'pong') {
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

  // Polling — only when a category is active
  const fetchAll = useCallback(async () => {
    if (!activeCategory) return
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
  }, [activeCategory])

  useEffect(() => {
    if (!activeCategory) return
    // Initial fetch after category is set
    fetchAll()
    // Then poll every 15 seconds
    pollRef.current = setInterval(fetchAll, 15000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [activeCategory, fetchAll])

  // Handle category selection
  const handleSelectCategory = async (category) => {
    setCategoryLoading(true)
    setOpportunities([])
    setStats(null)
    setHealth(null)
    setMarkets([])
    try {
      await api.setCategory(category)
      setActiveCategory(category)
      setApiConnected(true)
      addFeedEvent({ type: 'system', message: `Scanning ${category} markets...` })
    } catch (err) {
      addFeedEvent({ type: 'system', message: `Failed to set category: ${err.message}` })
    } finally {
      setCategoryLoading(false)
    }
  }

  // Handle going back to category selector
  const handleChangeCategory = async () => {
    try {
      await api.setCategory(null)
    } catch {}
    setActiveCategory(null)
    setOpportunities([])
    setDiscrepancies([])
    setStats(null)
    setHealth(null)
    setMarkets([])
    if (pollRef.current) clearInterval(pollRef.current)
  }

  // Show category selector when no category is active
  if (!activeCategory) {
    return <CategorySelector onSelectCategory={handleSelectCategory} />
  }

  return (
    <>
      <Dashboard
        activeCategory={activeCategory}
        onChangeCategory={handleChangeCategory}
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
