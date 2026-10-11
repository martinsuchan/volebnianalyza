"""Independent recomputation of seat allocation (zákon 491/2001 Sb., §45) and seat-margin analysis."""
import sys, os, json, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import load, RES


def allocate(V, NC, M, thr=0.05):
    """V, NC: dict party->votes, ncand. Returns seats dict, qualified set, recomputed pct."""
    tot = sum(V.values())
    pct = {p: (V[p] * M / NC[p] if NC[p] < M else V[p]) / tot for p in V}
    t = thr
    while True:
        q = {p for p in V if pct[p] >= t}
        if len(q) >= 2 or t <= 0 or len(V) < 2:
            break
        t -= 0.01
    quots = sorted(((V[p] / k, V[p], p) for p in q for k in range(1, NC[p] + 1)), reverse=True)
    seats = {p: 0 for p in V}
    for qq, v, p in quots[:M]:
        seats[p] += 1
    last_win = quots[M - 1][0] if len(quots) >= M else 0
    first_lose = quots[M][0] if len(quots) > M else 0
    return seats, q, pct, last_win, first_lose


def margins(V, NC, M, seats, q, last_win, first_lose):
    """Votes needed for party to gain one more seat / votes it can lose before losing one (ceteris paribus)."""
    res = {}
    for p in V:
        if p not in q:
            res[p] = dict(gain=None, lose=None)
            continue
        s = seats[p]
        # to gain: (V+x)/(s+1) > last_win of others (approx: last winning quotient)
        gain = math.floor(last_win * (s + 1) - V[p]) + 1 if s < NC[p] else None
        # to lose: V-x)/s < first_lose
        lose = V[p] - math.floor(first_lose * s) if s > 0 else None
        res[p] = dict(gain=gain, lose=lose)
    return res


def run(year):
    d = load(year); ros, rk, cm = d['ros'], d['rk'], d['councils']
    rows, crows = [], []
    for zk, g in ros.groupby('ZK'):
        g = g[g.NCAND.fillna(0) > 0]
        M = int(cm.MANDATY[zk]); V = dict(zip(g.POR_STR_HL, g.HLASY_STR.astype(int)))
        NC = dict(zip(g.POR_STR_HL, g.NCAND.astype(int)))
        seats, q, pct, lw, fl = allocate(V, NC, M)
        mg = margins(V, NC, M, seats, q, lw, fl)
        for _, r in g.iterrows():
            p = r.POR_STR_HL
            rows.append(dict(rok=year, ZK=zk, zastupitelstvo=cm.NAZEVZAST[zk], mandatu=M, strana=p,
                             nazev=r.ZKRATKAO30, hlasy=V[p], ncand=NC[p], pct_prep=round(100 * pct[p], 4),
                             pct_oficial=r.PROCHLSTR, mand_vypocet=seats[p], mand_oficial=int(r.MAND_STR),
                             hlasy_k_zisku=mg[p]['gain'], hlasy_k_ztrate=mg[p]['lose'],
                             volici_k_zisku=None if mg[p]['gain'] is None else math.ceil(mg[p]['gain'] / M),
                             volici_k_ztrate=None if mg[p]['lose'] is None else math.ceil(mg[p]['lose'] / M),
                             do_prahu=round(0.05 * sum(V.values()) * (NC[p] / M if NC[p] < M else 1) - V[p])))
        # preferential votes within each party with seats
        for p in V:
            c = rk[(rk.ZK == zk) & (rk.POR_STR_HL == p) & (rk.PLATNOST == 'A')].sort_values('PORCISLO')
            if not len(c):
                continue
            avg = math.floor(V[p] / NC[p])  # §45 odst. 4: průměr zaokrouhlený dolů
            thr = avg * 1.10
            pref = c[c.POCHLASU >= thr].sort_values('POCHLASU', ascending=False)
            order = list(pref.PORCISLO) + [x for x in c.PORCISLO if x not in set(pref.PORCISLO)]
            elected = set(order[:seats[p]])
            for _, r in c.iterrows():
                crows.append(dict(rok=year, ZK=zk, zastupitelstvo=cm.NAZEVZAST[zk], strana=p, porcislo=r.PORCISLO,
                                  jmeno=f'{r.JMENO} {r.PRIJMENI}', hlasy=int(r.POCHLASU), prah_pref=thr,
                                  rozdil_k_prahu=int(r.POCHLASU) - thr, mandat_vypocet=r.PORCISLO in elected,
                                  mandat_oficial=r.MANDAT == 'A', preskoceni=r.PRESKOCENI,
                                  poradi_vypocet=order.index(r.PORCISLO) + 1, strana_mandatu=seats[p]))
    return pd.DataFrame(rows), pd.DataFrame(crows)


if __name__ == '__main__':
    S, C = [], []
    for y in (2018, 2022, 2026):
        s, c = run(y); S.append(s); C.append(c)
        mism = s[s.mand_vypocet != s.mand_oficial]
        cm_ = c[c.mandat_vypocet != c.mandat_oficial]
        pdiff = (s.pct_prep - s.pct_oficial).abs().max()
        print(y, 'parties', len(s), 'seat mismatches', len(mism), 'candidate mismatches', len(cm_), 'max pct diff', round(pdiff, 3))
        if len(mism): print(mism.to_string())
        if len(cm_): print(cm_.head(20).to_string())
    pd.concat(S).to_csv(f'{RES}/seats.csv', index=False); pd.concat(C).to_csv(f'{RES}/candidates_pref.csv', index=False)
