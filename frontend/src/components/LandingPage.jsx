import React, { useState, useEffect } from 'react'
import { api } from '../api'

const PLATFORMS = [
  { name: 'Polymarket', color: 'text-purple-400' },
  { name: 'Kalshi', color: 'text-blue-400' },
  { name: 'Smarkets', color: 'text-green-400' },
  { name: 'PredictIt', color: 'text-yellow-400' },
  { name: 'Metaculus', color: 'text-cyan-400' },
  { name: 'Betfair', color: 'text-orange-400' },
  { name: 'Manifold', color: 'text-pink-400' },
]

const FEATURES = [
  { title: 'Cross-Platform Arbs', desc: 'Guaranteed profit when the same event is priced differently across exchanges', icon: '1' },
  { title: 'Fee-Adjusted Profits', desc: 'See real NET profit after platform fees — no surprises when you execute', icon: '2' },
  { title: 'Forecaster Consensus', desc: 'Compare market prices against Metaculus, GJOpen & expert forecasters', icon: '3' },
  { title: 'Execution Plans', desc: 'Step-by-step instructions with stake amounts and direct platform links', icon: '4' },
  { title: '7 Market Categories', desc: 'Politics, sports, crypto, entertainment, science, weather & more', icon: '5' },
  { title: 'Real-Time Scanning', desc: 'Auto-updating every 2 minutes across all connected exchanges', icon: '6' },
]

const FAQS = [
  { q: 'What is prediction market arbitrage?', a: 'When the same event is priced differently on two prediction markets, you can bet both sides for a guaranteed profit regardless of the outcome. For example, if Polymarket says an event has a 40% chance and Smarkets says 50%, the price gap creates risk-free profit.' },
  { q: 'Which platforms do you support?', a: 'We scan Polymarket, Kalshi, Smarkets, PredictIt, SX Bet, Manifold, plus 10+ additional sources via Metaforecast (including Metaculus, Betfair, GJOpen, INFER, and Hypermind).' },
  { q: 'How fast do arbs disappear?', a: 'Prediction market arbs typically last minutes to hours — much longer than sports arbs which last seconds. Our scanner checks every 2 minutes and alerts you instantly via Telegram or Discord.' },
  { q: 'Is this legal?', a: 'Yes. Prediction market trading is legal in the US through CFTC-regulated platforms like Kalshi. Arbitrage is simply buying and selling at different prices — a standard trading practice.' },
  { q: 'What does the free plan include?', a: 'Free users can see the first 2 arb opportunities and browse categories. Premium unlocks all opportunities, discrepancy signals, the stake calculator, execution plans, and alerts.' },
]

