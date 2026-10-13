"""Registr územních jednotek komunálních voleb (obec + její MČ/MO), které web zobrazuje.

Všechny obce: 13 krajských měst, sídla ostatních obcí s rozšířenou působností (ORP), sídla ostatních pověřených obecních úřadů (POU)
a ostatní obce (typ 'obec'). Stav analýzy: 'hotovo' (výsledky v data/results) nebo 'pripravuje' (jen základní údaje z ČSÚ).
Základní údaje se počítají z celostátních dat KV 2026 a ukládají do data/processed/units_2026.json.

Adresy (slug) a zobrazované názvy obcí určuje pevná tabulka data/obce_2026.csv, která je součástí repozitáře: jednou přidělená adresa
se nemění, i když přibudou další obce (v ČR je přes 600 jmen, která nese více obcí). Nové obce se do tabulky jen doplňují (mapa()).
"""
import csv, glob, json, os, re, sys, unicodedata
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

KRAJE = {1100: 'Hlavní město Praha', 2100: 'Středočeský kraj', 3100: 'Jihočeský kraj', 3200: 'Plzeňský kraj', 4100: 'Karlovarský kraj',
         4200: 'Ústecký kraj', 5100: 'Liberecký kraj', 5200: 'Královéhradecký kraj', 5300: 'Pardubický kraj', 6100: 'Kraj Vysočina',
         6200: 'Jihomoravský kraj', 7100: 'Olomoucký kraj', 7200: 'Zlínský kraj', 8100: 'Moravskoslezský kraj'}
KRAJSKA_MESTA = [554782, 582786, 554821, 554791, 563889, 500496, 554804, 569810, 544256, 555134, 585068, 586846, 554961]
# sídla ORP, která nejsou (nebo nejsou jako jediná) největším registračním úřadem ve svém správním obvodu
ORP_SIDLO = {2105: 'Černošice', 3212: 'Stod', 5315: 'Žamberk', 7204: 'Luhačovice', 7209: 'Valašské Klobouky', 8101: 'Bílovec',
             8117: 'Opava'}
HOTOVO = {554782}  # Praha (ručně psané stránky); ostatní města jsou hotová, pokud existuje data/results/kv/<slug>/summary.json
CACHE = os.path.join(ROOT, 'data', 'processed', 'units_2026.json')
MAPA = os.path.join(ROOT, 'data', 'obce_2026.csv')
MAPA_COLS = ['kod', 'slug', 'nazev', 'nazev_plny', 'obec', 'okres', 'okres_nazev', 'kraj']


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def okres_slug(okres_nazev):
    return slug(okres_nazev)


