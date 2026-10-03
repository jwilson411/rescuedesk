# Local recovery runbook

This runbook is only for disposable synthetic RescueDesk runs. Preserve the original state if investigating a failed run; do not patch its checkpoint to force progress.

| Observation | Interpretation | Supported next action |
| --- | --- | --- |
| VERIFIED | Exact destination payload and ownership receipt observed | Leave it alone; never rerun that effect |
| MISSING | Neither destination row nor receipt exists, and checkpoint does not contradict absence | Select an ordered missing prefix using the latest preview |
| CONFLICT | Human edit, missing committed row, missing ownership receipt, unexpected row, or dependency gap | Stop; inspect the SQLite application and checkpoint separately |
| UNKNOWN | Adapter cannot prove state: unreadable/corrupt/unsupported source, schema, identity, or database | Stop; preserve the failure for inspection; no automatic retry |
| Stale preview rejection | Destination/checkpoint changed after the preview | Reconcile again; examine the new report before selecting work |
| Cancelled | Future resume prohibited after the cancellation lock was acquired | Existing effects remain; use a new disposable run for another scenario |

For a lost acknowledgement, use `reconcile` from a new process and inspect the report. Never infer that a nonzero worker exit means no effect occurred. A crash after the application commit deliberately leaves the checkpoint behind.

Cancellation serializes behind an active resume. Wait for the cancellation command to return, then reconcile to confirm `cancelled: true` and `allowed: []`. Cancellation is not an emergency interrupt. Crash injection is a separate synthetic test facility, not a general process manager.

To reset a demo, stop the exact server/worker you started, delete only that disposable run directory, and use `init` to create a fresh run. Reset creates a new run ID and deliberately destroys its old synthetic evidence. There is no browser reset button or repair endpoint. Do not use this procedure for production data.

Keep source and sanitized test exports on NAS as desired; keep the live SQLite run on a local filesystem. Do not commit checkpoint/database files or the server's session token. Reconcile's diagnostic intentionally describes the failure category without exposing raw file contents.

## Reading an effect's diagnosis

The desk now describes the evidence behind each status. The technical report includes `diagnosis.effects`, with fixed `reason_codes` and evidence booleans. `null` match values mean that the row or receipt is absent; UNKNOWN uses `evidence: null` because no trustworthy observation was completed.

- `checkpoint_acknowledgement_missing`: matching application row and ownership receipt prove the effect committed even though the checkpoint lags. Leave that effect alone; review only the reported missing work.
- `payload_changed`, `row_missing`, `receipt_missing`, `receipt_changed`, or `checkpoint_ahead`: preserve the original state and inspect the identified mismatch. No repair or overwrite is authorized.
- `dependency_gap`: a later effect has matching evidence while an earlier effect is not verified. Resume remains blocked.
- `unexpected_records`: records outside the fixed fixture exist; their contents and keys are deliberately withheld.
- UNKNOWN codes identify unavailable/invalid checkpoint, unsupported source, or unavailable/unreadable/unsupported destination. These are diagnostic categories, not a claim that the underlying cause or safe repair is known.

Diagnosis never grants authority or substitutes for a fresh preview. A cancellation summary takes precedence while preserving each effect's evidence. Reports intentionally omit raw edited values, unexpected keys and raw exception text. Reconcile diagnoses the checkpoint first, so if both checkpoint and destination are unreadable, the checkpoint issue is reported first. First reconciliation after an uncommitted SQLite crash may recover a hot journal; subsequent observations do not rewrite application rows or checkpoint contents.
