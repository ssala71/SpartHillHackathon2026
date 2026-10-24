import { useEffect, useMemo, useState } from 'react'
import { useCollection } from '@cloudscape-design/collection-hooks'
import Box from '@cloudscape-design/components/box'
import Button from '@cloudscape-design/components/button'
import ContentLayout from '@cloudscape-design/components/content-layout'
import Header from '@cloudscape-design/components/header'
import SegmentedControl from '@cloudscape-design/components/segmented-control'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Table from '@cloudscape-design/components/table'
import TextFilter from '@cloudscape-design/components/text-filter'
import { useData } from '../hooks/DataContext.jsx'
import { needLabel, timeAgo } from '../components/format.js'
import { RequestStatus, UrgencyBadge } from '../components/StatusBadges.jsx'
import RequestDetail from './RequestDetail.jsx'

const URGENCY_ORDER = { Medical: 0, Urgent: 1, Normal: 2 }

const VIEWS = {
  review: (r) => r.status === 'NeedsReview' || Boolean(r.processing_error),
  open: (r) => !['Completed', 'Cancelled'].includes(r.status),
  all: () => true,
}

export default function RequestsPage({ setSplitPanel }) {
  const { requests, loading, error, refresh } = useData()
  const [view, setView] = useState('review')
  const [selectedId, setSelectedId] = useState(null)

  const visible = useMemo(
    () =>
      requests
        .filter(VIEWS[view])
        .sort((a, b) => URGENCY_ORDER[a.urgency] - URGENCY_ORDER[b.urgency] || b.created_at.localeCompare(a.created_at)),
    [requests, view],
  )

  const { items, filterProps, collectionProps, filteredItemsCount } = useCollection(visible, {
    filtering: {
      filteringFunction: (item, text) =>
        [item.message, item.location_description, ...(item.needs ?? [])].join(' ').toLowerCase().includes(text.toLowerCase()),
      empty: (
        <Box textAlign="center" color="inherit">
          <b>No requests here</b>
          <Box variant="p" color="inherit">
            {view === 'review' ? 'Nothing needs review right now.' : 'Incoming SMS requests will appear here.'}
          </Box>
        </Box>
      ),
      noMatch: <Box textAlign="center">No requests match the filter.</Box>,
    },
    sorting: {},
  })

  const selected = requests.find((r) => r.id === selectedId)

  useEffect(() => {
    setSplitPanel(selected ? { content: <RequestDetail request={selected} onClose={() => setSelectedId(null)} /> } : null)
  }, [selected, setSplitPanel])

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Incoming SMS replies after Bedrock extraction. Urgent and medical requests always need a coordinator.">
          Requests
        </Header>
      }
    >
      <Table
        {...collectionProps}
        items={items}
        loading={loading}
        loadingText="Loading requests"
        trackBy="id"
        variant="full-page"
        selectionType="single"
        selectedItems={selected ? [selected] : []}
        onSelectionChange={({ detail }) => setSelectedId(detail.selectedItems[0]?.id ?? null)}
        onRowClick={({ detail }) => setSelectedId(detail.item.id)}
        header={
          <Header
            counter={`(${visible.length})`}
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                <SegmentedControl
                  selectedId={view}
                  onChange={({ detail }) => setView(detail.selectedId)}
                  options={[
                    { id: 'review', text: 'Needs review' },
                    { id: 'open', text: 'Open' },
                    { id: 'all', text: 'All' },
                  ]}
                />
                <Button iconName="refresh" ariaLabel="Refresh" onClick={refresh} />
              </SpaceBetween>
            }
          >
            {error ? `Requests (error: ${error})` : 'Requests'}
          </Header>
        }
        filter={<TextFilter {...filterProps} filteringPlaceholder="Search messages, locations, needs" countText={`${filteredItemsCount} matches`} />}
        columnDefinitions={[
          { id: 'urgency', header: 'Urgency', cell: (r) => <UrgencyBadge urgency={r.urgency} />, width: 110 },
          { id: 'message', header: 'Message', cell: (r) => r.message, maxWidth: 380 },
          {
            id: 'needs',
            header: 'Needs',
            cell: (r) => (r.needs?.length ? r.needs.map(needLabel).join(', ') : <Box color="text-status-inactive">Unclear</Box>),
          },
          { id: 'location', header: 'Location', cell: (r) => r.location_description ?? <Box color="text-status-inactive">Missing</Box> },
          { id: 'status', header: 'Status', cell: (r) => <RequestStatus request={r} /> },
          { id: 'next', header: 'Next action', cell: (r) => r.suggested_match?.next_action ?? '-' },
          { id: 'received', header: 'Received', cell: (r) => timeAgo(r.created_at), sortingField: 'created_at' },
        ]}
      />
    </ContentLayout>
  )
}
