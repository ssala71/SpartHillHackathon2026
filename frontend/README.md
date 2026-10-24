# Waypoint coordinator dashboard (frontend)

React 19 + Vite + [Cloudscape](https://cloudscape.design) (AWS's open-source design system).

## Run it

```bash
cd frontend
pnpm install
pnpm dev          # open the URL it prints, e.g. http://localhost:5173
```

With no configuration the dashboard runs on **simulated demo data** held in memory
(`src/api/mockData.js`). Refreshing the page resets it.

To use the FastAPI backend instead, create `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

and restart `pnpm dev`. The backend also needs CORS enabled for the Vite origin.

Other commands: `pnpm build`, `pnpm lint`, `pnpm preview`.

## Pages

| Page | What it does |
| --- | --- |
| Overview | Counts that need attention, active incidents, prototype disclaimer |
| Requests | SMS requests sorted by urgency, filter by Needs review / Open / All. Click a row for the original SMS, extracted fields, suggested match with source and verification time, and actions: retry failed processing, approve and send location, send follow-up, assign delivery, cancel |
| Incidents and alerts | Create or edit an incident, write the SMS alert (with a 160-character counter), send it, resolve it |
| Resources and inventory | Resource status, services, source, last verified (stale after 4 h). Click an inventory quantity to edit it; matches update on the next load |
| SMS simulator | A phone on screen. Text as a resident (presets for medical, Spanish, unclear, STOP) and watch the message get saved, read by Bedrock, matched, and answered. Can force a Bedrock timeout to show recovery |
| How it works | Pipeline with the AWS service at each step, the decision rules, what Bedrock does and doesn't do, safety limits |
| Assignments | Pending → Accepted → In progress → Delivered, or Declined/Cancelled (which returns the request to review) |

## Code layout

```
src/
  api/client.js       all data access; mock vs real backend switch
  api/mockData.js     simulated incidents, requests, resources, inventory, assignments
  api/matching.js     mock-only matching so inventory edits change matches
  api/mockBedrock.js  mock-only keyword extractor + SMS reply rules (stand-in for Bedrock)
  hooks/DataContext.jsx  loads everything, run(action, message) for changes + toasts
  components/         status badges, formatting helpers
  pages/              one file per page; RequestDetail.jsx is the side panel
```

## API the frontend expects

Field names match `backend/app/api/schemas`. Responses can be the `ApiResponse` shape
(`{ data, error }`) or the bare data.

| Call | Endpoint |
| --- | --- |
| list / create / update incidents | `GET /incidents`, `POST /incidents`, `PATCH /incidents/{id}` |
| send alert | `POST /incidents/{id}/alert` |
| list / update requests | `GET /requests`, `PATCH /requests/{id}` |
| simulate an inbound SMS | `POST /sms/simulate` with `{ from, body }` |
| run or retry Bedrock + matching | `POST /requests/{id}/process` |
| approve match / resend follow-up | `POST /requests/{id}/approve`, `POST /requests/{id}/follow-up` |
| resources, inventory | `GET /resources`, `GET /inventory`, `PATCH /inventory/{id}` |
| assignments | `GET /assignments`, `POST /assignments`, `PATCH /assignments/{id}` |

Fields the dashboard uses that are **not in the backend schemas yet**:

- Request: `latitude`, `longitude`, `processing_error`, `language`, `messages` (`direction`, `body`, `at`),
  `events` (`label`, `detail`, `at`, `error`), `extraction` (`model_id`, `language`, `urgency_indicators`,
  `missing_fields`, `latency_ms`), and `suggested_match`
  (`resource_id`, `resource_name`, `address`, `distance_km`, `reason`, `next_action`, `source`, `last_verified_at`)
- Incident: `alert_text`
- Resource: `services`, `source`, `last_verified_at`
- Assignment: `coordinator_name` exists in the Pydantic schema, but the DB model has `coordinator_user_id`
