import Box from '@cloudscape-design/components/box'

const clock = (iso) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })

export default function SmsThread({ messages, emptyText = 'No messages yet.' }) {
  if (!messages?.length) return <Box color="text-body-secondary">{emptyText}</Box>
  return (
    <div className="sms-thread">
      {messages.map((m, i) => (
        <div key={i} className={`sms-bubble sms-${m.direction}`}>
          {m.body}
          {m.direction !== 'system' && <div className="sms-time">{clock(m.at)}</div>}
        </div>
      ))}
    </div>
  )
}
