"""Spuštění celé analýzy od zpracování dat po vygenerování webu (report/).

Použití:  python scripts/run_all.py [--units praha,brno,...|--units orp|--units pou] [--keep-going] [--no-global]
Předpoklad: data stažená skriptem scripts/download.py. Krajská města trvají zhruba 15 minut, všechna sídla ORP několik hodin.
Komunální volby se počítají postupně pro každou jednotku (proměnná AUDIT_UNIT), pak senát a web.
--units orp     jen sídla obcí s rozšířenou působností (bez krajských měst), od největšího
--units pou     jen sídla pověřených obecních úřadů (bez ORP a krajských měst), od největšího
--keep-going    chyba v jedné jednotce nezastaví ostatní (zapíše se do data/results/kv/_chyby.txt)
--no-global     bez senátu a sestavení webu
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import units as _units
_units.units()  # registr jednotek (data/processed/units_2026.json) musí existovat dřív, než se načte common.CITIES
from common import CITIES

KV_STEPS = ['etl', 'geo', 'integrity', 'seats', 'anomalies', 'missing', 'stacks', 'year2018', 'typos', 'batches',
            'fingerprints', 'materiality', 'findings', 'build_unit']
GLOBAL_STEPS = ['se_etl', 'se_audit', 'se_kolo2', 'build_site']


def year2018():
    """Detektory sdílení hlasů, chybějících balíků a nulových hlasů pro rok 2018 (srovnávací rok na webu)."""
    from common import RES
    import anomalies, missing, stacks
    R = anomalies.share_residuals(2018); R.to_pickle(f'{RES}/shares_2018.pkl')
    anomalies.zero_votes(R).to_pickle(f'{RES}/zeros_2018.pkl')
    missing.detect(2018).to_pickle(f'{RES}/missing_2018.pkl')
    stacks.run(2018).to_pickle(f'{RES}/stacks_2018.pkl')


def run(step, unit=None):
    if step == 'build_unit' and unit == 'praha':  # Praha má ručně psané stránky v build_site.py
        return 0.0
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    if unit:
        env['AUDIT_UNIT'] = unit
    if step == 'year2018':
        cmd = [sys.executable, '-X', 'utf8', os.path.join(HERE, 'run_all.py'), 'year2018']
    else:
        if step == 'findings' and unit != 'praha':
            step = 'findings_auto'  # pražské nálezy jsou ručně ověřené, ostatní města generuje šablona
        cmd = [sys.executable, '-X', 'utf8', os.path.join(HERE, f'{step}.py')]
    t = time.time()
    r = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL if step != 'build_site' else None)
    if r.returncode:
        raise RuntimeError(f'Krok {step} ({unit or "společný"}) selhal (kód {r.returncode}).')
    return time.time() - t


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'year2018':
        year2018(); sys.exit(0)
    root = os.path.dirname(HERE)
    if not os.path.isdir(os.path.join(root, 'data', 'raw', 'kv2026')):
        sys.exit('Chybí zdrojová data – nejdřív spusťte: python scripts/download.py')
    for d in ('data/processed', 'data/results', 'report/data', 'report/assets'):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    units = [u['slug'] for u in _units.units() if u['typ'] == 'krajske']
    if '--units' in sys.argv:
        a = sys.argv[sys.argv.index('--units') + 1]
        units = [u['slug'] for u in _units.units() if u['typ'] == a] if a in ('orp', 'pou') else a.split(',')
    keep = '--keep-going' in sys.argv
    for u in units:
        t = time.time()
        print(f'== komunální volby: {u}', flush=True)
        try:
            for s in KV_STEPS:
                run(s, u)
        except RuntimeError as e:
            if not keep:
                sys.exit(str(e))
            print('   CHYBA:', e, flush=True)
            with open(os.path.join(root, 'data', 'results', 'kv', '_chyby.txt'), 'a', encoding='utf-8') as f:
                f.write(f'{u}\t{e}\n')
            continue
        print(f'   hotovo za {time.time() - t:.0f} s', flush=True)
    if '--no-global' in sys.argv:
        sys.exit(0)
    for s in GLOBAL_STEPS:
        print(f'== {s}', flush=True)
        print(f'   hotovo za {run(s):.0f} s', flush=True)
    print('Web je v', os.path.join(root, 'report', 'index.html'))
