import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function AlertSettings({ onClose }) {
  const [settings, setSettings] = useState({
    alerts_enabled: true,
    alert_min_profit: 0.02,
    telegram_chat_id: '',
    discord_webhook_url: '',
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [testingTg, setTestingTg] = useState(false)
  const [testingDc, setTestingDc] = useState(false)

  useEffect(() => {
    api.getAlertSettings()
      .then(d => {
        if (!d.error) setSettings(s => ({ ...s, ...d }))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const res = await api.updateAlertSettings(settings)
      if (res.error) throw new Error(res.error)
      setMessage({ type: 'success', text: 'Settings saved' })
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setSaving(false)
    }
  }

  const handleTestTelegram = async () => {
    setTestingTg(true)
    try {
      const res = await fetch(
        (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/alerts/test',
        { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('aiq_token')}` } }
      )
      const d = await res.json()
      setMessage({ type: d.error ? 'error' : 'success', text: d.error || 'Test alert sent to Telegram' })
    } catch {
      setMessage({ type: 'error', text: 'Failed to send test' })
    } finally {
      setTestingTg(false)
    }
  }

  const profitOptions = [
    { value: 0.01, label: '1%+' },
    { value: 0.02, label: '2%+' },
    { value: 0.03, label: '3%+' },
    { value: 0.05, label: '5%+' },
    { value: 0.10, label: '10%+' },
  ]

  if (loading) {
    return (
      <Modal onClose={onClose}>
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-2 border-mint-500/20 border-t-mint-500 rounded-full animate-spin" />
        </div>
      </Modal>
    )
  }

  return (
    <Modal onClose={onClose}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-white">Alert Settings</h2>
          <p className="text-xs text-gray-500 mt-0.5">Get notified when opportunities appear</p>
        </div>
        <button onClick={onClose} className="p-1.5 text-gray-600 hover:text-gray-300 rounded-lg hover:bg-white/[0.04] transition-colors">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="space-y-6">
        {/* Master toggle */}
        <div className="flex items-center justify-between p-4 bg-surface-1 rounded-xl border border-white/[0.04]">
          <div>
            <p className="text-sm font-medium text-gray-200">Enable Alerts</p>
            <p className="text-[11px] text-gray-500 mt-0.5">Receive notifications for new opportunities</p>
          </div>
          <button
            onClick={() => setSettings(s => ({ ...s, alerts_enabled: !s.alerts_enabled }))}
            className={`relative w-11 h-6 rounded-full transition-colors ${settings.alerts_enabled ? 'bg-mint-500' : 'bg-gray-700'}`}
          >
            <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow-md transition-transform ${settings.alerts_enabled ? 'left-[22px]' : 'left-0.5'}`} />
          </button>
        </div>

        {/* Min profit threshold */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-2">Minimum Profit to Alert</label>
          <div className="flex gap-1.5">
            {profitOptions.map(opt => (
              <button
                key={opt.value}
                onClick={() => setSettings(s => ({ ...s, alert_min_profit: opt.value }))}
                className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${
                  settings.alert_min_profit === opt.value
                    ? 'bg-mint-500/15 text-mint-400 border border-mint-500/30'
                    : 'bg-surface-1 text-gray-500 border border-white/[0.04] hover:text-gray-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Telegram */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-gray-400 flex items-center gap-2">
              <svg className="w-4 h-4 text-blue-400" viewBox="0 0 24 24" fill="currentColor">
                <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
              </svg>
              Telegram Chat ID
            </label>
            <button
              onClick={handleTestTelegram}
              disabled={testingTg || !settings.telegram_chat_id}
              className="text-[10px] text-blue-400 hover:text-blue-300 font-medium disabled:text-gray-600 disabled:cursor-not-allowed"
            >
              {testingTg ? 'Sending...' : 'Send test'}
            </button>
          </div>
          <input
            type="text"
            value={settings.telegram_chat_id || ''}
            onChange={(e) => setSettings(s => ({ ...s, telegram_chat_id: e.target.value }))}
            placeholder="Your Telegram chat ID (send /start to @ArbitrageIQBot)"
            className="w-full bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-mint-500/40 focus:ring-1 focus:ring-mint-500/20 placeholder:text-gray-600 font-mono transition-colors"
          />
          <p className="text-[10px] text-gray-600">Send /start to the bot first to get your chat ID</p>
        </div>

        {/* Discord */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-gray-400 flex items-center gap-2">
            <svg className="w-4 h-4 text-indigo-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286z"/>
            </svg>
            Discord Webhook URL
          </label>
          <input
            type="url"
            value={settings.discord_webhook_url || ''}
            onChange={(e) => setSettings(s => ({ ...s, discord_webhook_url: e.target.value }))}
            placeholder="https://discord.com/api/webhooks/..."
            className="w-full bg-surface-0 border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-mint-500/40 focus:ring-1 focus:ring-mint-500/20 placeholder:text-gray-600 font-mono text-[11px] transition-colors"
          />
          <p className="text-[10px] text-gray-600">Server Settings → Integrations → Webhooks → Copy URL</p>
        </div>

        {/* Message */}
        {message && (
          <div className={`px-4 py-2.5 rounded-xl text-xs font-medium ${
            message.type === 'success' ? 'bg-mint-500/10 text-mint-400 border border-mint-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
          }`}>
            {message.text}
          </div>
        )}

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full bg-mint-500 hover:bg-mint-400 disabled:opacity-50 text-surface-0 font-semibold py-2.5 rounded-xl text-sm transition-all shadow-md shadow-mint-500/20"
        >
          {saving ? 'Saving...' : 'Save settings'}
        </button>
      </div>
    </Modal>
  )
}

function Modal({ children, onClose }) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative bg-surface-2 rounded-2xl border border-white/[0.06] p-6 w-full max-w-md shadow-2xl shadow-black/40 animate-slide-up max-h-[90vh] overflow-y-auto">
        {children}
      </div>
    </div>
  )
}
