---
inclusion: always
---

# Shared Data Contract (Role 2 request format)

One request format for SMS -> Bedrock -> geocoding -> matching -> reply.
Canonical code: `backend/app/api/schemas/ai.py`, `backend/app/resource_matching/adapter.py`.
Do not change a field without telling the whole team.

## Storage
PostgreSQL (SQLAlchemy + Alembic). Run `alembic upgrade head` after pulling;
migration `0002_unified_urgency` converts old urgency values in place.

## Urgency
`low | medium | high` everywhere (API, database, Bedrock prompt, matcher).
Medical is NOT an urgency level: it is `medical_concern: true` (usually with `high`).
Old values are still accepted on input: Normal -> low, Urgent -> high, Medical -> high.

## Bedrock output (`AIProcessingResult`)
| Field | Type | Notes |
|---|---|---|
| needs | list of `water, food, shelter, medical, baby_formula, power, hygiene, other` | synonyms mapped by `normalize_need` (medicine -> medical, charging -> power) |
| urgency | low / medium / high | |
| location | text or null | Bedrock never produces coordinates |
| people_count, household_size | int or null | |
| medical_concern | bool | true -> coordinator review |
| delivery_mode | deliver / collect / null | asked only for medicine |
| missing_information | list | needs, location, people_count, delivery_mode |
| needs_review, summary | bool, text | |

## Stored result adds
`latitude, longitude, location_source` from `app/services/geocoding.py`
(`GEOCODING_PROVIDER=gazetteer` offline demo landmarks, or `aws_location`).

## Matcher input mapping (`adapter.to_extraction`)
needs -> `Need(category)`, lat/lon -> `ExtractedLocation`, urgency -> urgency,
medical_concern or a medical need -> `requires_human_review`.

## Next action (`GET /api/requests/{id}/match` -> `MatchResult.action`)
| action | When | Request status |
|---|---|---|
| not_processed | no AI result yet | unchanged |
| follow_up | any required field missing; ONE SMS asks for all of them (`follow_up_message`) | NeedsReview |
| coordinator_review | medicine (any urgency) or high urgency; nearest stocked place attached as a suggestion only | NeedsReview |
| direct_to_location | verified, open (Pacific time), in-stock place for the need | Matched |
| no_match | nothing qualifies; never invented | NeedsReview |

Inventory rule: a place qualifies only with stock of the requested category
(per-category, not a single capacity number).

## Non-negotiable rules
1. The original message is saved before Bedrock runs and is never overwritten.
2. Failed Bedrock attempts are stored and retryable.
3. Matches come only from sourced, verified records; show `source`, `last_verified_at`, `simulated`.
4. Medicine or high urgency never gets an automatic dispatch; a coordinator decides.
5. Follow-up replies merge into the first message with `adapter.merge_follow_up` (fills blanks only, never lowers urgency).
