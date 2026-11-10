import glob, os, json, csv, re
import pandas as pd
import sys
ROKS = sys.argv[1] if len(sys.argv) > 1 else '2026'
SP = os.path.dirname(os.path.abspath(__file__))
R = r'C:\git\volebni-analyza'
pd.set_option('display.width', 260); pd.set_option('display.max_colwidth', 55); pd.set_option('display.max_rows', 500)
soudy = list(csv.DictReader(open(os.path.join(R, 'soudy', 'podani_2026.csv'), encoding='utf-8-sig')))


def nalezy(slug, oid):
    p = os.path.join(R, 'data', 'results', 'kv', slug, f'findings_{ROKS}.json')
    if not os.path.exists(p):
        return ''
    F = json.load(open(p, encoding='utf-8'))
    return ' '.join(f['id'] for f in F if oid in str(f.get('OID')).replace(' ', '').split(','))


def soud(slug, oid, mc):
    okr = oid.split('/')[1]
    hit = [r['spis'] + ' ' + (r['rozhodnuti'] or 'běží') for r in soudy if r['slug'] == slug and okr in r['okrsky_v_podani'].split()
           and (not mc or not r['mc'] or r['mc'] == mc)]
    return '; '.join(hit)


rows = {'p8': [], 'p9': []}
stat = {'p8': {}, 'p9': {}}
for f in sorted(glob.glob(os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'results', '_p8p9'), f'*_{ROKS}_p8.pkl'))):
    slug = os.path.basename(f)[:-len(f'_{ROKS}_p8.pkl')]
    for k in ('p8', 'p9'):
        D = pd.read_pickle(f.replace('_p8.pkl', f'_{k}.pkl'))
        if not len(D):
            continue
        for j, n in D.jistota.value_counts().items():
            stat[k][j] = stat[k].get(j, 0) + n
        D = D[D.jistota >= 2].copy()
        if not len(D):
            continue
        D.insert(0, 'slug', slug)
        rows[k].append(D)
for k in ('p8', 'p9'):
    print(f'== {k.upper()} počty podle jistoty (všechny jednotky):', dict(sorted(stat[k].items())))
    if not rows[k]:
        continue
    D = pd.concat(rows[k], ignore_index=True)
    D['nalez_v_okrsku'] = [nalezy(r.slug, r.OID) for r in D.itertuples()]
    D['soud'] = [soud(r.slug, r.OID, r.zast if r.zast != r.slug else '') for r in D.itertuples()]
    D.to_pickle(os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'results', '_p8p9'), f'souhrn_{k}_{ROKS}.pkl'))
    cols = (['slug', 'OID', 'zast', 'X', 'hlasy_X', 'ocek_X', 'Y', 'hlasy_Y', 'ocek_Y', 'presun', 'presun_listku', 'vyvazenost', 'druhy_listek', 'zvyk', 'jistota', 'dopad', 'nalez_v_okrsku', 'soud']
            if k == 'p8' else ['slug', 'OID', 'zast', 'strana', 'porcislo', 'jmeno', 'hlasy', 'zaklad', 'nadbytek', 'typicky', 'sousede_max', 'druhy_listek', 'jistota', 'dopad', 'nalez_v_okrsku', 'soud'])
    D = D.sort_values(['jistota', 'slug'], ascending=[False, True])
    print(f'-- jistota ≥ 3: {int((D.jistota >= 3).sum())}, jistota 2: {int((D.jistota == 2).sum())}')
    print(D[D.jistota >= 3][cols].to_string(index=False))
    print('\n-- jistota 2 (jen souhrn), které mění výsledek:')
    print(D[(D.jistota == 2) & (D.dopad != 'Bez vlivu')][cols].to_string(index=False))
    print()
