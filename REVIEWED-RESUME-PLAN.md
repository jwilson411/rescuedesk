# Staged recovery through a reviewed missing prefix

Base: reviewed `3bc5fa3260d407344d2ca132cefbe7ccb30a3f0a`; PR1 and PR2 remain frozen.

## Demonstrable gap

The backend and CLI already accept an explicit ordered missing prefix. The desk always submitted every remaining effect directly, so an operator could not resume one step and inspect its result before continuing. This increment exposes that existing capability through a reviewable end-to-end workflow.

Reconcile → choose how far this attempt should go → review the exact effect list → execute that reviewed list. The default is one next effect, and review itself performs no request or write. Discarding only removes the in-memory plan. Choosing a longer prefix remains an explicit action; skipping a prerequisite is unavailable.

`recovery_plan.js` holds bounded presentation state. `server.py` embeds this local file into the existing page; no new route, dependency download, endpoint, persistent grant or external asset is introduced. Core/domain/diagnosis code is unchanged. The server still owns all checks of preview freshness, missing-prefix selection, cancellation and transaction safety.

Prepared plans are invalidated by new observations, selection changes, token edits, cancellation requests and errors. A submitted plan is consumed immediately, even if the response is lost; there is no automatic replay. Controls are disabled during an in-flight request, preventing older overlapping responses from replacing a newer review. Browser reload discards the plan. These UX constraints do not replace the server's authorization checks.

## Verification

- 19 Python tests passed, including the existing crash/corruption suite and an extended HTTP flow that commits only effect1, verifies exact SQL state, then submits effects2/3 against the new observation and rejects the old request.
- 10 dependency-free Node presentation-state tests passed: preparation/discard, exact selected prefix, single consumption, next-step default, selection/report/token/error invalidation, blocked/malformed report rejection and defensive copies. Node is needed only to run these development checks, not to serve the app.
- Fresh isolated browser against disposable local SQLite: prepare/discard wrote zero rows; selection change hid the prepared plan; one-effect execution wrote only effect1; another local process committed effect2, making the prepared browser plan stale; stale submission was rejected and did not write effect3; fresh review then keyboard execution completed only effect3. Final independent SQL readback found exactly three rows/receipts, version3; cancellation blocked further planning.
- Token edit cleared the prepared plan and observation. Mobile test exposed native fieldset minimum-width overflow; corrected min-width and wrapping, then verified actual390×844 rendering with clientWidth=scrollWidth=390. Saved PNG reopened visually and decoded fully; the viewport excludes the token input.

Evidence: evidence/resume-plan-tests.txt, resume-plan-state-tests.txt, resume-plan-browser.json and resume-plan-mobile.png. Existing agent-browser/Chromium installations were reused in a unique namespace; no dependency installation, provider call or paid CI. Browser session closed; owned server/state cleanup completed before handoff.

## Remaining limits

This is one fixed three-effect synthetic adapter. A prepared browser plan is not durable approval and cannot be imported or replayed. The UI's current-state check is an observation, not a guarantee against subsequent changes; the server revalidates. Existing process-failure, single-user, local-filesystem and cancellation-after-active-batch limits remain. No production adapter, general exactly-once, power-loss or comprehensive accessibility guarantee is added.
