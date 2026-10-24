# =============================================================================
# In-process ledger double for deterministic unit tests
#
# Models the small claim/finish/consume interface expected by MessagingService.
# It is not a DynamoDB emulator, is not thread-safe, and cannot prove AWS atomicity
# or durability. Fresh instances isolate tests and avoid all database calls.
# Runtime code imports DynamoStore; only tests import this file. SAM excludes the
# entire tests/ directory because deployment CodeUri is src/.
# =============================================================================
"""Test-only ledger; never included in Lambda's src/ deployment package."""
from copy import deepcopy

from app.store import QuotaExceeded


class MemoryStore:
    def __init__(self):
        # Keep message outcomes and quota counters separate, as distinct namespaces
        # within DynamoDB do in production. Nothing persists between test instances.
        self.items = {}
        self.counts = {}

    def claim(self, key, fingerprint):
        # Match the adapter contract: None reserves new work; a dict means duplicate.
        if key in self.items:
            # Copy so service/test mutations cannot silently alter stored state.
            return deepcopy(self.items[key])
        self.items[key] = {'fingerprint': fingerprint, 'status': 'PROCESSING'}
        return None

    def finish(self, key, status, result):
        # Preserve the fingerprint so subsequent requests still detect ID misuse.
        self.items[key].update(status=status, result=result)

    def consume(self, bucket, limit):
        # Check before incrementing. Tests rely on the same boundary as DynamoDB's
        # conditional update, but concurrency is only verified in real AWS testing.
        if self.counts.get(bucket, 0) >= limit:
            raise QuotaExceeded()
        self.counts[bucket] = self.counts.get(bucket, 0) + 1
