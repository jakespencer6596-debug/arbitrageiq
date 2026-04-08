import React, { useState, useEffect } from 'react'
import { api } from '../api'

const PLATFORMS = [
  { name: 'Polymarket', color: '#8B5CF6' },
  { name: 'Kalshi', color: '#3B82F6' },
  { name: 'Smarkets', color: '#10B981' },
  { name: 'PredictIt', color: '#EAB308' },
  { name: 'Metaculus', color: '#06B6D4' },
  { name: 'Betfair', color: '#F97316' },
  { name: 'Manifold', color: '#EC4899' },
  { name: 'SX Bet', color: '#14B8A6' },
  { name: 'GJOpen', color: '#8B5CF6' },
  { name: 'INFER', color: '#6366F1' },
]

const FEATURES = [
  {
    title: 'Cross-Platform Detection',
    desc: 'Simultaneous scanning across 10+ prediction markets and sportsbooks. When the same event is priced differently, we find it.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    ),
  },
  {
    title: 'Fee-Adjusted Net Profit',
    desc: 'Every opportunity shows real profit after platform fees, withdrawal costs, and profit taxes. No surprises when you execute.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8V7m0 1v8m0 0v1" />
      </svg>
    ),
  },
  {
    title: 'Consensus Intelligence',
    desc: 'Cross-reference market prices against forecaster consensus from Metaculus, GJOpen, and INFER to find mispriced markets.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    title: 'Instant Execution Plans',
    desc: 'Click any opportunity for exact stake amounts, platform links, and step-by-step instructions. Copy and execute in seconds.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    title: 'Multi-Outcome Arbitrage',
    desc: 'Detect arbs across 3+ way markets like presidential elections. Buy the cheapest candidate on each platform for guaranteed profit.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm0 8a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zm12 0a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
      </svg>
    ),
  },
  {
    title: 'Real-Time Alerts',
    desc: 'Telegram and Discord notifications the moment a new opportunity appears. Audio chimes with distinct sounds per opportunity type.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
    ),
  },
]

