import React from 'react'

const CATEGORY_CONFIG = {
  weather: { label: 'Weather', color: 'bg-blue-500', barBg: 'bg-blue-500/20' },
  economic: { label: 'Economic', color: 'bg-yellow-500', barBg: 'bg-yellow-500/20' },
  political: { label: 'Political', color: 'bg-purple-500', barBg: 'bg-purple-500/20' },
  sports: { label: 'Sports', color: 'bg-green-500', barBg: 'bg-green-500/20' },
  entertainment: { label: 'Entertainment', color: 'bg-pink-500', barBg: 'bg-pink-500/20' },
  other: { label: 'Other', color: 'bg-gray-500', barBg: 'bg-gray-500/20' },
}

export default function MarketMap({ markets, health, stats }) {
  const categoryBreakdown = stats?.category_breakdown || {}
  const platforms = stats?.platforms || health?.components || health?.platforms || []
  const totalMarkets = stats?.total_markets || markets?.length || 0
  const platformCount = platforms.length || stats?.platform_count || 0
  const unmapped = stats?.unmapped_markets || 0

  // Compute max for bar scaling
  const counts = Object.values(categoryBreakdown)
  const maxCount = Math.max(...counts, 1)

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 shadow-lg shadow-black/20 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Market Coverage</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Monitoring <span className="text-gray-300 font-medium">{totalMarkets}</span> markets
            {platformCount > 0 && (
              <>
                {' '}across <span className="text-gray-300 font-medium">{platformCount}</span> platforms
              </>
            )}
          </p>
        </div>
        {/* System health strip */}
        <div className="flex items-center gap-2">
          <HealthDot status={health?.status} />
          <span className="text-xs text-gray-500">
            {health?.status === 'healthy' ? 'All systems go' : health?.status || 'Checking...'}
          </span>
        </div>
      </div>

      <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left: Category bars */}
        <div className="space-y-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Markets by Category</h3>

          {Object.keys(categoryBreakdown).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(categoryBreakdown).map(([cat, count]) => {
                const config = CATEGORY_CONFIG[cat.toLowerCase()] || {
                  label: cat,
                  color: 'bg-gray-500',
                  barBg: 'bg-gray-500/20',
                }
                const pct = Math.max(5, (count / maxCount) * 100)

                return (
                  <div key={cat}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-400 capitalize">{config.label}</span>
                      <span className="text-sm text-gray-300 font-medium tabular-nums">{count}</span>
                    </div>
                    <div className={`h-2 rounded-full ${config.barBg} overflow-hidden`}>
                      <div
                        className={`h-full rounded-full ${config.color} transition-all duration-700 ease-out`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}

              {/* Unmapped */}
              {unmapped > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-amber-400/80">Unmapped</span>
                    <span className="text-sm text-amber-400 font-medium tabular-nums">{unmapped}</span>
                  </div>
                  <div className="h-2 rounded-full bg-amber-500/20 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-500 transition-all duration-700 ease-out"
                      style={{ width: `${Math.max(5, (unmapped / maxCount) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Placeholder bars when no data */
            <div className="space-y-3">
              {Object.values(CATEGORY_CONFIG).map((config) => (
                <div key={config.label}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-gray-600">{config.label}</span>
                    <span className="text-sm text-gray-700 tabular-nums">0</span>
                  </div>
                  <div className={`h-2 rounded-full bg-gray-800 overflow-hidden`}>
                    <div className={`h-full rounded-full ${config.color} opacity-20`} style={{ width: '0%' }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Platform grid */}
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">Platform Status</h3>

          {platforms.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {platforms.map((p, i) => {
                const name = typeof p === 'string' ? p : p.name || p.platform || 'Unknown'
                const status = typeof p === 'string' ? 'unknown' : p.status || 'unknown'
                return (
                  <div
                    key={i}
                    className="flex items-center gap-2.5 bg-gray-800/50 rounded-lg border border-gray-700/50 px-3 py-2.5 hover:bg-gray-800 transition-colors"
                  >
                    <PlatformStatusDot status={status} />
                    <div className="min-w-0">
                      <p className="text-sm text-gray-300 font-medium truncate">{name}</p>
                      <p className="text-xs text-gray-600 capitalize">{status}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {['Odds API', 'Kalshi', 'Polymarket', 'PredictIt', 'Weather', 'FRED'].map((name) => (
                <div
                  key={name}
                  className="flex items-center gap-2.5 bg-gray-800/30 rounded-lg border border-gray-800 px-3 py-2.5"
                >
                  <PlatformStatusDot status="unknown" />
                  <div className="min-w-0">
                    <p className="text-sm text-gray-500 font-medium truncate">{name}</p>
                    <p className="text-xs text-gray-700">Waiting...</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function HealthDot({ status }) {
  const s = (status || '').toLowerCase()
  let cls = 'bg-gray-500'
  if (s === 'healthy' || s === 'ok') cls = 'bg-green-500'
  else if (s === 'degraded' || s === 'warning') cls = 'bg-yellow-500'
  else if (s === 'error' || s === 'unhealthy') cls = 'bg-red-500'

  return <span className={`w-2.5 h-2.5 rounded-full ${cls}`} />
}

function PlatformStatusDot({ status }) {
  const s = (status || '').toLowerCase()
  let cls = 'bg-gray-600'
  if (s === 'healthy' || s === 'ok' || s === 'connected' || s === 'active') cls = 'bg-green-500'
  else if (s === 'error' || s === 'disconnected' || s === 'down') cls = 'bg-red-500'
  else if (s === 'degraded' || s === 'slow') cls = 'bg-yellow-500'

  return <span className={`w-2 h-2 rounded-full shrink-0 ${cls}`} />
}
