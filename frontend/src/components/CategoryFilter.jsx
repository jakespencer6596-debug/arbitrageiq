import React from 'react'

const CATEGORIES = [
  { key: null, name: 'All', color: 'mint' },
  { key: 'politics', name: 'Politics', color: 'purple' },
  { key: 'sports', name: 'Sports', color: 'emerald' },
  { key: 'crypto', name: 'Crypto', color: 'amber' },
  { key: 'entertainment', name: 'Entertainment', color: 'pink' },
  { key: 'science_tech', name: 'Sci/Tech', color: 'blue' },
  { key: 'weather', name: 'Weather', color: 'cyan' },
  { key: 'other', name: 'Other', color: 'gray' },
]

const COLOR_MAP = {
  mint:    { active: 'bg-mint-500/15 text-mint-300 border-mint-500/30', dot: 'bg-mint-400' },
  purple:  { active: 'bg-purple-500/15 text-purple-300 border-purple-500/30', dot: 'bg-purple-400' },
  emerald: { active: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
  amber:   { active: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' },
  pink:    { active: 'bg-pink-500/15 text-pink-300 border-pink-500/30', dot: 'bg-pink-400' },
  blue:    { active: 'bg-blue-500/15 text-blue-300 border-blue-500/30', dot: 'bg-blue-400' },
  cyan:    { active: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30', dot: 'bg-cyan-400' },
  gray:    { active: 'bg-gray-500/15 text-gray-300 border-gray-500/30', dot: 'bg-gray-400' },
}

export default function CategoryFilter({ activeCategory, onSelectCategory }) {
  return (
    <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-0.5 -mb-0.5">
      {CATEGORIES.map((cat) => {
        const isActive = cat.key === activeCategory
        const colors = COLOR_MAP[cat.color]
        return (
          <button
            key={cat.key ?? 'all'}
            onClick={() => onSelectCategory(cat.key)}
            className={`flex items-center gap-1.5 px-3 py-1 text-[11px] font-medium rounded-lg border transition-all duration-150 whitespace-nowrap ${
              isActive
                ? colors.active
                : 'text-gray-500 border-transparent hover:text-gray-300 hover:bg-white/[0.02]'
            }`}
          >
            {isActive && <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />}
            {cat.name}
          </button>
        )
      })}
      <style>{`.no-scrollbar::-webkit-scrollbar { display: none; } .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }`}</style>
    </div>
  )
}
