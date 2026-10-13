"""Stránky jednoho města (AUDIT_UNIT) pod report/kv/<slug>/: Přehled, Nálezy, Mapa okrsků, Forenzní testy.

Používá se pro města s automaticky generovaným registrem nálezů (findings_auto.py); Praha má ručně psané stránky v build_site.py.
Kromě stránek zapisuje data/results/kv/<slug>/summary.json (souhrn pro rozcestník, seznam obcí, registr a vyhledávání)
a CSV do report/data/<slug>/.
"""
import sys, os, json, math, re
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RES, P, ROOT, load, MAGISTRAT, HCOLS, UNIT, druh
from anomalies import prep
import svg
from svg import E, fmt
from sablona import page as _page, fig, badge_j, badge_d, filters, link, OUT, DOPAD_RANK
from units import units, okres_url, okres_label
from findings_auto import MO_MESTA

Y = 2026
U = {u['slug']: u for u in units()}[UNIT]
PD = f'kv/{UNIT}/'
TABS = [(PD + 'index.html', 'Přehled'), (PD + 'nalezy.html', 'Nálezy'), (PD + 'mapa.html', 'Mapa okrsků'), (PD + 'testy.html', 'Forenzní testy')]
CITY_ZK = MAGISTRAT * 100 + 1
JED = 'MO' if MAGISTRAT in MO_MESTA else 'MČ'
JED_PL = 'městských obvodů' if JED == 'MO' else 'městských částí'
MESTO = U['nazev']
VG_APP = 'https://volby.gov.cz/app/kv2026/cs/20261009/results/'
VG_JSON = f'https://volby.gov.cz/appdata/kv2026/20261009/vysled/okrsek/{U["okres"]}/'
A = 'target="_blank" rel="noopener"'
n0 = lambda v: f'{int(round(v)):,}'.replace(',', ' ')

d26 = load(Y); cm, ros, rk, t3 = d26['councils'], d26['ros'], d26['rk'], d26['t3']
F = pd.read_json(f'{RES}/findings_{Y}.json') if os.path.getsize(f'{RES}/findings_{Y}.json') > 5 else pd.DataFrame()
seats = pd.read_csv(f'{RES}/seats.csv')
fp = json.load(open(f'{RES}/fingerprints.json')); dc = json.load(open(f'{RES}/digits_corrected.json'))
integ = json.load(open(f'{RES}/integrity_summary.json'))
T = pd.read_pickle(f'{RES}/typos_{Y}.pkl')
_pref = set(json.load(open(f'{RES}/typos_preference_{Y}.json', encoding='utf-8'))) if os.path.exists(f'{RES}/typos_preference_{Y}.json') else set()
T = T[[f'{r.OID}|{int(r.ZK)}|{int(r.strana)}|{int(r.porcislo)}' not in _pref for r in T.itertuples()]] if len(T) else T  # bez preferenčních kandidátů
HAS_MC = (t3.TYPZASTUP == 2).any()
s26 = seats[seats.rok == Y].copy()
fr = s26.groupby('ZK').agg(z=('zastupitelstvo', 'first'), M=('mandatu', 'first'), gain=('hlasy_k_zisku', 'min'), lose=('hlasy_k_ztrate', 'min'))
fr['thr'] = s26[s26.prah_rozhoduje].assign(a=lambda x: x.do_prahu.abs()).groupby('ZK').a.min()  # jen strany, jimž hranice mění mandáty
fr['krit'] = fr[['gain', 'lose', 'thr']].min(axis=1); fr['vol'] = fr.krit / fr.M
fr = fr.sort_values('vol')
DRUH1 = {'města': 'město', 'obce': 'obec', 'městyse': 'městys'}[druh()]  # 1. pád do závorek a popisků
zlabel = lambda zk: f'{MESTO} ({DRUH1})' if int(zk) == CITY_ZK else cm.NAZEVZAST[int(zk)]


# ------------------------------------------------------------------ odkazy na volby.gov.cz
def vg_url(kod, okrsek=None, strana=None):
    """Zastupitelstvo města: typ 1, zastupitelstvo MČ/MO: typ 0 s kódem MČ/MO (ověřeno v aplikaci ČSÚ)."""
    ct = '1' if int(kod) == MAGISTRAT else '0'
    url = VG_APP + f'!__{ct}_{U["krajkod"]}_{U["okres"]}_{int(kod)}'
    if okrsek:
        url += f'___{int(okrsek)}'
        if strana:
            url += f'_{int(strana)}'
    return url


