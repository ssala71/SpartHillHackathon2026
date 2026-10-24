import { useState } from 'react'
import Box from '@cloudscape-design/components/box'
import Button from '@cloudscape-design/components/button'
import ButtonDropdown from '@cloudscape-design/components/button-dropdown'
import ContentLayout from '@cloudscape-design/components/content-layout'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Table from '@cloudscape-design/components/table'
import { useData } from '../hooks/DataContext.jsx'
import { needLabel, splitWords } from '../components/format.js'
import { Status, UrgencyBadge } from '../components/StatusBadges.jsx'

// Next steps for each status: the first is the main action, the rest go in the menu.
const TRANSITIONS = {
  Pending: [
    { status: 'Accepted', label: 'Accept' },
    { status: 'Declined', label: 'Decline' },
  ],
  Accepted: [
    { status: 'InProgress', label: 'Start delivery' },
    { status: 'Pending', label: 'Move back to pending' },
    { status: 'Cancelled', label: 'Cancel' },
  ],
  InProgress: [
    { status: 'Completed', label: 'Mark delivered' },
    { status: 'Accepted', label: 'Move back to accepted' },
  ],
  Completed: [{ status: 'InProgress', label: 'Reopen' }],
  Declined: [{ status: 'Pending', label: 'Reopen' }],
  Cancelled: [{ status: 'Pending', label: 'Reopen' }],
}

// Only forward progress texts the requester; reopening or stepping back stays silent.
const FORWARD = { Pending: 'Accepted', Accepted: 'InProgress' }

export default function AssignmentsPage() {
  const { assignments, requests, resources, loading, run } = useData()
  const [busyId, setBusyId] = useState(null)
  const requestFor = (a) => requests.find((r) => r.id === a.request_id)

  const move = async (assignment, status) => {
    const before = { status: assignment.status, requestStatus: requestFor(assignment)?.status }
    setBusyId(assignment.id)
    await run(
      (api) => api.updateAssignment(assignment.id, { status, notify: FORWARD[assignment.status] === status }),
      `Assignment marked ${splitWords(status).toLowerCase()}.`,
      async (api) => {
        await api.updateAssignment(assignment.id, { status: before.status, notify: false })
        if (before.requestStatus) await api.updateRequest(assignment.request_id, { status: before.requestStatus })
      },
    )
    setBusyId(null)
  }

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="The requester is only told help is coming after someone accepts.">
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
          {
            id: 'request',
            header: 'Request',
            cell: (a) => {
              const r = requestFor(a)
              if (!r) return a.request_id
              return (
                <SpaceBetween size="xxs">
                  <UrgencyBadge urgency={r.urgency} />
                  <span>{r.message}</span>
                  <Box variant="small" color="text-body-secondary">
                    {r.needs?.map(needLabel).join(', ')}
                  </Box>
                </SpaceBetween>
              )
            },
          },
          { id: 'resource', header: 'Resource', cell: (a) => resources.find((r) => r.id === a.resource_id)?.name ?? a.resource_id },
          { id: 'person', header: 'Assigned to', cell: (a) => a.coordinator_name ?? <Box color="text-status-inactive">Unassigned</Box> },
          { id: 'status', header: 'Status', cell: (a) => <Status value={a.status} />, minWidth: 140 },
          {
            id: 'actions',
            header: 'Actions',
            minWidth: 160,
            cell: (a) => {
              const [main, ...more] = TRANSITIONS[a.status] ?? []
              if (!main) return null
              return (
                <SpaceBetween direction="horizontal" size="xxs" alignItems="center">
                  <Button
                    variant={a.status === 'Completed' || a.status === 'Declined' || a.status === 'Cancelled' ? 'normal' : 'primary'}
                    loading={busyId === a.id}
                    onClick={() => move(a, main.status)}
                  >
                    {main.label}
                  </Button>
                  {more.length > 0 && (
                    <ButtonDropdown
                      variant="icon"
                      ariaLabel="More actions"
                      items={more.map((t) => ({ id: t.status, text: t.label }))}
                      onItemClick={({ detail }) => move(a, detail.id)}
                    />
                  )}
                </SpaceBetween>
              )
            },
          },
        ]}
      />
    </ContentLayout>
  )
}
