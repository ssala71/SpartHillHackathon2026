import { useEffect, useRef, useState } from 'react'

const STEPS = ['Received', 'Saved', 'Bedrock', 'Matched', 'Replied']

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// A critically damped spring eases the marker into each step without overshoot.
function useSpring(target, { stiffness = 120, damping = 22 } = {}) {
  const [value, setValue] = useState(target)
  const state = useRef({ x: target, v: 0 })

  useEffect(() => {
    let frame
    if (reducedMotion()) {
      state.current = { x: target, v: 0 }
      frame = requestAnimationFrame(() => setValue(target))
      return () => cancelAnimationFrame(frame)
    }
    let last = performance.now()
    const tick = (now) => {
      const dt = Math.min((now - last) / 1000, 1 / 30)
      last = now
      const s = state.current
      const force = -stiffness * (s.x - target) - damping * s.v
      s.v += force * dt
      s.x += s.v * dt
      setValue(s.x)
      if (Math.abs(s.x - target) > 0.001 || Math.abs(s.v) > 0.001) frame = requestAnimationFrame(tick)
      else setValue(target)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, stiffness, damping])

  return value
}

export default function PipelineTracker({ step, failed = false, busy = false }) {
  const position = useSpring(step)
  const percent = Math.max(0, Math.min(100, (position / (STEPS.length - 1)) * 100))
  const tone = failed ? 'bg-danger' : 'bg-accent'

  return (
    <div role="list" aria-label="Processing steps">
      {/* The rail runs between the first and last label centers. */}
      <div className="relative mx-[10%] mb-3 h-1 rounded-full bg-line" aria-hidden="true">
        <div className={`absolute inset-y-0 left-0 rounded-full transition-colors duration-200 ${tone}`} style={{ width: `${percent}%` }} />
        {step >= 0 && (
          <div
            className={`absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-4 ring-bg transition-colors duration-200 ${tone}`}
            style={{ left: `${percent}%` }}
          >
            {busy && <span className={`absolute inset-0 animate-ping rounded-full opacity-40 ${tone}`} />}
          </div>
        )}
      </div>
      <div className="flex text-[13px]">
        {STEPS.map((label, i) => (
          <span
            key={label}
            role="listitem"
            aria-current={i === step ? 'step' : undefined}
            className={`flex-1 text-center transition-colors duration-300 ${
              i === step && failed ? 'font-semibold text-danger' : i <= step ? 'font-medium text-text' : 'text-muted'
            }`}
          >
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}
