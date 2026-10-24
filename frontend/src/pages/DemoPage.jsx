import { useEffect, useRef, useState } from 'react'
import { useData } from '../hooks/DataContext.jsx'
import SmsThread from '../components/SmsThread.jsx'
import PipelineTracker from '../components/PipelineTracker.jsx'
import { needLabel } from '../components/format.js'

// The people Waypoint is built for. Each texts from a 555 test number.
const PERSONAS = [
  {
    phone: '+14085550142',
    name: 'Maria',
    situation: 'Caring for her grandmother, who relies on an oxygen concentrator. The power has been out for hours.',
    samples: [
      { label: 'Oxygen', text: "My grandma's oxygen machine has no power. We are near Tully Rd, 2 of us." },
      { label: 'Water', text: 'We also need water, 2 people near Tully Rd.' },
    ],
  },
  {
    phone: '+14085550136',
    name: 'Luis',
    situation: 'Speaks Spanish. His family of four is running out of food.',
    samples: [
      { label: 'Comida', text: 'Necesitamos comida para mi familia, somos cuatro personas cerca de Story y King.' },
      { label: 'Agua', text: 'Necesitamos agua, somos cuatro cerca de Story y King.' },
    ],
  },
  {
    phone: '+14085550175',
    name: 'Sam',
    situation: 'A student living alone. Phone at 10% and not sure what to ask for.',
    samples: [
      { label: 'First text', text: 'please help' },
      { label: 'Answer the follow-up', text: 'water and a place to charge my phone, near McLaughlin, 1 person' },
    ],
  },
]

const TAG = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-[13px] font-medium'
const URGENCY_TONE = { Normal: 'bg-panel text-text', Urgent: 'bg-warn-soft text-warn', Medical: 'bg-danger-soft text-danger' }

function Understood({ request, onRetry, retrying }) {
  if (!request) return <p className="m-auto max-w-[240px] text-center text-muted">Send a message to see what Waypoint understood.</p>

  if (request.processing_error) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-2xl bg-danger-soft p-4">
        <div>
          <p className="font-semibold text-danger">Bedrock timed out</p>
          <p className="text-sm text-muted">The message was saved first, so nothing is lost.</p>
        </div>
        <button
          onClick={onRetry}
          disabled={retrying}
          className="rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {retrying ? 'Retrying…' : 'Retry'}
        </button>
      </div>
    )
  }
  if (!request.extraction) return <p className="m-auto text-center text-muted">Reading the message…</p>

  const match = request.suggested_match
  const rows = [
    [
      'Needs',
      request.needs?.length ? (
        <span key="needs" className="flex flex-wrap gap-1.5">
          {request.needs.map((n) => (
            <span key={n} className={`${TAG} bg-accent-soft text-accent`}>
              {needLabel(n)}
            </span>
          ))}
        </span>
      ) : (
        'Unclear'
      ),
    ],
    ['Location', request.location_description ?? 'Missing'],
    ['People', request.people_count ?? '—'],
    ['Urgency', <span key="urgency" className={`${TAG} ${URGENCY_TONE[request.urgency]}`}>{request.urgency}</span>],
    ['Language', request.extraction.language === 'es' ? 'Spanish' : 'English'],
  ]
  const matched = match?.resource_id && request.urgency === 'Normal'

  return (
    <div className="flex flex-col gap-5">
      <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-3 text-[15px]">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="min-w-0 break-words">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="rounded-2xl bg-panel p-4">
        <p className="text-xs font-medium tracking-wide text-muted uppercase">Result</p>
        <p className="mt-1">
          {matched ? (
            <>
              <span className="font-semibold">{match.resource_name}</span>, {match.distance_km} km away
            </>
          ) : (
            <span className="font-semibold">{match?.next_action === 'Ask follow-up question' ? 'Asked a follow-up' : 'Sent to a coordinator'}</span>
          )}
        </p>
      </div>
    </div>
  )
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  )
}

