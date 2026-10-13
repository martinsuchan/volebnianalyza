"""Statistical anomaly detection at precinct level (2026, calibrated against 2022)."""
import sys, os, json, math
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(__file__))
from common import load, HCOLS, RES, MAGISTRAT
from geo import neighbours

MAD = 1.4826
_CACHE = {}


def rz(x):
    """Robust z-score (median / MAD)."""
    x = np.asarray(x, float); m = np.nanmedian(x); s = MAD * np.nanmedian(np.abs(x - m))
    return (x - m) / s if s > 0 else np.zeros_like(x)


def prep(year):
    if year in _CACHE:
        return _CACHE[year]
    d = load(year)
    t3, hl, ros = d['t3'], d['hl'], d['ros']
    if t3.PLAT_LISTKY.isna().all():  # 2018/2022 lack PLAT_LISTKY -> approximate by ODEVZ_OBAL
        t3['PLAT_LISTKY'] = t3.ODEVZ_OBAL
    oids = t3.OID.unique().tolist()
    nb, _ = neighbours(oids, k=8)
    _CACHE[year] = (d, t3, hl, ros, nb)
    return _CACHE[year]


def precinct_metrics(year):
    d, t3, hl, ros, nb = prep(year)
    m = t3[t3.TYPZASTUP == 1].set_index('OID')[['MC', 'OBEC', 'OKRSEK', 'VOL_SEZNAM', 'VYD_OBALKY', 'ODEVZ_OBAL',
                                                 'PLAT_LISTKY', 'PL_HL_CELK']].copy()
    m2 = t3[t3.TYPZASTUP == 2].set_index('OID')
    m['PLAT_MC'] = m2.PLAT_LISTKY; m['PLHL_MC'] = m2.PL_HL_CELK; m['M_MC'] = m2.MANDATY
    m['turnout'] = m.VYD_OBALKY / m.VOL_SEZNAM
    m['gap'] = m.VYD_OBALKY - m.ODEVZ_OBAL
    m['inv_mag'] = 1 - m.PLAT_LISTKY / m.ODEVZ_OBAL
    m['inv_mc'] = 1 - m.PLAT_MC / m.ODEVZ_OBAL
    mand = t3[t3.TYPZASTUP == 1].MANDATY  # mandáty zastupitelstva města (Praha 65); prázdné, pokud se v daném roce v obci nevolilo
    m['vpb_mag'] = m.PL_HL_CELK / m.PLAT_LISTKY / (int(mand.iloc[0]) if len(mand) else np.nan)
    m['vpb_mc'] = m.PLHL_MC / m.PLAT_MC / m.M_MC
    m['d_valid'] = m.PLAT_LISTKY - m.PLAT_MC
    for col in ('turnout', 'inv_mag', 'inv_mc'):
        exp = []
        for o in m.index:
            nn = [x for x in nb.get(o, []) if x in m.index]
            exp.append(np.median(m.loc[nn, col]) if nn else np.nan)
        m[col + '_nb'] = exp
    for col in ('inv_mag', 'inv_mc'):
        p = m[col + '_nb'].clip(0.002, 0.5); n = m.ODEVZ_OBAL
        zr = (m[col] - p) / np.sqrt(p * (1 - p) / n)
        m['z_' + col] = zr / (MAD * np.median(np.abs(zr - np.median(zr))))
    p = m.turnout_nb; zr = (m.turnout - p) / np.sqrt(p * (1 - p) / m.VOL_SEZNAM)
    m['z_turnout'] = zr / (MAD * np.median(np.abs(zr - np.median(zr))))
    m['z_vpb_mag'] = rz(m.vpb_mag); m['z_vpb_mc'] = m.groupby('MC').vpb_mc.transform(rz)
    m['ddiff'] = (m.inv_mc - m.inv_mag)
    m['z_ddiff'] = rz(m.ddiff * np.sqrt(m.ODEVZ_OBAL))
    lam = m.gap.clip(lower=0).sum() / m.VYD_OBALKY.sum() * m.VYD_OBALKY
    m['p_gap'] = stats.poisson.sf(m.gap - 1, lam)
    m['rok'] = year
    return m


