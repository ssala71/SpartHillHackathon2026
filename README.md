# Waypoint - SMS Disaster Resource Coordinator

**SpartHill Hackathon 2026 | AWS Challenge**

**Team:** Jordan, Samuel, Bhuvana, Hiral, Josh

**Status:** Project plan. Features below are planned, not confirmed as built.

## Overview

An SMS-based service that helps people find essential resources during an outage, disaster, or major disruption.

A coordinator sends an alert to subscribed users in the affected area. Users reply with their needs. Amazon Bedrock converts each message into a structured request, flags possible urgency, and passes it to resource-matching logic.

- **Normal requests:** Point to the nearest suitable verified location.
- **Medical or very urgent requests:** Flag for coordinator review and possible delivery. Only confirm delivery after someone accepts the assignment.

## Example User

Maria, a San José resident during a power outage, texts:

> I'm near Tully Road with my grandmother. We need water and somewhere to charge her medical device.

The system extracts her location and needs, flags the medical-device concern for review, and checks verified resources. The dashboard shows the request, suggested match, and next action.

## How It Works

1. A coordinator starts an incident and sends an SMS alert.
2. A user replies with their needs and location.
3. Bedrock extracts the location, needs, people count if known, and urgency indicators.
4. The application checks resource suitability, distance, operating status, and inventory.
5. It replies with a sourced match or sends the request for human review.
6. The dashboard tracks the request and any confirmed assignment.

| Situation | Response |
| --- | --- |
| Normal request | Send the nearest suitable verified location with availability. |
| Medical or very urgent | Flag for human review; a coordinator decides the next action. |
| Missing location or unclear need | Ask a short follow-up question. |
| No suitable resource or outdated information | Explain the limitation and flag for review. Do not invent a match. |

## Team Roles

### Role 1: AWS Backend and SMS

**Jordan, Samuel**

- Build incoming and outgoing SMS, coordinator-triggered broadcasts, and opt-out handling.
- Build APIs and storage for incidents, requests, resources, inventory, and assignments.
- Connect Role 2's processing and matching logic to SMS and the dashboard.
- Save requests before AI processing.
- Track failures and support retries without duplicate replies or assignments.
- Handle AWS deployment and keep credentials out of the repository.

**Deliverable:** A working alert-to-reply flow that saves requests and makes failures visible for review.

### Role 2: Bedrock, Resources, and Matching

**Bhuvana, Hiral, Josh**

- Use Bedrock to turn messages into validated structured requests.
- Extract needs and urgency indicators; identify missing details.
- Flag unclear or potentially urgent cases for review.
- Define resource records and prepare a small, clearly labeled demo dataset.
- Match requests using verified services, location, operating status, and inventory.
- Return the match, source, verification time, and reason, or an explicit "no match."
- Agree with Role 1 on inventory rules so confirmed allocations cannot exceed stock.

**Deliverable:** Structured requests and suitable resource matches without invented facts or availability.

### Role 3: Frontend, Product, Testing, and Demo

**Everyone**

- Build the coordinator dashboard with incident alerts, incoming requests, urgency flags, resource and inventory views, and status updates.
- Support human review and confirmed delivery assignments.
- Show clear loading, empty, and error states.
- Agree on the persona, feature scope, specifications, and API formats.
- Test individual components and the full connected application.
- Prepare the demo and presentation together.
- Make sure everyone can explain their contribution.

**Deliverable:** A connected, readable dashboard and a tested end-to-end demo.

## Shared Data and Handoffs

Agree on field names and API inputs and outputs before building separately.

| Record | Required information |
| --- | --- |
| Incident | ID, type, affected area, alert text, status, timestamp |
| Request | ID, incident ID, original message, location, needs, people count if known, urgency flag, status |
| Resource | ID, name, location, services, inventory, operating status, source, last-verified time |
| Match or assignment | Request ID, resource ID if matched, reason, next action, status, assigned person if confirmed |

- **Role 1:** Owns storage and APIs.
- **Role 2:** Supplies processing, matching, and resource data.
- **Everyone:** Connects the dashboard through those APIs and tests the full flow.

## Challenge Requirements

