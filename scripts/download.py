"""Stažení všech zdrojových dat ČSÚ do data/raw/ ve struktuře, kterou očekává pipeline.

Použití:  python scripts/download.py [--force]

Stahuje (jen standardní knihovna Pythonu):
  - okrskové CSV, registry a číselníky KV 2018, 2022, 2026 a Senátu 2018, 2020, 2022, 2026
    (názvy souborů se zjišťují z indexových stránek volby.gov.cz/opendata, protože ČSÚ při opravách dat mění datum v názvu)
  - XML dávky volební noci 2026 (KV, Senát 1. a 2. kolo) a souhrnné výsledky Senátu 2026 (vysledky.xml, obě kola)
  - hranice volebních okrsků 2022 (GeoJSON)
Již stažené soubory se přeskakují (--force je stáhne znovu).
"""
import os, re, sys, time, zipfile
import urllib.request, urllib.error

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW = os.path.join(ROOT, 'data', 'raw')
BASE = 'https://volby.gov.cz'
# ČSÚ blokuje požadavky bez běžné hlavičky prohlížeče
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
FORCE = '--force' in sys.argv

DATASETS = [  # (složka v data/raw, indexová stránka otevřených dat)
    ('kv2026', '/opendata/kv2026/kv2026_opendata.htm'),
    ('kv2022', '/opendata/kv2022/kv2022_opendata.htm'),
    ('kv2018', '/opendata/kv2018/kv2018_opendata.htm'),
    ('se2026', '/opendata/se2026/se2026_opendata.htm'),
    ('se2022', '/opendata/se2022/se2022_opendata.htm'),
    ('se2020', '/opendata/se2020/se2020_opendata.htm'),
    ('se2018', '/opendata/se2018/se2018_opendata.htm'),
]
BATCHES = [  # (cílová složka, URL dávky se zástupným číslem)
    ('kv2026/davky', '/appdata/kv2026/20261009/odata/okrsky/vysledky_okrsky_{n:05d}.xml'),
    ('se2026/davky', '/appdata/senat/20261009/odata/okrsky/K1/vysledky_okrsky_{n:05d}.xml'),
    ('se2026/davky_k2', '/appdata/senat/20261009/odata/okrsky/K2/vysledky_okrsky_{n:05d}.xml'),
]
# souhrnné výsledky (oficiální součty obvodů a zvolení) – stahují se vždy znovu, protože se během sčítání mění
SUMMARIES = [('se2026/vysledky_souhrn.xml', '/appdata/senat/20261009/odata/vysledky.xml')]
GEO = ('geo/vol_okrsky_2022g100.geojson', '/opendata/kv2022/geo/vol_okrsky_2022g100.geojson')


def get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if i == retries - 1:
                raise
        except urllib.error.URLError:
            if i == retries - 1:
                raise
        time.sleep(3 * (i + 1))


def save(rel, url):
    path = os.path.join(RAW, rel)
    if os.path.exists(path) and not FORCE:
        return path, False
    data = get(url)
    if data is None:
        return None, False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    return path, True


def extract(zpath):
    """Rozbalí zip do složky se stejným názvem; odmítne cesty mimo cílovou složku."""
    dest = zpath[:-4]
    if os.path.isdir(dest) and not FORCE:
        return
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            target = os.path.realpath(os.path.join(dest, m.filename))
            if not target.startswith(os.path.realpath(dest) + os.sep):
                raise RuntimeError(f'Nebezpečná cesta v archivu {zpath}: {m.filename}')
        z.extractall(dest)


def kind(name):
    n = name.lower()
    return 'data' if 'data' in n else 'reg' if 'reg' in n else 'cis' if 'cis' in n else None


def datasets():
    for folder, page in DATASETS:
        html = get(BASE + page)
        if html is None:
            print(f'! {folder}: stránka {page} nenalezena'); continue
        links = sorted(set(re.findall(r'href="([^"/]+_csv\.zip)"', html.decode('utf-8', 'replace'))))
        latest = {}
        for l in links:  # při více verzích téhož souboru vezmi poslední (datum v názvu)
            k = kind(l)
            if k and (k not in latest or l > latest[k]):
                latest[k] = l
        if set(latest) != {'data', 'reg', 'cis'}:
            print(f'! {folder}: nečekaný seznam souborů {links}')
        url_dir = page.rsplit('/', 1)[0]
        for k, l in sorted(latest.items()):
            path, new = save(f'{folder}/{l}', f'{BASE}{url_dir}/{l}')
            extract(path)
            print(f'{folder}: {l} {"staženo" if new else "už existuje"}')


def batches():
    for folder, pattern in BATCHES:
        n, miss, got = 1, 0, 0
        while miss < 3 and n < 1000:  # dávky jsou číslované od 1; konec = tři chybějící po sobě
            path, new = save(f'{folder}/d{n:05d}.xml', BASE + pattern.format(n=n))
            if path is None:
                miss += 1
            else:
                miss = 0; got += 1
                if new:
                    time.sleep(0.2)
            n += 1
        print(f'{folder}: {got} dávek')


if __name__ == '__main__':
    os.makedirs(RAW, exist_ok=True)
    datasets()
    batches()
    for rel, url in SUMMARIES:
        data = get(BASE + url)
        if data is not None:
            open(os.path.join(RAW, rel), 'wb').write(data)
            print(f'{rel}: staženo (aktuální stav)')
    path, new = save(GEO[0], BASE + GEO[1])
    print(f'{GEO[0]}: {"staženo" if new else "už existuje"}')
    print('Hotovo. Data jsou v', RAW)
