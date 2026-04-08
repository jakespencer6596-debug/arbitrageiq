import React, { useEffect, useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { api } from '../api'
import AnimatedCounter from './AnimatedCounter'

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'history', label: 'Arb History' },
  { key: 'platforms', label: 'Platform Pairs' },
]

const PLATFORM_COLORS = {
  polymarket: '#8B5CF6',
  kalshi: '#3B82F6',
  predictit: '#EF4444',
  smarkets: '#F59E0B',
  manifold: '#10B981',
  sxbet: '#EC4899',
  betfair: '#F97316',
  matchbook: '#06B6D4',
  opinion: '#8B5CF6',
  metaforecast: '#6366F1',
}

function getPlatformColor(name) {
  const key = (name || '').toLowerCase()
  for (const [k, v] of Object.entries(PLATFORM_COLORS)) {
    if (key.includes(k)) return v
  }
  return '#6B7280'
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-xl text-xs">
      <p className="text-gray-400 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-gray-200">
          <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ backgroundColor: p.color }} />
          {p.name}: <span className="font-bold">{typeof p.value === 'number' ? p.value.toFixed(2) : p.value}</span>
        </p>
      ))}
    </div>
  )
}

export default function AnalyticsPanel() {
  const [tab, setTab] = useState('overview')
  const [analytics, setAnalytics] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [a, h] = await Promise.allSettled([
          api.getAnalytics(),
          api.getHistory(),
        ])
        if (a.status === 'fulfilled') setAnalytics(a.value)
        if (h.status === 'fulfilled') setHistory(h.value?.history || h.value || [])
      } catch { /* silent */ }
      setLoading(false)
    }
    load()
    const interval = setInterval(load, 60000)
    return () => clearInterval(interval)
  }, [])

  if (loading && !analytics) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-8">
        <div className="flex items-center justify-center gap-3 text-gray-500">
          <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading analytics...
        </div>
      </div>
    )
  }

  // Build chart data from history
  const timelineData = buildTimelineData(history)
  const platformPairData = analytics?.platform_pairs || []
  const totalArbs = analytics?.total_arbs_ever || history.length
  const activeNow = analytics?.active_now || 0
  const avgProfit = analytics?.avg_peak_profit || 0
  const avgDuration = analytics?.avg_duration_minutes || 0

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 shadow-lg shadow-black/20 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Analytics</h2>
          <p className="text-xs text-gray-500 mt-0.5">Historical arbitrage performance</p>
        </div>
        <div className="flex gap-1 bg-gray-800/50 rounded-lg p-0.5">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                tab === t.key
                  ? 'bg-gray-700 text-white shadow-sm'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {tab === 'overview' && (
          <OverviewTab
            totalArbs={totalArbs}
            activeNow={activeNow}
            avgProfit={avgProfit}
            avgDuration={avgDuration}
            timelineData={timelineData}
          />
        )}
        {tab === 'history' && (
          <HistoryTab history={history} />
        )}
        {tab === 'platforms' && (
          <PlatformPairsTab pairs={platformPairData} />
        )}
      </div>
    </div>
  )
}


function OverviewTab({ totalArbs, activeNow, avgProfit, avgDuration, timelineData }) {
  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Total Arbs Detected"
          value={totalArbs}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          }
          iconColor="text-green-400"
          format="integer"
        />
        <KpiCard
          label="Active Now"
          value={activeNow}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
          iconColor="text-emerald-400"
          format="integer"
        />
        <KpiCard
          label="Avg Peak Profit"
          value={avgProfit}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1" />
            </svg>
          }
          iconColor="text-yellow-400"
          format="percent"
        />
        <KpiCard
          label="Avg Duration"
          value={avgDuration}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          iconColor="text-blue-400"
          format="minutes"
        />
      </div>

      {/* Arb frequency chart */}
      {timelineData.length > 1 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-3">Arb Detections Over Time</h3>
          <div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timelineData}>
                <defs>
                  <linearGradient id="arbGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10B981" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#10B981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                <XAxis dataKey="time" tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="count"
                  name="Arbs"
                  stroke="#10B981"
                  strokeWidth={2}
                  fill="url(#arbGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {timelineData.length <= 1 && (
        <div className="text-center py-8 text-gray-600 text-sm">
          Charts will populate as arb history accumulates
        </div>
      )}
    </div>
  )
}


