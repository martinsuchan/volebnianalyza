"""Doplňková pravidla kontroly okrskových výsledků (listopad 2026) – poučení ze soudních podání a srovnání s jinými analýzami.

Vycházejí z logiky hlasovacího lístku: křížek u strany dává hlas prvním K = min(počet kandidátů, počet mandátů) kandidátům.
Každý z nich má proto v okrsku aspoň tolik hlasů, kolik je lístků s křížkem u strany (základ B); osobní křížky jen přidávají.

  P1  kandidát (i první nebo poslední) hluboko pod základem kandidátky – i když nemá nulu
  P2  úsek kandidátky (začátek, střed, konec; i „křížek jen prvnímu“) posunutý dolů proti profilu sousedních okrsků
  P3  rozptýlené nuly uvnitř kandidátky, ostatní kandidáti mají podobné nenulové hodnoty
  P4  chybějící / přebývající balík: celá kandidátka posunutá proti okolí a stejně velký schodek / přebytek hlasů okrsku
  P5  okrsek s nedostatkem hlasů bez určené strany (využití hlasů proti okolí)
  P6  neobvykle mnoho neplatných lístků proti okolí
  P7  citlivost těsných výsledků: hodnoty, jejichž věrohodný překlep (záměna dvou číslic, jedna číslice) by změnil výsledek

Funkce vrací kandidáty na nález (DataFrame) s klíčem `klic`; texty a číslování řeší volající (findings.py, findings_auto.py).
"""
import numpy as np, pandas as pd

HC = [f'HLASY_{i:02d}' for i in range(1, 71)]


def _mad(x):
    x = np.asarray(x, float)
    return 1.4826 * np.median(np.abs(x - np.median(x))) if len(x) else 0.0


def vektory(d, nb):
    """Pro každé zastupitelstvo a stranu: matice hlasů kandidátů v okrscích (jen prvních K pozic) a profil okolí
    (medián 8 nejbližších okrsků téhož zastupitelstva přepočtený na platné lístky okrsku)."""
    t3, hl, ros, cm = d['t3'], d['hl'], d['ros'], d['councils']
    T = t3.drop_duplicates(['OID', 'ZK']).set_index(['OID', 'ZK']).PLAT_LISTKY
    out = []
    for (zk, p), g in hl[hl.ZK.notna()].groupby(['ZK', 'POR_STR_HL']):
        zk, p = int(zk), int(p)
        r = ros[(ros.ZK == zk) & (ros.POR_STR_HL == p)]
        if not len(r) or not (r.NCAND.fillna(0).iloc[0] > 0):
            continue
        nc, M = int(r.NCAND.iloc[0]), int(cm.MANDATY[zk])
        K = min(nc, M)
        g = g.drop_duplicates('OID').set_index('OID')
        V = g[HC[:K]].astype(float).values
        lis = np.array([T.get((o, zk), np.nan) for o in g.index], float)
        pos = {o: i for i, o in enumerate(g.index)}
        P = np.full_like(V, np.nan)
        for i, o in enumerate(g.index):
            j = [pos[x] for x in nb.get(o, []) if x in pos][:8]
            if len(j) >= 3 and lis[i] > 0:
                P[i] = np.median(V[j] / np.maximum(lis[j], 1)[:, None], axis=0) * lis[i]
        out.append(dict(ZK=zk, strana=p, nazev=str(r.ZKRATKAO30.iloc[0]), NC=nc, M=M, K=K, OID=list(g.index), V=V, P=P, listky=lis))
    return out


def odstoupivsi(d):
    """Kandidáti, kteří nejsou platní (PLATNOST ≠ A) nebo mají nulu v naprosté většině okrsků (vzdali se, zemřeli)."""
    rk = d['rk']
    return {(int(r.ZK), int(r.POR_STR_HL), int(r.PORCISLO)) for r in rk.itertuples() if r.PLATNOST != 'A'}


