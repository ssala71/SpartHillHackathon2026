# Requirements — Disaster Request Processing and Matching

## Introduction

This feature processes free-form disaster-related messages from people in need and
matches them to verified relief resources. An incoming natural-language message is
analyzed with Amazon Bedrock to extract structured intent (needs, location, people
count, urgency). The system then classifies the request as **normal** or **urgent**,
and routes it accordingly:

- **Normal requests** are matched to the nearest open, verified resource that has
  available inventory.
- **Urgent or medical requests** are escalated to a human by creating a
  delivery-review task — the system never auto-promises a resource for these.
- **Incomplete requests** (missing location or need) trigger a clarifying follow-up
  question.
- When nothing suitable and verified exists, the system returns **no_match**.

A hard safety constraint governs the whole feature: the system must **never invent**
resources, availability, locations, or delivery confirmations. All matched data must
trace to a verified resource record.

## Glossary

- **Need**: A requested resource category (e.g., `water`, `food`, `shelter`, `medical`, `baby_formula`).
- **Verified resource**: A resource record whose `verified` flag is `true`, set by an
  authorized operator, not by the model.
- **Open resource**: A resource whose `status` is `open` and whose operating hours
  currently include the request time.
- **Urgent request**: A request flagged urgent by the model's urgency indicators OR
  whose need category is medical/life-safety.
- **Delivery-review task**: A human task record created for urgent/medical requests
  so a person confirms or arranges delivery.

## Requirements

### Requirement 1 — Structured extraction via Amazon Bedrock

**User Story:** As a relief coordinator, I want incoming messages parsed into
structured fields, so that downstream matching is deterministic and auditable.

#### Acceptance Criteria

1. WHEN a message is received THEN the system SHALL invoke Amazon Bedrock to extract
   `needs`, `location`, `people_count`, and `urgency_indicators`.
2. WHEN Bedrock returns a response THEN the system SHALL validate it against the
   structured Bedrock output schema BEFORE using it.
3. IF a field cannot be determined from the message THEN the system SHALL set that
   field to `null` (or an empty list for list fields) rather than guessing a value.
4. WHEN extraction produces a location or need value THEN that value SHALL be derived
   only from the message content and SHALL NOT be fabricated.

### Requirement 2 — Normal vs. urgent classification

**User Story:** As a coordinator, I want each request classified by urgency, so that
life-safety cases get human attention.

#### Acceptance Criteria

1. WHEN extraction completes THEN the system SHALL classify the request as `normal` or
   `urgent`.
2. IF the extracted need is a medical/life-safety category THEN the system SHALL
   classify the request as `urgent` regardless of other signals.
3. IF `urgency_indicators` contains any high-severity signal (e.g., injury, trapped,
   no water for days, infant/elderly at risk) THEN the system SHALL classify the
   request as `urgent`.
4. WHEN neither medical need nor high-severity signals are present THEN the system
   SHALL classify the request as `normal`.

### Requirement 3 — Clarifying follow-up for incomplete requests

**User Story:** As a requester, I want to be asked for missing details, so that I can
receive help without starting over.

#### Acceptance Criteria

1. IF the extracted `location` is missing AND/OR `needs` is empty THEN the system SHALL
   return outcome `follow_up` with a specific clarifying question.
2. WHEN a follow-up is returned THEN the system SHALL NOT perform matching or create a
   delivery-review task.
3. WHEN only one field is missing THEN the follow-up question SHALL ask only for that
   missing field.

### Requirement 4 — Normal request matching

**User Story:** As a requester with a routine need, I want the nearest available
verified resource, so that I can get help quickly.

#### Acceptance Criteria

1. WHEN a request is classified `normal` AND location and needs are present THEN the
   system SHALL search resources where `verified == true` AND `status == open` AND
   operating hours include the request time AND `inventory[need].available > 0`.
2. WHEN one or more candidate resources match THEN the system SHALL select the one with
   the smallest geographic distance to the request location and return outcome
   `matched`.
3. WHEN no verified, open, in-stock resource matches THEN the system SHALL return
   outcome `no_match`.
4. WHEN a `matched` result is returned THEN every field SHALL be copied from the
   selected verified resource record and SHALL NOT be fabricated.

### Requirement 5 — Urgent / medical delivery review

**User Story:** As a coordinator, I want urgent cases routed to a human, so that no
system promises a delivery it cannot guarantee for a life-safety case.

#### Acceptance Criteria

1. WHEN a request is classified `urgent` THEN the system SHALL return outcome
   `delivery_review` and create a delivery-review task instead of a direct match.
2. WHEN a delivery-review task is created THEN it SHALL include the extracted needs,
   location, people count, urgency indicators, and (if any) candidate resource
   references for the human to evaluate.
3. WHEN outcome is `delivery_review` THEN the system SHALL NOT state or imply that a
   resource or delivery is confirmed.

### Requirement 6 — No fabrication safety constraint

**User Story:** As a requester, I want to trust that any promised help is real, so that
I don't travel to a resource that doesn't exist.

#### Acceptance Criteria

1. The system SHALL NEVER output a resource, inventory availability, location, or
   delivery confirmation that is not present in a verified resource record.
2. IF the model output references a resource not found in the verified resource store
   THEN the system SHALL discard that reference and treat it as `no_match`.
3. The system SHALL treat all Bedrock output as untrusted until schema-validated and,
   for resource references, cross-checked against the verified resource store.

### Requirement 7 — Outcome contract

**User Story:** As an integrator, I want a single well-typed result, so that clients
can handle every case.

#### Acceptance Criteria

1. The system SHALL return exactly one outcome per request from the set:
   `matched`, `delivery_review`, `follow_up`, `no_match`.
2. Every outcome SHALL conform to the matching output schema defined in the design.
