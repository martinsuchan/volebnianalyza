"""Forenzní audit 2. kola senátních voleb 2026 (16.–17. 10. 2026).

Zdroj okrskových dat: CSV ČSÚ (set5.csv, KOLO = 2), jakmile je zveřejněno; do té doby poslední hlášení každého okrsku
z XML dávek volební noci (data/raw/se2026/davky_k2). Oficiální součty obvodů a zvolení: data/raw/se2026/vysledky_souhrn.xml.
Srovnání: 1. kolo 2026 ve stejném okrsku a 2. kola let 2018, 2020 a 2022.

Výstupy v data/results/se2_*.pkl|json. Spouštět po se_etl.py a se_audit.py (scripts/download.py stáhne dávky i souhrn).
"""
import glob, json, os, sys
import xml.etree.ElementTree as ET
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, P0 as P, RES0 as RES
from se_audit import neighbours, solve_rho, batches, batch_changes, NAMES

RAW = os.path.join(ROOT, 'data', 'raw')
HC = [f'HLASY_{i:02d}' for i in range(1, 23)]
NS = {'s': 'http://www.volby.cz/senat/'}


def rd_latest(pattern):
    """Nejnovější verze CSV ČSÚ (při opravě dat vychází nový zip s novým datem v názvu)."""
    fs = sorted(f for f in glob.glob(os.path.join(RAW, pattern), recursive=True) if os.sep + 'csv_od' + os.sep not in f)
    return pd.read_csv(fs[-1], sep=';', encoding='cp1250', low_memory=False)


def souhrn():
    """Oficiální výsledky obvodů (obě kola) ze souhrnného XML ČSÚ."""
    r = ET.parse(os.path.join(RAW, 'se2026', 'vysledky_souhrn.xml')).getroot()
    kand, ucast = [], []
    for o in r.findall('s:OBVOD', NS):
        ob = int(o.get('CISLO'))
        for k in o.findall('s:KANDIDAT', NS):
            kand.append(dict(OBVOD=ob, NAZEV_OBV=o.get('NAZEV'), CKAND=int(k.get('PORADOVE_CISLO')), JMENO=k.get('JMENO'), PRIJMENI=k.get('PRIJMENI'),
                             HLASY_K1=int(k.get('HLASY_1KOLO')), ZVOLEN_K1=k.get('ZVOLEN_1KOLO'),
                             HLASY_K2=int(k.get('HLASY_2KOLO')) if k.get('HLASY_2KOLO') else None, ZVOLEN_K2=k.get('ZVOLEN_2KOLO')))
        for u in o.findall('s:UCAST', NS):
            ucast.append(dict(OBVOD=ob, KOLO=int(u.get('KOLO')), **{c: int(u.get(c)) for c in ('OKRSKY_CELKEM', 'OKRSKY_ZPRAC', 'ZAPSANI_VOLICI', 'VYDANE_OBALKY',
                                                                                                  'VOLICSKE_PRUKAZY', 'ODEVZDANE_OBALKY', 'PLATNE_HLASY')}))
    return pd.DataFrame(kand), pd.DataFrame(ucast), r.get('DATUM_CAS_GENEROVANI')


def k2_okrsky():
    """Okrskové zápisy 2. kola 2026: CSV (je-li zveřejněno), jinak poslední hlášení okrsku z XML dávek."""
    t = rd_latest('se2026/*data*/**/set5.csv')
    if (t.KOLO == 2).any():
        t = t[t.KOLO == 2].copy(); t['zdroj'] = 'csv'
        b = batches('davky_k2')
    else:
        b = batches('davky_k2')
        last = b.sort_values(['davka', 'zprac']).drop_duplicates('OID', keep='last')
        rows = []
        for r in last.itertuples():
            h = json.loads(r.hlasy)
            d = dict(OBEC=r.OBEC, OKRSEK=r.OKRSEK, OBVOD=r.OBVOD, KOLO=2, VOL_SEZNAM=r.VOL, VYD_OBALKY=r.VYD, VOL_PRUKAZ=r.VP, ODEVZ_OBAL=r.ODEVZ, PL_HL_CELK=r.PL)
            d.update({c: int(h.get(str(i + 1), 0)) for i, c in enumerate(HC)})
            rows.append(d)
        t = pd.DataFrame(rows); t['zdroj'] = 'xml'
    t['OID'] = t.OBEC.astype(str) + '/' + t.OKRSEK.astype(str)
    t['NAZOBEC'] = t.OBEC.map(NAMES)
    t['INV'] = t.ODEVZ_OBAL - t.PL_HL_CELK
    return t.reset_index(drop=True), b


