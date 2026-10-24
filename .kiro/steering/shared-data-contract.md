---
inclusion: always
---

# Shared Data Contract — SMS Disaster Resource Coordinator

Single source of truth for the data shapes passed between the three groups.
Do not change a field without telling the whole team. Canonical definitions
live in `group2/schema.py`.

## The flow
1. Person in need texts freeform: "I need xyz".
2. Group 2 classifies the **category**: `food` / `medicine` / `other`.
3. Group 2 gathers the required fields. If any are missing, ONE follow-up
   SMS asks for all of them at once:
   - `category`, `address`, `urgency` (high/medium/low), `people_count`
   - PLUS `delivery_mode` (deliver/collect) — ONLY when category is `medicine`.
4. When all required fields are gathered, Group 2 matches to the nearest
   available place that serves the category and has capacity for the group.

## Ownership
- **Group 1** (Backend/SMS): stores records, exposes APIs, passes each inbound
  SMS string + phone into Group 2's `handle_message`. Backs the conversation
  store with DynamoDB.
- **Group 2** (Bedrock/Matching): classifies, gathers fields, produces
  `StructuredRequest` and `MatchResult`.
- **Group 3** (Dashboard): reads these shapes to render the UI.

## Records (minimum fields)

### Incident (Group 1 owns)
`id, type, affected_area, alert_text, status, timestamp`

### Request (StructuredRequest)
`phone, raw_messages[], category, address, urgency, people_count,
delivery_mode, model_notes`
- `category` ∈ {`food`, `medicine`, `other`}
- `urgency` ∈ {`high`, `medium`, `low`, `unknown`} (`unknown` = not yet given)
- `delivery_mode` ∈ {`deliver`, `collect`, `unknown`} — only required/used for
  medicine requests; stays `unknown` for food/other.
- `status` ∈ {`received`,`gathering`,`complete`,`needs_review`,`matched`,`no_match`,`failed`}

### Resource
`id, name, location_text, lat?, lon?, categories[], capacity, operating_status,
source, last_verified, is_simulated`
- `source` and `last_verified` are REQUIRED — they are the trust story.
- `capacity` = how many people the place can currently take.

### Match / Assignment (MatchResult)
`phone, matched, resource_id?, resource_name?, reason, action, source?,
last_verified?, is_simulated?, limitation_note?`
- `action` ∈ {`direct_to_location`,`review_queue`,`follow_up`,`no_action`}

## Non-negotiable rules (tie directly to judging)
1. **Save the inbound message before AI runs.** `handle_message` records the
   raw text first. If Bedrock fails, status becomes `failed` and the request
   stays visible for retry. Never lose the original message.
2. **Never invent availability.** Match only against records that serve the
   category, are not closed, and have `capacity >= people_count`. Otherwise an
   honest no-match.
3. **Medicine category OR high urgency → human review.** No automatic dispatch.
   Delivery is only confirmed after a coordinator accepts it.
4. **Medicine → ask delivery mode.** Every medicine request (any urgency) asks
   whether the person needs delivery or can collect, so the coordinator knows
   what response to arrange.
5. **Missing info → one combined follow-up question**, not a guess.
6. **Keep AI interpretation separate from resource facts.** Bedrock interprets
   the message only; availability comes from verified records.
7. **Label simulated data** (`is_simulated: true`) and always show `source`
   and `last_verified` in the UI.

## Where Group 2 sits
```
SMS in (phone, text) → Group1 saves raw → Group2 handle_message()
  → merges into StructuredRequest → if missing, one follow-up SMS
  → when complete, match_request() → MatchResult
  → Group1 stores + sends SMS reply → Group3 renders on dashboard
```

## Integration entry points (what Group 1 calls)
- `conversation.handle_message(store, phone, text) -> TurnResult`
  (`TurnResult` has `.request`, `.status`, `.reply_text`, `.complete`)
- `matching.match_request(request, resources) -> MatchResult`
- `matching.load_resources() -> list[Resource]`