const FAQS = [
  { q: 'What is prediction market arbitrage?', a: 'When the same event is priced differently on two prediction markets, you can bet both sides for a guaranteed profit regardless of the outcome. For example, if Polymarket says an event has a 40% chance and Smarkets says 50%, the price gap creates risk-free profit.' },
  { q: 'Which platforms do you support?', a: 'We scan Polymarket, Kalshi, Smarkets, PredictIt, SX Bet, Manifold, plus 10+ additional sources via Metaforecast (including Metaculus, Betfair, GJOpen, INFER, and Hypermind).' },
  { q: 'How fast do arbs disappear?', a: 'Prediction market arbs typically last minutes to hours — much longer than sports arbs which last seconds. Our scanner checks every 2 minutes and alerts you instantly.' },
  { q: 'Is this legal?', a: 'Yes. Prediction market trading is legal in the US through CFTC-regulated platforms like Kalshi. Arbitrage is simply buying and selling at different prices — a standard trading strategy.' },
  { q: 'What does the free plan include?', a: 'Free users can see the first 2 opportunities and browse all market categories. Premium unlocks every opportunity, consensus signals, the execution calculator, alerts, and historical analytics.' },
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
      if (isSignUp) await onSignUp(email, password)
      else await onLogin(email, password)
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-0">
      {/* ── Nav ── */}
      <nav className="fixed top-0 inset-x-0 z-50 glass border-b border-white/[0.04]">
        <div className="max-w-6xl mx-auto px-5 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-mint-500/15 flex items-center justify-center">
              <svg className="w-4 h-4 text-mint-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <span className="text-base font-bold tracking-tight text-gray-100">
              Arbitrage<span className="text-mint-400">IQ</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => { setShowLogin(true); setIsSignUp(false) }} className="text-sm text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-white/[0.04]">
              Log in
            </button>
            <button onClick={() => { setShowLogin(true); setIsSignUp(true) }} className="text-sm bg-mint-500 hover:bg-mint-400 text-surface-0 font-semibold px-4 py-1.5 rounded-lg transition-colors">
              Get started
            </button>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative pt-28 pb-20 px-5 overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-mint-500/[0.04] rounded-full blur-[120px] pointer-events-none" />

        <div className="max-w-3xl mx-auto text-center relative">
          {/* Live badge */}
          <div className="inline-flex items-center gap-2 bg-surface-2 border border-white/[0.06] rounded-full px-4 py-1.5 mb-8">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-mint-400 opacity-50" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-mint-500" />
            </span>
            <span className="text-xs text-gray-300 font-medium font-mono">
              {liveStats?.active_arbs || 0} opportunities live
            </span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold text-white leading-[1.1] tracking-tight mb-6">
            Find guaranteed profit<br className="hidden sm:block" /> across prediction markets
          </h1>

          <p className="text-base sm:text-lg text-gray-400 max-w-xl mx-auto mb-10 leading-relaxed">
            ArbitrageIQ scans 10+ exchanges simultaneously to detect price discrepancies. When the same event is priced differently across platforms, you profit — regardless of the outcome.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-14">
            <button
              onClick={() => { setShowLogin(true); setIsSignUp(true) }}
              className="w-full sm:w-auto bg-mint-500 hover:bg-mint-400 text-surface-0 font-semibold px-7 py-3 rounded-xl text-sm transition-all shadow-lg shadow-mint-500/20 hover:shadow-mint-500/30 hover:-translate-y-0.5 active:translate-y-0"
            >
              Start scanning free
            </button>
            <a
              href="#pricing"
              className="w-full sm:w-auto text-gray-400 hover:text-white font-medium px-7 py-3 rounded-xl text-sm border border-white/[0.08] hover:border-white/[0.15] hover:bg-white/[0.02] transition-all text-center"
            >
              View pricing
            </a>
          </div>

          {/* Platform ticker */}
          <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
            <span className="text-[10px] text-gray-600 uppercase tracking-[0.15em] font-medium">Scanning</span>
            {PLATFORMS.map(p => (
              <span key={p.name} className="text-xs font-medium text-gray-500 hover:text-gray-300 transition-colors cursor-default">{p.name}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Stats Bar ── */}
      <section className="border-y border-white/[0.04] scan-line">
        <div className="max-w-4xl mx-auto px-5 py-8 grid grid-cols-2 md:grid-cols-4 gap-8">
          <StatBlock value={liveStats?.active_arbs || 0} label="Active Arbs" accent />
          <StatBlock value={liveStats?.total_markets?.toLocaleString() || '0'} label="Markets Monitored" />
          <StatBlock value={`${liveStats?.source_count || 10}+`} label="Data Sources" />
          <StatBlock value="24/7" label="Auto-Scanning" />
        </div>
      </section>

      {/* ── Features ── */}
      <section className="max-w-5xl mx-auto px-5 py-24">
        <div className="text-center mb-16">
          <p className="text-[11px] uppercase tracking-[0.2em] text-mint-400 font-semibold mb-3">Capabilities</p>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">Built for serious traders</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => (
            <div
              key={i}
              className="group bg-surface-1 border border-white/[0.04] rounded-2xl p-6 hover:border-mint-500/20 transition-all duration-300 hover:bg-surface-2"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="w-9 h-9 rounded-xl bg-mint-500/10 flex items-center justify-center text-mint-400 mb-4 group-hover:bg-mint-500/15 transition-colors">
                {f.icon}
              </div>
              <h3 className="text-sm font-semibold text-gray-100 mb-2">{f.title}</h3>
              <p className="text-xs text-gray-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="border-y border-white/[0.04] bg-surface-1/50">
        <div className="max-w-4xl mx-auto px-5 py-24">
          <div className="text-center mb-16">
            <p className="text-[11px] uppercase tracking-[0.2em] text-mint-400 font-semibold mb-3">How it works</p>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">Three steps to guaranteed profit</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { step: '01', title: 'Scanner detects', desc: 'Our engine checks 10+ platforms every 2 minutes, matching events across markets using fuzzy matching and entity recognition.' },
              { step: '02', title: 'You review the edge', desc: 'See exact profit percentages after all fees, confidence scores, and which platforms to use. Click to expand full details.' },
              { step: '03', title: 'Execute the trade', desc: 'Follow the execution plan with pre-calculated stake amounts and direct platform links. Profit regardless of outcome.' },
            ].map((s, i) => (
              <div key={i} className="relative">
                <span className="text-5xl font-bold text-white/[0.03] font-mono absolute -top-3 -left-1">{s.step}</span>
                <div className="relative pt-8">
                  <h3 className="text-sm font-semibold text-gray-100 mb-2">{s.title}</h3>
                  <p className="text-xs text-gray-500 leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="max-w-5xl mx-auto px-5 py-24">
        <div className="text-center mb-16">
          <p className="text-[11px] uppercase tracking-[0.2em] text-mint-400 font-semibold mb-3">Pricing</p>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight mb-3">Start free, upgrade when ready</h2>
          <p className="text-sm text-gray-500">Cancel anytime. No hidden fees.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto">
          {[
            { name: 'Free', price: '$0', interval: '', desc: 'See what ArbitrageIQ can do', features: ['2 visible opportunities', 'All market categories', 'Basic market data', 'Platform health status'], cta: 'Start free', popular: false },
            { name: 'Pro Weekly', price: '$49', interval: '/week', desc: 'For active traders', features: ['All arbitrage opportunities', 'Consensus signals', 'Execution calculator', 'Telegram & Discord alerts', 'Historical analytics'], cta: 'Start Pro', popular: true },
            { name: 'Pro Monthly', price: '$99', interval: '/month', desc: 'Best value — save 50%', features: ['Everything in Pro Weekly', 'Priority data refresh', 'Bet tracker & P/L', 'API access', 'Save 50% vs weekly'], cta: 'Start Monthly', popular: false },
          ].map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-2xl border p-6 flex flex-col transition-all duration-300 ${
                plan.popular
                  ? 'border-mint-500/30 bg-mint-500/[0.03] shadow-lg shadow-mint-500/[0.05]'
                  : 'border-white/[0.06] bg-surface-1 hover:border-white/[0.1]'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-6">
                  <span className="bg-mint-500 text-surface-0 text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-wide">
                    Most popular
                  </span>
                </div>
              )}
              <h3 className="text-sm font-semibold text-gray-200 mb-1">{plan.name}</h3>
              <p className="text-[11px] text-gray-500 mb-4">{plan.desc}</p>
              <div className="mb-5">
                <span className="text-3xl font-bold text-white font-mono">{plan.price}</span>
                <span className="text-xs text-gray-500 ml-1">{plan.interval}</span>
              </div>
              <ul className="space-y-2.5 mb-6 flex-1">
                {plan.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-xs text-gray-400">
                    <svg className="w-3.5 h-3.5 text-mint-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>
              <button
                onClick={() => { setShowLogin(true); setIsSignUp(true) }}
                className={`w-full py-2.5 rounded-xl text-sm font-semibold transition-all ${
                  plan.popular
                    ? 'bg-mint-500 hover:bg-mint-400 text-surface-0 shadow-md shadow-mint-500/20'
                    : 'bg-white/[0.04] hover:bg-white/[0.08] text-gray-200 border border-white/[0.06]'
                }`}
              >
                {plan.cta}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="max-w-2xl mx-auto px-5 py-24">
        <div className="text-center mb-12">
          <h2 className="text-2xl font-bold text-white tracking-tight">Questions</h2>
        </div>
        <div className="space-y-2">
          {FAQS.map((faq, i) => (
            <div key={i} className="border border-white/[0.04] rounded-xl overflow-hidden bg-surface-1/50">
              <button
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
                className="w-full px-5 py-4 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
              >
                <span className="text-sm font-medium text-gray-200 pr-4">{faq.q}</span>
                <svg className={`w-4 h-4 text-gray-600 shrink-0 transition-transform duration-200 ${openFaq === i ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {openFaq === i && (
                <div className="px-5 pb-4 text-xs text-gray-500 leading-relaxed animate-fade-in">{faq.a}</div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/[0.04] py-10">
        <div className="max-w-6xl mx-auto px-5 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-mint-500/15 flex items-center justify-center">
              <svg className="w-3 h-3 text-mint-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <span className="text-sm font-semibold text-gray-300">Arbitrage<span className="text-mint-400">IQ</span></span>
          </div>
          <p className="text-[11px] text-gray-600">&copy; 2026 ArbitrageIQ. All rights reserved.</p>
        </div>
      </footer>

      {/* ── Auth Modal ── */}
      {showLogin && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" onClick={(e) => { if (e.target === e.currentTarget) setShowLogin(false) }}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative bg-surface-2 rounded-2xl border border-white/[0.06] p-7 w-full max-w-sm shadow-2xl shadow-black/40 animate-slide-up">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">{isSignUp ? 'Create account' : 'Welcome back'}</h2>
              <button onClick={() => setShowLogin(false)} className="p-1 text-gray-600 hover:text-gray-300 transition-colors rounded-lg hover:bg-white/[0.04]">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                  className="w-full bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-mint-500/40 focus:ring-1 focus:ring-mint-500/20 placeholder:text-gray-600 transition-colors"
                  placeholder="you@email.com" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6}
                  className="w-full bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-mint-500/40 focus:ring-1 focus:ring-mint-500/20 placeholder:text-gray-600 transition-colors"
                  placeholder={isSignUp ? '6+ characters' : 'Your password'} />
              </div>
              {error && (
                <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl px-4 py-2.5 text-xs text-rose-400">{error}</div>
              )}
              <button type="submit" disabled={loading}
                className="w-full bg-mint-500 hover:bg-mint-400 disabled:opacity-50 text-surface-0 font-semibold py-2.5 rounded-xl text-sm transition-all shadow-md shadow-mint-500/20">
                {loading ? 'Please wait...' : isSignUp ? 'Create account' : 'Log in'}
              </button>
            </form>
            <div className="mt-4 text-center">
              <button onClick={() => { setIsSignUp(!isSignUp); setError('') }} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
                {isSignUp ? 'Already have an account? Log in' : "Don't have an account? Sign up"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatBlock({ value, label, accent }) {
  return (
    <div className="text-center">
      <p className={`text-2xl sm:text-3xl font-bold font-mono tracking-tight ${accent ? 'text-mint-400' : 'text-white'}`}>
        {value}
      </p>
      <p className="text-[11px] text-gray-500 mt-1.5 uppercase tracking-[0.1em]">{label}</p>
    </div>
  )
}
