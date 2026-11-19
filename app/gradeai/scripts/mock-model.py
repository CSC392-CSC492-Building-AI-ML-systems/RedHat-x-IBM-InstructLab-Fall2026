"""A stand-in for vLLM so you can try GradeAI without Fir. It returns made-up grades.

    npm run mock-model          # terminal 1 (python3 scripts/mock-model.py 8001 local-key)
    set -a; source .env; set +a
    GRADEAI_URL=http://127.0.0.1:8080 GRADEAI_WORKER_TOKEN=$WORKER_TOKEN \
      VLLM_URL=http://127.0.0.1:8001/v1 VLLM_API_KEY=local-key MODEL_NAME=mock \
      python3 scripts/gradeai_worker.py
"""
import json, re, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
KEY = sys.argv[2] if len(sys.argv) > 2 else ''
LOG = []
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _auth(self):
        return not KEY or self.headers.get('Authorization') == f'Bearer {KEY}'
    def _send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if not self._auth(): return self._send(401, {'error':'key'})
        if self.path.endswith('/models'): return self._send(200, {'data':[{'id':'gradeai-csc236'}]})
        self._send(404, {})
    def do_POST(self):
        if not self._auth(): return self._send(401, {'error':'key'})
        n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n))
        msgs = body['messages']; user = msgs[-1]['content']
        time.sleep(0.4)
        if 'Convert this grading rubric' in user:
            out = {'name':'A3 — Context-Free Grammars','assignment':'Assignment 3','instructions':'','criteria':[{'name':'Grammar','points':12,'description':'Correct CFG','levels':[{'label':'Full','points':12,'description':'ok'},{'label':'None','points':0,'description':'no'}]},{'name':'Proof','points':8,'description':'L(G)=L','levels':[]}]}
        else:
            names = re.findall(r'^\d+\. (.+?) — max (\d+) pts', user, re.M)
            low = 'lferreira' in user
            sid = re.search(r'(\d{10})', user)
            nm = re.search(r'<submission>\n([A-Z][a-z]+ [A-Z][a-z]+)', user)
            out = {'student_name': nm.group(1) if nm else None, 'student_id': sid.group(1) if sid else None,
                   'criteria':[{'name':n,'level':'Partial' if low else 'Full','earned': round(int(m)/2) if low else int(m)-(3 if i==2 else 0),'max':int(m),'note':f'Fine-tuned note about {n}.'} for i,(n,m) in enumerate(names)],
                   'summary':'Solid induction proof; one algebra slip in the step.','confidence': 55 if low else 93,'concerns': ['proof only sketched in comments'] if low else []}
        self._send(200, {'choices':[{'message':{'role':'assistant','content': '```json\n'+json.dumps(out)+'\n```'}}]})
ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