def vg_links(oid, zk=None, strana=None, both=False):
    obec, okr = str(oid).split('/')
    mc_kod = int(t3[(t3.OID == oid) & (t3.TYPZASTUP == 2)].KODZASTUP.iloc[0]) if HAS_MC and ((t3.OID == oid) & (t3.TYPZASTUP == 2)).any() else None
    kods = [MAGISTRAT] + ([mc_kod] if mc_kod else []) if both or zk is None else [int(zk) // 100]
    out = []
    for k in kods:
        lab = DRUH1 if k == MAGISTRAT else JED
        s = f'<a href="{vg_url(k, okr)}" {A}>okrsek {okr} – {lab}</a>'
        if strana:
            s += f' · <a href="{vg_url(k, okr, strana)}" {A}>hlasy kandidátů strany č. {int(strana)}</a>'
        s += f' <a class="json" href="{VG_JSON}{k}_{okr}.json" {A} title="Strojová data ČSÚ pro tento okrsek">(data)</a>'
        out.append(s)
    return ' · '.join(out)


def finding_links(r):
    oids = [o.strip() for o in str(r.OID).split(',') if '/' in o]
    if not oids:
        return ''
    parts = str(r.klic).split(':')
    strana = int(parts[3]) if parts[0] in ('stack', 'zero', 'typo') and len(parts) > 3 else None
    if len(oids) == 1:
        return vg_links(oids[0], r.ZK if int(r.ZK) > 0 else None, strana, both=int(r.ZK) == 0)
    return '<br>'.join(vg_links(o, None, None, both=True) for o in oids[:15]) + (f'<br>… a dalších {len(oids) - 15}' if len(oids) > 15 else '')


# ------------------------------------------------------------------ grafy
def year_counts(y):
    Ty = pd.read_pickle(f'{RES}/typos_{y}.pkl'); S = pd.read_pickle(f'{RES}/stacks_{y}.pkl'); Z = pd.read_pickle(f'{RES}/zeros_{y}.pkl')
    dy, t, _, _, _ = prep(y); t = t[t.TYPZASTUP == 1]
    if len(Ty):  # stejná vyřazovací pravidla jako v registru (preference kandidátů, řádky s dírami) pro všechny roky
        from findings_auto import excluded_typos, typo_key
        ex = excluded_typos(dy, Ty)
        Ty = Ty[np.array([typo_key(r) not in ex for r in Ty.itertuples()], dtype=bool)]
    if y == Y and len(Ty):  # rok 2026: bez hodnot, které vyřadila kontrola v datech (review/<obec>.json)
        rp = os.path.join(ROOT, 'review', f'{UNIT}.json')
        rv = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}
        key = lambda r: f'typo:{r.OID}:{int(r.ZK)}:{int(r.strana)}:{int(r.porcislo)}'
        souhrn_out = rv.get('typos:souhrn', {}).get('vyradit', False)
        Ty = Ty[np.array([not rv.get(key(r), {}).get('vyradit', False) and not (souhrn_out and key(r) not in rv) for r in Ty.itertuples()], dtype=bool)]
    g = lambda D, c, v: int((D[c] == v).sum()) if len(D) and c in D else 0
    return dict(ins=g(Ty, 'typ', 'vlozena_cislice'), drop=g(Ty, 'typ', 'vypadla_cislice'), dip=g(Ty, 'typ', 'propad'),
                stack=int((S.tri != 'slaby').sum()) if len(S) else 0, zero=int((Z.p_conservative < 1e-3).sum()) if len(Z) else 0,
                gap=int(((t.VYD_OBALKY - t.ODEVZ_OBAL) >= 20).sum()), a2=int((t.ODEVZ_OBAL > t.VYD_OBALKY).sum()))


def chart_years():
    YC = {y: year_counts(y) for y in (2018, 2022, 2026)}
    cats = ['Vložená číslice u kandidáta', 'Vypadlá číslice u kandidáta', 'Nelogický propad kandidáta', 'Chybějící balík lístků strany',
            'Strana s nulou místo očekávaných hlasů', 'Rozdíl obálek ≥ 20', 'Odevzdáno více obálek než vydáno']
    keys = ['ins', 'drop', 'dip', 'stack', 'zero', 'gap', 'a2']
    ch = svg.hbars(cats, [(str(y), [YC[y][k] for k in keys]) for y in (2018, 2022, 2026)], ['--series-3', '--series-2', '--series-1'], label_w=270)
    tb = svg.table(['Typ'] + [str(y) for y in (2018, 2022, 2026)], [[c] + [YC[y][k] for y in (2018, 2022, 2026)] for c, k in zip(cats, keys)])
    return fig(f'Stejné detektory, tři volby – {MESTO}', 'Počet nálezů podle typu (' + ('město + ' + JED if HAS_MC else f'zastupitelstvo {druh()}') + '), komunální volby 2018, 2022 a 2026', ch,
               svg.legend([('2018', '--series-3', 'rect'), ('2022', '--series-2', 'rect'), ('2026', '--series-1', 'rect')]), tb,
               'Počty zachycené detektory po automatickém vyřazení zjevných falešných poplachů (stejná pravidla pro všechny tři roky); u roku 2026 navíc bez hodnot, '
               'které vyřadila kontrola v datech. Roky 2018 a 2022 kontrolou neprošly a slouží jako kalibrační základna; data z nich neobsahují počet platných lístků, '
               'detektory jsou tam o něco citlivější na šum.')


def chart_margins():
    f = fr.head(14)
    ch = svg.hbars([zlabel(z) for z in f.index], [('Rezerva', [round(v, 1) for v in f.vol])], ['--series-1'], label_w=230, unit=' voličů', value_fmt=lambda v: fmt(v))
    tb = svg.table(['Zastupitelstvo', 'Mandátů', 'Rozhodující rezerva (hlasů)', 'Rezerva v „plných“ voličích'],
                   [[zlabel(z), r.M, int(r.krit), round(r.vol, 1)] for z, r in f.iterrows()])
    return fig('Kde rozhoduje pár hlasů', 'Nejmenší počet hlasů, který by změnil rozdělení mandátů (zisk/ztráta mandátu nebo 5% hranice), přepočtený na voliče se všemi hlasy',
               ch, '', tb)


