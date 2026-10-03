import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import rescuedesk as rd

SCRIPT = Path(rd.__file__).resolve()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'state'
        rd.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def child(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, timeout=10, start_new_session=True)

    def write(self, sql, values=()):
        with sqlite3.connect(self.root / 'application.sqlite') as db:
            db.execute(sql, values)

    def run_missing(self):
        report = rd.reconcile(self.root)
        return rd.resume(self.root, report['preview'], report['allowed'])

    def test_crash_matrix_new_process_recovery_and_no_duplicates(self):
        for boundary in ['before-write', 'during-write', 'after-write-before-ack', 'after-ack']:
            for key in rd.EFFECTS:
                with self.subTest(boundary=boundary, effect=key):
                    root = Path(self.tmp.name) / f'{boundary}-{key}'
                    rd.init(root)
                    before = rd.reconcile(root)
                    result = self.child('resume', str(root), '--preview', before['preview'], '--effects', '1', '2', '3', '--crash', f'{boundary}:{key}')
                    self.assertEqual(result.returncode, 77, result.stderr)
                    # New process observes committed destination, not the worker's return value.
                    observed = json.loads(self.child('reconcile', str(root)).stdout)
                    count = int(key) - (boundary in ['before-write', 'during-write'])
                    self.assertEqual(list(observed['statuses'].values()).count('VERIFIED'), count)
                    if observed['allowed']:
                        restarted = self.child('resume', str(root), '--preview', observed['preview'], '--effects', *observed['allowed'])
                        self.assertEqual(restarted.returncode, 0, restarted.stderr)
                    with sqlite3.connect(root / 'application.sqlite') as db:
                        self.assertEqual(db.execute('SELECT key,payload FROM effects ORDER BY key').fetchall(), list(rd.EFFECTS.items()))
                        self.assertEqual(db.execute('SELECT count(*) FROM receipts').fetchone()[0], 3)
                    retry = self.child('resume', str(root), '--preview', before['preview'], '--effects', '1', '2', '3')
                    self.assertEqual(retry.returncode, 2)

    def test_stale_preview_and_human_modification(self):
        old = rd.reconcile(self.root)
        rd.resume(self.root, old['preview'], ['1'])
        with self.assertRaises(ValueError):
            rd.resume(self.root, old['preview'], ['1'])
        self.write("UPDATE effects SET payload='Human edit' WHERE key='1'")
        report = rd.reconcile(self.root)
        self.assertEqual(report['statuses']['1'], 'CONFLICT')
        self.assertEqual(report['allowed'], [])
        with self.assertRaises(ValueError):
            rd.resume(self.root, report['preview'], ['2'])

    def test_deleted_committed_effect_is_conflict(self):
        self.run_missing()
        self.write("DELETE FROM effects WHERE key='2'")
        self.assertEqual(rd.reconcile(self.root)['statuses']['2'], 'CONFLICT')

    def test_corrupt_checkpoints_and_stale_source(self):
        original = (self.root / 'checkpoint.json').read_text()
        for value in ['{', '[]', '{"run": 123}', original.replace(rd.FIXTURE, 'old-source'), original.replace('false', '"false"')]:
            (self.root / 'checkpoint.json').write_text(value)
            report = rd.reconcile(self.root)
            self.assertEqual(set(report['statuses'].values()), {'UNKNOWN'})
            self.assertEqual(report['allowed'], [])

    def test_missing_corrupt_and_changed_destination(self):
        destination = self.root / 'application.sqlite'
        self.write('UPDATE meta SET schema=2')
        self.assertEqual(set(rd.reconcile(self.root)['statuses'].values()), {'UNKNOWN'})
        destination.unlink()
        self.assertEqual(set(rd.reconcile(self.root)['statuses'].values()), {'UNKNOWN'})
        self.assertFalse(destination.exists())
        destination.write_bytes(b'corrupt')
        self.assertEqual(set(rd.reconcile(self.root)['statuses'].values()), {'UNKNOWN'})

    def test_cancel_before_and_after_commit(self):
        old = rd.reconcile(self.root)
        rd.resume(self.root, old['preview'], ['1'])
        report = rd.cancel(self.root)
        self.assertTrue(report['cancelled'])
        self.assertEqual(report['allowed'], [])
        self.assertEqual(report['statuses']['1'], 'VERIFIED')
        with self.assertRaises(ValueError):
            rd.resume(self.root, old['preview'], ['1', '2', '3'])
        other = Path(self.tmp.name) / 'cancel-first'
        rd.init(other)
        self.assertEqual(rd.cancel(other)['statuses']['1'], 'MISSING')

    def test_non_prefix_or_duplicate_selection_rejected(self):
        report = rd.reconcile(self.root)
        for effects in [['2'], ['1', '1'], [], ['1', '3']]:
            with self.assertRaises(ValueError):
                rd.resume(self.root, report['preview'], effects)

    def test_same_payload_without_ownership_receipt_is_conflict(self):
        self.write('INSERT INTO effects VALUES (?,?)', ('1', rd.EFFECTS['1']))
        self.assertEqual(rd.reconcile(self.root)['statuses']['1'], 'CONFLICT')

    def test_version_drift_rejects_preview(self):
        report = rd.reconcile(self.root)
        self.write('UPDATE meta SET version=version+1')
        with self.assertRaises(ValueError):
            rd.resume(self.root, report['preview'], ['1'])
        self.assertEqual(rd.reconcile(self.root)['statuses']['1'], 'MISSING')

    def test_changed_schema_is_unknown(self):
        self.write('CREATE TABLE unrecognized(value TEXT)')
        self.assertEqual(set(rd.reconcile(self.root)['statuses'].values()), {'UNKNOWN'})

    def test_concurrent_resume_has_one_winner(self):
        report = rd.reconcile(self.root)
        args = [sys.executable, str(SCRIPT), 'resume', str(self.root), '--preview', report['preview'], '--effects', '1', '2', '3']
        workers = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        for worker in workers:
            worker.communicate(timeout=10)
        self.assertEqual(sorted(worker.returncode for worker in workers), [0, 2])
        with sqlite3.connect(self.root / 'application.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM effects').fetchone(), (3,))


if __name__ == '__main__':
    unittest.main()