def p1_p2_p3(vecs, vyrazeni):
    """P1 propady pod základ, P2 posunuté úseky, P3 rozptýlené nuly."""
    rows = []
    for g in vecs:
        V, P, K = g['V'], g['P'], g['K']
        if K < 5:
            continue
        # kandidát slabý ve většině okrsků (odstoupil, zemřel) – v P1 se nehlásí
        lvl = np.median(V, axis=1, keepdims=True)
        slaby = (V < 0.3 * np.maximum(lvl, 1)).mean(axis=0) > 0.5
        for i, oid in enumerate(g['OID']):
            v = V[i]; p = P[i]
            q = np.percentile(v, 25); med = np.median(v)
            # --- P3: rozptýlené nuly
            nz = v[v > 0]
            last = int(np.nonzero(v)[0].max()) if len(nz) else -1
            zeros_in = int((v[:last] == 0).sum()) if last > 0 else 0
            if len(nz) >= 3 and zeros_in >= max(5, 0.3 * K) and np.median(nz) >= 5 and nz.std() / nz.mean() <= 0.35 and g['NC'] <= g['M']:
                rows.append(dict(pravidlo='P3', ZK=g['ZK'], strana=g['strana'], nazev=g['nazev'], OID=oid, K=K, M=g['M'],
                                 pozice=[int(k) + 1 for k in np.where(v[:last] == 0)[0]], hodnoty=v.astype(int).tolist(),
                                 zaklad=float(np.median(nz)), chybi=float(np.median(nz) * zeros_in),
                                 sila=float(zeros_in * np.median(nz) / max(np.sqrt(np.median(nz)), 1))))
                continue
            # --- P2: posunutý úsek (proti profilu okolí), nejvýraznější úsek s deficitem
            seg = None
            if not np.isnan(p).any():
                r = v - p
                s = _mad(np.diff(r)) / np.sqrt(2)
                s = max(s, np.sqrt(max(med, 1)) * 0.5, 1.0)
                cs = np.concatenate([[0], np.cumsum(r)]); tot = cs[-1]
                A, B = np.meshgrid(np.arange(K + 1), np.arange(K + 1), indexing='ij')  # úsek [a, b)
                L = (B - A).astype(float); Lo = K - L
                ok = (L >= 2) & ((Lo >= 2) | ((Lo == 1) & (A == 1)))  # doplněk aspoň 2 pozice; výjimka „křížek jen prvnímu“ (úsek 2..K)
                with np.errstate(divide='ignore', invalid='ignore'):
                    S = cs[B] - cs[A]
                    din = S / L; dout = (tot - S) / Lo
                    tt = np.where(ok, (din - dout) / (s * np.sqrt(1 / L + 1 / Lo)), np.inf)
                ia, ib = np.unravel_index(np.argmin(tt), tt.shape)
                best = (float(tt[ia, ib]), int(ia), int(ib), float(din[ia, ib] - dout[ia, ib])) if np.isfinite(tt[ia, ib]) else None
                ok_seg = False
                if best and best[0] <= -10 and -best[3] >= max(5, 0.25 * med):
                    t, a, b, dd = best
                    rin = r[a:b].mean(); rout = np.delete(r, np.arange(a, b)).mean()
                    # úsek musí být pod okolím a zbytek kandidátky s okolím souhlasit (jinak jde o osobní hlasy lídrů)
                    ok_seg = rin <= -max(5, 0.25 * np.median(p[a:b])) and abs(rout) <= 0.5 * abs(rin)
                    # propad musí být vidět i uvnitř kandidátky v okrsku (jinak jde jen o jiný vzor osobních hlasů v okolí)
                    vin, vout = v[a:b].mean(), np.delete(v, np.arange(a, b)).mean()
                    ok_seg = ok_seg and vin <= vout - max(5, 0.25 * vout)
                if ok_seg:
                    seg = (a, b)
                    rows.append(dict(pravidlo='P2', ZK=g['ZK'], strana=g['strana'], nazev=g['nazev'], OID=oid, K=K, M=g['M'], od=a + 1, do=b,
                                     posun=float(dd), t=float(t), hodnoty=v.astype(int).tolist(), okoli=np.round(p).astype(int).tolist(),
                                     chybi=float(-dd * (b - a)), sila=float(-t)))
            # --- P1: kandidát hluboko pod základem (mimo nalezený úsek)
            spread = max(_mad(v), np.sqrt(max(q, 1)), 2.0)
            for k in range(K):
                if seg and seg[0] <= k < seg[1]:
                    continue
                if slaby[k] or (g['ZK'], g['strana'], k + 1) in vyrazeni:
                    continue
                if not np.isnan(p).any() and p[k] < 0.6 * np.median(p):  # kandidát je slabý i v okolí
                    continue
                gap = q - v[k]
                if gap >= max(10, 0.3 * q) and gap / spread >= 6:
                    rows.append(dict(pravidlo='P1', ZK=g['ZK'], strana=g['strana'], nazev=g['nazev'], OID=oid, K=K, M=g['M'], pozice=[k + 1],
                                     hodnota=int(v[k]), zaklad=float(q), hodnoty=v.astype(int).tolist(), chybi=float(gap), sila=float(gap / spread)))
    R = pd.DataFrame(rows)
    if len(R):  # sousední propady v jednom okrsku a straně sloučit (např. č. 19–20)
        p1 = R[R.pravidlo == 'P1'].sort_values('pozice')
        merged = []
        for (zk, s, o), grp in p1.groupby(['ZK', 'strana', 'OID']):
            r0 = grp.iloc[0].to_dict()
            r0['pozice'] = sorted(sum(grp.pozice, []))
            r0['hodnota'] = [int(x) for x in grp.hodnota]
            r0['chybi'] = float(grp.chybi.sum()); r0['sila'] = float(grp.sila.max())
            merged.append(r0)
        R = pd.concat([R[R.pravidlo != 'P1'], pd.DataFrame(merged)], ignore_index=True)
    return R


