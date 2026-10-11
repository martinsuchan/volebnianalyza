"""Detector of 'missing ballot stacks': valid ballots whose votes were not transcribed.

For every precinct × council: votes-per-valid-ballot (vpb = PL_HL_CELK / (PLAT_LISTKY·M)) vs. the
neighbour median. The deficit is converted to ballot-equivalents and attributed to the parties with the
largest negative residual against the neighbour model; their candidate vectors are summarised
(median candidate votes ≈ number of party-box ballots).
"""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import HCOLS, RES
from anomalies import prep, MAD


def detect(year):
    d, t3, hl, ros, nb = prep(year)
    R = pd.read_pickle(f'{RES}/shares_{year}.pkl')
    t = t3.copy()
    t['vpb'] = t.PL_HL_CELK / (t.PLAT_LISTKY * t.MANDATY)
    vp = t.set_index(['ZK', 'OID']).vpb
    rows = []
    for zk, g in t.groupby('ZK'):
        g = g.set_index('OID'); M = int(g.MANDATY.iloc[0])
        for o, r in g.iterrows():
            nn = [x for x in nb.get(o, []) if x in g.index]
            if len(nn) < 3:
                nn = [x for x in g.index if x != o]
            if len(nn) < 2:
                continue
            ev = np.median(g.loc[nn, 'vpb']); sd = max(MAD * np.median(np.abs(g.loc[nn, 'vpb'] - ev)), 0.012)
            deficit_votes = ev * r.PLAT_LISTKY * M - r.PL_HL_CELK
            rows.append(dict(rok=year, ZK=zk, OID=o, MC=r.MC, M=M, PLAT_LISTKY=r.PLAT_LISTKY, ODEVZ_OBAL=r.ODEVZ_OBAL,
                             PL_HL_CELK=r.PL_HL_CELK, vpb=r.vpb, vpb_ocek=ev, z_vpb=(r.vpb - ev) / sd,
                             chybi_hlasu=deficit_votes, chybi_listku=deficit_votes / M))
    D = pd.DataFrame(rows)
    # attribute deficit to parties with largest negative residuals
    att = []
    for _, r in D[D.z_vpb < -4].iterrows():
        rr = R[(R.ZK == r.ZK) & (R.OID == r.OID)].copy()
        rr['dif'] = rr.hlasy - rr.e * rr['T']
        neg = rr.sort_values('dif').head(3)
        att.append('; '.join(f'{x.nazev} ({int(x.hlasy)} vs ~{int(x.e * x["T"])})' for _, x in neg.iterrows() if x.dif < -100))
    D.loc[D.z_vpb < -4, 'podezrele_strany'] = att
    return D


if __name__ == '__main__':
    pd.set_option('display.width', 260); pd.set_option('display.max_colwidth', 120)
    for y in (2022, 2026):
        D = detect(y); D.to_pickle(f'{RES}/missing_{y}.pkl')
        f = D[D.z_vpb < -4].sort_values('z_vpb')
        print('=====', y, 'flagged', len(f), 'of', len(D))
        print(f[['ZK', 'OID', 'MC', 'M', 'PLAT_LISTKY', 'vpb', 'vpb_ocek', 'z_vpb', 'chybi_hlasu', 'chybi_listku', 'podezrele_strany']].round(3).to_string())