def finalisti(kand):
    f = kand[kand.HLASY_K2.notna()].sort_values(['OBVOD', 'CKAND'])
    return {o: (int(g.CKAND.iloc[0]), int(g.CKAND.iloc[1])) for o, g in f.groupby('OBVOD') if len(g) == 2}


# ---------------------------------------------------------------- 1. reprodukce a integrita
def reprodukce(t, kand, ucast):
    out = []
    for o, g in t.groupby('OBVOD'):
        k = kand[(kand.OBVOD == o) & kand.HLASY_K2.notna()]
        u = ucast[(ucast.OBVOD == o) & (ucast.KOLO == 2)].iloc[0]
        d = dict(OBVOD=o, okrsku=len(g), okrsku_oficialne=int(u.OKRSKY_CELKEM), okrsku_zprac=int(u.OKRSKY_ZPRAC),
                 volici=int(g.VOL_SEZNAM.sum()), volici_of=int(u.ZAPSANI_VOLICI), vydane=int(g.VYD_OBALKY.sum()), vydane_of=int(u.VYDANE_OBALKY),
                 odevzdane=int(g.ODEVZ_OBAL.sum()), odevzdane_of=int(u.ODEVZDANE_OBALKY), platne=int(g.PL_HL_CELK.sum()), platne_of=int(u.PLATNE_HLASY))
        d['kand_shoda'] = all(int(g[f'HLASY_{int(r.CKAND):02d}'].sum()) == int(r.HLASY_K2) for r in k.itertuples())
        d['shoda'] = d['kand_shoda'] and all(d[c] == d[c + '_of'] for c in ('volici', 'vydane', 'odevzdane', 'platne'))
        out.append(d)
    return pd.DataFrame(out)


def integrita(t, fin, t1):
    """Deterministické kontroly zápisu 2. kola a srovnání se seznamem voličů 1. kola."""
    out = []
    k1 = t1.set_index('OID')
    for r in t.itertuples():
        a, b = fin.get(r.OBVOD, (None, None))
        hl = [getattr(r, c) for c in HC]
        chk = [('A1', 'Vydáno více obálek, než je zapsaných voličů', r.VYD_OBALKY > r.VOL_SEZNAM, f'{r.VYD_OBALKY} > {r.VOL_SEZNAM}'),
               ('A2', 'Odevzdáno více obálek, než bylo vydáno', r.ODEVZ_OBAL > r.VYD_OBALKY, f'{r.ODEVZ_OBAL} > {r.VYD_OBALKY}'),
               ('A3', 'Platných hlasů více než odevzdaných obálek', r.PL_HL_CELK > r.ODEVZ_OBAL, f'{r.PL_HL_CELK} > {r.ODEVZ_OBAL}'),
               ('A4', 'Součet hlasů kandidátů nesouhlasí s platnými hlasy', sum(hl) != r.PL_HL_CELK, f'{sum(hl)} ≠ {r.PL_HL_CELK}'),
               ('A5', 'Hlasy pro kandidáta, který do 2. kola nepostoupil', any(v for i, v in enumerate(hl) if i + 1 not in (a, b)),
                ', '.join(f'č. {i + 1}: {v}' for i, v in enumerate(hl) if v and i + 1 not in (a, b)))]
        if r.OID in k1.index:
            v1 = int(k1.at[r.OID, 'VOL_SEZNAM'])
            chk.append(('A6', 'Počet zapsaných voličů se mezi koly výrazně změnil', abs(r.VOL_SEZNAM - v1) > max(20, 0.05 * v1), f'1. kolo {v1}, 2. kolo {r.VOL_SEZNAM}'))
        for kod, popis, bad, hodnota in chk:
            if bad:
                out.append(dict(kod=kod, popis=popis, OID=r.OID, OBVOD=r.OBVOD, obec=r.NAZOBEC, hodnota=hodnota))
    return pd.DataFrame(out, columns=['kod', 'popis', 'OID', 'OBVOD', 'obec', 'hodnota'])


