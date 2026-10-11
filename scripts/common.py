"""Shared loaders for the Prague KV forensic audit."""
import os
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P = os.path.join(ROOT, 'data', 'processed')
RES = os.path.join(ROOT, 'data', 'results')
os.makedirs(RES, exist_ok=True)
MAGISTRAT = 554782
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
    d['mc_name'] = mc
    t3 = d['t3']
    if 'PLAT_LISTKY' not in t3:
        t3['PLAT_LISTKY'] = np.nan
    t3['ZK'] = t3.KODZASTUP * 100 + t3.COBVODU
    t3['MANDATY'] = t3.ZK.map(cm.MANDATY)
    t3['MC'] = t3.OBEC.map(mc)
    t3['OID'] = t3.OBEC.astype(str) + '/' + t3.OKRSEK.astype(str)
    d['t3'] = t3
    hl = d['hl']
    hl['OID'] = hl.OBEC.astype(str) + '/' + hl.OKRSEK.astype(str)
    hl = hl.merge(t3[['OID', 'TYPZASTUP', 'ZK']], on=['OID', 'TYPZASTUP'], how='left')
    d['hl'] = hl
    rk = d['rk'].copy(); rk['ZK'] = rk.KODZASTUP * 100 + rk.COBVODU; d['rk'] = rk
    ros = d['ros'].copy(); ros['ZK'] = ros.KODZASTUP * 100 + ros.COBVODU
    ncand = rk[rk.PLATNOST == 'A'].groupby(['ZK', 'POR_STR_HL']).size().rename('NCAND')  # valid candidates only
    ros = ros.merge(ncand, left_on=['ZK', 'POR_STR_HL'], right_index=True, how='left')
    d['ros'] = ros
    return d
