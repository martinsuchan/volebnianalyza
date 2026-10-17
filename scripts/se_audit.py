"""Forenzní audit 1. kola senátních voleb 2026 (27 obvodů) + srovnání s KV 2026 a s lety 2018/2020/2022.

Výstupy v data/results/se_*.pkl|json. Spouštět po se_etl.py.
"""
import glob, json, os, re, sys
import xml.etree.ElementTree as ET
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, P0 as P, RES0 as RES

HC = [f'HLASY_{i:02d}' for i in range(1, 23)]
YEARS = (2018, 2020, 2022, 2026)
KV_PAIR = {2018: 2018, 2022: 2022, 2026: 2026}  # senát souběžně s KV
CEN = pd.read_pickle(os.path.join(P, 'se_centroids.pkl')).set_index('OID')
NAMES = pd.read_csv(os.path.join(ROOT, 'data/raw/se2026/SE2026ciselniky20261011_csv/csv/cisob.csv'), sep=';',
                    encoding='cp1250').drop_duplicates('OBEC_PREZ').set_index('OBEC_PREZ').NAZEVOBCE


def load(y):
    t5 = pd.read_pickle(os.path.join(P, f'se_t5_{y}.pkl')).reset_index(drop=True)
    rk = pd.read_pickle(os.path.join(P, f'se_rk_{y}.pkl'))
    obv = pd.read_pickle(os.path.join(P, f'se_obv_{y}.pkl')).set_index('OBVOD').NAZEV_OBV
    t5['NAZOBEC'] = t5.OBEC.map(NAMES)
    t5['NAZOBV'] = t5.OBVOD.map(obv)
    t5['INV'] = t5.ODEVZ_OBAL - t5.PL_HL_CELK
    return t5, rk, obv


def neighbours(t5, k=8):
    """Indexy k nejbližších okrsků ve stejném senátním obvodu (bez okrsku samotného)."""
    nb = {}
    xy = CEN.reindex(t5.OID)[['lon', 'lat']].values * np.array([np.cos(np.radians(49.8)), 1.0])
    for o, idx in t5.groupby('OBVOD').groups.items():
        idx = np.array(list(idx))
        have = idx[~np.isnan(xy[idx, 0])]
        for i in idx:
            if np.isnan(xy[i, 0]):  # bez geometrie: okrsky téže obce, jinak nejbližší čísla
                same = [j for j in idx if t5.OBEC[j] == t5.OBEC[i] and j != i]
                nb[i] = np.array(same[:k] if same else [j for j in idx if j != i][:k]); continue
            d = ((xy[have] - xy[i]) ** 2).sum(1)
            order = have[np.argsort(d)]
            nb[i] = order[order != i][:k]
    return nb


def solve_rho(r, n, p):
    """Beta-binomická overdisperze: var = n p q (1 + rho (n-1)); rho tak, aby medián z² = 0,455 (medián χ²₁)."""
    base = n * p * (1 - p)
    ok = base > 0.5
    r, n, base = r[ok], n[ok], base[ok]
    if len(r) < 20:
        return 0.0
    f = lambda rho: np.median(r ** 2 / (base * (1 + rho * (n - 1)))) - 0.455
    if f(0) <= 0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    return hi


# ---------------------------------------------------------------- 1. reprodukce a integrita
def reproduce(y):
    t5, rk, obv = load(y)
    out = []
    for o, g in t5.groupby('OBVOD'):
        r = rk[rk.OBVOD == o].sort_values('CKAND')
        sums = g[HC].sum()
        for c in r.itertuples():
            out.append(dict(rok=y, OBVOD=o, CKAND=c.CKAND, okrsky=int(sums[f'HLASY_{c.CKAND:02d}']), oficialni=int(c.HLASY_K1)))
    df = pd.DataFrame(out)
    # přepočet postupu: > 50 % zvolen, jinak první dva postupují
    adv = []
    for o, g in df.groupby('OBVOD'):
        tot = g.okrsky.sum(); s = g.sort_values('okrsky', ascending=False)
        top = s.iloc[0]
        if top.okrsky * 2 > tot:
            adv += [(o, top.CKAND, 1)]
        else:
            adv += [(o, s.iloc[0].CKAND, 2), (o, s.iloc[1].CKAND, 2)]
    a = pd.DataFrame(adv, columns=['OBVOD', 'CKAND', 'ZV'])
    off = rk[rk.ZVOLEN_K1 > 0][['OBVOD', 'CKAND', 'ZVOLEN_K1']]
    m = a.merge(off, on=['OBVOD', 'CKAND'], how='outer')
    return df, int((df.okrsky != df.oficialni).sum()), int((m.ZV != m.ZVOLEN_K1).sum())