function HistoryTab({ history }) {
  const sorted = [...history].sort((a, b) => {
    const da = new Date(b.last_seen_at || b.first_detected_at || 0)
    const db = new Date(a.last_seen_at || a.first_detected_at || 0)
    return da - db
  })

  const exportCSV = () => {
    const headers = ['Event', 'Category', 'Type', 'Source A', 'Source B', 'Peak Profit %', 'Times Detected', 'Duration (s)', 'First Detected', 'Last Seen', 'Status']
    const rows = sorted.map(h => [
      h.event_name || '', h.category || '', h.arb_type || '', h.source_a || '', h.source_b || '',
      ((h.peak_profit_pct || 0) * 100).toFixed(2), h.times_detected || 1, h.duration_seconds || 0,
      h.first_detected || '', h.last_seen || '', h.status || ''
    ])
    const csv = [headers, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `arbitrageiq-arb-history-${new Date().toISOString().slice(0,10)}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  if (sorted.length === 0) {
    return (
      <div className="text-center py-12 text-gray-600">
        <svg className="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <p className="text-sm">No arb history yet</p>
        <p className="text-xs text-gray-700 mt-1">History builds up as the scanner runs</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      {sorted.length > 0 && (
        <div className="flex justify-end mb-3">
          <button onClick={exportCSV} className="text-[10px] text-gray-500 hover:text-gray-300 font-medium px-2.5 py-1.5 rounded-lg hover:bg-white/[0.04] transition-colors flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export CSV
          </button>
        </div>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
            <th className="pb-3 pr-4">Event</th>
            <th className="pb-3 pr-4">Platforms</th>
            <th className="pb-3 pr-4 text-right">Peak Profit</th>
            <th className="pb-3 pr-4 text-right">Times Seen</th>
            <th className="pb-3 pr-4 text-right">Duration</th>
            <th className="pb-3 text-right">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {sorted.slice(0, 50).map((h, i) => {
            const dur = h.duration_seconds || 0
            const durStr = dur >= 3600
              ? `${Math.floor(dur / 3600)}h ${Math.floor((dur % 3600) / 60)}m`
              : dur >= 60
                ? `${Math.floor(dur / 60)}m ${dur % 60}s`
                : `${dur}s`

            return (
              <tr key={h.id || i} className="hover:bg-gray-800/30 transition-colors">
                <td className="py-3 pr-4">
                  <div className="max-w-[300px] truncate text-gray-200 font-medium">
                    {(h.event_name || '').replace(/^\[.*?\]\s*/, '')}
                  </div>
                  <div className="text-[10px] text-gray-600 mt-0.5">
                    {h.category} | {h.arb_type}
                  </div>
                </td>
                <td className="py-3 pr-4">
                  <div className="flex gap-1">
                    {h.source_a && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                        {h.source_a}
                      </span>
                    )}
                    {h.source_b && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                        {h.source_b}
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-3 pr-4 text-right">
                  <span className="text-green-400 font-bold">
                    {((h.peak_profit_pct || 0) * 100).toFixed(2)}%
                  </span>
                </td>
                <td className="py-3 pr-4 text-right text-gray-400 tabular-nums">
                  {h.times_detected || 1}x
                </td>
                <td className="py-3 pr-4 text-right text-gray-400 tabular-nums text-xs">
                  {durStr}
                </td>
                <td className="py-3 text-right">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                    h.status === 'active'
                      ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                      : 'bg-gray-800 text-gray-500'
                  }`}>
                    {h.status || 'expired'}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}


function PlatformPairsTab({ pairs }) {
  if (!pairs || pairs.length === 0) {
    return (
      <div className="text-center py-12 text-gray-600">
        <p className="text-sm">No platform pair data yet</p>
        <p className="text-xs text-gray-700 mt-1">Accumulates as arbs are detected across platforms</p>
      </div>
    )
  }

  const chartData = pairs.slice(0, 10).map(p => ({
    name: `${p.source_a} / ${p.source_b}`,
    count: p.count || 0,
    colorA: getPlatformColor(p.source_a),
    colorB: getPlatformColor(p.source_b),
  }))

  return (
    <div className="space-y-6">
      <h3 className="text-sm font-medium text-gray-400">Most Profitable Platform Pairs</h3>
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ left: 120 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" horizontal={false} />
            <XAxis type="number" tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis type="category" dataKey="name" tick={{ fill: '#9CA3AF', fontSize: 11 }} axisLine={false} tickLine={false} width={110} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="count" name="Arbs Found" radius={[0, 4, 4, 0]} maxBarSize={28}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.colorA} fillOpacity={0.8} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}


function KpiCard({ label, value, icon, iconColor, format }) {
  let displayValue
  if (format === 'percent') {
    displayValue = <AnimatedCounter value={value || 0} decimals={2} suffix="%" className="text-2xl font-bold text-gray-100" />
  } else if (format === 'minutes') {
    displayValue = <AnimatedCounter value={value || 0} decimals={1} suffix="m" className="text-2xl font-bold text-gray-100" />
  } else {
    displayValue = <AnimatedCounter value={value || 0} className="text-2xl font-bold text-gray-100" />
  }

  return (
    <div className="bg-gray-800/40 rounded-lg border border-gray-800 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">{label}</span>
        <span className={iconColor}>{icon}</span>
      </div>
      {displayValue}
    </div>
  )
}


function buildTimelineData(history) {
  if (!history || history.length === 0) return []

  // Group by hour
  const buckets = {}
  for (const h of history) {
    const dt = new Date(h.first_detected_at || h.last_seen_at)
    if (isNaN(dt.getTime())) continue
    const key = `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours()}:00`
    buckets[key] = (buckets[key] || 0) + 1
  }

  return Object.entries(buckets)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-24) // last 24 data points
    .map(([time, count]) => ({ time, count }))
}
