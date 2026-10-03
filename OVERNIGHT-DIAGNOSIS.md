# Bounded operator diagnosis increment

Base: independently reviewed `703043beba3a09c11f18b12d25e9badfcc623bd1`. PR1 stays frozen. This branch is stacked on it.

## Reproduced operator gap

The plan calls for operator-visible evidence, but the base report gives a human-edited committed row only `CONFLICT` and an unreadable checkpoint only an exception category. The runbook then asks the operator to inspect raw SQLite/checkpoint state. This makes the common lost-acknowledgement and drift cases unnecessarily difficult to distinguish.

## Scope

Add fixed safe reason codes, explanations and evidence booleans to the existing reconciliation report. Display readable effect descriptions in the desk, with the technical report collapsed underneath. Distinguish matching committed evidence without checkpoint acknowledgement, missing work, edited rows, missing/changed receipts, deleted committed rows, checkpoint-ahead state and dependency gaps. UNKNOWN identifies checkpoint versus destination failure using safe fixed messages. Do not include observed payloads, unexpected keys, arbitrary source values or raw exception strings.

Diagnosis is descriptive only. Status predicates, explicit missing-prefix selection, preview input, destination transactions and authorization remain the same. No new repair, retry, reset, remote adapter or arbitrary command capability. Reconcile reads the checkpoint before opening the destination so its failure diagnosis is deterministic if both are unavailable; all UNKNOWN results still block resume.

## Finite acceptance

- A new-process lost-ack crash reports matching row/receipt and absent checkpoint acknowledgement; only remaining work is allowed.
- Human edits, missing/changed receipts, deleted rows, checkpoint-ahead state and dependency gaps are distinguishable and fail closed.
- Corrupt/missing checkpoint and missing/corrupt destination yield specific UNKNOWN diagnostics without inferred evidence or a preview.
- Repeated diagnosis preserves checkpoint/database bytes; no altered values or unknown identifiers appear in output.
- Cancellation preserves observed evidence but allows no further work; stale bindings still reject.
- Desk presents readable text, clears stale diagnosis on errors, preserves token/Host/Origin gates, and fits mobile/keyboard workflows.
- Existing process-crash/retry regression suite passes. Independent review is against a frozen exact commit. Local checks only; no CI, merge or deployment.
