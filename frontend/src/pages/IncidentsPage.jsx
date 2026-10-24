import { useState } from 'react'
import Box from '@cloudscape-design/components/box'
import Button from '@cloudscape-design/components/button'
import ContentLayout from '@cloudscape-design/components/content-layout'
import FormField from '@cloudscape-design/components/form-field'
import Header from '@cloudscape-design/components/header'
import Input from '@cloudscape-design/components/input'
import Modal from '@cloudscape-design/components/modal'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Table from '@cloudscape-design/components/table'
import Textarea from '@cloudscape-design/components/textarea'
import { useData } from '../hooks/DataContext.jsx'
import { timeAgo } from '../components/format.js'
import { Status } from '../components/StatusBadges.jsx'

const SMS_LIMIT = 160

export default function IncidentsPage() {
  const { incidents, requests, loading, run } = useData()
  const [editing, setEditing] = useState(null) // null, 'new', or an incident
  const [busyId, setBusyId] = useState(null)

  const setStatus = async (incident, status, message) => {
    setBusyId(incident.id)
    await run((api) => (status === 'Active' ? api.sendAlert(incident.id) : api.updateIncident(incident.id, { status })), message)
    setBusyId(null)
  }

  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          description="Start an incident, write the SMS alert, and send it to subscribers in the affected area."
          actions={
            <Button variant="primary" onClick={() => setEditing('new')}>
              New incident
            </Button>
          }
        >
          Incidents and alerts
        </Header>
      }
    >
      <Table
        items={incidents}
        loading={loading}
        loadingText="Loading incidents"
        trackBy="id"
        wrapLines
        empty={<Box textAlign="center">No incidents yet. Create one to send the first alert.</Box>}
        columnDefinitions={[
          { id: 'name', header: 'Incident', cell: (i) => <b>{i.name}</b> },
          { id: 'area', header: 'Affected area', cell: (i) => i.affected_area },
          { id: 'status', header: 'Status', cell: (i) => <Status value={i.status} /> },
          { id: 'alert', header: 'Alert text', cell: (i) => i.alert_text || <Box color="text-status-inactive">Not written</Box>, maxWidth: 360 },
          { id: 'requests', header: 'Requests', cell: (i) => requests.filter((r) => r.incident_id === i.id).length },
          { id: 'created', header: 'Created', cell: (i) => timeAgo(i.created_at) },
          {
            id: 'actions',
            header: 'Actions',
            cell: (i) => (
              <SpaceBetween direction="horizontal" size="xs">
                {['Draft', 'Paused'].includes(i.status) && (
                  <Button variant="primary" loading={busyId === i.id} onClick={() => setStatus(i, 'Active', `Alert sent for ${i.name} (simulated).`)}>
                    Send alert
                  </Button>
                )}
                {i.status === 'Active' && (
                  <Button loading={busyId === i.id} onClick={() => setStatus(i, 'Resolved', `${i.name} resolved.`)}>
                    Resolve
                  </Button>
                )}
                {!['Resolved', 'Cancelled'].includes(i.status) && <Button onClick={() => setEditing(i)}>Edit</Button>}
              </SpaceBetween>
            ),
          },
        ]}
      />
      {editing && <IncidentModal incident={editing === 'new' ? null : editing} onDismiss={() => setEditing(null)} />}
    </ContentLayout>
  )
}

function IncidentModal({ incident, onDismiss }) {
  const { run } = useData()
  const [form, setForm] = useState({
    name: incident?.name ?? '',
    affected_area: incident?.affected_area ?? '',
    description: incident?.description ?? '',
    alert_text: incident?.alert_text ?? '',
  })
  const [submitting, setSubmitting] = useState(false)
  const field = (key) => ({ value: form[key], onChange: ({ detail }) => setForm((f) => ({ ...f, [key]: detail.value })) })
  const valid = form.name.trim() && form.affected_area.trim()

  const submit = async () => {
    setSubmitting(true)
    const result = await run(
      (api) => (incident ? api.updateIncident(incident.id, form) : api.createIncident(form)),
      incident ? 'Incident updated.' : 'Incident created as a draft.',
    )
    setSubmitting(false)
    if (result) onDismiss()
  }

  return (
    <Modal
      visible
      onDismiss={onDismiss}
      header={incident ? 'Edit incident' : 'New incident'}
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={onDismiss}>
              Cancel
            </Button>
            <Button variant="primary" disabled={!valid} loading={submitting} onClick={submit}>
              Save
            </Button>
          </SpaceBetween>
        </Box>
      }
    >
      <SpaceBetween size="m">
        <FormField label="Name">
          <Input {...field('name')} placeholder="San José power outage" />
        </FormField>
        <FormField label="Affected area">
          <Input {...field('affected_area')} placeholder="ZIP codes or neighborhoods" />
        </FormField>
        <FormField label="Description" description="Internal only.">
          <Textarea {...field('description')} rows={2} />
        </FormField>
        <FormField
          label="SMS alert text"
          constraintText={`${form.alert_text.length}/${SMS_LIMIT} characters${form.alert_text.length > SMS_LIMIT ? ', will send as multiple messages' : ''}`}
        >
          <Textarea {...field('alert_text')} rows={4} placeholder="Reply with what you need and your nearest cross street. Reply STOP to opt out." />
        </FormField>
      </SpaceBetween>
    </Modal>
  )
}
