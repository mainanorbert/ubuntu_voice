"use client"

import { useEffect, useRef } from "react"
import * as THREE from "three"

/** Renders a subtle, non-interactive Three.js particle field for the emergency welcome state. */
export function EmergencyBackground() {
  const container_ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = container_ref.current
    if (!container || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100)
    camera.position.z = 6

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setClearColor(0x000000, 0)
    container.appendChild(renderer.domElement)

    const particle_count = 90
    const positions = new Float32Array(particle_count * 3)
    const colors = new Float32Array(particle_count * 3)
    const palette = [new THREE.Color("#2563EB"), new THREE.Color("#60A5FA"), new THREE.Color("#1E3A8A")]
    for (let index = 0; index < particle_count; index += 1) {
      const offset = index * 3
      positions[offset] = (Math.random() - 0.5) * 11
      positions[offset + 1] = (Math.random() - 0.5) * 7
      positions[offset + 2] = (Math.random() - 0.5) * 2
      const color = palette[index % palette.length]!
      colors[offset] = color.r
      colors[offset + 1] = color.g
      colors[offset + 2] = color.b
    }

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3))
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3))
    const material = new THREE.PointsMaterial({ size: 0.055, transparent: true, opacity: 0.42, vertexColors: true, sizeAttenuation: true })
    const particles = new THREE.Points(geometry, material)
    scene.add(particles)

    const resize = () => {
      const { width, height } = container.getBoundingClientRect()
      camera.aspect = width / Math.max(height, 1)
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
    }
    const resize_observer = new ResizeObserver(resize)
    resize_observer.observe(container)
    resize()

    let frame_id = 0
    const animate = () => {
      particles.rotation.y += 0.0007
      particles.rotation.x = Math.sin(Date.now() * 0.00018) * 0.12
      renderer.render(scene, camera)
      frame_id = requestAnimationFrame(animate)
    }
    animate()

    return () => {
      cancelAnimationFrame(frame_id)
      resize_observer.disconnect()
      geometry.dispose()
      material.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  return <div ref={container_ref} className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden />
}
