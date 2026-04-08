import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api, createWebSocket, setToken, getToken } from './api'
import Dashboard from './components/Dashboard'
import StakeCalculator from './components/StakeCalculator'
import CategoryFilter from './components/CategoryFilter'
import LoginPage from './components/LoginPage'
import LandingPage from './components/LandingPage'
import PricingPage from './components/PricingPage'
import PaywallOverlay from './components/PaywallOverlay'
import AdminDashboard from './components/AdminDashboard'

export default function App() {
  // Auth state
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [showPricing, setShowPricing] = useState(false)
  const [showAdmin, setShowAdmin] = useState(false)

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
  const isAdmin = user?.role === 'admin' || user?.role === 'employee'

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

  // Polling — always runs (no category gate)
  const fetchAll = useCallback(async () => {
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
  }, [])

  useEffect(() => {
    if (!user) return
    fetchAll()
    pollRef.current = setInterval(fetchAll, 15000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [user, fetchAll])

  // Category filter — just changes the display filter, backend always fetches everything
  const handleSelectCategory = async (category) => {
    setCategoryLoading(true)
    try {
      await api.setCategory(category)
      setActiveCategory(category)
      // Immediately refetch with new filter
      await fetchAll()
      if (category) {
        addFeedEvent({ type: 'system', message: `Filtering to ${category} markets` })
      } else {
        addFeedEvent({ type: 'system', message: 'Showing all categories' })
      }
    } catch (err) {
      addFeedEvent({ type: 'system', message: `Failed: ${err.message}` })
    } finally {
      setCategoryLoading(false)
    }
  }

  const handleChangeCategory = async () => {
    await handleSelectCategory(null)
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

  // Not logged in — show landing page
  if (!user) {
    return (
      <LandingPage
        onLogin={(email, pw) => handleAuth('login', email, pw)}
        onSignUp={(email, pw) => handleAuth('register', email, pw)}
      />
    )
  }

  // Dashboard loads immediately — no category gate
  return (
    <>
      <Dashboard
        activeCategory={activeCategory}
        onChangeCategory={handleChangeCategory}
        onSelectCategory={handleSelectCategory}
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
        isAdmin={isAdmin}
        onOpenAdmin={() => setShowAdmin(true)}
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
      {showAdmin && isAdmin && (
        <AdminDashboard onClose={() => setShowAdmin(false)} />
      )}
    </>
  )
}
