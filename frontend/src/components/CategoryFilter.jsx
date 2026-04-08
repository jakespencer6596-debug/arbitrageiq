import React from 'react'

const CATEGORIES = [
  { key: null, name: 'All', color: 'green' },
  { key: 'politics', name: 'Politics', color: 'purple' },
  { key: 'sports', name: 'Sports', color: 'green' },
  { key: 'crypto', name: 'Crypto', color: 'orange' },
  { key: 'entertainment', name: 'Entertainment', color: 'pink' },
  { key: 'science_tech', name: 'Sci/Tech', color: 'blue' },
  { key: 'weather', name: 'Weather', color: 'cyan' },
  { key: 'other', name: 'Other', color: 'gray' },
]

const COLOR_MAP = {
  purple: { active: 'bg-purple-500/20 text-purple-300 border-purple-500/50', inactive: 'text-gray-500 border-gray-700 hover:border-purple-500/30 hover:text-purple-400' },
  green: { active: 'bg-green-500/20 text-green-300 border-green-500/50', inactive: 'text-gray-500 border-gray-700 hover:border-green-500/30 hover:text-green-400' },
  orange: { active: 'bg-orange-500/20 text-orange-300 border-orange-500/50', inactive: 'text-gray-500 border-gray-700 hover:border-orange-500/30 hover:text-orange-400' },
  pink: { active: 'bg-pink-500/20 text-pink-300 border-pink-500/50', inactive: 'text-gray-500 border-gray-700 hover:border-pink-500/30 hover:text-pink-400' },
  blue: { active: 'bg-blue-500/20 text-blue-300 border-blue-500/50', inactive: 'text-gray-500 border-gray-700 hover:border-blue-500/30 hover:text-blue-400' },
  cyan: { active: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50', inactive: 'text-gray-500 border-gray-700 hover:border-cyan-500/30 hover:text-cyan-400' },
  gray: { active: 'bg-gray-500/20 text-gray-300 border-gray-500/50', inactive: 'text-gray-500 border-gray-700 hover:border-gray-500/30 hover:text-gray-400' },
}

export default function CategoryFilter({ activeCategory, onSelectCategory }) {
  return (
    <div className="flex flex-wrap gap-2">
      {CATEGORIES.map((cat) => {
        const isActive = cat.key === activeCategory
        const colors = COLOR_MAP[cat.color]
        return (
          <button
            key={cat.key ?? 'all'}
            onClick={() => onSelectCategory(cat.key)}
            className={`px-3 py-1 text-xs font-medium rounded-full border transition-all duration-150 ${
              isActive ? colors.active : colors.inactive
            }`}
          >
            {cat.name}
          </button>
        )
      })}
    </div>
  )
}
