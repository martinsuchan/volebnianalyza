import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
SP = os.path.dirname(os.path.abspath(__file__))
U = json.load(open(r'C:\git\volebni-analyza\data\processed\units_2026.json', encoding='utf-8'))
sel = [u['slug'] for u in U if u.get('typ') in ('krajske', 'orp') and u['slug'] != 'praha']
Y = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
PY = r'C:\git\volebni-analyza\.venv\Scripts\python.exe'
def run(s):
    if os.path.exists(os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'results', '_p8p9'), f'{s}_{Y}_p9.pkl')):
        return s, 0, ''
    env = dict(os.environ, AUDIT_UNIT=s, AUDIT_YEAR=str(Y), PYTHONIOENCODING='utf-8')
    r = subprocess.run([PY, os.path.join(SP, 'pravidla_p8_p9.py'), str(Y)], env=env, capture_output=True, text=True, encoding='utf-8', cwd=r'C:\git\volebni-analyza')
    return s, r.returncode, r.stderr[-400:]
with ThreadPoolExecutor(6) as ex:
    for i, (s, rc, err) in enumerate(ex.map(run, sel), 1):
        print(i, s, 'OK' if rc == 0 else 'CHYBA ' + err, flush=True)