def integrity(y):
    t5, rk, obv = load(y)
    nk = rk[rk.PLATNOST == 'A'].groupby('OBVOD').CKAND.max() if 'PLATNOST' in rk else rk.groupby('OBVOD').CKAND.max()
    out = []
    def add(rows, kod, popis, zav, val):
        for r in rows.itertuples():
            out.append(dict(rok=y, kod=kod, popis=popis, zavaznost=zav, OID=r.OID, OBVOD=r.OBVOD, obec=r.NAZOBEC, okrsek=r.OKRSEK, hodnota=val(r)))
    add(t5[t5.VYD_OBALKY > t5.VOL_SEZNAM], 'S1', 'Vydáno více obálek než zapsaných voličů', 3, lambda r: f'{r.VYD_OBALKY} > {r.VOL_SEZNAM}')
    add(t5[t5.ODEVZ_OBAL > t5.VYD_OBALKY], 'S2', 'Odevzdáno více obálek, než bylo vydáno', 2, lambda r: f'odevzdáno {r.ODEVZ_OBAL} > vydáno {r.VYD_OBALKY}')
    add(t5[t5.PL_HL_CELK > t5.ODEVZ_OBAL], 'S3', 'Více platných hlasů než odevzdaných obálek', 3, lambda r: f'{r.PL_HL_CELK} > {r.ODEVZ_OBAL}')
    add(t5[t5[HC].sum(axis=1) != t5.PL_HL_CELK], 'S4', 'Součet hlasů kandidátů ≠ platné hlasy', 3, lambda r: f'{sum(getattr(r, c) for c in HC)} vs {r.PL_HL_CELK}')
    beyond = [any(getattr(r, f'HLASY_{i:02d}') > 0 for i in range(int(nk.get(r.OBVOD, 22)) + 1, 23)) for r in t5.itertuples()]
    add(t5[beyond], 'S5', 'Hlasy pro neexistující číslo kandidáta', 3, lambda r: 'ano')
    gap = t5.VYD_OBALKY - t5.ODEVZ_OBAL
    add(t5[(gap >= 10) & (gap >= 0.03 * t5.VYD_OBALKY)], 'S6', 'Velký rozdíl vydaných a odevzdaných obálek', 2,
        lambda r: f'vydáno {r.VYD_OBALKY}, odevzdáno {r.ODEVZ_OBAL} (−{r.VYD_OBALKY - r.ODEVZ_OBAL})')
    add(t5[(t5.INV == 0) & (t5.ODEVZ_OBAL >= 300)], 'S7', 'Nula neplatných hlasů ve velkém okrsku', 1, lambda r: f'{r.ODEVZ_OBAL} obálek, 0 neplatných')
    add(t5[t5.CHYBA == 1], 'S8', 'Záznam ČSÚ s příznakem CHYBA=1', 1, lambda r: 'CHYBA=1')
    add(t5[t5.OPRAVA == 1], 'S9', 'Zápis opravován (OPRAVA=1)', 0, lambda r: 'OPRAVA=1')
    if t5.VOL_PRUKAZ.notna().any():
        add(t5[t5.VOL_PRUKAZ > t5.VYD_OBALKY], 'S10', 'Více voličských průkazů než vydaných obálek', 3, lambda r: f'{r.VOL_PRUKAZ} > {r.VYD_OBALKY}')
    return pd.DataFrame(out)


def completeness(y):
    """Okrsky KV v obcích senátního obvodu (dle číselníku SECOCO), které v datech Senátu chybí."""
    if y not in KV_PAIR:
        return pd.DataFrame()
    t5, rk, obv = load(y)
    co = glob.glob(os.path.join(ROOT, f'data/raw/se{y}/*cis*/**/secoco.csv'), recursive=True)
    co = [f for f in co if os.sep + 'csv_od' + os.sep not in f] or co
    co = pd.read_csv(co[0], sep=';', encoding='cp1250')
    kv = pd.read_pickle(os.path.join(P, f'kvnat_{KV_PAIR[y]}.pkl'))
    have = set(t5.OID)
    miss = []
    for r in co.itertuples():
        rng = [(getattr(r, f'MINOKRSEK{i}' if i < 10 else 'MINOKRSE10'), getattr(r, f'MAXOKRSEK{i}' if i < 10 else 'MAXOKRSE10')) for i in range(1, 11)]
        rng = [(a, b) for a, b in rng if a > 0]
        ks = kv[kv.OBEC == r.OBEC]
        for k in ks.itertuples():
            if (not rng or any(a <= k.OKRSEK <= b for a, b in rng)) and k.OID not in have:
                miss.append(dict(rok=y, OID=k.OID, OBVOD=r.OBVOD, obec=r.NAZEVOBCE, KV_VOL=k.KV_VOL))
    return pd.DataFrame(miss)


