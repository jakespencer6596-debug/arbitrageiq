import React from 'react'

export default function DiscrepancyFeed() {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 shadow-lg shadow-black/20 overflow-hidden flex flex-col h-full">
      <div className="px-6 py-4 border-b border-gray-800">
        <h2 className="text-lg font-semibold text-gray-100">Discrepancies</h2>
        <p className="text-sm text-gray-500 mt-0.5">Data vs. market probability gaps</p>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center py-16 px-6 text-center">
        <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
            />
          </svg>
        </div>
        <h3 className="text-gray-300 font-medium mb-2">Coming Soon</h3>
        <p className="text-gray-500 text-sm max-w-xs">
          The discrepancy engine compares market prices against real-world data sources.
          This feature is being redesigned for higher accuracy.
        </p>
      </div>
    </div>
  )
}
