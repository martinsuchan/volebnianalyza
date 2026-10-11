"""Deep-dive of a single precinct: both ballots, neighbour expectation, 2022 comparison, batch history."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import RES, MAGISTRAT
from anomalies import prep

pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 45)


def show(oid, years=(2026, 2022)):
    for y in years:
        d, t3, hl, ros, nb = prep(y)
        R = pd.read_pickle(f'{RES}/shares_{y}.pkl')
        print(f'===== {y} okrsek {oid}  sousedé: {nb.get(oid)}')
        print(t3[t3.OID == oid][['TYPZASTUP', 'ZK', 'VOL_SEZNAM', 'VYD_OBALKY', 'ODEVZ_OBAL', 'PLAT_LISTKY', 'PL_HL_CELK', 'MANDATY']].to_string())
        r = R[R.OID == oid][['ZK', 'strana', 'nazev', 'hlasy', 'e', 's', 'z', 'exp_ballots']].copy()
        r['ocek_hlasy'] = (r.e * R[R.OID == oid]['T']).round(); r['e'] = (100 * r.e).round(2); r['s'] = (100 * r.s).round(2)
        print(r.round(2).to_string())


if __name__ == '__main__':
    for o in sys.argv[1:]:
        show(o)
