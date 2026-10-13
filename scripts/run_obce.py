"""Dávkové zpracování mnoha obcí: stejné kroky jako run_all.py (KV_STEPS), ale v jednom procesu pro mnoho obcí.

Celostátní tabulky ČSÚ, hranice okrsků a XML dávky se načtou jednou na proces (common.MEMO) místo jednou na krok a obec,
takže malá obec trvá několik sekund místo zhruba minuty. Výsledky jsou totožné s run_all.py (kroky se spouštějí stejným kódem;
mezi obcemi se přepnou cesty a kód jednotky v common a v už načtených modulech a smaže se mezipaměť anomalies._CACHE).

Použití:  python scripts/run_obce.py [--typ obec|pou|orp|vse] [--okres 3210] [--units slug,slug] [--workers 6] [--znovu] [--kroky findings,build_unit]
  --typ      které jednotky zpracovat (výchozí: obec = obce mimo krajská města, ORP a POU)
  --okres    jen obce daného okresu (kód NUTS, např. 3210 = Písek)
  --workers  počet paralelních procesů (každý drží celostátní tabulky v paměti, ~1,5 GB)
  --znovu    zpracovat i obce, které už mají data/results/kv/<slug>/summary.json
  --kroky    jen vybrané kroky (např. po změně textů nálezů: findings,build_unit); výchozí všechny
Chyby se zapisují do data/results/kv/_chyby.txt; obce s volbami, které se nekonaly, se přeskočí.
Proces po DAVKA obcích skončí a spouštěč ho nahradí novým: v dlouho běžícím procesu se zpracování obce postupně zpomaluje
(po ~400 obcích z ~3 s na ~12 s), čerstvý proces je opět rychlý.
"""
import contextlib, io, json, os, runpy, subprocess, sys, time, traceback, warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
LOCK = os.path.join(ROOT, 'data', 'results', 'kv', '_lock')
CHYBY = os.path.join(ROOT, 'data', 'results', 'kv', '_chyby.txt')
DAVKA = 100  # obcí na jeden proces
POKRACOVAT = 3  # návratový kód procesu, který skončil po DAVKA obcích (zbývá práce)


def vyber(argv):
    import units as _units
    U = _units.units()
    typ = argv[argv.index('--typ') + 1] if '--typ' in argv else 'obec'
    if '--units' in argv:
        chci = argv[argv.index('--units') + 1].split(',')
        sel = [u for u in U if u['slug'] in chci]
    else:
        sel = [u for u in U if (typ == 'vse' or u['typ'] == typ) and u['slug'] != 'praha']
    if '--okres' in argv:
        ok = int(argv[argv.index('--okres') + 1])
        sel = [u for u in sel if u['okres'] == ok]
    sel = [u for u in sel if u.get('volby', True)]
    if '--znovu' not in argv:
        sel = [u for u in sel if not os.path.exists(os.path.join(ROOT, 'data', 'results', 'kv', u['slug'], 'summary.json'))]
    return [u['slug'] for u in sel]


def nastav(slug):
    """Přepne analyzovanou jednotku v common i ve všech už načtených modulech pipeline (hodnoty převzaté přes `from common import …`)."""
    import common
    os.environ['AUDIT_UNIT'] = slug
    val = dict(UNIT=slug, MAGISTRAT=common.CITIES[slug], P=os.path.join(common.P0, 'kv', slug), RES=os.path.join(common.RES0, 'kv', slug))
    os.makedirs(val['P'], exist_ok=True); os.makedirs(val['RES'], exist_ok=True)
    for k, v in val.items():
        setattr(common, k, v)
    for m in list(sys.modules.values()):
        f = getattr(m, '__file__', None)
        if not f or m is common or os.path.dirname(os.path.abspath(f)) != HERE:
            continue
        for k, v in val.items():
            if k in m.__dict__:
                m.__dict__[k] = v
        if isinstance(m.__dict__.get('_CACHE'), dict):
            m._CACHE.clear()


def zpracuj(slug, steps):
    import run_all
    nastav(slug)
    path0 = list(sys.path)
    for s in steps:
        if s == 'build_unit' and slug == 'praha':
            continue
        if s == 'year2018':
            run_all.year2018()
        else:
            if s == 'findings':
                s = 'findings_auto'
            runpy.run_path(os.path.join(HERE, f'{s}.py'), run_name='__main__')
        sys.path[:] = path0  # skripty si při každém spuštění přidávají vlastní adresář


def worker(slugs, steps=None):
    import run_all
    steps = steps or run_all.KV_STEPS
    warnings.filterwarnings('ignore')
    os.makedirs(LOCK, exist_ok=True)
    hotovo = 0
    for slug in slugs:
        if hotovo >= DAVKA:
            return POKRACOVAT
        try:
            os.mkdir(os.path.join(LOCK, slug))  # zámek: obec zpracuje jen jeden proces
        except FileExistsError:
            continue
        t = time.time()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                zpracuj(slug, steps)
            print(f'{slug} ok {time.time() - t:.1f}', flush=True)
            hotovo += 1
        except BaseException as e:  # noqa: BLE001 – chyba jedné obce nesmí zastavit dávku
            if isinstance(e, KeyboardInterrupt):
                raise
            msg = f'{type(e).__name__}: {e}'.replace('\n', ' ')[:300]
            print(f'{slug} CHYBA {msg}', flush=True)
            with open(CHYBY, 'a', encoding='utf-8') as f:
                f.write(f'{slug}\t{msg}\n')
            with open(os.path.join(LOCK, slug, 'traceback.txt'), 'w', encoding='utf-8') as f:
                f.write(traceback.format_exc())
    return 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--worker':  # interní: seznam obcí ze souboru
        sys.exit(worker(json.load(open(a[1], encoding='utf-8')), a[2].split(',') if len(a) > 2 else None))
    slugs = vyber(a)
    n = int(a[a.index('--workers') + 1]) if '--workers' in a else 1
    print(f'obcí ke zpracování: {len(slugs)}, procesů: {n}', flush=True)
    if not slugs:
        sys.exit(0)
    if os.path.isdir(LOCK):  # zámky z předchozího (přerušeného) běhu
        import shutil
        shutil.rmtree(LOCK)
    lst = os.path.join(ROOT, 'data', 'results', 'kv', '_fronta.json')
    json.dump(slugs, open(lst, 'w', encoding='utf-8'))
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    t0 = time.time()
    kroky = [a[a.index('--kroky') + 1]] if '--kroky' in a else []
    cmd = [sys.executable, '-X', 'utf8', os.path.abspath(__file__), '--worker', lst] + kroky
    ps = [subprocess.Popen(cmd, env=env) for _ in range(n)]
    rc = []
    while ps:  # proces, který skončil po DAVKA obcích, nahradí nový
        time.sleep(1)
        for p in [p for p in ps if p.poll() is not None]:
            ps.remove(p)
            if p.returncode == POKRACOVAT:
                ps.append(subprocess.Popen(cmd, env=env))
            else:
                rc.append(p.returncode)
    print(f'hotovo za {(time.time() - t0) / 60:.1f} min, návratové kódy {rc}', flush=True)
