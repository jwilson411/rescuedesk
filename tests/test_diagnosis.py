import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import rescuedesk as rd


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'state'
        rd.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def sql(self, statement, args=()):
        with sqlite3.connect(self.root / 'application.sqlite') as db:
            db.execute(statement, args)

    def effect(self, report, key='1'):
        return next(effect for effect in report['diagnosis']['effects'] if effect['id'] == key)

    def fingerprints(self):
        return {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
                for name in ['checkpoint.json', 'application.sqlite']}

    def test_new_process_lost_ack_explains_actual_evidence_without_rewrite(self):
        before = rd.reconcile(self.root)
        result = subprocess.run([sys.executable, str(Path(rd.__file__).resolve()), 'resume', str(self.root),
                                 '--preview', before['preview'], '--effects', '1', '2', '3',
                                 '--crash', 'after-write-before-ack:2'], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 77)
        observed = json.loads(subprocess.check_output([sys.executable, str(Path(rd.__file__).resolve()), 'reconcile', str(self.root)], timeout=10))
        self.assertEqual(self.effect(observed, '1')['reason_codes'], ['committed_and_acknowledged'])
        second = self.effect(observed, '2')
        self.assertEqual(second['reason_codes'], ['checkpoint_acknowledgement_missing'])
        self.assertEqual(second['evidence'], {'row_present': True, 'receipt_present': True,
                                            'payload_matches': True, 'receipt_matches': True,
                                            'checkpoint_acknowledged': False})
        self.assertEqual(self.effect(observed, '3')['reason_codes'], ['not_observed'])
        self.assertEqual(observed['allowed'], ['3'])
        fingerprints = self.fingerprints()
        for _ in range(3):
            self.assertEqual(rd.reconcile(self.root), observed)
        self.assertEqual(self.fingerprints(), fingerprints)
        final = rd.resume(self.root, observed['preview'], ['3'])
        self.assertEqual(list(final['statuses'].values()), ['VERIFIED'] * 3)

    def test_edited_payload_and_unknown_keys_are_not_disclosed(self):
        before = rd.reconcile(self.root)
        rd.resume(self.root, before['preview'], ['1'])
        marker = '<script>PRIVATE_SYNTHETIC_MARKER</script>'
        self.sql('UPDATE effects SET payload=? WHERE key=?', (marker, '1'))
        self.sql('INSERT INTO receipts VALUES (?,?)', (marker, marker))
        fingerprints = self.fingerprints()
        report = rd.reconcile(self.root)
        self.assertEqual(self.effect(report)['reason_codes'], ['payload_changed'])
        self.assertEqual(report['diagnosis']['issue_codes'], ['unexpected_records'])
        self.assertNotIn(marker, json.dumps(report))
        self.assertNotIn('PRIVATE_SYNTHETIC_MARKER', json.dumps(report))
        self.assertEqual(report['allowed'], [])
        self.assertEqual(self.fingerprints(), fingerprints)
        with self.assertRaises(ValueError):
            rd.resume(self.root, report['preview'], ['2'])

    def test_missing_receipt_is_distinct_from_deleted_row(self):
        self.sql('INSERT INTO effects VALUES (?,?)', ('1', rd.EFFECTS['1']))
        report = rd.reconcile(self.root)
        self.assertEqual(self.effect(report)['reason_codes'], ['receipt_missing'])
        self.assertTrue(self.effect(report)['evidence']['payload_matches'])
        self.assertIsNone(self.effect(report)['evidence']['receipt_matches'])
        self.sql('DELETE FROM effects')
        self.sql('INSERT INTO receipts VALUES (?,?)', ('1', rd.digest(rd.EFFECTS['1'])))
        report = rd.reconcile(self.root)
        self.assertEqual(self.effect(report)['reason_codes'], ['row_missing'])
        self.assertIsNone(self.effect(report)['evidence']['payload_matches'])

    def test_corrupt_receipt_and_checkpoint_ahead(self):
        self.sql('INSERT INTO effects VALUES (?,?)', ('1', rd.EFFECTS['1']))
        self.sql('INSERT INTO receipts VALUES (?,?)', ('1', 'wrong-hash'))
        self.assertEqual(self.effect(rd.reconcile(self.root))['reason_codes'], ['receipt_changed'])
        self.sql('DELETE FROM effects');self.sql('DELETE FROM receipts')
        value = rd.read_checkpoint(self.root);value['receipts'] = ['1'];rd.checkpoint(self.root, value)
        self.assertEqual(self.effect(rd.reconcile(self.root))['reason_codes'], ['checkpoint_ahead'])

    def test_dependency_gap_does_not_claim_completion(self):
        self.sql('INSERT INTO effects VALUES (?,?)', ('2', rd.EFFECTS['2']))
        self.sql('INSERT INTO receipts VALUES (?,?)', ('2', rd.digest(rd.EFFECTS['2'])))
        report = rd.reconcile(self.root)
        self.assertEqual(self.effect(report, '2')['status'], 'CONFLICT')
        self.assertEqual(self.effect(report, '2')['reason_codes'], ['dependency_gap'])
        self.assertEqual(report['allowed'], [])

    def test_unknown_checkpoint_and_destination_have_safe_separate_diagnoses(self):
        checkpoint = self.root / 'checkpoint.json'
        original = checkpoint.read_bytes()
        checkpoint.write_text('{SYNTHETIC_SECRET:broken')
        report = rd.reconcile(self.root)
        self.assertEqual(report['diagnosis']['issue_codes'], ['checkpoint_invalid'])
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(report))
        self.assertIsNone(self.effect(report)['evidence'])
        self.assertNotIn('preview', report)
        checkpoint.unlink()
        self.assertEqual(rd.reconcile(self.root)['diagnosis']['issue_codes'], ['checkpoint_unavailable'])
        checkpoint.write_bytes(original)
        value = rd.read_checkpoint(self.root);value['source'] = 'SYNTHETIC_UNSUPPORTED_SOURCE';rd.checkpoint(self.root,value)
        report = rd.reconcile(self.root)
        self.assertEqual(report['diagnosis']['issue_codes'], ['source_changed'])
        self.assertNotIn('SYNTHETIC_UNSUPPORTED_SOURCE', json.dumps(report))
        checkpoint.write_bytes(original)
        destination = self.root / 'application.sqlite';destination.unlink()
        self.assertEqual(rd.reconcile(self.root)['diagnosis']['issue_codes'], ['destination_unavailable'])
        self.assertFalse(destination.exists())
        destination.write_bytes(b'not a database')
        self.assertEqual(rd.reconcile(self.root)['diagnosis']['issue_codes'], ['destination_unreadable'])

    def test_cancelled_state_retains_evidence_and_no_authority_from_diagnosis(self):
        before = rd.reconcile(self.root)
        rd.resume(self.root, before['preview'], ['1'])
        report = rd.cancel(self.root)
        self.assertEqual(self.effect(report)['status'], 'VERIFIED')
        self.assertEqual(report['allowed'], [])
        self.assertIn('Cancellation', report['diagnosis']['summary'])
        with self.assertRaises(ValueError):
            rd.resume(self.root, before['preview'], ['1', '2', '3'])


if __name__ == '__main__':
    unittest.main()
