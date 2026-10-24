# =============================================================================
# PostgreSQL ledger integration tests
#
# Run against a real database because the atomicity lives in the SQL itself.
# Skipped unless TEST_DATABASE_URL points at a disposable PostgreSQL database,
# for example: TEST_DATABASE_URL=postgresql://localhost/waypoint_test pytest
# =============================================================================
import os
import time

import pytest

from app.store import QuotaExceeded

URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='TEST_DATABASE_URL not set')


@pytest.fixture
def store():
    from app.pgstore import PostgresStore
    s = PostgresStore(URL)
    with s._connect() as conn:
        conn.execute('TRUNCATE sms_ledger')
    return s


def test_postgres_claim_reserves_once_then_returns_the_finished_record(store):
    assert store.claim('in:1', 'abc') is None
    assert store.claim('in:1', 'abc') == {'fingerprint': 'abc', 'status': 'PROCESSING', 'result': None}
    store.finish('in:1', 'COMPLETED', {'messageId': 'm1'})
    assert store.claim('in:1', 'abc')['result'] == {'messageId': 'm1'}


def test_postgres_quota_stops_at_the_limit(store):
    store.consume('day:a', 2)
    store.consume('day:a', 2)
    with pytest.raises(QuotaExceeded):
        store.consume('day:a', 2)
    store.consume('day:b', 2)


def test_postgres_history_round_trips_and_expires(store):
    assert store.history('chat:x') == []
    store.save_history('chat:x', [['need water', 'Where are you?']], 60)
    assert store.history('chat:x') == [['need water', 'Where are you?']]
    with store._connect() as conn:
        conn.execute('UPDATE sms_ledger SET expires_at = %s', (int(time.time()) - 1,))
    assert store.history('chat:x') == []


def test_postgres_accepts_the_backend_url_form():
    from app.pgstore import PostgresStore
    assert PostgresStore(URL.replace('postgresql://', 'postgresql+psycopg://', 1)).history('chat:none') == []
