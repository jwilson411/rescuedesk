# RescueDesk

After a runner crashes, an operator cannot tell which actions committed and risks duplicating effects by restarting the whole task.

Private planning foundation, dated 2026-10-01. No implementation yet. Read [PLAN.md](PLAN.md) for the v0.1 boundary, architecture and delivery gates.

**Initial slice:** A local synthetic SQLite job with three effects, named crash points, reconciliation report and explicit resume of only verified-missing work. Reuse agent-faultlab recovery harness and Pipeline Proof contract/readback concepts through optional adapters. No production supervisor, payments, arbitrary remote writes or autonomous resume of unknown effects.

**Implementation handoff:** one exclusive owner; start from the planning commit on `main`, create an implementation branch, and preserve these scope limits. Do not deploy or enable paid services.

License decision pending; no public distribution authorized.