def share_residuals(year):
    """Overdispersed residual of each party's share in each precinct vs spatial neighbours."""
    d, t3, hl, ros, nb = prep(year)
    names = ros.set_index(['ZK', 'POR_STR_HL']).ZKRATKAO30
    out = []
    for zk, g in hl.groupby('ZK'):
        V = g.pivot_table(index='OID', columns='POR_STR_HL', values='POC_HLASU', aggfunc='sum').fillna(0)
        tt = t3[t3.ZK == zk].set_index('OID')
        T = V.sum(axis=1); n = tt.PLAT_LISTKY.reindex(V.index).astype(float); M = int(tt.MANDATY.iloc[0])
        idx = {o: i for i, o in enumerate(V.index)}
        Vv = V.values
        E = np.full(Vv.shape, np.nan)
        for o, i in idx.items():
            nn = [idx[x] for x in nb.get(o, []) if x in idx]
            if len(nn) < 2:  # tiny councils: council total minus self
                nn = [j for j in range(len(Vv)) if j != i]
            if nn:
                s = Vv[nn].sum(axis=0); E[i] = s / s.sum() if s.sum() > 0 else np.nan
        S = Vv / np.maximum(T.values[:, None], 1)
        var = E * (1 - E) / np.maximum(n.values[:, None], 1)
        Z = (S - E) / np.sqrt(np.clip(var, 1e-9, None))
        for j, p in enumerate(V.columns):
            zc = Z[:, j]; ok = (E[:, j] * T.values / M >= 1) & np.isfinite(zc)
            sc = MAD * np.nanmedian(np.abs(zc[ok] - np.nanmedian(zc[ok]))) if ok.sum() >= 8 else np.nan
            sc = max(sc, 1.0) if not np.isnan(sc) else 1.5
            for o, i in idx.items():
                out.append((year, zk, o, p, names.get((zk, p), ''), Vv[i, j], T.iloc[i], n.iloc[i], M, E[i, j], S[i, j],
                            zc[i], sc, zc[i] / sc, E[i, j] * T.iloc[i] / M))
    R = pd.DataFrame(out, columns=['rok', 'ZK', 'OID', 'strana', 'nazev', 'hlasy', 'T', 'n', 'M', 'e', 's', 'zraw',
                                   'scale', 'z', 'exp_ballots'])
    R['MC'] = R.OID.map(t3.drop_duplicates('OID').set_index('OID').MC)
    return R


def zero_votes(R):
    """Blansko pattern: a party recorded with 0 votes although many ballots expected."""
    z = R[(R.hlasy == 0) & (R.exp_ballots >= 3)].copy()
    z['lam_eff'] = z.exp_ballots / z.scale ** 2
    z['p_nominal'] = np.exp(-z.exp_ballots); z['p_conservative'] = np.exp(-z.lam_eff)
    return z.sort_values('p_conservative')


def swaps(R, zmin=3.0):
    """Detect pairs of parties in one precinct whose numbers look exchanged."""
    out = []
    cand = R[(R.z.abs() >= zmin) & (R.exp_ballots >= 2)]
    for (zk, o), big in cand.groupby(['ZK', 'OID']):
        if len(big) < 2:
            continue
        rows = list(big.itertuples())
        for a in rows:
            for b in rows:
                if a.strana >= b.strana or np.sign(a.z) == np.sign(b.z):
                    continue
                def zz(v, r):
                    return ((v / r.T) - r.e) / math.sqrt(max(r.e * (1 - r.e) / r.n, 1e-9)) / r.scale
                za, zb = zz(b.hlasy, a), zz(a.hlasy, b)
                gain = a.z ** 2 + b.z ** 2 - za ** 2 - zb ** 2
                if abs(za) < 2.5 and abs(zb) < 2.5 and gain > 25:
                    out.append(dict(rok=a.rok, ZK=zk, OID=o, MC=a.MC, strana_a=a.strana, nazev_a=a.nazev, hlasy_a=a.hlasy,
                                    ocek_a=round(a.e * a.T), strana_b=b.strana, nazev_b=b.nazev, hlasy_b=b.hlasy,
                                    ocek_b=round(b.e * b.T), z_a=a.z, z_b=b.z, z_a_po=za, z_b_po=zb, zisk_chi2=gain,
                                    sousedni=abs(a.strana - b.strana) == 1))
    return pd.DataFrame(out)


CROSS_COLS = ['rok', 'ZK', 'MC', 'OID', 'strana_mc', 'nazev_mc', 'strany_mag', 'strany_mag_cisla', 'hlasy_mc', 'hlasy_mag',
              'podil_mc', 'podil_mag', 'ocek_podil_mag', 'ocek_podil_mc', 'ocek_hlasy_mag', 'ocek_hlasy_mc', 'z_mag', 'z_mc', 'pomer_median']


