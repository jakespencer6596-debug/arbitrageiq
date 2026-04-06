import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api, createWebSocket, setToken, getToken } from './api'
import Dashboard from './components/Dashboard'
import StakeCalculator from './components/StakeCalculator'
import CategorySelector from './components/CategorySelector'
import LoginPage from './components/LoginPage'
import PricingPage from './components/PricingPage'
import PaywallOverlay from './components/PaywallOverlay'

export default function App() {
  // Auth state
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [showPricing, setShowPricing] = useState(false)

  // App state
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
  const [premiumData, setPremiumData] = useState({ premium: false, blurred_count: 0, total_count: 0 })

  const wsRef = useRef(null)
  const pollRef = useRef(null)

  const isPremium = user?.subscription_tier && user.subscription_tier !== 'free'

  // Check auth on mount
  useEffect(() => {
    const token = getToken()
    if (token) {
      api.getMe()
        .then((data) => {
          if (data.user) setUser(data.user)
          else setToken(null)
        })
        .catch(() => setToken(null))
        .finally(() => setAuthLoading(false))
    } else {
      setAuthLoading(false)
    }
  }, [])

  // Handle login/register
  const handleAuth = async (action, email, password) => {
    const fn = action === 'register' ? api.register : api.login
    const data = await fn(email, password)
    if (data.error) throw new Error(data.error)
    if (data.token) {
      setToken(data.token)
      setUser(data.user)
    }
  }

  const handleLogout = () => {
    setToken(null)
    setUser(null)
    setActiveCategory(null)
    setOpportunities([])
    setDiscrepancies([])
    setStats(null)
  }

  // WebSocket
  const addFeedEvent = useCallback((event) => {
    setLiveFeed((prev) => {
      const next = [...prev, { ...event, id: Date.now() + Math.random(), timestamp: new Date().toISOString() }]
      return next.slice(-50)
    })
  }, [])

  const handleWsMessage = useCallback(
    (data) => {
      switch (data.type) {
        case 'ws_connected': setWsConnected(true); break
        case 'ws_disconnected': setWsConnected(false); break
        case 'arb': addFeedEvent({ type: 'arb', message: 'New arb detected' }); break
        default: break
      }
    },
    [addFeedEvent]
  )

  useEffect(() => {
    if (!user) return
    wsRef.current = createWebSocket(handleWsMessage)
    return () => { if (wsRef.current) wsRef.current.close() }
  }, [handleWsMessage, user])

  // Polling
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
        setPremiumData({
          premium: data.premium ?? false,
          blurred_count: data.blurred_count ?? 0,
          total_count: data.total_count ?? (data.arb || []).length,
        })
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
    fetchAll()
    pollRef.current = setInterval(fetchAll, 15000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [activeCategory, fetchAll])

  // Category selection
  const handleSelectCategory = async (category) => {
    setCategoryLoading(true)
    setOpportunities([])
    setStats(null)
    setHealth(null)
    try {
      await api.setCategory(category)
      setActiveCategory(category)
      setApiConnected(true)
      addFeedEvent({ type: 'system', message: `Scanning ${category} markets...` })
    } catch (err) {
      addFeedEvent({ type: 'system', message: `Failed: ${err.message}` })
    } finally {
      setCategoryLoading(false)
    }
  }

  const handleChangeCategory = async () => {
    try { await api.setCategory(null) } catch {}
    setActiveCategory(null)
    setOpportunities([])
    setDiscrepancies([])
    setStats(null)
    if (pollRef.current) clearInterval(pollRef.current)
  }

  const handleSelectPlan = (planKey) => {
    // Stripe integration will go here
    alert(`Stripe payment for ${planKey} plan will be connected soon. Contact support for early access.`)
    setShowPricing(false)
  }

  // Loading auth
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <svg className="animate-spin h-8 w-8 text-green-500 mx-auto mb-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  // Not logged in
  if (!user) {
    return <LoginPage onAuth={handleAuth} />
  }

  // Category selector
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
        onSelectOpportunity={(opp) => {
          if (!isPremium) {
            setShowPricing(true)
            return
          }
          setSelectedOpp(opp)
        }}
        user={user}
        isPremium={isPremium}
        premiumData={premiumData}
        onUpgrade={() => setShowPricing(true)}
        onLogout={handleLogout}
      />
      {selectedOpp && isPremium && (
        <StakeCalculator
          opportunity={selectedOpp}
          onClose={() => setSelectedOpp(null)}
        />
      )}
      {showPricing && (
        <PricingPage
          onSelectPlan={handleSelectPlan}
          onClose={() => setShowPricing(false)}
        />
      )}
    </>
  )
}
