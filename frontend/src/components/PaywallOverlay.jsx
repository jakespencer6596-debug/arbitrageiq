import React from 'react'

export default function PaywallOverlay({ count, onUpgrade }) {
  return (
    <div className="relative">
      {/* Blurred content hint */}
      <div className="blur-sm opacity-20 pointer-events-none select-none py-4 px-5 space-y-2.5">
        {[...Array(Math.min(count || 3, 4))].map((_, i) => (
          <div key={i} className="flex items-center gap-3 py-2.5">
            <div className="w-16 h-7 bg-mint-500/15 rounded-lg" />
            <div className="flex-1 h-3 bg-surface-3 rounded" />
            <div className="w-14 h-3 bg-surface-3 rounded" />
            <div className="w-20 h-5 bg-surface-4 rounded-lg" />
          </div>
        ))}
      </div>

      {/* Overlay */}
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface-0/80 backdrop-blur-[2px]">
        <div className="text-center px-6">
          <div className="w-10 h-10 rounded-xl bg-mint-500/10 border border-mint-500/20 flex items-center justify-center mx-auto mb-3">
            <svg className="w-5 h-5 text-mint-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h3 className="text-sm text-gray-200 font-semibold mb-1">
            {count > 0 ? `${count} more available` : 'Premium content'}
          </h3>
          <p className="text-[11px] text-gray-500 mb-4 max-w-[240px] mx-auto leading-relaxed">
            Upgrade for full access to all opportunities, signals, and execution tools.
          </p>
          <button onClick={onUpgrade}
            className="bg-mint-500 hover:bg-mint-400 text-surface-0 font-semibold text-xs px-5 py-2 rounded-xl transition-all shadow-md shadow-mint-500/20">
            Unlock Pro
          </button>
        </div>
      </div>
    </div>
  )
}