# ---------------------------------------------------------------- 2. model podílu finalisty podle 1. kola
def model(t, t1, fin, rk):
    """Podíl finalisty A na hlasech obou finalistů v okrsku; očekávání z 1. kola téhož okrsku:
    logit(p2) = α + β·logit(p1) + γ·podíl ostatních kandidátů v 1. kole (vážená regrese po obvodech).
    Rozptyl beta-binomický (nadrozptyl ρ odhadnut z reziduí obvodu)."""
    k1 = t1.set_index('OID')
    by = {(r.OBVOD, r.CKAND): str(r.BYDLISTEN) for r in rk.itertuples()}
    jm = {(r.OBVOD, r.CKAND): f'{r.JMENO} {r.PRIJMENI}' for r in rk.itertuples()}
    rows = []
    for o, g in t.groupby('OBVOD'):
        if o not in fin:
            continue
        a, b = fin[o]
        g = g[g.OID.isin(k1.index) & (g.PL_HL_CELK > 0)].copy()
        A, B = g[f'HLASY_{a:02d}'].values.astype(float), g[f'HLASY_{b:02d}'].values.astype(float)
        n = A + B
        A1 = k1.loc[g.OID, f'HLASY_{a:02d}'].values.astype(float); B1 = k1.loc[g.OID, f'HLASY_{b:02d}'].values.astype(float)
        N1 = k1.loc[g.OID, 'PL_HL_CELK'].values.astype(float)
        x1 = np.log((A1 + .5) / (B1 + .5)); x2 = (N1 - A1 - B1) / np.maximum(N1, 1)
        y = np.log((A + .5) / (B + .5))
        X = np.column_stack([np.ones_like(x1), x1, x2])
        w = 1 / (1 / (A + .5) + 1 / (B + .5))
        sw = np.sqrt(w)
        coef = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
        # robustní dofitování: vynechat odlehlé okrsky (|reziduum| > 4 MAD) a přepočítat
        res = (y - X @ coef) * sw
        keep = np.abs(res - np.median(res)) < 4 * 1.4826 * np.median(np.abs(res - np.median(res)))
        coef = np.linalg.lstsq(X[keep] * sw[keep, None], y[keep] * sw[keep], rcond=None)[0]
        p = 1 / (1 + np.exp(-(X @ coef)))
        r = A - n * p
        rho = solve_rho(r[keep], n[keep], p[keep])
        var = n * p * (1 - p) * (1 + rho * (n - 1))
        z = r / np.sqrt(np.maximum(var, 1e-9))
        zs = (B - n * p) / np.sqrt(np.maximum(var, 1e-9))  # po prohození A ↔ B
        for i, (oid, obec) in enumerate(zip(g.OID, g.NAZOBEC)):
            rows.append(dict(OID=oid, OBVOD=o, obec=obec, A=a, B=b, kandA=jm.get((o, a)), kandB=jm.get((o, b)), hlasyA=int(A[i]), hlasyB=int(B[i]),
                             n=int(n[i]), A1=int(A1[i]), B1=int(B1[i]), N1=int(N1[i]), p=float(p[i]), ocekA=float(n[i] * p[i]), z=float(z[i]), z_prohozeni=float(zs[i]),
                             rho=float(rho), beta=float(coef[1]),
                             domovA=str(obec).lower() == by.get((o, a), '').split(' - ')[0].strip().lower(),
                             domovB=str(obec).lower() == by.get((o, b), '').split(' - ')[0].strip().lower()))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 3. účast, neplatné hlasy, obálky
def ucast_a_obalky(t, t1):
    """Pokles účasti mezi koly (poměr vydaných obálek) proti sousedním okrskům; neplatné hlasy a nevrácené obálky."""
    k1 = t1.set_index('OID')
    t = t[t.OID.isin(k1.index)].reset_index(drop=True).copy()
    t['VYD1'] = k1.loc[t.OID, 'VYD_OBALKY'].values
    nb = neighbours(t, 8)
    lr = np.log((t.VYD_OBALKY + 1) / (t.VYD1 + 1)).values
    med = np.array([np.median(lr[nb[i]]) if len(nb[i]) else np.nan for i in range(len(t))])
    d = lr - med
    s = 1.4826 * np.nanmedian(np.abs(d - np.nanmedian(d)))
    t['pomer'] = t.VYD_OBALKY / t.VYD1.replace(0, np.nan)
    t['pomer_okoli'] = np.exp(med)
    t['z_ucast'] = d / s
    # neplatné: proti sousedům ve 2. kole (beta-binomicky)
    inv, ob = t.INV.values.astype(float), t.ODEVZ_OBAL.values.astype(float)
    pe = np.array([(inv[nb[i]].sum() + 1) / (ob[nb[i]].sum() + 50) for i in range(len(t))])
    r = inv - ob * pe
    rho = solve_rho(r, ob, pe)
    t['inv_ocek'] = ob * pe
    t['z_inv'] = r / np.sqrt(np.maximum(ob * pe * (1 - pe) * (1 + rho * (ob - 1)), 1e-9))
    t['GAP'] = t.VYD_OBALKY - t.ODEVZ_OBAL
    return t


