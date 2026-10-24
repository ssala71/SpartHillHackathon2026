import Badge from '@cloudscape-design/components/badge'
import StatusIndicator from '@cloudscape-design/components/status-indicator'
import { splitWords } from './format.js'

const URGENCY_COLOR = { Normal: 'grey', Urgent: 'severity-high', Medical: 'severity-critical' }

export function UrgencyBadge({ urgency }) {
  return <Badge color={URGENCY_COLOR[urgency] ?? 'grey'}>{urgency}</Badge>
}

const REQUEST_STATUS = {
  Received: 'pending',
  Processing: 'in-progress',
  NeedsReview: 'warning',
  Matched: 'info',
  Assigned: 'in-progress',
  Completed: 'success',
  Cancelled: 'stopped',
}

export function RequestStatus({ request }) {
  if (request.processing_error) return <StatusIndicator type="error">Processing failed</StatusIndicator>
  return <StatusIndicator type={REQUEST_STATUS[request.status] ?? 'pending'}>{splitWords(request.status)}</StatusIndicator>
}

const GENERIC_STATUS = {
  // incidents
  Draft: 'pending',
  Active: 'success',
  Paused: 'stopped',
  Resolved: 'success',
  Cancelled: 'stopped',
  // resources
  Inactive: 'stopped',
  TemporarilyClosed: 'stopped',
  NeedsVerification: 'warning',
  // inventory
  Available: 'success',
  Low: 'warning',
  OutOfStock: 'error',
  Reserved: 'info',
  // assignments
  Pending: 'pending',
  Accepted: 'success',
  InProgress: 'in-progress',
  Completed: 'success',
  Declined: 'error',
}

export function Status({ value }) {
  return <StatusIndicator type={GENERIC_STATUS[value] ?? 'info'}>{splitWords(value)}</StatusIndicator>
}
