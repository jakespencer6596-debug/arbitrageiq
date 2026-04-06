import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function AdminDashboard({ onClose }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionMsg, setActionMsg] = useState('')

  useEffect(() => {
    loadStats()
    const interval = setInterval(loadStats, 30000)
    return () => clearInterval(interval)
  }, [])

  async function loadStats() {
    try {
      const data = await api.adminStats()
      setStats(data)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function setRole(userId, role) {
    try {
      await api.adminSetRole(userId, role)
      setActionMsg(`User ${userId} role set to ${role}`)
      loadStats()
    } catch (err) {
      setActionMsg(`Error: ${err.message}`)
    }
  }

  async function setTier(userId, tier) {
    try {
      await api.adminSetTier(userId, tier)
      setActionMsg(`User ${userId} tier set to ${tier}`)
      loadStats()
    } catch (err) {
      setActionMsg(`Error: ${err.message}`)
    }
  }

  if (loading) {
    return (
      <div className="fixed inset-0 z-[80] bg-gray-950/95 flex items-center justify-center">
        <div className="animate-spin h-8 w-8 border-2 border-green-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[80] bg-gray-950/95 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-100">Admin Dashboard</h1>
            <p className="text-gray-500 text-sm mt-1">Internal stats and user management</p>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-red-400 text-sm mb-6">
            {error}
          </div>
        )}

        {actionMsg && (
          <div className="bg-green-500/10 border border-green-500/20 rounded-lg px-4 py-3 text-green-400 text-sm mb-6">
            {actionMsg}
            <button onClick={() => setActionMsg('')} className="ml-3 text-green-600 hover:text-green-400">dismiss</button>
          </div>
        )}

        {stats && (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <KpiCard label="Total Users" value={stats.users?.total || 0} color="blue" />
              <KpiCard label="Premium Users" value={stats.users?.premium || 0} color="green" />
              <KpiCard label="Active Arbs" value={stats.data?.active_arbs || 0} color="green" />
              <KpiCard label="Discrepancies" value={stats.data?.active_discrepancies || 0} color="yellow" />
              <KpiCard label="Active Prices" value={stats.data?.active_prices || 0} color="blue" />
              <KpiCard label="Tracked Markets" value={stats.data?.tracked_markets || 0} color="blue" />
              <KpiCard label="Admin/Staff" value={stats.users?.admin || 0} color="purple" />
              <KpiCard label="Active Category" value={stats.active_category || 'none'} color="gray" isText />
            </div>

            {/* Data Sources */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Data Sources</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(stats.data?.sources || {}).map(([source, count]) => (
                  <div key={source} className="bg-gray-800/50 rounded-lg p-3">
                    <p className="text-xs text-gray-500 capitalize">{source}</p>
                    <p className="text-lg font-bold text-gray-200 tabular-nums">{count}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Platform Health */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Platform Health</h2>
              <div className="space-y-2">
                {(stats.platforms || []).map((p) => (
                  <div key={p.name} className="flex items-center justify-between bg-gray-800/30 rounded-lg px-4 py-2">
                    <div className="flex items-center gap-3">
                      <span className={`w-2.5 h-2.5 rounded-full ${p.status === 'healthy' ? 'bg-green-500' : p.status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'}`} />
                      <span className="text-sm text-gray-300 font-medium">{p.name}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-gray-500">{p.status}</span>
                      {p.failures > 0 && (
                        <span className="text-xs text-red-400">{p.failures} failures</span>
                      )}
                      {p.last_error && (
                        <span className="text-xs text-gray-600 truncate max-w-[200px]" title={p.last_error}>
                          {p.last_error.substring(0, 40)}...
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Users Table */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Users ({stats.recent_users?.length || 0})</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 text-xs uppercase border-b border-gray-800">
                      <th className="px-3 py-2">ID</th>
                      <th className="px-3 py-2">Email</th>
                      <th className="px-3 py-2">Role</th>
                      <th className="px-3 py-2">Tier</th>
                      <th className="px-3 py-2">Created</th>
                      <th className="px-3 py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/50">
                    {(stats.recent_users || []).map((u) => (
                      <tr key={u.id} className="hover:bg-gray-800/30">
                        <td className="px-3 py-2 text-gray-400 tabular-nums">{u.id}</td>
                        <td className="px-3 py-2 text-gray-200">{u.email}</td>
                        <td className="px-3 py-2">
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            u.role === 'admin' ? 'bg-red-500/10 text-red-400' :
                            u.role === 'employee' ? 'bg-purple-500/10 text-purple-400' :
                            'bg-gray-500/10 text-gray-400'
                          }`}>{u.role || 'user'}</span>
                        </td>
                        <td className="px-3 py-2">
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            u.tier !== 'free' ? 'bg-green-500/10 text-green-400' : 'bg-gray-500/10 text-gray-400'
                          }`}>{u.tier}</span>
                        </td>
                        <td className="px-3 py-2 text-gray-500 text-xs">{u.created?.substring(0, 10)}</td>
                        <td className="px-3 py-2">
                          <div className="flex gap-1">
                            <select
                              onChange={(e) => { if (e.target.value) setRole(u.id, e.target.value); e.target.value = '' }}
                              className="bg-gray-800 border border-gray-700 text-gray-400 text-xs rounded px-1 py-0.5"
                              defaultValue=""
                            >
                              <option value="" disabled>Role</option>
                              <option value="user">User</option>
                              <option value="employee">Employee</option>
                              <option value="admin">Admin</option>
                            </select>
                            <select
                              onChange={(e) => { if (e.target.value) setTier(u.id, e.target.value); e.target.value = '' }}
                              className="bg-gray-800 border border-gray-700 text-gray-400 text-xs rounded px-1 py-0.5"
                              defaultValue=""
                            >
                              <option value="" disabled>Tier</option>
                              <option value="free">Free</option>
                              <option value="daily">Daily</option>
                              <option value="weekly">Weekly</option>
                              <option value="monthly">Monthly</option>
                            </select>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function KpiCard({ label, value, color, isText }) {
  const colors = {
    blue: 'border-blue-500/20 text-blue-400',
    green: 'border-green-500/20 text-green-400',
    yellow: 'border-yellow-500/20 text-yellow-400',
    purple: 'border-purple-500/20 text-purple-400',
    red: 'border-red-500/20 text-red-400',
    gray: 'border-gray-500/20 text-gray-400',
  }
  return (
    <div className={`bg-gray-900 rounded-xl border p-4 ${colors[color] || colors.gray}`}>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`${isText ? 'text-sm' : 'text-2xl'} font-bold tabular-nums`}>{value}</p>
    </div>
  )
}
