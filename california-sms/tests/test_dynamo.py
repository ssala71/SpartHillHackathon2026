# =============================================================================
# DynamoDB adapter contract tests
#
# Inject a mocked Boto3 Table and verify how DynamoStore builds conditional writes
# and handles AWS error codes. These tests protect the distinction between an
# expected duplicate/quota condition and an infrastructure or permission failure.
# They do not run DynamoDB, test its throughput, or prove concurrency behavior on
# a deployed table; those require separate AWS integration verification.
# =============================================================================
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.store import DynamoStore, QuotaExceeded


def conditional_failure():
    # Use the actual botocore exception shape inspected by the adapter. Only the
    # error Code drives the branch; the operation name is diagnostic metadata.
    return ClientError({'Error': {'Code': 'ConditionalCheckFailedException'}}, 'UpdateItem')


def test_dynamo_duplicate_returns_existing_record_with_consistent_read():
    # Pretend another invocation already won the conditional PutItem. The adapter
    # must retrieve that record rather than returning a new reservation.
    table = Mock()
    table.put_item.side_effect = conditional_failure()
    table.get_item.return_value = {'Item': {'status': 'COMPLETED', 'fingerprint': 'abc'}}
    store = DynamoStore(table)
    assert store.claim('in:123', 'abc')['status'] == 'COMPLETED'
    table.get_item.assert_called_once_with(Key={'pk': 'in:123'}, ConsistentRead=True)
    # This condition is the cross-process reservation boundary, not a prior read.
    assert table.put_item.call_args.kwargs['ConditionExpression'] == 'attribute_not_exists(pk)'


def test_dynamo_counter_rejects_limit_atomically():
    # A rejected counter write must become QuotaExceeded, while the request must
    # express the upper bound as part of the update rather than a separate check.
    table = Mock()
    table.update_item.side_effect = conditional_failure()
    with pytest.raises(QuotaExceeded):
        DynamoStore(table).consume('2026-10-23:recipient-hash', 20)
    request = table.update_item.call_args.kwargs
    # Inspect the submitted limit and condition, not implementation-private state.
    assert request['ExpressionAttributeValues'][':limit'] == 20
    assert '#count < :limit' in request['ConditionExpression']


def test_dynamo_service_error_is_not_treated_as_duplicate():
    # AccessDenied cannot be handled as an existing record: doing so could conceal
    # broken deployment permissions and misrepresent whether work was reserved.
    table = Mock()
    table.put_item.side_effect = ClientError({'Error': {'Code': 'AccessDeniedException'}}, 'PutItem')
    with pytest.raises(ClientError):
        DynamoStore(table).claim('in:123', 'abc')
    table.get_item.assert_not_called()
