import React, { useState } from 'react'

export default function LoginPage({ onAuth }) {
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await onAuth(isSignUp ? 'register' : 'login', email, password)
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Branding */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-100 tracking-tight">
            Arbitrage<span className="text-green-400">IQ</span>
          </h1>
          <p className="text-gray-500 mt-2">
            Cross-platform arbitrage & market intelligence
          </p>
        </div>

        {/* Form card */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-8 shadow-xl">
          <h2 className="text-xl font-semibold text-gray-100 mb-6">
            {isSignUp ? 'Create your account' : 'Welcome back'}
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-green-500/40 focus:border-green-500/60 transition-all placeholder:text-gray-600"
                placeholder="you@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-green-500/40 focus:border-green-500/60 transition-all placeholder:text-gray-600"
                placeholder={isSignUp ? 'Create a password (6+ chars)' : 'Enter your password'}
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-sm text-red-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 hover:bg-green-500 disabled:bg-green-800 disabled:cursor-wait text-white font-semibold py-3 rounded-lg transition-colors"
            >
              {loading ? 'Please wait...' : isSignUp ? 'Create Account' : 'Log In'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => { setIsSignUp(!isSignUp); setError('') }}
              className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              {isSignUp
                ? 'Already have an account? Log in'
                : "Don't have an account? Sign up"}
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-gray-600 text-xs mt-6">
          By signing up, you agree to our Terms of Service
        </p>
      </div>
    </div>
  )
}
