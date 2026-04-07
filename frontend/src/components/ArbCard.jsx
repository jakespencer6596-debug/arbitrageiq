import React from 'react'

const CONFIDENCE_COLORS = { high: 'bg-green-500', medium: 'bg-yellow-500', low: 'bg-gray-500' }

function bookUrl(book, eventName) {
  const key = (book || '').toLowerCase().trim()
  const q = encodeURIComponent(eventName || '')
  if (key === 'polymarket') return `https://polymarket.com/markets?_q=${q}`
  if (key === 'kalshi') return `https://kalshi.com/markets`
  if (key === 'predictit') return 'https://www.predictit.org/markets'
  if (key === 'manifold') return `https://manifold.markets/search?q=${q}`
  if (key === 'smarkets') return `https://smarkets.com`
  return null
}

export default function ArbCard({ opp, onClick }) {
  const grossPctRaw = opp.profit_pct ?? 0
  const netPctRaw = opp.net_profit_pct ?? grossPctRaw
  const isVB = opp.arb_type === 'value_bet'
  const displayPctRaw = isVB ? Math.abs(opp.edge ?? grossPctRaw) : netPctRaw
  const netPct = displayPctRaw < 1 ? displayPctRaw * 100 : displayPctRaw
  const netOn1K = displayPctRaw < 1 ? displayPctRaw * 1000 : (displayPctRaw / 100) * 1000
  const isOverround = opp.arb_type === 'overround'
  const isValueBet = opp.arb_type === 'value_bet'
  const confidence = opp.confidence || 'low'
  const legs = opp.legs || []

  return (
    <div
      onClick={onClick}
      className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4 hover:border-gray-600 transition-colors active:bg-gray-800"
    >
      {/* Top row: profit + confidence */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${CONFIDENCE_COLORS[confidence]}`} />
          <span className={`text-lg font-bold tabular-nums ${netPct >= 3 ? 'text-green-300' : 'text-green-400'}`}>
            +{netPct.toFixed(2)}%
          </span>
          {isOverround && <span className="text-[10px] bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 px-1.5 py-0.5 rounded font-medium">OVERROUND</span>}
          {isValueBet && <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded font-medium">{opp.direction || 'VALUE'}</span>}
        </div>
        <span className="text-green-400 font-semibold tabular-nums text-sm">${netOn1K.toFixed(0)} on $1K</span>
      </div>

      {/* Event name */}
      <p className="text-sm text-gray-200 font-medium mb-3 leading-snug line-clamp-2">
        {opp.event_name || 'Unknown Event'}
      </p>

      {/* Platform links */}
      <div className="flex items-center gap-2 flex-wrap">
        {legs.length > 0
          ? legs.slice(0, 3).map((leg, i) => {
              const b = leg.source || ''
              const url = leg.market_url || bookUrl(b, opp.event_name)
              return (
                <a
                  key={i}
                  href={url || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs bg-gray-700 text-gray-300 px-2.5 py-1 rounded-lg border border-gray-600 hover:text-blue-400 hover:border-blue-500/40 min-h-[32px] flex items-center"
                >
                  {b} &#8599;
                </a>
              )
            })
          : <span className="text-xs text-gray-600">No platform data</span>}
        {legs.length > 3 && <span className="text-xs text-gray-600">+{legs.length - 3} more</span>}
      </div>
    </div>
  )
}
