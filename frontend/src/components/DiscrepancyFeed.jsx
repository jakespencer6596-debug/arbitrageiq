import React, { useMemo, useState } from 'react'

const CONFIDENCE_CONFIG = {
  high:   { dot: 'bg-red-500',    text: 'text-red-400',    bar: 'bg-red-500',    label: 'HIGH',  width: 'w-full' },
  medium: { dot: 'bg-yellow-500', text: 'text-yellow-400', bar: 'bg-yellow-500', label: 'MED',   width: 'w-2/3' },
  low:    { dot: 'bg-gray-500',   text: 'text-gray-400',   bar: 'bg-gray-600',   label: 'LOW',   width: 'w-1/3' },
}

const PLATFORM_URLS = {
  predictit:      (id) => id?.startsWith('http') ? id : `https://www.predictit.org/markets/detail/${id}`,
  polymarket:     (id) => id?.startsWith('http') ? id : `https://polymarket.com/markets?_q=${encodeURIComponent(id)}`,
  kalshi:         (id) => id?.startsWith('http') ? id : `https://kalshi.com/markets/${id}`,
  smarkets:       (id) => id?.startsWith('http') ? id : `https://smarkets.com`,
  manifold:       (id) => id?.startsWith('http') ? id : `https://manifold.markets`,
  betfair:        ()   => 'https://www.betfair.com',
  sxbet:          ()   => 'https://sx.bet',
  opinion:        ()   => 'https://opinion.trade',
  matchbook:      ()   => 'https://www.matchbook.com',
}

const CONSENSUS_SOURCE_URLS = {
  predictit:      'https://www.predictit.org',
  polymarket:     'https://polymarket.com',
  kalshi:         'https://kalshi.com',
  smarkets:       'https://smarkets.com',
  manifold:       'https://manifold.markets',
  betfair:        'https://www.betfair.com',
  metaculus:      'https://www.metaculus.com',
  gjopen:         'https://www.gjopen.com',
  fantasyscotus:  'https://fantasyscotus.net',
  foretold:       'https://www.foretold.io',
  infer:          'https://www.infer-pub.com',
  hypermind:      'https://www.hypermind.com',
  insight:        'https://insightprediction.com',
  sxbet:          'https://sx.bet',
  opinion:        'https://opinion.trade',
}

function parseNoteSources(notes) {
  if (!notes) return []
  // Parse "6 sources | predictit: 4%, betfair: 15%, fantasyscotus: 13%"
  const pipeIdx = notes.indexOf('|')
  if (pipeIdx === -1) return []
  const sourceStr = notes.substring(pipeIdx + 1).trim()
  const parts = sourceStr.split(',').map(s => s.trim()).filter(Boolean)

  return parts.map(part => {
    const match = part.match(/^([^:]+):\s*([\d.]+)%?$/)
    if (!match) return null
    const name = match[1].trim()
    const prob = parseFloat(match[2]) / 100
    const url = CONSENSUS_SOURCE_URLS[name.toLowerCase()] || null
    return { name, prob, url }
  }).filter(Boolean)
}

function getMarketUrl(source, marketId) {
  if (marketId?.startsWith('http')) return marketId
  const fn = PLATFORM_URLS[source?.toLowerCase()]
  return fn ? fn(marketId) : null
}

