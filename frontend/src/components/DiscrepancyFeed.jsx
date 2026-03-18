import React, { useState, useMemo } from 'react'

const CATEGORIES = ['All', 'Weather', 'Economic', 'Political', 'Sports']

const CATEGORY_COLORS = {
  weather: { badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20', dot: 'bg-blue-400' },
  economic: { badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', dot: 'bg-yellow-400' },
  political: { badge: 'bg-purple-500/10 text-purple-400 border-purple-500/20', dot: 'bg-purple-400' },
  sports: { badge: 'bg-green-500/10 text-green-400 border-green-500/20', dot: 'bg-green-400' },
}

const CONFIDENCE_COLORS = {
  high: { dot: 'bg-red-400', label: 'text-red-400' },
  medium: { dot: 'bg-yellow-400', label: 'text-yellow-400' },
  low: { dot: 'bg-gray-500', label: 'text-gray-500' },
}

export default function DiscrepancyFeed({ discrepancies: discrepanciesProp, stats }) {
  const [filter, setFilter] = useState('All')
  const discrepancies = discrepanciesProp?.length > 0
    ? discrepanciesProp
    : stats?.discrepancy_details || []

  const filtered = useMemo(() => {
    let list = Array.isArray(discrepancies) ? [...discrepancies] : []
    if (filter !== 'All') {
      list = list.filter((d) => (d.category || '').toLowerCase() === filter.toLowerCase())
    }
    list.sort((a, b) => (b.edge_pct ?? 0) - (a.edge_pct ?? 0))
    return list
  }, [discrepancies, filter])

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 shadow-lg shadow-black/20 overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800">
        <h2 className="text-lg font-semibold text-gray-100">Discrepancies</h2>
        <p className="text-sm text-gray-500 mt-0.5">Data vs. market probability gaps</p>
      </div>

      {/* Filter buttons */}
      <div className="px-6 py-3 border-b border-gray-800 flex items-center gap-2 overflow-x-auto">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
              filter === cat
                ? 'bg-green-500/15 text-green-400 border border-green-500/30'
                : 'bg-gray-800 text-gray-400 border border-gray-700 hover:bg-gray-750 hover:text-gray-300'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[600px]">
        {filtered.length === 0 ? (
          <div className="py-12 text-center">
            <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <p className="text-gray-500 text-sm">No discrepancies detected</p>
            <p className="text-gray-600 text-xs mt-1">
              {filter !== 'All' ? `Try selecting "All" categories` : 'Data feeds are being analyzed...'}
            </p>
          </div>
        ) : (
          filtered.map((d, i) => <DiscrepancyCard key={d.id || i} data={d} />)
        )}
      </div>
    </div>
  )
}

function DiscrepancyCard({ data }) {
  const cat = (data.category || 'unknown').toLowerCase()
  const catStyle = CATEGORY_COLORS[cat] || { badge: 'bg-gray-500/10 text-gray-400 border-gray-500/20', dot: 'bg-gray-400' }
  const confidence = (data.confidence || 'low').toLowerCase()
  const confStyle = CONFIDENCE_COLORS[confidence] || CONFIDENCE_COLORS.low
  const direction = (data.direction || '').toUpperCase()
  const isBuyYes = direction.includes('YES') || direction.includes('BUY')

  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700/50 p-4 hover:border-gray-600/50 transition-all hover:bg-gray-800/80 animate-fade-in">
      {/* Top row */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <h3 className="text-sm font-medium text-gray-200 leading-snug flex-1">
          {data.event_name || 'Unknown Event'}
        </h3>
        <span className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border capitalize ${catStyle.badge}`}>
          {data.category || 'N/A'}
        </span>
      </div>

      {/* Probability row */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Market Prob.</p>
          <p className="text-sm font-semibold text-gray-300 tabular-nums">
            {data.market_probability != null ? `${(data.market_probability * 100).toFixed(1)}%` : '--'}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Data Implied</p>
          <p className="text-sm font-semibold text-gray-300 tabular-nums">
            {(data.data_implied_probability ?? data.data_implied) != null
              ? `${((data.data_implied_probability ?? data.data_implied) * 100).toFixed(1)}%`
              : '--'}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Edge</p>
          <p className="text-sm font-bold text-green-400 tabular-nums">
            {data.edge_pct != null ? `${(data.edge_pct * 100).toFixed(1)}%` : '--'}
          </p>
        </div>
      </div>

      {/* Bottom row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Direction chip */}
          {direction && (
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold ${
                isBuyYes
                  ? 'bg-green-500/15 text-green-400'
                  : 'bg-red-500/15 text-red-400'
              }`}
            >
              {direction.includes('YES') ? 'BUY YES' : direction.includes('NO') ? 'BUY NO' : direction}
            </span>
          )}

          {/* Confidence */}
          <div className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${confStyle.dot}`} />
            <span className={`text-xs capitalize ${confStyle.label}`}>{confidence}</span>
          </div>
        </div>

        {/* Data source */}
        {data.data_source && (
          <span className="text-xs text-gray-600 bg-gray-800 px-2 py-0.5 rounded border border-gray-700">
            {data.data_source}
          </span>
        )}
      </div>
    </div>
  )
}
