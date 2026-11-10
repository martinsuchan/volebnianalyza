"""Průzkum dvou nových pravidel (zatím mimo pipeline, bez zápisu do review/ a webu).

P8 – přesun hlasů mezi stranami v jednom okrsku (Kladno 51 A 85, okrsek 1):
     strana X má v okrsku schodek, strana Y stejně velký přebytek, součet hlasů okrsku sedí.
P9 – izolovaný nadbytek hlasů jednoho kandidáta (Praha-Petrovice 8 A 70, okrsek 44001):
     kandidát má v okrsku mnohonásobně víc hlasů, než je jeho obvyklý nadbytek v ostatních okrscích,
     a nadbytek se nepřelévá do sousedních okrsků ani na druhý lístek.

Použití:  AUDIT_UNIT=praha python pravidla_p8_p9.py 2026
"""
import os, sys, math, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np, pandas as pd
from common import RES, HCOLS, MAGISTRAT, load, PREDCHOZI
from anomalies import prep, MAD
from materiality import outcome

Y = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
YP = PREDCHOZI[Y]
d, t3, hl, ros, nb = prep(Y)
rk, cm = d['rk'], d['councils']
SH = pd.read_pickle(f'{RES}/shares_{Y}.pkl')
SHP = pd.read_pickle(f'{RES}/shares_{YP}.pkl') if YP and os.path.exists(f'{RES}/shares_{YP}.pkl') else None
CR = pd.read_pickle(f'{RES}/cross_{Y}.pkl') if os.path.exists(f'{RES}/cross_{Y}.pkl') else pd.DataFrame()
SP = pd.read_pickle(f'{RES}/spikes_{Y}.pkl') if os.path.exists(f'{RES}/spikes_{Y}.pkl') else pd.DataFrame()
TY = pd.read_pickle(f'{RES}/typos_{Y}.pkl') if os.path.exists(f'{RES}/typos_{Y}.pkl') else pd.DataFrame()
pn = {(int(r.ZK), int(r.POR_STR_HL)): str(r.ZKRATKAO30) for r in ros.itertuples()}
zname = cm.NAZEVZAST.to_dict()


def dopad(zk, dV, dC):
    s0, e0 = outcome(ros, rk, cm, zk)
    s1, e1 = outcome(ros, rk, cm, zk, dV, dC)
    zm = [f'{pn.get((zk, p), p)} {s0[p]}→{s1[p]}' for p in s0 if s0[p] != s1[p]]
    if zm:
        return 'Mění mandáty: ' + '; '.join(zm)
    if e1 != e0:
        jm = {(int(r.POR_STR_HL), int(r.PORCISLO)): r.PRIJMENI for r in rk[rk.ZK == zk].itertuples()}
        return 'Mění zvolené: ' + ', '.join(jm.get(k, str(k)) for k in sorted(e1 - e0)) + ' místo ' + ', '.join(jm.get(k, str(k)) for k in sorted(e0 - e1))
    return 'Bez vlivu'


# ---------------- P8: přesun hlasů mezi stranami ----------------
def zz(v, r):
    return ((v / r.T) - r.e) / math.sqrt(max(r.e * (1 - r.e) / max(r.n, 1), 1e-9)) / r.scale


def cross_z(zk, oid, strana):
    """z druhého lístku: u MČ z_mc (podíl na lístku MČ proti očekávání z lístku města), u města z_mag."""
    if not len(CR):
        return None
    if zk != MAGISTRAT * 100 + 1:
        c = CR[(CR.ZK == zk) & (CR.OID == oid) & (CR.strana_mc == strana)]
        return float(c.z_mc.iloc[0]) if len(c) else None
    c = CR[(CR.OID == oid) & CR.strany_mag_cisla.apply(lambda s: strana in s)]
    return float(c.z_mag.iloc[0]) if len(c) else None


n_sous = {}
for _zk, _g in SH.groupby('ZK'):
    _o = set(_g.OID)
    for _x in _o:
        n_sous[(_zk, _x)] = sum(1 for y in nb.get(_x, []) if y in _o)


