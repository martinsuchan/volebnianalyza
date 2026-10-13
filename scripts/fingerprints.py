"""Population-level election-forensics tests (2018 / 2022 / 2026).

* Last-digit test (Beber & Scacco 2012) on precinct party vote counts (>= 10 votes) – χ² vs uniform
* Second-digit Benford test (2BL, Mebane 2006) – mean of 2nd digit vs 4.187, χ²
* Integer-percentage test (Kobak, Shpilkin & Pshenichnikov 2016) – turnout exactly at integer %
  vs Monte-Carlo expectation; leader share near-integer frequency
* Turnout–vote-share fingerprint (Klimek et al. 2012) – correlations of turnout with party shares,
  2-D histogram data for plotting, skewness/kurtosis of turnout
* Turnout change 2022→2026 per precinct (matched precinct IDs)
"""
import sys, os, json
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(__file__))
from common import RES, MAGISTRAT
from anomalies import prep

BENF2 = np.array([sum(np.log10(1 + 1 / (10 * k + d)) for k in range(1, 10)) for d in range(10)])
rng = np.random.default_rng(2026)


def digit_tests(year):
    d, t3, hl, ros, nb = prep(year)
    out = {}
    for lab, sel in (('magistrat', hl.TYPZASTUP == 1), ('mc', hl.TYPZASTUP == 2)):
        v = hl[sel & (hl.POC_HLASU >= 10)].POC_HLASU.astype(int).values
        if len(v) < 50:  # město bez MČ/MO (nebo příliš málo dat)
            out[lab] = None
            continue
        ld = np.bincount(v % 10, minlength=10)
        chi_ld = stats.chisquare(ld)
        s = np.array([int(str(x)[1]) for x in v])
        sd = np.bincount(s, minlength=10)
        chi_2bl = stats.chisquare(sd, BENF2 * len(s))
        out[lab] = dict(n=int(len(v)), last_digit=ld.tolist(), ld_chi2=float(chi_ld.statistic), ld_p=float(chi_ld.pvalue),
                        second_digit=sd.tolist(), bl2_mean=float(s.mean()), bl2_chi2=float(chi_2bl.statistic), bl2_p=float(chi_2bl.pvalue))
    # per-MČ last digit (MČ ballots + magistrát ballots within MČ territory)
    per = []
    for mc, g in hl[hl.POC_HLASU >= 10].merge(t3[['OID', 'MC']].drop_duplicates(), on='OID').groupby('MC'):
        v = g.POC_HLASU.astype(int).values
        if len(v) < 100:
            continue
        c = np.bincount(v % 10, minlength=10); r = stats.chisquare(c)
        per.append(dict(MC=mc, n=int(len(v)), chi2=float(r.statistic), p=float(r.pvalue)))
    per = pd.DataFrame(per, columns=['MC', 'n', 'chi2', 'p']); per['p_bonf'] = (per.p * len(per)).clip(upper=1)
    out['per_mc'] = per.sort_values('p').to_dict('records')
    # T3 counts last digit
    t = t3[t3.TYPZASTUP == 1]
    cols = [c for c in ('VOL_SEZNAM', 'VYD_OBALKY', 'PL_HL_CELK') if c in t]
    v = np.concatenate([t[c].astype(int).values for c in cols]); v = v[v >= 10]
    c = np.bincount(v % 10, minlength=10); r = stats.chisquare(c)
    out['t3'] = dict(n=int(len(v)), last_digit=c.tolist(), chi2=float(r.statistic), p=float(r.pvalue))
    return out


