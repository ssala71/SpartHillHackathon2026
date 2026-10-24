# =============================================================================
# PostgreSQL ledger for duplicate protection, daily quotas, and reply history
#
# Same interface as store.DynamoStore, so MessagingService does not change. Used
# when DATABASE_URL is set, which lets the SMS service share the Waypoint
# backend's PostgreSQL database (in its own sms_ledger table). Atomicity comes
# from single-statement INSERT ... ON CONFLICT writes, matching DynamoDB's
# conditional writes. Expired rows are ignored on read and pruned on write.
# =============================================================================
import json
import time

import psycopg

from app.store import QuotaExceeded

SCHEMA = '''
CREATE TABLE IF NOT EXISTS sms_ledger (
    pk          TEXT PRIMARY KEY,
    fingerprint TEXT,
    status      TEXT,
    result      TEXT,
    count       INTEGER,
    turns       TEXT,
    expires_at  BIGINT NOT NULL
)'''


class PostgresStore:
    def __init__(self, url):
        # Accept the backend's SQLAlchemy form too, so both services can share one URL.
        self.url = url.replace('postgresql+psycopg://', 'postgresql://', 1)
        with self._connect() as conn:
            conn.execute(SCHEMA)

    def _connect(self):
        # One short connection per operation keeps this safe across FastAPI's
        # worker threads without a pool; demo traffic is a few requests a minute.
        return psycopg.connect(self.url, autocommit=True)

    def claim(self, key, fingerprint):
        # None reserves new work; an existing row (a duplicate) is returned instead.
        with self._connect() as conn:
            conn.execute('DELETE FROM sms_ledger WHERE expires_at < %s', (int(time.time()),))
            created = conn.execute(
                'INSERT INTO sms_ledger (pk, fingerprint, status, expires_at) VALUES (%s, %s, %s, %s) '
                'ON CONFLICT (pk) DO NOTHING RETURNING pk',
                (key, fingerprint, 'PROCESSING', int(time.time()) + 7 * 86400)).fetchone()
            if created:
                return None
            row = conn.execute('SELECT fingerprint, status, result FROM sms_ledger WHERE pk = %s',
                               (key,)).fetchone()
        if row is None:
            raise RuntimeError('Idempotency record disappeared; retry later')
        return {'fingerprint': row[0], 'status': row[1],
                'result': json.loads(row[2]) if row[2] else None}

    def finish(self, key, status, result):
        with self._connect() as conn:
            conn.execute('UPDATE sms_ledger SET status = %s, result = %s WHERE pk = %s',
                         (status, json.dumps(result), key))

    def consume(self, bucket, limit):
        # Increment only while below the limit, in one statement, so concurrent
        # requests cannot both take the last slot.
        with self._connect() as conn:
            row = conn.execute(
                'INSERT INTO sms_ledger (pk, count, expires_at) VALUES (%s, 1, %s) '
                'ON CONFLICT (pk) DO UPDATE SET count = sms_ledger.count + 1, '
                'expires_at = EXCLUDED.expires_at WHERE sms_ledger.count < %s RETURNING count',
                ('quota:' + bucket, int(time.time()) + 2 * 86400, limit)).fetchone()
        if row is None:
            raise QuotaExceeded()

    def history(self, key):
        with self._connect() as conn:
            row = conn.execute('SELECT turns FROM sms_ledger WHERE pk = %s AND expires_at >= %s',
                               (key, int(time.time()))).fetchone()
        return json.loads(row[0]) if row else []

    def save_history(self, key, turns, ttl):
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO sms_ledger (pk, turns, expires_at) VALUES (%s, %s, %s) '
                'ON CONFLICT (pk) DO UPDATE SET turns = EXCLUDED.turns, expires_at = EXCLUDED.expires_at',
                (key, json.dumps(turns), int(time.time()) + ttl))
