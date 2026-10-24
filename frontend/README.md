# Waypoint coordinator dashboard (frontend)

React 19 + Vite. The admin console uses [Cloudscape](https://cloudscape.design), AWS's open-source design system,
themed white and dark blue in `src/theme.js`. The public demo and the shared top bar use Tailwind CSS v4 with the
same color tokens (`src/index.css`). Tailwind's preflight reset is left out so it never changes Cloudscape's styles.
Light and dark mode follow the system and can be toggled from the top bar; the Demo/Admin switch sits beside it.

## Run it

```bash
cd frontend
pnpm install
pnpm dev          # open the URL it prints, e.g. http://localhost:5173
```

With no configuration the dashboard runs on **simulated demo data** held in memory
(`src/api/mockData.js`). Refreshing the page resets it.

To also show the **real SMS requests** from the Waypoint backend (see `california-sms/README.md`,
"Optional: connect to the Waypoint backend"), start the dev server with the backend's address:

```bash
VITE_BACKEND_URL=http://127.0.0.1:8001 pnpm dev
```

The admin's Live dot turns green. Each phone number's conversation appears at the top of Requests with the
backend's Bedrock fields and matcher result, refreshed every 5 seconds. Changing a status saves it to the
backend. Incidents, resources, inventory, and assignments stay on demo data because the backend has no
routes for them yet. The dev server forwards `/api` to the backend, so no CORS setup is needed. The
hosted site cannot reach a laptop, so this works only with `pnpm dev`.

Other commands: `pnpm build`, `pnpm lint`, `pnpm preview`.

## Pages

**Public demo** (`#/`): a phone on screen. Text as a resident (or as Maria, or in Spanish) or tap a sample message, and watch it move
through Received, Saved, Bedrock, Matched, Replied. A side card shows what Waypoint understood and the result.
"Simulate a Bedrock failure" shows the saved message being retried.

**Admin** (`#/admin`), the coordinator console:

| Page | What it does |
| --- | --- |
| Overview | Counts that need attention and active incidents |
| Requests | Queue sorted by urgency. Open one for the SMS thread, Bedrock fields, suggested match, timeline, and actions (approve, retry, assign, cancel) |
| Incidents and alerts | Create an incident, write and send the SMS alert, resolve it |
| Resources and inventory | Resource status and verification time; click a quantity to edit stock |
| Assignments | Pending → Accepted → In progress → Delivered |
| How it works | The AWS pipeline and decision rules |

## Code layout

```
src/
  api/client.js       all data access; mock vs real backend switch
  api/mockData.js     simulated incidents, requests, resources, inventory, assignments
  api/matching.js     mock-only matching so inventory edits change matches
  api/mockBedrock.js  mock-only keyword extractor + SMS reply rules (stand-in for Bedrock)
  hooks/DataContext.jsx  loads everything; run(action, message, undo) for changes, toasts and Undo
  components/         TopBar (shared header), PipelineTracker, SMS thread, status badges, formatting helpers
  pages/              DemoPage.jsx (public) and the admin pages; RequestDetail.jsx is the side panel
  theme.js            Cloudscape theme and light/dark mode
  index.css           Tailwind setup, color tokens for both modes, shared SMS and timeline styles
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