def integer_pct(year, nsim=2000):
    d, t3, hl, ros, nb = prep(year)
    t = t3[t3.TYPZASTUP == 1]
    n = t.VOL_SEZNAM.values.astype(int); k = t.VYD_OBALKY.values.astype(int)
    obs = int(((100 * k) % n == 0).sum())
    p = k / n
    sims = np.array([((100 * rng.binomial(n, p)) % n == 0).sum() for _ in range(nsim)])
    # leader share near integer (magistrát leader of the year)
    mag = ros[ros.KODZASTUP == MAGISTRAT].sort_values('HLASY_STR', ascending=False)
    if not len(mag):  # řádné volby zrušené a opakované (např. 2018 → 26. 1. 2019): bez výsledků stran
        return dict(turnout_integer_obs=obs, turnout_integer_exp=float(sims.mean()), turnout_integer_sd=float(sims.std()),
                    turnout_integer_p=float((sims >= obs).mean()), leader='–', leader_near_integer=0, leader_near_integer_exp=0.0, leader_n=0,
                    leader_binom_p=float('nan'))
    leader = int(mag.POR_STR_HL.iloc[0]); lname = mag.ZKRATKAO30.iloc[0]
    h = hl[(hl.TYPZASTUP == 1) & (hl.POR_STR_HL == leader)].set_index('OID').POC_HLASU
    T = t.set_index('OID').PL_HL_CELK
    sh = 100 * h / T.reindex(h.index)
    frac = np.abs(sh - np.round(sh))
    near = int((frac <= 0.05).sum())
    return dict(turnout_integer_obs=obs, turnout_integer_exp=float(sims.mean()), turnout_integer_sd=float(sims.std()),
                turnout_integer_p=float((sims >= obs).mean()), leader=lname, leader_near_integer=near,
                leader_near_integer_exp=0.1 * len(sh), leader_n=int(len(sh)),
                leader_binom_p=float(stats.binomtest(near, len(sh), 0.1, alternative='greater').pvalue))


def klimek(year):
    d, t3, hl, ros, nb = prep(year)
    t = t3[t3.TYPZASTUP == 1].set_index('OID')
    turn = t.VYD_OBALKY / t.VOL_SEZNAM
    mag = ros[ros.KODZASTUP == MAGISTRAT].sort_values('HLASY_STR', ascending=False).head(6)
    res = []
    hist = {}
    for p, name in zip(mag.POR_STR_HL, mag.ZKRATKAO30):
        h = hl[(hl.TYPZASTUP == 1) & (hl.POR_STR_HL == p)].set_index('OID').POC_HLASU
        sh = (h / t.PL_HL_CELK.reindex(h.index)).reindex(turn.index)
        ok = (t.VOL_SEZNAM >= 100) & sh.notna()
        r = stats.spearmanr(turn[ok], sh[ok])
        res.append(dict(strana=name, spearman=float(r.statistic), p=float(r.pvalue)))
        H, xe, ye = np.histogram2d(turn[ok], sh[ok], bins=[40, 40], range=[[0, 1], [0, 0.6]])
        hist[name] = dict(H=H.astype(int).tolist(), x=xe.tolist(), y=ye.tolist(),
                          pts=[[round(a, 4), round(b, 4), int(c)] for a, b, c in zip(turn[ok], sh[ok], t.VOL_SEZNAM[ok])])
    tv = turn[t.VOL_SEZNAM >= 100]
    return dict(korelace=res, turnout_mean=float(tv.mean()), turnout_sd=float(tv.std()), turnout_skew=float(stats.skew(tv)),
                turnout_kurt=float(stats.kurtosis(tv))), hist