export default function DiscrepancyFeed({ discrepancies, stats }) {
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
            <h2 className="text-lg font-semibold text-gray-100">Value Signals</h2>
            <p className="text-xs text-gray-500 mt-0.5">Market prices vs. cross-platform consensus</p>
          </div>
          {sorted.length > 0 && (
            <span className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2.5 py-1 rounded-md font-bold tabular-nums">
              {sorted.length} found
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4 shimmer">
              <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h3 className="text-gray-400 font-medium mb-1">Scanning for signals</h3>
            <p className="text-gray-600 text-sm max-w-xs">
              Comparing market prices against cross-platform consensus from multiple forecasting sources.
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
  const [expanded, setExpanded] = useState(false)

  const edge = (data.edge_pct ?? 0) * 100
  const marketProb = (data.market_probability ?? 0) * 100
  const consensusProb = (data.data_implied_probability ?? data.data_value ?? 0) * 100
  const direction = data.direction || ''
  const confidence = data.confidence || 'low'
  const conf = CONFIDENCE_CONFIG[confidence] || CONFIDENCE_CONFIG.low
  const source = data.source || ''
  const isBuyYes = direction.toUpperCase().includes('YES')
  const marketUrl = getMarketUrl(source, data.market_id)
  const sources = parseNoteSources(data.notes)
  const sourceCount = sources.length
  const detectedAt = data.detected_at ? new Date(data.detected_at) : null

  // Clean event name — strip duplicate " -- " pattern from PredictIt
  let eventName = data.event_name || 'Unknown Event'
  if (eventName.includes(' -- ')) {
    const parts = eventName.split(' -- ')
    // If both sides are very similar, just use the first
    if (parts.length === 2 && parts[0].length > 20 && parts[1].length > 20) {
      eventName = parts[0]
    }
  }

  return (
    <div
      className={`transition-colors ${expanded ? 'bg-gray-800/20' : 'hover:bg-gray-800/20'}`}
    >
      {/* Clickable header area */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-5 py-4"
      >
        {/* Row 1: Event name + confidence */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <h4 className="text-sm font-medium text-gray-200 leading-snug flex-1">
            {eventName}
          </h4>
          <div className="flex items-center gap-1.5 shrink-0">
            <div className="w-10 h-1 bg-gray-700 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${conf.bar} ${conf.width}`} />
            </div>
            <span className={`text-[10px] font-semibold ${conf.text}`}>{conf.label}</span>
          </div>
        </div>

        {/* Row 2: Direction + edge + source link */}
        <div className="flex items-center gap-2 mb-3">
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${
            isBuyYes
              ? 'bg-green-500/15 text-green-400 border border-green-500/20'
              : 'bg-red-500/15 text-red-400 border border-red-500/20'
          }`}>
            {direction || 'EDGE'}
          </span>
          <span className="text-xs text-blue-400 font-bold tabular-nums">
            {edge.toFixed(1)}% edge
          </span>
          {source && (
            <span className="text-[10px] text-gray-500">on</span>
          )}
          {marketUrl ? (
            <a
              href={marketUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-xs text-gray-400 hover:text-blue-400 underline underline-offset-2 decoration-gray-700 hover:decoration-blue-500/40 transition-colors"
            >
              {source} &#8599;
            </a>
          ) : (
            <span className="text-xs text-gray-500">{source}</span>
          )}
          {sourceCount > 0 && (
            <span className="text-[10px] text-gray-600 ml-auto">
              {sourceCount} source{sourceCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Row 3: Price comparison bars */}
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <div className="flex items-center justify-between text-[10px] mb-1">
              <span className="text-gray-500 uppercase tracking-wide">Market</span>
              <span className="text-gray-300 font-bold tabular-nums">{marketProb.toFixed(1)}%</span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-orange-500/70 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(2, marketProb))}%` }}
              />
            </div>
          </div>
          <div className="text-gray-700 text-[10px] font-bold">vs</div>
          <div className="flex-1">
            <div className="flex items-center justify-between text-[10px] mb-1">
              <span className="text-gray-500 uppercase tracking-wide">Consensus</span>
              <span className="text-blue-400 font-bold tabular-nums">{consensusProb.toFixed(1)}%</span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500/70 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(2, consensusProb))}%` }}
              />
            </div>
          </div>
        </div>

        {/* Expand indicator */}
        <div className="flex items-center justify-center mt-2">
          <svg
            className={`w-4 h-4 text-gray-600 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="px-5 pb-5 space-y-4 animate-fade-in">

          {/* Source breakdown table */}
          {sources.length > 0 && (
            <div>
              <h5 className="text-[10px] uppercase tracking-widest text-gray-500 font-semibold mb-2">
                Source Breakdown
              </h5>
              <div className="bg-gray-800/40 rounded-lg border border-gray-700/50 divide-y divide-gray-700/30">
                {sources.map((s, i) => {
                  const prob = s.prob * 100
                  const diff = prob - marketProb
                  const isHigher = diff > 0
                  return (
                    <div key={i} className="flex items-center justify-between px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className="w-5 text-center text-[10px] text-gray-600 font-mono">{i + 1}</span>
                        {s.url ? (
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs font-medium text-gray-300 hover:text-blue-400 underline underline-offset-2 decoration-gray-700 hover:decoration-blue-500/40 transition-colors"
                          >
                            {s.name} &#8599;
                          </a>
                        ) : (
                          <span className="text-xs font-medium text-gray-300">{s.name}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        {/* Mini probability bar */}
                        <div className="w-20 h-1 bg-gray-700 rounded-full overflow-hidden hidden sm:block">
                          <div
                            className="h-full bg-blue-500/50 rounded-full"
                            style={{ width: `${Math.min(100, Math.max(2, prob))}%` }}
                          />
                        </div>
                        <span className="text-xs font-bold tabular-nums text-gray-200 w-12 text-right">
                          {prob.toFixed(1)}%
                        </span>
                        <span className={`text-[10px] font-medium tabular-nums w-14 text-right ${
                          isHigher ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {isHigher ? '+' : ''}{diff.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  )
                })}

                {/* Summary row */}
                <div className="flex items-center justify-between px-3 py-2 bg-gray-800/40">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wide font-semibold">
                    Consensus (median)
                  </span>
                  <div className="flex items-center gap-3">
                    <div className="w-20 hidden sm:block" />
                    <span className="text-xs font-bold tabular-nums text-blue-400 w-12 text-right">
                      {consensusProb.toFixed(1)}%
                    </span>
                    <span className="text-[10px] font-bold tabular-nums text-blue-400 w-14 text-right">
                      {edge.toFixed(1)}% edge
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Action section */}
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              {/* Signal explanation */}
              <p className="text-[11px] text-gray-500 leading-relaxed max-w-sm">
                {isBuyYes ? (
                  <>The market prices this at <span className="text-orange-400 font-medium">{marketProb.toFixed(0)}%</span>, but {sourceCount} source{sourceCount !== 1 ? 's' : ''} suggest <span className="text-blue-400 font-medium">{consensusProb.toFixed(0)}%</span> is more accurate. Potential <span className="text-green-400 font-medium">{direction}</span> opportunity.</>
                ) : (
                  <>The market prices this at <span className="text-orange-400 font-medium">{marketProb.toFixed(0)}%</span>, but consensus across {sourceCount} source{sourceCount !== 1 ? 's' : ''} is only <span className="text-blue-400 font-medium">{consensusProb.toFixed(0)}%</span>. The market may be overpriced — <span className="text-red-400 font-medium">{direction}</span>.</>
                )}
              </p>
              {detectedAt && (
                <p className="text-[10px] text-gray-600">
                  Detected {detectedAt.toLocaleTimeString()} &middot; {data.data_source || 'consensus'}
                </p>
              )}
            </div>

            {/* Trade button */}
            {marketUrl && (
              <a
                href={marketUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors shrink-0"
              >
                Trade on {source}
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
