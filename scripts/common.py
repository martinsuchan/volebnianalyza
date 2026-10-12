"""Společné načítání dat pro forenzní audit komunálních voleb.

Analyzovaná územní jednotka (město včetně MČ/MO) se volí proměnnou prostředí AUDIT_UNIT (slug, výchozí 'praha').
Výsledky jednotky se ukládají do data/processed/kv/<slug> a data/results/kv/<slug>; P0 a RES0 jsou společné
adresáře (senát, celostátní výřezy, registr jednotek).
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P0 = os.path.join(ROOT, 'data', 'processed')
RES0 = os.path.join(ROOT, 'data', 'results')
# krajská města: slug -> kód obce (= kód zastupitelstva města); sídla ORP se doplní z registru jednotek
CITIES = {'praha': 554782, 'brno': 582786, 'ostrava': 554821, 'plzen': 554791, 'liberec': 563889, 'olomouc': 500496,
          'usti-nad-labem': 554804, 'hradec-kralove': 569810, 'ceske-budejovice': 544256, 'pardubice': 555134,
          'zlin': 585068, 'jihlava': 586846, 'karlovy-vary': 554961}
_REG = os.path.join(P0, 'units_2026.json')  # registr jednotek (scripts/units.py) – doplní sídla ORP
if os.path.exists(_REG):
    import json as _json
    for _u in _json.load(open(_REG, encoding='utf-8')):
        CITIES.setdefault(_u['slug'], _u['kod'])
UNIT = os.environ.get('AUDIT_UNIT', 'praha')
MAGISTRAT = CITIES[UNIT]  # kód zastupitelstva města (historický název z pražské verze)
P = os.path.join(P0, 'kv', UNIT)
RES = os.path.join(RES0, 'kv', UNIT)
os.makedirs(P, exist_ok=True); os.makedirs(RES, exist_ok=True); os.makedirs(RES0, exist_ok=True)
HCOLS = [f'HLASY_{i:02d}' for i in range(1, 71)]
MAIN_DATE = {2018: 20181005, 2022: 20220923}


def load(year):
    d = {k: pd.read_pickle(os.path.join(P, f'{k}_{year}.pkl'))
         for k in ('t3', 'hl', 'rz', 'ros', 'rk', 'cvs', 'cns')}
    if year in MAIN_DATE:  # drop repeated/supplementary elections
        for k in ('t3', 'hl', 'ros', 'rk'):
            if 'DATUMVOLEB' in d[k]:
                d[k] = d[k][d[k].DATUMVOLEB == MAIN_DATE[year]].copy()
    rz = d['rz']
    if 'DATUMVOLEB' in rz:
        rz = rz[rz.DATUMVOLEB == MAIN_DATE[year]]
    d['rz'] = rz
    # council key ZK = KODZASTUP*100+COBVODU (Praha 9 had 2 electoral districts in 2018)
    rz = rz.copy()
    rz['ZK'] = rz.KODZASTUP * 100 + np.where(rz.OBVODY == 2, rz.COBVODU, 1)
    cm = rz.sort_values('OBVODY', ascending=False).drop_duplicates('ZK')[['ZK', 'KODZASTUP', 'NAZEVZAST', 'MANDATY', 'TYPZASTUP']].set_index('ZK')
    d['councils'] = cm
    # MČ name per OBEC (okrsek location)
    mc = rz[rz.TYPZASTUP == 2].drop_duplicates('OBEC').set_index('OBEC').NAZEVZAST
    city = rz[rz.KODZASTUP == MAGISTRAT].NAZEVZAST
    mc.loc[MAGISTRAT] = 'Praha' if MAGISTRAT == 554782 else (city.iloc[0] if len(city) else str(MAGISTRAT))  # okrsky mimo MČ
    d['mc_name'] = mc
    t3 = d['t3']
    if 'PLAT_LISTKY' not in t3:
        t3['PLAT_LISTKY'] = np.nan
    t3['ZK'] = t3.KODZASTUP * 100 + t3.COBVODU
    t3['MANDATY'] = t3.ZK.map(cm.MANDATY)
    t3['MC'] = t3.OBEC.map(mc).fillna(mc.get(MAGISTRAT))  # okrsky mimo MČ/MO (např. Liberec mimo Vratislavice)
    t3['OID'] = t3.OBEC.astype(str) + '/' + t3.OKRSEK.astype(str)
    d['t3'] = t3
    hl = d['hl']
    hl['OID'] = hl.OBEC.astype(str) + '/' + hl.OKRSEK.astype(str)
    hl = hl.merge(t3[['OID', 'TYPZASTUP', 'ZK']], on=['OID', 'TYPZASTUP'], how='left')
    d['hl'] = hl
    rk = d['rk'].copy(); rk['ZK'] = rk.KODZASTUP * 100 + rk.COBVODU
    rk['POCHLASU'] = rk.POCHLASU.fillna(0)  # chybějící údaj v registru (Jilemnice 2018)
    d['rk'] = rk
    ros = d['ros'].copy(); ros['ZK'] = ros.KODZASTUP * 100 + ros.COBVODU
    ncand = rk[rk.PLATNOST == 'A'].groupby(['ZK', 'POR_STR_HL']).size().rename('NCAND')  # valid candidates only
    ros = ros.merge(ncand, left_on=['ZK', 'POR_STR_HL'], right_index=True, how='left')
    d['ros'] = ros
    return d
