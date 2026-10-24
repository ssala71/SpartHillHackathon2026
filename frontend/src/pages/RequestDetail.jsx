import { useState } from 'react'
import Alert from '@cloudscape-design/components/alert'
import Box from '@cloudscape-design/components/box'
import Button from '@cloudscape-design/components/button'
import Container from '@cloudscape-design/components/container'
import Form from '@cloudscape-design/components/form'
import FormField from '@cloudscape-design/components/form-field'
import Header from '@cloudscape-design/components/header'
import Input from '@cloudscape-design/components/input'
import KeyValuePairs from '@cloudscape-design/components/key-value-pairs'
import Modal from '@cloudscape-design/components/modal'
import Select from '@cloudscape-design/components/select'
import SpaceBetween from '@cloudscape-design/components/space-between'
import SplitPanel from '@cloudscape-design/components/split-panel'
import Textarea from '@cloudscape-design/components/textarea'
import { useData } from '../hooks/DataContext.jsx'
import { maskPhone, timeAgo } from '../components/format.js'
import { RequestStatus, Status } from '../components/StatusBadges.jsx'
import SmsThread from '../components/SmsThread.jsx'
import { ExtractionPanel, ProcessingTimeline } from '../components/RequestInsights.jsx'

export default function RequestDetail({ request, onClose }) {
  const { run, assignments } = useData()
  const [busy, setBusy] = useState(null)
  const [assignOpen, setAssignOpen] = useState(false)
  const match = request.suggested_match
  const assignment = assignments.find((a) => a.request_id === request.id && !['Declined', 'Cancelled'].includes(a.status))
  const closed = ['Completed', 'Cancelled'].includes(request.status)

  const act = async (key, action, message) => {
    setBusy(key)
    await run(action, message)
    setBusy(null)
  }

  return (
    <SplitPanel header={`Request from ${maskPhone(request.source_phone)}`} closeBehavior="hide" hidePreferencesButton>
      <SpaceBetween size="l">
        {request.processing_error && (
          <Alert
            type="error"
            header="Bedrock processing failed"
            action={
              <Button loading={busy === 'retry'} onClick={() => act('retry', (api) => api.processRequest(request.id), 'Bedrock processed the saved message.')}>
                Retry processing
              </Button>
            }
          >
            {request.processing_error}. The original message is saved, so it can be retried without losing anything.
          </Alert>
        )}

        {request.urgency !== 'Normal' && (
          <Alert type="warning" header={`${request.urgency} flag: coordinator decision needed`}>
            This flag comes from the message text. It is not a medical diagnosis or a final triage decision.
          </Alert>
        )}

        <Container header={<Header variant="h3" description={`Received ${timeAgo(request.created_at)}`}>SMS conversation</Header>}>
          <SmsThread messages={request.messages ?? [{ direction: 'in', body: request.message, at: request.created_at }]} />
        </Container>

        <KeyValuePairs
          columns={2}
          items={[
            { label: 'Status', value: <RequestStatus request={request} /> },
            { label: 'People', value: request.people_count ?? 'Unknown' },
          ]}
        />

        <ExtractionPanel request={request} />

        <Container header={<Header variant="h3">Suggested match</Header>}>
          {match?.resource_id ? (
            <KeyValuePairs
              columns={2}
              items={[
                { label: 'Resource', value: <b>{match.resource_name}</b> },
                { label: 'Distance', value: `${match.distance_km} km (straight line)` },
                { label: 'Address', value: match.address },
                { label: 'Next action', value: match.next_action },
                { label: 'Reason', value: match.reason },
                { label: 'Source', value: `${match.source}, verified ${timeAgo(match.last_verified_at)}` },
              ]}
            />
          ) : (
            <SpaceBetween size="xs">
              <Box variant="strong">No match</Box>
              <Box>{match?.reason}</Box>
              <Box color="text-body-secondary">Next action: {match?.next_action}</Box>
            </SpaceBetween>
          )}
        </Container>

        {assignment && (
          <Alert type="info" header="Assignment exists">
            {assignment.coordinator_name ? `${assignment.coordinator_name}: ` : ''}
            <Status value={assignment.status} /> Delivery is only confirmed once someone accepts it.
          </Alert>
        )}

        {!closed && !request.processing_error && (
          <SpaceBetween direction="horizontal" size="xs">
            {match?.resource_id && request.status === 'NeedsReview' && (
              <Button
                variant="primary"
                loading={busy === 'approve'}
                onClick={() => act('approve', (api) => api.approveMatch(request.id), 'Match approved and location sent by SMS.')}
              >
                Approve and send location
              </Button>
            )}
            {match?.next_action === 'Ask follow-up question' && (
              <Button
                variant="primary"
                loading={busy === 'followup'}
                onClick={() => act('followup', (api) => api.sendFollowUp(request.id), 'Follow-up question sent by SMS.')}
              >
                Resend follow-up
              </Button>
            )}
            {!assignment && <Button onClick={() => setAssignOpen(true)}>Assign delivery</Button>}
            <Button
              loading={busy === 'cancel'}
              onClick={() => act('cancel', (api) => api.updateRequest(request.id, { status: 'Cancelled' }), 'Request cancelled.')}
            >
              Cancel request
            </Button>
            <Button variant="link" onClick={onClose}>
              Close
            </Button>
          </SpaceBetween>
        )}
      </SpaceBetween>

      <Box margin={{ top: 'l' }}>
        <ProcessingTimeline request={request} />
      </Box>

      {assignOpen && <AssignModal request={request} onDismiss={() => setAssignOpen(false)} />}
    </SplitPanel>
  )
}

function AssignModal({ request, onDismiss }) {
  const { resources, run } = useData()
  const options = resources.map((r) => ({ value: r.id, label: r.name, description: r.address, tags: [r.status] }))
  const [resource, setResource] = useState(options.find((o) => o.value === request.suggested_match?.resource_id) ?? null)
  const [coordinator, setCoordinator] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    setSubmitting(true)
    const result = await run(
      (api) => api.createAssignment({ request_id: request.id, resource_id: resource.value, coordinator_name: coordinator || null, notes: notes || null }),
      'Assignment created. It stays pending until someone accepts it.',
    )
    setSubmitting(false)
    if (result) onDismiss()
  }

  return (
    <Modal
      visible
      onDismiss={onDismiss}
      header="Assign delivery"
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={onDismiss}>
              Cancel
            </Button>
            <Button variant="primary" disabled={!resource} loading={submitting} onClick={submit}>
              Create assignment
            </Button>
          </SpaceBetween>
        </Box>
      }
    >
      <Form>
        <SpaceBetween size="m">
          <FormField label="Resource">
            <Select selectedOption={resource} onChange={({ detail }) => setResource(detail.selectedOption)} options={options} placeholder="Choose a resource" />
          </FormField>
          <FormField label="Volunteer or coordinator" description="Optional. Leave blank until someone takes it.">
            <Input value={coordinator} onChange={({ detail }) => setCoordinator(detail.value)} />
          </FormField>
          <FormField label="Notes">
            <Textarea value={notes} onChange={({ detail }) => setNotes(detail.value)} rows={3} />
          </FormField>
        </SpaceBetween>
      </Form>
    </Modal>
  )
}
