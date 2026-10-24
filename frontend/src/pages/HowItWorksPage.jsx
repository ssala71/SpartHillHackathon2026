import Box from '@cloudscape-design/components/box'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import Container from '@cloudscape-design/components/container'
import ContentLayout from '@cloudscape-design/components/content-layout'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Table from '@cloudscape-design/components/table'

// Update the service names here if the team's AWS choices change.
const PIPELINE = [
  { step: 'Resident texts', svc: 'Any phone with SMS', body: 'No app, no data plan, no account. Works when the internet is down but cell service is up.' },
  { step: 'Message arrives', svc: 'AWS End User Messaging SMS', body: 'Inbound text is forwarded to our API. Opt-outs (STOP) are honored here.' },
  { step: 'Saved first', svc: 'FastAPI + Amazon RDS (PostgreSQL)', body: 'The raw message is stored before any AI runs, so a failure never loses a request.' },
  { step: 'Understood', svc: 'Amazon Bedrock', body: 'Turns free text (English or Spanish) into validated fields: needs, location, people, urgency words, missing details.' },
  { step: 'Matched', svc: 'Matching rules on verified data', body: 'Only active, verified resources with stock on hand. Nearest first. Never invented.' },
  { step: 'Answered', svc: 'SMS reply + this dashboard', body: 'Normal needs get a location. Urgent or medical needs go to a coordinator. Unclear ones get a follow-up question.' },
]

const DECISIONS = [
  { situation: 'Normal request with a verified match', response: 'Text the nearest location, what it has, and when it was verified.' },
  { situation: 'Medical or urgent words detected', response: 'Lead with 911, send the nearest verified location, and flag it so a coordinator follows up.' },
  { situation: 'Need or location missing', response: 'Ask one short follow-up question. Their answer joins the same request.' },
  { situation: 'No suitable resource or stale data', response: 'Say so plainly and flag for review. Do not invent a match.' },
  { situation: 'Bedrock fails or times out', response: 'The saved message is marked failed and stays in the queue for retry.' },
  { situation: 'Delivery needed', response: 'Create an assignment. The person is only told help is coming after a volunteer accepts.' },
]

export default function HowItWorksPage() {
  return (
    <ContentLayout
      header={
        <Header variant="h1" description="From a text message to a verified answer, and where AWS fits.">
          How it works
        </Header>
      }
    >
      <SpaceBetween size="l">
        <Container header={<Header variant="h2">Request pipeline</Header>}>
          <div className="pipeline">
            {PIPELINE.map((p, i) => (
              <div key={p.step} className="pipeline-step">
                <div className="svc">{p.svc}</div>
                <Box variant="h4" padding={{ top: 'xxs' }}>
                  {i + 1}. {p.step}
                </Box>
                <Box variant="small">{p.body}</Box>
              </div>
            ))}
          </div>
        </Container>

        <Table
          header={<Header variant="h2">What the system does in each case</Header>}
          items={DECISIONS}
          wrapLines
          columnDefinitions={[
            { id: 'situation', header: 'Situation', cell: (d) => <b>{d.situation}</b> },
            { id: 'response', header: 'Response', cell: (d) => d.response },
          ]}
        />

        <ColumnLayout columns={2}>
          <Container header={<Header variant="h2">What Bedrock does, and doesn't</Header>}>
            <SpaceBetween size="xs">
              <Box>Bedrock reads messy, misspelled, bilingual texts and returns structured JSON that we validate before use.</Box>
              <Box>It flags urgency words and lists what is missing, which drives the follow-up question.</Box>
              <Box>It does not choose resources, invent addresses, or make medical decisions. Matching uses verified records and fixed rules.</Box>
            </SpaceBetween>
          </Container>
          <Container header={<Header variant="h2">Safety and limits</Header>}>
            <SpaceBetween size="xs">
              <Box>Prototype only. Not an emergency dispatch or official alert system.</Box>
              <Box>Urgency flags are not diagnoses. A person makes the call.</Box>
              <Box>Phone numbers are masked on screen. Demo data is simulated and labeled.</Box>
              <Box>SMS depends on cellular service. We do not claim guaranteed availability.</Box>
            </SpaceBetween>
          </Container>
        </ColumnLayout>
      </SpaceBetween>
    </ContentLayout>
  )
}
