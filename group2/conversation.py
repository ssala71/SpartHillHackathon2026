"""
Conversation layer — ties the pieces together per phone number.

Responsibilities:
  - Keep a partial StructuredRequest per phone (in-memory here; Group 1 will
    back this with DynamoDB so it survives restarts).
  - Merge each incoming SMS into the request (only fill fields that are still
    blank, so a later vague message can't wipe earlier good data).
  - If anything is still missing, build ONE follow-up message asking for all
    the missing fields at once.
  - When complete, hand off to matching.

The 'reliability' story lives here too: handle_message stores the raw text
first, and if extraction fails the request stays visible (status FAILED)
rather than being lost.
"""

from __future__ import annotations

from dataclasses import dataclass

from schema import StructuredRequest, RequestStatus, Urgency, Category, DeliveryMode
from extract import extract_fields, ExtractionError


# Human-readable prompts for each missing field, combined into one message.
_FIELD_PROMPTS = {
    "category": "what you need (food, medicine, or other)",
    "address": "your location (a cross street or landmark)",
    "urgency": "how urgent it is (reply high, medium, or low)",
    "people_count": "how many people need assistance",
    "delivery_mode": "whether you need the medicine delivered or can collect it "
                     "(reply deliver or collect)",
}


@dataclass
class TurnResult:
    """What handle_message returns to the backend/SMS layer."""
    request: StructuredRequest
    status: str                 # RequestStatus value
    reply_text: str | None      # SMS to send back, or None if nothing to say
    complete: bool


class ConversationStore:
    """In-memory per-phone sessions. Swap for DynamoDB in Group 1's backend."""

    def __init__(self):
        self._sessions: dict[str, StructuredRequest] = {}

    def get(self, phone: str) -> StructuredRequest:
        if phone not in self._sessions:
            self._sessions[phone] = StructuredRequest(phone=phone)
        return self._sessions[phone]

    def reset(self, phone: str) -> None:
        self._sessions.pop(phone, None)


def handle_message(store: ConversationStore, phone: str, text: str) -> TurnResult:
    """Process one inbound SMS and decide what to say back."""
    req = store.get(phone)
    req.raw_messages.append(text)  # reliability: record the raw text first

    try:
        fields = extract_fields(text)
    except ExtractionError as e:
        # Request stays visible for retry; we don't lose what we already had.
        return TurnResult(
            request=req,
            status=RequestStatus.FAILED.value,
            reply_text=("Sorry, we couldn't read that. Please resend what you "
                        "need, your location, how many people, and urgency."),
            complete=False,
        )

    _merge(req, fields)
    if fields.get("model_notes"):
        req.model_notes = fields["model_notes"]

    missing = req.missing_fields()
    if missing:
        return TurnResult(
            request=req,
            status=RequestStatus.GATHERING.value,
            reply_text=_build_follow_up(missing),
            complete=False,
        )

    # All four fields gathered.
    return TurnResult(
        request=req,
        status=RequestStatus.COMPLETE.value,
        reply_text=None,   # backend proceeds to matching and sends the result
        complete=True,
    )


def _merge(req: StructuredRequest, fields: dict) -> None:
    """Fill only blank fields, so a later message can't erase good earlier data."""
    if not req.category and fields.get("category"):
        req.category = fields["category"]
    if not req.address and fields.get("address"):
        req.address = fields["address"]
    if req.urgency == Urgency.UNKNOWN.value and fields.get("urgency"):
        req.urgency = fields["urgency"]
    if req.people_count is None and fields.get("people_count") is not None:
        req.people_count = fields["people_count"]
    if req.delivery_mode == DeliveryMode.UNKNOWN.value and fields.get("delivery_mode"):
        req.delivery_mode = fields["delivery_mode"]


def _build_follow_up(missing: list[str]) -> str:
    """One message asking for everything still missing."""
    parts = [_FIELD_PROMPTS[f] for f in missing if f in _FIELD_PROMPTS]
    if len(parts) == 1:
        body = parts[0]
    else:
        body = ", ".join(parts[:-1]) + ", and " + parts[-1]
    return f"To find help near you, please reply with {body}."
