import React, { useMemo } from 'react'

const CONFIDENCE_COLORS = {
  high: { dot: 'bg-red-500', text: 'text-red-400', bg: 'border-red-500/20' },
  medium: { dot: 'bg-yellow-500', text: 'text-yellow-400', bg: 'border-yellow-500/20' },
  low: { dot: 'bg-gray-500', text: 'text-gray-400', bg: 'border-gray-500/20' },
}

export default function DiscrepancyFeed({ discrepancies, stats }) {
  // Get discrepancies from props or fallback to stats
  const rawDiscs = discrepancies?.length > 0
    ? discrepancies
    : (stats?.discrepancy_details || [])

  const sorted = useMemo(() => {
    const list = Array.isArray(rawDiscs) ? [...rawDiscs] : []
    list.sort((a, b) => (b.edge_pct ?? 0) - (a.edge_pct ?? 0))
    return list
  }, [rawDiscs])

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 shadow-lg shadow-black/20 overflow-hidden flex flex-col h-full">
      <div className="px-6 py-4 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Discrepancies</h2>
            <p className="text-sm text-gray-500 mt-0.5">Market prices vs. forecaster consensus</p>
          </div>
          {sorted.length > 0 && (
            <span className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-md font-medium">
              {sorted.length} found
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h3 className="text-gray-400 font-medium mb-1">Scanning for discrepancies</h3>
            <p className="text-gray-600 text-sm max-w-xs">
              Comparing market prices against forecaster consensus from Metaculus, GJOpen, and other sources.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {sorted.map((d, i) => (
              <DiscrepancyCard key={d.id || i} data={d} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function DiscrepancyCard({ data }) {
  const edge = (data.edge_pct ?? 0) * 100
  const marketProb = (data.market_probability ?? 0) * 100
  const consensusProb = (data.data_implied_probability ?? data.data_value ?? 0) * 100
  const direction = data.direction || ''
  const confidence = data.confidence || 'low'
  const colors = CONFIDENCE_COLORS[confidence] || CONFIDENCE_COLORS.low
  const notes = data.notes || ''
  const source = data.source || ''
  const isBuyYes = direction.toUpperCase().includes('YES')

  return (
    <div className="px-5 py-4 hover:bg-gray-800/30 transition-colors">
      {/* Header: event name + confidence */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <h4 className="text-sm font-medium text-gray-200 leading-snug flex-1">
          {data.event_name || 'Unknown Event'}
        </h4>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
          <span className={`text-xs ${colors.text}`}>{confidence}</span>
        </div>
      </div>

      {/* Direction badge + edge */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`text-xs font-bold px-2 py-0.5 rounded ${
          isBuyYes
            ? 'bg-green-500/15 text-green-400 border border-green-500/20'
            : 'bg-red-500/15 text-red-400 border border-red-500/20'
        }`}>
          {direction || 'EDGE'}
        </span>
        <span className="text-xs text-blue-400 font-semibold tabular-nums">
          {edge.toFixed(1)}% edge
        </span>
        {source && (
          <span className="text-xs text-gray-600">
            on {source}
          </span>
        )}
      </div>

      {/* Price comparison bar */}
      <div className="flex items-center gap-3 mb-2">
        <div className="flex-1">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500">Market</span>
            <span className="text-gray-300 font-medium tabular-nums">{marketProb.toFixed(1)}%</span>
          </div>
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-orange-500/60 rounded-full"
              style={{ width: `${Math.min(100, marketProb)}%` }}
            />
          </div>
        </div>
        <div className="text-gray-600 text-xs font-bold">vs</div>
        <div className="flex-1">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500">Consensus</span>
            <span className="text-blue-400 font-medium tabular-nums">{consensusProb.toFixed(1)}%</span>
          </div>
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500/60 rounded-full"
              style={{ width: `${Math.min(100, consensusProb)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Sources */}
      {notes && (
        <p className="text-[11px] text-gray-600 mt-1 leading-relaxed">{notes}</p>
      )}
    </div>
  )
}
