"""Fixed, sanitized explanations for the supported synthetic adapter.

Diagnosis is descriptive only: it never supplies a resume preview or permissions.
"""

MESSAGES = {
    'committed_and_acknowledged': 'The expected row and ownership receipt match, and the checkpoint acknowledges the effect.',
    'checkpoint_acknowledgement_missing': 'The expected row and ownership receipt prove the effect committed, but the checkpoint has not acknowledged it. Do not repeat this effect.',
    'not_observed': 'Neither a destination row nor ownership receipt is present, and the checkpoint does not claim completion.',
    'payload_changed': 'The destination row differs from the intended synthetic payload. Preserve the row for inspection.',
    'row_missing': 'An ownership receipt exists but the destination row is absent. Do not recreate it automatically.',
    'receipt_missing': 'A destination row exists without its ownership receipt. Matching text alone does not prove this run committed it.',
    'receipt_changed': 'The destination ownership receipt does not match the intended payload hash.',
    'checkpoint_ahead': 'The checkpoint acknowledges an effect for which neither destination row nor receipt is present.',
    'dependency_gap': 'This effect has matching destination evidence, but an earlier effect is not verified.',
    'unexpected_records': 'The destination contains records outside the fixed three-effect workflow. Their keys and contents are withheld.',
    'checkpoint_too_large': 'The checkpoint exceeds the supported size bound.',
    'checkpoint_invalid': 'The checkpoint does not have a supported, valid structure or run identifier.',
    'source_changed': 'The checkpoint names an unsupported fixture version.',
    'checkpoint_unavailable': 'The checkpoint could not be read. Check its presence and local accessibility.',
    'destination_too_large': 'The destination file exceeds the supported size bound.',
    'destination_schema_changed': 'The destination schema differs from the supported adapter contract.',
    'destination_journal_changed': 'The destination uses an unsupported journal mode.',
    'destination_integrity_failed': 'The destination did not pass its SQLite integrity check.',
    'destination_identity_changed': 'The destination run identity, schema version or state version is invalid or mismatched.',
    'destination_bounds': 'The destination exceeds the supported observation bound.',
    'destination_duplicate_keys': 'The destination contains duplicate keys and cannot be classified safely.',
    'destination_unavailable': 'The destination could not be opened. Check its presence and local accessibility.',
    'destination_unreadable': 'The destination could not be read consistently as the supported SQLite application.',
    'state_unavailable': 'The local run could not be accessed or locked for a consistent observation.',
}


class EvidenceUnavailable(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def describe(codes):
    # Every caller supplies internal constants; never interpolate observed payloads.
    return [MESSAGES[code] for code in codes]


def observed_diagnosis(statuses, actual, ledger, journal, expected, hashes):
    effects = []
    for key, label in expected.items():
        row = key in actual
        receipt = key in ledger
        acknowledged = key in journal['receipts']
        payload_matches = actual[key] == label if row else None
        receipt_matches = ledger[key] == hashes[key] if receipt else None
        status = statuses[key]
        if status == 'VERIFIED':
            codes = ['committed_and_acknowledged' if acknowledged else 'checkpoint_acknowledgement_missing']
        elif status == 'MISSING':
            codes = ['not_observed']
        else:
            codes = []
            if row and not payload_matches:
                codes.append('payload_changed')
            if not row and receipt:
                codes.append('row_missing')
            if row and not receipt:
                codes.append('receipt_missing')
            if receipt and not receipt_matches:
                codes.append('receipt_changed')
            if not row and not receipt and acknowledged:
                codes.append('checkpoint_ahead')
            if row and payload_matches and receipt_matches:
                codes.append('dependency_gap')
        effects.append({'id': key, 'label': label, 'status': status,
                        'reason_codes': codes, 'explanations': describe(codes),
                        'evidence': {'row_present': row, 'receipt_present': receipt,
                                     'payload_matches': payload_matches, 'receipt_matches': receipt_matches,
                                     'checkpoint_acknowledged': acknowledged}})
    issues = ['unexpected_records'] if 'unexpected' in statuses else []
    if journal['cancelled']:
        summary = 'Cancellation is recorded; future work is blocked. Existing effects remain.'
    elif 'CONFLICT' in statuses.values():
        summary = 'Destination evidence conflicts with intended work; resume is blocked.'
    elif all(status == 'VERIFIED' for status in statuses.values()):
        summary = 'All three intended effects are verified. No effect needs to be repeated.'
    else:
        summary = 'Review the observed evidence. Only missing effects are eligible for resume.'
    return {'summary': summary, 'issue_codes': issues, 'issues': describe(issues), 'effects': effects}


def unknown_diagnosis(code, expected):
    return {'summary': 'Completion cannot be proven; resume is blocked. Preserve the original state for inspection.',
            'issue_codes': [code], 'issues': describe([code]),
            'effects': [{'id': key, 'label': label, 'status': 'UNKNOWN',
                         'reason_codes': [code], 'explanations': describe([code]), 'evidence': None}
                        for key, label in expected.items()]}
