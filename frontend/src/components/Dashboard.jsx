import React, { useState } from 'react'
import ArbTable from './ArbTable'
import DiscrepancyFeed from './DiscrepancyFeed'
import MarketMap from './MarketMap'
import LiveFeed from './LiveFeed'
import PaywallOverlay from './PaywallOverlay'
import CategoryFilter from './CategoryFilter'
import AnimatedCounter from './AnimatedCounter'
import AnalyticsPanel from './AnalyticsPanel'
import ArbAlert from './ArbAlert'
import BetTracker from './BetTracker'
import AlertSettings from './AlertSettings'

const CATEGORY_LABELS = {
  politics: { name: 'Politics', color: 'purple' },
  sports: { name: 'Sports', color: 'green' },
  crypto: { name: 'Crypto & Finance', color: 'orange' },
  entertainment: { name: 'Entertainment', color: 'pink' },
  science_tech: { name: 'Science & Tech', color: 'blue' },
  weather: { name: 'Weather & Climate', color: 'cyan' },
  other: { name: 'Other', color: 'gray' },
}

const VIEW_TABS = [
  { key: 'scanner', label: 'Scanner', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
  { key: 'analytics', label: 'Analytics', icon: 'M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z' },
  { key: 'bets', label: 'Bets', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
  { key: 'platforms', label: 'Platforms', icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2' },
]

export default function Dashboard({
  activeCategory, onChangeCategory, onSelectCategory,
  opportunities, discrepancies, markets, health, stats,
  wsConnected, apiConnected, liveFeed, showLiveFeed, onToggleLiveFeed,
  onSelectOpportunity, user, isPremium, premiumData, onUpgrade, onLogout,
  isAdmin, onOpenAdmin, toasts, onDismissToast, soundEnabled, onToggleSound,
}) {
  const [view, setView] = useState('scanner')
  const [showAlertSettings, setShowAlertSettings] = useState(false)

  const activeArbs = stats?.active_arbs ?? opportunities?.length ?? 0
  const activeDiscs = stats?.active_discrepancies ?? discrepancies?.length ?? 0
  const totalMarkets = stats?.total_markets ?? 0
  const activePrices = stats?.active_prices ?? 0
  const sourceCount = stats?.source_count ?? 0
  const isConnected = apiConnected || wsConnected
  const isLoading = stats === null

  return (
    <div className="min-h-screen flex flex-col bg-surface-0">
      <ArbAlert toasts={toasts || []} onDismiss={onDismissToast || (() => {})} />

      {/* ── Nav ── */}
      <nav className="sticky top-0 z-40 glass border-b border-white/[0.04] safe-top">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 h-12 flex items-center justify-between">
          {/* Left */}
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-mint-500/15 flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-mint-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <span className="text-sm font-bold tracking-tight text-gray-200 hidden sm:inline">
              Arbitrage<span className="text-mint-400">IQ</span>
            </span>
          </div>

          {/* Center: Tabs */}
          <div className="hidden md:flex items-center gap-0.5 bg-surface-2/80 rounded-lg p-0.5 border border-white/[0.03]">
            {VIEW_TABS.map(t => (
              <button
                key={t.key}
                onClick={() => setView(t.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-150 ${
                  view === t.key
                    ? 'bg-surface-3 text-white shadow-sm border border-white/[0.04]'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={t.icon} />
                </svg>
                {t.label}
              </button>
            ))}
          </div>

          {/* Right */}
          <div className="flex items-center gap-2">
            {/* Alert settings */}
            <button onClick={() => setShowAlertSettings(true)} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-white/[0.04] transition-colors" title="Alert settings">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </button>
            <button onClick={onToggleSound} className={`p-1.5 rounded-lg transition-colors ${soundEnabled ? 'text-mint-400' : 'text-gray-600'}`} title={soundEnabled ? 'Sound on' : 'Sound off'}>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {soundEnabled
                  ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                }
              </svg>
            </button>

            {/* Status */}
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-surface-2/50">
              <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-mint-500 shadow-[0_0_4px_rgba(16,185,129,0.5)]' : 'bg-rose-500'}`} />
              <span className={`text-[10px] font-mono font-medium ${isConnected ? 'text-mint-400' : 'text-rose-400'}`}>
                {isConnected ? 'LIVE' : 'OFFLINE'}
              </span>
            </div>

            {/* Tier */}
            {isPremium ? (
              <span className="text-[9px] bg-mint-500/10 text-mint-400 border border-mint-500/20 px-2 py-0.5 rounded font-bold font-mono tracking-wider">PRO</span>
            ) : (
              <button onClick={onUpgrade} className="text-[9px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded font-bold font-mono tracking-wider hover:bg-amber-500/20 transition-colors">UPGRADE</button>
            )}

            {isAdmin && (
              <button onClick={onOpenAdmin} className="text-[9px] bg-purple-500/10 text-purple-400 border border-purple-500/20 px-2 py-0.5 rounded font-bold font-mono tracking-wider hover:bg-purple-500/20 transition-colors">ADMIN</button>
            )}

            <div className="flex items-center gap-2 pl-2 ml-1 border-l border-white/[0.04]">
              <span className="hidden sm:inline text-[10px] text-gray-600 truncate max-w-[100px]">{user?.email}</span>
              <button onClick={onLogout} className="text-gray-600 hover:text-gray-300 transition-colors" title="Log out">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Category + Mobile Tabs ── */}
      <div className="border-b border-white/[0.03] px-4 sm:px-6 py-2">
        <div className="max-w-[1920px] mx-auto flex items-center justify-between gap-4">
          <CategoryFilter activeCategory={activeCategory} onSelectCategory={onSelectCategory || onChangeCategory} />
          <div className="flex md:hidden items-center gap-0.5">
            {VIEW_TABS.map(t => (
              <button key={t.key} onClick={() => setView(t.key)}
                className={`p-1.5 rounded-md transition-colors ${view === t.key ? 'text-white bg-surface-3' : 'text-gray-600'}`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={t.icon} />
                </svg>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Hero Stats ── */}
      {!isLoading && (
        <div className="border-b border-white/[0.03] px-4 sm:px-6 py-4 scan-line">
          <div className="max-w-[1920px] mx-auto grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-6">
            <HeroStat label="Markets" value={totalMarkets} />
            <HeroStat label="Prices" value={activePrices} />
            <HeroStat label="Sources" value={sourceCount} />
            <HeroStat label="Live Arbs" value={activeArbs} accent glow />
            <HeroStat label="Signals" value={activeDiscs} />
          </div>
        </div>
      )}

      {/* ── Loading ── */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="relative w-12 h-12 mb-5">
            <div className="absolute inset-0 rounded-full border-2 border-mint-500/20" />
            <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-mint-500 animate-spin" />
            <div className="absolute inset-0 bg-mint-500/10 rounded-full blur-xl animate-glow-pulse" />
          </div>
          <p className="text-sm text-gray-300 font-medium">Scanning markets...</p>
          <p className="text-xs text-gray-600 mt-1">Connecting to prediction markets and exchanges</p>
        </div>
      )}

      {/* ── Content ── */}
      {!isLoading && (
        <main className="flex-1 max-w-[1920px] w-full mx-auto px-4 sm:px-6 py-5 space-y-5">
          {view === 'scanner' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              <div className="lg:col-span-2 space-y-3">
                <ArbTable opportunities={opportunities} onSelectOpportunity={onSelectOpportunity} />
                {!isPremium && premiumData.blurred_count > 0 && (
                  <div className="rounded-2xl border border-white/[0.04] overflow-hidden">
                    <PaywallOverlay count={premiumData.blurred_count} onUpgrade={onUpgrade} />
                  </div>
                )}
              </div>
              <div className="lg:col-span-1">
                {isPremium ? (
                  <DiscrepancyFeed discrepancies={discrepancies} stats={stats} />
                ) : (
                  <div className="bg-surface-1 rounded-2xl border border-white/[0.04] card-glow overflow-hidden">
                    <div className="px-5 py-4 border-b border-white/[0.04]">
                      <h2 className="text-sm font-semibold text-gray-100">Value Signals</h2>
                      <p className="text-[11px] text-gray-500 mt-0.5">Market vs. consensus probability</p>
                    </div>
                    <PaywallOverlay count={activeDiscs || 3} onUpgrade={onUpgrade} />
                  </div>
                )}
              </div>
            </div>
          )}
          {view === 'analytics' && <AnalyticsPanel />}
          {view === 'bets' && <BetTracker />}
          {view === 'platforms' && <MarketMap markets={markets} health={health} stats={stats} />}
        </main>
      )}

      {/* ── Feed FAB ── */}
      <button
        onClick={onToggleLiveFeed}
        className={`fixed bottom-5 right-5 z-50 flex items-center gap-2 px-4 py-2.5 rounded-full shadow-xl shadow-black/40 transition-all duration-200 hover:scale-105 active:scale-95 safe-bottom ${
          showLiveFeed
            ? 'bg-surface-3 text-gray-300 border border-white/[0.06]'
            : 'bg-mint-500 text-surface-0 hover:bg-mint-400'
        }`}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span className="text-xs font-semibold">
          {showLiveFeed ? 'Hide' : 'Feed'}
          {liveFeed.length > 0 && !showLiveFeed && (
            <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 text-[9px] bg-white/20 rounded-full font-bold">{liveFeed.length}</span>
          )}
        </span>
      </button>

      {showLiveFeed && <LiveFeed events={liveFeed} onClose={() => onToggleLiveFeed()} />}

      {/* Alert settings modal */}
      {showAlertSettings && <AlertSettings onClose={() => setShowAlertSettings(false)} />}

      {/* Mobile bottom nav */}
      <div className="fixed bottom-0 inset-x-0 z-30 md:hidden glass border-t border-white/[0.04] safe-bottom">
        <div className="flex items-center justify-around py-2 px-2">
          {VIEW_TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setView(t.key)}
              className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg transition-colors ${
                view === t.key ? 'text-mint-400' : 'text-gray-600'
              }`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={t.icon} />
              </svg>
              <span className="text-[9px] font-medium">{t.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function HeroStat({ label, value, accent, glow }) {
  return (
    <div className="text-center relative py-1">
      {glow && value > 0 && (
        <div className="absolute inset-0 bg-mint-500/[0.04] rounded-xl blur-lg" />
      )}
      <div className={`text-xl sm:text-2xl font-bold font-mono tracking-tight relative ${accent ? 'text-mint-400' : 'text-gray-100'}`}>
        <AnimatedCounter value={value} />
      </div>
      <div className="text-[9px] uppercase tracking-[0.15em] text-gray-600 mt-0.5 font-medium">{label}</div>
    </div>
  )
}