def p8():
    out = []
    S = SH[SH.e.notna() & (SH['T'] > 0)]
    for (zk, oid), g in S.groupby(['ZK', 'OID']):
        M = int(g.M.iloc[0])
        g = g.assign(E=g.e * g['T'], d=lambda x: x.e * x['T'] - x.hlasy)
        neg = g[(g.z <= -3) & (g.d >= max(3 * M, 30))]
        pos = g[(g.z >= 3) & (-g.d >= max(3 * M, 30))]
        for a in neg.itertuples():
            for b in pos.itertuples():
                t = min(a.d, -b.d); bal = t / max(a.d, -b.d)
                za, zb = zz(a.hlasy + t, a), zz(b.hlasy - t, b)
                gain = a.z ** 2 + b.z ** 2 - za ** 2 - zb ** 2
                if bal < 0.5 or abs(za) >= 2.5 or abs(zb) >= 2.5 or gain < 25:
                    continue
                ca, cb = cross_z(zk, oid, a.strana), cross_z(zk, oid, b.strana)
                hab = None
                if SHP is not None:
                    pq = SHP[(SHP.OID == oid) & (SHP.ZK == zk)]
                    pp = pq.set_index('nazev').z
                    hab = (pp.get(a.nazev), pp.get(b.nazev))
                    # strany se mezi volbami přejmenovávají: okrsek s podobně rozevřenými podíly už minule = místní struktura
                    okr_minule = len(pq) and pq.z.min() <= -3 and pq.z.max() >= 3
                else:
                    okr_minule = False
                # na lístku MČ i města: chyba zápisu je jen na jednom lístku → z druhého lístku musí ukázat stejný směr
                potv = [c_ <= -2 for c_ in [ca] if c_ is not None] + [c_ >= 2 for c_ in [cb] if c_ is not None]
                if not potv:
                    druhy = 'n/a'
                elif all(potv):
                    druhy = 'potvrzuje'
                elif not any(potv):
                    druhy = 'místní podpora'
                else:
                    druhy = 'nejasné'
                zvyk = bool(okr_minule) or (hab is not None and ((hab[0] is not None and hab[0] <= -2) or (hab[1] is not None and hab[1] >= 2)))
                # očekávání z ≥ 4 sousedních okrsků téhož zastupitelstva (jinak jen „zbytek obce“ – části obce se liší doopravdy)
                maly = n_sous.get((zk, oid), 0) < 4
                if druhy == 'místní podpora':
                    jist = 0
                elif zvyk or maly or druhy == 'nejasné':
                    jist = 2
                elif druhy == 'potvrzuje':
                    jist = 4 if bal >= 0.7 and len(potv) == 2 else 3
                else:
                    jist = 3
                ti = int(round(t))
                out.append(dict(OID=oid, ZK=zk, zast=zname.get(zk), X=a.nazev, hlasy_X=int(a.hlasy), ocek_X=int(a.E), z_X=round(a.z, 1),
                                Y=b.nazev, hlasy_Y=int(b.hlasy), ocek_Y=int(b.E), z_Y=round(b.z, 1), presun=ti, presun_listku=round(t / M, 1),
                                vyvazenost=round(bal, 2), z_po=(round(za, 1), round(zb, 1)), druhy_listek=(None if ca is None else round(ca, 1), None if cb is None else round(cb, 1), druhy),
                                predchozi=(None if not hab or hab[0] is None else round(hab[0], 1), None if not hab or hab[1] is None else round(hab[1], 1)),
                                zvyk=zvyk, jistota=jist, dopad=dopad(zk, {int(a.strana): ti, int(b.strana): -ti}, None)))
    return pd.DataFrame(out)


# ---------------- P9: izolovaný nadbytek kandidáta ----------------
def rates(zk, p):
    """Nadbytek kandidátů nad medián kandidátky po okrscích, relativně k mediánu (stejně jako anomalies.candidate_anomalies)."""
    val = sorted(rk[(rk.ZK == zk) & (rk.POR_STR_HL == p) & (rk.PLATNOST == 'A')].PORCISLO)
    g = hl[(hl.ZK == zk) & (hl.POR_STR_HL == p)]
    X = g.set_index('OID')[[HCOLS[i - 1] for i in val]].astype(float); X.columns = val
    X = X[X.sum(axis=1) > 0]
    base = X.median(axis=1)
    return X.sub(base, axis=0).div(base.clip(lower=1), axis=0), base, X


