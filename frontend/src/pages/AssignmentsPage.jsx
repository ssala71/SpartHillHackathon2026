import { useState } from 'react'
import Box from '@cloudscape-design/components/box'
import Button from '@cloudscape-design/components/button'
import ContentLayout from '@cloudscape-design/components/content-layout'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Table from '@cloudscape-design/components/table'
import { useData } from '../hooks/DataContext.jsx'
import { needLabel, timeAgo } from '../components/format.js'
import { Status, UrgencyBadge } from '../components/StatusBadges.jsx'

// Allowed next steps for each assignment status.
const TRANSITIONS = {
  Pending: [
    { status: 'Accepted', label: 'Accept', primary: true },
    { status: 'Declined', label: 'Decline' },
  ],
  Accepted: [
    { status: 'InProgress', label: 'Start delivery', primary: true },
    { status: 'Cancelled', label: 'Cancel' },
  ],
  InProgress: [{ status: 'Completed', label: 'Mark delivered', primary: true }],
}

export default function AssignmentsPage() {
  const { assignments, requests, resources, loading, run } = useData()
  const [busyId, setBusyId] = useState(null)
  const requestFor = (a) => requests.find((r) => r.id === a.request_id)

  const move = async (assignment, status) => {
    setBusyId(assignment.id)
    await run((api) => api.updateAssignment(assignment.id, { status }), `Assignment marked ${status}.`)
    setBusyId(null)
  }

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Delivery is only confirmed to the requester after someone accepts the assignment.">
          Assignments
        </Header>
      }
    >
      <Table
        items={assignments}
        loading={loading}
        loadingText="Loading assignments"
        trackBy="id"
        wrapLines
        empty={<Box textAlign="center">No assignments yet. Create one from a request.</Box>}
        columnDefinitions={[
          { id: 'urgency', header: 'Urgency', cell: (a) => (requestFor(a) ? <UrgencyBadge urgency={requestFor(a).urgency} /> : '-') },
          { id: 'request', header: 'Request', cell: (a) => requestFor(a)?.message ?? a.request_id, minWidth: 260 },
          { id: 'needs', header: 'Needs', cell: (a) => requestFor(a)?.needs?.map(needLabel).join(', ') || '-' },
          { id: 'resource', header: 'From resource', cell: (a) => resources.find((r) => r.id === a.resource_id)?.name ?? a.resource_id },
          { id: 'person', header: 'Assigned to', cell: (a) => a.coordinator_name ?? <Box color="text-status-inactive">Unassigned</Box> },
          { id: 'status', header: 'Status', cell: (a) => <Status value={a.status} />, minWidth: 130 },
          { id: 'notes', header: 'Notes', cell: (a) => a.notes ?? '-', minWidth: 180 },
          { id: 'updated', header: 'Updated', cell: (a) => timeAgo(a.updated_at) },
          {
            id: 'actions',
            header: 'Actions',
            minWidth: 230,
            cell: (a) => (
              <SpaceBetween direction="horizontal" size="xs">
                {(TRANSITIONS[a.status] ?? []).map((t) => (
                  <Button key={t.status} variant={t.primary ? 'primary' : 'normal'} loading={busyId === a.id && t.primary} onClick={() => move(a, t.status)}>
                    {t.label}
                  </Button>
                ))}
              </SpaceBetween>
            ),
          },
        ]}
      />
    </ContentLayout>
  )
}
