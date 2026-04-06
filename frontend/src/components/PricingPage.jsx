import React from 'react'

const PLANS = [
  {
    key: 'daily',
    name: 'Day Pass',
    price: '$9.99',
    interval: '/day',
    description: 'Perfect for trying out the platform',
    features: [
      'All arbitrage opportunities',
      'Discrepancy signals',
      'Stake calculator',
      'Execution plans',
    ],
    cta: 'Get Day Pass',
  },
  {
    key: 'weekly',
    name: 'Weekly',
    price: '$49.99',
    interval: '/week',
    description: 'Most popular for active traders',
    popular: true,
    features: [
      'All arbitrage opportunities',
      'Discrepancy signals',
      'Stake calculator',
      'Execution plans',
      'Priority data refresh',
    ],
    cta: 'Start Weekly',
  },
  {
    key: 'monthly',
    name: 'Monthly',
    price: '$98.99',
    interval: '/month',
    description: 'Best value for serious traders',
    features: [
      'All arbitrage opportunities',
      'Discrepancy signals',
      'Stake calculator',
      'Execution plans',
      'Priority data refresh',
      'Save 34% vs weekly',
    ],
    cta: 'Start Monthly',
  },
]

export default function PricingPage({ onSelectPlan, onClose }) {
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-gray-950 rounded-2xl border border-gray-800 max-w-4xl w-full max-h-[90vh] overflow-y-auto p-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-gray-100">
              Unlock Arbitrage<span className="text-green-400">IQ</span> Premium
            </h2>
            <p className="text-gray-500 mt-1">
              Get full access to all arbitrage opportunities and market intelligence signals
            </p>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Plans grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PLANS.map((plan) => (
            <div
              key={plan.key}
              className={`relative rounded-xl border p-6 flex flex-col ${
                plan.popular
                  ? 'border-green-500/50 bg-green-500/5 shadow-lg shadow-green-500/10'
                  : 'border-gray-800 bg-gray-900/50'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-green-500 text-white text-xs font-bold px-3 py-1 rounded-full">
                    MOST POPULAR
                  </span>
                </div>
              )}

              <div className="mb-4">
                <h3 className="text-lg font-semibold text-gray-100">{plan.name}</h3>
                <p className="text-sm text-gray-500 mt-1">{plan.description}</p>
              </div>

              <div className="mb-6">
                <span className="text-3xl font-bold text-gray-100">{plan.price}</span>
                <span className="text-gray-500 text-sm">{plan.interval}</span>
              </div>

              <ul className="space-y-2.5 mb-6 flex-1">
                {plan.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-400">
                    <svg className="w-4 h-4 text-green-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>

              <button
                onClick={() => onSelectPlan(plan.key)}
                className={`w-full py-3 rounded-lg font-semibold transition-colors ${
                  plan.popular
                    ? 'bg-green-600 hover:bg-green-500 text-white'
                    : 'bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700'
                }`}
              >
                {plan.cta}
              </button>
            </div>
          ))}
        </div>

        <p className="text-center text-gray-600 text-xs mt-6">
          Cancel anytime. Payments processed securely via Stripe.
        </p>
      </div>
    </div>
  )
}
