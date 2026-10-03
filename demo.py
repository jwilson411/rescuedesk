"""Bounded reproducible crash/restart demonstration; synthetic state only."""
import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time

import rescuedesk as rd


def child(*args):
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen([sys.executable, str(Path(rd.__file__).resolve()), *args], stdout=output, stderr=output, start_new_session=True)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError('worker exceeded 10 second limit; owned process group stopped')
        output.seek(0)
        data = output.read(65537)
        if len(data) > 65536:
            raise RuntimeError('worker exceeded output limit')
        return process.returncode, data.decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, help='new disposable local directory; defaults to temporary state removed after demo')
    args = parser.parse_args()
    temporary = tempfile.TemporaryDirectory() if args.state is None else None
    root = args.state or Path(temporary.name) / 'state'
    started = time.monotonic()
    try:
        rd.init(root)
        before = rd.reconcile(root)
        code, _ = child('resume', str(root), '--preview', before['preview'], '--effects', '1', '2', '3', '--crash', 'after-write-before-ack:2')
        assert code == 77
        code, output = child('reconcile', str(root))
        assert code == 0
        lost_ack = json.loads(output)
        assert lost_ack['statuses'] == {'1': 'VERIFIED', '2': 'VERIFIED', '3': 'MISSING'}
        code, output = child('resume', str(root), '--preview', lost_ack['preview'], '--effects', '3')
        assert code == 0
        with sqlite3.connect(root / 'application.sqlite') as db:
            actual = db.execute('SELECT key,payload FROM effects ORDER BY key').fetchall()
            assert actual == list(rd.EFFECTS.items())
            assert db.execute('SELECT count(*) FROM receipts').fetchone() == (3,)
        (root / 'checkpoint.json').write_text('{broken synthetic checkpoint')
        ambiguous = rd.reconcile(root)
        assert set(ambiguous['statuses'].values()) == {'UNKNOWN'}
        print(json.dumps({'synthetic': True, 'scenario': 'lost acknowledgement at effect 2; new-process reconciliation and resume; corrupt checkpoint',
                          'after_crash': lost_ack['statuses'], 'resumed': ['3'], 'independent_readback': actual,
                          'ambiguous': ambiguous, 'elapsed_seconds': round(time.monotonic() - started, 4)}, indent=2))
    finally:
        if temporary:
            temporary.cleanup()


if __name__ == '__main__':
    main()
