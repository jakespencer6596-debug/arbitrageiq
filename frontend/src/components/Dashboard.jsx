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
  liveFeed,
  showLiveFeed,
  onToggleLiveFeed,
  onSelectOpportunity,
}) {
  const marketCount = stats?.total_markets || markets?.length || 0
  const activeArbs = stats?.active_arbs ?? opportunities?.length ?? 0
  const discrepancyCount = stats?.active_discrepancies ?? discrepancies?.length ?? 0

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
            {/* WS indicator */}
            <div className="flex items-center gap-2 text-sm">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  wsConnected
                    ? 'bg-green-500 animate-pulse-green'
                    : 'bg-red-500'
                }`}
              />
              <span className={`hidden sm:inline ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
                {wsConnected ? 'Live' : 'Offline'}
              </span>
            </div>

            {/* Settings icon */}
            <button
              className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors"
              title="Settings"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28z"
                />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
        </div>
      </nav>

      {/* ── Mobile stats row ── */}
      <div className="md:hidden flex items-center gap-2 px-4 py-2 overflow-x-auto bg-gray-900/50 border-b border-gray-800">
        <StatBadge label="Markets" value={marketCount} color="blue" />
        <StatBadge label="Arbs" value={activeArbs} color="green" />
        <StatBadge label="Disc." value={discrepancies} color="yellow" />
      </div>

      {/* ── Main Content ── */}
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