export default function LandingPage({ onLogin, onSignUp }) {
  const [showLogin, setShowLogin] = useState(false)
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [liveStats, setLiveStats] = useState(null)
  const [openFaq, setOpenFaq] = useState(null)

  useEffect(() => {
    // Fetch live stats for the landing page
    fetch((import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/stats')
      .then(r => r.json())
      .then(d => setLiveStats(d))
      .catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (isSignUp) {
        await onSignUp(email, password)
      } else {
        await onLogin(email, password)
      }
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Nav */}
      <nav className="border-b border-gray-800/50 bg-gray-950/80 backdrop-blur-lg sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <span className="text-xl font-extrabold bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent">
            ArbitrageIQ
          </span>
          <div className="flex items-center gap-3">
            <button onClick={() => { setShowLogin(true); setIsSignUp(false) }} className="text-sm text-gray-400 hover:text-white transition-colors px-3 py-1.5">
              Log In
            </button>
            <button onClick={() => { setShowLogin(true); setIsSignUp(true) }} className="text-sm bg-green-600 hover:bg-green-500 text-white px-4 py-1.5 rounded-lg font-medium transition-colors">
              Sign Up Free
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-4 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-green-500/10 border border-green-500/20 rounded-full px-4 py-1.5 mb-6">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm text-green-400 font-medium">{liveStats?.active_arbs || 0} arbs active right now</span>
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-100 leading-tight mb-6">
          Cross-Platform<br />
          <span className="bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">Prediction Market</span><br />
          Arbitrage
        </h1>
        <p className="text-lg sm:text-xl text-gray-400 max-w-2xl mx-auto mb-8">
          The only tool that scans 7+ prediction market exchanges simultaneously to find guaranteed profit opportunities. Real-time arb detection with fee-adjusted profits.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
          <button onClick={() => { setShowLogin(true); setIsSignUp(true) }} className="w-full sm:w-auto bg-green-600 hover:bg-green-500 text-white font-semibold px-8 py-3.5 rounded-xl text-lg transition-colors shadow-lg shadow-green-500/20">
            Start Free
          </button>
          <a href="#pricing" className="w-full sm:w-auto text-gray-400 hover:text-white font-medium px-8 py-3.5 rounded-xl text-lg border border-gray-700 hover:border-gray-500 transition-colors text-center">
            View Pricing
          </a>
        </div>

        {/* Platform logos */}
        <div className="flex flex-wrap items-center justify-center gap-4">
          <span className="text-xs text-gray-600 uppercase tracking-wider">Scanning:</span>
          {PLATFORMS.map(p => (
            <span key={p.name} className={`text-xs font-medium ${p.color}`}>{p.name}</span>
          ))}
        </div>
      </section>

      {/* Live Stats Bar */}
      {liveStats && (
        <section className="border-y border-gray-800 bg-gray-900/50 py-8">
          <div className="max-w-4xl mx-auto px-4 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
            <div>
              <p className="text-3xl font-bold text-green-400 tabular-nums">{liveStats.active_arbs || 0}</p>
              <p className="text-sm text-gray-500 mt-1">Active Arbs</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-blue-400 tabular-nums">{liveStats.total_markets || 0}</p>
              <p className="text-sm text-gray-500 mt-1">Markets Monitored</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-purple-400 tabular-nums">7+</p>
              <p className="text-sm text-gray-500 mt-1">Data Sources</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-orange-400 tabular-nums">24/7</p>
              <p className="text-sm text-gray-500 mt-1">Auto-Scanning</p>
            </div>
          </div>
        </section>
      )}

      {/* Features Grid */}
      <section className="max-w-6xl mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold text-gray-100 text-center mb-4">Everything you need to profit from prediction markets</h2>
        <p className="text-gray-500 text-center mb-12 max-w-2xl mx-auto">No other tool combines cross-platform arbitrage detection with forecaster consensus intelligence across this many exchanges.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((f, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center text-green-400 font-bold text-sm mb-4">
                {f.icon}
              </div>
              <h3 className="text-lg font-semibold text-gray-100 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-6xl mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold text-gray-100 text-center mb-4">Simple, transparent pricing</h2>
        <p className="text-gray-500 text-center mb-12">Start free. Upgrade when you're ready to see all opportunities.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
          {[
            { name: 'Free', price: '$0', interval: '', desc: 'See what ArbitrageIQ can do', features: ['2 visible arbs', 'Category browsing', 'Basic market data'], cta: 'Start Free', popular: false },
            { name: 'Weekly', price: '$49.99', interval: '/week', desc: 'Most popular for active traders', features: ['All arbitrage opportunities', 'Discrepancy signals', 'Stake calculator', 'Execution plans', 'Telegram/Discord alerts'], cta: 'Start Weekly', popular: true },
            { name: 'Monthly', price: '$98.99', interval: '/month', desc: 'Best value — save 50%', features: ['Everything in Weekly', 'Priority data refresh', 'Historical analytics', 'Bet tracker & P/L', 'Save 50% vs weekly'], cta: 'Start Monthly', popular: false },
          ].map((plan) => (
            <div key={plan.name} className={`relative rounded-xl border p-6 flex flex-col ${plan.popular ? 'border-green-500/50 bg-green-500/5 shadow-lg shadow-green-500/10' : 'border-gray-800 bg-gray-900/50'}`}>
              {plan.popular && <div className="absolute -top-3 left-1/2 -translate-x-1/2"><span className="bg-green-500 text-white text-xs font-bold px-3 py-1 rounded-full">MOST POPULAR</span></div>}
              <h3 className="text-xl font-semibold text-gray-100">{plan.name}</h3>
              <p className="text-sm text-gray-500 mt-1 mb-4">{plan.desc}</p>
              <div className="mb-6"><span className="text-3xl font-bold text-gray-100">{plan.price}</span><span className="text-gray-500 text-sm">{plan.interval}</span></div>
              <ul className="space-y-2.5 mb-6 flex-1">
                {plan.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-400">
                    <svg className="w-4 h-4 text-green-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    {f}
                  </li>
                ))}
              </ul>
              <button onClick={() => { setShowLogin(true); setIsSignUp(true) }} className={`w-full py-3 rounded-lg font-semibold transition-colors ${plan.popular ? 'bg-green-600 hover:bg-green-500 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700'}`}>
                {plan.cta}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className="max-w-3xl mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold text-gray-100 text-center mb-12">Frequently asked questions</h2>
        <div className="space-y-3">
          {FAQS.map((faq, i) => (
            <div key={i} className="border border-gray-800 rounded-xl overflow-hidden">
              <button onClick={() => setOpenFaq(openFaq === i ? null : i)} className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-900/50 transition-colors">
                <span className="text-sm font-medium text-gray-200">{faq.q}</span>
                <svg className={`w-5 h-5 text-gray-500 transition-transform ${openFaq === i ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
              </button>
              {openFaq === i && <div className="px-6 pb-4 text-sm text-gray-500 leading-relaxed">{faq.a}</div>}
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-12">
        <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-lg font-bold bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent">ArbitrageIQ</span>
          <p className="text-sm text-gray-600">The first cross-platform prediction market arbitrage scanner</p>
          <p className="text-xs text-gray-700">&copy; 2026 ArbitrageIQ. All rights reserved.</p>
        </div>
      </footer>

      {/* Login Modal */}
      {showLogin && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) setShowLogin(false) }}>
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-8 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-100">{isSignUp ? 'Create your account' : 'Welcome back'}</h2>
              <button onClick={() => setShowLogin(false)} className="p-1 text-gray-500 hover:text-gray-300"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1.5">Email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-green-500/40 placeholder:text-gray-600" placeholder="you@email.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1.5">Password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-green-500/40 placeholder:text-gray-600" placeholder={isSignUp ? '6+ characters' : 'Your password'} />
              </div>
              {error && <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-sm text-red-400">{error}</div>}
              <button type="submit" disabled={loading} className="w-full bg-green-600 hover:bg-green-500 disabled:bg-green-800 text-white font-semibold py-3 rounded-lg transition-colors">
                {loading ? 'Please wait...' : isSignUp ? 'Create Account' : 'Log In'}
              </button>
            </form>
            <div className="mt-4 text-center">
              <button onClick={() => { setIsSignUp(!isSignUp); setError('') }} className="text-sm text-gray-500 hover:text-gray-300 transition-colors">
                {isSignUp ? 'Already have an account? Log in' : "Don't have an account? Sign up"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
