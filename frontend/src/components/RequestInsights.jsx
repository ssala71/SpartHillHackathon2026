import Badge from '@cloudscape-design/components/badge'
import Box from '@cloudscape-design/components/box'
import Container from '@cloudscape-design/components/container'
import ExpandableSection from '@cloudscape-design/components/expandable-section'
import Header from '@cloudscape-design/components/header'
import KeyValuePairs from '@cloudscape-design/components/key-value-pairs'
import SpaceBetween from '@cloudscape-design/components/space-between'
import StatusIndicator from '@cloudscape-design/components/status-indicator'
import { needLabel } from './format.js'
import { UrgencyBadge } from './StatusBadges.jsx'

const clock = (iso) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })

export function ProcessingTimeline({ request }) {
  const events = request.events ?? []
  const processing = request.status === 'Processing' && !request.processing_error
  return (
    <Container header={<Header variant="h3" description="Every step is logged, so nothing is lost if one fails.">Processing timeline</Header>}>
      <ol className="timeline">
        {events.map((e, i) => (
          <li key={i}>
            <time>{clock(e.at)}</time>
            <div>
              <StatusIndicator type={e.error ? 'error' : 'success'}>{e.label}</StatusIndicator>
              {e.detail && <Box variant="small" color="text-body-secondary" display="block">{e.detail}</Box>}
            </div>
          </li>
        ))}
        {processing && (
          <li>
            <time />
            <StatusIndicator type="loading">Bedrock is reading the message…</StatusIndicator>
          </li>
        )}
      </ol>
    </Container>
  )
}

export function ExtractionPanel({ request }) {
  const x = request.extraction
  if (!x) {
    return (
      <Container header={<Header variant="h3">Amazon Bedrock extraction</Header>}>
        <Box color="text-body-secondary">{request.processing_error ? 'No extraction yet. Processing failed.' : 'Waiting for Bedrock.'}</Box>
      </Container>
    )
  }
  const structured = {
    needs: request.needs,
    location_description: request.location_description,
    people_count: request.people_count,
    urgency: request.urgency,
    urgency_indicators: x.urgency_indicators,
    missing_fields: x.missing_fields,
    language: x.language,
  }
  return (
    <Container
      header={
        <Header variant="h3" description="Bedrock turns free text into validated fields. It never picks the resource; verified data and rules do.">
          Amazon Bedrock extraction
        </Header>
      }
    >
      <SpaceBetween size="m">
        <KeyValuePairs
          columns={2}
          items={[
            { label: 'Needs', value: request.needs?.length ? request.needs.map(needLabel).join(', ') : 'Unclear' },
            { label: 'Location', value: request.location_description ?? 'Missing' },
            { label: 'People', value: request.people_count ?? 'Not stated' },
            { label: 'Urgency', value: <UrgencyBadge urgency={request.urgency} /> },
            {
              label: 'Why flagged',
              value: x.urgency_indicators.length ? (
                <SpaceBetween direction="horizontal" size="xxs">
                  {x.urgency_indicators.map((w) => (
                    <Badge key={w} color="severity-medium">{w}</Badge>
                  ))}
                </SpaceBetween>
              ) : (
                'No urgency words'
              ),
            },
            { label: 'Missing', value: x.missing_fields.length ? x.missing_fields.join(', ') : 'Nothing' },
            { label: 'Language', value: x.language === 'es' ? 'Spanish (reply sent in Spanish)' : 'English' },
            { label: 'Model', value: `${x.model_id}, ${x.latency_ms} ms` },
          ]}
        />
        <ExpandableSection headerText="Structured output (validated JSON)">
          <Box variant="code">
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(structured, null, 2)}</pre>
          </Box>
        </ExpandableSection>
      </SpaceBetween>
    </Container>
  )
}
