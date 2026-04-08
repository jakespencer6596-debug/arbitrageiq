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
import { useArbAlerts } from './components/ArbAlert'

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

  // Sound + alerts
  const [soundEnabled, setSoundEnabled] = useState(() => {
    const saved = localStorage.getItem('aiq_sound')
    return saved !== null ? saved === 'true' : true
  })
  const { toasts, addToast, dismissToast } = useArbAlerts(soundEnabled)

  const wsRef = useRef(null)
  const pollRef = useRef(null)
  const prevArbCountRef = useRef(0)

  const isPremium = user?.subscription_tier && user.subscription_tier !== 'free'
  const isAdmin = user?.role === 'admin' || user?.role === 'employee'

  const handleToggleSound = useCallback(() => {
    setSoundEnabled(prev => {
      const next = !prev
      localStorage.setItem('aiq_sound', String(next))
      return next
    })
  }, [])

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
        case 'arb': {
          addFeedEvent({ type: 'arb', message: 'New arb detected' })
          // Fire toast alert
          const arbData = data.data || {}
          const d = typeof arbData.to_dict === 'function' ? arbData.to_dict() : arbData
          const profit = d.net_profit_pct || d.profit_pct || 0
          const eventName = d.event_name || 'New opportunity'
          const legs = d.legs || []
          const platforms = legs.slice(0, 3).map(l => l.source || '').filter(Boolean)

          addToast({
            type: profit >= 0.05 ? 'high_value' : 'arb',
            message: eventName,
            profit: profit,
            platforms: platforms,
          })
          break
        }
        default: break
      }
    },
    [addFeedEvent, addToast]
  )

  useEffect(() => {
    if (!user) return
    wsRef.current = createWebSocket(handleWsMessage)
    return () => { if (wsRef.current) wsRef.current.close() }
  }, [handleWsMessage, user])

  // Polling
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
        const newArbs = data.arb || []
        setOpportunities(newArbs)
        setDiscrepancies(data.discrepancies || [])
        setPremiumData({
          premium: data.premium ?? false,
          blurred_count: data.blurred_count ?? 0,
          total_count: data.total_count ?? newArbs.length,
        })

        // Detect new arbs via polling (if WS missed them)
        if (newArbs.length > prevArbCountRef.current && prevArbCountRef.current > 0) {
          const diff = newArbs.length - prevArbCountRef.current
          if (diff > 0 && diff <= 10) {
            // Alert for the highest-profit new arb
            const topNew = newArbs[0]
            if (topNew) {
              const legs = topNew.legs?.legs || topNew.legs || []
              addToast({
                type: (topNew.profit_pct || 0) >= 0.05 ? 'high_value' : 'arb',
                message: topNew.event_name || 'New opportunity',
                profit: topNew.profit_pct || 0,
                platforms: (Array.isArray(legs) ? legs : []).slice(0, 3).map(l => l?.source || '').filter(Boolean),
              })
            }
          }
        }
        prevArbCountRef.current = newArbs.length

        anySuccess = true
      }
      if (statsData.status === 'fulfilled') { setStats(statsData.value); anySuccess = true }
      if (healthData.status === 'fulfilled') { setHealth(healthData.value); anySuccess = true }
      if (anySuccess) setApiConnected(true)
    } catch {
      setApiConnected(false)
    }
  }, [addToast])

  useEffect(() => {
    if (!user) return
    fetchAll()
    pollRef.current = setInterval(fetchAll, 15000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [user, fetchAll])

  // Category filter
  const handleSelectCategory = async (category) => {
    setCategoryLoading(true)
    try {
      await api.setCategory(category)
      setActiveCategory(category)
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
    alert(`Stripe payment for ${planKey} plan will be connected soon. Contact support for early access.`)
    setShowPricing(false)
  }

  // Loading auth
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <div className="relative inline-block">
            <svg className="animate-spin h-8 w-8 text-green-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
          <p className="text-gray-500 text-xs mt-3">Loading...</p>
        </div>
      </div>
    )
  }

  // Not logged in
  if (!user) {
    return (
      <LandingPage
        onLogin={(email, pw) => handleAuth('login', email, pw)}
        onSignUp={(email, pw) => handleAuth('register', email, pw)}
      />
    )
  }

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
        toasts={toasts}
        onDismissToast={dismissToast}
        soundEnabled={soundEnabled}
        onToggleSound={handleToggleSound}
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
