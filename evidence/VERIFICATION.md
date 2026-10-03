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

Browser acceptance checklist (requires manual/browser verification): token entry is keyboard accessible; reconcile announces status; missing effects enable resume; completed/cancelled/UNKNOWN state disables it; stale previews show a readable rejection. The HTML uses native controls, an aria-live status region, visible focus, and textContent. Automated HTTP tests do not establish actual browser rendering/accessibility quality.

Known plan deviations: fixed single fixture/single run, CLI initialization instead of POST creation, three-effect workload only, cancellation serialized after active batch, no real-adapter comparison, no power-loss/storage durability testing. These are bounded v0.1 limitations, not release guarantees.
