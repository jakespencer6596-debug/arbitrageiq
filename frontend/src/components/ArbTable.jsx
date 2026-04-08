import React, { useState, useMemo } from 'react'
import ArbCard from './ArbCard'

function bookUrl(book, eventName) {
  const key = (book || '').toLowerCase().trim()
  const q = encodeURIComponent(eventName || '')
  if (key === 'polymarket') return `https://polymarket.com/markets?_q=${q}`
  if (key === 'kalshi') return `https://kalshi.com/markets`
  if (key === 'sxbet') return 'https://sx.bet'
  if (key === 'opinion') return 'https://opinion.trade'
  if (key === 'futuur') return 'https://futuur.com'
  if (key === 'insight') return 'https://insightprediction.com'
  const books = { draftkings:'https://www.draftkings.com', fanduel:'https://www.fanduel.com', betmgm:'https://www.betmgm.com', bovada:'https://www.bovada.lv', bet365:'https://www.bet365.com', pinnacle:'https://www.pinnacle.com' }
  if (books[key]) return books[key]
  for (const [n, u] of Object.entries(books)) { if (key.includes(n)) return u }
  return null
}

const SORT_KEYS = {
  profit_pct: (a, b) => (b.net_profit_pct ?? b.profit_pct ?? 0) - (a.net_profit_pct ?? a.profit_pct ?? 0),
  event_name: (a, b) => (a.event_name || '').localeCompare(b.event_name || ''),
  category: (a, b) => (a.category || '').localeCompare(b.category || ''),
  profit_1k: (a, b) => (b.net_profit_on_1000 ?? 0) - (a.net_profit_on_1000 ?? 0),
  annualized: (a, b) => (b.annualized_roi ?? -1) - (a.annualized_roi ?? -1),
}

const ROWS_PER_PAGE = 25

