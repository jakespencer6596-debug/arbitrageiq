import React, { useEffect, useRef } from 'react'

export default function ThreeHeroBackground({ className }) {
  const containerRef = useRef(null)
  const frameRef = useRef(null)
  const mouseRef = useRef({ x: 0, y: 0 })

  useEffect(() => {
    // Poll for THREE.js to load (CDN defer script may not be ready yet)
    let attempts = 0
    const waitForThree = setInterval(() => {
      attempts++
      if (window.THREE) {
        clearInterval(waitForThree)
        init()
      } else if (attempts > 50) {
        clearInterval(waitForThree)
      }
    }, 100)

    let cleanup = null

    function init() {
      const THREE = window.THREE
      const container = containerRef.current
      if (!THREE || !container) return
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

      const isMobile = window.innerWidth < 768
      const PARTICLE_COUNT = isMobile ? 400 : 800
      const MAX_LINES = isMobile ? 800 : 2000
      const CONNECT_DIST = 2.5

      // Use parent dimensions for sizing
      const w = container.offsetWidth || window.innerWidth
      const h = container.offsetHeight || window.innerHeight

      // Create canvas
      const canvas = document.createElement('canvas')
      canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;'
      container.appendChild(canvas)

      // Renderer
      const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
      renderer.setSize(w, h)

      // Scene + Camera
      const scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 100)
      camera.position.z = 8

      // Particles
      const positions = new Float32Array(PARTICLE_COUNT * 3)
      const originalPositions = new Float32Array(PARTICLE_COUNT * 3)
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const i3 = i * 3
        positions[i3] = (Math.random() - 0.5) * 20
        positions[i3 + 1] = (Math.random() - 0.5) * 12
        positions[i3 + 2] = (Math.random() - 0.5) * 8
        originalPositions[i3] = positions[i3]
        originalPositions[i3 + 1] = positions[i3 + 1]
        originalPositions[i3 + 2] = positions[i3 + 2]
      }

      const particleGeometry = new THREE.BufferGeometry()
      particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))

      const particleMaterial = new THREE.PointsMaterial({
        color: 0x10b981,
        size: isMobile ? 0.06 : 0.04,
        transparent: true,
        opacity: 0.6,
        sizeAttenuation: true,
      })

      const points = new THREE.Points(particleGeometry, particleMaterial)
      scene.add(points)

      // Connecting lines
      const linePositions = new Float32Array(MAX_LINES * 6)
      const lineGeometry = new THREE.BufferGeometry()
      lineGeometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3))
      lineGeometry.setDrawRange(0, 0)

      const lineMaterial = new THREE.LineBasicMaterial({
        color: 0x10b981,
        transparent: true,
        opacity: 0.06,
      })

      const lines = new THREE.LineSegments(lineGeometry, lineMaterial)
      scene.add(lines)

      // Animation loop
      const startTime = performance.now()

      function animate() {
        frameRef.current = requestAnimationFrame(animate)

        const elapsed = (performance.now() - startTime) * 0.001
        const posAttr = particleGeometry.getAttribute('position')
        const posArray = posAttr.array

        for (let i = 0; i < PARTICLE_COUNT; i++) {
          const i3 = i * 3
          const ox = originalPositions[i3]
          const oy = originalPositions[i3 + 1]
          const oz = originalPositions[i3 + 2]
          posArray[i3] = ox + Math.sin(elapsed * 0.3 + ox * 0.5) * 0.3
          posArray[i3 + 1] = oy + Math.cos(elapsed * 0.25 + oy * 0.4) * 0.25
          posArray[i3 + 2] = oz + Math.sin(elapsed * 0.2 + oz * 0.3) * 0.2
        }
        posAttr.needsUpdate = true

        // Update connecting lines
        let lineIndex = 0
        const lineArr = lineGeometry.getAttribute('position').array
        for (let i = 0; i < PARTICLE_COUNT && lineIndex < MAX_LINES; i++) {
          const i3 = i * 3
          const ax = posArray[i3], ay = posArray[i3 + 1], az = posArray[i3 + 2]
          for (let j = i + 1; j < PARTICLE_COUNT && lineIndex < MAX_LINES; j++) {
            const j3 = j * 3
            const dx = posArray[j3] - ax
            const dy = posArray[j3 + 1] - ay
            const dz = posArray[j3 + 2] - az
            const dist = dx * dx + dy * dy + dz * dz
            if (dist < CONNECT_DIST * CONNECT_DIST) {
              const li = lineIndex * 6
              lineArr[li] = ax; lineArr[li + 1] = ay; lineArr[li + 2] = az
              lineArr[li + 3] = posArray[j3]; lineArr[li + 4] = posArray[j3 + 1]; lineArr[li + 5] = posArray[j3 + 2]
              lineIndex++
            }
          }
        }
        lineGeometry.setDrawRange(0, lineIndex * 2)
        lineGeometry.getAttribute('position').needsUpdate = true

        // Mouse parallax on camera
        camera.position.x += (mouseRef.current.x * 0.8 - camera.position.x) * 0.02
        camera.position.y += (mouseRef.current.y * 0.5 - camera.position.y) * 0.02

        renderer.render(scene, camera)
      }
      animate()

      // Resize
      function onResize() {
        const nw = container.offsetWidth || window.innerWidth
        const nh = container.offsetHeight || window.innerHeight
        camera.aspect = nw / nh
        camera.updateProjectionMatrix()
        renderer.setSize(nw, nh)
      }
      window.addEventListener('resize', onResize)

      // Mouse tracking
      function onMouseMove(e) {
        mouseRef.current.x = (e.clientX / window.innerWidth - 0.5) * 2
        mouseRef.current.y = -(e.clientY / window.innerHeight - 0.5) * 2
      }
      document.addEventListener('mousemove', onMouseMove, { passive: true })

      cleanup = () => {
        if (frameRef.current) cancelAnimationFrame(frameRef.current)
        window.removeEventListener('resize', onResize)
        document.removeEventListener('mousemove', onMouseMove)
        particleGeometry.dispose()
        particleMaterial.dispose()
        lineGeometry.dispose()
        lineMaterial.dispose()
        renderer.dispose()
        if (canvas.parentNode) canvas.parentNode.removeChild(canvas)
      }
    }

    return () => {
      clearInterval(waitForThree)
      if (cleanup) cleanup()
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className={className || ''}
      style={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none', overflow: 'hidden' }}
    />
  )
}
