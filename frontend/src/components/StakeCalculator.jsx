import React, { useState, useMemo, useRef, useEffect } from 'react'

export default function StakeCalculator({ opportunity, onClose }) {
  const [bankroll, setBankroll] = useState(1000)
  const overlayRef = useRef(null)
  const inputRef = useRef(null)

  // Focus input on mount
  useEffect(() => {
    if (inputRef.current) inputRef.current.select()
  }, [])

  // Close on Escape
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  // Click outside to close
  function handleOverlayClick(e) {
    if (e.target === overlayRef.current) onClose()
  }

  const opp = opportunity
  const legs = opp?.legs || []
  const profitPct = opp?.profit_pct ?? 0

  // Calculate stakes for guaranteed-profit arbitrage
  // For each leg: stake_i = bankroll * (1/odds_i) / sum(1/odds_j)
  const calculations = useMemo(() => {
    if (legs.length === 0) return []

    // Get decimal odds for each leg
    const decimalOdds = legs.map((leg) => {
      if (leg.decimal_odds) return leg.decimal_odds
      if (leg.american_odds) {
        const am = leg.american_odds
        return am > 0 ? am / 100 + 1 : 100 / Math.abs(am) + 1
      }
      if (leg.implied_probability) return 1 / (leg.implied_probability / 100)
      return 2.0 // fallback
    })

    const inverseSum = decimalOdds.reduce((sum, odds) => sum + 1 / odds, 0)

    return legs.map((leg, i) => {
      const odds = decimalOdds[i]
      const stake = (bankroll * (1 / odds)) / inverseSum
      const payout = stake * odds
      return {
        ...leg,
        decimalOdds: odds,
        stake,
        payout,
      }
    })
  }, [legs, bankroll])

  const totalStaked = calculations.reduce((s, c) => s + c.stake, 0)
  const guaranteedPayout = calculations.length > 0 ? Math.min(...calculations.map((c) => c.payout)) : 0
  const guaranteedProfit = guaranteedPayout - totalStaked

  function copyLeg(calc) {
    const oddsStr =
      calc.american_odds != null
        ? (calc.american_odds > 0 ? `+${calc.american_odds}` : `${calc.american_odds}`)
        : `${calc.decimalOdds.toFixed(2)}`
    const text = `Bet $${calc.stake.toFixed(2)} on ${calc.outcome || calc.selection || 'selection'} (${oddsStr}) at ${calc.source || calc.book || calc.platform || 'book'}`
    navigator.clipboard.writeText(text).catch(() => {})
  }

  function formatOdds(leg, calc) {
    if (leg.american_odds != null) {
      return leg.american_odds > 0 ? `+${leg.american_odds}` : `${leg.american_odds}`
    }
    return calc.decimalOdds.toFixed(2)
  }

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
            <div className="flex items-center gap-3 mt-1.5">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-bold bg-green-500/20 text-green-300 tabular-nums">
                +{profitPct.toFixed(2)}% profit
              </span>
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
          {/* Quick amount buttons */}
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

        {/* Legs */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {calculations.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-gray-500 text-sm">No leg data available for this opportunity.</p>
            </div>
          ) : (
            calculations.map((calc, i) => (
              <div
                key={i}
                className="bg-gray-800/50 rounded-xl border border-gray-700/50 p-4 hover:border-gray-600/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-200">
                      {calc.outcome || calc.selection || `Leg ${i + 1}`}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {calc.source || calc.book || calc.platform || 'Unknown book'}
                      <span className="mx-1.5 text-gray-700">|</span>
                      Odds: <span className="text-gray-400 font-medium">{formatOdds(calc, calc)}</span>
                    </p>
                  </div>
                  <button
                    onClick={() => copyLeg(calc)}
                    title="Copy bet instruction"
                    className="shrink-0 p-1.5 rounded-md text-gray-500 hover:text-gray-300 hover:bg-gray-700 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-gray-900/50 rounded-lg p-2.5">
                    <p className="text-xs text-gray-500 mb-0.5">Stake</p>
                    <p className="text-base font-bold text-green-400 tabular-nums">
                      ${calc.stake.toFixed(2)}
                    </p>
                  </div>
                  <div className="bg-gray-900/50 rounded-lg p-2.5">
                    <p className="text-xs text-gray-500 mb-0.5">Payout</p>
                    <p className="text-base font-bold text-gray-200 tabular-nums">
                      ${calc.payout.toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer summary */}
        {calculations.length > 0 && (
          <div className="px-6 py-4 border-t border-gray-800 bg-gray-800/30">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Total Staked</p>
                <p className="text-sm font-bold text-gray-200 tabular-nums">${totalStaked.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Min. Payout</p>
                <p className="text-sm font-bold text-gray-200 tabular-nums">${guaranteedPayout.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Guaranteed Profit</p>
                <p className={`text-sm font-bold tabular-nums ${guaranteedProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {guaranteedProfit >= 0 ? '+' : ''}${guaranteedProfit.toFixed(2)}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
