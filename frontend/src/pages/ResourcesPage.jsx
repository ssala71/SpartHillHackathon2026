import Box from '@cloudscape-design/components/box'
import ContentLayout from '@cloudscape-design/components/content-layout'
import Header from '@cloudscape-design/components/header'
import Input from '@cloudscape-design/components/input'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Table from '@cloudscape-design/components/table'
import { useData } from '../hooks/DataContext.jsx'
import { needLabel, splitWords, timeAgo } from '../components/format.js'
import { Status } from '../components/StatusBadges.jsx'

const STALE_MINUTES = 240

export default function ResourcesPage() {
  const { resources, inventory, loading, run } = useData()
  const resourceName = (id) => resources.find((r) => r.id === id)?.name ?? id

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Only active resources are matched. Stock changes take effect on the next match.">
          Resources and inventory
        </Header>
      }
    >
      <SpaceBetween size="l">
        <Table
          items={resources}
          loading={loading}
          loadingText="Loading resources"
          trackBy="id"
          wrapLines
          header={<Header counter={`(${resources.length})`}>Resources</Header>}
          empty={<Box textAlign="center">No resources yet. Add the demo dataset to get started.</Box>}
          columnDefinitions={[
            {
              id: 'name',
              header: 'Resource',
              cell: (r) => (
                <>
                  <b>{r.name}</b>
                  <Box variant="small" color="text-body-secondary" display="block">
                    {r.resource_type} · {r.address}
                  </Box>
                </>
              ),
            },
            { id: 'services', header: 'Services', cell: (r) => r.services?.map(needLabel).join(', ') ?? '-' },
            { id: 'status', header: 'Status', cell: (r) => <Status value={r.status} />, minWidth: 190 },
            {
              id: 'verified',
              header: 'Verified',
              cell: (r) => {
                const stale = (Date.now() - new Date(r.last_verified_at)) / 60_000 > STALE_MINUTES
                return (
                  <>
                    <Box color={stale ? 'text-status-warning' : 'inherit'}>
                      {timeAgo(r.last_verified_at)}
                      {stale ? ' (stale)' : ''}
                    </Box>
                    <Box variant="small" color="text-body-secondary" display="block">
                      {r.source}
                    </Box>
                  </>
                )
              },
            },
          ]}
        />

        <Table
          items={inventory}
          loading={loading}
          loadingText="Loading inventory"
          trackBy="id"
          header={
            <Header counter={`(${inventory.length})`} description="Click a quantity to edit it.">
              Inventory
            </Header>
          }
          empty={<Box textAlign="center">No inventory recorded.</Box>}
          submitEdit={async (item, column, value) => {
            if (value === undefined) return
            const quantity = Number(value)
            await run(
              (api) => api.updateInventoryItem(item.id, { quantity }),
              `${item.item_name} at ${resourceName(item.resource_id)} set to ${quantity}.`,
              (api) => api.updateInventoryItem(item.id, { quantity: item.quantity, status: item.status }),
            )
          }}
          columnDefinitions={[
            { id: 'item', header: 'Item', cell: (i) => i.item_name },
            { id: 'resource', header: 'Resource', cell: (i) => resourceName(i.resource_id) },
            { id: 'category', header: 'Category', cell: (i) => splitWords(i.category) },
            {
              id: 'quantity',
              header: 'Quantity',
              cell: (i) => `${i.quantity} ${i.unit}`,
              editConfig: {
                ariaLabel: 'Quantity',
                editIconAriaLabel: 'editable',
                validation: (item, value) => {
                  if (value === undefined) return undefined
                  const quantity = Number(value)
                  return Number.isInteger(quantity) && quantity >= 0 ? undefined : 'Enter a whole number, 0 or more.'
                },
                editingCell: (item, { currentValue, setValue }) => (
                  <Input autoFocus type="number" value={currentValue ?? String(item.quantity)} onChange={({ detail }) => setValue(detail.value)} />
                ),
              },
            },
            { id: 'status', header: 'Status', cell: (i) => <Status value={i.status} />, minWidth: 140 },
            { id: 'expires', header: 'Expires', cell: (i) => i.expiration_date ?? '-' },
          ]}
        />
      </SpaceBetween>
    </ContentLayout>
  )
}
