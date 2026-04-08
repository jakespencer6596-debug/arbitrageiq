import React, { useEffect, useRef, useState } from 'react'

/**
 * Smooth animated number counter — premium feel for hero stats.
 * Uses requestAnimationFrame with easeOutExpo for natural deceleration.
 */
export default function AnimatedCounter({
  value,
  duration = 1200,
  prefix = '',
  suffix = '',
  decimals = 0,
  className = '',
}) {
  const [display, setDisplay] = useState(0)
  const prevValue = useRef(0)
  const frameRef = useRef(null)

  useEffect(() => {
    const from = prevValue.current
    const to = typeof value === 'number' ? value : parseFloat(value) || 0
    const startTime = performance.now()

    function easeOutExpo(t) {
      return t === 1 ? 1 : 1 - Math.pow(2, -10 * t)
    }

    function animate(now) {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = easeOutExpo(progress)
      const current = from + (to - from) * eased

      setDisplay(current)

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate)
      } else {
        prevValue.current = to
      }
    }

    frameRef.current = requestAnimationFrame(animate)
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
  }, [value, duration])

  const formatted = decimals > 0
    ? display.toFixed(decimals)
    : Math.round(display).toLocaleString()

  return (
    <span className={`tabular-nums ${className}`}>
      {prefix}{formatted}{suffix}
    </span>
  )
}
