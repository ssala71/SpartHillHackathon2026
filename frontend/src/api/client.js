// Single entry point for all data the dashboard reads or changes.
// Set VITE_API_BASE_URL (for example http://127.0.0.1:8000) to call the
// FastAPI backend. Without it, everything runs against an in-memory mock.
import * as seed from './mockData.js'
import { suggestMatch } from './matching.js'
import { composeReply, extract, locationReply, MODEL_ID } from './mockBedrock.js'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
export const USING_MOCK = !API_BASE_URL

// ---------- Real backend ----------

async function http(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  // Backend responses use ApiResponse: { data, error }
  const payload = await response.json().catch(() => null)
  if (!response.ok || payload?.error) {
    throw new Error(payload?.error?.message ?? `Request failed (${response.status})`)
  }
  return payload?.data ?? payload
}

const realApi = {
  listIncidents: () => http('/incidents'),
  createIncident: (incident) => http('/incidents', { method: 'POST', body: incident }),
  updateIncident: (id, patch) => http(`/incidents/${id}`, { method: 'PATCH', body: patch }),
  sendAlert: (id) => http(`/incidents/${id}/alert`, { method: 'POST' }),
  listRequests: () => http('/requests'),
  receiveSms: (from, body) => http('/sms/simulate', { method: 'POST', body: { from, body } }),
  processRequest: (id, options = {}) => http(`/requests/${id}/process`, { method: 'POST', body: options }),
  approveMatch: (id) => http(`/requests/${id}/approve`, { method: 'POST' }),
  sendFollowUp: (id) => http(`/requests/${id}/follow-up`, { method: 'POST' }),
  updateRequest: (id, patch) => http(`/requests/${id}`, { method: 'PATCH', body: patch }),
  listResources: () => http('/resources'),
  listInventory: () => http('/inventory'),
  updateInventoryItem: (id, patch) => http(`/inventory/${id}`, { method: 'PATCH', body: patch }),
  listAssignments: () => http('/assignments'),
  createAssignment: (assignment) => http('/assignments', { method: 'POST', body: assignment }),
  updateAssignment: (id, patch) => http(`/assignments/${id}`, { method: 'PATCH', body: patch }),
}

// ---------- In-memory mock ----------

const delay = (ms = 300) => new Promise((resolve) => setTimeout(resolve, ms))
const now = () => new Date().toISOString()
const shift = (iso, seconds) => new Date(new Date(iso).getTime() + seconds * 1000).toISOString()
const newId = (prefix) => `${prefix}-${Math.random().toString(36).slice(2, 8)}`

const db = {
  incidents: structuredClone(seed.incidents),
  requests: [],
  resources: structuredClone(seed.resources),
  inventory: structuredClone(seed.inventoryItems),
  assignments: structuredClone(seed.assignments),
  optedOut: new Set(),
}

const match = (request) => suggestMatch(request, db.resources, db.inventory)

// Give seed requests the same history a live request would have.
for (const original of structuredClone(seed.requests)) {
  const request = { ...original, messages: [], events: [] }
  const t = request.created_at
  request.messages.push({ direction: 'in', body: request.message, at: t })
  request.events.push({ label: 'SMS received', at: t }, { label: 'Saved before processing', at: shift(t, 1) })
  if (request.processing_error) {
    request.events.push({ label: 'Bedrock extraction failed', detail: request.processing_error, at: shift(t, 11), error: true })
  } else {
    const { extraction } = extract(request.message)
    request.extraction = extraction
    request.language = extraction.language
    request.events.push({ label: 'Bedrock extracted fields', detail: `${extraction.latency_ms} ms, ${MODEL_ID}`, at: shift(t, 2) })
    const m = match(request)
    request.events.push({ label: 'Matched against verified resources', detail: m.resource_name ?? m.reason, at: shift(t, 3) })
    request.messages.push({ direction: 'out', body: composeReply(request, m, request.language), at: shift(t, 4) })
    request.events.push({ label: 'Reply sent', at: shift(t, 4) })
  }
  db.requests.push(request)
}

function findRequest(id) {
  const request = db.requests.find((item) => item.id === id)
  if (!request) throw new Error(`Request ${id} not found`)
  return request
}

function patchRecord(table, id, patch) {
  const record = db[table].find((item) => item.id === id)
  if (!record) throw new Error(`Record ${id} not found`)
  Object.assign(record, patch, { updated_at: now() })
  return structuredClone(record)
}

function log(request, label, detail, error = false) {
  request.events.push({ label, detail, at: now(), error })
}

function sendSms(request, body) {
  request.messages.push({ direction: 'out', body, at: now() })
  log(request, 'Reply sent')
}

function withMatch(request) {
  return structuredClone({ ...request, suggested_match: match(request) })
}

const OPEN = (r) => !['Completed', 'Cancelled'].includes(r.status)

