"""Materiality: would correcting the detected errors change seats or elected candidates?

Corrections (2026):
  * typos (inserted / dropped digit, zero dips): candidate & party votes set to the probable value
  * missing party-box stacks: + k ballots × min(NCAND, M) votes for the party, +k for each candidate
    in party-box range; k conservative = min(party deficit, precinct deficit), upper = party deficit
  * Praha 2/2038 magistrát: ANO & SEN stack restored (same mechanism; party votes 0)
Scenarios are applied per finding and jointly; seats (§45) and the preferential order are recomputed.
"""
import sys, os, math, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import load, RES, UNIT
from seats import allocate

Y = 2026


def outcome(ros, rk, cm, zk, dV=None, dC=None):
    """Elected candidate set for council zk with optional party (dV) / candidate (dC) vote deltas."""
    g = ros[(ros.ZK == zk) & (ros.NCAND.fillna(0) > 0)]
    M = int(cm.MANDATY[zk])
    V = {p: int(v) + (dV or {}).get(p, 0) for p, v in zip(g.POR_STR_HL, g.HLASY_STR)}
    NC = dict(zip(g.POR_STR_HL, g.NCAND.astype(int)))
    seats, q, pct, lw, fl = allocate(V, NC, M)
    elected = []
    c_all = rk[(rk.ZK == zk) & (rk.PLATNOST == 'A')]
    for p in V:
        if seats[p] == 0:
            continue
        c = c_all[c_all.POR_STR_HL == p].sort_values('PORCISLO')
        votes = {r.PORCISLO: int(r.POCHLASU) + (dC or {}).get((p, r.PORCISLO), 0) for r in c.itertuples()}
        thr = math.floor(V[p] / NC[p]) * 1.10
        pref = sorted([k for k, v in votes.items() if v >= thr], key=lambda k: (-votes[k], k))
        order = pref + [k for k in sorted(votes) if k not in pref]
        elected += [(p, k) for k in order[:seats[p]]]
    return seats, set(elected)


def corrections():
    d = load(Y); ros, rk = d['ros'], d['rk']
    corr = []
    T = pd.read_pickle(f'{RES}/typos_{Y}.pkl')
    for r in T.itertuples():
        corr.append(dict(id=f'T-{r.OID}-{r.ZK}-{r.strana}-{r.porcislo}', druh='překlep/propad', ZK=r.ZK, OID=r.OID,
                         dV={r.strana: int(-r.rozdil)}, dC={(r.strana, r.porcislo): int(-r.rozdil)}, popis=f'{r.jmeno} ({r.nazev_strany}): {r.hlasy} → ~{r.pravdepodobne}'))
    S = pd.read_pickle(f'{RES}/stacks_{Y}.pkl'); S = S[S.tri != 'slaby']
    cm = d['councils']
    for r in S.itertuples():
        M = int(cm.MANDATY[r.ZK]); nc = int(ros[(ros.ZK == r.ZK) & (ros.POR_STR_HL == r.strana)].NCAND.iloc[0])
        for lab, k in (('kons', min(r.chybi_listku_strana, r.chybi_listku_okrsek)), ('max', r.chybi_listku_strana)):
            k = int(round(k)); width = min(nc, M)
            pos = sorted(rk[(rk.ZK == r.ZK) & (rk.POR_STR_HL == r.strana) & (rk.PLATNOST == 'A')].PORCISLO)[:width]
            corr.append(dict(id=f'S-{r.OID}-{r.ZK}-{r.strana}-{lab}', druh=f'chybějící balík ({lab})', ZK=r.ZK, OID=r.OID,
                             dV={r.strana: k * width}, dC={(r.strana, c): k for c in pos},
                             popis=f'{r.nazev}: +{k} lístků × {width} hlasů'))
    if UNIT != 'praha':
        # nulové hlasy strany při vysokém očekávání: doplnit očekávaný počet lístků s křížkem u strany
        Z = pd.read_pickle(f'{RES}/zeros_{Y}.pkl')
        Z = Z[(Z.rok == Y) & (Z.p_conservative < 1e-3)] if len(Z) else Z
        for r in Z.itertuples():
            M = int(cm.MANDATY[r.ZK]); nc = int(ros[(ros.ZK == r.ZK) & (ros.POR_STR_HL == r.strana)].NCAND.fillna(0).iloc[0])
            width = max(min(nc, M), 1); k = int(round(r.exp_ballots))
            pos = sorted(rk[(rk.ZK == r.ZK) & (rk.POR_STR_HL == r.strana) & (rk.PLATNOST == 'A')].PORCISLO)[:width]
            corr.append(dict(id=f'Z-{r.OID}-{r.ZK}-{r.strana}-kons', druh='nulové hlasy strany', ZK=r.ZK, OID=r.OID,
                             dV={r.strana: k * width}, dC={(r.strana, c): k for c in pos}, popis=f'{r.nazev}: +{k} lístků × {width} hlasů'))
        return corr
    # Praha 2/2038 – ANO (22) & SEN (24) restored from MČ-ballot ratio / neighbours
    X = pd.read_pickle(f'{RES}/cross_{Y}.pkl')
    ano = X[(X.OID == '500089/2038') & (X.strany_mag == 'ANO 2011')].ocek_hlasy_mag.iloc[0]
    for lab, k_ano, k_sen in (('kons', int(round(1567 / 65)), int(round(305 / 65))), ('max', int(round(ano / 65)), int(round(305 / 65)))):
        dC = {}
        for p, k in ((22, k_ano), (24, k_sen)):
            for c in sorted(rk[(rk.ZK == 55478201) & (rk.POR_STR_HL == p) & (rk.PLATNOST == 'A')].PORCISLO)[:65]:
                dC[(p, c)] = k
        corr.append(dict(id=f'Z-500089/2038-{lab}', druh=f'nulové hlasy strany ({lab})', ZK=55478201, OID='500089/2038',
                         dV={22: k_ano * 65, 24: k_sen * 65}, dC=dC, popis=f'ANO +{k_ano} lístků, SEN +{k_sen} lístků'))
    return corr