# ---------------------------------------------------------------- 2. Senát × KV
def se_vs_kv(y):
    t5, rk, obv = load(y)
    kv = pd.read_pickle(os.path.join(P, f'kvnat_{KV_PAIR[y]}.pkl'))
    x = t5.merge(kv.drop(columns=['OBEC', 'OKRSEK']), on='OID', how='left')
    x['VP'] = x.VOL_PRUKAZ.fillna(0)
    nb = neighbours(x)
    m = x.KV_ODEVZ.notna() & (x.KV_ODEVZ > 0)
    # očekávaný poměr SE/KV odevzdaných obálek ze sousedů (sdružený)
    r_exp, dv_exp = np.full(len(x), np.nan), np.full(len(x), np.nan)
    for i in range(len(x)):
        j = [k for k in nb[i] if m[k]]
        if j:
            r_exp[i] = x.ODEVZ_OBAL[j].sum() / x.KV_ODEVZ[j].sum()
            dv_exp[i] = (x.VOL_SEZNAM[j] - x.KV_VOL[j]).sum() / x.KV_VOL[j].sum()
    x['r'] = x.ODEVZ_OBAL / x.KV_ODEVZ
    x['r_exp'] = r_exp
    x['diff_obal'] = x.ODEVZ_OBAL - x.KV_ODEVZ
    x['exc_obal'] = x.ODEVZ_OBAL - r_exp * x.KV_ODEVZ  # přebytek/deficit senátních obálek vůči očekávání
    u = x.exc_obal / np.sqrt(x.KV_ODEVZ * r_exp.clip(0.05, 0.95) * (1 - r_exp.clip(0.05, 0.95)) + 1)
    med, mad = np.nanmedian(u), stats.median_abs_deviation(u, nan_policy='omit', scale='normal')
    x['z_obal'] = (u - med) / mad
    x['dvol'] = x.VOL_SEZNAM - x.KV_VOL
    x['dvol_exc'] = x.dvol - dv_exp * x.KV_VOL
    x['dvyd'] = x.VYD_OBALKY - x.KV_VYD
    x['gap_se'] = x.VYD_OBALKY - x.ODEVZ_OBAL
    x['gap_kv'] = x.KV_VYD - x.KV_ODEVZ
    return x


def find_record_swaps(x):
    """Páry okrsků téže obce, jejichž senátní záznamy odpovídají KV údajům toho druhého (záměna zápisů)."""
    out = []
    big = x[(x.dvol.abs() >= 25) & x.KV_VOL.notna()]
    for obec, g in big.groupby('OBEC'):
        allg = x[(x.OBEC == obec) & x.KV_VOL.notna()]
        for a in g.itertuples():
            for b in allg.itertuples():
                if b.OID == a.OID:
                    continue
                now = abs(a.VOL_SEZNAM - a.KV_VOL) + abs(b.VOL_SEZNAM - b.KV_VOL)
                sw = abs(a.VOL_SEZNAM - b.KV_VOL) + abs(b.VOL_SEZNAM - a.KV_VOL)
                if sw <= 0.15 * now and now >= 50:
                    out.append(dict(A=a.OID, B=b.OID, obec=a.NAZOBEC, OBVOD=a.OBVOD,
                                    SE_vol_A=a.VOL_SEZNAM, KV_vol_A=a.KV_VOL, SE_vol_B=b.VOL_SEZNAM, KV_vol_B=b.KV_VOL,
                                    SE_vyd_A=a.VYD_OBALKY, KV_vyd_A=a.KV_VYD, SE_vyd_B=b.VYD_OBALKY, KV_vyd_B=b.KV_VYD,
                                    shoda_pred=now, shoda_po=sw))
    df = pd.DataFrame(out)
    if len(df):
        df['key'] = [tuple(sorted((a, b))) for a, b in zip(df.A, df.B)]
        df = df.drop_duplicates('key').drop(columns='key')
    return df


