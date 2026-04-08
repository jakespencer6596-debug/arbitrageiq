import React, { useState } from 'react'

const CONFIDENCE_CONFIG = {
  high:   { color: 'bg-green-500', text: 'text-green-400', bar: 'bg-green-500', width: 'w-full',  label: 'HIGH' },
  medium: { color: 'bg-yellow-500', text: 'text-yellow-400', bar: 'bg-yellow-500', width: 'w-2/3', label: 'MED' },
  low:    { color: 'bg-gray-500', text: 'text-gray-400', bar: 'bg-gray-600', width: 'w-1/3',  label: 'LOW' },
}

const ARB_TYPE_BADGE = {
  overround:    { label: 'OVERROUND', cls: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  multi_outcome:{ label: 'MULTI-WAY', cls: 'bg-purple-500/10 text-purple-400 border-purple-500/20' },
  play_money:   { label: 'PLAY MONEY', cls: 'bg-gray-500/10 text-gray-400 border-gray-500/20' },
  value_bet:    { label: 'VALUE BET', cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  cross_platform: null,
}

function formatFreshness(seconds) {
  if (!seconds || seconds <= 0) return null
  if (seconds < 60) return { text: `${seconds}s`, color: 'text-green-400', dot: 'bg-green-400' }
  if (seconds < 300) return { text: `${Math.floor(seconds / 60)}m`, color: 'text-yellow-400', dot: 'bg-yellow-400' }
  return { text: `${Math.floor(seconds / 60)}m`, color: 'text-red-400', dot: 'bg-red-400' }
}

function formatVolume(vol) {
  if (!vol || vol <= 0) return null
  if (vol >= 1_000_000) return `$${(vol / 1_000_000).toFixed(1)}M`
  if (vol >= 1_000) return `$${(vol / 1_000).toFixed(0)}K`
  return `$${vol.toFixed(0)}`
}

export default function ArbCard({ opp, onClick }) {
  const [expanded, setExpanded] = useState(false)

  const grossPctRaw = opp.profit_pct ?? 0
  const netPctRaw = opp.net_profit_pct ?? grossPctRaw
  const isVB = opp.arb_type === 'value_bet'
  const displayPctRaw = isVB ? Math.abs(opp.edge ?? grossPctRaw) : netPctRaw
  const netPct = displayPctRaw < 1 ? displayPctRaw * 100 : displayPctRaw
  const grossPct = grossPctRaw < 1 ? grossPctRaw * 100 : grossPctRaw
  const netOn1K = displayPctRaw < 1 ? displayPctRaw * 1000 : (displayPctRaw / 100) * 1000
  const confidence = opp.confidence || 'low'
  const conf = CONFIDENCE_CONFIG[confidence] || CONFIDENCE_CONFIG.low
  const legs = opp.legs || []
  const typeBadge = ARB_TYPE_BADGE[opp.arb_type]
  const freshness = formatFreshness(opp.freshness_seconds)
  const annualizedRoi = opp.annualized_roi

  // Determine profit color intensity
  const profitColorClass = netPct >= 5
    ? 'text-green-300 drop-shadow-[0_0_8px_rgba(34,197,94,0.4)]'
    : netPct >= 2
      ? 'text-green-400'
      : 'text-green-500'

  return (
    <div
      className="group relative bg-gray-800/50 border border-gray-700/50 rounded-xl overflow-hidden hover:border-gray-600 transition-all duration-200 hover:shadow-lg hover:shadow-black/20"
    >
      {/* Confidence bar — thin colored stripe at top */}
      <div className={`h-0.5 ${conf.bar} ${conf.width} transition-all`} />

      <div className="p-4">
        {/* Row 1: Profit + badges */}
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xl font-bold tabular-nums tracking-tight ${profitColorClass}`}>
              +{netPct.toFixed(2)}%
            </span>
            {grossPct !== netPct && (
              <span className="text-[10px] text-gray-500 tabular-nums line-through">
                {grossPct.toFixed(2)}%
              </span>
            )}
            {typeBadge && (
              <span className={`text-[10px] border px-1.5 py-0.5 rounded font-semibold ${typeBadge.cls}`}>
                {typeBadge.label}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {freshness && (
              <div className="flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${freshness.dot} ${freshness.dot === 'bg-green-400' ? 'animate-pulse' : ''}`} />
                <span className={`text-[10px] font-medium ${freshness.color}`}>{freshness.text}</span>
              </div>
            )}
            <span className="text-green-400 font-bold tabular-nums text-sm">
              ${netOn1K.toFixed(0)}
              <span className="text-gray-600 font-normal text-[10px] ml-0.5">/ $1K</span>
            </span>
          </div>
        </div>

        {/* Row 2: Event name */}
        <p className="text-sm text-gray-200 font-medium mb-3 leading-snug line-clamp-2">
          {(opp.event_name || 'Unknown Event').replace(/^\[.*?\]\s*/, '')}
        </p>

        {/* Row 3: Confidence + ROI + legs */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            {/* Confidence meter */}
            <div className="flex items-center gap-1.5">
              <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${conf.bar} ${conf.width} transition-all`} />
              </div>
              <span className={`text-[10px] font-semibold ${conf.text}`}>{conf.label}</span>
            </div>
            {/* Annualized ROI */}
            {annualizedRoi != null && annualizedRoi > 0 && (
              <span className="text-[10px] text-gray-500">
                <span className="text-gray-400 font-medium">{(annualizedRoi * 100).toFixed(0)}%</span> ann.
              </span>
            )}
          </div>
          {/* Leg count */}
          <span className="text-[10px] text-gray-500">
            {legs.length} leg{legs.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Row 4: Platform legs (collapsed) */}
        <div className="flex items-center gap-2 flex-wrap">
          {legs.slice(0, expanded ? legs.length : 3).map((leg, i) => {
            const source = leg.source || ''
            const url = leg.market_url || ''
            const vol = formatVolume(leg.volume)
            return (
              <a
                key={i}
                href={url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="group/leg flex items-center gap-1.5 text-xs bg-gray-700/60 text-gray-300 pl-2.5 pr-2 py-1.5 rounded-lg border border-gray-600/50 hover:text-blue-400 hover:border-blue-500/40 transition-colors"
              >
                <span className="font-medium">{source}</span>
                <span className="text-gray-500 text-[10px]">{leg.outcome}</span>
                {vol && <span className="text-[9px] text-gray-600 ml-0.5">{vol}</span>}
                <svg className="w-3 h-3 opacity-0 group-hover/leg:opacity-100 transition-opacity text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            )
          })}
          {legs.length > 3 && !expanded && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(true) }}
              className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors px-2 py-1"
            >
              +{legs.length - 3} more
            </button>
          )}
        </div>

        {/* Expanded detail: fee breakdown */}
        {expanded && legs.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-700/50 space-y-1.5">
            {legs.map((leg, i) => {
              const fees = leg.fees || {}
              const hasFees = (fees.trade_fee || 0) + (fees.profit_fee || 0) + (fees.withdrawal_fee || 0) > 0
              return (
                <div key={i} className="flex items-center justify-between text-[11px] text-gray-400">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-gray-700 text-gray-400 flex items-center justify-center text-[10px] font-bold">
                      {i + 1}
                    </span>
                    <span className="font-medium text-gray-300">{leg.source}</span>
                    <span className="text-gray-500">{leg.outcome}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="tabular-nums">{leg.decimal_odds?.toFixed(3)}x</span>
                    <span className="tabular-nums">${leg.stake_dollars?.toFixed(0)}</span>
                    {hasFees && (
                      <span className="text-red-400/70 text-[10px]">
                        -{((fees.trade_fee || 0) * 100 + (fees.profit_fee || 0) * 100).toFixed(0)}% fees
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Click handler for the card body */}
      <button
        onClick={onClick}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        aria-label="View opportunity details"
      />
    </div>
  )
}