def digits_corrected(year):
    """Test poslední číslice očištěný o strukturální artefakt: hlasy strany = součet hlasů kandidátů a každý křížek u strany
    dává hlas všem kandidátům do počtu mandátů (magistrát 65), takže hlasy stran nejsou vhodné. Testuje se proto
    (a) hlas lídra kandidátky (≥ 10, resp. ≥ 100 hlasů) a (b) hlasy stran v MČ, kde počet mandátů není dělitelný 5 (≥ 100 hlasů)."""
    d, t3, hl, ros, nb = prep(year)
    out = {}
    for lab, tz in (('magistrat', 1), ('mc', 2)):
        h = hl[hl.TYPZASTUP == tz]
        if (h.HLASY_01 >= 10).sum() < 50:
            out[lab] = None
            continue
        c1 = h.HLASY_01.astype(int).values
        v = c1[c1 >= 10]; ld = np.bincount(v % 10, minlength=10); r = stats.chisquare(ld)
        s = np.array([int(str(x)[1]) for x in v]); sd = np.bincount(s, minlength=10); r2 = stats.chisquare(sd, BENF2 * len(s))
        v100 = c1[c1 >= 100]; ld100 = np.bincount(v100 % 10, minlength=10); r100 = stats.chisquare(ld100)
        hm = h.merge(t3[['OID', 'TYPZASTUP', 'MANDATY']].drop_duplicates(['OID', 'TYPZASTUP']), on=['OID', 'TYPZASTUP'], how='left')
        vp = hm[(hm.MANDATY % 5 != 0) & (hm.POC_HLASU >= 100)].POC_HLASU.astype(int).values
        rp = stats.chisquare(np.bincount(vp % 10, minlength=10)) if len(vp) >= 50 else None
        out[lab] = dict(n_c1=int(len(v)), ld_c1_chi2=float(r.statistic), ld_c1_p=float(r.pvalue), ld_c1_counts=ld.tolist(),
                        bl2_c1_mean=float(s.mean()), bl2_c1_chi2=float(r2.statistic), bl2_c1_p=float(r2.pvalue),
                        n_c1_100=int(len(v100)), ld_c1_100_chi2=float(r100.statistic), ld_c1_100_p=float(r100.pvalue), ld_c1_100=ld100.tolist(),
                        n_party_M_not5=int(len(vp)), ld_party_M_not5_chi2=float(rp.statistic) if rp else None,
                        ld_party_M_not5_p=float(rp.pvalue) if rp else None)
    return out


def turnout_change():
    _, a, _, _, _ = prep(2022); _, b, _, _, _ = prep(2026)
    a = a[a.TYPZASTUP == 1].set_index('OID'); b = b[b.TYPZASTUP == 1].set_index('OID')
    j = b[['MC', 'VOL_SEZNAM', 'VYD_OBALKY']].join(a[['VOL_SEZNAM', 'VYD_OBALKY']], rsuffix='_22', how='inner')
    j['t26'] = j.VYD_OBALKY / j.VOL_SEZNAM; j['t22'] = j.VYD_OBALKY_22 / j.VOL_SEZNAM_22
    j['stabilni'] = (j.VOL_SEZNAM / j.VOL_SEZNAM_22 - 1).abs() < 0.25
    j['dt'] = j.t26 - j.t22
    s = j[j.stabilni]
    med = s.groupby('MC').dt.transform('median')
    sd = 1.4826 * np.median(np.abs(s.dt - med))
    j.loc[s.index, 'z'] = (s.dt - med) / sd
    return j


if __name__ == '__main__':
    out = {}
    for y in (2018, 2022, 2026):
        dt = digit_tests(y); ip = integer_pct(y); kl, hist = klimek(y)
        out[y] = dict(digits=dt, integer=ip, klimek=kl)
        json.dump(hist, open(f'{RES}/klimek_hist_{y}.json', 'w'), ensure_ascii=False)
        print('=====', y)
        for lab in ('magistrat', 'mc'):
            x = dt[lab]
            if x is None:
                continue
            print(f" {lab}: n={x['n']} lastdigit chi2={x['ld_chi2']:.1f} p={x['ld_p']:.3g} | 2BL mean={x['bl2_mean']:.3f} chi2={x['bl2_chi2']:.1f} p={x['bl2_p']:.3g}")
        print(' T3 last digit', dt['t3']['chi2'], dt['t3']['p'], ' worst MČ', dt['per_mc'][:3])
        print(' integer %', ip)
        print(' klimek', kl)
    j = turnout_change(); j.to_pickle(f'{RES}/turnout_change.pkl')
    print('turnout change matched', len(j), 'stable', j.stabilni.sum(), '|z|>5', (j.z.abs() > 5).sum())
    print(j.sort_values('z', key=abs, ascending=False).head(10).round(3).to_string())
    json.dump(out, open(f'{RES}/fingerprints.json', 'w'), ensure_ascii=False, indent=1, default=float)
    dc = {str(y): digits_corrected(y) for y in (2018, 2022, 2026)}
    json.dump(dc, open(f'{RES}/digits_corrected.json', 'w'), ensure_ascii=False, indent=1)