def mapa(rz=None, nuts=None):
    """Pevná tabulka obcí: kód obce -> slug (adresa kv/<slug>/), nazev (nadpis stránky), nazev_plny (vyhledávání, s okresem u stejnojmenných obcí).

    Existující řádky se nikdy nepřepisují. Nové obce: jméno, je-li v ČR jediné (po odstranění diakritiky), jinak jméno s okresem,
    a nestačí-li ani okres (dvě Březiny v okrese Brno-venkov), navíc kód obce; shodnou adresu po odstranění diakritiky (Pohled a Pohleď)
    odliší kód obce v adrese."""
    old = {}
    if os.path.exists(MAPA):
        with open(MAPA, encoding='utf-8', newline='') as f:
            old = {int(r['kod']): r for r in csv.DictReader(f)}
    if rz is None:
        return old
    o = rz[rz.TYPZASTUP == 1].drop_duplicates('KODZASTUP')
    o = o.assign(nm=o.NAZEVZAST.map(str).where(o.KODZASTUP != 554782, 'Praha'))
    o = o.assign(s=o.nm.map(slug), on=o.OKRES.map(lambda k: str(nuts.get(k, k))))
    ns = o.s.value_counts()
    nso = o.groupby(['nm', 'on']).size()
    if not old and os.path.exists(CACHE):  # první vytvoření: zachovat adresy už zveřejněných jednotek
        old = {u['kod']: dict(slug=u['slug'], nazev=u['nazev']) for u in json.load(open(CACHE, encoding='utf-8'))}
    used = {r['slug'] for r in old.values()}
    out = {}
    for r in o.sort_values('POCOBYV', ascending=False).itertuples():  # při kolizi dostane kratší adresu větší obec
        kod = int(r.KODZASTUP)
        plny = r.nm if ns[r.s] == 1 else f'{r.nm} (okres {r.on})'
        if ns[r.s] > 1 and nso[(r.nm, r.on)] > 1:  # stejné jméno i okres – odliší až kód obce
            plny = f'{r.nm} (okres {r.on}, kód obce {kod})'
        if kod in old:
            sl, nazev = old[kod]['slug'], old[kod]['nazev']
        else:
            nazev = plny
            sl = slug(nazev)
            if sl in used:
                sl = f'{sl}-{kod}'
        used.add(sl)
        out[kod] = dict(kod=kod, slug=sl, nazev=nazev, nazev_plny=old.get(kod, {}).get('nazev_plny') or (nazev if '(okres' in nazev else plny),
                        obec=r.nm, okres=int(r.OKRES), okres_nazev=r.on, kraj=int(r.KRAJ))
    assert len({r['slug'] for r in out.values()}) == len(out), 'duplicitní slug v mapě obcí'
    with open(MAPA, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, MAPA_COLS, lineterminator='\n')
        w.writeheader()
        for kod in sorted(out):
            w.writerow(out[kod])
    return out


def orp_seats(rz):
    """Kódy zastupitelstev sídel ORP (bez Prahy a krajských měst): registrační úřad s největším počtem obyvatel ve správním
    obvodu ORP, výjimky podle názvu (ORP_SIDLO)."""
    o = rz[rz.TYPZASTUP == 1].drop_duplicates('KODZASTUP')
    out = {}
    for orp, g in o.groupby('ORP'):
        if orp in ORP_SIDLO:
            c = g[g.NAZEVZAST == ORP_SIDLO[orp]]
        else:
            p = g[g.REGURAD == g.OBEC]
            c = (p if len(p) else g).sort_values('POCOBYV', ascending=False)
        if (set(g.KODZASTUP) & set(KRAJSKA_MESTA)) or orp == 1000:
            continue
        out[int(c.KODZASTUP.iloc[0])] = int(orp)
    return out


def pou_seats(rz, known):
    """Kódy zastupitelstev sídel pověřených obecních úřadů: obce, které jsou registračním úřadem (REGURAD) pro komunální volby
    (§ 21 zák. 491/2001 Sb.: registračním úřadem je pověřený obecní úřad). Bez obcí, které už registr obsahuje."""
    o = rz[rz.TYPZASTUP == 1].drop_duplicates('KODZASTUP')
    return [int(k) for k in o[o.OBEC.isin(set(o.REGURAD))].KODZASTUP if int(k) not in known]


