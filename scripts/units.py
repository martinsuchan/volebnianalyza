"""Registr územních jednotek komunálních voleb (obec + její MČ/MO), které web zobrazuje.

Zatím: 13 krajských měst, sídla ostatních obcí s rozšířenou působností (ORP) a sídla ostatních pověřených obecních úřadů (POU). Stav analýzy: 'hotovo' (výsledky v data/results) nebo 'pripravuje' (jen základní údaje z ČSÚ).
Základní údaje se počítají z celostátních dat KV 2026 a ukládají do data/processed/units_2026.json.
"""
import glob, json, os, re, sys, unicodedata
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


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


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
    out = []
    orp = orp_seats(rz)
    pop = rz[rz.TYPZASTUP == 1].drop_duplicates('KODZASTUP').set_index('KODZASTUP').POCOBYV
    pou = pou_seats(rz, set(KRAJSKA_MESTA) | set(orp))
    for kod in KRAJSKA_MESTA + sorted(orp, key=lambda k: -pop[k]) + sorted(pou, key=lambda k: -pop[k]):
        z = rz[rz.KODZASTUP == kod].iloc[0]
        city = t3[t3.KODZASTUP == kod]
        mcs = []
        uzemi = set(city.OBEC)
        for mk in sorted(set(t3[t3.OBEC.isin(uzemi) & (t3.TYPZASTUP == 2)].KODZASTUP)):  # zastupitelstva MČ/MO na území města
            zm = rz[(rz.KODZASTUP == mk)]
            mt = t3[t3.KODZASTUP == mk]
            mcs.append(dict(kod=int(mk), nazev=str(zm.NAZEVZAST.iloc[0]) if len(zm) else str(mk), mandatu=int(zm.MANDATY.iloc[0]) if len(zm) else None,
                            okrsku=int(len(mt)), volicu=int(mt.VOL_SEZNAM.sum())))
        nazev = 'Praha' if kod == 554782 else str(z.NAZEVZAST)
        out.append(dict(kod=int(kod), nazev=nazev, slug=slug(nazev), kraj=KRAJE.get(int(z.KRAJ), str(z.KRAJ)), krajkod=int(z.KRAJ), okres=int(z.OKRES),
                        mandatu=int(z.MANDATY), okrsku=int(len(city)), volicu=int(city.VOL_SEZNAM.sum()),
                        ucast=float(city.VYD_OBALKY.sum() / city.VOL_SEZNAM.sum()), mc=mcs,
                        typ='krajske' if kod in KRAJSKA_MESTA else ('orp' if kod in orp else 'pou'), obyv=int(pop[kod])))
    # stejnojmenné obce (např. Jesenice) odliší název okresu
    nuts = pd.read_csv(glob.glob(os.path.join(raw, '*cis*_csv', 'csv', 'cnumnuts.csv'))[0], sep=';', encoding='cp1250').set_index('NUMNUTS').NAZEVNUTS
    names = [u['nazev'] for u in out]
    for u in out:
        if names.count(u['nazev']) > 1:
            u['nazev'] = f'{u["nazev"]} (okres {nuts.get(u["okres"], u["okres"])})'
            u['slug'] = slug(u['nazev'])
    return out


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
        u['url'] = f'kv/{u["slug"]}/index.html'
    return U


if __name__ == '__main__':
    if os.path.exists(CACHE):
        os.remove(CACHE)
    for u in units():
        print(u['nazev'], u['kraj'], u['okrsku'], len(u['mc']), u['stav'])
