"""Dodatečná kontrola P8 v obcích bez druhého lístku: byla strana X nebo Y ve stejném okrsku v předchozích volbách normální?
Párování stran přes kód strany (VSTRANA), u místních uskupení se sdíleným kódem přes název. Výstup: tabulka případů s jistotou ≥ 3."""
import sys, os, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd, numpy as np
SP = os.path.dirname(os.path.abspath(__file__))
Y = int(sys.argv[1]); YP = {2026: 2022, 2022: 2018}[Y]
os.environ.setdefault('AUDIT_UNIT', 'praha')
from common import RES, load


def kody(ros):
    r = ros.copy(); r['ZK'] = r.KODZASTUP * 100 + r.COBVODU
    n = r.groupby(['ZK', 'VSTRANA']).size()
    out = {}
    for x in r.itertuples():
        jednoznacny = n.get((x.ZK, x.VSTRANA), 0) == 1 and x.VSTRANA not in (80, 90, 99)
        out[(x.ZK, int(x.POR_STR_HL))] = ('k', int(x.VSTRANA)) if jednoznacny else ('n', str(x.ZKRATKAO30))
    return out


A = pd.read_pickle(sys.argv[2])
A = A[A.jistota >= 3]
rows = []
for slug, g in A.groupby('slug'):
    os.environ['AUDIT_UNIT'] = slug
    res = os.path.join(r'C:\git\volebni-analyza\data\results\kv', slug)
    SH = pd.read_pickle(os.path.join(res, f'shares_{Y}.pkl'))
    p = os.path.join(res, f'shares_{YP}.pkl')
    SHP = pd.read_pickle(p) if os.path.exists(p) else None
    proc = os.path.join(r'C:\git\volebni-analyza\data\processed\kv', slug)
    K = kody(pd.read_pickle(os.path.join(proc, f'ros_{Y}.pkl')))
    KP = kody(pd.read_pickle(os.path.join(proc, f'ros_{YP}.pkl'))) if os.path.exists(os.path.join(proc, f'ros_{YP}.pkl')) else {}
    for r in g.itertuples():
        s = SH[(SH.ZK == r.ZK) & (SH.OID == r.OID)].set_index('nazev').strana
        zp = []
        for nm in (r.X, r.Y):
            key = K.get((r.ZK, int(s[nm])))
            z = None
            if SHP is not None and key:
                q = SHP[(SHP.ZK == r.ZK) & (SHP.OID == r.OID)]
                for x in q.itertuples():
                    if KP.get((r.ZK, int(x.strana))) == key or (key[0] == 'n' and x.nazev == nm):
                        z = round(float(x.z), 1)
            zp.append(z)
        normal = [abs(z) < 2 for z in zp if z is not None]
        rows.append(dict(slug=slug, OID=r.OID, X=r.X[:30], Y=r.Y[:30], z_X=r.z_X, z_Y=r.z_Y, presun_listku=r.presun_listku,
                         druhy=r.druhy_listek[2], z_predchozi=tuple(zp), dukaz_predchozi=bool(normal) and all(normal), dopad=r.dopad[:60]))
D = pd.DataFrame(rows)
pd.set_option('display.width', 250)
print(D.to_string(index=False))
print('s doložením z předchozích voleb:', int(D.dukaz_predchozi.sum()), 'z', len(D))