# ---------------------------------------------------------------- 3. hlasy kandidátů
def candidate_model(y, k=8):
    t5, rk, obv = load(y)
    nb = neighbours(t5, k)
    rows = []
    for o, idx in t5.groupby('OBVOD').groups.items():
        idx = np.array(list(idx))
        K = int(rk[rk.OBVOD == o].CKAND.max())
        V = t5.loc[idx, HC[:K]].values.astype(float)
        n = t5.loc[idx, 'PL_HL_CELK'].values.astype(float)
        dist = V.sum(0) / V.sum()
        pos = {g: i for i, g in enumerate(idx)}
        E = np.zeros_like(V)
        for a, g in enumerate(idx):
            j = [pos[h] for h in nb[g] if h in pos]
            pv = V[j].sum(0); pn = n[j].sum()
            E[a] = (pv + 30 * dist) / (pn + 30)  # mírné smrštění k průměru obvodu
        Pm = E
        resid = V - n[:, None] * Pm
        rho = np.array([solve_rho(resid[:, c], n, Pm[:, c]) for c in range(K)])
        var = n[:, None] * Pm * (1 - Pm) * (1 + rho[None, :] * (n[:, None] - 1))
        Z = resid / np.sqrt(np.maximum(var, 1e-9))
        for a, g in enumerate(idx):
            for c in range(K):
                rows.append((g, o, c + 1, V[a, c], n[a] * Pm[a, c], Z[a, c], Pm[a, c], rho[c], n[a]))
    df = pd.DataFrame(rows, columns=['ix', 'OBVOD', 'CKAND', 'hlasy', 'ocek', 'z', 'p', 'rho', 'n'])
    df['OID'] = t5.OID.values[df.ix]
    df['obec'] = t5.NAZOBEC.values[df.ix]
    df['OBEC'] = t5.OBEC.values[df.ix]
    jm = {(r.OBVOD, r.CKAND): f'{r.JMENO} {r.PRIJMENI}' for r in rk.itertuples()}
    by = {(r.OBVOD, r.CKAND): str(r.BYDLISTEN) for r in rk.itertuples()}
    df['kandidat'] = [jm.get((o, c), f'kandidát č. {c}') for o, c in zip(df.OBVOD, df.CKAND)]
    df['bydliste'] = [by.get((o, c), '') for o, c in zip(df.OBVOD, df.CKAND)]
    df['domov'] = [str(ob).split('-')[0].strip().lower() == b.split(' - ')[0].strip().lower() or str(ob).lower() == b.lower()
                   for ob, b in zip(df.obec, df.bydliste)]
    return t5, df


def zero_test(df):
    """Kandidát s 0 hlasy, kde okolí čeká mnoho: P(0) pod beta-binomickým modelem."""
    z = df[(df.hlasy == 0) & (df.ocek >= 8)].copy()
    neff = z.n / (1 + z.rho * (z.n - 1))
    z['p0'] = np.exp(neff * np.log1p(-z.p.clip(1e-9, 0.999)))
    return z[z.p0 < 1e-4].sort_values('p0')


def swap_test(t5, df):
    """Záměna hlasů dvou kandidátů v okrsku: prohození dramaticky zlepší shodu s okolím."""
    out = []
    for ix, g in df.groupby('ix'):
        g = g.set_index('CKAND')
        for a in g.index:
            for b in g.index:
                if b <= a:
                    continue
                ga, gb = g.loc[a], g.loc[b]
                if ga.z * gb.z >= 0 or min(abs(ga.z), abs(gb.z)) < 3:
                    continue
                sa = ga.n * ga.p * (1 - ga.p) * (1 + ga.rho * (ga.n - 1)); sb = gb.n * gb.p * (1 - gb.p) * (1 + gb.rho * (gb.n - 1))
                za2 = (gb.hlasy - ga.ocek) / np.sqrt(sa); zb2 = (ga.hlasy - gb.ocek) / np.sqrt(sb)
                gain = ga.z ** 2 + gb.z ** 2 - za2 ** 2 - zb2 ** 2
                if gain >= 40 and abs(za2) < 3 and abs(zb2) < 3:
                    out.append(dict(ix=ix, OID=ga.OID, obec=ga.obec, OBVOD=ga.OBVOD, A=a, B=b, kandA=ga.kandidat, kandB=gb.kandidat,
                                    hlasyA=int(ga.hlasy), hlasyB=int(gb.hlasy), ocekA=ga.ocek, ocekB=gb.ocek, zA=ga.z, zB=gb.z,
                                    z_po_A=za2, z_po_B=zb2, zisk=gain, sousedni_cisla=abs(a - b) == 1))
    return pd.DataFrame(out).sort_values('zisk', ascending=False) if out else pd.DataFrame()