export default function DemoPage() {
  const { requests, incidents, resources, run } = useData()
  const [sender, setSender] = useState(PERSONAS[0].phone)
  const [text, setText] = useState('')
  const [failNext, setFailNext] = useState(false)
  const [sending, setSending] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [activeId, setActiveId] = useState(null)
  const [liveStep, setLiveStep] = useState(null)
  const threadRef = useRef(null)

  const mine = requests.filter((r) => r.source_phone === sender)
  const messages = mine.flatMap((r) => r.messages ?? []).sort((a, b) => a.at.localeCompare(b.at))
  const active = requests.find((r) => r.id === activeId && r.source_phone === sender) ?? mine[0]
  const settledStep = !active ? -1 : active.processing_error ? 2 : active.status === 'Received' ? 1 : 4
  const step = liveStep ?? settledStep
  const personaIndex = PERSONAS.findIndex((p) => p.phone === sender)
  const persona = PERSONAS[personaIndex]
  const incident = incidents.find((i) => i.status === 'Active')
  const openCount = resources.filter((r) => r.status === 'Active').length

  useEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages.length, sender])

  const send = async (body) => {
    body = body.trim()
    if (!body || sending) return
    setSending(true)
    setText('')
    setLiveStep(0)
    const received = await run((api) => api.receiveSms(sender, body))
    if (received && !received.reply) {
      setActiveId(received.id)
      setLiveStep(2)
      await run((api) => api.processRequest(received.id, { simulateFailure: failNext }))
      setFailNext(false)
    }
    setLiveStep(null)
    setSending(false)
  }

  const retry = async () => {
    setRetrying(true)
    setLiveStep(2)
    await run((api) => api.processRequest(active.id))
    setLiveStep(null)
    setRetrying(false)
  }

  return (
    <div className="wp min-h-[calc(100dvh-57px)] bg-bg text-[15px] text-text">
      <main className="mx-auto flex max-w-[960px] flex-col gap-8 px-4 py-6 sm:px-6 sm:py-8">
        <div className="flex flex-col gap-3">
          {incident && (
            <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-2xl bg-[linear-gradient(135deg,#0b1f3a_0%,#1f3b73_100%)] px-4 py-2.5 text-[13px] text-white/80">
              <span className="inline-flex items-center gap-2 font-semibold text-white">
                <span className="size-1.5 animate-pulse rounded-full bg-[#ffb547]" />
                {incident.name}
              </span>
              <span aria-hidden="true" className="hidden sm:inline">·</span>
              <span>{incident.affected_area}</span>
              <span aria-hidden="true" className="hidden sm:inline">·</span>
              <span>{openCount} locations open</span>
              <span aria-hidden="true" className="hidden sm:inline">·</span>
              <span>
                Emergency? <span className="font-semibold text-white">Call 911</span>
              </span>
            </div>
          )}
          <p className="text-center text-muted">Pick a person, then send one of their texts or write your own. Waypoint replies with the nearest verified resource.</p>
        </div>

        <div className="mx-auto w-full max-w-[640px]">
          <PipelineTracker step={step} failed={liveStep === null && Boolean(active?.processing_error)} busy={liveStep !== null} />
        </div>

        <div className="grid items-start gap-8 md:grid-cols-[340px_1fr]">
          <section className="mx-auto flex w-full max-w-[340px] flex-col gap-4">
            <div role="tablist" aria-label="Texting as" className="relative grid grid-cols-3 rounded-full bg-panel p-0.5 text-[13px] font-medium">
              <span
                aria-hidden="true"
                className="absolute inset-y-0.5 left-0.5 w-[calc((100%-4px)/3)] rounded-full bg-raised shadow-sm ring-1 ring-line/60 transition-transform duration-300 ease-apple"
                style={{ transform: `translateX(${personaIndex * 100}%)` }}
              />
              {PERSONAS.map((p) => (
                <button
                  key={p.phone}
                  role="tab"
                  aria-selected={sender === p.phone}
                  onClick={() => setSender(p.phone)}
                  className={`relative z-10 truncate px-2 py-1.5 transition-colors duration-200 ${sender === p.phone ? 'text-text' : 'text-muted hover:text-text'}`}
                >
                  {p.name}
                </button>
              ))}
            </div>
            <p key={persona.phone} className="min-h-[3lh] animate-in text-center text-[13px] leading-snug text-muted">
              {persona.situation}
            </p>

            <div className="flex h-[520px] flex-col overflow-hidden rounded-[36px] border border-line bg-raised shadow-[0_24px_60px_-24px_rgb(11_31_58/0.28)]">
              <div className="border-b border-line/70 py-3 text-center text-[13px] font-semibold">Waypoint</div>
              <div ref={threadRef} className="flex flex-1 flex-col overflow-y-auto p-3">
                <SmsThread messages={messages} emptyText="No messages yet." />
              </div>
              <form
                className="flex items-center gap-2 border-t border-line/70 p-2.5"
                onSubmit={(e) => {
                  e.preventDefault()
                  send(text)
                }}
              >
                <input
                  id="demo-message"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Text message"
                  aria-label="Text message"
                  autoComplete="off"
                  className="h-9 min-w-0 flex-1 rounded-full border border-line bg-bg px-4 text-[15px] outline-none placeholder:text-muted focus:border-accent"
                />
                <button
                  disabled={!text.trim() || sending}
                  aria-label="Send"
                  className="grid size-9 shrink-0 place-items-center rounded-full bg-accent text-accent-fg transition-[opacity,transform] duration-200 enabled:active:scale-95 disabled:opacity-30"
                >
                  <SendIcon />
                </button>
              </form>
            </div>

            <div className="flex flex-wrap justify-center gap-2">
              {persona.samples.map((p) => (
                <button
                  key={p.label}
                  onClick={() => send(p.text)}
                  disabled={sending}
                  title={p.text}
                  className="rounded-full border border-line px-3.5 py-1.5 text-[13px] font-medium transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </section>

          <section aria-live="polite" className="flex flex-col gap-6 self-stretch rounded-3xl border border-line bg-raised p-6 sm:p-8">
            <h2 className="text-xl font-semibold tracking-tight">What Waypoint understood</h2>
            <div key={`${active?.id}-${active?.status}-${active?.processing_error}`} className="flex flex-1 flex-col animate-in">
              <Understood request={active} onRetry={retry} retrying={retrying} />
            </div>
            <label className="flex cursor-pointer items-center justify-between gap-4 border-t border-line pt-5 text-sm text-muted">
              Simulate a Bedrock failure
              <input id="demo-fail" type="checkbox" role="switch" checked={failNext} onChange={(e) => setFailNext(e.target.checked)} className="peer sr-only" />
              <span
                aria-hidden="true"
                className="relative h-6 w-10 shrink-0 rounded-full bg-line transition-colors duration-200 peer-checked:bg-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent after:absolute after:top-0.5 after:left-0.5 after:size-5 after:rounded-full after:bg-white after:shadow after:transition-transform after:duration-200 peer-checked:after:translate-x-4"
              />
            </label>
          </section>
        </div>
      </main>
    </div>
  )
}
