# =============================================================================
# DynamoDB persistence for duplicate protection and daily attempt quotas
#
# One table stores message records (in:/out: keys) and quota counters (quota: keys).
# Conditional writes arbitrate new requests and quota increments across concurrent
# Lambda invocations. The state is durable and shared; there is no runtime cache
# standing in for DynamoDB. TTL requests eventual cleanup, not exact-time deletion.
# This ledger cannot atomically commit an external SMS send and a database write,
# so callers must retain the review-required policy for uncertain sends.
# =============================================================================
"""Small idempotency ledger. Records contain hashes/status, not SMS content."""
import time

from botocore.exceptions import ClientError


class QuotaExceeded(Exception):
    # Translate the counter's expected conditional failure into a domain exception.
    # Permission errors, throttling, and other DynamoDB failures must stay distinct.
    pass


class DynamoStore:
    # Accept a Boto3 Table resource rather than constructing it here. That keeps
    # region/table selection centralized in service() and makes adapter tests small.
    def __init__(self, table):
        self.table = table

    def claim(self, key, fingerprint):
        # Return None only when this invocation successfully reserves new work.
        # A concurrent caller with the same key gets the existing record instead.
        try:
            self.table.put_item(
                Item={'pk': key, 'fingerprint': fingerprint, 'status': 'PROCESSING',
                      'expires_at': int(time.time()) + 7 * 86400},
                # Atomic check-and-create prevents two writers claiming one ID.
                ConditionExpression='attribute_not_exists(pk)',
            )
            return None
        except ClientError as error:
            # Do not misinterpret IAM/network/service failures as a duplicate.
            if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
                raise
            item = self.table.get_item(Key={'pk': key}, ConsistentRead=True).get('Item')
            # A strongly consistent read sees the competing writer's committed
            # record. A rare TTL deletion between the put and read must fail closed.
            if item is None:
                raise RuntimeError('Idempotency record disappeared; retry later')
            return item

    def finish(self, key, status, result):
        # Update only outcome fields, keeping the original fingerprint and expiry.
        # Expression aliases avoid collisions with DynamoDB reserved words.
        self.table.update_item(
            Key={'pk': key},
            UpdateExpression='SET #state = :state, #result = :result',
            ExpressionAttributeNames={'#state': 'status', '#result': 'result'},
            ExpressionAttributeValues={':state': status, ':result': result},
        )

    def consume(self, bucket, limit):
        # bucket combines UTC date and recipient hash. ADD is atomic, and the
        # condition is checked as part of that same write, preventing oversubscription
        # caused by separate read-then-increment operations under concurrency.
        try:
            self.table.update_item(
                Key={'pk': 'quota:' + bucket},
                UpdateExpression='SET expires_at = :ttl ADD #count :one',
                # A new day's counter may be absent; existing counters must be below
                # the limit BEFORE incrementing. At the limit, no increment occurs.
                ConditionExpression='attribute_not_exists(#count) OR #count < :limit',
                ExpressionAttributeNames={'#count': 'count'},
                ExpressionAttributeValues={':ttl': int(time.time()) + 2 * 86400,
                                           ':one': 1, ':limit': limit},
            )
        except ClientError as error:
            # Only this condition failure means the application limit was reached.
            # Unexpected AWS errors propagate to the processing-failure path.
            if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise QuotaExceeded() from error
            raise
