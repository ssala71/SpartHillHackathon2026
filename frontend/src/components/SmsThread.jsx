const clock = (iso) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })

export default function SmsThread({ messages, emptyText = 'No messages yet.' }) {
  if (!messages?.length) return <p className="sms-empty">{emptyText}</p>
  return (
    <div className="sms-thread">
      {messages.map((m, i) => (
        <div key={i} className={`sms-bubble sms-${m.direction}`}>
          {m.body}
          <div className="sms-time">{clock(m.at)}</div>
        </div>
      ))}
    </div>
  )
}