export default function ArbTable({ opportunities, onSelectOpportunity }) {
  const [sortKey, setSortKey] = useState('profit_pct')
  const [sortAsc, setSortAsc] = useState(false)
  const [page, setPage] = useState(0)

  const handleSort = (key) => {
    if (sortKey === key) setSortAsc(v => !v)
    else { setSortKey(key); setSortAsc(false) }
  }

  const sorted = useMemo(() => {
    const list = [...(opportunities || [])]
    const fn = SORT_KEYS[sortKey] || SORT_KEYS.profit_pct
    list.sort((a, b) => sortAsc ? -fn(a, b) : fn(a, b))
    return list
  }, [opportunities, sortKey, sortAsc])

  React.useEffect(() => { setPage(0) }, [opportunities, sortKey, sortAsc])

  const totalPages = Math.max(1, Math.ceil(sorted.length / ROWS_PER_PAGE))
  const currentPage = Math.min(page, totalPages - 1)
  const rows = sorted.slice(currentPage * ROWS_PER_PAGE, (currentPage + 1) * ROWS_PER_PAGE)

  const SortIcon = ({ column }) => {
    if (sortKey !== column) return <svg className="w-3 h-3 text-gray-700 ml-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" /></svg>
    return <svg className="w-3 h-3 text-mint-400 ml-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={sortAsc ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} /></svg>
  }

  return (
    <div className="bg-surface-1 rounded-2xl border border-white/[0.04] card-glow overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/[0.04] flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-100">Arbitrage Opportunities</h2>
          <p className="text-[11px] text-gray-500 mt-0.5 font-mono">{sorted.length} active</p>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-mint-400 opacity-40" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-mint-500" />
          </span>
          <span className="text-[10px] text-gray-500 font-mono">SCANNING</span>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="py-20 flex flex-col items-center justify-center text-center px-6">
          <div className="w-14 h-14 rounded-2xl bg-surface-2 border border-white/[0.04] flex items-center justify-center mb-4 shimmer">
            <svg className="w-7 h-7 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <h3 className="text-sm text-gray-400 font-medium mb-1">Scanning for opportunities</h3>
          <p className="text-xs text-gray-600 max-w-xs">
            Cross-platform price discrepancies will appear here automatically when detected.
          </p>
        </div>
      ) : (
        <>
          {/* Mobile cards */}
          <div className="md:hidden p-3 space-y-2.5">
            {rows.map((opp) => (
              <ArbCard key={opp.id || `${opp.event_name}-${opp.profit_pct}`} opp={opp} onClick={() => onSelectOpportunity(opp)} />
            ))}
          </div>

          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] text-gray-600 uppercase tracking-[0.1em] border-b border-white/[0.04]">
                  <th className="px-5 py-3 cursor-pointer hover:text-gray-400 transition-colors select-none" onClick={() => handleSort('profit_pct')}>
                    Edge <SortIcon column="profit_pct" />
                  </th>
                  <th className="px-5 py-3 cursor-pointer hover:text-gray-400 transition-colors select-none" onClick={() => handleSort('event_name')}>
                    Event <SortIcon column="event_name" />
                  </th>
                  <th className="px-5 py-3 cursor-pointer hover:text-gray-400 transition-colors select-none" onClick={() => handleSort('category')}>
                    Category <SortIcon column="category" />
                  </th>
                  <th className="px-5 py-3">Platforms</th>
                  <th className="px-5 py-3 cursor-pointer hover:text-gray-400 transition-colors select-none" onClick={() => handleSort('profit_1k')}>
                    Net/$1K <SortIcon column="profit_1k" />
                  </th>
                  <th className="px-5 py-3 cursor-pointer hover:text-gray-400 transition-colors select-none" onClick={() => handleSort('annualized')}>
                    Ann. ROI <SortIcon column="annualized" />
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.02]">
                {rows.map((opp) => {
                  const grossRaw = opp.profit_pct ?? 0
                  const netRaw = opp.net_profit_pct ?? grossRaw
                  const isVB = opp.arb_type === 'value_bet'
                  const displayRaw = isVB ? Math.abs(opp.edge ?? grossRaw) : netRaw
                  const netPct = displayRaw < 1 ? displayRaw * 100 : displayRaw
                  const grossPct = grossRaw < 1 ? grossRaw * 100 : grossRaw
                  const netOn1K = isVB
                    ? (displayRaw < 1 ? displayRaw * 1000 : (displayRaw / 100) * 1000)
                    : (opp.net_profit_on_1000 ?? (netRaw < 1 ? netRaw * 1000 : (netRaw / 100) * 1000))
                  const isPlayMoney = opp.arb_type === 'play_money'
                  const isOverround = opp.arb_type === 'overround'
                  const isValueBet = opp.arb_type === 'value_bet'
                  const feeDiff = grossPct - netPct
                  const confidence = opp.confidence || 'low'
                  const confCfg = { high: 'bg-mint-500', medium: 'bg-amber-500', low: 'bg-gray-600' }
                  const freshness = opp.freshness_seconds ?? 0
                  const isStale = freshness > 120
                  const annRoi = opp.annualized_roi != null ? (opp.annualized_roi < 1 ? opp.annualized_roi * 100 : opp.annualized_roi) : null

                  return (
                    <tr
                      key={opp.id || `${opp.event_name}-${opp.profit_pct}-${opp.detected_at}`}
                      onClick={() => onSelectOpportunity(opp)}
                      className={`cursor-pointer transition-colors hover:bg-white/[0.02] ${isPlayMoney ? 'opacity-50' : ''}`}
                    >
                      <td className="px-5 py-3.5">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1.5">
                            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${confCfg[confidence]}`} />
                            <span className={`font-bold font-mono text-xs tabular-nums ${
                              netPct >= 5 ? 'text-mint-300' : netPct >= 2 ? 'text-mint-400' : 'text-mint-500'
                            }`}>
                              +{netPct.toFixed(2)}%
                            </span>
                            {isStale && <span className="text-[8px] text-amber-500/60 font-mono">STALE</span>}
                          </div>
                          {feeDiff > 0.01 && (
                            <span className="text-[9px] text-gray-700 mt-0.5 pl-3 font-mono">{grossPct.toFixed(1)}% - {feeDiff.toFixed(1)}% fees</span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-start gap-1.5">
                          {(isOverround || isValueBet) && (
                            <span className={`shrink-0 text-[8px] border px-1 py-0.5 rounded font-bold mt-0.5 ${
                              isValueBet ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            }`}>
                              {isValueBet ? 'VALUE' : 'OVRND'}
                            </span>
                          )}
                          <span className="text-[12px] text-gray-300 font-medium leading-snug">{opp.event_name || 'Unknown'}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <CatBadge category={opp.category} />
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-1 flex-wrap">
                          {opp.legs?.slice(0, 3).map((leg, i) => {
                            const b = leg.source || ''
                            const url = leg.market_url || bookUrl(b, opp.event_name)
                            return url ? (
                              <a key={i} href={url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                                className="text-[10px] bg-surface-2 text-gray-400 px-1.5 py-0.5 rounded border border-white/[0.04] hover:text-mint-400 hover:border-mint-500/20 transition-colors font-medium">
                                {b}
                              </a>
                            ) : (
                              <span key={i} className="text-[10px] bg-surface-2 text-gray-500 px-1.5 py-0.5 rounded border border-white/[0.04]">{b}</span>
                            )
                          })}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="text-mint-400 font-bold font-mono text-xs">${netOn1K.toFixed(2)}</span>
                      </td>
                      <td className="px-5 py-3.5">
                        {annRoi != null ? (
                          <span className={`text-xs font-bold font-mono ${annRoi >= 100 ? 'text-mint-300' : annRoi >= 20 ? 'text-mint-400' : 'text-gray-500'}`}>
                            {annRoi >= 1000 ? `${(annRoi/1000).toFixed(0)}K%` : `${annRoi.toFixed(0)}%`}
                          </span>
                        ) : <span className="text-xs text-gray-700 font-mono">--</span>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {sorted.length > ROWS_PER_PAGE && (
        <div className="px-5 py-3 border-t border-white/[0.04] flex items-center justify-between">
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={currentPage === 0}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${currentPage === 0 ? 'text-gray-700' : 'text-gray-400 hover:bg-white/[0.04]'}`}>
            Previous
          </button>
          <span className="text-[11px] text-gray-600 font-mono">{currentPage + 1} / {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={currentPage >= totalPages - 1}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${currentPage >= totalPages - 1 ? 'text-gray-700' : 'text-gray-400 hover:bg-white/[0.04]'}`}>
            Next
          </button>
        </div>
      )}
    </div>
  )
}

function CatBadge({ category }) {
  const cat = (category || '').toLowerCase()
  const m = {
    politics: 'text-purple-400 bg-purple-500/8 border-purple-500/15',
    sports: 'text-emerald-400 bg-emerald-500/8 border-emerald-500/15',
    crypto: 'text-amber-400 bg-amber-500/8 border-amber-500/15',
    entertainment: 'text-pink-400 bg-pink-500/8 border-pink-500/15',
    science_tech: 'text-blue-400 bg-blue-500/8 border-blue-500/15',
    weather: 'text-cyan-400 bg-cyan-500/8 border-cyan-500/15',
  }
  const cls = m[cat] || 'text-gray-500 bg-gray-500/8 border-gray-500/15'
  return <span className={`text-[9px] px-1.5 py-0.5 rounded border font-bold uppercase tracking-wide ${cls}`}>{category || 'N/A'}</span>
}