const mockApi = {
  async listIncidents() {
    await delay()
    return structuredClone(db.incidents)
  },
  async createIncident(incident) {
    await delay()
    const record = { id: newId('inc'), status: 'Draft', created_at: now(), updated_at: now(), ...incident }
    db.incidents.unshift(record)
    return structuredClone(record)
  },
  async updateIncident(id, patch) {
    await delay()
    return patchRecord('incidents', id, patch)
  },
  async sendAlert(id) {
    await delay(600)
    const incident = db.incidents.find((item) => item.id === id)
    if (!incident?.alert_text) throw new Error('Add alert text before sending.')
    return patchRecord('incidents', id, { status: 'Active' })
  },
  async listRequests() {
    await delay()
    return db.requests.map(withMatch)
  },

  // An inbound text. It is saved first, before any AI processing.
  async receiveSms(from, body) {
    await delay(200)
    if (/^\s*(stop|unsubscribe|cancel)\s*$/i.test(body)) {
      db.optedOut.add(from)
      return { reply: "You're unsubscribed and won't get more alerts. Reply START to resubscribe." }
    }
    db.optedOut.delete(from)

    // A reply to a follow-up question joins the open request instead of starting a new one.
    const waiting = db.requests.find((r) => r.source_phone === from && OPEN(r) && match(r).next_action === 'Ask follow-up question')
    if (waiting) {
      waiting.messages.push({ direction: 'in', body, at: now() })
      waiting.message = `${waiting.message} ${body}`
      waiting.status = 'Received'
      log(waiting, 'Follow-up answer received')
      return withMatch(waiting)
    }

    const request = {
      id: newId('req'),
      incident_id: db.incidents.find((i) => i.status === 'Active')?.id ?? null,
      source_phone: from,
      message: body,
      location_description: null,
      latitude: null,
      longitude: null,
      needs: [],
      people_count: null,
      urgency: 'Normal',
      status: 'Received',
      processing_error: null,
      messages: [{ direction: 'in', body, at: now() }],
      events: [],
      created_at: now(),
      updated_at: now(),
    }
    log(request, 'SMS received')
    log(request, 'Saved before processing')
    db.requests.unshift(request)
    return withMatch(request)
  },

  // Bedrock extraction, then rule-based matching, then the reply.
  async processRequest(id, { simulateFailure = false } = {}) {
    const request = findRequest(id)
    Object.assign(request, { status: 'Processing', processing_error: null })
    await delay(1200)
    if (simulateFailure) {
      request.processing_error = 'Bedrock request timed out after 10s'
      log(request, 'Bedrock extraction failed', request.processing_error, true)
      return withMatch(request)
    }
    const { fields, extraction } = extract(request.message)
    Object.assign(request, fields, { extraction, language: extraction.language })
    log(request, 'Bedrock extracted fields', `${extraction.latency_ms} ms, ${MODEL_ID}`)
    const m = match(request)
    log(request, 'Matched against verified resources', m.resource_name ?? m.reason)
    request.status = request.urgency === 'Normal' && m.resource_id ? 'Matched' : 'NeedsReview'
    request.updated_at = now()
    sendSms(request, composeReply(request, m, request.language))
    return withMatch(request)
  },

  async approveMatch(id) {
    await delay()
    const request = findRequest(id)
    const m = match(request)
    if (!m.resource_id) throw new Error('There is no match to approve.')
    request.status = 'Matched'
    log(request, 'Coordinator approved match', m.resource_name)
    sendSms(request, locationReply(m, m.covered_needs, request.language))
    return withMatch(request)
  },

  async sendFollowUp(id) {
    await delay()
    const request = findRequest(id)
    sendSms(request, composeReply(request, match(request), request.language))
    return withMatch(request)
  },

  async updateRequest(id, patch) {
    await delay()
    const request = findRequest(id)
    if (patch.status && patch.status !== request.status) log(request, `Status set to ${patch.status} by coordinator`)
    return withMatch(Object.assign(request, patch, { updated_at: now() }))
  },
  async listResources() {
    await delay()
    return structuredClone(db.resources)
  },
  async listInventory() {
    await delay()
    return structuredClone(db.inventory)
  },
  async updateInventoryItem(id, patch) {
    await delay()
    if (patch.quantity !== undefined) {
      if (patch.quantity < 0) throw new Error('Quantity cannot be negative.')
      if (patch.status === undefined) {
        patch.status = patch.quantity === 0 ? 'OutOfStock' : patch.quantity < 10 ? 'Low' : 'Available'
      }
    }
    return patchRecord('inventory', id, patch)
  },
  async listAssignments() {
    await delay()
    return structuredClone(db.assignments)
  },
  async createAssignment(assignment) {
    await delay()
    if (db.assignments.some((item) => item.request_id === assignment.request_id && !['Declined', 'Cancelled'].includes(item.status))) {
      throw new Error('This request already has an active assignment.')
    }
    const record = { id: newId('asg'), status: 'Pending', created_at: now(), updated_at: now(), ...assignment }
    db.assignments.unshift(record)
    const request = findRequest(assignment.request_id)
    request.status = 'Assigned'
    log(request, 'Delivery assignment created', 'Waiting for someone to accept')
    return structuredClone(record)
  },
  async updateAssignment(id, patch) {
    await delay()
    // notify: false is used by Undo, so reverting a step never re-texts the requester.
    const { notify = true, ...changes } = patch
    const record = patchRecord('assignments', id, changes)
    const request = findRequest(record.request_id)
    const es = request.language === 'es'
    log(request, `Assignment ${patch.status}`)
    if (patch.status === 'Completed') request.status = 'Completed'
    else if (['Declined', 'Cancelled'].includes(patch.status)) request.status = 'NeedsReview'
    else request.status = 'Assigned'
    if (!notify) return record
    // Delivery is only promised to the requester once someone has accepted it.
    if (patch.status === 'Accepted') {
      sendSms(request, es ? 'Un voluntario aceptó su entrega. Le avisaremos cuando salga.' : 'A volunteer has accepted your delivery. We will text you when they are on the way.')
    }
    if (patch.status === 'InProgress') sendSms(request, es ? 'Su entrega va en camino.' : 'Your delivery is on the way.')
    return record
  },
}

export const api = USING_MOCK ? mockApi : realApi