def historie():
    """Srovnávací ukazatele 2. kol 2018–2026: účast 2. / 1. kolo, neplatné hlasy, nevrácené obálky."""
    out = {}
    for y in (2018, 2020, 2022):
        t = rd_latest(f'se{y}/*data*/**/set5.csv')
        k1, k2 = t[t.KOLO == 1], t[t.KOLO == 2]
        ob = set(k2.OBVOD)
        k1 = k1[k1.OBVOD.isin(ob)]
        out[y] = dict(obvodu=len(ob), okrsku=int(len(k2)), ucast_k1=float(k1.VYD_OBALKY.sum() / k1.VOL_SEZNAM.sum()), ucast_k2=float(k2.VYD_OBALKY.sum() / k2.VOL_SEZNAM.sum()),
                      neplatne_k2=float((k2.ODEVZ_OBAL - k2.PL_HL_CELK).sum() / k2.ODEVZ_OBAL.sum()),
                      nevracene_k2=float((k2.VYD_OBALKY - k2.ODEVZ_OBAL).sum() / k2.VYD_OBALKY.sum()),
                      okrsky_gap10=int(((k2.VYD_OBALKY - k2.ODEVZ_OBAL) >= 10).sum()))
    return out


def otisky(t, fin):
    """Globální testy 2. kola: poslední číslice hlasů finalistů (≥ 100), celá procenta účasti (Kobak)."""
    v = np.concatenate([t[t.OBVOD == o][[f'HLASY_{a:02d}', f'HLASY_{b:02d}']].values.ravel() for o, (a, b) in fin.items()])
    v3 = v[v >= 100]
    ld = np.bincount(v3 % 10, minlength=10)
    mx = int(v3.max()) + 60
    hist_v = np.bincount(v3, minlength=mx).astype(float)
    ker = np.exp(-0.5 * (np.arange(-40, 41) / 8.0) ** 2); ker /= ker.sum()
    dens = np.convolve(hist_v, ker, mode='same'); dens[:100] = 0
    exp_ld = np.array([dens[dd::10].sum() for dd in range(10)]); exp_ld = exp_ld / exp_ld.sum() * ld.sum()
    big = t[t.VOL_SEZNAM >= 100]
    pct = big.VYD_OBALKY * 100 / big.VOL_SEZNAM
    obs_int = int((np.abs(pct - np.round(pct)) < 1e-9).sum())
    rng = np.random.default_rng(1)
    sims = []
    for _ in range(300):
        tv = rng.binomial(big.VOL_SEZNAM.values, (big.VYD_OBALKY / big.VOL_SEZNAM).values)
        pp = tv * 100 / big.VOL_SEZNAM.values
        sims.append(int((np.abs(pp - np.round(pp)) < 1e-9).sum()))
    sims = np.array(sims)
    return dict(n_digits=int(len(v3)), last_digit=ld.tolist(), last_digit_exp=exp_ld.tolist(), last_digit_p=float(stats.chisquare(ld, exp_ld).pvalue),
                kobak_obs=obs_int, kobak_sim_mean=float(sims.mean()), kobak_sim_p=float((sims >= obs_int).mean()))


def vysledky(kand, ucast):
    """Výsledek obvodu: vítěz, poražený, rozdíl a kolik hlasů by muselo změnit kandidáta, aby se výsledek obrátil."""
    out = []
    for o, g in kand[kand.HLASY_K2.notna()].groupby('OBVOD'):
        g = g.sort_values('HLASY_K2', ascending=False)
        w, l = g.iloc[0], g.iloc[1]
        u2 = ucast[(ucast.OBVOD == o) & (ucast.KOLO == 2)].iloc[0]; u1 = ucast[(ucast.OBVOD == o) & (ucast.KOLO == 1)].iloc[0]
        diff = int(w.HLASY_K2 - l.HLASY_K2)
        out.append(dict(OBVOD=o, nazev=w.NAZEV_OBV, vitez=f'{w.JMENO} {w.PRIJMENI}', CKAND_v=int(w.CKAND), hlasy_v=int(w.HLASY_K2),
                        porazeny=f'{l.JMENO} {l.PRIJMENI}', CKAND_p=int(l.CKAND), hlasy_p=int(l.HLASY_K2), platne=int(u2.PLATNE_HLASY),
                        podil_v=float(w.HLASY_K2 / u2.PLATNE_HLASY), rozdil=diff, k_obratu=diff // 2 + 1,
                        vitez_1k_poradi=int((kand[(kand.OBVOD == o)].HLASY_K1 > w.HLASY_K1).sum()) + 1, hlasy_v_k1=int(w.HLASY_K1), hlasy_p_k1=int(l.HLASY_K1),
                        zvolen=w.ZVOLEN_K2, ucast_k1=float(u1.VYDANE_OBALKY / u1.ZAPSANI_VOLICI), ucast_k2=float(u2.VYDANE_OBALKY / u2.ZAPSANI_VOLICI),
                        neplatne_k2=float((u2.ODEVZDANE_OBALKY - u2.PLATNE_HLASY) / u2.ODEVZDANE_OBALKY)))
    v = pd.DataFrame(out)
    # obvody rozhodnuté v 1. kole
    k1 = kand[(kand.ZVOLEN_K1 == 'ZVOLEN')]
    return v, k1[['OBVOD', 'NAZEV_OBV', 'JMENO', 'PRIJMENI', 'HLASY_K1']]


