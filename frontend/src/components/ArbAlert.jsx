import React, { useEffect, useRef, useCallback, useState } from 'react'

/**
 * Toast notification system for real-time arb alerts.
 * Slides in from top-right with optional sound chime.
 * Stacks up to 4 toasts, auto-dismisses after 6 seconds.
 */

// Web Audio API chime — no external audio files needed
function playChime(type = 'arb') {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.connect(gain)
    gain.connect(ctx.destination)

    if (type === 'arb') {
      // Rising double chime — new arb detected
      osc.type = 'sine'
      osc.frequency.setValueAtTime(587, ctx.currentTime)         // D5
      osc.frequency.setValueAtTime(784, ctx.currentTime + 0.12)  // G5
      gain.gain.setValueAtTime(0.15, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.3)
    } else if (type === 'high_value') {
      // Triple chime — high-value arb
      osc.type = 'sine'
      osc.frequency.setValueAtTime(523, ctx.currentTime)         // C5
      osc.frequency.setValueAtTime(659, ctx.currentTime + 0.1)   // E5
      osc.frequency.setValueAtTime(784, ctx.currentTime + 0.2)   // G5
      gain.gain.setValueAtTime(0.18, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.4)
    } else {
      // Soft ping — info/value bet
      osc.type = 'sine'
      osc.frequency.setValueAtTime(440, ctx.currentTime)
      gain.gain.setValueAtTime(0.08, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.15)
    }

    setTimeout(() => ctx.close(), 500)
  } catch {
    // Audio not supported — silent fail
  }
}

const TYPE_CONFIG = {
  arb: {
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    ),
    color: 'border-green-500/40 bg-green-500/5',
    iconColor: 'text-green-400',
    label: 'New Arb',
  },
  high_value: {
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: 'border-emerald-500/40 bg-emerald-500/5',
    iconColor: 'text-emerald-400',
    label: 'High Value',
  },
  value_bet: {
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    color: 'border-yellow-500/40 bg-yellow-500/5',
    iconColor: 'text-yellow-400',
    label: 'Value Bet',
  },
  expired: {
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: 'border-gray-600/40 bg-gray-600/5',
    iconColor: 'text-gray-400',
    label: 'Expired',
  },
}

export function useArbAlerts(soundEnabled = true) {
  const [toasts, setToasts] = useState([])
  const toastIdRef = useRef(0)

  const addToast = useCallback((toast) => {
    const id = ++toastIdRef.current
    const type = toast.type || 'arb'

    if (soundEnabled && (type === 'arb' || type === 'high_value' || type === 'value_bet')) {
      playChime(type)
    }

    setToasts(prev => {
      const next = [...prev, { ...toast, id, type, createdAt: Date.now() }]
      return next.slice(-4) // max 4 toasts
    })

    // Auto-dismiss after 6s
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 6000)

    return id
  }, [soundEnabled])

  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return { toasts, addToast, dismissToast }
}

export default function ArbAlert({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null

  return (
    <div className="fixed top-20 right-4 z-50 flex flex-col gap-2 w-[380px] max-w-[calc(100vw-2rem)]">
      {toasts.map((toast, i) => {
        const config = TYPE_CONFIG[toast.type] || TYPE_CONFIG.arb
        return (
          <div
            key={toast.id}
            className={`flex items-start gap-3 px-4 py-3 rounded-xl border shadow-xl shadow-black/30 backdrop-blur-md transition-all duration-300 ${config.color}`}
            style={{
              animation: 'slideInRight 0.3s ease-out',
              opacity: 1 - i * 0.05,
            }}
          >
            <div className={`flex-shrink-0 mt-0.5 ${config.iconColor}`}>
              {config.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-bold uppercase tracking-wide ${config.iconColor}`}>
                  {config.label}
                </span>
                {toast.profit && (
                  <span className="text-xs font-bold text-green-400">
                    +{(toast.profit * 100).toFixed(2)}%
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-300 mt-0.5 truncate">
                {toast.message || toast.event_name || 'New opportunity detected'}
              </p>
              {toast.platforms && (
                <div className="flex items-center gap-1.5 mt-1.5">
                  {toast.platforms.map((p, j) => (
                    <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-medium">
                      {p}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={() => onDismiss(toast.id)}
              className="flex-shrink-0 text-gray-600 hover:text-gray-300 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )
      })}

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
