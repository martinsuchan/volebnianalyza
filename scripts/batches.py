"""Parse ČSÚ incremental XML batches (dávky) – processing times, re-sent precincts, first vs final values."""
import glob, os, sys
import xml.etree.ElementTree as ET
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, RES, load

NS = '{http://www.volby.cz/kv/}'


def parse():
    rows, votes = [], []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data/raw/kv2026/davky/d*.xml'))):
        root = ET.parse(f).getroot()
        dav = root.find(NS + 'DAVKA'); bn = int(dav.get('PORADI_DAVKY')); gen = root.get('DATUM_CAS_GENEROVANI')
        for ok in root.findall(NS + 'OKRSEK'):
            u = ok.find(NS + 'UCAST_OKRSEK')
            if u is None:
                continue
            kz = int(ok.get('KODZASTUP'))
            obec = int(ok.get('CIS_OBEC'))
            r = dict(davka=bn, generovano=gen, OBEC=obec, OKRSEK=int(ok.get('CIS_OKRSEK')), KODZASTUP=kz,
                     typ=ok.get('OZNAC_TYPU'), poradi=int(ok.get('PORADI_ZPRAC')), cas=ok.get('DATUM_CAS_ZPRAC'),
                     opakovane=int(ok.get('OPAKOVANE')), **{k: int(v) for k, v in u.attrib.items()})
            rows.append(r)
            for h in ok.findall(NS + 'HLASY_OKRSEK'):
                votes.append(dict(davka=bn, OBEC=obec, OKRSEK=r['OKRSEK'], KODZASTUP=kz,
                                  POR_STR_HL=int(h.get('POR_STR_HLAS_LIST')), HLASY=int(h.get('HLASY'))))
    return pd.DataFrame(rows), pd.DataFrame(votes)


if __name__ == '__main__':
    B, V = parse()
    d = load(2026); t3 = d['t3']
    praha_obce = set(t3.OBEC)
    B = B[B.OBEC.isin(praha_obce)].copy(); V = V[V.OBEC.isin(praha_obce)].copy()
    B['OID'] = B.OBEC.astype(str) + '/' + B.OKRSEK.astype(str)
    B['cas'] = pd.to_datetime(B.cas)
    print('Prague batch records', len(B), 'unique precinct×council', B[['OID', 'KODZASTUP']].drop_duplicates().shape[0])
    print('OPAKOVANE counts', B.opakovane.value_counts().to_dict(), 'typ', B.typ.value_counts().to_dict())
    rep = B.groupby(['OID', 'KODZASTUP']).size(); print('precincts sent >1x', (rep > 1).sum())
    # first vs last transmission per precinct×council
    first = B.sort_values(['davka', 'poradi']).groupby(['OID', 'KODZASTUP']).first()
    last = B.sort_values(['davka', 'poradi']).groupby(['OID', 'KODZASTUP']).last()
    cols = ['ZAPSANI_VOLICI', 'VYDANE_OBALKY', 'ODEVZDANE_OBALKY', 'PLATNE_LISTKY', 'PLATNE_HLASY']
    chg = (first[cols] != last[cols]).any(axis=1)
    print('precinct×council with changed totals between first and last transmission:', chg.sum())
    # compare last transmission with final CSV
    fin = t3.set_index(['OID', 'KODZASTUP'])[['VOL_SEZNAM', 'VYD_OBALKY', 'ODEVZ_OBAL', 'PLAT_LISTKY', 'PL_HL_CELK']]
    fin.columns = cols
    j = last[cols].join(fin, rsuffix='_fin', how='outer')
    diffcsv = j[(j[cols].values != j[[c + '_fin' for c in cols]].values).any(axis=1)]
    print('last batch vs final CSV differences:', len(diffcsv))
    B.to_pickle(f'{RES}/batches_2026.pkl'); V.to_pickle(f'{RES}/batch_votes_2026.pkl')
    ch = first[chg].join(last[chg][cols], rsuffix='_last')
    ch.to_pickle(f'{RES}/batch_changes_2026.pkl')
    pd.set_option('display.width', 250)
    print(ch.reset_index()[['OID', 'KODZASTUP', 'davka', 'opakovane'] + cols + [c + '_last' for c in cols]].head(40).to_string())
    print(diffcsv.head(20).to_string())
    print('time range', B.cas.min(), B.cas.max())
