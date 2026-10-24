import Alert from '@cloudscape-design/components/alert'
import Box from '@cloudscape-design/components/box'
import ColumnLayout from '@cloudscape-design/components/column-layout'
import Container from '@cloudscape-design/components/container'
import ContentLayout from '@cloudscape-design/components/content-layout'
import Header from '@cloudscape-design/components/header'
import Link from '@cloudscape-design/components/link'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Spinner from '@cloudscape-design/components/spinner'
import { useData } from '../hooks/DataContext.jsx'
import { Status } from '../components/StatusBadges.jsx'

function Stat({ label, value, href, loading }) {
  return (
    <div>
      <Box variant="awsui-key-label">{label}</Box>
      <Link variant="awsui-value-large" href={href}>
        {loading ? <Spinner /> : value}
      </Link>
    </div>
  )
}

export default function OverviewPage() {
  const { incidents, requests, inventory, assignments, loading, error } = useData()
  const active = incidents.filter((i) => i.status === 'Active')
  const needsReview = requests.filter((r) => r.status === 'NeedsReview' && !r.processing_error).length
  const failed = requests.filter((r) => r.processing_error).length
  const lowStock = inventory.filter((i) => ['Low', 'OutOfStock'].includes(i.status)).length
  const pendingAssignments = assignments.filter((a) => a.status === 'Pending').length

  return (
    <ContentLayout header={<Header variant="h1">Overview</Header>}>
      <SpaceBetween size="l">
        {error && (
          <Alert type="error" header="Could not load data">
            {error}
          </Alert>
        )}
        <Container header={<Header variant="h2">Right now</Header>}>
          <ColumnLayout columns={5} variant="text-grid">
            <Stat label="Needs review" value={needsReview} href="#/admin/requests" loading={loading} />
            <Stat label="Failed processing" value={failed} href="#/admin/requests" loading={loading} />
            <Stat label="Pending assignments" value={pendingAssignments} href="#/admin/assignments" loading={loading} />
            <Stat label="Low or out of stock" value={lowStock} href="#/admin/resources" loading={loading} />
            <Stat label="Total requests" value={requests.length} href="#/admin/requests" loading={loading} />
          </ColumnLayout>
        </Container>
        <Container header={<Header variant="h2">Active incidents</Header>}>
          {active.length ? (
            <SpaceBetween size="s">
              {active.map((i) => (
                <div key={i.id}>
                  <Box variant="strong">{i.name}</Box> <Status value={i.status} />
                  <Box color="text-body-secondary">{i.affected_area}</Box>
                </div>
              ))}
            </SpaceBetween>
          ) : (
            <Box color="text-body-secondary">{loading ? 'Loading…' : 'No active incidents.'}</Box>
          )}
        </Container>
        <Alert type="warning">
          Prototype only. This is not an emergency dispatch or official alert system, and SMS depends on cellular service. Urgency flags are not medical
          diagnoses.
        </Alert>
      </SpaceBetween>
    </ContentLayout>
  )
}
