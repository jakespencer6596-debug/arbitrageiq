import React, { useState } from 'react'

const CONFIDENCE_CONFIG = {
  high:   { bar: 'bg-mint-500', width: 'w-full',  label: 'HIGH', text: 'text-mint-400' },
  medium: { bar: 'bg-amber-500', width: 'w-2/3', label: 'MED',  text: 'text-amber-400' },
  low:    { bar: 'bg-gray-600', width: 'w-1/3',  label: 'LOW',  text: 'text-gray-500' },
}

const ARB_TYPE_BADGE = {
  overround:     { label: 'OVERROUND', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  multi_outcome: { label: 'MULTI-WAY', cls: 'bg-purple-500/10 text-purple-400 border-purple-500/20' },
  play_money:    { label: 'PLAY $',    cls: 'bg-gray-500/10 text-gray-500 border-gray-500/20' },
  value_bet:     { label: 'VALUE BET', cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  cross_platform: null,
}

function formatFreshness(seconds) {
  if (!seconds || seconds <= 0) return null
  if (seconds < 60) return { text: `${seconds}s`, cls: 'text-mint-400', dot: 'bg-mint-400' }
  if (seconds < 300) return { text: `${Math.floor(seconds / 60)}m`, cls: 'text-amber-400', dot: 'bg-amber-400' }
  return { text: `${Math.floor(seconds / 60)}m`, cls: 'text-rose-400', dot: 'bg-rose-400' }
}

function formatVolume(vol) {
  if (!vol || vol <= 0) return null
  if (vol >= 1e6) return `$${(vol / 1e6).toFixed(1)}M`
  if (vol >= 1e3) return `$${(vol / 1e3).toFixed(0)}K`
  return `$${vol.toFixed(0)}`
}

export default function ArbCard({ opp, onClick }) {
  const [expanded, setExpanded] = useState(false)

  const grossRaw = opp.profit_pct ?? 0
  const netRaw = opp.net_profit_pct ?? grossRaw
  const isVB = opp.arb_type === 'value_bet'
  const displayRaw = isVB ? Math.abs(opp.edge ?? grossRaw) : netRaw
  const netPct = displayRaw < 1 ? displayRaw * 100 : displayRaw
  const grossPct = grossRaw < 1 ? grossRaw * 100 : grossRaw
  const netOn1K = displayRaw < 1 ? displayRaw * 1000 : (displayRaw / 100) * 1000
  const confidence = opp.confidence || 'low'
  const conf = CONFIDENCE_CONFIG[confidence] || CONFIDENCE_CONFIG.low
  const legs = opp.legs || []
  const typeBadge = ARB_TYPE_BADGE[opp.arb_type]
  const freshness = formatFreshness(opp.freshness_seconds)
  const annRoi = opp.annualized_roi

  return (
    <div className="group relative bg-surface-1 border border-white/[0.04] rounded-2xl overflow-hidden hover:border-mint-500/20 transition-all duration-200 card-glow">
      {/* Top accent bar */}
      <div className={`h-[2px] ${conf.bar} ${conf.width} transition-all duration-300`} />

      <div className="p-4">
        {/* Profit + meta */}
        <div className="flex items-start justify-between mb-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xl font-bold font-mono tracking-tight ${
              netPct >= 5 ? 'text-mint-300' : netPct >= 2 ? 'text-mint-400' : 'text-mint-500'
            }`}>
              +{netPct.toFixed(2)}%
            </span>
            {grossPct !== netPct && (
              <span className="text-[10px] text-gray-600 font-mono line-through">{grossPct.toFixed(1)}%</span>
            )}
            {typeBadge && (
              <span className={`text-[9px] border px-1.5 py-0.5 rounded font-bold tracking-wide ${typeBadge.cls}`}>
                {typeBadge.label}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {freshness && (
              <div className="flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${freshness.dot} ${freshness.dot === 'bg-mint-400' ? 'animate-pulse' : ''}`} />
                <span className={`text-[10px] font-mono font-medium ${freshness.cls}`}>{freshness.text}</span>
              </div>
            )}
            <span className="text-mint-400 font-bold font-mono text-sm">
              ${netOn1K.toFixed(0)}
              <span className="text-gray-600 font-normal text-[9px] ml-0.5">/$1K</span>
            </span>
          </div>
        </div>

        {/* Event name */}
        <p className="text-[13px] text-gray-200 font-medium mb-3 leading-snug line-clamp-2">
          {(opp.event_name || 'Unknown Event').replace(/^\[.*?\]\s*/, '')}
        </p>

        {/* Confidence + ROI */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-14 h-1 bg-surface-3 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${conf.bar} ${conf.width} transition-all`} />
              </div>
              <span className={`text-[9px] font-bold font-mono ${conf.text}`}>{conf.label}</span>
            </div>
            {annRoi != null && annRoi > 0 && (
              <span className="text-[10px] text-gray-500 font-mono">
                {(annRoi * 100).toFixed(0)}% <span className="text-gray-600">ann</span>
              </span>
            )}
          </div>
          <span className="text-[10px] text-gray-600">{legs.length} leg{legs.length !== 1 ? 's' : ''}</span>
        </div>

        {/* Platform legs */}
        <div className="flex items-center gap-1.5 flex-wrap">
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
                className="group/leg flex items-center gap-1 text-[11px] bg-surface-2 text-gray-400 pl-2 pr-1.5 py-1 rounded-lg border border-white/[0.04] hover:text-mint-400 hover:border-mint-500/20 transition-colors"
              >
                <span className="font-medium">{source}</span>
                <span className="text-gray-600 text-[9px]">{leg.outcome}</span>
                {vol && <span className="text-[8px] text-gray-700 ml-0.5">{vol}</span>}
                <svg className="w-2.5 h-2.5 opacity-0 group-hover/leg:opacity-100 transition-opacity text-mint-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            )
          })}
          {legs.length > 3 && !expanded && (
            <button onClick={(e) => { e.stopPropagation(); setExpanded(true) }}
              className="text-[10px] text-gray-600 hover:text-gray-300 transition-colors px-1.5 py-1">
              +{legs.length - 3}
            </button>
          )}
        </div>

        {/* Expanded fee breakdown */}
        {expanded && legs.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/[0.04] space-y-1 animate-fade-in">
            {legs.map((leg, i) => {
              const fees = leg.fees || {}
              const hasFees = (fees.trade_fee || 0) + (fees.profit_fee || 0) + (fees.withdrawal_fee || 0) > 0
              return (
                <div key={i} className="flex items-center justify-between text-[10px] text-gray-500">
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded-md bg-surface-3 text-gray-500 flex items-center justify-center text-[9px] font-bold font-mono">{i + 1}</span>
                    <span className="font-medium text-gray-300">{leg.source}</span>
                    <span className="text-gray-600">{leg.outcome}</span>
                  </div>
                  <div className="flex items-center gap-2.5 font-mono">
                    <span>{leg.decimal_odds?.toFixed(3)}x</span>
                    <span>${leg.stake_dollars?.toFixed(0)}</span>
                    {hasFees && (
                      <span className="text-rose-400/60 text-[9px]">
                        -{((fees.trade_fee || 0) * 100 + (fees.profit_fee || 0) * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Click target */}
      <button onClick={onClick} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" aria-label="View details" />
    </div>
  )
}