def cross_ballot(year):
    """Lístek města (magistrát) vs. lístek MČ/MO: podíl téže strany na obou lístcích by měl být místně stabilní."""
    d, t3, hl, ros, nb = prep(year)
    mag = ros[ros.KODZASTUP == MAGISTRAT]
    if not (t3.TYPZASTUP == 2).any():  # město bez MČ/MO: druhý lístek neexistuje
        return pd.DataFrame(columns=CROSS_COLS)
    def code(s):
        return {c.lstrip('0') for c in str(s).replace(' ', '').split(',') if c and c.lstrip('0') not in ('80', '999', 'nan', '')}
    magc = {r.POR_STR_HL: code(r.SLOZENI) | {str(r.VSTRANA)} for _, r in mag.iterrows()}
    magn = dict(zip(mag.POR_STR_HL, mag.ZKRATKAO30))
    hv = hl.pivot_table(index=['OID', 'ZK'], columns='POR_STR_HL', values='POC_HLASU', aggfunc='sum').fillna(0)
    mz = hv.xs(MAGISTRAT * 100 + 1, level='ZK')
    tm = t3[t3.TYPZASTUP == 1].set_index('OID')
    zks = set(hv.index.get_level_values('ZK'))
    out = []
    for zk, g in ros[ros.KODZASTUP != MAGISTRAT].groupby('ZK'):
        if zk not in zks:
            continue
        mc = hv.xs(zk, level='ZK')
        tc = t3[t3.ZK == zk].set_index('OID'); M = int(tc.MANDATY.iloc[0])
        for _, r in g.iterrows():
            cc = code(r.SLOZENI) | {str(r.VSTRANA)}
            S = [p for p, c in magc.items() if c & cc]
            if not S or r.POR_STR_HL not in mc.columns:
                continue
            oids = mc.index.intersection(mz.index)
            vL = mc.loc[oids, r.POR_STR_HL]; vS = mz.loc[oids, S].sum(axis=1)
            if len(oids) < 4 or vL.sum() / M < 30:
                continue
            TL = tc.loc[oids, 'PL_HL_CELK'].astype(float); TS = tm.loc[oids, 'PL_HL_CELK'].astype(float)
            nS = tm.loc[oids, 'PLAT_LISTKY'].astype(float); nL = tc.loc[oids, 'PLAT_LISTKY'].astype(float)
            sL = vL / TL; sS = vS / TS
            ok = (sL > 0) & (sS > 0)
            if ok.sum() < 4:
                continue
            med = np.median(np.log(sS[ok] / sL[ok]))  # typical magistrát/MČ share ratio in this MČ
            # expected magistrát share from MČ share (and vice versa), test in count space using expected values
            eS = (sL * np.exp(med)).clip(1e-4, 0.95); eL = (sS * np.exp(-med)).clip(1e-4, 0.95)
            zS = (sS - eS) / np.sqrt(eS * (1 - eS) / nS); zL = (sL - eL) / np.sqrt(eL * (1 - eL) / nL)
            okz = ok & (eS * nS >= 3)
            scS = max(MAD * np.median(np.abs(zS[okz] - np.median(zS[okz]))), 1.0) if okz.sum() >= 4 else 2.0
            scL = max(MAD * np.median(np.abs(zL[okz] - np.median(zL[okz]))), 1.0) if okz.sum() >= 4 else 2.0
            for o in oids:
                out.append(dict(rok=year, ZK=zk, MC=tc.MC.iloc[0], OID=o, strana_mc=r.POR_STR_HL, nazev_mc=r.ZKRATKAO30,
                                strany_mag='+'.join(magn[p] for p in S), strany_mag_cisla=S, hlasy_mc=vL[o], hlasy_mag=vS[o],
                                podil_mc=sL[o], podil_mag=sS[o], ocek_podil_mag=eS[o], ocek_podil_mc=eL[o],
                                ocek_hlasy_mag=eS[o] * TS[o], ocek_hlasy_mc=eL[o] * TL[o],
                                z_mag=zS[o] / scS, z_mc=zL[o] / scL, pomer_median=float(np.exp(med))))
    return pd.DataFrame(out, columns=CROSS_COLS)


