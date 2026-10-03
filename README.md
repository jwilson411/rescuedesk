# RescueDesk

A private local recovery desk for one deterministic synthetic ticket workflow. When a worker stops between an application commit and its acknowledgement, RescueDesk reads the destination, shows evidence, and resumes only verified-missing work. Ambiguous state stays **UNKNOWN**. No agents, models, remote APIs, or real user data are involved.

## Run locally

Requires Linux/macOS, Python 3.11+ with SQLite, and a local filesystem for runtime state. No packages or downloads. Source may live on NAS; **do not put SQLite runtime on NAS**.

```sh
python3 demo.py
python3 -m unittest discover -s tests -v
python3 rescuedesk.py init /tmp/rescuedesk-example
python3 rescuedesk.py serve /tmp/rescuedesk-example --port 8765
```

Open `http://127.0.0.1:8765`, paste the server's per-run session token, then reconcile and explicitly resume the displayed missing effects. Server binds only `127.0.0.1`. Stop with Ctrl-C. Choose a fresh state path if it exists already. Delete only your disposable state directory after stopping its server/worker to remove all run data; no state is uploaded. Token is shown only in the local terminal and never in evidence exports.

`python3 demo.py` runs a bounded child worker, stops after the second effect commits but before its checkpoint acknowledgement, reconciles in a new process, and starts another process to commit only effect 3. It independently queries SQLite to prove the three expected rows and receipts. It then corrupts the checkpoint and demonstrates UNKNOWN. Temporary state is deleted automatically. `--state /tmp/new-rescuedesk-demo` retains the deliberately corrupt fixture for inspection; it must be a new directory.

For manual interruption:

```sh
python3 rescuedesk.py reconcile /tmp/rescuedesk-example
# Copy the returned preview and choose the displayed missing prefix:
python3 rescuedesk.py resume /tmp/rescuedesk-example --preview COPY_PREVIEW --effects 1 2 3 --crash after-write-before-ack:2
# Exit 77 is the intentional crash. Reconcile afresh, then resume only 3.
python3 rescuedesk.py reconcile /tmp/rescuedesk-example
python3 rescuedesk.py cancel /tmp/rescuedesk-example
```

Supported crash boundaries for each effect `1`, `2`, `3`: `before-write`, `during-write` (uncommitted application row), `after-write-before-ack`, `after-ack`. Exit 2 indicates a rejected operation. Reconcile returns a JSON report; inspect `blocked` and statuses rather than treating command exit 0 as success of the workflow.

## Contracts and recovery invariants

The immutable fixture consists of opening, assigning, and resolving a synthetic ticket. `checkpoint.json` identifies the run and fixture version, records acknowledged progress, and stores cancellation. `application.sqlite` is the independently observed application, with effects and ownership receipts. These are deliberately separate persistence boundaries.

* An application row and its ownership receipt commit in one SQLite transaction. A receipt includes the expected payload hash. The checkpoint acknowledgement happens afterwards, by atomic file replacement.
* VERIFIED requires the exact expected row and its destination receipt. Matching text alone is insufficient. A checkpoint receipt alone never proves application completion.
* MISSING requires absence of both destination row and receipt and no contrary checkpoint evidence. Edits, deleted committed rows, extra rows, and dependency gaps yield CONFLICT. Unreadable/corrupt state, unsupported schema/source, or absent destination yields UNKNOWN and no allowed effects.
* Resume requires an explicit ordered missing prefix and the current preview hash. The hash binds the complete observed fixture state, run, checkpoint, and destination version. It is rechecked inside `BEGIN IMMEDIATE` before each effect. Stale previews reject; completed effects are never rewritten. Unique keys prevent duplicate supported commits.
* An advisory run lock serializes supported processes; SQLite transactions protect destination writes. Two callers using the same preview produce one winner. A fresh reconciliation after lost acknowledgement excludes the already committed effect.
* Cancellation blocks subsequent resume after acquiring the run lock. It **waits for an active resume batch to finish**; it does not interrupt it, roll back existing effects, or undo commits. UNKNOWN and CONFLICT require inspection; no force/repair button is supplied.

The local desk exposes `GET /api/reconcile`, `POST /api/resume`, and `POST /api/cancel` for one CLI-created run. This intentionally narrows the plan's multi-run API: fixture creation and crash injection remain CLI operations. Tokens, exact Host/Origin checks, no CORS, no external assets, CSP, text-only report rendering, bounded request bodies, and request timeouts protect the single-user loopback boundary.

## Verification and limits

See [evidence/demo.json](evidence/demo.json) and [evidence/VERIFICATION.md](evidence/VERIFICATION.md). Tests include all 12 crash/effect combinations, fresh-process restart, repeated/stale submissions, concurrent callers, human edits/deletion, missing ownership proof, corrupt checkpoints/database, stale source/schema, cancellation, and HTTP authorization checks.

This proves behavior only for the owned synthetic SQLite adapter under tested process termination. It does **not** claim universal exactly-once execution, power-loss durability, malicious operator resistance, or safe recovery for external effects. No real agent adapter exists. A person able to rewrite both destination evidence and checkpoint can forge history; coordinated deletion of all evidence cannot be distinguished from work never attempted. Such tampering is outside the supported model. Session tokens protect browser requests, not a compromised host.

The fixture is deliberately three effects, with a 4 MiB destination-file limit and 100-row observation limit. The broader plan's 1,000-event/100-entity workload has not been implemented or benchmarked. Harness workers are fixed, dependency-free programs, limited to 10 seconds with owned process-group termination on timeout and a 64 KiB captured-output read bound; arbitrary plugins/commands are unsupported. Output is spooled to a temporary file, so this is not a disk quota against malicious workers. OS power-loss, network filesystems, external agents, and cross-host recovery remain untested. No CI workflows are installed or enabled by this increment.

[OPERATOR.md](OPERATOR.md) covers inspection and disposable reset. [PLAN.md](PLAN.md) retains the original roadmap. License decision is pending; repository and draft PR remain private, with no public deployment authorized.
