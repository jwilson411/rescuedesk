# Local v0.1 verification

Synthetic fixture only. Python 3.12.3 / Linux. No provider calls, runtime dependencies, hosted CI, or paid services.

Commands:

```sh
python3 -m unittest discover -s tests -v
python3 demo.py
python3 -m py_compile rescuedesk.py server.py demo.py
```

The crash matrix executes 12 real worker exits (four boundaries × three effects), then uses new processes for reconciliation/resume. Direct SQLite readback checks exact effect rows and three receipts. Concurrent same-preview callers produce one successful writer and one rejected stale caller. HTTP checks require a local socket permission in the sandbox; the approved loopback run passed.

`demo.json` is a sanitized deterministic scenario report; its elapsed time is a single measured wall-clock sample on this machine, not a benchmark. No state paths, session tokens, user data, or private reasoning are exported.

Browser acceptance checklist (producer smoke completed below): token entry is keyboard accessible; reconcile announces status; missing effects enable resume; completed/cancelled/UNKNOWN state disables it; stale previews show a readable rejection. The HTML uses native controls, an aria-live status region, visible focus, and textContent. Automated HTTP tests do not establish actual browser rendering/accessibility quality.

Known plan deviations: fixed single fixture/single run, CLI initialization instead of POST creation, three-effect workload only, cancellation serialized after active batch, no real-adapter comparison, no power-loss/storage durability testing. These are bounded v0.1 limitations, not release guarantees.

## Browser smoke against cca2ebd

In-app browser, isolated background tabs, disposable `/tmp` fixture, 127.0.0.1-only server. Verified token entry; keyboard Tab/Enter reconciliation; MISSING report enables resume; resume produces three VERIFIED effects and disables retry; cancellation preserves verified effects and sets blocked. A separately restarted fixture crashed after effect 2's application commit; browser readback showed VERIFIED/VERIFIED/MISSING. Completing effect 3 in a CLI process made the browser's retained preview stale; clicking resume rejected it visibly, and reconciliation showed the final state.

Reset was tested by stopping the owned server, deleting only the named disposable directory, then initializing a fresh run. Both owned servers were stopped, tabs closed, viewport reset, and final disposable state deleted. No persistent background service remains.

390×844 mobile inspection found horizontal overflow from the 64-character preview hash; tracked for the follow-up fix. Desktop result screenshot `browser-cancelled.jpg` clears the session-token field before capture. Basic keyboard interaction passed; comprehensive screen-reader accessibility remains untested.

## Mobile correction

Applied overflow-wrap:anywhere to the report and bounded controls to available width. Fresh 390×844 browser smoke with the full preview hash reports document clientWidth=375 and scrollWidth=375 (15px scrollbar), so no horizontal overflow. Sanitized full-page screenshot: browser-mobile.jpg. This follow-up changes CSS and documentation only; recovery runtime remains identical to cca2ebd.

Independent reviewer at /home/ai-bot/Documents/Codex/2026-10-02/task-23/review passed 27 independently scripted recovery/corruption scenarios on cca2ebd. Original NO-GO was for mobile overflow and independently blocked HTTP/browser verification, not a demonstrated recovery safety failure. Final reviewer disposition remains a separate gate.