def cand_vector_chart(zk, p, oid, title, sub):
    d, t, hl, ros_, nb = prep(Y)
    valid = sorted(d['rk'][(d['rk'].ZK == zk) & (d['rk'].POR_STR_HL == p) & (d['rk'].PLATNOST == 'A')].PORCISLO)
    g = hl[(hl.ZK == zk) & (hl.POR_STR_HL == p)].set_index('OID')
    if oid not in g.index or len(valid) < 3:
        return ''
    X = g[[HCOLS[i - 1] for i in valid]].astype(float); X.columns = valid
    n = t[t.ZK == zk].set_index('OID').PLAT_LISTKY
    nbs = [o for o in nb.get(oid, []) if o in X.index]
    if not nbs:
        return ''
    scaled = X.loc[nbs].div(n[nbs], axis=0).median() * n[oid]
    ser = [('Okrsek ' + oid.split('/')[1], X.loc[oid].tolist()), ('Medián sousedních okrsků (přepočteno na velikost okrsku)', scaled.round(1).tolist())]
    ch = svg.lines(valid, ser, ['--critical', '--series-1'], xlabel='Pořadí kandidáta', ylabel='Hlasy')
    tb = svg.table(['Pořadí', 'Okrsek', 'Sousedé (medián, přepočteno)'], [[c, int(X.loc[oid, c]), round(scaled[c], 1)] for c in valid])
    return fig(title, sub, ch, svg.legend([(ser[0][0], '--critical', 'line'), ('Medián sousedních okrsků', '--series-1', 'line')]), tb)


def party_chart(zk, oid, hl_party=None):
    R = pd.read_pickle(f'{RES}/shares_{Y}.pkl'); r = R[(R.OID == oid) & (R.ZK == zk)].sort_values('strana')
    if not len(r):
        return ''
    exp = (r.e * r['T']).round().fillna(0).tolist()
    tips = [f'č. {int(s)} {n}: zapsáno {int(h)}, očekáváno ~{int(e)}' for s, n, h, e in zip(r.strana, r.nazev, r.hlasy, exp)]
    ch = svg.columns([str(int(a)) for a in r.strana], r.hlasy.tolist(), highlight={i for i, s in enumerate(r.strana) if s == hl_party},
                     expected=exp, tips=tips, ylabel='Hlasy', xlab_every=1)
    tb = svg.table(['Č.', 'Strana', 'Zapsáno', 'Očekáváno dle sousedů'], [[int(s), n, int(h), int(e)] for s, n, h, e in zip(r.strana, r.nazev, r.hlasy, exp)])
    return fig(f'{zlabel(zk)}, okrsek {oid.split("/")[1]}: hlasy stran', 'Zapsané hlasy podle čísla strany; vodorovná čárka = očekávání podle sousedních okrsků', ch,
               svg.legend([('Zapsané hlasy', '--series-1', 'rect'), ('Strana z nálezu', '--critical', 'rect'), ('Očekávání (sousedé)', '--ink', 'line')]), tb)


