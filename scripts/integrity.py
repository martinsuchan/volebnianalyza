"""Deterministic integrity checks of precinct records (zápisy okrskových komisí)."""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, __import__('os').path.dirname(__file__))
from common import load, HCOLS, RES, MAGISTRAT


def checks(year):
    d = load(year); t3, hl, ros, rk = d['t3'], d['hl'], d['ros'], d['rk']
    out = []
    def add(rows, code, desc, sev, val=None):
        for _, r in rows.iterrows():
            out.append(dict(rok=year, kod=code, popis=desc, zavaznost=sev, OID=r.OID, MC=r.MC,
                            KODZASTUP=int(r.KODZASTUP), TYPZASTUP=int(r.TYPZASTUP),
                            hodnota=None if val is None else (val(r) if callable(val) else r[val])))
    add(t3[t3.VYD_OBALKY > t3.VOL_SEZNAM], 'A1', 'Vydáno více obálek než zapsaných voličů', 3,
        lambda r: f'{r.VYD_OBALKY} > {r.VOL_SEZNAM}')
    add(t3[t3.ODEVZ_OBAL > t3.VYD_OBALKY], 'A2', 'Odevzdáno více obálek, než bylo vydáno', 2,
        lambda r: f'odevzdáno {r.ODEVZ_OBAL} > vydáno {r.VYD_OBALKY}')
    if t3.PLAT_LISTKY.notna().any():
        add(t3[t3.PLAT_LISTKY > t3.ODEVZ_OBAL], 'A3', 'Více platných lístků než odevzdaných obálek', 3,
            lambda r: f'{r.PLAT_LISTKY} > {r.ODEVZ_OBAL}')
        add(t3[t3.PL_HL_CELK > t3.PLAT_LISTKY * t3.MANDATY], 'A4', 'Více hlasů, než umožňuje počet platných lístků × mandátů', 3,
            lambda r: f'{r.PL_HL_CELK} > {r.PLAT_LISTKY}×{r.MANDATY}')
    # party sums vs PL_HL_CELK
    ps = hl.groupby(['OID', 'TYPZASTUP']).POC_HLASU.sum().rename('SUM_STR')
    x = t3.merge(ps, left_on=['OID', 'TYPZASTUP'], right_index=True, how='left')
    add(x[x.SUM_STR != x.PL_HL_CELK], 'A5', 'Součet hlasů stran ≠ platné hlasy celkem', 3,
        lambda r: f'{r.SUM_STR} vs {r.PL_HL_CELK}')
    nz = hl[hl.POC_HLASU > 0].groupby(['OID', 'TYPZASTUP']).size().rename('NZ')
    x = x.merge(nz, left_on=['OID', 'TYPZASTUP'], right_index=True, how='left').fillna({'NZ': 0})
    add(x[x.NZ != x.POC_VS_HL], 'A6', 'Počet stran s hlasy neodpovídá údaji POC_VS_HL', 1,
        lambda r: f'{int(r.NZ)} vs {r.POC_VS_HL}')
    # candidate sum vs party votes
    h = hl.copy(); h['CSUM'] = h[HCOLS].sum(axis=1)
    bad = h[h.CSUM != h.POC_HLASU].merge(t3[['OID', 'TYPZASTUP', 'MC']].drop_duplicates(), on=['OID', 'TYPZASTUP'])
    add(bad, 'A7', 'Součet hlasů kandidátů ≠ hlasy strany', 3, lambda r: f'strana {r.POR_STR_HL}: {r.CSUM} vs {r.POC_HLASU}')
    # candidate > valid ballots (impossible: one ballot = max one vote per candidate)
    if t3.PLAT_LISTKY.notna().any():
        h = h.merge(t3[['OID', 'TYPZASTUP', 'PLAT_LISTKY', 'MANDATY', 'MC']], on=['OID', 'TYPZASTUP'])
        h['CMAX'] = h[HCOLS].max(axis=1)
        add(h[h.CMAX > h.PLAT_LISTKY], 'A8', 'Kandidát má více hlasů než je platných lístků v okrsku', 3,
            lambda r: f'strana {r.POR_STR_HL}: max {r.CMAX} > {r.PLAT_LISTKY}')
        nc = ros.set_index(['ZK', 'POR_STR_HL']).NCAND
        h['NCAND'] = [nc.get((k, p), np.nan) for k, p in zip(h.ZK, h.POR_STR_HL)]
        lim = h.PLAT_LISTKY * np.minimum(h.NCAND, h.MANDATY)
        add(h[h.POC_HLASU > lim], 'A9', 'Strana má více hlasů, než je fyzicky možné', 3,
            lambda r: f'strana {r.POR_STR_HL}: {r.POC_HLASU}')
        # votes for candidates beyond list length
        npos = rk.groupby(['ZK', 'POR_STR_HL']).PORCISLO.max()
        h['NPOS'] = [npos.get((k, p), 70) for k, p in zip(h.ZK, h.POR_STR_HL)]
        def beyond(r):
            n = r.NPOS
            return int(n) < 70 and r[HCOLS[int(n):]].sum() > 0
        b = h[[beyond(r) for _, r in h.iterrows()]] if len(h) < 60000 else h.iloc[:0]
        add(b, 'A10', 'Hlasy pro neexistující pořadí kandidáta', 3, 'POR_STR_HL')
    # magistrát vs MČ envelope consistency (same envelope)
    w = t3.pivot_table(index='OID', columns='TYPZASTUP', values=['VOL_SEZNAM', 'VYD_OBALKY', 'ODEVZ_OBAL'])
    for c in ['VOL_SEZNAM', 'VYD_OBALKY', 'ODEVZ_OBAL']:
        if (c, 2) in w:
            mm = w[(w[(c, 1)] != w[(c, 2)]) & w[(c, 2)].notna()]
            for oid in mm.index:
                out.append(dict(rok=year, kod='A11', popis=f'{c} se liší mezi lístkem magistrátu a MČ', zavaznost=2,
                                OID=oid, MC=t3[t3.OID == oid].MC.iloc[0], KODZASTUP=MAGISTRAT, TYPZASTUP=1,
                                hodnota=f'{mm.loc[oid, (c, 1)]} vs {mm.loc[oid, (c, 2)]}'))
    if 'CHYBA' in t3:
        add(t3[t3.CHYBA == 1], 'A12', 'Záznam ČSÚ označen příznakem CHYBA=1', 1, 'CHYBA')
    # reproducibility: okrsky sums == official totals
    agg = hl.groupby(['ZK', 'POR_STR_HL']).POC_HLASU.sum()
    off = ros.set_index(['ZK', 'POR_STR_HL']).HLASY_STR
    j = pd.concat([agg.rename('okrsky'), off.rename('oficialni')], axis=1).dropna()
    diff = j[j.okrsky != j.oficialni]
    for (k, p), r in diff.iterrows():
        out.append(dict(rok=year, kod='A13', popis='Součet okrsků ≠ oficiální výsledek strany', zavaznost=3,
                        OID='', MC=d['councils'].NAZEVZAST.get(k), KODZASTUP=int(k // 100), TYPZASTUP=0,
                        hodnota=f'strana {p}: {r.okrsky} vs {r.oficialni}'))
    cagg = hl.groupby(['ZK', 'POR_STR_HL'])[HCOLS].sum().stack().rename('okrsky').reset_index()
    cagg['PORCISLO'] = cagg.level_2.str[-2:].astype(int)
    cc = cagg.merge(rk[['ZK', 'POR_STR_HL', 'PORCISLO', 'POCHLASU']], on=['ZK', 'POR_STR_HL', 'PORCISLO'])
    cd = cc[cc.okrsky != cc.POCHLASU]
    for _, r in cd.iterrows():
        out.append(dict(rok=year, kod='A14', popis='Součet okrsků ≠ oficiální hlasy kandidáta', zavaznost=3,
                        OID='', MC=d['councils'].NAZEVZAST.get(r.ZK), KODZASTUP=int(r.ZK // 100), TYPZASTUP=0,
                        hodnota=f'strana {r.POR_STR_HL} kand {r.PORCISLO}: {r.okrsky} vs {r.POCHLASU}'))
    summ = dict(rok=year, okrsku=int(t3.OID.nunique()), zaznamu_t3=len(t3), zaznamu_hl=len(hl),
                stran_overeno=len(j), kandidatu_overeno=len(cc))
    return pd.DataFrame(out), summ


if __name__ == '__main__':
    allf, summs = [], []
    for y in (2018, 2022, 2026):
        f, s = checks(y); allf.append(f); summs.append(s)
        print(y, s); print(f.groupby(['kod', 'popis']).size().to_string() if len(f) else 'no findings')
    F = pd.concat(allf); F.to_csv(f'{RES}/integrity.csv', index=False)
    json.dump(summs, open(f'{RES}/integrity_summary.json', 'w'), ensure_ascii=False, indent=1)
