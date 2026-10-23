# Implementation Plan — Disaster Request Processing and Matching

- [ ] 1. Define data models and schema validators
  - Implement `DisasterRequestInput`, `ExtractionResult`, `Resource`,
    `MatchingOutcome`, and `DeliveryReviewTask` as typed models.
  - Implement a strict validator for `ExtractionResult` (unknown scalars → null,
    unknown lists → []).
  - _Requirements: 1.2, 1.3, 7.2_

- [ ] 2. Implement Bedrock extraction
  - [ ] 2.1 Build `BedrockExtractor` with a JSON-only system prompt and "use null when
    unknown; never guess" guidance.
    - _Requirements: 1.1, 1.4_
  - [ ] 2.2 Wire parse + `ExtractionValidator`; retry once, then fall back to
    `follow_up`.
    - _Requirements: 1.2, 6.3_

- [ ] 3. Implement `UrgencyClassifier`
  - Flag `urgent` for medical/life-safety needs or any high-severity indicator;
    otherwise `normal`.
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 4. Implement completeness check and `follow_up`
  - Detect missing `location` and/or empty `needs`; produce a targeted question for
    only the missing field(s); skip matching and review-task creation.
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 5. Implement `ResourceStore` and `Matcher`
  - [ ] 5.1 Read-only store exposing only `verified` resources.
    - _Requirements: 6.1, 6.2_
  - [ ] 5.2 Filter by verified + open + in-hours + in-stock; rank by haversine distance
    with documented tie-breakers; return nearest or `no_match`.
    - _Requirements: 4.1, 4.2, 4.3_
  - [ ] 5.3 Build `match` strictly from the selected record (no model fields).
    - _Requirements: 4.4, 6.1_

- [ ] 6. Implement `ReviewTaskService` for urgent/medical
  - Create a `DeliveryReviewTask` (status `pending_review`), attach extraction data and
    only verified candidate IDs, and ensure no delivery is confirmed.
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 7. Implement `Responder` and the single-outcome contract
  - Assemble exactly one `MatchingOutcome`; populate exactly one of
    `match` / `follow_up` / `delivery_review_task_id` / `no_match_reason`; add the
    non-confirmation disclaimer for non-matched outcomes.
  - _Requirements: 7.1, 7.2, 6.1_

- [ ] 8. Acceptance tests — four outcomes

  - [ ] 8.1 **Outcome: `matched` (normal request)**
    - GIVEN message "We need drinking water for 3 people in Riverside District"
    - AND a verified, open resource with `water.available > 0` near Riverside, plus a
      farther verified resource also in stock
    - WHEN the pipeline runs
    - THEN `outcome == "matched"`, `classification == "normal"`, the nearer resource is
      selected, and every `match` field equals that verified record (asserting no
      fabricated fields).
    - _Requirements: 2.4, 4.1, 4.2, 4.4, 6.1, 7.1_

  - [ ] 8.2 **Outcome: `delivery_review` (urgent/medical request)**
    - GIVEN message "My father is injured and bleeding, we need medical help now at 5th & Main"
    - WHEN the pipeline runs
    - THEN `outcome == "delivery_review"`, `classification == "urgent"`, a
      `DeliveryReviewTask` is created with `status == "pending_review"` carrying needs,
      location, people count, and urgency indicators, AND the result does NOT confirm
      any resource or delivery (assert disclaimer present, no `match` object).
    - _Requirements: 2.2, 2.3, 5.1, 5.2, 5.3, 7.1_

  - [ ] 8.3 **Outcome: `follow_up` (missing field)**
    - GIVEN message "We need water" (no location)
    - WHEN the pipeline runs
    - THEN `outcome == "follow_up"`, `missing_fields == ["location"]`, the question asks
      only for location, AND no match or review task is produced.
    - _Requirements: 3.1, 3.2, 3.3, 7.1_

  - [ ] 8.4 **Outcome: `no_match` (nothing verified/available)**
    - GIVEN message "We need baby formula in Northgate for 1 infant" classified
      `normal`
    - AND the store contains only unverified, closed, or zero-inventory resources for
      `baby_formula`
    - WHEN the pipeline runs
    - THEN `outcome == "no_match"` with a reason, and NO resource is fabricated or
      returned (assert empty `match`).
    - _Requirements: 4.3, 6.1, 6.2, 7.1_

  - [ ] 8.5 **Safety test: model hallucination is discarded**
    - GIVEN Bedrock output references `candidate_resource_ids` not present in
      `ResourceStore`
    - WHEN the pipeline runs
    - THEN those references are dropped and the outcome falls back to `no_match` (never
      a fabricated `matched`).
    - _Requirements: 6.1, 6.2, 6.3_
