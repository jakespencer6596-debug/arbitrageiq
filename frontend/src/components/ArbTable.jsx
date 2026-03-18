import React, { useState, useMemo } from 'react'

function relativeTime(dateStr) {
  if (!dateStr) return '--'
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diff = Math.max(0, now - then)
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function isNew(dateStr) {
  if (!dateStr) return false
  return Date.now() - new Date(dateStr).getTime() < 60000
}

const SORT_KEYS = {
  profit_pct: (a, b) => (b.profit_pct ?? 0) - (a.profit_pct ?? 0),
  event_name: (a, b) => (a.event_name || '').localeCompare(b.event_name || ''),
  category: (a, b) => (a.category || '').localeCompare(b.category || ''),
  profit_1k: (a, b) => (b.profit_pct ?? 0) - (a.profit_pct ?? 0),
  detected_at: (a, b) => new Date(b.detected_at || 0) - new Date(a.detected_at || 0),
}

export default function ArbTable({ opportunities, onSelectOpportunity }) {
  const [sortKey, setSortKey] = useState('profit_pct')
  const [sortAsc, setSortAsc] = useState(false)

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortAsc((v) => !v)
    } else {
      setSortKey(key)
      setSortAsc(false)
    }
  }

  const sorted = useMemo(() => {
    const list = [...(opportunities || [])]
    const fn = SORT_KEYS[sortKey] || SORT_KEYS.profit_pct
    list.sort((a, b) => {
      const result = fn(a, b)
      return sortAsc ? -result : result
    })
    return list
  }, [opportunities, sortKey, sortAsc])

  const SortIcon = ({ column }) => {
    if (sortKey !== column) {
      return (
        <svg className="w-3.5 h-3.5 text-gray-600 ml-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      )
    }
    return (
      <svg className="w-3.5 h-3.5 text-green-400 ml-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d={sortAsc ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'}
        />
      </svg>
    )
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 shadow-lg shadow-black/20 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Arbitrage Opportunities</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {sorted.length} active {sorted.length === 1 ? 'opportunity' : 'opportunities'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-gray-500">Auto-updating</span>
        </div>
      </div>

      {sorted.length === 0 ? (
        /* Empty state */
        <div className="py-20 flex flex-col items-center justify-center text-center px-6">
          <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4 shimmer">
            <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
          <h3 className="text-gray-400 font-medium mb-1">No arbitrage opportunities detected yet</h3>
          <p className="text-gray-600 text-sm max-w-sm">
            The scanner is running. Opportunities will appear here automatically when cross-market price discrepancies are found.
          </p>
        </div>
      ) : (
        /* Table */
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                <th
                  className="px-6 py-3 cursor-pointer hover:text-gray-300 transition-colors select-none"
                  onClick={() => handleSort('profit_pct')}
                >
                  Profit % <SortIcon column="profit_pct" />
                </th>
                <th
                  className="px-6 py-3 cursor-pointer hover:text-gray-300 transition-colors select-none"
                  onClick={() => handleSort('event_name')}
                >
                  Event <SortIcon column="event_name" />
                </th>
                <th
                  className="px-6 py-3 cursor-pointer hover:text-gray-300 transition-colors select-none"
                  onClick={() => handleSort('category')}
                >
                  Category <SortIcon column="category" />
                </th>
                <th className="px-6 py-3">Books</th>
                <th
                  className="px-6 py-3 cursor-pointer hover:text-gray-300 transition-colors select-none"
                  onClick={() => handleSort('profit_1k')}
                >
                  Profit on $1K <SortIcon column="profit_1k" />
                </th>
                <th
                  className="px-6 py-3 cursor-pointer hover:text-gray-300 transition-colors select-none"
                  onClick={() => handleSort('detected_at')}
                >
                  Time <SortIcon column="detected_at" />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {sorted.map((opp) => {
                const profitPctRaw = opp.profit_pct ?? 0
                // profit_pct from API is 0-1 scale (0.023 = 2.3%), convert to display %
                const profitPct = profitPctRaw < 1 ? profitPctRaw * 100 : profitPctRaw
                const profitOn1K = opp.profit_on_base ?? (profitPctRaw < 1 ? profitPctRaw * 1000 : (profitPctRaw / 100) * 1000)
                const books = opp.legs?.map((l) => l.source || l.book || l.platform).filter(Boolean) || []
                const freshRow = isNew(opp.detected_at)

                return (
                  <tr
                    key={opp.id || opp.event_name + opp.detected_at}
                    onClick={() => onSelectOpportunity(opp)}
                    className={`cursor-pointer transition-colors hover:bg-gray-800/60 group ${
                      freshRow ? 'animate-row-highlight' : ''
                    }`}
                  >
                    {/* Profit % */}
                    <td className="px-6 py-3.5">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold tabular-nums ${
                          profitPct >= 5
                            ? 'bg-green-500/20 text-green-300'
                            : profitPct >= 2
                            ? 'bg-green-500/10 text-green-400'
                            : 'bg-green-500/5 text-green-500'
                        }`}
                      >
                        +{profitPct.toFixed(2)}%
                      </span>
                    </td>

                    {/* Event */}
                    <td className="px-6 py-3.5">
                      <span className="text-gray-200 font-medium group-hover:text-white transition-colors">
                        {opp.event_name || 'Unknown Event'}
                      </span>
                    </td>

                    {/* Category */}
                    <td className="px-6 py-3.5">
                      <CategoryBadge category={opp.category} />
                    </td>

                    {/* Books */}
                    <td className="px-6 py-3.5">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {books.length > 0
                          ? books.map((b, i) => (
                              <span
                                key={i}
                                className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-md border border-gray-700"
                              >
                                {b}
                              </span>
                            ))
                          : <span className="text-gray-600">--</span>}
                      </div>
                    </td>

                    {/* Profit on $1K */}
                    <td className="px-6 py-3.5">
                      <span className="text-green-400 font-semibold tabular-nums">
                        ${profitOn1K.toFixed(2)}
                      </span>
                    </td>

                    {/* Time */}
                    <td className="px-6 py-3.5">
                      <span className={`text-xs tabular-nums ${freshRow ? 'text-green-400 font-medium' : 'text-gray-500'}`}>
                        {relativeTime(opp.detected_at)}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function CategoryBadge({ category }) {
  const cat = (category || 'unknown').toLowerCase()
  const colors = {
    weather: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    economic: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    political: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    sports: 'bg-green-500/10 text-green-400 border-green-500/20',
    crypto: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    entertainment: 'bg-pink-500/10 text-pink-400 border-pink-500/20',
  }
  const cls = colors[cat] || 'bg-gray-500/10 text-gray-400 border-gray-500/20'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border capitalize ${cls}`}>
      {category || 'N/A'}
    </span>
  )
}