def invalid_test(t5, k=8):
    """Podíl neplatných obálek vůči sousedům (chybějící balík → neplatné / nezapočtené)."""
    nb = neighbours(t5, k)
    inv, ob = t5.INV.values.astype(float), t5.ODEVZ_OBAL.values.astype(float)
    pe = np.array([(inv[nb[i]].sum() + 1) / (ob[nb[i]].sum() + 50) for i in range(len(t5))])
    r = inv - ob * pe
    rho = solve_rho(r, ob, pe)
    z = r / np.sqrt(ob * pe * (1 - pe) * (1 + rho * (ob - 1)))
    x = t5[['OID', 'OBVOD', 'NAZOBEC', 'OKRSEK', 'ODEVZ_OBAL', 'PL_HL_CELK', 'INV']].copy()
    x['inv_ocek'] = ob * pe; x['z_inv'] = z; x['rho'] = rho
    return x


# ---------------------------------------------------------------- 4. otisky (fingerprints)
def fingerprints(y):
    t5, rk, obv = load(y)
    t5 = t5[t5.VOL_SEZNAM >= 50]
    turn = t5.VYD_OBALKY / t5.VOL_SEZNAM
    # vítěz obvodu (1. místo v 1. kole) – jeho podíl v okrsku
    lead = rk.loc[rk.groupby('OBVOD').HLASY_K1.idxmax()].set_index('OBVOD').CKAND
    ws = np.array([getattr(r, f'HLASY_{int(lead[r.OBVOD]):02d}') / r.PL_HL_CELK if r.PL_HL_CELK else np.nan for r in t5.itertuples()])
    H, xe, ye = np.histogram2d(turn.clip(0, 1), np.nan_to_num(ws).clip(0, 1), bins=50, range=[[0, 1], [0, 1]], weights=t5.VOL_SEZNAM)
    hi = float(((turn > .8) & (ws > .8)).sum())
    # poslední číslice hlasů kandidátů (≥ 10 hlasů), 2BL (druhá číslice, ≥ 10)
    v = t5[HC].values.ravel(); v = v[v >= 10]
    v3 = v[v >= 100]  # u dvoumístných čísel je poslední číslice zároveň druhou číslicí → strukturálně nerovnoměrná
    ld = np.bincount(v3 % 10, minlength=10)
    # očekávání z vyhlazené hustoty počtů (Gauss σ = 8): klesající hustota mírně zvýhodňuje nižší číslice
    mx = int(v3.max()) + 60
    hist_v = np.bincount(v3, minlength=mx).astype(float)
    ker = np.exp(-0.5 * (np.arange(-40, 41) / 8.0) ** 2); ker /= ker.sum()
    dens = np.convolve(hist_v, ker, mode='same'); dens[:100] = 0
    exp_ld = np.array([dens[d::10].sum() for d in range(10)]); exp_ld = exp_ld / exp_ld.sum() * ld.sum()
    chi_ld = stats.chisquare(ld, exp_ld)
    chi_ld_naive = stats.chisquare(ld)
    sd = np.array([int(str(int(a))[1]) for a in v])
    # Kobak: celá procenta účasti (okrsky ≥ 100 voličů) vs. simulace
    big = t5[t5.VOL_SEZNAM >= 100]
    pct = big.VYD_OBALKY * 100 / big.VOL_SEZNAM
    obs_int = int((np.abs(pct - np.round(pct)) < 1e-9).sum())
    rng = np.random.default_rng(1)
    sims = []
    for _ in range(300):
        tv = rng.binomial(big.VOL_SEZNAM.values, (big.VYD_OBALKY / big.VOL_SEZNAM).values)
        pp = tv * 100 / big.VOL_SEZNAM.values
        sims.append(int((np.abs(pp - np.round(pp)) < 1e-9).sum()))
    sims = np.array(sims)
    return dict(rok=y, okrsku=int(len(t5)), ucast=float(t5.VYD_OBALKY.sum() / t5.VOL_SEZNAM.sum()),
                neplatne=float(t5.INV.sum() / t5.ODEVZ_OBAL.sum()),
                klimek_hi=hi, klimek_hist=H.tolist(),
                last_digit=ld.tolist(), last_digit_exp=exp_ld.tolist(), last_digit_p=float(chi_ld.pvalue), last_digit_p_naive=float(chi_ld_naive.pvalue), n_digits=int(len(v3)),
                bl2_mean=float(sd.mean()), bl2_exp=4.187,
                kobak_obs=obs_int, kobak_sim_mean=float(sims.mean()), kobak_sim_p=float((sims >= obs_int).mean()),
                turnout_hist=np.histogram(turn.clip(0, 1), bins=50, range=(0, 1))[0].tolist())