def p9():
    if not len(SP):
        return pd.DataFrame()
    out = []
    SPP = pd.read_pickle(f'{RES}/spikes_{YP}.pkl') if YP and os.path.exists(f'{RES}/spikes_{YP}.pkl') else pd.DataFrame()
    cand = SP[(SP.nadbytek >= np.maximum(40, 4 * SP.typicky_nadbytek.clip(lower=1))) & (SP.z >= 8)]
    # ≥ 3 kandidáti téže strany v jednom okrsku = vzor úseku kandidátky (pravidla P2/P4), ne jednotlivý kandidát
    vic = SP.groupby(['ZK', 'OID', 'strana']).size()
    cand = cand[[vic.get((r.ZK, r.OID, r.strana), 0) < 3 for r in cand.itertuples()]]
    for r in cand.itertuples():
        zk, p, c, oid = int(r.ZK), int(r.strana), int(r.porcislo), r.OID
        if len(TY) and len(TY[(TY.ZK == zk) & (TY.OID == oid) & (TY.strana == p) & (TY.porcislo == c)]):
            continue  # už nález překlepu
        R, base, X = rates(zk, p)
        rr = R[c]; me = rr.drop(oid).median()
        sous = [o for o in nb.get(oid, []) if o in rr.index]
        sous_max = rr[sous].max() if sous else np.nan
        izol = sous and (sous_max - me) < 0.4 * (rr[oid] - me)
        # druhý lístek: stejný kandidát (jméno) na lístku města / MČ ve stejném okrsku
        nm = rk[(rk.ZK == zk) & (rk.POR_STR_HL == p) & (rk.PORCISLO == c)].iloc[0]
        jin = rk[(rk.ZK != zk) & (rk.JMENO == nm.JMENO) & (rk.PRIJMENI == nm.PRIJMENI) & (rk.ZK.isin(hl[hl.OID == oid].ZK.unique()))]
        druhy = None
        if len(jin):
            j = jin.iloc[0]; R2, _, _ = rates(int(j.ZK), int(j.POR_STR_HL))
            if oid in R2.index and int(j.PORCISLO) in R2.columns:
                r2 = R2[int(j.PORCISLO)]; druhy = round(float((r2[oid] - r2.drop(oid).median()) / max(rr[oid] - me, 1e-9)), 2)
        zvyk = bool(len(SPP) and len(SPP[(SPP.OID == oid) & (SPP.jmeno == r.jmeno)]))
        nadb = int(round(r.nadbytek - r.typicky_nadbytek))
        dp = dopad(zk, {p: -nadb}, {(p, c): -nadb})
        if druhy is not None and druhy >= 0.4:
            jist = 0  # nadbytek i na druhém lístku = skutečná místní obliba
        elif not izol or zvyk:
            jist = 1
        elif dp == 'Bez vlivu':
            jist = 1  # domácí obliba kandidáta je běžná; samostatný nález jen tam, kde oprava mění výsledek
        else:
            jist = 3 if druhy is not None else 2
        out.append(dict(OID=oid, ZK=zk, zast=zname.get(zk), strana=pn.get((zk, p)), porcislo=c, jmeno=r.jmeno, hlasy=int(r.hlasy), zaklad=r.zaklad,
                        nadbytek=int(r.nadbytek), typicky=r.typicky_nadbytek, nasobek=round(r.nadbytek / max(r.typicky_nadbytek, 1), 1), z=round(r.z, 1),
                        sousede_max=round(float(sous_max - me) / max(rr[oid] - me, 1e-9), 2) if sous else None, izolovany=bool(izol),
                        druhy_listek=druhy, predchozi_volby=zvyk, jistota=jist,
                        dopad=dp))
    return pd.DataFrame(out)


pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 70); pd.set_option('display.max_columns', 30)
A = p8(); B = p9()
dst = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'results', '_p8p9'), f'{os.environ.get("AUDIT_UNIT", "praha")}_{Y}')
A.to_pickle(dst + '_p8.pkl'); B.to_pickle(dst + '_p9.pkl')
print(f'== P8 ({len(A)} kandidátů, jistota≥3: {int((A.jistota >= 3).sum()) if len(A) else 0})')
if len(A):
    print(A.sort_values(['jistota', 'presun'], ascending=False).drop(columns=['ZK']).to_string(index=False))
print(f'\n== P9 ({len(B)} kandidátů, jistota≥2: {int((B.jistota >= 2).sum()) if len(B) else 0})')
if len(B):
    print(B.sort_values(['jistota', 'nasobek'], ascending=False).drop(columns=['ZK']).to_string(index=False))