def _compute():
    raw = os.path.join(ROOT, 'data', 'raw', 'kv2026')
    t3 = pd.read_csv(glob.glob(os.path.join(raw, '*data*_csv', 'csv', 'kvt3.csv'))[0], sep=';', encoding='cp1250', low_memory=False)
    rz = pd.read_csv(glob.glob(os.path.join(raw, '*reg*_csv', 'csv', 'kvrzcoco.csv'))[0], sep=';', encoding='cp1250', low_memory=False)
    nuts = pd.read_csv(glob.glob(os.path.join(raw, '*cis*_csv', 'csv', 'cnumnuts.csv'))[0], sep=';', encoding='cp1250').set_index('NUMNUTS').NAZEVNUTS
    M = mapa(rz, nuts)
    out = []
    orp = orp_seats(rz)
    o1 = rz[rz.TYPZASTUP == 1].drop_duplicates('KODZASTUP').set_index('KODZASTUP')
    pop = o1.POCOBYV
    pou = pou_seats(rz, set(KRAJSKA_MESTA) | set(orp))
    known = set(KRAJSKA_MESTA) | set(orp) | set(pou)
    ostatni = sorted((int(k) for k in o1.index if int(k) not in known), key=lambda k: -pop[k])
    t3g = dict(tuple(t3.groupby('KODZASTUP')))
    for kod in KRAJSKA_MESTA + sorted(orp, key=lambda k: -pop[k]) + sorted(pou, key=lambda k: -pop[k]) + ostatni:
        z = o1.loc[kod]
        city = t3g.get(kod, t3.iloc[:0])
        mcs = []
        uzemi = set(city.OBEC)
        for mk in sorted(set(t3[t3.OBEC.isin(uzemi) & (t3.TYPZASTUP == 2)].KODZASTUP)) if kod in known else []:  # zastupitelstva MČ/MO na území města
            zm = rz[(rz.KODZASTUP == mk)]
            mt = t3[t3.KODZASTUP == mk]
            mcs.append(dict(kod=int(mk), nazev=str(zm.NAZEVZAST.iloc[0]) if len(zm) else str(mk), mandatu=int(zm.MANDATY.iloc[0]) if len(zm) else None,
                            okrsku=int(len(mt)), volicu=int(mt.VOL_SEZNAM.sum())))
        m = M[kod]
        out.append(dict(kod=int(kod), nazev=m['nazev'], nazev_plny=m['nazev_plny'], slug=m['slug'], kraj=KRAJE.get(int(z.KRAJ), str(z.KRAJ)), krajkod=int(z.KRAJ),
                        okres=int(z.OKRES), okres_nazev=m['okres_nazev'], mandatu=int(z.MANDATY), okrsku=int(len(city)), volicu=int(city.VOL_SEZNAM.sum()),
                        ucast=float(city.VYD_OBALKY.sum() / city.VOL_SEZNAM.sum()) if len(city) else None, mc=mcs,
                        typ='krajske' if kod in KRAJSKA_MESTA else ('orp' if kod in orp else ('pou' if kod in pou else 'obec')), obyv=int(pop[kod]),
                        volby=bool(len(city)),  # False: volby se nekonaly (nikdo nekandidoval)
                        druh={1: 'obce', 6: 'městyse'}.get(int(z.DRUHZASTUP), 'města')))  # 2. pád: zastupitelstvo obce / města / městyse
    return out


def okres_url(u):
    return f'kv/okres/{okres_slug(u["okres_nazev"])}.html'


def okres_label(u):
    return u['okres_nazev'] if u['okres_nazev'].startswith('Hlavní') else f'Okres {u["okres_nazev"]}'


def units():
    if os.path.exists(CACHE):
        U = json.load(open(CACHE, encoding='utf-8'))
    else:
        U = _compute()
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(U, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for u in U:
        done = u['kod'] in HOTOVO or os.path.exists(os.path.join(ROOT, 'data', 'results', 'kv', u['slug'], 'summary.json'))
        u['stav'] = 'hotovo' if done else 'pripravuje'
        # vlastní stránku mají větší obce a obce s nálezem (build_unit.py); ostatní jsou řádkem v přehledu okresu
        u['stranka'] = u['kod'] in HOTOVO or os.path.exists(os.path.join(ROOT, 'report', 'kv', u['slug'], 'index.html'))
        u['url'] = f'kv/{u["slug"]}/index.html' if u['stranka'] else f'{okres_url(u)}#o-{u["kod"]}'
    return U


if __name__ == '__main__':
    if os.path.exists(CACHE):
        os.remove(CACHE)
    for u in units():
        print(u['nazev'], u['kraj'], u['okrsku'], len(u['mc']), u['stav'])