def p4(vecs, MS):
    """Celá kandidátka posunutá o stejnou hodnotu proti okolí a odpovídající schodek / přebytek využití hlasů okrsku."""
    ms = MS.set_index(['OID', 'ZK'])
    rows = []
    for g in vecs:
        for i, oid in enumerate(g['OID']):
            v, p = g['V'][i], g['P'][i]
            if np.isnan(p).any() or (oid, g['ZK']) not in ms.index:
                continue
            r = v - p; dd = np.median(r); spread = _mad(r - dd)
            if abs(dd) < max(10, 0.25 * np.median(p)) or spread > 0.35 * abs(dd):
                continue
            m = ms.loc[(oid, g['ZK'])]
            okrsek = (m.vpb - m.vpb_ocek) * m.PLAT_LISTKY * m.M  # schodek (−) / přebytek (+) hlasů okrsku
            strana = dd * g['K']
            shoda = strana / okrsek if okrsek else np.nan
            if not (0.4 <= shoda <= 1.6):
                continue
            if dd < 0 and m.z_vpb > -3:
                continue
            if dd > 0 and m.z_vpb < 3:
                continue
            rows.append(dict(pravidlo='P4', ZK=g['ZK'], strana=g['strana'], nazev=g['nazev'], OID=oid, K=g['K'], M=g['M'], posun=float(dd),
                             chybi=float(-strana), okrsek_hlasu=float(okrsek), shoda=float(shoda), z_vpb=float(m.z_vpb), vpb=float(m.vpb), vpb_ocek=float(m.vpb_ocek),
                             hodnoty=v.astype(int).tolist(), okoli=np.round(p).astype(int).tolist(), sila=float(abs(m.z_vpb))))
    return pd.DataFrame(rows)


