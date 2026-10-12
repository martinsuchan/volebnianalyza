"""ETL pro senátní volby (1. kolo 2018, 2020, 2022, 2026) + celostátní okrskové údaje KV pro párování okrsků.

Výstupy v data/processed:
  se_t5_<rok>.pkl   okrskové zápisy T/5 (jen 1. kolo), klíč OID = OBEC/OKRSEK
  se_rk_<rok>.pkl   registr kandidátů s oficiálními výsledky
  kvnat_<rok>.pkl   KV za celé Česko agregované na okrsek (2018, 2022, 2026)
  se_centroids.pkl  těžiště okrsků z hranic ČSÚ 2022 (celé Česko)
"""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, P0 as P

RAW = os.path.join(ROOT, 'data', 'raw')
KV_DATE = {2018: 20181005, 2022: 20220923}
HC = [f'HLASY_{i:02d}' for i in range(1, 23)]


def rd(pattern):
    """CSV ČSÚ ve formátu csv/ (cp1250, středník); u 2018/2020 leží v kořeni rozbaleného zipu."""
    fs = sorted(glob.glob(os.path.join(RAW, pattern), recursive=True))
    fs = [f for f in fs if os.sep + 'csv_od' + os.sep not in f] or fs
    return pd.read_csv(fs[0], sep=';', encoding='cp1250', low_memory=False)


def senate(year):
    t5 = rd(f'se{year}/*data*/**/set5.csv')
    t5 = t5[t5.KOLO == 1].copy()
    if 'VOL_PRUKAZ' not in t5:
        t5['VOL_PRUKAZ'] = np.nan
    t5['OID'] = t5.OBEC.astype(str) + '/' + t5.OKRSEK.astype(str)
    rk = rd(f'se{year}/*reg*/**/serk.csv')
    obv = rd(f'se{year}/*ciselnik*/**/secobv.csv')
    return t5, rk, obv


def kv_national(year):
    t3 = rd(f'kv{year}/*data*/**/kvt3.csv')
    if year in KV_DATE:
        t3 = t3[t3.DATUMVOLEB == KV_DATE[year]]
    g = t3.groupby(['OBEC', 'OKRSEK'])
    a = g.agg(KV_VOL=('VOL_SEZNAM', 'max'), KV_VYD=('VYD_OBALKY', 'max'), KV_ODEVZ=('ODEVZ_OBAL', 'max'),
              KV_ODEVZ_MIN=('ODEVZ_OBAL', 'min'), KV_N=('TYPZASTUP', 'size'), OKRES=('OKRES', 'first')).reset_index()
    if 'VOL_PRUKAZ' in t3:
        a = a.merge(g.VOL_PRUKAZ.max().rename('KV_VP').reset_index(), on=['OBEC', 'OKRSEK'])
    a['OID'] = a.OBEC.astype(str) + '/' + a.OKRSEK.astype(str)
    return a


def centroids():
    gj = json.load(open(os.path.join(RAW, 'geo', 'vol_okrsky_2022g100.geojson'), encoding='utf8'))
    rows = []
    for f in gj['features']:
        pr = f['properties']
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        pts = np.array([p for poly in polys for p in poly[0]])
        obec = pr['MOMC'] if pr['MOMC'] not in ('', '0') else pr['OBEC']
        rows.append(dict(OID=f"{int(obec)}/{int(pr['CISLO'])}", lon=pts[:, 0].mean(), lat=pts[:, 1].mean()))
    return pd.DataFrame(rows).drop_duplicates('OID')


if __name__ == '__main__':
    for y in (2018, 2020, 2022, 2026):
        t5, rk, obv = senate(y)
        t5.to_pickle(os.path.join(P, f'se_t5_{y}.pkl')); rk.to_pickle(os.path.join(P, f'se_rk_{y}.pkl'))
        obv.to_pickle(os.path.join(P, f'se_obv_{y}.pkl'))
        print('SE', y, t5.shape, 'obvody', t5.OBVOD.nunique(), 'kandidáti', len(rk))
    for y in (2018, 2022, 2026):
        a = kv_national(y); a.to_pickle(os.path.join(P, f'kvnat_{y}.pkl'))
        print('KV', y, a.shape)
    c = centroids(); c.to_pickle(os.path.join(P, 'se_centroids.pkl')); print('centroids', len(c))