# ---------------------------------------------------------------- 5. XML dávky
def batches(slozka='davky'):
    """Záznamy okrsků z XML dávek volební noci (slozka 'davky' = 1. kolo, 'davky_k2' = 2. kolo)."""
    ns = {'s': 'http://www.volby.cz/senat/'}
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, f'data/raw/se2026/{slozka}/d*.xml'))):
        r = ET.parse(f).getroot()
        d = r.find('s:DAVKA', ns)
        for ok in r.findall('s:OKRSEK', ns):
            u = ok.find('s:UCAST_OKRSEK', ns)
            h = {int(e.get('PORADOVE_CISLO')): int(e.get('HLASY')) for e in ok.findall('s:HLASY_OKRSEK', ns)}
            rows.append(dict(davka=int(d.get('PORADI_DAVKY')), gen=r.get('DATUM_CAS_GENEROVANI'), OBEC=int(ok.get('CIS_OBEC')),
                             OKRSEK=int(ok.get('CIS_OKRSEK')), OBVOD=int(ok.get('CIS_OBVOD')), zprac=ok.get('DATUM_CAS_ZPRAC'),
                             opak=int(ok.get('OPAKOVANE')), VOL=int(u.get('ZAPSANI_VOLICI')), VYD=int(u.get('VYDANE_OBALKY')),
                             VP=int(u.get('VOLICSKE_PRUKAZY')), ODEVZ=int(u.get('ODEVZDANE_OBALKY')), PL=int(u.get('PLATNE_HLASY')),
                             hlasy=json.dumps(h, sort_keys=True)))
    b = pd.DataFrame(rows)
    b['OID'] = b.OBEC.astype(str) + '/' + b.OKRSEK.astype(str)
    return b


def batch_changes(b, t5):
    ch = []
    for oid, g in b.groupby('OID'):
        if len(g) < 2:
            continue
        g = g.sort_values(['davka', 'zprac'])
        for a, c in zip(g.iloc[:-1].itertuples(), g.iloc[1:].itertuples()):
            diffs = [f'{k}: {getattr(a, k)} → {getattr(c, k)}' for k in ('VOL', 'VYD', 'VP', 'ODEVZ', 'PL') if getattr(a, k) != getattr(c, k)]
            ha, hc = json.loads(a.hlasy), json.loads(c.hlasy)
            diffs += [f'kand. {k}: {ha.get(k, 0)} → {hc.get(k, 0)}' for k in sorted(set(ha) | set(hc), key=int) if ha.get(k, 0) != hc.get(k, 0)]
            ch.append(dict(OID=oid, OBVOD=c.OBVOD, davka_pred=a.davka, davka_po=c.davka, cas_po=c.zprac, zmeny='; '.join(diffs) or 'beze změny'))
    # konzistence poslední verze s CSV
    last = b.sort_values(['davka', 'zprac']).drop_duplicates('OID', keep='last').set_index('OID')
    t = t5.set_index('OID')
    common = last.index.intersection(t.index)
    mism = int(((last.loc[common, 'PL'] != t.loc[common, 'PL_HL_CELK']) | (last.loc[common, 'ODEVZ'] != t.loc[common, 'ODEVZ_OBAL'])).sum())
    return pd.DataFrame(ch), dict(okrsku_v_davkach=int(b.OID.nunique()), zaznamu=int(len(b)), opakovane=int(b.opak.sum()),
                                  davek=int(b.davka.nunique()), neshoda_s_csv=mism, chybi_v_davkach=int(len(set(t.index) - set(b.OID))),
                                  prvni=b.zprac.min(), posledni=b.zprac.max())


