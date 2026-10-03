"""Deterministic, local-only recovery demonstration. Python standard library."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid

from diagnosis import EvidenceUnavailable, observed_diagnosis, unknown_diagnosis

FIXTURE = 'synthetic-ticket-v1'
SCHEMA = {
    'meta': 'CREATE TABLE meta(run TEXT, schema INTEGER, version INTEGER)',
    'effects': 'CREATE TABLE effects(key TEXT PRIMARY KEY, payload TEXT NOT NULL)',
    'receipts': 'CREATE TABLE receipts(key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL)',
}
EFFECTS = {'1': 'Synthetic ticket opened', '2': 'Synthetic ticket assigned', '3': 'Synthetic ticket resolved'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def checkpoint(root, value):
    temporary = root / 'checkpoint.tmp'
    with temporary.open('w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, root / 'checkpoint.json')


@contextlib.contextmanager
def locked(root):
    # Advisory process lock only; destination transaction also guards writers.
    with (root / 'recovery.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def init(root):
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    run = str(uuid.uuid4())
    with sqlite3.connect(root / 'application.sqlite') as db:
        for statement in SCHEMA.values():
            db.execute(statement)
        db.execute('INSERT INTO meta VALUES (?,1,0)', (run,))
    checkpoint(root, {'run': run, 'source': FIXTURE, 'receipts': [], 'cancelled': False})
    return {'run': run, 'fixture': FIXTURE, 'synthetic': True}


def read_checkpoint(root):
    path = root / 'checkpoint.json'
    if path.stat().st_size > 8192:
        raise EvidenceUnavailable('checkpoint_too_large')
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or set(value) != {'run', 'source', 'receipts', 'cancelled'}:
        raise EvidenceUnavailable('checkpoint_invalid')
    if not isinstance(value['run'], str) or str(uuid.UUID(value['run'])) != value['run']:
        raise EvidenceUnavailable('checkpoint_invalid')
    if value['source'] != FIXTURE:
        raise EvidenceUnavailable('source_changed')
    receipts = value['receipts']
    if type(value['cancelled']) is not bool or receipts not in [list(EFFECTS)[:n] for n in range(4)]:
        raise EvidenceUnavailable('checkpoint_invalid')
    return value


def connect(root):
    # mode=rw prevents accidentally creating a missing destination.
    if (root / 'application.sqlite').stat().st_size > 4 * 1024 * 1024:
        raise EvidenceUnavailable('destination_too_large')
    db = sqlite3.connect((root / 'application.sqlite').resolve().as_uri() + '?mode=rw', uri=True, timeout=2)
    db.execute('PRAGMA busy_timeout=2000')
    return db


def observe(db, journal):
    schema = db.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
    if dict(schema) != SCHEMA or len(schema) != len(SCHEMA):
        raise EvidenceUnavailable('destination_schema_changed')
    if db.execute('PRAGMA journal_mode').fetchone() != ('delete',):
        raise EvidenceUnavailable('destination_journal_changed')
    if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
        raise EvidenceUnavailable('destination_integrity_failed')
    meta = db.execute('SELECT run,schema,version FROM meta').fetchall()
    if len(meta) != 1 or meta[0][0] != journal['run'] or meta[0][1] != 1 or type(meta[0][2]) is not int or meta[0][2] < 0:
        raise EvidenceUnavailable('destination_identity_changed')
    rows = db.execute('SELECT key,payload FROM effects ORDER BY key LIMIT 101').fetchall()
    receipts = db.execute('SELECT key,payload_hash FROM receipts ORDER BY key LIMIT 101').fetchall()
    if len(rows) > 100 or len(receipts) > 100:
        raise EvidenceUnavailable('destination_bounds')
    actual, ledger = dict(rows), dict(receipts)
    if len(actual) != len(rows) or len(ledger) != len(receipts):
        raise EvidenceUnavailable('destination_duplicate_keys')
    statuses = {}
    for key, payload in EFFECTS.items():
        if key in actual and actual[key] == payload and ledger.get(key) == digest(payload):
            statuses[key] = 'VERIFIED'
        elif key not in actual and key not in ledger and key not in journal['receipts']:
            statuses[key] = 'MISSING'
        else:
            statuses[key] = 'CONFLICT'
    if (set(actual) | set(ledger)) - set(EFFECTS):
        statuses['unexpected'] = 'CONFLICT'
    # A later committed effect without its predecessor is inconsistent.
    missing_seen = False
    for key in EFFECTS:
        if statuses[key] != 'VERIFIED':
            missing_seen = True
        elif missing_seen:
            statuses[key] = 'CONFLICT'
    blocked = journal['cancelled'] or 'CONFLICT' in statuses.values()
    return {'run': journal['run'], 'synthetic': True, 'statuses': statuses,
            'cancelled': journal['cancelled'], 'version': meta[0][2],
            'preview': digest([journal, meta, rows, receipts]),
            'allowed': [] if blocked else [k for k in EFFECTS if statuses[k] == 'MISSING'],
            'blocked': blocked,
            'diagnosis': observed_diagnosis(statuses, actual, ledger, journal, EFFECTS,
                                            {key: digest(payload) for key, payload in EFFECTS.items()})}


def reconcile(root):
    root = Path(root)
    stage = 'state'
    try:
        with locked(root):
            stage = 'checkpoint'
            journal = read_checkpoint(root)
            stage = 'destination'
            with contextlib.closing(connect(root)) as db:
                db.execute('BEGIN')
                return observe(db, journal)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        if isinstance(exc, EvidenceUnavailable):
            code = exc.code
        elif stage == 'checkpoint':
            code = 'checkpoint_unavailable' if isinstance(exc, OSError) else 'checkpoint_invalid'
        elif stage == 'destination':
            code = 'destination_unavailable' if isinstance(exc, OSError) else 'destination_unreadable'
        else:
            code = 'state_unavailable'
        diagnosis = unknown_diagnosis(code, EFFECTS)
        return {'statuses': {key: 'UNKNOWN' for key in EFFECTS}, 'allowed': [], 'blocked': True,
                'diagnostic': diagnosis['issues'][0], 'diagnosis': diagnosis}


def crash_at(selected, boundary, key):
    if selected == f'{boundary}:{key}':
        os._exit(77)  # Actual process termination; no Python cleanup/acknowledgement.


def resume(root, preview, allowed, crash=None):
    root = Path(root)
    if not isinstance(allowed, list) or not allowed or any(type(k) is not str for k in allowed):
        raise ValueError('explicit nonempty effect list required')
    with locked(root):
        journal = read_checkpoint(root)
        with contextlib.closing(connect(root)) as db:
            db.execute('BEGIN IMMEDIATE')
            report = observe(db, journal)
            if report['blocked'] or preview != report['preview'] or allowed != report['allowed'][:len(allowed)]:
                raise ValueError('stale preview, blocked state, or non-prefix effect selection; reconcile again')
            db.rollback()
            for key in allowed:
                # Revalidate immediately before each effect, including human edits between transactions.
                db.execute('BEGIN IMMEDIATE')
                fresh = observe(db, journal)
                if fresh['preview'] != report['preview'] or fresh['blocked']:
                    raise ValueError('destination changed during resume')
                crash_at(crash, 'before-write', key)
                db.execute('INSERT INTO effects VALUES (?,?)', (key, EFFECTS[key]))
                crash_at(crash, 'during-write', key)
                db.execute('INSERT INTO receipts VALUES (?,?)', (key, digest(EFFECTS[key])))
                db.execute('UPDATE meta SET version=version+1')
                db.commit()  # Effect boundary: separate from checkpoint acknowledgement.
                crash_at(crash, 'after-write-before-ack', key)
                journal['receipts'] = list(EFFECTS)[:int(key)]
                checkpoint(root, journal)
                crash_at(crash, 'after-ack', key)
                db.execute('BEGIN')
                report = observe(db, journal)
                db.rollback()
    return reconcile(root)


def cancel(root):
    root = Path(root)
    with locked(root):
        journal = read_checkpoint(root)
        journal['cancelled'] = True
        checkpoint(root, journal)
    return reconcile(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'reconcile', 'resume', 'cancel', 'serve'])
    parser.add_argument('root', type=Path, help='disposable local directory; init requires a new path')
    parser.add_argument('--preview')
    parser.add_argument('--effects', nargs='+')
    parser.add_argument('--crash', choices=[f'{b}:{k}' for b in ['before-write', 'during-write', 'after-write-before-ack', 'after-ack'] for k in EFFECTS])
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            from server import serve
            serve(args.root, args.port)
            return
        result = {'init': lambda: init(args.root), 'reconcile': lambda: reconcile(args.root),
                  'resume': lambda: resume(args.root, args.preview, args.effects, args.crash),
                  'cancel': lambda: cancel(args.root)}[args.command]()
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({'error': type(exc).__name__, 'message': 'Operation rejected; reconcile and inspect local state.'}))
        sys.exit(2)


if __name__ == '__main__':
    main()
