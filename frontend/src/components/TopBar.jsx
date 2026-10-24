import { useState } from 'react'
import { USING_MOCK } from '../api/client.js'
import logoUrl from '../assets/waypoint.svg'
import { getMode, setMode } from '../theme.js'

const VIEWS = [
  { key: 'demo', label: 'Demo', href: '#/' },
  { key: 'admin', label: 'Admin', href: '#/admin' },
]

function ModeIcon({ dark }) {
  return dark ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  )
}

// Shared by the demo and the admin, so switching views feels like one app.
export default function TopBar({ view, id }) {
  const [mode, setModeState] = useState(getMode)
  const dark = mode === 'dark'

  const toggleMode = () => {
    const next = dark ? 'light' : 'dark'
    setMode(next)
    setModeState(next)
  }

  return (
    <header
      id={id}
      className="wp sticky top-0 z-[1002] border-b border-line/70 bg-bg/80 text-text backdrop-blur-xl backdrop-saturate-150"
    >
      <div className="grid h-14 grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 sm:px-6">
        <a href="#/" className="flex items-center gap-2 justify-self-start text-[17px] font-semibold tracking-tight">
          <img src={logoUrl} alt="" width="24" height="24" />
          Waypoint
        </a>

        <nav aria-label="View" className="relative grid grid-cols-2 rounded-full bg-panel p-0.5 text-[13px] font-medium">
          <span
            aria-hidden="true"
            className="absolute inset-y-0.5 left-0.5 w-[calc(50%-2px)] rounded-full bg-raised shadow-sm ring-1 ring-line/60 transition-transform duration-300 ease-apple"
            style={{ transform: view === 'admin' ? 'translateX(100%)' : 'none' }}
          />
          {VIEWS.map((v) => (
            <a
              key={v.key}
              href={v.href}
              aria-current={view === v.key ? 'page' : undefined}
              className={`relative z-10 px-4 py-1.5 sm:px-5 text-center transition-colors duration-200 ${view === v.key ? 'text-text' : 'text-muted hover:text-text'}`}
            >
              {v.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2 justify-self-end">
          {view === 'admin' && (
            <span
              className="hidden items-center gap-1.5 text-xs text-muted sm:flex"
              title={USING_MOCK ? 'Simulated data. Set VITE_BACKEND_URL to add real SMS requests.' : 'Real SMS requests from the Waypoint backend, plus demo data'}
            >
              <span className={`size-1.5 rounded-full ${USING_MOCK ? 'bg-warn' : 'bg-ok'}`} />
              {USING_MOCK ? 'Demo data' : 'Live'}
            </span>
          )}
          <button
            type="button"
            onClick={toggleMode}
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="grid size-8 place-items-center rounded-full text-muted transition-colors hover:bg-panel hover:text-text"
          >
            <ModeIcon dark={dark} />
          </button>
        </div>
      </div>
    </header>
  )
}
