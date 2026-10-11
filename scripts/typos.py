"""Keystroke-error detector for candidate vote counts (inserted / dropped digit).

For a candidate i in a precinct, the local reference t is taken from the neighbouring candidates on the
same list (i-1, i+1) when those agree. A count is flagged as a probable typo when it deviates strongly
from t AND a single-digit edit (delete one digit / insert one digit) maps it back to within ±tol of t.
Genuine preferential spikes are arbitrary numbers and only rarely satisfy the digit-edit condition;
dips (counts far below both neighbours) are not explainable by voter behaviour in the middle of a list.
"""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import HCOLS, RES
from anomalies import prep


def deletions(v):
    s = str(int(v)); return {int(s[:k] + s[k + 1:]) for k in range(len(s)) if len(s) > 1}


def insertions(v):
    s = str(int(v)); out = set()
    for k in range(len(s) + 1):
        for dgt in '0123456789':
            x = s[:k] + dgt + s[k:]
            if not (x.startswith('0') and len(x) > 1):
                out.add(int(x))
    return out


def run(year):
    d, t3, hl, ros, nb = prep(year)
    rk = d['rk']; valid = rk[rk.PLATNOST == 'A']
    names = rk.set_index(['ZK', 'POR_STR_HL', 'PORCISLO'])
    pn = ros.set_index(['ZK', 'POR_STR_HL']).ZKRATKAO30
    mand = t3.groupby('ZK').MANDATY.first()
    out = []
    for (zk, p), g in hl.groupby(['ZK', 'POR_STR_HL']):
        pos = sorted(valid[(valid.ZK == zk) & (valid.POR_STR_HL == p)].PORCISLO)
        if len(pos) < 3:
            continue
        X = g.set_index('OID')[[HCOLS[i - 1] for i in pos]].astype(int)
        M = int(mand[zk])
        for o, row in X.iterrows():
            v = row.values
            for i in range(len(v)):
                if 0 < i < len(v) - 1:
                    nbv = [v[i - 1], v[i + 1]]
                else:  # list ends: use the two nearest candidates, which must agree with each other
                    two = [v[j] for j in ((1, 2) if i == 0 else (i - 1, i - 2)) if 0 <= j < len(v)]
                    if len(two) < 2 or abs(two[0] - two[1]) > max(3, 0.2 * max(two)):
                        continue
                    nbv = two
                if len(nbv) == 2 and abs(nbv[0] - nbv[1]) > max(3, 0.2 * max(nbv)):
                    continue  # neighbours disagree – no reliable reference
                t = int(round(np.mean(nbv)))
                tol = max(2, int(0.1 * t))
                x = v[i]
                if t < 3 and x < 30:
                    continue
                kind = None
                if x >= t + 15 and x >= 3 * max(t, 1):
                    if any(abs(c - t) <= tol for c in deletions(x)):
                        kind = 'vlozena_cislice'
                elif t >= 15 and x <= t / 3 and 0 < i < len(v) - 1 and pos[i] < M:  # dips only mid-list, within party-box range
                    if any(abs(c - t) <= tol for c in insertions(x)):
                        kind = 'vypadla_cislice'
                    else:
                        kind = 'propad'
                if kind:
                    nm = names.loc[(zk, p, pos[i])]
                    best = min((c for c in (deletions(x) if kind == 'vlozena_cislice' else insertions(x))), key=lambda c: abs(c - t)) if kind != 'propad' else t
                    out.append(dict(rok=year, ZK=zk, OID=o, strana=p, nazev_strany=pn.get((zk, p)), porcislo=pos[i],
                                    jmeno=f'{nm.JMENO} {nm.PRIJMENI}', hlasy=x, reference=t, pravdepodobne=best,
                                    rozdil=x - best, typ=kind, celkem_kand=int(nm.POCHLASU), mandat=nm.MANDAT))
    T = pd.DataFrame(out)
    if len(T):
        T['MC'] = T.OID.map(t3.drop_duplicates('OID').set_index('OID').MC)
    return T


if __name__ == '__main__':
    pd.set_option('display.width', 260); pd.set_option('display.max_colwidth', 40); pd.set_option('display.max_rows', 200)
    for y in (2018, 2022, 2026):
        T = run(y); T.to_pickle(f'{RES}/typos_{y}.pkl')
        print('=====', y, len(T), T.typ.value_counts().to_dict() if len(T) else {})
        if y == 2026:
            print(T.sort_values('rozdil', key=abs, ascending=False)[['MC', 'OID', 'ZK', 'strana', 'nazev_strany', 'porcislo', 'jmeno', 'hlasy',
                                                                    'reference', 'pravdepodobne', 'rozdil', 'typ', 'celkem_kand', 'mandat']].to_string())
