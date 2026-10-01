# RescueDesk — v0.1 plan

2026-10-01 · private · deterministic local fixtures first

## User pain and distinction hypothesis

After a runner crashes, an operator cannot tell which actions committed and risks duplicating effects by restarting the whole task.

A recovery desk that reconciles destination state against intended effects may complement durable workflow engines with operator-visible evidence. Validate lost-acknowledgement and partial-write cases; do not claim to replace Temporal or guarantee general exactly-once execution.

## v0.1 boundary

A local synthetic SQLite job with three effects, named crash points, reconciliation report and explicit resume of only verified-missing work. Reuse agent-faultlab recovery harness and Pipeline Proof contract/readback concepts through optional adapters. No production supervisor, payments, arbitrary remote writes or autonomous resume of unknown effects.

## Architecture and contracts

**Data model:** RecoveryRun(id, contractVersion, sourceVersion), IntendedEffect(id, key, payloadHash, target), Observation(version, outcome), Reconciliation(status: verified/missing/conflict/unknown), ResumePlan(expectedTargetVersion, allowedEffectIds), Receipt. A checkpoint is evidence of progress, not proof of destination state.

**Flow:** Read immutable intent and actual destination state; classify each effect using the adapter contract. Resume only missing effects with still-valid scoped authorization and idempotency keys in a transaction. Conflicts/unknowns block dependent work. Local crash harness kills the synthetic worker at named boundaries; Pipeline Proof verifies destination contract independently. Pin tested upstream commits and check licenses before importing; existing repositories remain read-only.

**Local API:** POST /recoveries from local allowlisted fixture ID; GET /recoveries/{id}/reconcile; POST /recoveries/{id}/resume with bound target version and explicit missing effect IDs. Never accept arbitrary shell command strings. Invalid or corrupted state yields unknown and a diagnostic, not optimistic success.

## Execution and ownership contract

Planning foundation only: no implementation or working demo exists yet. The implementation owner must record fixture behavior honestly and add runnable instructions, evidence and tests before claiming v0.1 completion.

One exclusive implementation child owns this repository after handoff. Parent/planning work stops writing it. No other repository is an implementation dependency in v0.1; shared concepts are documented, not extracted into a shared package. Do not modify existing NAS projects.

Choose Python 3.11+ standard library for local HTTP/SQLite/domain logic and plain HTML/CSS/JavaScript for the viewer; no runtime downloads needed. Use unittest for core invariants and a browser smoke script/manual checklist for UI. An existing local browser automation install may be reused; no new credentials or paid providers. Persist runtime SQLite and raw captures outside git. Serve on loopback only with a per-run session token, Host/Origin checks, mutation protection and bounded inputs; no permissive CORS. Render imports as text, never execute them. Keyboard navigation and accessible status/conflict announcements are required.

Vercel may later host an approved interface; privileged browser/extension/container runners remain local. Initial deployment is local only, incremental provider spend is $0, and CI is not enabled automatically. The NAS stores durable sources, not proof of database transaction durability or a backup guarantee: use local SQLite runtime storage, then copy sanitized exports. Run identifiers, schema versions and command IDs are explicit. Tests must fail on violated invariants rather than mirror implementation.

## Privacy, security and release limits

Private GitHub repository. No public release, telemetry, external messaging, paid services or new credentials. Use synthetic fixture data and clearly label deterministic actors. Real-agent integration is deferred pending separately established access. Sanitize evidence before disk/export, retain only the minimum, and expose local deletion. Treat fixture text, imported bundles and agent output as untrusted. Do not record private model reasoning. Local host/operator compromise, unlabeled secrets and unsupported adapters remain outside guarantees. Licensing is undecided: no open-source LICENSE is granted; see LICENSE-DECISION.md.

## Completion gate and validation

All product-specific acceptance/adversarial cases below must pass with reproducible evidence and one runnable local demo; exports must contain only synthetic/sanitized data. Document each known coverage gap. Core fixtures should use logical time and stable IDs; measured performance must use real clocks and be labeled separately. Initial target: 1,000 fixture events or 100 board entities, bounded input/output, and interactive response within one second on the developer machine; publish the measured environment rather than claiming a benchmark. Do not claim cancellation, secrecy, exact replay or recovery outside the stated boundary.

## Open validation questions

Recruit 3–5 target users after the local prototype; measure whether the pain is frequent and whether the UI improves the task. Choose the first real adapter only after evidence from v0.1. Naming is a working title, not trademark clearance. Licensing, distribution and hosted production deployment require later decisions.

## Acceptance and adversarial cases

1. Crash before effect, after commit before receipt, and mid-sequence; reconcile correctly and resume only missing work.
2. Repeat resume after lost acknowledgement: committed effect count stays one per supported idempotency key.
3. Corrupt checkpoint, unavailable destination, changed schema or stale source: unknown/conflict blocks unsafe resume.
4. Destination drift after preview: CAS rejects; completed effects are not rewritten.
5. Harness runtime/output limits stop child process groups; independent readback verifies final effects rather than trusting worker done event.

## Two-week milestones

- Week 1: Days 1–2 inspect/pin upstream seams and define reconciliation contract; days 3–4 implement destination adapter and classifier; day 5 replay crash fixtures.
- Week 2: Days 6–8 build recovery desk and bounded resume; days 9–10 fault matrix, independent verification and operational limits/runbook.

## Longer-term path

One real destination adapter with separately established access, then supported workflow-engine integrations. Preserve unknown classification where a destination cannot prove completion.

## Reuse and comparison sources

[agent-faultlab](https://github.com/jwilson411/agent-faultlab) has a bounded local crash/restart harness and synthetic idempotency oracle; its README was inspected through GitHub. [Pipeline Proof](https://github.com/jwilson411/pipeline-proof) has contract/run/version-bound destination verification; `/Volumes/Vaults/Code/pipeline-proof/README.md` was inspected. Neither supplies a general production recovery guarantee. [Temporal durable AI](https://docs.temporal.io/ai) describes durable workflow resumption; RescueDesk must validate its reconciliation UI benefit rather than claim workflow resumption is novel. Pin upstream revisions during implementation, not an unverified current branch.
