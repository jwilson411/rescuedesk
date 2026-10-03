"""Single-user loopback desk; no external assets or provider calls."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sqlite3

from rescuedesk import cancel, reconcile, resume

PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>RescueDesk</title>
<style>body{font:18px system-ui;background:#101a29;color:#e6edf7;max-width:850px;margin:4rem auto;padding:1rem}button,input{max-width:100%;box-sizing:border-box;font:inherit;padding:.6rem;margin:.3rem}button:focus-visible,input:focus-visible{outline:3px solid #7cf}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1c2b41;padding:1rem}label{display:block}small{color:#bbd1ed}.effect{background:#1c2b41;padding:1rem;margin:1rem 0;border-radius:.4rem}.effect h2{font-size:1.05rem;margin-top:0}#diagnosis{list-style:none;padding:0}details{margin:1rem 0}</style>
<h1>RescueDesk</h1><p>Synthetic recovery desk · local v0.1</p><p>Destination evidence determines recovery. UNKNOWN and CONFLICT stop work.</p>
<label>Session token <input id="token" type="password" autocomplete="off"></label><button id="read">Reconcile actual state</button>
<p id="summary" role="status" aria-live="polite">Paste the token printed by the local server.</p>
<ul id="diagnosis" aria-label="Observed effect evidence"></ul>
<details><summary>Technical reconciliation report</summary><pre id="report">No observation yet.</pre></details>
<button id="resume" disabled>Resume displayed missing effects</button><button id="cancel">Cancel future work</button>
<p><small>Cancellation waits for an active resume to finish; it never undoes effects. A stale preview requires reconciliation. Use the CLI crash harness to interrupt the synthetic worker.</small></p>
<script>
let preview=null; const report=document.querySelector('#report'), res=document.querySelector('#resume'), summary=document.querySelector('#summary'), list=document.querySelector('#diagnosis');
function renderDiagnosis(data){
 summary.textContent=data.diagnosis.summary;
 for(const issue of data.diagnosis.issues){const item=document.createElement('li');item.textContent=issue;list.append(item);}
 for(const effect of data.diagnosis.effects){
  const item=document.createElement('li');item.className='effect';
  const heading=document.createElement('h2');heading.textContent=effect.label+' — '+effect.status;item.append(heading);
  for(const explanation of effect.explanations){const text=document.createElement('p');text.textContent=explanation;item.append(text);}
  const observed=document.createElement('small'), ev=effect.evidence;
  observed.textContent=ev?'Application row: '+(ev.row_present?'present':'absent')+' · Ownership receipt: '+(ev.receipt_present?'present':'absent')+' · Checkpoint acknowledgement: '+(ev.checkpoint_acknowledged?'recorded':'absent'):'Evidence unavailable; no completion inference.';
  item.append(observed);list.append(item);
 }
}
async function call(path, body){res.disabled=true;preview=null;list.replaceChildren();summary.textContent='Reading actual application state…';try{const response=await fetch(path,{method:body?'POST':'GET',headers:{'X-Session-Token':document.querySelector('#token').value,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw Error(data.error);preview=data;report.textContent=JSON.stringify(data,null,2);renderDiagnosis(data);res.disabled=!data.allowed?.length;}catch(e){preview=null;list.replaceChildren();summary.textContent=e.message;report.textContent='No current observation. Reconcile again.';}}
document.querySelector('#read').onclick=()=>call('/api/reconcile');res.onclick=()=>{if(preview)call('/api/resume',{preview:preview.preview,effects:preview.allowed});};document.querySelector('#cancel').onclick=()=>call('/api/cancel',{});
</script></html>'''


def serve(root, port):
    root = Path(root)
    if not root.is_dir():
        raise ValueError('initialize state first')
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *args):
            pass  # Never log session tokens or request bodies.

        def reply(self, status, value, html=False):
            data = value.encode() if html else json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)

        def permitted(self, api=True):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != origin.removeprefix('http://') or self.headers.get('Origin', origin) != origin:
                self.reply(403, {'error': 'Host/Origin rejected'})
                return False
            if api and not secrets.compare_digest(self.headers.get('X-Session-Token', '').encode(), token.encode()):
                self.reply(403, {'error': 'Session token required'})
                return False
            return True

        def do_GET(self):
            if not self.permitted(self.path != '/'):
                return
            if self.path == '/':
                self.reply(200, PAGE, True)
            elif self.path == '/api/reconcile':
                self.reply(200, reconcile(root))
            else:
                self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.permitted():
                return
            try:
                if self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
                    raise ValueError()
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError()
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError()
                if self.path == '/api/resume' and set(body) == {'preview', 'effects'}:
                    result = resume(root, body['preview'], body['effects'])
                elif self.path == '/api/cancel' and body == {}:
                    result = cancel(root)
                else:
                    raise ValueError()
                self.reply(200, result)
            except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
                self.reply(409, {'error': 'Rejected; reconcile again and inspect state'})

    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'RescueDesk synthetic only: http://127.0.0.1:{server.server_port}\nSession token: {token}', flush=True)
    server.serve_forever()
