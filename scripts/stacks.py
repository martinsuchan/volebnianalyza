"""Missing 'party-box stack' detector (two independent lines of evidence).

Line 1 – ballot-level deficit: votes per valid ballot (vpb) far below neighbours  -> D1 ballots missing.
Line 2 – party-level deficit: the party's party-box ballots (≈ median candidate votes) far below the
         neighbour rate per valid ballot -> D2 ballots missing for one party.
Strong finding = both lines agree (D2 explains a large part of D1).
"""
import sys, os
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(__file__))
from common import HCOLS, RES
from anomalies import prep, MAD


def run(year):
    d, t3, hl, ros, nb = prep(year)
    rk = d['rk']; valid = rk[rk.PLATNOST == 'A']
    miss = pd.read_pickle(f'{RES}/missing_{year}.pkl').set_index(['ZK', 'OID'])
    names = ros.set_index(['ZK', 'POR_STR_HL']).ZKRATKAO30
    n = t3.set_index(['ZK', 'OID']).PLAT_LISTKY
    out = []
    for (zk, p), g in hl.groupby(['ZK', 'POR_STR_HL']):
        pos = sorted(valid[(valid.ZK == zk) & (valid.POR_STR_HL == p)].PORCISLO)
        if len(pos) < 3:
            continue
        X = g.set_index('OID')[[HCOLS[i - 1] for i in pos]].astype(float)
        pb = X.median(axis=1)  # party-box ballots estimate
        nn_ = n.xs(zk).reindex(pb.index).astype(float)
        rate = pb / nn_
        ex, zz = {}, {}
        for o in pb.index:
            nbs = [x for x in nb.get(o, []) if x in pb.index]
            if len(nbs) < 3:
                nbs = [x for x in pb.index if x != o]
            if len(nbs) < 2:
                continue
            ex[o] = pb[nbs].sum() / nn_[nbs].sum()
        ex = pd.Series(ex)
        if ex.empty:
            continue
        exp_pb = ex * nn_.reindex(ex.index)
        zr = (pb.reindex(ex.index) - exp_pb) / np.sqrt(exp_pb.clip(lower=1))
        ok = exp_pb >= 5
        sc = max(MAD * np.median(np.abs(zr[ok] - np.median(zr[ok]))), 1.0) if ok.sum() >= 6 else 2.0
        for o in ex.index:
            if exp_pb[o] < 5:
                continue
            z = zr[o] / sc
            if z > -3.5:
                continue
            m = miss.loc[(zk, o)] if (zk, o) in miss.index else None
            d1 = m.chybi_listku if m is not None else np.nan
            d2 = exp_pb[o] - pb[o]
            out.append(dict(rok=year, ZK=zk, OID=o, strana=p, nazev=names.get((zk, p)), pb_obs=pb[o], pb_ocek=exp_pb[o],
                            z_strana=z, chybi_listku_strana=d2, chybi_listku_okrsek=d1,
                            z_vpb=m.z_vpb if m is not None else np.nan,
                            shoda=min(d2, d1) / max(d2, d1) if d1 and d1 > 0 and d2 > 0 else 0,
                            hlasy=g.set_index('OID').POC_HLASU[o], scale=sc))
    S = pd.DataFrame(out)
    S['MC'] = S.OID.map(t3.drop_duplicates('OID').set_index('OID').MC)
    # classification
    S['tri'] = np.select([(S.z_vpb <= -5) & (S.z_strana <= -3.5) & (S.shoda >= 0.6),
                          (S.z_vpb <= -3.5) & (S.z_strana <= -3.5) & (S.shoda >= 0.4)], ['silny', 'stredni'], 'slaby')
    return S


if __name__ == '__main__':
    pd.set_option('display.width', 260); pd.set_option('display.max_colwidth', 45)
    for y in (2022, 2026):
        S = run(y); S.to_pickle(f'{RES}/stacks_{y}.pkl')
        print('=====', y, S.tri.value_counts().to_dict())
        print(S[S.tri != 'slaby'].sort_values('z_strana')[['OID', 'MC', 'ZK', 'strana', 'nazev', 'hlasy', 'pb_obs', 'pb_ocek', 'z_strana',
                                                            'chybi_listku_strana', 'chybi_listku_okrsek', 'z_vpb', 'shoda', 'tri']].round(2).to_string())