def vpb_council_chart(zk, oid):
    S = pd.read_pickle(f'{RES}/missing_{Y}.pkl'); s = S[S.ZK == zk].sort_values('vpb')
    if len(s) < 2:
        return ''
    cats = [o.split('/')[1] for o in s.OID]
    ch = svg.columns(cats, (100 * s.vpb).round(1).tolist(), highlight={i for i, o in enumerate(s.OID) if o == oid}, ylabel='% využitých hlasů',
                     tips=[f'Okrsek {c}: {v:.1f} % hlasů na platný lístek' for c, v in zip(cats, 100 * s.vpb)], xlab_every=max(1, len(cats) // 20))
    return fig(f'{zlabel(zk)}: využití hlasů na lístek v okrscích', 'Podíl zapsaných hlasů z maxima (platné lístky × počet mandátů); červeně okrsek z nálezu', ch)


def chart_vpb():
    M = pd.read_pickle(f'{RES}/missing_{Y}.pkl'); M = M[M.z_vpb.notna()]
    if len(M) < 8:  # malé obce: srovnání se sousedními okrsky nemá oporu
        return ''
    S = pd.read_pickle(f'{RES}/stacks_{Y}.pkl')
    flag = set(zip(S[S.tri != 'slaby'].ZK, S[S.tri != 'slaby'].OID)) if len(S) else set()
    isf = np.array([(a, b) in flag for a, b in zip(M.ZK, M.OID)], dtype=bool)
    THR = -3.5
    tail = M.assign(f=isf)[M.z_vpb <= THR]
    rug = [(max(r.z_vpb, -35), '--critical' if r.f else '--muted',
            f'{r.MC} {r.OID.split("/")[1]} ({"město" if r.ZK == CITY_ZK else JED}): z = {r.z_vpb:.1f}'.replace('.', ',') + (' · potvrzený balík' if r.f else ''))
           for r in tail.itertuples()]
    ch = svg.hist(M.z_vpb.clip(-35, 10).values, np.arange(-35, 10.5, 1), M[isf].z_vpb.clip(-35, 10).values,
                  xlabel='Robustní z-skóre využití hlasů vůči sousedním okrskům', min_h=3, thr=(THR, 'práh podezření z = −3,5'), rug=rug,
                  rug_label=f'Každý záznam pod prahem jako tečka ({len(tail)} z {len(M)}):')
    return fig('Využití hlasů na lístek', f'Všech {n0(len(M))} záznamů okrsek × zastupitelstvo (2026); lineární osa, řídký levý chvost rozepsán po záznamech', ch,
               svg.legend([('Okrsky (histogram)', '--series-1', 'rect'), ('Potvrzený chybějící balík', '--critical', 'dot'), ('Pod prahem, nepotvrzeno', '--muted', 'dot')]))


def chart_klimek():
    out = []
    for y in (2022, 2026):
        h = json.load(open(f'{RES}/klimek_hist_{y}.json', encoding='utf-8'))
        k = fp[str(y)]['klimek']['korelace'][0]
        pts = h[k['strana']]['pts']
        ymax = min(1.0, max(0.6, math.ceil(max(p[1] for p in pts) * 10) / 10)) if pts else 0.6
        out.append(svg.scatter(pts, xlabel='Volební účast', ylabel=f'Podíl {k["strana"][:22]}', ymax=ymax,
                               title=f'{y}: vítěz {k["strana"][:30]} (ρ = {k["spearman"]:.2f})'.replace('.', ',')))
    return fig('Otisk volebních dat (Klimek et al.)', 'Každá tečka je okrsek: účast vs. podíl vítězné strany v zastupitelstvu ' + druh(), f'<div class="two">{out[0]}{out[1]}</div>', '',
               note='Při vhazování lístků vzniká „ocas“ okrsků s extrémní účastí a extrémním podílem vítěze a druhý shluk u 100 %.')


def tests_tables():
    ip = {y: fp[str(y)]['integer'] for y in (2018, 2022, 2026)}
    rows = [[y, ip[y]['turnout_integer_obs'], f"{ip[y]['turnout_integer_exp']:.1f} ± {ip[y]['turnout_integer_sd']:.1f}", f"{ip[y]['turnout_integer_p']:.2f}",
             ip[y]['leader'], ip[y]['leader_near_integer'], f"{ip[y]['leader_near_integer_exp']:.0f}", f"{ip[y]['leader_binom_p']:.2f}"] for y in (2018, 2022, 2026)]
    s = ('<figure class="card"><figcaption><h3>Celá procenta (Kobak, Shpilkin & Pshenichnikov 2016)</h3><p class="sub">Okrsky s účastí přesně na celém procentu vs. Monte Carlo očekávání; '
         'podíl vítěze v pásmu ±0,05 p. b. od celého procenta vs. 10 % očekávaných</p></figcaption>'
         '<div class="tw"><table><thead><tr><th>Rok</th><th class="num">Účast = celé %</th><th class="num">Očekáváno</th><th class="num">p</th><th>Vítěz</th><th class="num">Podíl ≈ celé %</th><th class="num">Očekáváno</th><th class="num">p</th></tr></thead><tbody>'
         + ''.join('<tr>' + ''.join(f'<td{" class=num" if i not in (0, 4) else ""}>{E(str(c))}</td>' for i, c in enumerate(r)) + '</tr>' for r in rows) + '</tbody></table></div></figure>')
    g = lambda y, lab, key, f='{:.3f}': (f.format(dc[str(y)][lab][key]).replace('.', ',') if dc[str(y)].get(lab) and dc[str(y)][lab].get(key) is not None else '–')
    trs = [(f'Poslední číslice – lídři kandidátek ≥ 100, {DRUH1} (p)', [g(y, 'magistrat', 'ld_c1_100_p') for y in (2018, 2022, 2026)])]
    if HAS_MC:
        trs += [(f'Poslední číslice – lídři ≥ 100, {JED} (p)', [g(y, 'mc', 'ld_c1_100_p') for y in (2018, 2022, 2026)]),
                (f'Poslední číslice – hlasy stran {JED} s počtem mandátů nedělitelným 5 (p)', [g(y, 'mc', 'ld_party_M_not5_p') for y in (2018, 2022, 2026)])]
    trs.append(('Poslední číslice – počty voličů, obálek, hlasů v zápisech (p)', [f'{fp[str(y)]["digits"]["t3"]["p"]:.3f}'.replace('.', ',') for y in (2018, 2022, 2026)]))
    # konkrétní odchylky roku 2026 (p < 0,01) s popisem nejčastější koncovky
    odch = []
    cand = [(f'lídři kandidátek ≥ 100, {DRUH1}', (dc['2026'].get('magistrat') or {}).get('ld_c1_100_p'), (dc['2026'].get('magistrat') or {}).get('ld_c1_100')),
            ('počty v zápisech', fp['2026']['digits']['t3']['p'], fp['2026']['digits']['t3']['last_digit'])]
    if HAS_MC:
        cand.append((f'lídři kandidátek ≥ 100, {JED}', (dc['2026'].get('mc') or {}).get('ld_c1_100_p'), (dc['2026'].get('mc') or {}).get('ld_c1_100')))
    for lab, pv, cnt in cand:
        if pv is not None and cnt and pv < 0.01:
            n = sum(cnt); k = int(np.argmax(cnt))
            odch.append(f'{lab}: p = {pv:.3f} při {n} hodnotách, nejčastější koncovka {k} ({cnt[k]}× místo očekávaných {n / 10:.0f}×)'.replace('.', ','))
    s += ('<figure class="card"><figcaption><h3>Číslicové testy – souhrn</h3><p class="sub">p &gt; 0,05 = v normě; hodnoty pod 0,01 jsou signálem k bližšímu pohledu, nikoli důkazem</p></figcaption>'
          '<div class="tw"><table><thead><tr><th>Test</th><th>2018</th><th>2022</th><th>2026</th></tr></thead><tbody>'
          + ''.join(f'<tr><td>{E(a)}</td>' + ''.join(f'<td>{E(v)}</td>' for v in b) + '</tr>' for a, b in trs) + '</tbody></table></div>'
          '<p class="note">Číslicových testů je napříč 13 městy, několika typy a třemi ročníky přes sto; hodnota p &lt; 0,01 se proto u některého z nich objeví náhodou '
          's vysokou pravděpodobností a malé vzorky (desítky hodnot) jsou citlivé na náhodné shluky. Jako signál hodnotíme až p &lt; 0,0005 (Bonferroniho korekce). '
          'Hlasy stran nejsou do testu zahrnuty: křížek u strany násobí počet lístků počtem mandátů, což poslední číslici strukturálně ovlivňuje.'
          + (' V roce 2026: ' + E('; '.join(odch)) + '. Hodnoty pocházejí z různých okrsků a stran bez opakujících se čísel – samostatně nejde o doklad manipulace.' if odch else '')
          + '</p></figure>')
    return s


def map_svg(status):
    cen = pd.read_pickle(os.path.join(P, 'centroids.pkl'))
    if not len(cen):
        return '<p class="sub">Hranice okrsků nejsou k dispozici.</p>'
    lat0 = float(cen.lat.mean()); k = 1400
    allp = [pt for g in cen.geom for poly in g for pt in poly]
    lon_min = min(p[0] for p in allp); lat_max = max(p[1] for p in allp)
    X = lambda lo: (lo - lon_min) * math.cos(math.radians(lat0)) * k; Yf = lambda la: (lat_max - la) * k
    W = max(X(p[0]) for p in allp); H = max(Yf(p[1]) for p in allp)
    mcn = t3.drop_duplicates('OID').set_index('OID').MC
    paths = []
    for r in cen.itertuples():
        dpath = ' '.join('M' + ' L'.join(f'{X(a):.1f},{Yf(b):.1f}' for a, b in poly) + 'Z' for poly in r.geom)
        st = status.get(r.OID)
        fill = {'critical': 'var(--critical)', 'serious': 'var(--serious)', 'warning': 'var(--warning)'}[st[0]] if st else 'var(--map-base)'
        tip = f'{mcn.get(r.OID, "")} · okrsek {r.OID.split("/")[1]}' + (f' — {st[1]}' if st else ' — bez nálezu')
        paths.append(f'<path d="{dpath}" fill="{fill}" class="{"f" if st else ""}" data-tip="{E(tip)}" tabindex="{0 if st else -1}"/>')
    paths.sort(key=lambda s: 'class="f"' in s)
    return f'<svg viewBox="0 0 {W:.0f} {H:.0f}" class="chart map" role="img" aria-label="Mapa volebních okrsků – {E(MESTO)}">{"".join(paths)}</svg>'


# ------------------------------------------------------------------ stránky
def page(fn, title, body, desc=''):
    crumbs = [('Přehled', 'index.html'), ('Komunální volby 2026', 'kv/index.html'), (okres_label(U), okres_url(U))]
    crumbs += [(MESTO, None)] if fn == 'index.html' else [(MESTO, PD + 'index.html'), (title, None)]
    _page(PD + fn, f'{title} – {MESTO}' if fn != 'index.html' else f'Komunální volby 2026 – {MESTO}', body, desc, section='kv', crumbs=crumbs, tabs=TABS)


def registry_rows():
    if not len(F):
        return '<tr><td colspan="5">Žádné nálezy.</td></tr>'
    return ''.join(f'<tr><td class="id"><a href="nalezy.html#{r.id}">{r.id}</a></td><td>{E(r.zastupitelstvo)}<br><span class="sub">'
                   + (finding_links(r) if str(r.OID).count('/') == 1 else E(str(r.MC))[:120]) + '</span></td>'
                   f'<td>{E(r.typ)}<br><span class="sub">{E(str(r.subjekt))}</span></td><td>{badge_j(int(r.jistota))}</td><td>{badge_d(r.dopad_kat)}</td></tr>'
                   for r in F.itertuples())


def mc_table():
    if not U['mc']:
        return ''
    rows = ''
    for m in sorted(U['mc'], key=lambda m: m['nazev']):
        zk = m['kod'] * 100 + 1
        ids = [r.id for r in F.itertuples() if int(r.ZK) == zk] if len(F) else []
        ids += [r.id for r in F.itertuples() if int(r.ZK) == 0 and m['nazev'] in str(r.MC).split(', ')] if len(F) else []
        nt = int((T.ZK == zk).sum()) if len(T) else 0
        krit = fr.krit.get(zk)
        rows += (f'<tr id="mc-{m["kod"]}"><td data-v="{E(m["nazev"])}"><a href="{vg_url(m["kod"])}" {A}>{E(m["nazev"])}</a></td>'
                 f'<td class="num">{m["mandatu"]}</td><td class="num">{m["okrsku"]}</td><td class="num" data-v="{m["volicu"]}">{n0(m["volicu"])}</td>'
                 f'<td data-v="{len(ids)}">' + ', '.join(f'<a href="nalezy.html#{i}">{i}</a>' for i in ids) + '</td>'
                 f'<td class="num">{nt}</td><td class="num" data-v="{krit if krit is not None and krit == krit else 1e9}">{n0(krit) if krit is not None and krit == krit else "–"}</td></tr>')
    return (f'<h2 id="mc">Zastupitelstva {JED_PL}</h2><p class="sub">Název vede na výsledky na volby.gov.cz. Rozhodující rezerva = nejmenší počet hlasů, '
            'který by změnil rozdělení mandátů nebo vedl k rovnosti rozhodované losem. Řadit lze kliknutím na záhlaví sloupce.</p>' + filters('t-mc', []) +
            f'<div class="card tw"><table id="t-mc" class="sortable"><thead><tr><th>{"Městský obvod" if JED == "MO" else "Městská část"}</th><th class="num">Mandátů</th><th class="num">Okrsků</th><th class="num">Voličů</th>'
            '<th>Nálezy</th><th class="num">Překlepy u kandidátů</th><th class="num">Rozhodující rezerva (hlasů)</th></tr></thead><tbody>' + rows + '</tbody></table></div>')


def prepocet():
    """(souhlasí, zastupitelstva s losem): rozdíl jen mezi kandidátkami se shodným počtem hlasů znamená, že o mandátu rozhodl los,
    který přepočet zopakovat nemůže."""
    ok, los = True, []
    for zk, g in s26.groupby('ZK'):
        mm = g[g.mand_vypocet != g.mand_oficial]
        if not len(mm):
            continue
        if mm.hlasy.nunique() == 1 and mm.mand_vypocet.sum() == mm.mand_oficial.sum():
            los.append(zlabel(zk))
        else:
            ok = False
    return ok, los


def page_index():
    i26 = [x for x in integ if x['rok'] == Y][0]
    n_zast = 1 + len(U['mc'])
    rep_ok, los = prepocet()
    los_txt = f' (v zastupitelstvu {", ".join(los)} rozhodl při shodném počtu hlasů o mandátu los)' if los else ''
    nv = F[F.dopad_kat.isin(['Mění mandáty', 'Mění zvolené', 'Může změnit mandáty'])] if len(F) else F
    nzk = int((F.stav_kontroly == 'zkontrolováno').sum()) if len(F) else 0
    tight = fr[(fr.krit <= 30) | (fr.vol <= 3)]
    pbad = [y for y in ('2026',) if fp[y]['integer']['turnout_integer_p'] < 0.0005 or (dc[y]['magistrat'] or {}).get('ld_c1_100_p', 1) < 0.0005
            or fp[y]['digits']['t3']['p'] < 0.0005]  # Bonferroniho korekce přes ~100 testů napříč městy
    verdict = ('<p><strong>Závěr:</strong> ' + (f'Celkové výsledky jsou plně reprodukovatelné z okrskových dat a nezávislý přepočet mandátů souhlasí u všech zastupitelstev{los_txt}. ' if rep_ok else
               'Nezávislý přepočet mandátů se u některého zastupitelstva liší – viz nálezy. ')
               + ('Globální forenzní testy jsou v normě a srovnatelné s lety 2018 a 2022. ' if not pbad else 'Některý z globálních testů vykazuje odchylku – viz Forenzní testy. ') + '</p>')
    if len(nv):
        verdict += '<p><strong>Nálezy s možným vlivem na výsledek:</strong> ' + '; '.join(f'<a href="nalezy.html#{r.id}">{r.id}</a> {E(r.zastupitelstvo)} – {E(r.typ.lower())} ({E(r.dopad_kat.lower())})' for r in nv.itertuples()) + '.</p>'
    else:
        verdict += '<p>Žádný z nálezů podle simulace oprav nemění rozdělení mandátů ani zvolené kandidáty.</p>'
    if len(tight):
        verdict += '<p><strong>Těsné výsledky:</strong> ' + ', '.join(f'{E(zlabel(z))} – rozhodlo {n0(r.krit)} hlasů' for z, r in tight.iterrows()) + '.</p>'
    body = f'''<h1>Komunální volby 2026 – {E(MESTO)}</h1>
<p class="lead">Analýza všech {n0(i26["okrsku"])} volebních okrsků a {n0(i26["zaznamu_t3"])} okrskových zápisů (zastupitelstvo {druh()}{f" a {len(U['mc'])} zastupitelstev {JED_PL}" if U['mc'] else ""}),
{n0(i26["stran_overeno"])} stranických a {n0(i26["kandidatu_overeno"])} kandidátních výsledků z otevřených dat ČSÚ, porovnaná s volbami 2018 a 2022.</p>
<p class="sub">Nálezy vytvořily stejné detektory jako u Prahy a registr byl sestaven automaticky; {f"zkontrolováno {nzk} z {len(F)} nálezů (stav je uveden u každého nálezu)" if len(F) else "detektory v obci nenašly nic, co by bylo třeba ověřit"}.
Každý nález obsahuje proklik na výsledky okrsku na volby.gov.cz.</p>
<div class="verdict">{verdict}</div>
<div class="tiles">
<div class="tile"><div class="l">Okrsků analyzováno</div><div class="v">{n0(i26["okrsku"])}</div><div class="s">{n0(i26["zaznamu_t3"])} zápisů, {n_zast} {"zastupitelstvo" if n_zast == 1 else ("zastupitelstva" if 2 <= n_zast <= 4 else "zastupitelstev")}</div></div>
<div class="tile"><div class="l">Reprodukce výsledků</div><div class="v">{"100 %" if rep_ok else "neshoda"}</div><div class="s">{n0(i26["stran_overeno"])} stran, {n0(i26["kandidatu_overeno"])} kandidátů</div></div>
<div class="tile"><div class="l">Nálezy s možným vlivem</div><div class="v">{len(nv)}</div><div class="s">mění / mohou změnit mandáty</div></div>
<div class="tile"><div class="l">Nálezů celkem</div><div class="v">{len(F)}</div><div class="s">z toho {len(T)} překlepů u kandidátů v souhrnu</div></div>
<div class="tile"><div class="l">Nejtěsnější rezerva</div><div class="v">{n0(fr.krit.iloc[0]) if len(fr) else "–"} hl.</div><div class="s">{E(zlabel(fr.index[0])) if len(fr) else ""}</div></div>
</div>
<h2>Registr nálezů podle priority</h2><p class="sub">Jistota = pravděpodobnost, že zveřejněný údaj neodpovídá skutečnosti. Dopad = výsledek simulace opravy a nového přepočtu mandátů a pořadí kandidátů,
u nálezů bez určené strany srovnání rozsahu chyby s rozhodující rezervou.</p>
<div class="card tw"><table><thead><tr><th>ID</th><th>Zastupitelstvo / okrsek</th><th>Typ a subjekt</th><th>Jistota chyby</th><th>Dopad</th></tr></thead><tbody>{registry_rows()}</tbody></table></div>'''
    body += chart_years() + chart_margins() + mc_table()
    body += '<h2>Co jsme ověřili</h2><ul class="l">' + ''.join(f'<li>{x}</li>' for x in [
        f'Součty okrsků proti oficiálním výsledkům u všech {n0(i26["stran_overeno"])} stran a {n0(i26["kandidatu_overeno"])} kandidátů (2026).',
        'Nezávislý přepočet mandátů (5% klauzule s přepočtem pro neúplné kandidátky, d’Hondt, 10% preferenční pravidlo) ' + (f'souhlasí u všech zastupitelstev{los_txt}.' if rep_ok else 'se u některého zastupitelstva liší.'),
        'Aritmetika zápisů, shoda obálek mezi lístky, nulové a chybějící hlasy stran, chybějící balíky lístků, překlepy u kandidátů' + (', rozdíly mezi lístky města a ' + JED if HAS_MC else '') + '.',
        'Globální testy (Klimek, celá procenta, poslední číslice) a srovnání četnosti nálezů s lety 2018 a 2022.'
    ]) + '</ul>'
    page('index.html', 'Přehled', body, f'Forenzní audit komunálních voleb 2026 – {MESTO}')


def page_findings():
    body = f'<h1>Nálezy – {E(MESTO)}</h1><p class="lead">Každý nález uvádí důkazy, míru jistoty, simulovaný dopad a doporučený krok. Registr byl vytvořen automaticky; u každého nálezu je uveden stav kontroly.</p>'
    body += ('<p class="sub">Škála jistoty: <strong>Jistá</strong> – deterministický rozpor v datech; <strong>Velmi vysoká</strong> ≥ 95 %; <strong>Vysoká</strong> 80–95 %; '
             '<strong>Střední</strong> 50–80 %; <strong>Nízká</strong> &lt; 50 % (riziko, nikoli zjištěná chyba).</p>')
    for r in F.itertuples() if len(F) else []:
        parts = str(r.klic).split(':')
        ch = ''
        if parts[0] == 'stack':
            ch = cand_vector_chart(int(parts[2]), int(parts[3]), parts[1], f'{zlabel(parts[2])}, okrsek {parts[1].split("/")[1]} – {r.subjekt}: hlasy kandidátů',
                                   'Celá kandidátka je posunutá dolů o stejný počet hlasů – chybí lístky s křížkem u strany')
        elif parts[0] == 'zero':
            ch = party_chart(int(parts[2]), parts[1], int(parts[3]))
        elif parts[0] == 'missing':
            ch = vpb_council_chart(int(parts[2]), parts[1])
        elif parts[0] == 'typo':
            ch = cand_vector_chart(int(parts[2]), int(parts[3]), parts[1], f'{zlabel(parts[2])}, okrsek {parts[1].split("/")[1]}: hlasy kandidátů strany', 'Hodnota kandidáta z nálezu proti sousedům na listině')
        stav = ('<span class="st st-done">zkontrolováno</span> ' + E(str(r.kontrola))) if r.stav_kontroly == 'zkontrolováno' else '<span class="st st-plan">automaticky, zatím neověřeno</span>'
        links = finding_links(r)
        body += (f'<article class="card find p{int(r.priorita)}" id="{r.id}"><h3>{r.id} · {E(r.typ)}</h3><p class="sub">{E(r.zastupitelstvo)} · {E(str(r.MC))[:200]}'
                 + (f' · okrsek {E(str(r.OID))}' if str(r.OID).count('/') == 1 else '') + '</p>'
                 f'<div style="margin-top:8px">{badge_j(int(r.jistota))} {badge_d(r.dopad_kat)}</div><dl>'
                 f'<dt>Subjekt</dt><dd>{E(str(r.subjekt))}</dd><dt>Zjištění</dt><dd>{E(r.zjisteni)}</dd><dt>Důkaz</dt><dd>{E(r.dukaz)}</dd>'
                 f'<dt>Jistota chyby</dt><dd>{E(r.jistota_text)}</dd><dt>Indikace úmyslu</dt><dd>{E(r.umysl)}</dd><dt>Dopad</dt><dd>{E(r.dopad)}</dd>'
                 f'<dt>Doporučení</dt><dd>{E(r.doporuceni)}</dd><dt>Stav kontroly</dt><dd>{stav}</dd>'
                 + (f'<dt>Ověřit na volby.gov.cz</dt><dd>{links}</dd>' if links else '') + f'</dl>{ch}</article>')
    if len(T):
        Ts = T.sort_values('rozdil', key=abs, ascending=False)
        rows = [[zlabel(r.ZK), r.OID.split('/')[1], r.nazev_strany, r.porcislo, r.jmeno, r.hlasy, r.pravdepodobne,
                 {'vlozena_cislice': 'vložená číslice', 'vypadla_cislice': 'vypadlá číslice', 'propad': 'propad'}[r.typ], 'ano' if r.mandat == 'A' else 'ne',
                 vg_links(r.OID, r.ZK, r.strana)] for r in Ts.itertuples()]
        body += '<h2 id="preklepy">Seznam překlepů a propadů u kandidátů (2026)</h2>'
        body += ('<div class="card tw"><table><thead><tr><th>Zastupitelstvo</th><th>Okrsek</th><th>Strana</th><th class="num">Poř.</th><th>Kandidát</th><th class="num">Zapsáno</th><th class="num">Pravděp.</th><th>Typ</th><th>Zvolen</th><th>Ověřit</th></tr></thead><tbody>'
                 + ''.join('<tr>' + ''.join(f'<td{" class=num" if i in (3, 5, 6) else ""}>{c if i == 9 else E(str(c))}</td>' for i, c in enumerate(row)) + '</tr>' for row in rows) + '</tbody></table></div>')
    page('nalezy.html', 'Nálezy', body, f'Detailní nálezy forenzního auditu komunálních voleb 2026 – {MESTO}')


def status_map():
    status = {}
    for o in T.OID if len(T) else []:
        status[o] = ('warning', 'Překlep / propad u kandidáta')
    m = pd.read_pickle(f'{RES}/precinct_{Y}.pkl')
    for o in m[m.gap >= 20].index:
        status[o] = ('warning', f'Rozdíl obálek {int(m.gap[o])}')
    for r in F.itertuples() if len(F) else []:
        if str(r.OID).count('/') == 1:
            sev = 'critical' if r.dopad_kat in ('Mění mandáty', 'Mění zvolené', 'Může změnit mandáty') else ('serious' if int(r.jistota) >= 3 else 'warning')
            status[r.OID] = (sev, f'{r.id}: {r.typ}')
    return status


def page_map():
    st = status_map()
    cnt = pd.Series([v[0] for v in st.values()], dtype=object).value_counts()
    body = (f'<h1>Mapa okrsků s nálezy – {E(MESTO)}</h1><p class="lead">Polygony okrsků podle hranic ČSÚ (stav 2022; hranice 2026 nebyly jako soubor zveřejněny – nové okrsky nejsou zakresleny). '
            'Najetím myší nebo tabulátorem zobrazíte detail.</p>')
    body += fig('Kde se nálezy nacházejí', 'Barva = nejzávažnější nález v okrsku', map_svg(st),
                svg.legend([(f'Mění / může měnit výsledek ({cnt.get("critical", 0)})', '--critical', 'rect'), (f'Chyba bez vlivu ({cnt.get("serious", 0)})', '--serious', 'rect'),
                            (f'Drobná chyba / nesrovnalost ({cnt.get("warning", 0)})', '--warning', 'rect'), ('Bez nálezu', '--map-base', 'rect')]))
    page('mapa.html', 'Mapa okrsků', body, f'Mapa volebních okrsků s nálezy – {MESTO}')


def page_tests():
    body = f'<h1>Forenzní testy – {E(MESTO)}</h1><p class="lead">Testy celé populace okrsků, které se v odborné literatuře používají k odhalení plošné manipulace, porovnané s volbami 2018 a 2022.</p>'
    body += chart_klimek() + chart_vpb() + tests_tables()
    page('testy.html', 'Forenzní testy', body, f'Globální forenzní testy – {MESTO}')


STRANKA_OKRSKU = 4  # obce s menším počtem okrsků (typ 'obec') dostanou vlastní stránku jen s nálezem; jinak jsou řádkem v přehledu okresu
INFORMATIVNI = ('tight', 'batches')  # těsný výsledek a opravy během volební noci ukáže tabulka okresu


def ma_stranku():
    if U['typ'] != 'obec' or U['okrsku'] >= STRANKA_OKRSKU:
        return True
    return bool(len(F)) and any(str(k) not in INFORMATIVNI for k in F.klic)


def write_outputs(stranka=True):
    od = os.path.join(OUT, 'data', UNIT)
    files = []
    if stranka:
        os.makedirs(od, exist_ok=True)
        if len(F):
            F.to_csv(os.path.join(od, 'nalezy_2026.csv'), index=False, encoding='utf-8-sig'); files.append((f'{UNIT}/nalezy_2026.csv', f'{MESTO}: registr nálezů'))
        if len(T):
            T.to_csv(os.path.join(od, 'preklepy_kandidati_2026.csv'), index=False, encoding='utf-8-sig'); files.append((f'{UNIT}/preklepy_kandidati_2026.csv', f'{MESTO}: překlepy a propady u kandidátů'))
        seats.to_csv(os.path.join(od, 'mandaty_prepocet_2018_2026.csv'), index=False, encoding='utf-8-sig'); files.append((f'{UNIT}/mandaty_prepocet_2018_2026.csv', f'{MESTO}: přepočet mandátů a rezervy'))
        pd.read_pickle(f'{RES}/precinct_{Y}.pkl').to_csv(os.path.join(od, 'okrsky_metriky_2026.csv'), encoding='utf-8-sig'); files.append((f'{UNIT}/okrsky_metriky_2026.csv', f'{MESTO}: metriky okrsků'))
    else:  # bez vlastní stránky: odstranit případné starší výstupy
        import shutil
        for d in (od, os.path.join(OUT, PD)):
            shutil.rmtree(d, ignore_errors=True)
    nv = F[F.dopad_kat.isin(['Mění mandáty', 'Mění zvolené', 'Může změnit mandáty'])] if len(F) else F
    c26 = ros[(ros.ZK == CITY_ZK) & (ros.NCAND.fillna(0) > 0)]
    rk0 = fr.loc[CITY_ZK] if CITY_ZK in fr.index else None
    summ = dict(kod=MAGISTRAT, slug=UNIT, nazev=MESTO, stranka=bool(stranka), url=PD + 'index.html' if stranka else '', nal=int(len(F)), nal_vysl=int(len(nv)),
                nal_zkontrolovano=int((F.stav_kontroly == 'zkontrolováno').sum()) if len(F) else 0,
                rez=float(fr.krit.iloc[0]) if len(fr) else None, rez_z=zlabel(fr.index[0]) if len(fr) else '',
                # přehled okresu: údaje zastupitelstva obce
                kandidatek=int(len(c26)), rep_ok=prepocet()[0], los=prepocet()[1],
                preklepu=int(len(T)), rez_obec=float(rk0.krit) if rk0 is not None and rk0.krit == rk0.krit else None,
                files=files,
                findings=[dict(id=r.id, klic=str(r.klic), zastupitelstvo=r.zastupitelstvo, OID=str(r.OID), MC=str(r.MC), typ=r.typ, subjekt=str(r.subjekt), jistota=int(r.jistota),
                               dopad_kat=r.dopad_kat, stav=r.stav_kontroly, zjisteni=str(r.zjisteni)) for r in F.itertuples()] if len(F) else [])
    json.dump(summ, open(f'{RES}/summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    st = ma_stranku()
    if st:
        page_index(); page_findings(); page_map(); page_tests()
    write_outputs(st)
    print('ok', UNIT, len(F), 'stránka' if st else 'jen přehled okresu')
