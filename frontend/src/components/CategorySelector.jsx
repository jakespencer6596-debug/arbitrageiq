import React, { useState } from 'react'

const CATEGORIES = [
  {
    key: 'politics',
    name: 'Politics',
    description: 'Elections, legislation, government, approval ratings',
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11m16-11v11M8 14v4m4-4v4m4-4v4" />
      </svg>
    ),
    color: 'purple',
  },
  {
    key: 'sports',
    name: 'Sports',
    description: 'NFL, NBA, MLB, NHL, soccer, MMA, Olympics',
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M12 2a10 10 0 110 20 10 10 0 010-20z" />
      </svg>
    ),
    color: 'green',
  },
  {
    key: 'crypto',
    name: 'Crypto & Finance',
    description: 'Bitcoin, Ethereum, stocks, inflation, interest rates',
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: 'orange',
  },
  {
    key: 'entertainment',
    name: 'Entertainment',
    description: 'Oscars, box office, music, TV, celebrities, pop culture',
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
      </svg>
    ),
    color: 'pink',
  },
  {
    key: 'science_tech',
    name: 'Science & Tech',
    description: 'AI, space, biotech, semiconductors, FDA approvals',
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
    color: 'blue',
  },
  {
    key: 'weather',
    name: 'Weather & Climate',
    description: 'Temperature records, hurricanes, storms, forecasts',
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
      </svg>
    ),
    color: 'cyan',
  },
  {
    key: 'other',
    name: 'Other',
    description: 'Everything else -- miscellaneous prediction markets',
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
    color: 'gray',
  },
]

const COLOR_MAP = {
  purple: {
    card: 'border-purple-500/30 hover:border-purple-400/60 hover:bg-purple-500/5',
    icon: 'bg-purple-500/10 text-purple-400',
    glow: 'group-hover:shadow-purple-500/10',
  },
  green: {
    card: 'border-green-500/30 hover:border-green-400/60 hover:bg-green-500/5',
    icon: 'bg-green-500/10 text-green-400',
    glow: 'group-hover:shadow-green-500/10',
  },
  orange: {
    card: 'border-orange-500/30 hover:border-orange-400/60 hover:bg-orange-500/5',
    icon: 'bg-orange-500/10 text-orange-400',
    glow: 'group-hover:shadow-orange-500/10',
  },
  pink: {
    card: 'border-pink-500/30 hover:border-pink-400/60 hover:bg-pink-500/5',
    icon: 'bg-pink-500/10 text-pink-400',
    glow: 'group-hover:shadow-pink-500/10',
  },
  blue: {
    card: 'border-blue-500/30 hover:border-blue-400/60 hover:bg-blue-500/5',
    icon: 'bg-blue-500/10 text-blue-400',
    glow: 'group-hover:shadow-blue-500/10',
  },
  cyan: {
    card: 'border-cyan-500/30 hover:border-cyan-400/60 hover:bg-cyan-500/5',
    icon: 'bg-cyan-500/10 text-cyan-400',
    glow: 'group-hover:shadow-cyan-500/10',
  },
  gray: {
    card: 'border-gray-500/30 hover:border-gray-400/60 hover:bg-gray-500/5',
    icon: 'bg-gray-500/10 text-gray-400',
    glow: 'group-hover:shadow-gray-500/10',
  },
}

export default function CategorySelector({ onSelectCategory }) {
  const [loading, setLoading] = useState(null)

  const handleSelect = async (key) => {
    setLoading(key)
    await onSelectCategory(key)
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4 py-12">
      {/* Branding */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-100 tracking-tight">
          Arbitrage<span className="text-green-400">IQ</span>
        </h1>
        <p className="text-gray-500 mt-3 text-lg max-w-md">
          Select a sector to scan for cross-platform arbitrage opportunities
        </p>
      </div>

      {/* Category Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 max-w-5xl w-full">
        {CATEGORIES.map((cat) => {
          const colors = COLOR_MAP[cat.color]
          const isLoading = loading === cat.key

          return (
            <button
              key={cat.key}
              onClick={() => handleSelect(cat.key)}
              disabled={loading !== null}
              className={`group relative flex flex-col items-start p-6 rounded-xl border bg-gray-900/50 transition-all duration-200 text-left ${colors.card} ${colors.glow} shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-wait`}
            >
              <div className={`w-14 h-14 rounded-lg flex items-center justify-center mb-4 ${colors.icon}`}>
                {isLoading ? (
                  <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  cat.icon
                )}
              </div>
              <h3 className="text-lg font-semibold text-gray-100 mb-1">{cat.name}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{cat.description}</p>
              {isLoading && (
                <p className="text-xs text-green-400 mt-3 animate-pulse">Scanning markets...</p>
              )}
            </button>
          )
        })}
      </div>

      {/* Footer */}
      <p className="text-gray-600 text-xs mt-12">
        Scanning Polymarket, Kalshi, SX Bet, Futuur, DraftKings &amp; 10+ exchanges
      </p>
    </div>
  )
}
