"""Těžiště okrsků z hranic ČSÚ 2022 (hranice 2026 nebyly zveřejněny jako soubor); k nejbližších sousedů."""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, P, MAGISTRAT, MEMO


def centroids():
    if 'geo' not in MEMO:
        MEMO['geo'] = json.load(open(os.path.join(ROOT, 'data/raw/geo/vol_okrsky_2022g100.geojson'), encoding='utf8'))
    gj = MEMO['geo']
    rows = []
    for f in gj['features']:
        pr = f['properties']
        if int(pr['OBEC']) != MAGISTRAT:
            continue
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        pts = np.array([p for poly in polys for p in poly[0]])
        obec = pr['MOMC'] if pr['MOMC'] not in ('', '0') else pr['OBEC']  # okrsky mimo MČ/MO mají MOMC = 0
        rows.append(dict(OID=f"{int(obec)}/{int(pr['CISLO'])}", lon=pts[:, 0].mean(), lat=pts[:, 1].mean(),
                         geom=[[list(map(lambda v: round(v, 4), p)) for p in poly[0]] for poly in polys]))
    return pd.DataFrame(rows)


def neighbours(oids, k=6):
    """Return dict OID -> list of k neighbour OIDs (same MČ preferred by caller). Fallback: numeric order."""
    c = centroids().drop_duplicates('OID').set_index('OID')
    have = [o for o in oids if o in c.index]
    lat0 = 50.08 if MAGISTRAT == 554782 else float(c.lat.mean())  # Praha: původní konstanta (reprodukovatelnost)
    xy = c.loc[have, ['lon', 'lat']].values * np.array([np.cos(np.radians(lat0)), 1.0])
    nb = {}
    for i, o in enumerate(have):
        dd = ((xy - xy[i]) ** 2).sum(1); idx = np.argsort(dd)[1:k + 1]
        nb[o] = [have[j] for j in idx]
    miss = [o for o in oids if o not in c.index]
    num = sorted(oids, key=lambda s: (int(s.split('/')[0]), int(s.split('/')[1])))
    for o in miss:
        i = num.index(o); cand = num[max(0, i - k // 2): i] + num[i + 1: i + 1 + k // 2]
        nb[o] = cand
    return nb, miss


if __name__ == '__main__':
    c = centroids(); print(len(c))
    t3 = pd.read_pickle(os.path.join(P, 't3_2026.pkl'))
    oids = (t3.OBEC.astype(str) + '/' + t3.OKRSEK.astype(str)).unique().tolist()
    nb, miss = neighbours(oids)
    print('2026 okrsky', len(oids), 'without 2022 geometry', len(miss), miss[:30])
    c.to_pickle(os.path.join(P, 'centroids.pkl'))
