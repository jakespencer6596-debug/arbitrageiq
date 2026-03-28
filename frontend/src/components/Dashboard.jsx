import React from 'react'
import ArbTable from './ArbTable'
import DiscrepancyFeed from './DiscrepancyFeed'
import MarketMap from './MarketMap'
import LiveFeed from './LiveFeed'

export default function Dashboard({
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
}) {
  const marketCount = stats?.total_markets || markets?.length || 0
  const activeArbs = stats?.active_arbs ?? opportunities?.length ?? 0
  const discrepancyCount = stats?.active_discrepancies ?? discrepancies?.length ?? 0
  const isConnected = apiConnected || wsConnected
  const isLoading = stats === null

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Top Nav ── */}
      <nav className="sticky top-0 z-40 bg-gray-900/80 backdrop-blur-lg border-b border-gray-800">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <span className="text-2xl font-extrabold bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent tracking-tight">
              ArbitrageIQ
            </span>
            <span className="hidden sm:inline text-xs text-gray-500 font-medium border border-gray-700 rounded px-1.5 py-0.5">
              BETA
            </span>
          </div>

          {/* Centre stats badges */}
          <div className="hidden md:flex items-center gap-3">
            <StatBadge label="Markets" value={marketCount} color="blue" />
            <StatBadge label="Active Arbs" value={activeArbs} color="green" />
            <StatBadge label="Discrepancies" value={discrepancyCount} color="yellow" />
          </div>

          {/* Right side */}
          <div className="flex items-center gap-4">
            {/* Connection indicator */}
            <div className="flex items-center gap-2 text-sm">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isConnected
                    ? 'bg-green-500 animate-pulse-green'
                    : 'bg-red-500'
                }`}
              />
              <span className={`hidden sm:inline ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
                {isConnected ? 'Live' : 'Offline'}
              </span>
            </div>

            {/* Info tooltip */}
            <div
              className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors cursor-default"
              title="ArbitrageIQ scans prediction markets for arbitrage opportunities in real-time."
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z"
                />
              </svg>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Mobile stats row ── */}
      <div className="md:hidden flex items-center gap-2 px-4 py-2 overflow-x-auto bg-gray-900/50 border-b border-gray-800">
        <StatBadge label="Markets" value={marketCount} color="blue" />
        <StatBadge label="Arbs" value={activeArbs} color="green" />
        <StatBadge label="Disc." value={discrepancyCount} color="yellow" />
      </div>

      {/* ── Loading State ── */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <svg className="animate-spin h-8 w-8 text-green-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-gray-400 text-sm font-medium">Connecting to server...</p>
          <p className="text-gray-600 text-xs mt-1">Fetching market data and scanning for opportunities</p>
        </div>
      )}

      {/* ── Main Content ── */}
      {!isLoading && (
      <main className="flex-1 max-w-[1920px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Two-column grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left - Arb Table (2/3) */}
          <div className="lg:col-span-2">
            <ArbTable
              opportunities={opportunities}
              onSelectOpportunity={onSelectOpportunity}
            />
          </div>

          {/* Right - Discrepancy Feed (1/3) */}
          <div className="lg:col-span-1">
            <DiscrepancyFeed discrepancies={discrepancies} stats={stats} />
          </div>
        </div>

        {/* Bottom row */}
        <div className="grid grid-cols-1 lg:grid-cols-1 gap-6">
          <MarketMap markets={markets} health={health} stats={stats} />
        </div>
      </main>
      )}

      {/* ── Live Feed Toggle Button ── */}
      <button
        onClick={onToggleLiveFeed}
        className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-full shadow-lg shadow-black/30 transition-all duration-200 hover:scale-105 ${
          showLiveFeed
            ? 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            : 'bg-green-600 text-white hover:bg-green-500'
        }`}
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span className="text-sm font-medium">
          {showLiveFeed ? 'Hide Feed' : 'Live Feed'}
          {liveFeed.length > 0 && !showLiveFeed && (
            <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 text-xs bg-white/20 rounded-full">
              {liveFeed.length}
            </span>
          )}
        </span>
      </button>

      {/* ── Live Feed Panel ── */}
      {showLiveFeed && (
        <LiveFeed events={liveFeed} onClose={() => onToggleLiveFeed()} />
      )}
    </div>
  )
}

function StatBadge({ label, value, color }) {
  const colorMap = {
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    green: 'bg-green-500/10 text-green-400 border-green-500/20',
    yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
  }

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${colorMap[color] || colorMap.blue}`}
    >
      <span className="text-gray-400 text-xs uppercase tracking-wide">{label}</span>
      <span className="font-bold tabular-nums">{value}</span>
    </div>
  )
}