if __name__ == '__main__':
    if not os.path.exists(os.path.join(RAW, 'se2026', 'vysledky_souhrn.xml')):
        sys.exit(print('2. kolo: chybí data (spusťte scripts/download.py) – přeskočeno') or 0)
    kand, ucast, gen = souhrn()
    if kand.HLASY_K2.isna().all():
        sys.exit(print('2. kolo: ČSÚ zatím nezveřejnil výsledky – přeskočeno') or 0)
    t, b = k2_okrsky()
    t1 = pd.read_pickle(os.path.join(P, 'se_t5_2026.pkl'))
    t1['OID'] = t1.OBEC.astype(str) + '/' + t1.OKRSEK.astype(str)
    rk = pd.read_pickle(os.path.join(P, 'se_rk_2026.pkl'))
    fin = finalisti(kand)
    rep = reprodukce(t, kand, ucast)
    integ = integrita(t, fin, t1)
    M = model(t, t1, fin, rk)
    U = ucast_a_obalky(t, t1)
    bc, bs = batch_changes(b, t)
    V, k1z = vysledky(kand, ucast)
    summ = dict(generovano_souhrn=gen, zdroj=str(t.zdroj.iloc[0]), obvodu=int(len(fin)), okrsku=int(len(t)),
                okrsku_zprac=int(ucast[ucast.KOLO == 2].OKRSKY_ZPRAC.sum()), okrsku_celkem=int(ucast[ucast.KOLO == 2].OKRSKY_CELKEM.sum()),
                reprodukce_shoda=int(rep.shoda.sum()), reprodukce_obvodu=int(len(rep)),
                ucast_k1=float(t1[t1.OBVOD.isin(fin)].VYD_OBALKY.sum() / t1[t1.OBVOD.isin(fin)].VOL_SEZNAM.sum()),
                ucast_k2=float(t.VYD_OBALKY.sum() / t.VOL_SEZNAM.sum()), neplatne_k2=float(t.INV.sum() / t.ODEVZ_OBAL.sum()),
                nevracene_k2=float((t.VYD_OBALKY - t.ODEVZ_OBAL).sum() / t.VYD_OBALKY.sum()), okrsky_gap10=int(((t.VYD_OBALKY - t.ODEVZ_OBAL) >= 10).sum()),
                integrita=integ.kod.value_counts().to_dict(), model_z4=int((M.z.abs() >= 4).sum()), model_n=int(len(M)),
                davky=bs, historie=historie(), otisky=otisky(t, fin),
                rozhodnuto_v_1_kole=[f'{r.NAZEV_OBV} ({r.OBVOD}): {r.JMENO} {r.PRIJMENI}' for r in k1z.itertuples()])
    for nm, df in (('okrsky', t), ('reprodukce', rep), ('integrita', integ), ('model', M), ('ucast', U), ('zmeny', bc), ('vysledky', V), ('davky', b)):
        df.to_pickle(f'{RES}/se2_{nm}.pkl')
    json.dump(summ, open(f'{RES}/se2_summary.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v for k, v in summ.items() if k not in ('otisky',)}, ensure_ascii=False, indent=1, default=str)[:3000])
    print(V[['OBVOD', 'nazev', 'vitez', 'hlasy_v', 'porazeny', 'hlasy_p', 'rozdil', 'k_obratu', 'ucast_k2']].sort_values('rozdil').to_string(index=False))