- **Critical service:** Keep access to essential-resource information and coordination running during disruptions.
- **Working application:** Demonstrate the actual connected flow, not just screens.
- **AWS first:** Use AWS primarily, with Bedrock doing meaningful request-processing work.
- **Spec coding:** Write requirements and acceptance tests before coding. Use Kiro credits and steering files where available.
- **Judging:** Show a genuine user need, accurate information, reliability, polish, and understanding of what we built.
- **Going beyond:** Demonstrate recovery from a failed processing step before adding extra features.

## Build Order

1. Agree on the scenario, data formats, API contracts, and a small resource dataset.
2. Confirm AWS and Bedrock access and SMS setup early.
3. Complete one connected alert, reply, processing, matching, and dashboard flow.
4. Test failures and polish the demo.
5. Add optional features only after the core flow works.

## Collaboration

- Use one shared repository and separate branches for tasks.
- Write a short specification before implementing each feature.
- Make focused commits with clear descriptions.
- Review each other's changes and integrate regularly.
- Keep credentials and sensitive information out of commits.
- Add exact setup and run instructions once the implementation exists.

## Reliability and Safety

- Use sourced records with verification times.
- Clearly label simulated data and demo steps.
- Bedrock interprets messages; verified data and application rules determine matches.
- Urgency flags are not medical diagnoses or final triage decisions.
- Keep failed requests visible for retry or manual review.
- Only confirm delivery after someone accepts the assignment.
- Protect phone numbers and sensitive information.
- This is a prototype, not emergency dispatch or an official alert system.
- SMS depends on cellular service. Do not claim guaranteed availability.

## Demo Checklist

- [ ] Send an alert to a subscribed test number and receive a reply.
- [ ] Process the reply through Bedrock and show it on the dashboard.
- [ ] Match a normal request to a sourced resource.
- [ ] Flag an urgent request for human review.
- [ ] Show an inventory update changing a match.
- [ ] Ask a follow-up question for an unclear message.
- [ ] Handle a request with no suitable resource.
- [ ] Show a failed processing step remaining available for retry.
- [ ] Display sources, verification times, and clear request statuses.

## Optional Features

Add these only after the core flow works:

- Weather reports with sources and timestamps.
- More resource categories beyond food and shelters.
- Travel or delivery estimates, clearly labeled as estimates.
- Food-distribution and expiry tracking. Only claim food waste prevented if we can measure it.

## Local Development

The backend and frontend use separate environments. Do not commit virtual environments, frontend dependencies, build output, IDE settings, or local `.env` files.

### Prerequisites

- Python 3.13
- Node.js and pnpm
- Access to the AWS RDS PostgreSQL database for backend work

### Backend setup

From the repository root, enter the backend directory:

```bash
cd backend
```

On Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS or Linux:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and set the RDS connection string:

```env
DATABASE_URL=postgresql+psycopg://username:password@host:5432/database_name?sslmode=require
```

Start the API from the `backend` directory on any operating system:

```bash
python -m uvicorn app.main:app --reload
```

Run the backend tests:

```bash
python -m pytest
```

The health check is available at `http://127.0.0.1:8000/health`.

### Request persistence API

Request records are saved before any later processing. The original `message`
is stored with the request and the persistence route does not provide a way to
overwrite it. The same normalized phone number produces the same SHA-256
`person_id` for frontend and future SMS submissions.

Available endpoints:

```text
POST  /api/incidents
GET   /api/incidents
GET   /api/incidents/{incident_id}

POST  /api/requests
GET   /api/requests
GET   /api/requests/{request_id}
PATCH /api/requests/{request_id}/status
```

Completed requests remain in the default request list. Status updates require
an `admin_user_id`; authentication and authorization for that ID will be added
in a later configuration/security branch.

### Frontend setup

The React/Vite frontend is maintained on the `frontendReactSetUp` branch. From the repository root after that branch is checked out or merged:

```bash
cd frontend
pnpm install
pnpm dev
```

The Vite development server prints its local URL in the terminal. Other useful commands are:

```bash
pnpm build
pnpm lint
```

Use `python -m ...` for backend tools and `pnpm ...` for frontend tools so the commands work consistently on Windows, macOS, and Linux.
