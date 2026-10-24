import { useEffect, useRef, useState } from 'react'
import Box from '@cloudscape-design/components/box'
import Button from '@cloudscape-design/components/button'
import Checkbox from '@cloudscape-design/components/checkbox'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import Container from '@cloudscape-design/components/container'
import ContentLayout from '@cloudscape-design/components/content-layout'
import Header from '@cloudscape-design/components/header'
import Input from '@cloudscape-design/components/input'
import Link from '@cloudscape-design/components/link'
import Select from '@cloudscape-design/components/select'
import SpaceBetween from '@cloudscape-design/components/space-between'
import { useData } from '../hooks/DataContext.jsx'
import SmsThread from '../components/SmsThread.jsx'
import { ExtractionPanel, ProcessingTimeline } from '../components/RequestInsights.jsx'
import { RequestStatus } from '../components/StatusBadges.jsx'
import { maskPhone } from '../components/format.js'

// Demo senders. All numbers are 555 test numbers.
const SENDERS = [
  { value: '+14085550142', label: 'Maria (+1 408-555-0142)' },
  { value: '+14085550175', label: 'New resident (+1 408-555-0175)' },
  { value: '+14085550136', label: 'Spanish speaker (+1 408-555-0136)' },
]

const PRESETS = [
  { label: 'Normal need', text: 'Hi, 3 of us near McLaughlin. We need water.' },
  { label: 'Medical device', text: 'My dad uses an oxygen concentrator and the power is out. We are near Tully Rd.' },
  { label: 'Spanish', text: 'Necesitamos comida para mi familia, somos cuatro personas cerca de Story y King.' },
  { label: 'Unclear', text: 'please help us' },
  { label: 'Opt out', text: 'STOP' },
]

export default function SimulatorPage() {
  const { requests, run } = useData()
  const [sender, setSender] = useState(SENDERS[1])
  const [text, setText] = useState(PRESETS[0].text)
  const [failNext, setFailNext] = useState(false)
  const [sending, setSending] = useState(false)
  const [systemNotes, setSystemNotes] = useState([])
  const [activeId, setActiveId] = useState(null)

  const mine = requests.filter((r) => r.source_phone === sender.value)
  const messages = [...mine.flatMap((r) => r.messages ?? []), ...systemNotes.filter((n) => n.phone === sender.value)].sort((a, b) =>
    a.at.localeCompare(b.at),
  )
  const active = requests.find((r) => r.id === activeId) ?? mine[0]
  const threadEnd = useRef(null)

  useEffect(() => {
    if (threadEnd.current) threadEnd.current.scrollTop = threadEnd.current.scrollHeight
  }, [messages.length])

  const send = async () => {
    if (!text.trim()) return
    setSending(true)
    const body = text.trim()
    setText('')
    const received = await run((api) => api.receiveSms(sender.value, body))
    if (received?.reply) {
      // Opt-out handled without creating a request.
      const at = new Date().toISOString()
      setSystemNotes((n) => [...n, { phone: sender.value, direction: 'in', body, at }, { phone: sender.value, direction: 'out', body: received.reply, at }])
    } else if (received) {
      setActiveId(received.id)
      await run((api) => api.processRequest(received.id, { simulateFailure: failNext }))
      setFailNext(false)
    }
    setSending(false)
  }

  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          description="Text the service the way a resident would. The message is saved, read by Bedrock, matched against verified resources, and answered, and it appears in the coordinator queue."
        >
          SMS simulator
        </Header>
      }
    >
      <ColumnLayout columns={2}>
        <SpaceBetween size="m">
          <div className="phone">
            <div className="phone-header">
              <strong>Waypoint</strong>
              Texting as {maskPhone(sender.value)}
            </div>
            <div className="phone-body" ref={threadEnd}>
              <SmsThread messages={messages} emptyText="Send a text to start." />
            </div>
            <div className="phone-input">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  send()
                }}
              >
                <SpaceBetween direction="horizontal" size="xs" alignItems="center">
                  <div style={{ width: 230 }}>
                    <Input value={text} onChange={({ detail }) => setText(detail.value)} placeholder="Text message" ariaLabel="Text message" />
                  </div>
                  <Button variant="primary" loading={sending} disabled={!text.trim()} formAction="submit">
                    Send
                  </Button>
                </SpaceBetween>
              </form>
            </div>
          </div>
        </SpaceBetween>

        <SpaceBetween size="m">
          <Container header={<Header variant="h3">Try it</Header>}>
            <SpaceBetween size="s">
              <Select selectedOption={sender} onChange={({ detail }) => setSender(detail.selectedOption)} options={SENDERS} ariaLabel="Sender" />
              <SpaceBetween direction="horizontal" size="xs">
                {PRESETS.map((p) => (
                  <Button key={p.label} onClick={() => setText(p.text)}>
                    {p.label}
                  </Button>
                ))}
              </SpaceBetween>
              <Checkbox checked={failNext} onChange={({ detail }) => setFailNext(detail.checked)}>
                Make Bedrock time out on the next message (to show recovery)
              </Checkbox>
            </SpaceBetween>
          </Container>

          {active ? (
            <>
              <Container
                header={
                  <Header variant="h3" actions={<Link href="#/requests">Open in queue</Link>}>
                    What the system did
                  </Header>
                }
              >
                <RequestStatus request={active} />
                {active.processing_error && (
                  <Box margin={{ top: 'xs' }} color="text-body-secondary">
                    The message is saved. Retry it from the Requests page.
                  </Box>
                )}
              </Container>
              <ExtractionPanel request={active} />
              <ProcessingTimeline request={active} />
            </>
          ) : (
            <Box color="text-body-secondary">Send a message to see each processing step here.</Box>
          )}
        </SpaceBetween>
      </ColumnLayout>
    </ContentLayout>
  )
}
