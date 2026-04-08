import React, { useState, useMemo, useRef, useEffect } from 'react'

const PLATFORM_NOTES = {
  polymarket: 'Polymarket: No fees. USDC on Polygon network.',
  kalshi: 'Kalshi: ~2% spread cost. US-regulated exchange.',
  sxbet: 'SX Bet: 2% commission. Decentralized exchange.',
  opinion: 'Opinion: No fees. 3rd largest prediction market.',
}

export default function StakeCalculator({ opportunity, onClose }) {
  const [bankroll, setBankroll] = useState(1000)
  const overlayRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (inputRef.current) inputRef.current.select()
  }, [])

  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  function handleOverlayClick(e) {
    if (e.target === overlayRef.current) onClose()
  }

  const opp = opportunity
  const legs = opp?.legs || []
  const netPctRaw = opp?.net_profit_pct ?? opp?.profit_pct ?? 0
  const grossPctRaw = opp?.profit_pct ?? 0
  const netPct = netPctRaw < 1 ? netPctRaw * 100 : netPctRaw
  const grossPct = grossPctRaw < 1 ? grossPctRaw * 100 : grossPctRaw
  const confidence = opp?.confidence || 'low'
  const annRoi = opp?.annualized_roi != null ? (opp.annualized_roi < 1 ? opp.annualized_roi * 100 : opp.annualized_roi) : null

  const calculations = useMemo(() => {
    if (legs.length === 0) return []

    const decimalOdds = legs.map((leg) => {
      if (leg.decimal_odds) return leg.decimal_odds
      if (leg.implied_probability) return 1 / (leg.implied_probability / 100)
      return 2.0
    })

    const inverseSum = decimalOdds.reduce((sum, odds) => sum + 1 / odds, 0)

    return legs.map((leg, i) => {
      const odds = decimalOdds[i]
      const stake = (bankroll * (1 / odds)) / inverseSum
      const payout = stake * odds

      // Compute fees for this leg
      const fees = leg.fees || {}
      const tradeFee = stake * (fees.trade_fee || 0)
      const profit = payout - stake
      const profitFee = profit > 0 ? profit * (fees.profit_fee || 0) : 0
      const withdrawalFee = (stake + profit - profitFee) * (fees.withdrawal_fee || 0)
      const totalFees = tradeFee + profitFee + withdrawalFee

      return {
        ...leg,
        decimalOdds: odds,
        stake,
        payout,
        tradeFee,
        profitFee,
        withdrawalFee,
        totalFees,
        netPayout: payout - totalFees,
      }
    })
  }, [legs, bankroll])

  const totalStaked = calculations.reduce((s, c) => s + c.stake, 0)
  const grossPayout = calculations.length > 0 ? Math.min(...calculations.map((c) => c.payout)) : 0
  const grossProfit = grossPayout - totalStaked
  const totalFees = calculations.reduce((s, c) => s + c.totalFees, 0)
  const netProfit = grossProfit - totalFees

  function copyAllSteps() {
    const steps = calculations.map((calc, i) => {
      const src = calc.source || calc.book || calc.platform || 'Unknown'
      return `Step ${i + 1}: ${calc.outcome} on ${src} — Bet $${calc.stake.toFixed(2)}${calc.market_url ? `\n   Link: ${calc.market_url}` : ''}`
    })
    const text = [
      `=== ArbitrageIQ Execution Plan ===`,
      `Event: ${opp?.event_name || 'Unknown'}`,
      `Bankroll: $${bankroll}`,
      ``,
      ...steps,
      ``,
      `Total Staked: $${totalStaked.toFixed(2)}`,
      `Gross Profit: $${grossProfit.toFixed(2)}`,
      `Est. Fees: -$${totalFees.toFixed(2)}`,
      `Net Profit: $${netProfit.toFixed(2)} (${netPct.toFixed(2)}%)`,
      annRoi != null ? `Annualized ROI: ${annRoi.toFixed(0)}%` : '',
    ].filter(Boolean).join('\n')
    navigator.clipboard.writeText(text).catch(() => {})
  }

  function formatOdds(leg, calc) {
    if (leg.american_odds != null) {
      return leg.american_odds > 0 ? `+${leg.american_odds}` : `${leg.american_odds}`
    }
    return calc.decimalOdds.toFixed(2)
  }

  const confidenceColors = { high: 'text-green-400', medium: 'text-yellow-400', low: 'text-gray-400' }
  const confidenceDots = { high: 'bg-green-500', medium: 'bg-yellow-500', low: 'bg-gray-500' }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
    >
      <div className="bg-gray-900 rounded-2xl border border-gray-700 shadow-2xl shadow-black/50 w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-5 border-b border-gray-800 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-gray-100 truncate">
              {opp?.event_name || 'Stake Calculator'}
            </h2>
            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-bold bg-green-500/20 text-green-300 tabular-nums">
                +{netPct.toFixed(2)}% net
              </span>
              <span className="inline-flex items-center gap-1 text-xs">
                <span className={`w-1.5 h-1.5 rounded-full ${confidenceDots[confidence]}`} />
                <span className={confidenceColors[confidence]}>{confidence}</span>
              </span>
              {annRoi != null && (
                <span className="text-xs text-gray-500">
                  {annRoi >= 1000 ? `${(annRoi/1000).toFixed(0)}K` : annRoi.toFixed(0)}% ann.
                </span>
              )}
              {opp?.category && (
                <span className="text-xs text-gray-500 capitalize">{opp.category}</span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 p-2 -mr-2 -mt-1 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Bankroll input */}
        <div className="px-6 py-4 border-b border-gray-800 bg-gray-800/30">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-2">
            Bankroll
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 font-medium">$</span>
            <input
              ref={inputRef}
              type="number"
              min="1"
              step="100"
              value={bankroll}
              onChange={(e) => setBankroll(Math.max(1, parseFloat(e.target.value) || 0))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-8 pr-4 py-2.5 text-gray-100 font-semibold text-lg tabular-nums focus:outline-none focus:ring-2 focus:ring-green-500/40 focus:border-green-500/60 transition-all placeholder:text-gray-600"
              placeholder="1000"
            />
          </div>
          <div className="flex items-center gap-2 mt-2">
            {[100, 500, 1000, 5000, 10000].map((amt) => (
              <button
                key={amt}
                onClick={() => setBankroll(amt)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  bankroll === amt
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                    : 'bg-gray-800 text-gray-500 border border-gray-700 hover:text-gray-300 hover:bg-gray-750'
                }`}
              >
                ${amt >= 1000 ? `${amt / 1000}K` : amt}
              </button>
            ))}
          </div>
        </div>

        {/* Execution Steps + Legs */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {calculations.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-gray-500 text-sm">No leg data available for this opportunity.</p>
            </div>
          ) : (
            <>
              {/* Execution steps header */}
              <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-1">Execution Steps</div>

              {calculations.map((calc, i) => {
                const src = calc.source || calc.book || calc.platform || 'Unknown'
                const platformNote = PLATFORM_NOTES[src.toLowerCase()] || ''

                return (
                  <div
                    key={i}
                    className="bg-gray-800/50 rounded-xl border border-gray-700/50 p-4 hover:border-gray-600/50 transition-colors"
                  >
                    {/* Step number + outcome */}
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-green-500/20 text-green-400 text-xs font-bold">{i + 1}</span>
                          <p className="text-sm font-medium text-gray-200">
                            {calc.outcome || `Leg ${i + 1}`}
                          </p>
                        </div>
                        <p className="text-xs text-gray-500 mt-1 pl-7">
                          {calc.market_url ? (
                            <a
                              href={calc.market_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-400 hover:text-blue-300 hover:underline transition-colors"
                            >
                              {src} <span className="text-[10px]">&#8599;</span>
                            </a>
                          ) : src}
                          <span className="mx-1.5 text-gray-700">|</span>
                          Odds: <span className="text-gray-400 font-medium">{formatOdds(calc, calc)}</span>
                          {calc.volume > 0 && (
                            <>
                              <span className="mx-1.5 text-gray-700">|</span>
                              Vol: <span className={`font-medium ${calc.volume >= 10000 ? 'text-green-400' : calc.volume >= 1000 ? 'text-yellow-400' : 'text-red-400'}`}>
                                ${calc.volume >= 1000000 ? `${(calc.volume/1000000).toFixed(1)}M` : calc.volume >= 1000 ? `${(calc.volume/1000).toFixed(0)}K` : calc.volume.toFixed(0)}
                              </span>
                            </>
                          )}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2 pl-7">
                      <div className="bg-gray-900/50 rounded-lg p-2">
                        <p className="text-[10px] text-gray-500 mb-0.5">Stake</p>
                        <p className="text-sm font-bold text-green-400 tabular-nums">${calc.stake.toFixed(2)}</p>
                      </div>
                      <div className="bg-gray-900/50 rounded-lg p-2">
                        <p className="text-[10px] text-gray-500 mb-0.5">Payout</p>
                        <p className="text-sm font-bold text-gray-200 tabular-nums">${calc.payout.toFixed(2)}</p>
                      </div>
                      <div className="bg-gray-900/50 rounded-lg p-2">
                        <p className="text-[10px] text-gray-500 mb-0.5">Fees</p>
                        <p className={`text-sm font-bold tabular-nums ${calc.totalFees > 0 ? 'text-red-400' : 'text-gray-400'}`}>
                          {calc.totalFees > 0.01 ? `-$${calc.totalFees.toFixed(2)}` : '$0'}
                        </p>
                      </div>
                    </div>

                    {platformNote && (
                      <p className="text-[10px] text-gray-600 mt-2 pl-7">{platformNote}</p>
                    )}
                  </div>
                )
              })}
            </>
          )}
        </div>

        {/* Footer summary */}
        {calculations.length > 0 && (
          <div className="px-6 py-4 border-t border-gray-800 bg-gray-800/30 space-y-3">
            <div className="grid grid-cols-4 gap-3 text-center">
              <div>
                <p className="text-[10px] text-gray-500 mb-0.5">Total Staked</p>
                <p className="text-sm font-bold text-gray-200 tabular-nums">${totalStaked.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 mb-0.5">Gross Profit</p>
                <p className="text-sm font-bold text-gray-300 tabular-nums">${grossProfit.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 mb-0.5">Est. Fees</p>
                <p className={`text-sm font-bold tabular-nums ${totalFees > 0 ? 'text-red-400' : 'text-gray-400'}`}>
                  {totalFees > 0.01 ? `-$${totalFees.toFixed(2)}` : '$0'}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 mb-0.5">Net Profit</p>
                <p className={`text-sm font-bold tabular-nums ${netProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {netProfit >= 0 ? '+' : ''}${netProfit.toFixed(2)}
                </p>
              </div>
            </div>

            {/* Copy all steps button */}
            <button
              onClick={copyAllSteps}
              className="w-full py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy Execution Plan
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
