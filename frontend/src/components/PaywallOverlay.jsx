import React from 'react'

export default function PaywallOverlay({ count, onUpgrade }) {
  return (
    <div className="relative">
      {/* Blurred content hint */}
      <div className="blur-sm opacity-30 pointer-events-none select-none py-4 px-6 space-y-3">
        {[...Array(Math.min(count || 3, 4))].map((_, i) => (
          <div key={i} className="flex items-center gap-4 py-3">
            <div className="w-20 h-8 bg-green-500/20 rounded-md" />
            <div className="flex-1 h-4 bg-gray-700 rounded" />
            <div className="w-16 h-4 bg-gray-700 rounded" />
            <div className="w-24 h-6 bg-gray-800 rounded-md" />
            <div className="w-16 h-4 bg-green-500/20 rounded" />
          </div>
        ))}
      </div>

      {/* Overlay CTA */}
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/80 backdrop-blur-[2px] rounded-lg">
        <div className="text-center px-6">
          <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h3 className="text-gray-100 font-semibold mb-1">
            {count > 0 ? `${count} more opportunities available` : 'Premium Content'}
          </h3>
          <p className="text-gray-500 text-sm mb-4 max-w-xs mx-auto">
            Upgrade to Premium for full access to all arbitrage opportunities, discrepancy signals, and execution tools
          </p>
          <button
            onClick={onUpgrade}
            className="bg-green-600 hover:bg-green-500 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors"
          >
            Unlock Premium
          </button>
        </div>
      </div>
    </div>
  )
}
