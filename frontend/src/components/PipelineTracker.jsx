import { useEffect, useRef, useState } from 'react'

const STEPS = ['Received', 'Saved', 'Bedrock', 'Matched', 'Replied']

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// A damped spring pulls the marker toward the current step, so it overshoots
// slightly and settles instead of sliding at constant speed.
function useSpring(target, { stiffness = 170, damping = 16 } = {}) {
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
  const percent = (position / (STEPS.length - 1)) * 100

  return (
    <div className={`pipeline-track${failed ? ' is-failed' : ''}`} role="list" aria-label="Processing steps">
      <div className="pipeline-rail" aria-hidden="true">
        <div className="pipeline-fill" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
        <div className={`pipeline-marker${busy ? ' is-busy' : ''}`} style={{ left: `${percent}%` }} />
      </div>
      <div className="pipeline-labels">
        {STEPS.map((label, i) => (
          <span
            key={label}
            role="listitem"
            aria-current={i === step ? 'step' : undefined}
            className={i < step ? 'done' : i === step ? (failed ? 'failed' : 'current') : ''}
          >
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}
