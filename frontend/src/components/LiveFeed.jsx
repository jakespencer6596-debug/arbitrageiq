import React, { useEffect, useRef } from 'react'

const EVENT_ICONS = {
  arb: <svg className="w-3.5 h-3.5 text-mint-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>,
  arb_expired: <svg className="w-3.5 h-3.5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" /></svg>,
  discrepancy: <svg className="w-3.5 h-3.5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>,
  system: <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
  info: <svg className="w-3.5 h-3.5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
}

function formatTime(isoStr) {
  if (!isoStr) return ''
  try { return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return '' }
}

export default function LiveFeed({ events, onClose }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [events.length])

  return (
    <div className="fixed bottom-16 md:bottom-20 right-4 md:right-6 z-50 w-80 md:w-96 max-w-[calc(100vw-2rem)] animate-slide-in-right">
      <div className="glass rounded-2xl border border-white/[0.06] shadow-2xl shadow-black/50 overflow-hidden flex flex-col max-h-[420px]">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.04]">
          <div className="flex items-center gap-2">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-mint-400 opacity-50" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-mint-500" />
            </span>
            <h3 className="text-xs font-semibold text-gray-200">Live Feed</h3>
            <span className="text-[10px] text-gray-600 font-mono">{events.length}</span>
          </div>
          <button onClick={onClose} className="p-1 rounded-md text-gray-600 hover:text-gray-300 hover:bg-white/[0.04] transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-2.5 space-y-1">
          {events.length === 0 ? (
            <div className="py-8 text-center"><p className="text-gray-700 text-xs">Waiting for events...</p></div>
          ) : events.map((evt) => (
            <div key={evt.id} className="flex items-start gap-2 px-2 py-1.5 rounded-lg hover:bg-white/[0.02] transition-colors animate-fade-in">
              <div className="shrink-0 mt-0.5">{EVENT_ICONS[evt.type] || EVENT_ICONS.info}</div>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] text-gray-300 leading-snug break-words">{evt.message || 'Event received'}</p>
                <p className="text-[9px] text-gray-700 mt-0.5 font-mono">{formatTime(evt.timestamp)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
