"""Spuštění celé analýzy od zpracování dat po vygenerování webu (report/).

Použití:  python scripts/run_all.py
Předpoklad: data stažená skriptem scripts/download.py. Trvá zhruba 5–10 minut.
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ['etl', 'geo', 'integrity', 'seats', 'anomalies', 'missing', 'stacks', 'year2018', 'typos', 'batches',
         'fingerprints', 'materiality', 'findings', 'se_etl', 'se_audit', 'build_site']


def year2018():
    """Detektory sdílení hlasů, chybějících balíků a nulových hlasů pro rok 2018 (srovnávací rok na webu)."""
    sys.path.insert(0, HERE)
    from common import RES
    import anomalies, missing, stacks
    R = anomalies.share_residuals(2018); R.to_pickle(f'{RES}/shares_2018.pkl')
    anomalies.zero_votes(R).to_pickle(f'{RES}/zeros_2018.pkl')
    missing.detect(2018).to_pickle(f'{RES}/missing_2018.pkl')
    stacks.run(2018).to_pickle(f'{RES}/stacks_2018.pkl')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'year2018':
        year2018(); sys.exit(0)
    root = os.path.dirname(HERE)
    if not os.path.isdir(os.path.join(root, 'data', 'raw', 'kv2026')):
        sys.exit('Chybí zdrojová data – nejdřív spusťte: python scripts/download.py')
    for d in ('data/processed', 'data/results', 'report/data', 'report/assets'):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    for s in STEPS:
        t = time.time()
        print(f'== {s}', flush=True)
        cmd = [sys.executable, '-X', 'utf8', os.path.join(HERE, 'run_all.py'), 'year2018'] if s == 'year2018' else \
              [sys.executable, '-X', 'utf8', os.path.join(HERE, f'{s}.py')]
        r = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL if s != 'build_site' else None)
        if r.returncode:
            sys.exit(f'Krok {s} selhal (kód {r.returncode}).')
        print(f'   hotovo za {time.time() - t:.0f} s', flush=True)
    print('Web je v', os.path.join(os.path.dirname(HERE), 'report', 'index.html'))
