# Design — Disaster Request Processing and Matching

## Overview

A single pipeline turns a free-form disaster message into exactly one typed outcome.
Stages: **ingest → extract (Bedrock) → validate → classify → route → respond**. The
router enforces the no-fabrication constraint: nothing reaches `matched` output unless
it maps to a verified resource record.

```
message ──▶ Ingest ──▶ Bedrock Extract ──▶ Schema Validate
                                               │
                                               ▼
                        (missing location/need?) ──yes──▶ follow_up
                                               │ no
                                               ▼
                                          Classify
                                 ┌────────────┴────────────┐
                               urgent                     normal
                                 │                          │
                                 ▼                          ▼
                          delivery_review            Match (verified,
                          (create task)               open, in-stock)
                                                    ┌──────┴──────┐
                                                 found          none
                                                   │              │
                                                   ▼              ▼
                                               matched         no_match
```

## Architecture

| Component            | Responsibility                                                        |
|----------------------|-----------------------------------------------------------------------|
| `RequestIngestor`    | Accepts and normalizes the input (per **Input Schema**).              |
| `BedrockExtractor`   | Calls Amazon Bedrock; returns raw structured JSON.                    |
| `ExtractionValidator`| Validates Bedrock output against the **Bedrock Output Schema**.       |
| `UrgencyClassifier`  | Produces `normal` / `urgent` per Requirement 2.                       |
| `ResourceStore`      | Read access to **verified** resource records (**Resource Schema**).   |
| `Matcher`            | Filters + ranks candidates; returns nearest valid resource.           |
| `ReviewTaskService`  | Creates delivery-review tasks (**Delivery-Review Output**).           |
| `Responder`          | Assembles the single typed **Matching Output**.                       |

### Bedrock integration

- Model invoked via the Bedrock Runtime `Converse`/`InvokeModel` API with a system
  prompt instructing JSON-only, schema-shaped output and explicit "use null when
  unknown; do not guess" guidance.
- Output is parsed and **strictly validated**; a parse/validation failure is handled
  as an extraction error (retry once, then `follow_up` asking the user to restate).
- The model is never the source of truth for resources. Any `candidate_resource_ids`
  it emits are advisory only and must be cross-checked against `ResourceStore`.

## Data Models

### 1. Input Schema (`DisasterRequestInput`)

```json
{
  "request_id": "string (uuid)",
  "message": "string (raw user text, required, non-empty)",
  "received_at": "string (ISO-8601 datetime)",
  "reported_location": {
    "lat": "number | null",
    "lon": "number | null",
    "text": "string | null"
  },
  "locale": "string | null",
  "channel": "string (sms | web | voice | app) | null"
}
```
Only `message` is required. `reported_location` is an optional caller-supplied hint;
it does not override extraction but may fill a missing location.

### 2. Bedrock Output Schema (`ExtractionResult`)

```json
{
  "needs": [
    {
      "category": "water | food | shelter | medical | baby_formula | power | hygiene | other",
      "raw_text": "string",
      "quantity": "number | null"
    }
  ],
  "location": {
    "text": "string | null",
    "lat": "number | null",
    "lon": "number | null",
    "confidence": "number (0..1)"
  } ,
  "people_count": "integer | null",
  "urgency_indicators": [
    {
      "signal": "string (e.g. 'injured', 'trapped', 'no_water_72h', 'infant_at_risk')",
      "severity": "low | medium | high"
    }
  ],
  "model_notes": "string | null"
}
```
Rules: unknown scalar fields → `null`; unknown lists → `[]`. `needs` and
`urgency_indicators` are arrays (possibly empty). No field may be invented to satisfy
the schema.

### 3. Resource Schema (`Resource`)

```json
{
  "resource_id": "string (uuid)",
  "name": "string",
  "verified": "boolean",
  "verified_by": "string (operator id) | null",
  "status": "open | closed | full",
  "location": { "lat": "number", "lon": "number", "address": "string" },
  "operating_hours": [
    { "day": "mon|tue|wed|thu|fri|sat|sun", "open": "HH:MM", "close": "HH:MM" }
  ],
  "inventory": {
    "<category>": { "available": "integer >= 0", "unit": "string", "updated_at": "ISO-8601" }
  },
  "handles_medical": "boolean",
  "contact": { "phone": "string | null", "notes": "string | null" }
}
```
A record is **eligible for normal matching** only when `verified == true`,
`status == open`, current time ∈ `operating_hours`, and
`inventory[need].available > 0`.

### 4. Matching Output Schema (`MatchingOutcome`) — the single result contract

```json
{
  "request_id": "string (uuid)",
  "outcome": "matched | delivery_review | follow_up | no_match",
  "classification": "normal | urgent",
  "extraction": { "...": "ExtractionResult (echoed for audit)" },

  "match": {
    "resource_id": "string",
    "name": "string",
    "distance_km": "number",
    "matched_needs": ["string"],
    "location": { "lat": "number", "lon": "number", "address": "string" },
    "contact": { "phone": "string | null", "notes": "string | null" }
  },

  "follow_up": {
    "question": "string",
    "missing_fields": ["location" | "needs"]
  },

  "delivery_review_task_id": "string | null",

  "no_match_reason": "string | null",

  "disclaimer": "string (present when outcome != matched; e.g. 'Not a delivery confirmation.')"
}
```
Exactly one of `match`, `follow_up`, `delivery_review_task_id`, or `no_match_reason`
is populated, keyed by `outcome`. Every field in `match` is copied verbatim from the
selected verified `Resource` — never model-generated.

### 5. Urgent Delivery-Review Output (`DeliveryReviewTask`)

```json
{
  "task_id": "string (uuid)",
  "request_id": "string (uuid)",
  "created_at": "ISO-8601",
  "status": "pending_review",
  "priority": "urgent",
  "reason": "medical | high_severity_urgency",
  "needs": ["ExtractionResult.needs[]"],
  "location": { "text": "string | null", "lat": "number | null", "lon": "number | null" },
  "people_count": "integer | null",
  "urgency_indicators": ["ExtractionResult.urgency_indicators[]"],
  "candidate_resource_ids": ["string (verified resources only, advisory)"],
  "assigned_to": "string | null",
  "note_to_reviewer": "string (must NOT confirm any delivery)"
}
```
`candidate_resource_ids` may contain only IDs that exist in `ResourceStore` and are
`verified`. The task explicitly carries no delivery confirmation.

## Matching Algorithm

1. Build candidate set = resources where `verified && status==open && in-hours && inventory[need].available > 0` for at least one requested need.
2. If empty → `no_match` (reason: no verified open in-stock resource).
3. Else compute haversine distance from request location to each candidate.
4. Select minimum distance; on tie, prefer the resource covering the most requested needs, then most recent `inventory.updated_at`.
5. Build `match` purely from the selected record.

## Error Handling

- **Bedrock parse/validation failure**: retry once; on second failure return
  `follow_up` asking the user to restate their need and location.
- **Model references unknown resource**: drop the reference; never surfaces in output.
- **No location coordinates but text present**: geocode via verified geocoder; if
  geocoding fails, treat location as missing → `follow_up`.
- **Resource store unavailable**: fail closed → `no_match` with reason
  `resource_store_unavailable` (never a fabricated match).

## Testing Strategy

Unit-test each component in isolation with a mocked Bedrock client and an in-memory
`ResourceStore`. Integration-test the four outcomes end-to-end (see `tasks.md`
acceptance tests). Bedrock output is always fed through `ExtractionValidator` in tests
to assert the no-fabrication guarantees.