def p5(MS, zmin=-5, min_listku=10):
    m = MS[(MS.z_vpb <= zmin) & (MS.chybi_listku >= min_listku)].copy()
    m['pravidlo'] = 'P5'
    return m


def p6(PM, zmin=5, nasobek=3, min_hlasu=10):
    """Neplatné lístky proti okolí, zvlášť lístek města (mag) a MČ/MO (mc)."""
    out = []
    for lis, c_inv, c_nb, c_z, c_pl in (('mag', 'inv_mag', 'inv_mag_nb', 'z_inv_mag', 'PLAT_LISTKY'), ('mc', 'inv_mc', 'inv_mc_nb', 'z_inv_mc', 'PLAT_MC')):
        if c_z not in PM:
            continue
        x = PM[PM[c_z].notna()]
        n = (x.ODEVZ_OBAL - x[c_pl])
        sel = x[(x[c_z] >= zmin) & (x[c_inv] >= nasobek * x[c_nb].clip(lower=0.003)) & (n >= min_hlasu)]
        for o, r in sel.iterrows():
            out.append(dict(pravidlo='P6', OID=o, MC=r.MC, listek=lis, neplatnych=int(r.ODEVZ_OBAL - r[c_pl]), obalek=int(r.ODEVZ_OBAL),
                            podil=float(r[c_inv]), okoli=float(r[c_nb]), z=float(r[c_z])))
    return pd.DataFrame(out)


def _edity(v):
    """Věrohodné překlepy hodnoty: záměna sousedních číslic, jiná číslice na jedné pozici, vložená / vypadlá číslice."""
    s = str(int(v)); out = set()
    for i in range(len(s) - 1):
        t = s[:i] + s[i + 1] + s[i] + s[i + 2:]
        out.add(int(t))
    for i in range(len(s)):
        for c in '0123456789':
            out.add(int(s[:i] + c + s[i + 1:]) if (i or c != '0' or len(s) == 1) else v)
    if len(s) > 1:
        out |= {int(s[:i] + s[i + 1:]) for i in range(len(s))}
    out.discard(int(v))
    return out


def p7(d, zk, outcome, rezerva, max_vysledku=8):
    """Kritické hodnoty těsného výsledku: okrskové hodnoty kandidátů, jejichž věrohodný překlep (v rozpětí kandidátky v okrsku)
    by změnil rozdělení mandátů nebo zvolené kandidáty. Nejde o nález chyby, ale o seznam míst k ověření v zápisu."""
    hl, ros, rk, cm = d['hl'], d['ros'], d['rk'], d['councils']
    s0, e0 = outcome(ros, rk, cm, zk)
    rows = []
    for p, g in hl[hl.ZK == zk].groupby('POR_STR_HL'):
        nc = int(ros[(ros.ZK == zk) & (ros.POR_STR_HL == p)].NCAND.fillna(0).iloc[0])
        for r in g.itertuples():
            v = np.array([getattr(r, c) for c in HC[:nc]], float)
            lo, hi = np.percentile(v, 10), v.max()
            for k in range(nc):
                x = int(v[k])
                if x < 10:
                    continue
                for y in _edity(x):
                    if abs(y - x) < rezerva or not (0.8 * lo <= y <= 1.2 * hi):
                        continue
                    dlt = y - x
                    s1, e1 = outcome(ros, rk, cm, zk, {int(p): dlt}, {(int(p), k + 1): dlt})
                    if s1 != s0 or e1 != e0:
                        rows.append(dict(pravidlo='P7', ZK=zk, OID=r.OID, strana=int(p), porcislo=k + 1, zapsano=x, varianta=y, rozdil=dlt,
                                         mandaty=s1 != s0, zvoleni=e1 != e0))
    R = pd.DataFrame(rows)
    return R.sort_values(['rozdil'], key=abs).head(max_vysledku * 5) if len(R) else R
