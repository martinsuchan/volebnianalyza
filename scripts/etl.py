"""ETL: načte otevřená data ČSÚ (KV 2018/2022/2026) a ponechá jen analyzované město (AUDIT_UNIT) včetně jeho MČ/MO."""
import glob, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import P as OUT, MAGISTRAT, MEMO

RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')

def rd(year, kind, name):
    pat = {'data': '*data*_csv', 'reg': '*reg*_csv', 'cis': '*cis*_csv'}[kind]
    f = glob.glob(os.path.join(RAW, f'kv{year}', pat, 'csv', name))[0]
    # celostátní tabulky se při zpracování mnoha obcí čtou opakovaně – mezipaměť v pickle (obnoví se při změně zdroje)
    cache = os.path.join(OUT, '..', '..', '_celostatni', f'kv{year}_{name}.pkl')
    if ('kv', year, name) in MEMO:  # dávkový běh: tabulka už je v paměti (volající ji jen filtruje, nemění)
        return MEMO[('kv', year, name)]
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(f):
        MEMO[('kv', year, name)] = pd.read_pickle(cache)
        return MEMO[('kv', year, name)]
    df = pd.read_csv(f, sep=';', encoding='cp1250', low_memory=False)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    df.to_pickle(cache)
    return df

def load(year):
    t3 = rd(year, 'data', 'kvt3.csv')
    obce = set(t3[t3.KODZASTUP == MAGISTRAT].OBEC) | {MAGISTRAT}  # území města: obec nebo její MČ/MO
    t3 = t3[t3.OBEC.isin(obce)].copy()
    kody = set(t3.KODZASTUP) | {MAGISTRAT}  # zastupitelstvo města + zastupitelstva MČ/MO
    hl = rd(year, 'data', 'kvhl.csv'); hl = hl[hl.OBEC.isin(obce)].copy()
    rz = rd(year, 'reg', 'kvrzcoco.csv'); rz = rz[rz.KODZASTUP.isin(kody)].copy()
    ros = rd(year, 'reg', 'kvros.csv'); ros = ros[ros.KODZASTUP.isin(kody)].copy()
    rk = rd(year, 'reg', 'kvrk.csv'); rk = rk[rk.KODZASTUP.isin(kody)].copy()
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