def run():
    d = load(Y); ros, rk, cm = d['ros'], d['rk'], d['councils']
    base = {zk: outcome(ros, rk, cm, zk) for zk in ros.ZK.unique()}
    corr = corrections()
    res = []
    for c in corr:
        s0, e0 = base[c['ZK']]
        s1, e1 = outcome(ros, rk, cm, c['ZK'], c['dV'], c['dC'])
        res.append(dict(id=c['id'], druh=c['druh'], ZK=c['ZK'], OID=c['OID'], popis=c['popis'],
                        zmena_mandatu=s0 != s1, zmena_zvolenych=e0 != e1,
                        detail='; '.join(f'strana {p}: {s0[p]}→{s1[p]}' for p in s0 if s0[p] != s1[p]) +
                               ('' if e0 == e1 else f' | zvoleni navíc {sorted(e1 - e0)}, vypadli {sorted(e0 - e1)}')))
    R = pd.DataFrame(res, columns=['id', 'druh', 'ZK', 'OID', 'popis', 'zmena_mandatu', 'zmena_zvolenych', 'detail'])
    # joint scenario per council (conservative variants + all typos)
    joint = []
    for zk, g in (pd.DataFrame(corr).groupby('ZK') if corr else []):
        sel = [c for c in corr if c['ZK'] == zk and not c['id'].endswith('-max')]
        dV, dC = {}, {}
        for c in sel:
            for k, v in c['dV'].items(): dV[k] = dV.get(k, 0) + v
            for k, v in c['dC'].items(): dC[k] = dC.get(k, 0) + v
        s0, e0 = base[zk]; s1, e1 = outcome(ros, rk, cm, zk, dV, dC)
        joint.append(dict(ZK=zk, zastupitelstvo=cm.NAZEVZAST[zk], oprav=len(sel), zmena_mandatu=s0 != s1, zmena_zvolenych=e0 != e1,
                          detail='; '.join(f'strana {p}: {s0[p]}→{s1[p]}' for p in s0 if s0[p] != s1[p]) +
                                 ('' if e0 == e1 else f' | navíc {sorted(e1 - e0)}, vypadli {sorted(e0 - e1)}'),
                          dV=json.dumps({int(k): int(v) for k, v in dV.items()})))
    J = pd.DataFrame(joint, columns=['ZK', 'zastupitelstvo', 'oprav', 'zmena_mandatu', 'zmena_zvolenych', 'detail', 'dV'])
    return R, J


if __name__ == '__main__':
    pd.set_option('display.width', 260); pd.set_option('display.max_colwidth', 120)
    R, J = run()
    R.to_pickle(f'{RES}/materiality_{Y}.pkl'); J.to_pickle(f'{RES}/materiality_joint_{Y}.pkl')
    print('individual corrections', len(R), 'changing seats', R.zmena_mandatu.sum(), 'changing elected', R.zmena_zvolenych.sum())
    print(R[R.zmena_zvolenych | R.zmena_mandatu].to_string())
    print(J.to_string())
