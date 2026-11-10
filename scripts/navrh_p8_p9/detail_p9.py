import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd, numpy as np
SP = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'results', '_p8p9'), f'souhrn_p9_{sys.argv[1]}.pkl'))
D = D[(D.jistota >= 2) & (D.dopad != 'Bez vlivu')]
for slug, g in D.groupby('slug'):
    P = os.path.join(r'C:\git\volebni-analyza\data\processed\kv', slug)
    hl = pd.read_pickle(os.path.join(P, f'hl_{sys.argv[1]}.pkl')); rk = pd.read_pickle(os.path.join(P, f'rk_{sys.argv[1]}.pkl'))
    hl['OID'] = hl.OBEC.astype(str) + '/' + hl.OKRSEK.astype(str)
    for r in g.itertuples():
        zk = r.ZK; kod, ob = zk // 100, zk % 100
        c = rk[(rk.KODZASTUP == kod) & (rk.COBVODU == ob) & (rk.PRIJMENI == r.jmeno.split()[-1]) & (rk.PORCISLO == r.porcislo)].iloc[0]
        h = hl[(hl.KODZASTUP == kod) & (hl.POR_STR_HL == c.POR_STR_HL)].set_index('OID')
        col = f'HLASY_{r.porcislo:02d}'
        v = h.loc[r.OID, [f'HLASY_{i:02d}' for i in range(max(1, r.porcislo - 3), r.porcislo + 4)]].astype(int).tolist()
        dal = h[col].astype(int).sort_values(ascending=False)
        print(f'{slug:18s} {r.OID:13s} {r.jmeno:22s} č.{r.porcislo:<2d} ({str(r.strana)[:25]}) hodnoty č.{max(1,r.porcislo-3)}–{r.porcislo+3}: {v} | '
              f'kandidát celkem {int(c.POCHLASU)}, v ostatních okrscích: {dal.drop(r.OID).head(6).tolist()} | {r.dopad[:70]}')
