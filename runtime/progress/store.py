"""Transactional append-only progress journal, bounded per logical job.

SQLite is from the standard library. FULL synchronous transactions atomically
commit the event and chain head; a killed writer leaves both or neither. This
is evidence, never an authorization store. A local owner with arbitrary file
access can replace the database; hashes are not signatures.
"""

from contextlib import contextmanager
from pathlib import Path
import json
import os
import tempfile
import re
import sqlite3

from runtime.storage.file_store import FileJobStore
from runtime.progress.models import ProgressError, ProgressEvent, canonical, digest


MAX_EVENTS = 4096
MAX_JOB_EVENTS = 128
MAX_EVENT_BYTES = 4096
MAX_DATABASE_BYTES = 32 * 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")


_SCHEMA = {
    ("table", "events"): "CREATE TABLE events (sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL)",
    ("table", "head"): "CREATE TABLE head (singleton INTEGER PRIMARY KEY CHECK(singleton=1), sequence INTEGER NOT NULL, hash TEXT NOT NULL)",
    ("trigger", "no_update"): "CREATE TRIGGER no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'append only'); END",
    ("trigger", "no_delete"): "CREATE TRIGGER no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'append only'); END",
    ("table", "pending"): "CREATE TABLE pending (job_id TEXT PRIMARY KEY NOT NULL, before_digest TEXT NOT NULL, after_digest TEXT NOT NULL, bundle TEXT NOT NULL)",
    ("table", "recovery"): "CREATE TABLE recovery (job_id TEXT PRIMARY KEY NOT NULL, ready INTEGER NOT NULL CHECK(ready IN (0,1)), payload TEXT NOT NULL)",
}
_TERMINAL = {"job_completed": "completed", "job_failed": "failed", "job_cancelled": "cancelled"}


def _check_terminals(events):
    states, identities = {}, {}
    for event in events:
        state = _TERMINAL.get(event.event_type)
        if event.event_type == "job_state_observed" and event.detail in _TERMINAL.values():
            state = event.detail
        if state is not None:
            previous = states.setdefault(event.job_id, state)
            if previous != state:
                raise ProgressError("Conflicting terminal job history")
        if event.event_type in _TERMINAL:
            previous = identities.setdefault(event.job_id, event.event_id)
            if previous != event.event_id:
                raise ProgressError("Duplicate or conflicting terminal identity")


class ProgressStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, logical_job_id):
        if not isinstance(logical_job_id, str) or not _ID.fullmatch(logical_job_id):
            raise ProgressError("Invalid logical job identity")
        return self.root / (logical_job_id + ".sqlite3")

    @contextmanager
    def _connect(self, logical_job_id):
        # Match the existing cross-process file-store lock for first creation.
        try:
            with FileJobStore(self.root).claim_transaction():
                with self._transaction(logical_job_id) as connection:
                    yield connection
        except (ValueError, OSError) as error:
            raise ProgressError("Progress journal operation failed") from error

    @contextmanager
    def _transaction(self, logical_job_id):
        path = self.path(logical_job_id)
        self.root.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_DATABASE_BYTES:
            raise ProgressError("Progress database exceeds size bound")
        fresh = not path.exists()
        connection = None
        temporary = None
        try:
            if fresh:
                descriptor, name = tempfile.mkstemp(prefix=".progress-", suffix=".tmp", dir=self.root)
                os.close(descriptor)
                temporary = Path(name)
            connection = sqlite3.connect(temporary or path, timeout=5)
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            if fresh:
                for statement in _SCHEMA.values():
                    connection.execute(statement)
                connection.execute("PRAGMA user_version=2")
            self._validate_schema(connection)
            yield connection
            connection.commit()
            if temporary is not None:
                connection.close()
                connection = None
                os.replace(temporary, path)
        except (sqlite3.Error, OSError, ValueError, TypeError, RecursionError) as error:
            if connection is not None:
                connection.rollback()
            raise ProgressError("Progress journal is unavailable or malformed") from error
        finally:
            if connection is not None:
                connection.close()
            if temporary is not None and temporary.exists():
                temporary.unlink()

    @staticmethod
    def _validate_schema(connection):
        objects = {(kind, name): sql for kind, name, sql in connection.execute(
            "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL")}
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        v1 = {key: value for key, value in _SCHEMA.items() if key != ("table", "recovery")}
        legacy = {key: value for key, value in v1.items() if key != ("table", "pending")}
        if version == 0 and objects == legacy:
            # Bounded migration of intact R1 journals. Never repair altered DDL.
            connection.execute(_SCHEMA[("table", "pending")])
            connection.execute("PRAGMA user_version=1")
            objects[("table", "pending")] = _SCHEMA[("table", "pending")]
            version = 1
        if version == 1 and objects == v1:
            connection.execute(_SCHEMA[("table", "recovery")])
            connection.execute("PRAGMA user_version=2")
            objects[("table", "recovery")] = _SCHEMA[("table", "recovery")]
            version = 2
        if version != 2 or objects != _SCHEMA:
            raise ProgressError("Progress schema/protection definition mismatch")

    @staticmethod
    def _recoveries(connection, logical_id):
        records = {}
        for job_id, ready, payload in connection.execute("SELECT job_id,ready,payload FROM recovery LIMIT ?", (MAX_EVENTS + 1,)):
            if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_EVENT_BYTES:
                raise ProgressError("Invalid recovery delivery")
            event = ProgressEvent.from_dict(json.loads(payload))
            if (ready not in (0, 1) or event.event_type != "recovery_completed"
                    or event.job_id != job_id or event.logical_job_id != logical_id
                    or canonical(event.to_dict()) != payload
                    or (not ready and event.detail != "worker_error")):
                raise ProgressError("Recovery delivery binding mismatch")
            records[job_id] = (ready, event)
        if len(records) > MAX_EVENTS:
            raise ProgressError("Too many recovery deliveries")
        return records

    @staticmethod
    def _pending(connection, logical_job_id):
        rows = connection.execute("SELECT job_id,before_digest,after_digest,bundle FROM pending LIMIT ?", (MAX_EVENTS + 1,)).fetchall()
        if len(rows) > MAX_EVENTS:
            raise ProgressError("Too many pending progress deliveries")
        pending = {}
        for job_id, before, after, payload in rows:
            if (not isinstance(job_id, str) or not _ID.fullmatch(job_id)
                    or any(not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None for value in (before, after))
                    or not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_JOB_EVENTS * MAX_EVENT_BYTES):
                raise ProgressError("Malformed pending progress delivery")
            values = json.loads(payload)
            if not isinstance(values, list) or not 1 <= len(values) <= MAX_JOB_EVENTS:
                raise ProgressError("Invalid pending progress bundle")
            events = [ProgressEvent.from_dict(value) for value in values]
            if (canonical(values) != payload or len({event.event_id for event in events}) != len(events)
                    or any(event.logical_job_id != logical_job_id or event.job_id != job_id for event in events)):
                raise ProgressError("Pending progress binding mismatch")
            pending[job_id] = (before, after, events)
        return pending

    @staticmethod
    def _capacity(history, pending, extra=(), recovery=None):
        # Count the union: replaying an already-reserved event consumes no new slot.
        events = {event.event_id: event for event in history}
        for _, _, bundle in pending.values():
            events.update((event.event_id, event) for event in bundle)
        events.update((event.event_id, event) for event in extra)
        counts = {}
        for event in events.values():
            counts[event.job_id] = counts.get(event.job_id, 0) + 1
        reserved = 0
        for job_id, (ready, event) in (recovery or {}).items():
            # An unfinished recovery reserves a slot for its still-unknown outcome.
            if not ready or event.event_id not in events:
                reserved += 1
                counts[job_id] = counts.get(job_id, 0) + 1
        if len(events) + reserved > MAX_EVENTS or any(count > MAX_JOB_EVENTS for count in counts.values()):
            raise ProgressError("Progress history is full; complete bundle cannot fit")
        _check_terminals(events.values())

    def _read(self, connection, logical_job_id):
        count = connection.execute("SELECT count(*) FROM events").fetchone()[0]
        if count > MAX_EVENTS:
            raise ProgressError("Progress history exceeds limit")
        result = []
        previous = "0" * 64
        per_job = {}
        for sequence, identity, payload, prior, chain_hash in connection.execute("SELECT sequence,event_id,payload,previous,hash FROM events ORDER BY sequence"):
            if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_EVENT_BYTES:
                raise ProgressError("Progress event exceeds byte bound")
            event = ProgressEvent.from_dict(json.loads(payload))
            if canonical(event.to_dict()) != payload:
                raise ProgressError("Progress payload is not canonical JSON")
            if event.logical_job_id != logical_job_id or identity != event.event_id:
                raise ProgressError("Progress identity mismatch")
            if sequence != len(result) + 1 or prior != previous or chain_hash != digest([sequence, prior, identity]):
                raise ProgressError("Progress chain mismatch")
            per_job[event.job_id] = per_job.get(event.job_id, 0) + 1
            if per_job[event.job_id] > MAX_JOB_EVENTS:
                raise ProgressError("Job progress history exceeds limit")
            previous = chain_hash
            result.append(event)
        head = connection.execute("SELECT sequence,hash FROM head WHERE singleton=1").fetchone()
        if head != ((len(result), previous) if result else None):
            raise ProgressError("Progress high-water evidence mismatch")
        pending = self._pending(connection, logical_job_id)
        self._capacity(result, pending, recovery=self._recoveries(connection, logical_job_id))
        return result, previous

    def read(self, logical_job_id):
        if not self.path(logical_job_id).exists():
            return []
        with self._connect(logical_job_id) as connection:
            return self._read(connection, logical_job_id)[0]

    @staticmethod
    def _insert(connection, history, previous, events):
        known = {event.event_id for event in history}
        sequence = len(history)
        count = 0
        for event in events:
            if event.event_id in known:
                continue
            payload = canonical(event.to_dict())
            if len(payload.encode("utf-8")) > MAX_EVENT_BYTES:
                raise ProgressError("Progress event exceeds byte bound")
            sequence += 1
            chain_hash = digest([sequence, previous, event.event_id])
            connection.execute("INSERT INTO events VALUES (?,?,?,?,?)", (sequence, event.event_id, payload, previous, chain_hash))
            connection.execute("INSERT OR REPLACE INTO head VALUES (1,?,?)", (sequence, chain_hash))
            previous = chain_hash
            known.add(event.event_id)
            count += 1
        return count

    def append(self, event: ProgressEvent):
        return bool(self.append_many([event]))

    def append_many(self, events):
        events = [ProgressEvent.from_dict(event.to_dict()) for event in events]
        if not events:
            return 0
        logical_id = events[0].logical_job_id
        if any(event.logical_job_id != logical_id for event in events):
            raise ProgressError("Progress bundle crosses logical jobs")
        with self._connect(logical_id) as connection:
            history, previous = self._read(connection, logical_id)
            pending = self._pending(connection, logical_id)
            # Only resolve() may deliver a reserved transition observation.
            reserved = {event.event_id for _, _, bundle in pending.values() for event in bundle}
            known = {event.event_id for event in history}
            if any(event.event_id in reserved - known for event in events):
                raise ProgressError("Pending transition needs canonical reconciliation")
            recovery = self._recoveries(connection, logical_id)
            for event in events:
                if event.event_type == "recovery_completed" and event.job_id in recovery:
                    ready, expected = recovery[event.job_id]
                    if not ready or event != expected:
                        raise ProgressError("Recovery outcome is not ready for delivery")
            self._capacity(history, pending, events, recovery)
            count = self._insert(connection, history, previous, events)
            for event in events:
                if event.event_type == "recovery_completed":
                    connection.execute("DELETE FROM recovery WHERE job_id=?", (event.job_id,))
            return count

    def reserve(self, logical_id, job_id, before_digest, after_digest, events):
        events = [ProgressEvent.from_dict(event.to_dict()) for event in events]
        if any(event.logical_job_id != logical_id or event.job_id != job_id for event in events):
            raise ProgressError("Transition bundle binding mismatch")
        with self._connect(logical_id) as connection:
            history, _ = self._read(connection, logical_id)
            pending = self._pending(connection, logical_id)
            if job_id in pending:
                raise ProgressError("Unresolved progress delivery before next transition")
            self._capacity(history, pending, events, self._recoveries(connection, logical_id))
            if all(event.event_id in {item.event_id for item in history} for event in events):
                return
            connection.execute("INSERT INTO pending VALUES (?,?,?,?)", (
                job_id, before_digest, after_digest, canonical([event.to_dict() for event in events])))
            self._pending(connection, logical_id)

    def resolve(self, logical_id, job_id, state_digest, expected_events):
        if not self.path(logical_id).exists():
            return
        with self._connect(logical_id) as connection:
            history, previous = self._read(connection, logical_id)
            pending = self._pending(connection, logical_id)
            if job_id not in pending:
                return
            before, after, events = pending[job_id]
            if state_digest == after:
                if events != list(expected_events):
                    raise ProgressError("Pending bundle differs from canonical observations")
                self._insert(connection, history, previous, events)
            elif state_digest != before:
                raise ProgressError("Pending transition does not match canonical state")
            # Never write a job from journal intent. An unchanged job aborts delivery.
            connection.execute("DELETE FROM pending WHERE job_id=?", (job_id,))

    def begin_recovery(self, event):
        """Reserve one outcome slot before any recovery lifecycle mutation."""
        event = ProgressEvent.from_dict(event.to_dict())
        if event.event_type != "recovery_completed" or event.detail != "worker_error":
            raise ProgressError("Invalid recovery reservation")
        with self._connect(event.logical_job_id) as connection:
            history, _ = self._read(connection, event.logical_job_id)
            recovery = self._recoveries(connection, event.logical_job_id)
            if event.job_id in recovery:
                raise ProgressError("Unresolved recovery delivery")
            recovery[event.job_id] = (0, event)
            self._capacity(history, self._pending(connection, event.logical_job_id), recovery=recovery)
            connection.execute("INSERT INTO recovery VALUES (?,0,?)", (event.job_id, canonical(event.to_dict())))

    def finish_recovery(self, event):
        """Persist the actual returned outcome before attempting event delivery."""
        event = ProgressEvent.from_dict(event.to_dict())
        with self._connect(event.logical_job_id) as connection:
            history, _ = self._read(connection, event.logical_job_id)
            recovery = self._recoveries(connection, event.logical_job_id)
            record = recovery.get(event.job_id)
            if (record is None or record[0] or event.event_type != "recovery_completed"
                    or event.execution_id != record[1].execution_id):
                raise ProgressError("Missing or already finished recovery reservation")
            recovery[event.job_id] = (1, event)
            self._capacity(history, self._pending(connection, event.logical_job_id), recovery=recovery)
            connection.execute("UPDATE recovery SET ready=1,payload=? WHERE job_id=?", (canonical(event.to_dict()), event.job_id))

    def recovery_record(self, logical_id, job_id):
        if not self.path(logical_id).exists():
            return None
        with self._connect(logical_id) as connection:
            self._read(connection, logical_id)
            return self._recoveries(connection, logical_id).get(job_id)

    def deliver_recovery(self, logical_id, job_id):
        record = self.recovery_record(logical_id, job_id)
        if record is not None and record[0]:
            self.append(record[1])
