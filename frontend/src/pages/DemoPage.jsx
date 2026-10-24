import { useEffect, useRef, useState } from 'react'
import { useData } from '../hooks/DataContext.jsx'
import SmsThread from '../components/SmsThread.jsx'
import PipelineTracker from '../components/PipelineTracker.jsx'
import { needLabel } from '../components/format.js'

// Demo senders use 555 test numbers.
const SENDERS = [
  { value: '+14085550175', label: 'Resident' },
  { value: '+14085550142', label: 'Maria' },
  { value: '+14085550136', label: 'Español' },
]

const PRESETS = [
  { label: 'Water', text: 'Hi, 3 of us near McLaughlin. We need water.' },
  { label: 'Medical', text: 'My dad uses an oxygen concentrator and the power is out. We are near Tully Rd.' },
  { label: 'Spanish', text: 'Necesitamos comida para mi familia, somos cuatro personas cerca de Story y King.' },
  { label: 'Unclear', text: 'please help us' },
]

const TAG = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-[13px] font-medium'
const URGENCY_TONE = { Normal: 'bg-panel text-text', Urgent: 'bg-warn-soft text-warn', Medical: 'bg-danger-soft text-danger' }

function Understood({ request, onRetry, retrying }) {
  if (!request) return <p className="text-muted">Send a message to see what Waypoint understood.</p>

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
  if (!request.extraction) return <p className="text-muted">Reading the message…</p>

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
  const { requests, run } = useData()
  const [sender, setSender] = useState(SENDERS[0].value)
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
  const senderIndex = SENDERS.findIndex((s) => s.value === sender)

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
      <main className="mx-auto flex max-w-[960px] flex-col gap-8 px-4 py-10 sm:px-6 sm:py-12">
        <div className="animate-in text-center">
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Text for help.</h1>
          <p className="mx-auto mt-3 max-w-md text-[17px] text-muted">Send a message. Waypoint reads it and replies with the nearest verified resource.</p>
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
                style={{ transform: `translateX(${senderIndex * 100}%)` }}
              />
              {SENDERS.map((s) => (
                <button
                  key={s.value}
                  role="tab"
                  aria-selected={sender === s.value}
                  onClick={() => setSender(s.value)}
                  className={`relative z-10 truncate px-2 py-1.5 transition-colors duration-200 ${sender === s.value ? 'text-text' : 'text-muted hover:text-text'}`}
                >
                  {s.label}
                </button>
              ))}
            </div>

            <div className="flex h-[520px] flex-col overflow-hidden rounded-[36px] border border-line bg-raised shadow-[0_24px_60px_-24px_rgb(11_31_58/0.28)]">
              <div className="border-b border-line/70 py-3 text-center text-[13px] font-semibold">Waypoint</div>
              <div ref={threadRef} className="flex-1 overflow-y-auto p-3">
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
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => send(p.text)}
                  disabled={sending}
                  className="rounded-full border border-line px-3.5 py-1.5 text-[13px] font-medium transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </section>

          <section aria-live="polite" className="flex flex-col gap-6 rounded-3xl border border-line bg-raised p-6 sm:p-8">
            <h2 className="text-xl font-semibold tracking-tight">What Waypoint understood</h2>
            <div key={`${active?.id}-${active?.status}-${active?.processing_error}`} className="animate-in">
              <Understood request={active} onRetry={retry} retrying={retrying} />
            </div>
            <label className="mt-auto flex cursor-pointer items-center justify-between gap-4 border-t border-line pt-5 text-sm text-muted">
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