# ---------------------------------------------------------------- 6. materialita
def margins(t5, rk):
    out = []
    for o, g in rk.groupby('OBVOD'):
        g = g.sort_values('HLASY_K1', ascending=False)
        tot = int(t5[t5.OBVOD == o].PL_HL_CELK.sum())
        v = g.HLASY_K1.values
        out.append(dict(OBVOD=o, platne=tot, prvni=g.iloc[0].PRIJMENI, druhy=g.iloc[1].PRIJMENI, treti=g.iloc[2].PRIJMENI if len(g) > 2 else '',
                        v1=int(v[0]), v2=int(v[1]), v3=int(v[2]) if len(v) > 2 else 0,
                        zvolen_1k=bool(v[0] * 2 > tot),
                        rozdil_nad_50=int(v[0] * 2 - tot),  # o kolik hlasů (×1) nad/pod nadpolovičním ziskem: přesun x hlasů mění o 2x
                        rozdil_2_3=int(v[1] - (v[2] if len(v) > 2 else 0))))
    return pd.DataFrame(out)


if __name__ == '__main__':
    summ = {}
    rep = {y: reproduce(y) for y in YEARS}
    summ['reprodukce'] = {y: dict(neshod_kandidatu=rep[y][1], neshod_postupu=rep[y][2], kandidatu=len(rep[y][0])) for y in YEARS}
    integ = pd.concat([integrity(y) for y in YEARS]); integ.to_pickle(f'{RES}/se_integrity.pkl')
    summ['integrita'] = integ.groupby(['kod', 'rok']).size().unstack(fill_value=0).to_dict()
    comp = pd.concat([completeness(y) for y in KV_PAIR]); comp.to_pickle(f'{RES}/se_completeness.pkl')
    summ['chybejici_okrsky'] = comp.groupby('rok').size().to_dict() if len(comp) else {}
    sk = {y: se_vs_kv(y) for y in KV_PAIR}
    for y, x in sk.items():
        x.to_pickle(f'{RES}/se_kv_{y}.pkl')
    swaps_rec = pd.concat([find_record_swaps(sk[y]).assign(rok=y) for y in KV_PAIR]); swaps_rec.to_pickle(f'{RES}/se_record_swaps.pkl')
    cand, zeros, swaps, invs = {}, [], [], []
    for y in YEARS:
        t5, df = candidate_model(y)
        df['rok'] = y; df.to_pickle(f'{RES}/se_cand_{y}.pkl')
        zeros.append(zero_test(df).assign(rok=y))
        sw = swap_test(t5, df)
        if len(sw):
            swaps.append(sw.assign(rok=y))
        invs.append(invalid_test(t5).assign(rok=y))
        cand[y] = dict(z5=int((df.z.abs() >= 5).sum()), z5_neg=int((df.z <= -5).sum()), z5_pos_domov=int(((df.z >= 5) & df.domov).sum()),
                       bunek=int(len(df)))
    pd.concat(zeros).to_pickle(f'{RES}/se_zeros.pkl')
    (pd.concat(swaps) if swaps else pd.DataFrame()).to_pickle(f'{RES}/se_swaps.pkl')
    pd.concat(invs).to_pickle(f'{RES}/se_invalid.pkl')
    summ['kandidati'] = cand
    fp = [fingerprints(y) for y in YEARS]
    json.dump(fp, open(f'{RES}/se_fingerprints.json', 'w', encoding='utf8'))
    b = batches(); b.to_pickle(f'{RES}/se_batches.pkl')
    t5, rk, obv = load(2026)
    bc, bs = batch_changes(b, t5); bc.to_pickle(f'{RES}/se_batch_changes.pkl'); summ['davky'] = bs
    mg = margins(t5, rk); mg.to_pickle(f'{RES}/se_margins.pkl')
    json.dump(summ, open(f'{RES}/se_summary.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(summ, ensure_ascii=False, indent=1, default=str)[:4000])
    print('record swaps\n', swaps_rec.to_string())
    print('cand swaps\n', (pd.concat(swaps) if swaps else pd.DataFrame()).head(30).to_string())
    print('zeros\n', pd.concat(zeros)[['rok', 'OID', 'obec', 'kandidat', 'ocek', 'n', 'p0']].head(30).to_string())
    print('batch changes\n', bc.to_string()[:3000])
    print(mg.to_string())
