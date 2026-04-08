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

const CATEGORY_LABELS = {
  politics: { name: 'Politics', color: 'purple' },
  sports: { name: 'Sports', color: 'green' },
  crypto: { name: 'Crypto & Finance', color: 'orange' },
  entertainment: { name: 'Entertainment', color: 'pink' },
  science_tech: { name: 'Science & Tech', color: 'blue' },
  weather: { name: 'Weather & Climate', color: 'cyan' },
  other: { name: 'Other', color: 'gray' },
}

const CATEGORY_DOT_COLORS = {
  purple: 'bg-purple-400',
  green: 'bg-green-400',
  orange: 'bg-orange-400',
  pink: 'bg-pink-400',
  blue: 'bg-blue-400',
  cyan: 'bg-cyan-400',
  gray: 'bg-gray-400',
}

const VIEW_TABS = [
  { key: 'scanner', label: 'Scanner', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { key: 'analytics', label: 'Analytics', icon: 'M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z' },
  { key: 'platforms', label: 'Platforms', icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2' },
]

export default function Dashboard({
  activeCategory,
  onChangeCategory,
  onSelectCategory,
  opportunities,
  discrepancies,
  markets,
  health,
  stats,
  wsConnected,
  apiConnected,
  liveFeed,
  showLiveFeed,
  onToggleLiveFeed,
  onSelectOpportunity,
  user,
  isPremium,
  premiumData,
  onUpgrade,
  onLogout,
  isAdmin,
  onOpenAdmin,
  toasts,
  onDismissToast,
  soundEnabled,
  onToggleSound,
}) {
  const [view, setView] = useState('scanner')

  const activeArbs = stats?.active_arbs ?? opportunities?.length ?? 0
  const activeDiscs = stats?.active_discrepancies ?? discrepancies?.length ?? 0
  const totalMarkets = stats?.total_markets ?? 0
  const activePrices = stats?.active_prices ?? 0
  const sourceCount = stats?.source_count ?? 0
  const isConnected = apiConnected || wsConnected
  const isLoading = stats === null
  const catInfo = activeCategory
    ? (CATEGORY_LABELS[activeCategory] || { name: activeCategory, color: 'gray' })
    : { name: 'All Markets', color: 'green' }

  return (
    <div className="min-h-screen flex flex-col bg-gray-950">
      {/* Toast notifications */}
      <ArbAlert toasts={toasts || []} onDismiss={onDismissToast || (() => {})} />

      {/* ── Top Nav ── */}
      <nav className="sticky top-0 z-40 bg-gray-900/80 backdrop-blur-xl border-b border-gray-800/80">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          {/* Left: Logo */}
          <div className="flex items-center gap-3">
            <span className="text-xl font-extrabold bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent tracking-tight">
              ArbitrageIQ
            </span>
            <span className="hidden sm:inline text-[9px] text-gray-500 font-semibold border border-gray-700 rounded px-1.5 py-0.5 uppercase tracking-widest">
              Beta
            </span>
            <div className="hidden lg:flex items-center gap-2 ml-3 pl-3 border-l border-gray-800">
              <span className={`w-1.5 h-1.5 rounded-full ${CATEGORY_DOT_COLORS[catInfo.color] || 'bg-gray-400'}`} />
              <span className="text-xs font-medium text-gray-400">{catInfo.name}</span>
            </div>
          </div>

          {/* Center: View tabs */}
          <div className="hidden md:flex items-center gap-1 bg-gray-800/40 rounded-lg p-0.5">
            {VIEW_TABS.map(t => (
              <button
                key={t.key}
                onClick={() => setView(t.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  view === t.key
                    ? 'bg-gray-700/80 text-white shadow-sm'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={t.icon} />
                </svg>
                {t.label}
              </button>
            ))}
          </div>

          {/* Right: Controls */}
          <div className="flex items-center gap-2.5">
            {/* Sound toggle */}
            <button
              onClick={onToggleSound}
              className={`p-1.5 rounded-lg transition-colors ${
                soundEnabled ? 'text-green-400 hover:bg-green-500/10' : 'text-gray-600 hover:bg-gray-800'
              }`}
              title={soundEnabled ? 'Sound on' : 'Sound off'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {soundEnabled ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                )}
              </svg>
            </button>

            {/* Connection dot */}
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]' : 'bg-red-500'}`} />
              <span className={`hidden sm:inline text-[10px] font-medium ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
                {isConnected ? 'Live' : 'Offline'}
              </span>
            </div>

            {/* Premium badge */}
            {isPremium ? (
              <span className="text-[9px] bg-green-500/15 text-green-400 border border-green-500/20 px-2 py-0.5 rounded font-bold tracking-wide">
                PRO
              </span>
            ) : (
              <button
                onClick={onUpgrade}
                className="text-[9px] bg-gradient-to-r from-orange-500/20 to-amber-500/20 text-orange-400 border border-orange-500/20 px-2.5 py-0.5 rounded font-bold hover:from-orange-500/30 hover:to-amber-500/30 transition-all tracking-wide"
              >
                UPGRADE
              </button>
            )}

            {isAdmin && (
              <button
                onClick={onOpenAdmin}
                className="text-[9px] bg-purple-500/15 text-purple-400 border border-purple-500/20 px-2 py-0.5 rounded font-bold hover:bg-purple-500/25 transition-colors"
              >
                ADMIN
              </button>
            )}

            {/* User */}
            <div className="flex items-center gap-2 pl-2 border-l border-gray-800">
              <span className="hidden sm:inline text-[10px] text-gray-500 truncate max-w-[100px]">{user?.email}</span>
              <button onClick={onLogout} className="text-gray-600 hover:text-gray-300 transition-colors" title="Log out">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Category Filter ── */}
      <div className="bg-gray-900/40 border-b border-gray-800/60 px-4 sm:px-6 lg:px-8 py-2.5">
        <div className="max-w-[1920px] mx-auto flex items-center justify-between gap-4">
          <CategoryFilter activeCategory={activeCategory} onSelectCategory={onSelectCategory || onChangeCategory} />
          {/* Mobile view tabs */}
          <div className="flex md:hidden items-center gap-1">
            {VIEW_TABS.map(t => (
              <button
                key={t.key}
                onClick={() => setView(t.key)}
                className={`p-1.5 rounded-md ${view === t.key ? 'text-white bg-gray-700' : 'text-gray-600'}`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={t.icon} />
                </svg>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Hero Stats ── */}
      {!isLoading && (
        <div className="border-b border-gray-800/40 px-4 sm:px-6 lg:px-8 py-4 bg-gradient-to-b from-gray-900/50 to-transparent">
          <div className="max-w-[1920px] mx-auto grid grid-cols-3 sm:grid-cols-5 gap-3 sm:gap-6">
            <HeroStat label="Markets" value={totalMarkets} />
            <HeroStat label="Price Feeds" value={activePrices} />
            <HeroStat label="Sources" value={sourceCount} />
            <HeroStat label="Live Arbs" value={activeArbs} highlight glow />
            <HeroStat label="Signals" value={activeDiscs} />
          </div>
        </div>
      )}

      {/* ── Loading State ── */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="relative">
            <svg className="animate-spin h-10 w-10 text-green-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <div className="absolute inset-0 bg-green-500/20 rounded-full blur-xl animate-pulse" />
          </div>
          <p className="text-gray-300 text-sm font-medium mt-5">Scanning markets across all platforms...</p>
          <p className="text-gray-600 text-xs mt-1.5">Fetching from prediction markets, sportsbooks & exchanges</p>
        </div>
      )}

      {/* ── Main Content ── */}
      {!isLoading && (
        <main className="flex-1 max-w-[1920px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

          {/* SCANNER VIEW */}
          {view === 'scanner' && (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Arb Table — 2/3 */}
                <div className="lg:col-span-2 space-y-3">
                  <ArbTable opportunities={opportunities} onSelectOpportunity={onSelectOpportunity} />
                  {!isPremium && premiumData.blurred_count > 0 && (
                    <div className="rounded-xl border border-gray-800 overflow-hidden">
                      <PaywallOverlay count={premiumData.blurred_count} onUpgrade={onUpgrade} />
                    </div>
                  )}
                </div>

                {/* Discrepancy Feed — 1/3 */}
                <div className="lg:col-span-1">
                  {isPremium ? (
                    <DiscrepancyFeed discrepancies={discrepancies} stats={stats} />
                  ) : (
                    <div className="bg-gray-900 rounded-xl border border-gray-800 shadow-lg shadow-black/20 overflow-hidden">
                      <div className="px-6 py-4 border-b border-gray-800">
                        <h2 className="text-lg font-semibold text-gray-100">Value Signals</h2>
                        <p className="text-xs text-gray-500 mt-0.5">Market prices vs. consensus probability</p>
                      </div>
                      <PaywallOverlay count={activeDiscs || 3} onUpgrade={onUpgrade} />
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* ANALYTICS VIEW */}
          {view === 'analytics' && (
            <AnalyticsPanel />
          )}

          {/* PLATFORMS VIEW */}
          {view === 'platforms' && (
            <MarketMap markets={markets} health={health} stats={stats} />
          )}
        </main>
      )}

      {/* ── Live Feed Toggle ── */}
      <button
        onClick={onToggleLiveFeed}
        className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-full shadow-xl shadow-black/40 transition-all duration-200 hover:scale-105 active:scale-95 ${
          showLiveFeed
            ? 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700'
            : 'bg-gradient-to-r from-green-600 to-emerald-600 text-white hover:from-green-500 hover:to-emerald-500'
        }`}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span className="text-sm font-semibold">
          {showLiveFeed ? 'Hide' : 'Feed'}
          {liveFeed.length > 0 && !showLiveFeed && (
            <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 text-[10px] bg-white/20 rounded-full font-bold">
              {liveFeed.length}
            </span>
          )}
        </span>
      </button>

      {showLiveFeed && (
        <LiveFeed events={liveFeed} onClose={() => onToggleLiveFeed()} />
      )}
    </div>
  )
}

function HeroStat({ label, value, highlight, glow }) {
  return (
    <div className="text-center relative">
      {glow && value > 0 && (
        <div className="absolute inset-0 bg-green-500/5 rounded-xl blur-xl" />
      )}
      <div className={`text-2xl sm:text-3xl font-bold ${highlight ? 'text-green-400' : 'text-gray-100'}`}>
        <AnimatedCounter value={value} />
      </div>
      <div className="text-[9px] sm:text-[10px] uppercase tracking-widest text-gray-500 mt-1 font-medium">{label}</div>
    </div>
  )
}
