"""ETL: load ČSÚ open data (KV 2018/2022/2026) and keep Prague (OKRES 1100) only."""
import glob, os, sys
import pandas as pd

RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
PRAHA_OKRES = 1100

def rd(year, kind, name):
    pat = {'data': '*data*_csv', 'reg': '*reg*_csv', 'cis': '*cis*_csv'}[kind]
    f = glob.glob(os.path.join(RAW, f'kv{year}', pat, 'csv', name))[0]
    enc = 'ascii' if kind == 'data' else 'cp1250'
    return pd.read_csv(f, sep=';', encoding=enc if kind != 'data' else 'cp1250', low_memory=False)

def load(year):
    t3 = rd(year, 'data', 'kvt3.csv'); t3 = t3[t3.OKRES == PRAHA_OKRES].copy()
    hl = rd(year, 'data', 'kvhl.csv'); hl = hl[hl.OKRES == PRAHA_OKRES].copy()
    rz = rd(year, 'reg', 'kvrzcoco.csv'); rz = rz[rz.OKRES == PRAHA_OKRES].copy()
    ros = rd(year, 'reg', 'kvros.csv'); ros = ros[ros.OKRES == PRAHA_OKRES].copy()
    rk = rd(year, 'reg', 'kvrk.csv'); rk = rk[rk.OKRES == PRAHA_OKRES].copy()
    cvs = rd(year, 'cis', 'cvs.csv'); cns = rd(year, 'cis', 'cns.csv')
    for d in (t3, hl, rz, ros, rk):
        d.insert(0, 'ROK', year)
    # okrsek -> KODZASTUP for hl (hl lacks it): join through t3
    key = ['OBEC', 'OKRSEK', 'TYPZASTUP']
    hl = hl.merge(t3[key + ['KODZASTUP']].drop_duplicates(), on=key, how='left')
    return dict(t3=t3, hl=hl, rz=rz, ros=ros, rk=rk, cvs=cvs, cns=cns)

if __name__ == '__main__':
    for y in (2018, 2022, 2026):
        d = load(y)
        for k, v in d.items():
            v.to_pickle(os.path.join(OUT, f'{k}_{y}.pkl'))
        print(y, {k: v.shape for k, v in d.items()})