def candidate_anomalies(year):
    """(a) preferential-vote spikes, (b) column shift / dropped entries in candidate vectors."""
    d, t3, hl, ros, nb = prep(year)
    rk = d['rk']; valid = rk[rk.PLATNOST == 'A']
    npos = rk.groupby(['ZK', 'POR_STR_HL']).PORCISLO.max()
    names = rk.set_index(['ZK', 'POR_STR_HL', 'PORCISLO'])
    spikes, shifts = [], []
    for (zk, p), g in hl.groupby(['ZK', 'POR_STR_HL']):
        N = int(npos.get((zk, p), 0))
        if N < 2:
            continue
        val_pos = sorted(valid[(valid.ZK == zk) & (valid.POR_STR_HL == p)].PORCISLO)
        cols = [HCOLS[i - 1] for i in val_pos]
        X = g.set_index('OID')[cols].astype(float); X.columns = val_pos
        P = X.sum(axis=1); X = X[P > 0]
        if len(X) < 3:
            continue
        base = X.median(axis=1)
        prof = X.sum() / X.values.sum()
        exc = X.sub(base, axis=0)
        rate = exc.div(base.clip(lower=1), axis=0)
        for c in X.columns:
            r = rate[c]; e = exc[c]
            med = r.median(); s = max(MAD * np.median(np.abs(r - med)), 0.05)
            zc = (r - med) / s
            expect = (med * base.clip(lower=1)).clip(lower=0)
            pv = pd.Series(stats.poisson.sf(e.round() - 1, expect + 1), index=e.index)
            for o in X.index[(zc > 6) & (e >= 15)]:
                nm = names.loc[(zk, p, c)]
                spikes.append(dict(rok=year, ZK=zk, strana=p, porcislo=c, jmeno=f'{nm.JMENO} {nm.PRIJMENI}', OID=o,
                                   hlasy=X.loc[o, c], zaklad=base[o], nadbytek=e[o], typicky_nadbytek=round(med * base[o], 1),
                                   z=zc[o], p_poisson=pv[o], celkem_kand=int(nm.POCHLASU), mandat=nm.MANDAT))
        if len(val_pos) >= 6:
            for o in X.index:
                v = X.loc[o].values; tot = v.sum()
                if tot < 30:
                    continue
                ex = prof.values * tot
                sse0 = ((v - ex) ** 2 / (ex + 1)).sum()
                best = None
                for sh in (-1, 1):
                    vs = np.roll(v, sh)
                    if sh == 1: vs[0] = v[0]
                    else: vs[-1] = v[-1]
                    sse = ((vs - ex) ** 2 / (ex + 1)).sum()
                    if best is None or sse < best[1]:
                        best = (sh, sse)
                dips = [val_pos[i] for i in range(1, len(v) - 1)
                        if min(v[i - 1], v[i + 1]) >= 20 and v[i] < 0.4 * min(v[i - 1], v[i + 1])]
                if (best[1] < 0.5 * sse0 and sse0 > 60) or dips:
                    shifts.append(dict(rok=year, ZK=zk, strana=p, OID=o, hlasy_strany=tot, chi2_0=sse0, chi2_posun=best[1],
                                       posun=best[0], propady=dips, vektor=list(map(int, v))))
    S = pd.DataFrame(spikes); H = pd.DataFrame(shifts)
    mcmap = t3.drop_duplicates('OID').set_index('OID').MC
    for D in (S, H):
        if len(D):
            D['MC'] = D.OID.map(mcmap)
    return S, H


def duplicates(year):
    d, t3, hl, ros, nb = prep(year)
    out = []
    v = hl.sort_values('POR_STR_HL').groupby(['ZK', 'OID']).POC_HLASU.apply(tuple)
    for zk in v.index.get_level_values(0).unique():
        s = v.xs(zk); dup = s[s.duplicated(keep=False) & s.apply(lambda t: sum(t) >= 50)]
        for key, gg in dup.groupby(dup):
            out.append(dict(rok=year, ZK=zk, okrsky=list(gg.index), vektor=key))
    # candidate vectors duplicated between precincts (copy/paste)
    hc = hl[hl.POC_HLASU >= 100].copy()
    hc['vec'] = hc[HCOLS].astype(int).apply(tuple, axis=1)
    for (zk, p), g in hc.groupby(['ZK', 'POR_STR_HL']):
        dd = g[g.vec.duplicated(keep=False)]
        for key, gg in dd.groupby('vec'):
            if len(set(key)) > 2:  # ignore pure party-box vectors (all equal)
                out.append(dict(rok=year, ZK=zk, strana=p, okrsky=list(gg.OID), vektor=key[:10]))
    return pd.DataFrame(out)


if __name__ == '__main__':
    for y in (2022, 2026):
        print('== year', y, flush=True)
        m = precinct_metrics(y); m.to_pickle(f'{RES}/precinct_{y}.pkl')
        R = share_residuals(y); R.to_pickle(f'{RES}/shares_{y}.pkl')
        print('share tests', len(R), '|z|>5:', (R.z.abs() > 5).sum(), '|z|>7:', (R.z.abs() > 7).sum(), flush=True)
        Z = zero_votes(R); Z.to_pickle(f'{RES}/zeros_{y}.pkl'); print('zeros', len(Z), (Z.p_conservative < 1e-3).sum())
        W = swaps(R); W.to_pickle(f'{RES}/swaps_{y}.pkl'); print('swaps', len(W))
        X = cross_ballot(y); X.to_pickle(f'{RES}/cross_{y}.pkl'); print('cross', len(X), '|z_mag|>5', (X.z_mag.abs() > 5).sum(), '|z_mc|>5', (X.z_mc.abs() > 5).sum())
        S, H = candidate_anomalies(y); S.to_pickle(f'{RES}/spikes_{y}.pkl'); H.to_pickle(f'{RES}/shifts_{y}.pkl')
        print('spikes', len(S), 'shift/dips', len(H))
        D = duplicates(y); D.to_pickle(f'{RES}/dups_{y}.pkl'); print('dups', len(D))
