import React, { useState, useEffect, useMemo } from 'react'
import { api } from '../api'
import AnimatedCounter from './AnimatedCounter'

export default function BetTracker() {
  const [bets, setBets] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editingId, setEditingId] = useState(null)

  const load = async () => {
    try {
      const [b, s] = await Promise.allSettled([api.getBets(), api.getBetsSummary()])
      if (b.status === 'fulfilled') setBets(b.value?.bets || b.value || [])
      if (s.status === 'fulfilled') setSummary(s.value)
    } catch { /* silent */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const sorted = useMemo(() =>
    [...bets].sort((a, b) => new Date(b.placed_at || 0) - new Date(a.placed_at || 0)),
  [bets])

  const handleAdd = async (bet) => {
    try {
      await api.createBet(bet)
      setShowAdd(false)
      load()
    } catch { /* silent */ }
  }

  const handleResolve = async (betId, status, payout) => {
    try {
      await api.updateBet(betId, { status, actual_payout: payout })
      setEditingId(null)
      load()
    } catch { /* silent */ }
  }

  const exportCSV = () => {
    const headers = ['Event', 'Platform', 'Direction', 'Odds', 'Stake', 'Status', 'P&L', 'Date']
    const rows = sorted.map(b => [
      b.event_name || '', b.platform || '', b.direction || '', b.odds || '',
      b.stake || '', b.status || '', b.profit_loss || '', b.placed_at || ''
    ])
    const csv = [headers, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `arbitrageiq-bets-${new Date().toISOString().slice(0,10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="bg-surface-1 rounded-2xl border border-white/[0.04] p-8 card-glow">
        <div className="flex items-center justify-center gap-3 text-gray-500">
          <div className="w-6 h-6 border-2 border-mint-500/20 border-t-mint-500 rounded-full animate-spin" />
          <span className="text-sm">Loading bet history...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryCard label="Total Bets" value={summary?.total_bets || bets.length} />
        <SummaryCard label="Win Rate" value={summary?.win_rate ? `${(summary.win_rate * 100).toFixed(0)}%` : '—'} />
        <SummaryCard label="Total P&L" value={summary?.total_pl != null ? `$${summary.total_pl.toFixed(2)}` : '—'} accent={summary?.total_pl > 0} negative={summary?.total_pl < 0} />
        <SummaryCard label="ROI" value={summary?.roi != null ? `${(summary.roi * 100).toFixed(1)}%` : '—'} accent={summary?.roi > 0} negative={summary?.roi < 0} />
      </div>

      {/* Bet list */}
      <div className="bg-surface-1 rounded-2xl border border-white/[0.04] card-glow overflow-hidden">
        <div className="px-5 py-4 border-b border-white/[0.04] flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Bet History</h2>
            <p className="text-[11px] text-gray-500 mt-0.5">{sorted.length} bet{sorted.length !== 1 ? 's' : ''} tracked</p>
          </div>
          <div className="flex items-center gap-2">
            {sorted.length > 0 && (
              <button onClick={exportCSV} className="text-[10px] text-gray-500 hover:text-gray-300 font-medium px-2.5 py-1.5 rounded-lg hover:bg-white/[0.04] transition-colors flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                CSV
              </button>
            )}
            <button onClick={() => setShowAdd(true)} className="text-xs bg-mint-500 hover:bg-mint-400 text-surface-0 font-semibold px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Bet
            </button>
          </div>
        </div>

        {sorted.length === 0 ? (
          <div className="py-16 text-center">
            <svg className="w-12 h-12 mx-auto text-gray-800 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <p className="text-sm text-gray-500">No bets tracked yet</p>
            <p className="text-xs text-gray-600 mt-1">Click "Add Bet" to start tracking your P&L</p>
          </div>
        ) : (
          <div className="divide-y divide-white/[0.03]">
            {sorted.map(bet => (
              <BetRow key={bet.id} bet={bet} editing={editingId === bet.id} onEdit={() => setEditingId(bet.id)} onResolve={handleResolve} onCancel={() => setEditingId(null)} />
            ))}
          </div>
        )}
      </div>

      {/* Add bet modal */}
      {showAdd && <AddBetModal onClose={() => setShowAdd(false)} onAdd={handleAdd} />}
    </div>
  )
}

function SummaryCard({ label, value, accent, negative }) {
  const color = negative ? 'text-rose-400' : accent ? 'text-mint-400' : 'text-gray-100'
  return (
    <div className="bg-surface-1 rounded-xl border border-white/[0.04] p-4 card-glow">
      <p className="text-[10px] uppercase tracking-[0.15em] text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-bold font-mono ${color}`}>{value}</p>
    </div>
  )
}

function BetRow({ bet, editing, onEdit, onResolve, onCancel }) {
  const [payout, setPayout] = useState('')
  const statusColors = {
    pending: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    won: 'bg-mint-500/10 text-mint-400 border-mint-500/20',
    lost: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    void: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
  }

  return (
    <div className="px-5 py-3.5 hover:bg-white/[0.01] transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0 mr-4">
          <p className="text-sm text-gray-200 font-medium truncate">{bet.event_name || 'Untitled'}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[10px] text-gray-500 font-mono">{bet.platform}</span>
            <span className="text-[10px] text-gray-600">|</span>
            <span className={`text-[10px] font-semibold ${bet.direction === 'YES' ? 'text-mint-400' : 'text-rose-400'}`}>{bet.direction}</span>
            <span className="text-[10px] text-gray-600">|</span>
            <span className="text-[10px] text-gray-400 font-mono">{bet.odds}x @ ${bet.stake}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {bet.profit_loss != null && (
            <span className={`text-xs font-bold font-mono ${bet.profit_loss >= 0 ? 'text-mint-400' : 'text-rose-400'}`}>
              {bet.profit_loss >= 0 ? '+' : ''}{bet.profit_loss.toFixed(2)}
            </span>
          )}
          <span className={`text-[9px] px-2 py-0.5 rounded-full border font-bold ${statusColors[bet.status] || statusColors.pending}`}>
            {(bet.status || 'pending').toUpperCase()}
          </span>
          {bet.status === 'pending' && !editing && (
            <button onClick={onEdit} className="text-[10px] text-gray-500 hover:text-gray-300 font-medium">Resolve</button>
          )}
        </div>
      </div>
      {editing && (
        <div className="mt-3 flex items-center gap-2 animate-fade-in">
          <input type="number" step="0.01" placeholder="Payout $" value={payout} onChange={e => setPayout(e.target.value)}
            className="w-24 bg-surface-0 border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-gray-100 font-mono focus:outline-none focus:border-mint-500/40" />
          <button onClick={() => onResolve(bet.id, 'won', parseFloat(payout) || 0)} className="text-[10px] bg-mint-500/15 text-mint-400 px-2.5 py-1.5 rounded-lg font-semibold hover:bg-mint-500/25">Won</button>
          <button onClick={() => onResolve(bet.id, 'lost', 0)} className="text-[10px] bg-rose-500/15 text-rose-400 px-2.5 py-1.5 rounded-lg font-semibold hover:bg-rose-500/25">Lost</button>
          <button onClick={() => onResolve(bet.id, 'void', parseFloat(payout) || bet.stake)} className="text-[10px] bg-gray-500/15 text-gray-400 px-2.5 py-1.5 rounded-lg font-semibold hover:bg-gray-500/25">Void</button>
          <button onClick={onCancel} className="text-[10px] text-gray-600 hover:text-gray-300 ml-1">Cancel</button>
        </div>
      )}
    </div>
  )
}

function AddBetModal({ onClose, onAdd }) {
  const [form, setForm] = useState({
    event_name: '', platform: '', direction: 'YES', odds: '', stake: '', notes: '',
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onAdd({
      ...form,
      odds: parseFloat(form.odds) || 0,
      stake: parseFloat(form.stake) || 0,
      potential_payout: (parseFloat(form.stake) || 0) * (parseFloat(form.odds) || 0),
    })
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative bg-surface-2 rounded-2xl border border-white/[0.06] p-6 w-full max-w-sm shadow-2xl shadow-black/40 animate-slide-up">
        <h2 className="text-lg font-semibold text-white mb-5">Log a Bet</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input placeholder="Event name" value={form.event_name} onChange={e => setForm(f => ({...f, event_name: e.target.value}))} required
            className="w-full bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-mint-500/40 placeholder:text-gray-600" />
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Platform" value={form.platform} onChange={e => setForm(f => ({...f, platform: e.target.value}))}
              className="bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-mint-500/40 placeholder:text-gray-600" />
            <div className="flex gap-1.5">
              {['YES', 'NO'].map(d => (
                <button key={d} type="button" onClick={() => setForm(f => ({...f, direction: d}))}
                  className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all ${
                    form.direction === d
                      ? d === 'YES' ? 'bg-mint-500/15 text-mint-400 border border-mint-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                      : 'bg-surface-0 text-gray-500 border border-white/[0.06]'
                  }`}
                >{d}</button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input type="number" step="0.01" placeholder="Odds (decimal)" value={form.odds} onChange={e => setForm(f => ({...f, odds: e.target.value}))} required
              className="bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 font-mono focus:outline-none focus:border-mint-500/40 placeholder:text-gray-600" />
            <input type="number" step="0.01" placeholder="Stake $" value={form.stake} onChange={e => setForm(f => ({...f, stake: e.target.value}))} required
              className="bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 font-mono focus:outline-none focus:border-mint-500/40 placeholder:text-gray-600" />
          </div>
          <input placeholder="Notes (optional)" value={form.notes} onChange={e => setForm(f => ({...f, notes: e.target.value}))}
            className="w-full bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-mint-500/40 placeholder:text-gray-600" />
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm font-medium text-gray-400 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] transition-colors">Cancel</button>
            <button type="submit" className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-mint-500 hover:bg-mint-400 text-surface-0 transition-colors shadow-md shadow-mint-500/20">Log Bet</button>
          </div>
        </form>
      </div>
    </div>
  )
}
