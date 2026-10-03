import http.client
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import unittest

import rescuedesk as rd


class ServerTests(unittest.TestCase):
    def test_loopback_auth_origin_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'state'
            rd.init(root)
            with tempfile.TemporaryFile(mode='w+') as output:
                proc = subprocess.Popen([sys.executable, str(Path(rd.__file__).resolve()), 'serve', str(root), '--port', '0'], stdout=output, stderr=output, start_new_session=True)
                try:
                    import time
                    deadline = time.monotonic() + 5
                    lines = []
                    while time.monotonic() < deadline:
                        output.seek(0)
                        lines = output.read().splitlines()
                        if len(lines) >= 2:
                            break
                        time.sleep(.02)
                    self.assertGreaterEqual(len(lines), 2)
                    port = int(lines[0].rsplit(':', 1)[1])
                    token = lines[1].split(': ', 1)[1]
                    def request(method, path, body=None, headers=None):
                        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                        conn.request(method, path, body, headers or {})
                        response = conn.getresponse()
                        result = response.status, response.read()
                        conn.close()
                        return result
                    self.assertEqual(request('GET', '/')[0], 200)
                    self.assertEqual(request('GET', '/api/reconcile')[0], 403)
                    auth = {'X-Session-Token': token}
                    self.assertEqual(request('GET', '/api/reconcile', headers={**auth, 'Host': 'evil.invalid'})[0], 403)
                    self.assertEqual(request('GET', '/api/reconcile', headers={**auth, 'Origin': 'https://evil.invalid'})[0], 403)
                    status, body = request('GET', '/api/reconcile', headers=auth)
                    self.assertEqual(status, 200)
                    report = json.loads(body)
                    headers = {**auth, 'Content-Type': 'application/json'}
                    payload = json.dumps({'preview': report['preview'], 'effects': report['allowed']})
                    status, body = request('POST', '/api/resume', payload, headers)
                    self.assertEqual(status, 200)
                    self.assertEqual(set(json.loads(body)['statuses'].values()), {'VERIFIED'})
                    self.assertEqual(request('POST', '/api/resume', payload, headers)[0], 409)
                    self.assertEqual(request('POST', '/api/cancel', 'x' * 4097, headers)[0], 409)
                    self.assertEqual(request('POST', '/api/cancel', '{}', headers)[0], 200)
                finally:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=5)
