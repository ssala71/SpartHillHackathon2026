# =============================================================================
# Message schemas shared by HTTP and SNS handlers
#
# Pydantic validates and parses external input before business logic runs. The
# outgoing schema is strict because it is our public API contract; incoming SNS
# messages may include AWS fields this application does not need. These schemas
# check structure only: service.py checks allowed recipients, expected destination,
# and nonblank text. Field names for incoming messages match AWS's payload exactly.
# =============================================================================
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OutgoingSMS(BaseModel):
    # Reject misspelled or unexpected API fields instead of silently ignoring them.
    model_config = ConfigDict(extra='forbid')
    # Basic +1 phone formatting is separate from the configured recipient allowlist.
    to: str = Field(pattern=r'^\+1[2-9]\d{2}[2-9]\d{6}$')
    # This is a character limit, not an SMS segment limit or cost estimate.
    body: str = Field(min_length=1, max_length=500)
    # The caller generates this once per intended message and reuses it on retries.
    # UUID parsing rejects malformed identifiers before the DynamoDB claim.
    request_id: UUID


class IncomingSMS(BaseModel):
    # AWS can include additional payload fields.
    # Pydantic's default extra-field behavior ignores them for forward compatibility.
    # The sender is the customer's number; destination is our dedicated AWS number.
    originationNumber: str
    destinationNumber: str
    messageBody: str = Field(min_length=1, max_length=1600)
    # AWS's inbound identifier becomes the idempotency key for the generated reply.
    inboundMessageId: str = Field(min_length=1, max_length=128)
