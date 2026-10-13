"""Statický web report/: rozcestník, komunální volby (zatím Praha pod kv/praha/), senát, registr nálezů, metodika, data."""
import sys, os, json, shutil, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import RES, P, ROOT, load, MAGISTRAT, HCOLS
from anomalies import prep
import svg
from svg import E, fmt
from sablona import page as _page, fig, badge_j, badge_d, filters, write_assets, link, AUTHOR_URL, GEN, OUT, JLAB, DOPAD_RANK
from units import units, okres_url, okres_label
import unicodedata

os.makedirs(os.path.join(OUT, 'assets'), exist_ok=True); os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
MAGZK = MAGISTRAT * 100 + 1
VG_APP = 'https://volby.gov.cz/app/kv2026/cs/20261009/results/'
VG_JSON = 'https://volby.gov.cz/appdata/kv2026/20261009/vysled/okrsek/1100/'


def vg_url(kod, okrsek=None, strana=None):
    """Odkaz do aplikace volby.gov.cz.
    Parametry v URL: přehled_typ zastupitelstva_kraj_okres_obec_MČMO_obvod_okrsek_kandidátní listina.
    Magistrát: typ 1 + obec 554782. Zastupitelstvo MČ: typ 0 (všechna) + obec = kód MČ – při typu 2
    aplikace kód MČ jako obec nepřijme a deeplink zahodí (ověřeno v prohlížeči 11. 10. 2026)."""
    ct = '1' if int(kod) == MAGISTRAT else '0'
    url = VG_APP + f'!__{ct}_1100_1100_{int(kod)}'
    if okrsek:
        url += f'___{int(okrsek)}'
        if strana:
            url += f'_{int(strana)}'
    return url


def vg_links(oid, which, strana=None):
    """HTML odkazy na výsledky okrsku; which: 'mag' | 'mc' | 'obe'; strana = číslo kandidátní listiny."""
    mc, okr = str(oid).split('/')
    kods = {'mag': [MAGISTRAT], 'mc': [int(mc)], 'obe': [MAGISTRAT, int(mc)]}[which]
    out = []
    for k in kods:
        lab = 'magistrát' if k == MAGISTRAT else 'MČ'
        s = f'<a href="{vg_url(k, okr)}" target="_blank" rel="noopener">okrsek {okr} – {lab}</a>'
        if strana:
            s += f' · <a href="{vg_url(k, okr, strana)}" target="_blank" rel="noopener">hlasy kandidátů strany č. {int(strana)}</a>'
        s += f' <a class="json" href="{VG_JSON}{k}_{okr}.json" target="_blank" rel="noopener" title="Strojová data ČSÚ pro tento okrsek">(data)</a>'
        out.append(s)
    return ' · '.join(out)


STRANA_NALEZU = {'N01': 6, 'N02': 2, 'N03': 22}


def finding_party(r):
    if r.id in STRANA_NALEZU:
        return STRANA_NALEZU[r.id]
    if int(r.ZK) > 0:
        m = ros26[(ros26.ZK == int(r.ZK)) & (ros26.ZKRATKAO30 == r.subjekt)]
        if len(m):
            return int(m.POR_STR_HL.iloc[0])
    return None


def finding_links(r):
    oids = [o.strip() for o in str(r.OID).split(',') if '/' in o]
    if oids:
        which = 'mag' if int(r.ZK) // 100 == MAGISTRAT else ('mc' if int(r.ZK) > 0 else 'obe')
        return '<br>'.join(vg_links(o, which, finding_party(r) if len(oids) == 1 else None) for o in oids)
    if r.typ.startswith('Výsledek těsnější'):
        names = {'Petrovice': 'Praha-Petrovice', 'Křeslice': 'Praha-Křeslice'}
        out = []
        for n in str(r.MC).split(', '):
            n = names.get(n, n)
            zk = cm26[(cm26.NAZEVZAST == n) & (cm26.TYPZASTUP == 2)].index
            if len(zk):
                out.append(f'<a href="{vg_url(int(zk[0]) // 100)}" target="_blank" rel="noopener">{E(n)}</a>')
        return ' · '.join(out)
    if r.typ.startswith('Překlepy'):
        return '<a href="#preklepy">odkazy u každé položky v tabulce níže</a>'
    return ''
F = pd.read_json(f'{RES}/findings_2026.json')

UL = units()
U = {u['kod']: u for u in UL}
PHA = U[MAGISTRAT]
PD = f'kv/{PHA["slug"]}/'
PHA_TABS = [(PD + 'index.html', 'Přehled'), (PD + 'nalezy.html', 'Nálezy'), (PD + 'mapa.html', 'Mapa okrsků'), (PD + 'testy.html', 'Forenzní testy')]


def page_pha(fn, title, body, desc=''):
    """Stránka územní jednotky Praha (kv/praha/<fn>) se záložkami a drobečkovou navigací."""
    crumbs = [('Přehled', 'index.html'), ('Komunální volby 2026', 'kv/index.html')]
    crumbs += [('Praha', None)] if fn == 'index.html' else [('Praha', PD + 'index.html'), (title, None)]
    _page(PD + fn, f'{title} – Praha' if fn != 'index.html' else 'Komunální volby 2026 – Praha', body, desc, section='kv', crumbs=crumbs, tabs=PHA_TABS)


# ------------------------------------------------------------------ data prep
d26 = load(2026); ros26, rk26, cm26 = d26['ros'], d26['rk'], d26['councils']
integ = json.load(open(f'{RES}/integrity_summary.json'))
seats = pd.read_csv(f'{RES}/seats.csv'); cands = pd.read_csv(f'{RES}/candidates_pref.csv')
fp = json.load(open(f'{RES}/fingerprints.json')); dc = json.load(open(f'{RES}/digits_corrected.json'))
mat = pd.read_pickle(f'{RES}/materiality_2026.pkl'); joint = pd.read_pickle(f'{RES}/materiality_joint_2026.pkl')
t3_26 = d26['t3']
n_ok = t3_26.OID.nunique()


def year_counts(y):
    T = pd.read_pickle(f'{RES}/typos_{y}.pkl'); S = pd.read_pickle(f'{RES}/stacks_{y}.pkl'); Z = pd.read_pickle(f'{RES}/zeros_{y}.pkl')
    _, t3, _, _, _ = prep(y); t = t3[t3.TYPZASTUP == 1]
    return dict(ins=int((T.typ == 'vlozena_cislice').sum()), drop=int((T.typ == 'vypadla_cislice').sum()), dip=int((T.typ == 'propad').sum()),
                stack=int((S.tri != 'slaby').sum()), zero=int((Z.p_conservative < 1e-3).sum()),
                gap=int(((t.VYD_OBALKY - t.ODEVZ_OBAL) >= 20).sum()), a2=int((t.ODEVZ_OBAL > t.VYD_OBALKY).sum()), okrsky=int(t.OID.nunique()))


YC = {y: year_counts(y) for y in (2018, 2022, 2026)}

# fragile councils
s26 = seats[seats.rok == 2026].copy()
fr = s26.groupby('ZK').agg(z=('zastupitelstvo', 'first'), M=('mandatu', 'first'), gain=('hlasy_k_zisku', 'min'), lose=('hlasy_k_ztrate', 'min'))
fr['thr'] = s26[s26.prah_rozhoduje].assign(a=lambda x: x.do_prahu.abs()).groupby('ZK').a.min()  # jen strany, jimž hranice mění mandáty
fr['krit'] = fr[['gain', 'lose', 'thr']].min(axis=1); fr['vol'] = fr.krit / fr.M
fr = fr.sort_values('vol')

# ------------------------------------------------------------------ charts
def chart_years():
    cats = ['Vložená číslice u kandidáta', 'Vypadlá číslice u kandidáta', 'Nelogický propad kandidáta', 'Chybějící balík lístků strany',
            'Strana s nulou místo očekávaných hlasů', 'Rozdíl obálek ≥ 20', 'Odevzdáno více obálek než vydáno']
    keys = ['ins', 'drop', 'dip', 'stack', 'zero', 'gap', 'a2']
    ser = [(str(y), [YC[y][k] for k in keys]) for y in (2018, 2022, 2026)]
    ch = svg.hbars(cats, ser, ['--series-3', '--series-2', '--series-1'], label_w=270)
    tb = svg.table(['Typ'] + [str(y) for y in (2018, 2022, 2026)], [[c] + [YC[y][k] for y in (2018, 2022, 2026)] for c, k in zip(cats, keys)])
    return fig('Stejné detektory, tři volby: chybovost je v roce 2026 běžná, ne mimořádná',
               'Počet nálezů podle typu v Praze (magistrát + MČ), komunální volby 2018, 2022 a 2026',
               ch, svg.legend([('2018', '--series-3', 'rect'), ('2022', '--series-2', 'rect'), ('2026', '--series-1', 'rect')]), tb,
               'Roky 2018 a 2022 slouží jako kalibrační základna. Data z let 2018 a 2022 neobsahují počet platných lístků, proto jsou detektory '
               'založené na hlasech na lístek v těchto letech o něco citlivější na šum.')


def chart_margins():
    f = fr.head(14)
    cats = [z for z in f.z]; vals = [round(v, 1) for v in f.vol]
    ch = svg.hbars(cats, [('Rezerva', vals)], ['--series-1'], label_w=190, unit=' voličů', value_fmt=lambda v: fmt(v))
    tb = svg.table(['Zastupitelstvo', 'Mandátů', 'Rozhodující rezerva (hlasů)', 'Rezerva v „plných“ voličích'],
                   [[r.z, r.M, int(r.krit), round(r.vol, 1)] for r in f.itertuples()])
    return fig('Kde rozhoduje pár hlasů', 'Nejmenší počet hlasů, který by změnil rozdělení mandátů (zisk/ztráta mandátu nebo 5% hranice), přepočtený na voliče se všemi hlasy',
               ch, '', tb, 'V Petrovicích stačí 2 hlasy – méně než jeden volič (každý volič zde má 15 hlasů).')


def chart_intent():
    j = joint[joint.ZK == MAGZK]
    dv = {int(k): v for k, v in json.loads(j.dV.iloc[0]).items()}
    names = ros26[ros26.ZK == MAGZK].set_index('POR_STR_HL').ZKRATKAO30
    items = sorted(((names[k], v) for k, v in dv.items() if abs(v) >= 100), key=lambda x: -x[1])
    ch = svg.diverging([a for a, _ in items], [b for _, b in items])
    tb = svg.table(['Strana', 'Čistý dopad oprav (hlasy)'], [[a, b] for a, b in items])
    return fig('Komu chyby uškodily: nikomu systematicky', 'Magistrát: o kolik hlasů by se strana změnila po opravě všech detekovaných chyb (kladné = chyby straně hlasy ubraly)',
               ch, svg.legend([('chyby straně ubraly', '--div-pos', 'rect'), ('chyby straně přidaly', '--div-neg', 'rect')]), tb,
               'Chybějící balíky postihly STAN, SPOLU, PRAHA SOBĚ i ANO; vložené číslice naopak nadsadily několik kandidátů Pirátů. '
               'Směr chyb nekoreluje s jedním politickým subjektem – to odpovídá nahodilým chybám, nikoli koordinované manipulaci.')


def cand_vector_chart(zk, p, oid, title, sub, hl_pos=None, note=''):
    d, t3, hl, ros, nb = prep(2026)
    valid = sorted(d['rk'][(d['rk'].ZK == zk) & (d['rk'].POR_STR_HL == p) & (d['rk'].PLATNOST == 'A')].PORCISLO)
    g = hl[(hl.ZK == zk) & (hl.POR_STR_HL == p)].set_index('OID')
    X = g[[HCOLS[i - 1] for i in valid]].astype(float); X.columns = valid
    n = t3[t3.ZK == zk].set_index('OID').PLAT_LISTKY
    nbs = [o for o in nb[oid] if o in X.index]
    # neighbours scaled to this precinct's number of valid ballots
    scaled = X.loc[nbs].div(n[nbs], axis=0).median() * n[oid]
    ser = [('Okrsek ' + oid.split('/')[1], X.loc[oid].tolist()), ('Medián sousedních okrsků (přepočteno na velikost okrsku)', scaled.round(1).tolist())]
    ch = svg.lines(valid, ser, ['--critical', '--series-1'], xlabel='Pořadí kandidáta', ylabel='Hlasy',
                   highlight=(hl_pos, f'č. {hl_pos}') if hl_pos else None)
    tb = svg.table(['Pořadí', 'Okrsek', 'Sousedé (medián, přepočteno)'], [[c, int(X.loc[oid, c]), round(scaled[c], 1)] for c in valid])
    return fig(title, sub, ch, svg.legend([(ser[0][0], '--critical', 'line'), ('Medián sousedních okrsků', '--series-1', 'line')]), tb, note)


def chart_2038():
    R = pd.read_pickle(f'{RES}/shares_2026.pkl'); r = R[(R.OID == '500089/2038') & (R.ZK == MAGZK)].sort_values('strana')
    cats = [f'{int(a)}' for a in r.strana]
    exp = (r.e * r['T']).round().tolist()
    tips = [f'č. {int(s)} {n}: zapsáno {int(h)}, očekáváno ~{int(e)}' for s, n, h, e in zip(r.strana, r.nazev, r.hlasy, exp)]
    ch = svg.columns(cats, r.hlasy.tolist(), highlight={i for i, (h, e) in enumerate(zip(r.hlasy, exp)) if h == 0 and e > 200},
                     expected=exp, tips=tips, ylabel='Hlasy', xlab_every=1)
    tb = svg.table(['Č.', 'Strana', 'Zapsáno', 'Očekáváno dle sousedů'], [[int(s), n, int(h), int(e)] for s, n, h, e in zip(r.strana, r.nazev, r.hlasy, exp)])
    return fig('Praha 2, okrsek 2038 – magistrát: strany na konci lístku chybí', 'Zapsané hlasy podle čísla strany na hlasovacím lístku; vodorovná čárka = očekávání podle 8 sousedních okrsků',
               ch, svg.legend([('Zapsané hlasy', '--series-1', 'rect'), ('Nula u strany s vysokým očekáváním', '--critical', 'rect'), ('Očekávání (sousedé)', '--ink', 'line')]), tb,
               'ANO 2011 (č. 22) má 0 hlasů při očekávání ~1 570 (podle lístku MČ ve stejném okrsku až ~2 530). Strany č. 19–24 mají dohromady 2 hlasy.')


def chart_15003():
    S = pd.read_pickle(f'{RES}/missing_2026.pkl'); s = S[S.ZK == 54738701].sort_values('vpb')
    cats = [o.split('/')[1] for o in s.OID]
    ch = svg.columns(cats, (100 * s.vpb).round(1).tolist(), highlight={0}, ylabel='% využitých hlasů',
                     tips=[f'Okrsek {c}: {v:.1f} % hlasů na platný lístek' for c, v in zip(cats, 100 * s.vpb)], xlab_every=1)
    tb = svg.table(['Okrsek', 'Platné lístky', 'Hlasy celkem', 'Využití hlasů'], [[o, int(a), int(b), f'{100 * v:.1f} %'] for o, a, b, v in zip(s.OID, s.PLAT_LISTKY, s.PL_HL_CELK, s.vpb)])
    return fig('Praha 15 – lístek MČ: okrsek 15003 využil jen 60 % hlasů', 'Podíl skutečně zapsaných hlasů z maxima (platné lístky × 31 mandátů) v každém okrsku Prahy 15',
               ch, '', tb, 'Běžná hodnota je 93–98 %. Volič může dát méně hlasů, ale 40% propad v jediném okrsku (v roce 2022 zde 90 %) znamená nezapsané hlasy zhruba 196 lístků.')


def chart_vpb():
    M = pd.read_pickle(f'{RES}/missing_2026.pkl')
    S = pd.read_pickle(f'{RES}/stacks_2026.pkl'); flag = set(zip(S[S.tri != 'slaby'].ZK, S[S.tri != 'slaby'].OID)) | {(MAGZK, '500089/2038')}
    M = M[M.z_vpb.notna()]
    isf = [(a, b) in flag for a, b in zip(M.ZK, M.OID)]
    v = M.z_vpb.clip(-35, 10).values; fv = M[isf].z_vpb.clip(-35, 10).values
    THR = -3.5
    tail = M.assign(f=isf)[M.z_vpb <= THR]
    def tip(r):
        zast = 'magistrát' if r.ZK == MAGZK else 'MČ'
        stav = 'potvrzená chyba' if r.f else 'pod prahem, bez potvrzení druhou linií důkazů'
        return f'{r.MC} {r.OID.split("/")[1]} ({zast}): z = {r.z_vpb:.1f}'.replace('.', ',') + f' · {stav}'
    rug = [(max(r.z_vpb, -35), '--critical' if r.f else '--muted', tip(r)) for r in tail.itertuples()]
    ch = svg.hist(v, np.arange(-35, 10.5, 1), fv, xlabel='Robustní z-skóre využití hlasů vůči sousedním okrskům',
                  min_h=3, thr=(THR, 'práh podezření z = −3,5'), rug=rug,
                  rug_label=f'Každý záznam pod prahem jako tečka ({len(tail)} z {len(M)}):')
    return fig('Využití hlasů na lístek: odlehlé hodnoty jsou vzácné a jasně oddělené',
               f'Všech {len(M):,} záznamů okrsek × zastupitelstvo (2026). Histogram má lineární osu, neprázdné sloupce mají minimální výšku 3 px. '
               'Řídký levý chvost je pod osou rozepsán po jednotlivých záznamech.'.replace(',', ' ', 1),
               ch, svg.legend([('Okrsky (histogram)', '--series-1', 'rect'), ('Potvrzená chyba (balík / nulové strany)', '--critical', 'dot'),
                               ('Pod prahem, nepotvrzeno', '--muted', 'dot')]))


def chart_klimek():
    out = []
    for y, nm in ((2022, 'SPOLU pro Prahu'), (2026, 'STAROSTOVÉ A NEZÁVISLÍ')):
        h = json.load(open(f'{RES}/klimek_hist_{y}.json', encoding='utf-8'))[nm]
        rho = [k for k in fp[str(y)]['klimek']['korelace'] if k['strana'] == nm][0]['spearman']
        out.append(svg.scatter(h['pts'], xlabel='Volební účast', ylabel=f'Podíl {nm[:22]}', title=f'{y}: vítěz {nm} (ρ = {rho:.2f})'.replace('.', ',')))
    return fig('Otisk volebních dat (Klimek et al.): bez známek vhazování lístků', 'Každá tečka je okrsek: účast vs. podíl vítězné strany na magistrátu',
               f'<div class="two">{out[0]}{out[1]}</div>', '',
               note='Při vhazování lístků vzniká „ocas“ okrsků s extrémní účastí a extrémním podílem vítěze a druhý shluk u 100 %. V Praze 2026 rozdělení odpovídá roku 2022 i 2018; '
                    'mírná kladná korelace účasti a podílu STAN (ρ = 0,32) je stejná jako u STAN v roce 2022 (0,32) a odráží sociodemografii, nikoli manipulaci.')


def chart_digits():
    a = fp['2026']['digits']['magistrat']['last_digit']
    b = dc['2026']['magistrat']['ld_c1_100']
    c1 = svg.columns([str(i) for i in range(10)], a, ylabel='Počet', xlab_every=1, width=520, height=280, small=True)
    c2 = svg.columns([str(i) for i in range(10)], b, ylabel='Počet', xlab_every=1, width=520, height=280, small=True)
    p1 = fp['2026']['digits']['magistrat']['ld_p']; p2 = dc['2026']['magistrat']['ld_c1_100_p']
    return fig('Test poslední číslice (Beber & Scacco): artefakt volebního systému, ne manipulace',
               'Poslední číslice počtů hlasů – vlevo hlasy stran na magistrátu, vpravo hlasy lídrů kandidátek (≥ 100)',
               f'<div class="two"><div><p class="sub">Hlasy stran, magistrát (p = {p1:.1e})</p>{c1}</div><div><p class="sub">Hlasy kandidátů č. 1 ≥ 100 (p = {p2:.2f})</p>{c2}</div></div>', '',
               note='Hlasy strany ≈ počet lístků s křížkem u strany × 65 mandátů, proto končí přednostně na 0 a 5 – test na hlasech stran je u komunálních voleb strukturálně nepoužitelný. '
                    'Na surových počtech lístků test prochází (p = 0,97), stejně jako na lístcích MČ s počtem mandátů nedělitelným pěti.')


# ------------------------------------------------------------------ map
def map_svg():
    cen = pd.read_pickle(os.path.join(P, 'centroids.pkl'))
    lat0 = 50.08; k = 1400
    allp = [pt for g in cen.geom for poly in g for pt in poly]
    lon_min = min(p[0] for p in allp); lat_max = max(p[1] for p in allp)
    X = lambda lo: (lo - lon_min) * math.cos(math.radians(lat0)) * k; Yf = lambda la: (lat_max - la) * k
    W = max(X(p[0]) for p in allp); H = max(Yf(p[1]) for p in allp)
    status = {}
    T = pd.read_pickle(f'{RES}/typos_2026.pkl')
    for o in T.OID: status[o] = ('warning', 'Překlep / propad u kandidáta')
    m = pd.read_pickle(f'{RES}/precinct_2026.pkl')
    for o in m[(m.PLAT_LISTKY == m.ODEVZ_OBAL) & (m.PLAT_MC == m.ODEVZ_OBAL) & (m.ODEVZ_OBAL >= 100)].index: status[o] = ('warning', 'Nulový počet neplatných lístků')
    for o in m[m.gap >= 20].index: status[o] = ('warning', f'Rozdíl obálek {int(m.gap[o])}')
    for r in F.itertuples():
        if r.typ.startswith('Chybějící balík') or r.typ.startswith('Nulové'):
            status[r.OID] = ('serious', f'{r.id}: {r.typ} – {r.subjekt}')
    status['500224/10043'] = ('critical', 'N01: překlep mění 2 mandáty v Praze 10')
    status['547387/15003'] = ('critical', 'N02: chybějící balík, možná změna mandátu v Praze 15')
    mcn = t3_26.drop_duplicates('OID').set_index('OID').MC
    paths = []
    for r in cen.itertuples():
        dpath = ' '.join('M' + ' L'.join(f'{X(a):.1f},{Yf(b):.1f}' for a, b in poly) + 'Z' for poly in r.geom)
        st = status.get(r.OID)
        fill = {'critical': 'var(--critical)', 'serious': 'var(--serious)', 'warning': 'var(--warning)'}[st[0]] if st else 'var(--map-base)'
        tip = f'{mcn.get(r.OID, "")} · okrsek {r.OID.split("/")[1]}' + (f' — {st[1]}' if st else ' — bez nálezu')
        paths.append(f'<path d="{dpath}" fill="{fill}" class="{"f" if st else ""}" data-tip="{E(tip)}" tabindex="{0 if st else -1}"/>')
    paths.sort(key=lambda s: 'class="f"' in s)
    return f'<svg viewBox="0 0 {W:.0f} {H:.0f}" class="chart map" role="img" aria-label="Mapa pražských volebních okrsků s vyznačenými nálezy">{"".join(paths)}</svg>', status


# ------------------------------------------------------------------ pages
def page_index():
    nf = F[F.priorita <= 2]
    rows = ''.join(f'<tr><td><a href="nalezy.html#{r.id}">{r.id}</a></td><td>{E(r.zastupitelstvo)}<br><span class="sub">'
                   + (finding_links(r) if str(r.OID).count('/') == 1 else E(str(r.OID)[:40]))
                   + '</span></td>'
                   f'<td>{E(r.typ)}<br><span class="sub">{E(r.subjekt)}</span></td><td>{badge_j(r.jistota)}</td><td>{badge_d(r.dopad_kat)}</td></tr>'
                   for r in F.sort_values(['priorita', 'jistota'], ascending=[True, False]).itertuples())
    s26c = seats[seats.rok == 2026]
    body = f'''<h1>Komunální volby 2026 – Praha</h1>
<p class="lead">Nezávislá analýza všech 1 120 volebních okrsků, 2 240 okrskových zápisů (Zastupitelstvo hl. m. Prahy a 57 zastupitelstev městských částí),
36 761 stranických a 8 607 kandidátních výsledků z otevřených dat ČSÚ, porovnaná s volbami 2018 a 2022.</p>
<p class="sub">Autor: <a href="{AUTHOR_URL}">Martin Suchan</a> · 11. 10. 2026 · Každý nález obsahuje proklik na výsledky okrsku na volby.gov.cz.</p>
<div class="verdict"><p><strong>Závěr:</strong> Data nenesou známky systematické ani koordinované manipulace. Celkové výsledky jsou plně reprodukovatelné
z okrskových dat a nezávislý přepočet mandátů souhlasí na 100 %. Globální forenzní testy (Klimek, Kobak, Beber–Scacco, 2BL) jsou v normě a srovnatelné s lety 2018 a 2022.</p>
<p><strong>Nalezli jsme ale konkrétní chyby v okrskových zápisech, z nichž dvě mohou změnit složení zastupitelstva MČ:</strong>
v <strong>Praze 10</strong> pravděpodobný překlep (165 místo ~16 hlasů) drží stranu Naše Praha 10 nad 5% hranicí – po opravě by <strong>2 mandáty připadly jiným stranám</strong>;
v <strong>Praze 15</strong> chybí v okrsku 15003 hlasy zhruba 196 lístků, což <strong>může změnit 1 mandát</strong>. Obě místa doporučujeme bezodkladně ověřit přepočtem –
lhůta pro návrh k Městskému soudu v Praze je <strong>10 dnů od vyhlášení výsledků Státní volební komisí</strong> (§ 60 zák. č. 491/2001 Sb.).</p></div>
<div class="tiles">
<div class="tile"><div class="l">Okrsků analyzováno</div><div class="v">{n_ok:,}</div><div class="s">2 240 zápisů, 100 % pokrytí</div></div>
<div class="tile"><div class="l">Reprodukce výsledků</div><div class="v">100 %</div><div class="s">330 stran, 8 607 kandidátů, mandáty i pořadí</div></div>
<div class="tile"><div class="l">Nálezy měnící mandáty</div><div class="v">1 + 1</div><div class="s">Praha 10 (jistá změna), Praha 15 (možná změna)</div></div>
<div class="tile"><div class="l">Potvrzené chyby bez dopadu</div><div class="v">{int((F.typ.str.startswith("Chybějící") | F.typ.str.startswith("Nulové")).sum()) - 1} + {len(pd.read_pickle(f"{RES}/typos_2026.pkl"))}</div><div class="s">chybějící balíky / nulové strany + překlepy u kandidátů</div></div>
<div class="tile"><div class="l">Známky manipulace</div><div class="v">žádné</div><div class="s">směr chyb je nahodilý</div></div>
</div>'''.replace(f'{n_ok:,}', f'{n_ok:,}'.replace(',', ' '))
    body += '<h2>Registr nálezů podle priority</h2><p class="sub">Jistota = pravděpodobnost, že zveřejněný údaj neodpovídá skutečnosti. Dopad = výsledek simulace opravy a nového přepočtu mandátů a pořadí kandidátů.</p>'
    body += f'<div class="card tw"><table><thead><tr><th>ID</th><th>Zastupitelstvo / okrsek</th><th>Typ a subjekt</th><th>Jistota chyby</th><th>Dopad</th></tr></thead><tbody>{rows}</tbody></table></div>'
    body += '<h2>Doporučení</h2><ol class="steps">'
    body += ('<li><strong>Okamžitě (lhůta 10 dnů):</strong> ověřit zápisy a přepočítat hlasovací lístky MČ v okrscích <strong>Praha 10 – 10043</strong> (N01) a <strong>Praha 15 – 15003</strong> (N02). '
             'Návrh na neplatnost volby kandidáta může podat každý volič zapsaný ve volebním okrsku, kde byl člen zastupitelstva volen, nebo každá volební strana, jejíž kandidátní listina byla pro volby do tohoto zastupitelstva zaregistrována (§ 60 odst. 1).</li>'
             '<li><strong>Preventivně:</strong> zvážit kontrolní přepočet v MČ s rozhodující rezervou pod úrovní běžné chybovosti – Praha-Petrovice (2 hlasy) a Praha 13 (22 hlasů, navíc potvrzená chyba v okrsku 13053).</li>'
             '<li><strong>Opravy bez vlivu na mandáty</strong> (N03–N10, překlepy): předat ČSÚ / MV jako podnět ke zpřesnění dat; ovlivňují preferenční hlasy jednotlivých kandidátů o desítky hlasů.</li>'
             '<li><strong>Systémově:</strong> doplnit do programu ČSÚ pro příjem zápisů automatické kontroly, které by všechny zde nalezené chyby zachytily: '
             '(a) využití hlasů na lístek &lt; 85 % vůči okolí, (b) strana s 0 hlasy při vysokém očekávání, (c) nemonotónní/odlehlé hlasy kandidátů uvnitř listiny, '
             '(d) nulový počet neplatných lístků u velkých okrsků. Kontrola (b) v roce 2026 jednou zafungovala (Praha 10/10034), jednou ne (Praha 2/2038).</li></ol>')
    body += fig_years + fig_margins + fig_intent
    body += '<h2>Co jsme ověřili a nenašli</h2><ul class="l">' + ''.join(f'<li>{x}</li>' for x in [
        'Součty okrsků se shodují s oficiálními výsledky u všech 330 stran a 8 607 kandidátů (2026), stejně jako v letech 2018 a 2022.',
        'Nezávislý přepočet mandátů (5% klauzule s přepočtem pro neúplné kandidátky, d’Hondt, 10% preferenční pravidlo) souhlasí u všech 58 zastupitelstev ve všech třech volbách.',
        'Žádný okrsek nemá více hlasů, než umožňuje počet platných lístků, ani kandidáta s více hlasy, než bylo platných lístků.',
        'Obálky na magistrátním a místním lístku se shodují ve všech okrscích (jedna úřední obálka).',
        'Nenalezli jsme nadbytek „kulatých“ procent účasti ani podílu vítěze (Kobak et al.): 6 okrsků oproti očekávaným 8,3.',
        'Žádné kopírované výsledky mezi okrsky; všech 11 případů podezřelého „prohození“ stran se vysvětlilo místní geografií (stejný vzorec na druhém lístku nebo v roce 2022).',
        'Účast oproti roku 2022 se výrazně (|z| &gt; 5) změnila jen ve 2 okrscích, bez výkyvu jakékoli strany.'
    ]) + '</ul>'
    body += mc_table()
    page_pha('index.html', 'Přehled', body, 'Manažerské shrnutí forenzního auditu komunálních voleb v Praze 2026')


def page_findings():
    body = '<h1>Nálezy – Praha</h1><p class="lead">Každý nález uvádí důkazy, míru jistoty, posouzení možného úmyslu, simulovaný dopad na mandáty a doporučený krok.</p>'
    body += '<p class="sub">Škála jistoty: <strong>Jistá</strong> – deterministický rozpor v datech; <strong>Velmi vysoká</strong> ≥ 95 % (dvě nezávislé linie důkazů nebo logická nemožnost); '
    body += '<strong>Vysoká</strong> 80–95 %; <strong>Střední</strong> 50–80 %; <strong>Nízká</strong> &lt; 50 % (riziko, nikoli zjištěná chyba).</p>'
    body += ('<p class="sub">U každého nálezu je odkaz <strong>„Ověřit na volby.gov.cz“</strong>, který otevře výsledky daného okrsku v oficiální aplikaci ČSÚ '
             'a tam, kde se nález týká konkrétní strany, i přímo hlasy jejích kandidátů v okrsku. Odkaz „(data)“ vede na strojová data ČSÚ pro okrsek včetně hlasů všech kandidátů.</p>')
    charts = {'N01': cand_vector_chart(50022401, 6, '500224/10043', 'Praha 10, okrsek 10043 – Naše Praha 10: hlasy kandidátů podle pořadí',
                                       'Kandidát č. 24 má 165 hlasů, ostatní 15–29; jeho průměr ve zbylých okrscích odpovídá hlasům pro stranu', 24),
              'N02': chart_15003(), 'N03': chart_2038()}
    for r in F.sort_values(['priorita', 'jistota'], ascending=[True, False]).itertuples():
        if r.typ.startswith('Chybějící balík') and r.id not in charts and str(r.OID).count('/') == 1:
            zk = int(r.ZK); p = int(ros26[(ros26.ZK == zk) & (ros26.ZKRATKAO30 == r.subjekt)].POR_STR_HL.iloc[0])
            charts[r.id] = cand_vector_chart(zk, p, r.OID, f'{r.MC}, okrsek {r.OID.split("/")[1]} – {r.subjekt}: hlasy kandidátů',
                                             'Celá kandidátka je posunutá dolů o stejný počet hlasů – chybí lístky s křížkem u strany')
        body += (f'<article class="card find p{r.priorita}" id="{r.id}"><h3>{r.id} · {E(r.typ)}</h3><p class="sub">{E(r.zastupitelstvo)} · {E(str(r.MC))} · okrsek {E(str(r.OID))}</p>'
                 f'<div style="margin-top:8px">{badge_j(r.jistota)} {badge_d(r.dopad_kat)}</div><dl>'
                 f'<dt>Subjekt</dt><dd>{E(r.subjekt)}</dd><dt>Zjištění</dt><dd>{E(r.zjisteni)}</dd><dt>Důkaz</dt><dd>{E(r.dukaz)}</dd>'
                 f'<dt>Jistota chyby</dt><dd>{E(r.jistota_text)}</dd><dt>Indikace úmyslu</dt><dd>{E(r.umysl)}</dd><dt>Dopad</dt><dd>{E(r.dopad)}</dd>'
                 f'<dt>Doporučení</dt><dd>{E(r.doporuceni)}</dd>'
                 + (f'<dt>Ověřit na volby.gov.cz</dt><dd>{finding_links(r)}</dd>' if finding_links(r) else '')
                 + f'</dl>{charts.get(r.id, "")}</article>')
        if r.id.startswith('N11'):
            pass
    T = pd.read_pickle(f'{RES}/typos_2026.pkl').sort_values('rozdil', key=abs, ascending=False)
    zn = lambda zk: 'Magistrát' if zk == MAGZK else cm26.NAZEVZAST[zk]
    rows = [[zn(r.ZK), r.OID.split('/')[1], r.nazev_strany, r.porcislo, r.jmeno, r.hlasy, r.pravdepodobne,
             {'vlozena_cislice': 'vložená číslice', 'vypadla_cislice': 'vypadlá číslice', 'propad': 'propad'}[r.typ], 'ano' if r.mandat == 'A' else 'ne',
             vg_links(r.OID, 'mag' if r.ZK == MAGZK else 'mc', r.strana)] for r in T.itertuples()]
    body += '<h2 id="preklepy">Seznam překlepů a propadů u kandidátů (2026)</h2>'
    body += ('<div class="card tw"><table><thead><tr><th>Zastupitelstvo</th><th>Okrsek</th><th>Strana</th><th class="num">Poř.</th><th>Kandidát</th><th class="num">Zapsáno</th><th class="num">Pravděp.</th><th>Typ</th><th>Zvolen</th><th>Ověřit</th></tr></thead><tbody>'
             + ''.join('<tr>' + ''.join(f'<td{" class=num" if i in (3, 5, 6) else ""}>{c if i == 9 else E(str(c))}</td>' for i, c in enumerate(row)) + '</tr>' for row in rows) + '</tbody></table></div>')
    page_pha('nalezy.html', 'Nálezy', body, 'Detailní nálezy forenzního auditu voleb Praha 2026')


def page_map():
    m, status = map_svg()
    cnt = pd.Series([v[0] for v in status.values()]).value_counts()
    body = ('<h1>Mapa okrsků s nálezy – Praha</h1><p class="lead">Polygony okrsků podle hranic ČSÚ (stav 2022; hranice 2026 nebyly jako soubor zveřejněny – 3 nové okrsky nejsou zakresleny). '
            'Najetím myší nebo tabulátorem zobrazíte detail.</p>')
    body += fig('Kde se nálezy nacházejí', 'Barva = nejzávažnější nález v okrsku (magistrát nebo MČ)', m,
                svg.legend([(f'Mění / může měnit mandáty ({cnt.get("critical", 0)})', '--critical', 'rect'),
                            (f'Potvrzená chyba bez vlivu na mandáty ({cnt.get("serious", 0)})', '--serious', 'rect'),
                            (f'Drobná chyba / procedurální nesrovnalost ({cnt.get("warning", 0)})', '--warning', 'rect'), ('Bez nálezu', '--map-base', 'rect')]),
                note='Nálezy jsou rozptýlené po celém městě bez prostorového shluku – to odpovídá nezávislým chybám jednotlivých komisí, nikoli řízenému zásahu.')
    page_pha('mapa.html', 'Mapa okrsků', body, 'Mapa pražských volebních okrsků s vyznačenými nálezy')


def page_tests():
    ip = {y: fp[str(y)]['integer'] for y in (2018, 2022, 2026)}
    body = '<h1>Forenzní testy – Praha</h1><p class="lead">Testy celé populace okrsků, které se v odborné literatuře používají k odhalení plošné manipulace (vhazování lístků, „kreslení“ výsledků). Všechny jsou porovnány s volbami 2018 a 2022.</p>'
    body += chart_klimek() + chart_vpb() + chart_digits()
    rows = [[y, ip[y]['turnout_integer_obs'], f"{ip[y]['turnout_integer_exp']:.1f} ± {ip[y]['turnout_integer_sd']:.1f}", f"{ip[y]['turnout_integer_p']:.2f}",
             ip[y]['leader'], ip[y]['leader_near_integer'], f"{ip[y]['leader_near_integer_exp']:.0f}", f"{ip[y]['leader_binom_p']:.2f}"] for y in (2018, 2022, 2026)]
    body += ('<figure class="card"><figcaption><h3>Celá procenta (Kobak, Shpilkin & Pshenichnikov 2016)</h3><p class="sub">Okrsky s účastí přesně na celém procentu vs. Monte Carlo očekávání; podíl vítěze v pásmu ±0,05 p. b. od celého procenta vs. 10 % očekávaných</p></figcaption>'
             '<div class="tw"><table><thead><tr><th>Rok</th><th class="num">Účast = celé %</th><th class="num">Očekáváno</th><th class="num">p</th><th>Vítěz</th><th class="num">Podíl ≈ celé %</th><th class="num">Očekáváno</th><th class="num">p</th></tr></thead><tbody>'
             + ''.join('<tr>' + ''.join(f'<td{" class=num" if i not in (0, 4) else ""}>{E(str(c))}</td>' for i, c in enumerate(r)) + '</tr>' for r in rows) + '</tbody></table></div>'
             '<p class="note">Ani v jednom roce není nadbytek celých procent – znak „ručně dopisovaných“ výsledků chybí.</p></figure>')
    kr = []
    for y in (2018, 2022, 2026):
        for k in fp[str(y)]['klimek']['korelace']:
            kr.append([y, k['strana'], f"{k['spearman']:.2f}"])
    body += fig('Korelace účasti a podílu stran', 'Spearmanův koeficient mezi účastí a podílem strany v okrsku (magistrát, 6 nejsilnějších stran)', '<div></div>', '',
                svg.table(['Rok', 'Strana', 'ρ'], kr), 'Profil korelací je ve všech třech volbách obdobný (pravicové/liberální strany kladně, ANO a SPD záporně) – jde o sociodemografický vzorec Prahy.')
    d26c = fp['2026']['digits']
    body += ('<figure class="card"><figcaption><h3>Číslicové testy – souhrn</h3></figcaption><div class="tw"><table><thead><tr><th>Test</th><th>2018</th><th>2022</th><th>2026</th><th>Interpretace</th></tr></thead><tbody>'
             f'<tr><td>Poslední číslice – lídři kandidátek ≥ 100, magistrát (p)</td><td>{dc["2018"]["magistrat"]["ld_c1_100_p"]:.3f}</td><td>{dc["2022"]["magistrat"]["ld_c1_100_p"]:.2f}</td><td>{dc["2026"]["magistrat"]["ld_c1_100_p"]:.2f}</td><td>2026 v normě</td></tr>'
             f'<tr><td>Poslední číslice – lídři ≥ 100, MČ (p)</td><td>{dc["2018"]["mc"]["ld_c1_100_p"]:.2f}</td><td>{dc["2022"]["mc"]["ld_c1_100_p"]:.2f}</td><td>{dc["2026"]["mc"]["ld_c1_100_p"]:.2f}</td><td>v normě</td></tr>'
             f'<tr><td>Poslední číslice – hlasy stran MČ s počtem mandátů nedělitelným 5 (p)</td><td>{dc["2018"]["mc"]["ld_party_M_not5_p"]:.2f}</td><td>{dc["2022"]["mc"]["ld_party_M_not5_p"]:.3f}</td><td>{dc["2026"]["mc"]["ld_party_M_not5_p"]:.2f}</td><td>v normě</td></tr>'
             f'<tr><td>Poslední číslice – počty voličů, obálek, hlasů v zápisech (p)</td><td>{fp["2018"]["digits"]["t3"]["p"]:.2f}</td><td>{fp["2022"]["digits"]["t3"]["p"]:.2f}</td><td>{d26c["t3"]["p"]:.2f}</td><td>v normě</td></tr>'
             f'<tr><td>2BL (Mebane) – průměr 2. číslice hlasů stran MČ (Benford 4,187)</td><td>{fp["2018"]["digits"]["mc"]["bl2_mean"]:.3f}</td><td>{fp["2022"]["digits"]["mc"]["bl2_mean"]:.3f}</td><td>{d26c["mc"]["bl2_mean"]:.3f}</td><td>v normě (p = {d26c["mc"]["bl2_p"]:.2f})</td></tr>'
             '</tbody></table></div><p class="note">Číslicové testy mají podle literatury (Deckert, Myagkov & Ordeshook 2011) omezenou průkaznost; zde slouží jen jako doplněk. '
             'U hlasů stran na magistrátu jsou kvůli násobení počtem mandátů (65) nepoužitelné.</p></figure>')
    tc = pd.read_pickle(f'{RES}/turnout_change.pkl')
    body += fig('Změna účasti 2022 → 2026 v okrscích se stabilními hranicemi', f'{int(tc.stabilni.sum())} okrsků; robustní z-skóre vůči mediánu změny v MČ',
                svg.hist(tc.z.dropna().clip(-8, 8).values, np.arange(-8, 8.5, 0.5), tc[tc.z.abs() > 5].z.values, xlabel='z-skóre změny účasti'),
                svg.legend([('Okrsky', '--series-1', 'rect'), ('|z| > 5', '--critical', 'rect')]),
                note='Jen 2 okrsky (Praha 2/2032, Praha 9/9033) mají neobvyklý nárůst účasti (+15 a +16 p. b.); žádná strana v nich nevykazuje odpovídající výkyv – slabý signál bez dalšího nálezu.')
    page_pha('testy.html', 'Forenzní testy', body, 'Klimek, Kobak, Beber–Scacco a další testy pro Prahu 2018–2026')


def page_method():
    src = [
        ('ČSÚ – Otevřená data, volby do zastupitelstev obcí 2026 (registry, číselníky, okrsková data CSV)', 'https://www.volby.cz/opendata/kv2026/kv2026_opendata.htm'),
        ('ČSÚ – Otevřená data KV 2022', 'https://www.volby.cz/opendata/kv2022/kv2022_opendata.htm'),
        ('ČSÚ – Otevřená data KV 2018', 'https://www.volby.cz/opendata/kv2018/kv2018_opendata.htm'),
        ('ČSÚ – průběžné XML dávky okrskových výsledků 2026 (165 dávek)', 'https://volby.gov.cz/appdata/kv2026/20261009/odata/okrsky/vysledky_okrsky.xml'),
        ('ČSÚ – popis datové věty T/3 a HL', 'https://www.volby.cz/opendata/kv2026/KV2026_datovaveta.htm'),
        ('ČSÚ – hranice volebních okrsků 2022 (GeoJSON)', 'https://www.volby.cz/opendata/kv2022/geo/vol_okrsky_2022g100.geojson'),
        ('Oficiální výsledky – Zastupitelstvo hl. m. Prahy 2026', 'https://volby.gov.cz/app/kv2026/cs/20261009/results/!__1_1100_1100_554782'),
        ('Zákon č. 491/2001 Sb., o volbách do zastupitelstev obcí (§ 40–45, § 60)', 'https://www.zakonyprolidi.cz/cs/2001-491'),
        ('Klimek, Yegorov, Hanel, Thurner (2012): Statistical detection of systematic election irregularities, PNAS 109(41)', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC3478593/'),
        ('Kobak, Shpilkin, Pshenichnikov (2016): Integer percentages as electoral falsification fingerprints, Annals of Applied Statistics', 'https://arxiv.org/abs/1410.6059'),
        ('Mebane (2006): Election Forensics: Vote Counts and Benford’s Law (2BL test)', 'https://public.websites.umich.edu/~wmebane/fraud06.pdf'),
        ('University of Michigan – Election Forensics (eforensics)', 'https://democracy.umich.edu/michigan-expertise/election-forensics-identifying-election-fraud'),
        ('Beber & Scacco (2012): What the Numbers Say: A Digit-Based Test for Election Fraud, Political Analysis', 'https://www.cambridge.org/core/services/aop-cambridge-core/content/view/AD86EEBC2F199E2C8A2FD36BD3799DF9/S1047198700013103a.pdf/what-the-numbers-say-a-digit-based-test-for-election-fraud.pdf'),
        ('Deckert, Myagkov, Ordeshook (2011): Benford’s Law and the Detection of Election Fraud, Political Analysis 19(3) – kritika číslicových testů', 'https://doi.org/10.1093/pan/mpr014'),
        ('Podlazov & Makarov (2025): Statistical study of the transcript of vote counts in multi-member constituencies', 'https://arxiv.org/abs/2509.00118'),
        ('ČT24 (2025): NSS zjistil chyby při sčítání v Blansku – strana s 0 hlasy místo 20', 'https://ct24.ceskatelevize.cz/clanek/domaci/soud-zjistil-chyby-pri-scitani-hlasu-na-blansku-vysledek-neovlivnily-366894'),
        ('E15 (2017): NSS přepočítal preferenční hlasy – nezapočtené kroužky na zadní straně lístku', 'https://www.e15.cz/vysledky-voleb-a-referend/volby-2017/nejvyssi-spravni-soud-prepocital-volebni-hlasy-misto-bendla-zasedne-ve-snemovne-kupka-1339967'),
        ('Kudrnáč, Lysek, Rejman (2014): Omyl, nebo úmysl? Analýza neplatných hlasů v Olomouckém kraji', 'https://journals.muni.cz/cepsr/article/view/4497'),
    ]
    body = '''<h1>Metodika, zdroje a omezení</h1>
<h2>1. Data</h2><p>Byla stažena kompletní okrsková data ČSÚ (věty T/3 – voliči, obálky, platné lístky, hlasy; věty HL – hlasy stran a všech kandidátů), registry stran a kandidátů
a číselníky pro komunální volby 2018, 2022 a 2026; dále všech 165 průběžných XML dávek z volební noci 2026 (časy zpracování, příznak opakovaného zaslání) a hranice okrsků.
Zpracovány jsou všechny obce, v nichž se volilo (seznam okresů a obcí na stránce <a href="kv/index.html">Komunální volby 2026</a>).
U menších obcí s několika okrsky je srovnání se sousedními okrsky slabé a u obcí s jediným okrskem (asi 4 900 obcí) nemožné; nálezy se tam opírají o vnitřní logiku zápisu
(aritmetika, součty stran a kandidátů, překlepy u kandidátů), nezávislý přepočet mandátů a rok 2022. Obce s méně než 4 okrsky mají vlastní stránku jen tehdy,
když detektory něco našly; ostatní jsou řádkem v přehledu svého okresu (těsný výsledek a opravy během volební noci uvádí přímo tabulka okresu). Praha: 1 120 okrsků, Zastupitelstvo hl. m. Prahy (65 mandátů)
a 57 zastupitelstev MČ; registr pražských nálezů byl jednotlivě ověřen v datech. U ostatních měst počítají stejné detektory a registr nálezů sestavuje šablona
(<code>findings_auto.py</code>); kontrola jednotlivých nálezů v datech (prováděná AI modelem podle zadání <code>review/ZADANI.md</code>) se zapisuje do souborů <code>review/&lt;obec&gt;.json</code> a stav kontroly je uveden u každého nálezu. Metodika senátních voleb je popsána na <a href="senat/index.html#metodika">stránce Senátu</a>.</p>
<h2>2. Deterministické kontroly integrity</h2><ul class="l">
<li>Aritmetika zápisu: vydané ≤ zapsaní voliči, odevzdané ≤ vydané obálky, platné lístky ≤ odevzdané, hlasy ≤ platné lístky × mandáty, součty stran a kandidátů, kandidát ≤ počet platných lístků, strana ≤ fyzické maximum.</li>
<li>Shoda údajů o obálkách mezi magistrátním a místním lístkem (jedna obálka).</li>
<li>Reprodukce oficiálních výsledků ze součtu okrsků; nezávislý přepočet mandátů podle § 45 (5% klauzule s přepočtem u neúplných kandidátek, d’Hondtova metoda, posun kandidátů s ≥ 110 % průměru hlasů strany).</li>
<li>Porovnání první a poslední verze každého okrsku v XML dávkách s finálními daty.</li></ul>
<p>Odkazy „Ověřit na volby.gov.cz“ vedou do oficiální aplikace ČSÚ – pro magistrát ve tvaru <code>results/!__1_1100_1100_554782___&lt;okrsek&gt;_&lt;strana&gt;</code>, pro zastupitelstvo MČ <code>results/!__0_1100_1100_&lt;kód MČ&gt;___&lt;okrsek&gt;_&lt;strana&gt;</code> – a na strojová data okrsku <code>/appdata/kv2026/20261009/vysled/okrsek/1100/&lt;kód zastupitelstva&gt;_&lt;okrsek&gt;.json</code>.</p>
<h2>3. Detektory chyb na úrovni okrsku</h2><ul class="l">
<li><strong>Prostorový model:</strong> pro každý okrsek a stranu očekávaný podíl z 8 nejbližších okrsků téhož zastupitelstva (centroidy hranic); reziduum normované binomickou chybou na počet platných lístků a robustně škálované (MAD) kvůli overdisperzi.</li>
<li><strong>Křížová kontrola lístků:</strong> poměr podílu téže strany na magistrátním a místním lístku v rámci MČ – chyba se projeví jen na jednom lístku, skutečné místní preference na obou.</li>
<li><strong>Využití hlasů na lístek</strong> (hlasy / (platné lístky × mandáty)) vůči sousedům – odhalí hlasy platných lístků, které nebyly zapsány.</li>
<li><strong>Chybějící balík lístků strany:</strong> medián hlasů kandidátů strany ≈ počet lístků s křížkem u strany; silný nález vyžaduje shodu deficitu strany a deficitu okrsku (dvě nezávislé linie důkazů).</li>
<li><strong>Nulové hlasy</strong> strany při vysokém očekávání (vzor z případu NSS Blansko 2025), Poissonova pravděpodobnost s korekcí na overdisperzi.</li>
<li><strong>Překlepy u kandidátů:</strong> hodnota se výrazně liší od sousedů na listině a jedna vložená/vypuštěná číslice ji vrací na jejich úroveň; <strong>propady</strong> uprostřed listiny jsou logicky nemožné, protože každý lístek s křížkem u strany přiděluje hlas všem kandidátům v pořadí do počtu mandátů (§ 40 odst. 2).</li>
<li><strong>Prohozené strany</strong> (záměna hlasů dvou stran, která zlepší shodu s okolím o Δχ² &gt; 25; jen v obcích s alespoň 10 okrsky – v menších obcích tvoří okolí jiné místní části, kde mají místní kandidátky jiné voliče), duplicitní vektory hlasů, preferenční výkyvy kandidátů, neplatné hlasy, rozdíl obálek, změna účasti oproti 2022.</li></ul>
<h2>4. Globální testy</h2><p>Klimkův otisk (účast × podíl), celá procenta (Kobak et al.), test poslední číslice (Beber & Scacco) včetně korekce na strukturu komunálních voleb, 2BL (Mebane), rozdělení účasti. Vše srovnáno s lety 2018 a 2022.</p>
<h2>5. Materialita</h2><p>Každá detekovaná chyba byla „opravena“ na nejpravděpodobnější hodnotu (konzervativní i horní varianta) a pro dotčené zastupitelstvo byl znovu spočítán počet mandátů stran i pořadí zvolených kandidátů; vyhodnocena je změna oproti oficiálnímu výsledku. Navíc je pro každé zastupitelstvo spočítána nejmenší změna hlasů, která by mandáty změnila.</p>
<h2>6. Škála jistoty a úmyslu</h2><p><strong>Jistota chyby</strong> vyjadřuje pravděpodobnost, že zveřejněný údaj neodpovídá skutečně odevzdaným hlasům. Je odvozena z počtu nezávislých linií důkazů, extrémnosti (z-skóre, p-hodnoty po korekci na overdisperzi) a z logických omezení volebního systému.
<strong>Indikace úmyslu</strong> se opírá o vzorec chyby (překlep vs. cílené přičtení), o směr chyb napříč stranami a o srovnání s předchozími volbami. Statistika sama úmysl prokázat nemůže.</p>
<h2>7. Omezení</h2><ul class="l">
<li>Bez přístupu k originálním zápisům a lístkům nelze žádnou chybu potvrdit definitivně; nálezy jsou podnětem k ověření.</li>
<li>Drobné chyby (±1–5 hlasů) a sofistikovaná manipulace, která zachová místní vzorce, jsou statisticky nedetekovatelné – proto je u těsných výsledků doporučen přepočet.</li>
<li>Hranice okrsků 2026 nebyly zveřejněny jako soubor; použity hranice 2022 (3 nové okrsky dostaly sousedy podle čísla).</li>
<li>Data z let 2018 a 2022 neobsahují počet platných lístků; pro srovnání byl nahrazen počtem odevzdaných obálek.</li>
<li>Skutečné místní preference (bydliště kandidáta, sídliště vs. vilová čtvrť) mohou vytvářet odlehlé hodnoty – proto jsou za silné považovány jen nálezy s dvojí oporou nebo logickým rozporem.</li></ul>
<h2>8. Reprodukovatelnost</h2><p>Celý výpočet je ve skriptech <code>scripts/</code> (Python 3.13, pandas, scipy): <code>etl.py</code> → <code>integrity.py</code> → <code>seats.py</code> → <code>anomalies.py</code> → <code>missing.py</code> → <code>stacks.py</code> → <code>typos.py</code> → <code>batches.py</code> → <code>fingerprints.py</code> → <code>materiality.py</code> → <code>findings.py</code> → <code>build_site.py</code>.</p>
<h2>9. Autor</h2><p><a href="https://www.facebook.com/martinsuchan85">Martin Suchan</a></p>
<h2>10. Zdroje</h2><ol class="l">''' + ''.join(f'<li><a href="{u}">{E(t)}</a></li>' for t, u in src) + '</ol>'
    _page('metodika.html', 'Metodika a zdroje', body, 'Metodika forenzní analýzy, omezení a zdroje', section='metodika',
          crumbs=[('Přehled', 'index.html'), ('Metodika', None)])


def page_data(extra=()):
    files = []
    F.to_csv(os.path.join(OUT, 'data/nalezy_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('nalezy_2026.csv', 'Registr nálezů s jistotou a dopadem'))
    pd.read_pickle(f'{RES}/typos_2026.pkl').to_csv(os.path.join(OUT, 'data/preklepy_kandidati_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('preklepy_kandidati_2026.csv', 'Překlepy a propady u hlasů kandidátů'))
    pd.read_pickle(f'{RES}/stacks_2026.pkl').to_csv(os.path.join(OUT, 'data/chybejici_baliky_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('chybejici_baliky_2026.csv', 'Kandidáti na chybějící balíky lístků (vč. slabých)'))
    pd.read_pickle(f'{RES}/missing_2026.pkl').to_csv(os.path.join(OUT, 'data/vyuziti_hlasu_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('vyuziti_hlasu_2026.csv', 'Využití hlasů na lístek pro všechny okrsky a zastupitelstva'))
    seats.to_csv(os.path.join(OUT, 'data/mandaty_prepocet_2018_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('mandaty_prepocet_2018_2026.csv', 'Nezávislý přepočet mandátů a rezervy'))
    mat.drop(columns=[]).to_csv(os.path.join(OUT, 'data/materialita_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('materialita_2026.csv', 'Simulace oprav a dopad na mandáty'))
    pd.read_pickle(f'{RES}/precinct_2026.pkl').to_csv(os.path.join(OUT, 'data/okrsky_metriky_2026.csv'), encoding='utf-8-sig'); files.append(('okrsky_metriky_2026.csv', 'Metriky okrsků (účast, neplatné, obálky, z-skóre)'))
    b = pd.read_pickle(f'{RES}/batches_2026.pkl'); b.to_csv(os.path.join(OUT, 'data/xml_davky_praha_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('xml_davky_praha_2026.csv', 'Pražské záznamy z XML dávek volební noci'))
    pd.read_csv(f'{RES}/integrity.csv').to_csv(os.path.join(OUT, 'data/integrita_2018_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('integrita_2018_2026.csv', 'Výsledky deterministických kontrol'))
    files += list(extra)
    rows = []
    for u in UL:
        sm = summ_of(u) if u['kod'] != MAGISTRAT else None
        rows.append(dict(kod=u['kod'], obec=u['nazev'], okres=u['okres_nazev'], kraj=u['kraj'], typ=u['typ'], okrsku=u['okrsku'], volicu=u['volicu'],
                         ucast=round(u['ucast'], 4) if u['ucast'] is not None else None, mandatu=u['mandatu'], volby_konany=u['volby'],
                         zpracovano=sm is not None or u['kod'] == MAGISTRAT, vlastni_stranka=u['stranka'], kandidatek=sm.get('kandidatek') if sm else None,
                         nalezu=sm['nal'] if sm else None, nalezu_s_dopadem=sm['nal_vysl'] if sm else None, rozhodujici_rezerva_obec=sm.get('rez_obec') if sm else None,
                         tesny_vysledek='tight' in klice(sm), opravy_v_noci='batches' in klice(sm), prepocet_mandatu_souhlasi=sm.get('rep_ok') if sm else None,
                         rozhodl_los=bool(sm.get('los')) if sm else None,
                         url=u['url']))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, 'data/obce_prehled_2026.csv'), index=False, encoding='utf-8-sig')
    files.append(('obce_prehled_2026.csv', 'Všechny obce: okrsky, voliči, nálezy, rozhodující rezerva zastupitelstva obce, těsný výsledek, opravy během volební noci'))
    for u in UL:
        s = summ_of(u) if u['kod'] != MAGISTRAT and u['stav'] == 'hotovo' else None
        files += [tuple(x) for x in (s['files'] if s else [])]
    body = '<h1>Data ke stažení</h1><p class="lead">Mezivýsledky analýzy ve formátu CSV (UTF-8). Zdrojová data jsou volně dostupná na volby.gov.cz (viz <a href="metodika.html">Metodika</a>); celý výpočet lze zopakovat skripty v repozitáři.</p><div class="card tw"><table><thead><tr><th>Soubor</th><th>Obsah</th></tr></thead><tbody>'
    body += ''.join(f'<tr><td><a href="data/{f}">{f}</a></td><td>{E(t)}</td></tr>' for f, t in files) + '</tbody></table></div>'
    _page('data.html', 'Data ke stažení', body, 'CSV výstupy forenzní analýzy', section='data', crumbs=[('Přehled', 'index.html'), ('Data', None)])


def n0(v):
    return f'{int(round(v)):,}'.replace(',', ' ')


def mc_sortkey(name):
    import re
    m = re.match(r'Praha (\d+)$', name)
    return (0, int(m.group(1)), '') if m else (1, 0, name)


def mc_table():
    """Tabulka zastupitelstev MČ s kotvami (cíl vyhledávání) – přehled, kam se podívat dál."""
    T = pd.read_pickle(f'{RES}/typos_2026.pkl')
    rows = ''
    for m in sorted(PHA['mc'], key=lambda m: mc_sortkey(m['nazev'])):
        zk = m['kod'] * 100 + 1
        short = m['nazev'].replace('Praha-', '')
        nf = F[F.ZK.astype(int) == zk]
        nf = nf[~nf.typ.str.startswith('Překlepy')]
        ft = F[F.typ.str.startswith('Výsledek těsnější') & F.MC.astype(str).str.split(', ').apply(lambda l: short in l or m['nazev'] in l)]
        ids = list(nf.id) + list(ft.id)
        nt = int((T.ZK == zk).sum())
        krit = fr.krit.get(zk)
        rows += (f'<tr id="mc-{m["kod"]}"><td data-v="{E(m["nazev"])}"><a href="{vg_url(m["kod"])}" target="_blank" rel="noopener">{E(m["nazev"])}</a></td>'
                 f'<td class="num">{m["mandatu"]}</td><td class="num">{m["okrsku"]}</td><td class="num" data-v="{m["volicu"]}">{n0(m["volicu"])}</td>'
                 f'<td data-v="{len(ids)}">' + ', '.join(f'<a href="nalezy.html#{i}">{i}</a>' for i in ids) + '</td>'
                 f'<td class="num">{nt}</td><td class="num" data-v="{krit if krit is not None else 1e9}">{n0(krit) if krit is not None else "–"}</td></tr>')
    return ('<h2 id="mc">Zastupitelstva městských částí</h2><p class="sub">Název vede na výsledky MČ na volby.gov.cz. Rozhodující rezerva = nejmenší počet hlasů, '
            'který by změnil rozdělení mandátů nebo vedl k rovnosti rozhodované losem. Řadit lze kliknutím na záhlaví sloupce.</p>'
            + filters('t-mc', []) +
            '<div class="card tw"><table id="t-mc" class="sortable"><thead><tr><th>Městská část</th><th class="num">Mandátů</th><th class="num">Okrsků</th><th class="num">Voličů</th>'
            '<th>Nálezy</th><th class="num">Překlepy u kandidátů</th><th class="num">Rozhodující rezerva (hlasů)</th></tr></thead><tbody>' + rows + '</tbody></table></div>')


def all_findings(SF):
    out = []
    for r in F.itertuples():
        if str(r.OID).count('/') == 1:
            misto = f'{r.zastupitelstvo} · okrsek {r.OID.split("/")[1]}'
        else:  # souhrnný nález za více okrsků / zastupitelstev
            zast = {'MČ': 'zastupitelstva MČ', 'magistrát i MČ': 'magistrát i zastupitelstva MČ'}.get(r.zastupitelstvo, r.zastupitelstvo)
            misto = f'Praha – {zast}' + (f' ({r.MC})' if str(r.MC) not in ('', 'nan', 'více MČ') else ', více MČ')
        out.append(dict(gid=f'Praha {r.id}', volby='kv', uzemi='Praha', misto=misto, typ=r.typ, subjekt=str(r.subjekt), jistota=int(r.jistota),
                        dopad=r.dopad_kat, url=f'{PD}nalezy.html#{r.id}', kraj=PHA['kraj'], obec='krajske'))
    for u in UL:
        s = summ_of(u) if u['kod'] != MAGISTRAT and u['stav'] == 'hotovo' and u['stranka'] else None
        for f in (s['findings'] if s else []):
            misto = f['zastupitelstvo'] + (f' · okrsek {f["OID"].split("/")[1]}' if f['OID'].count('/') == 1 else f' ({f["MC"]})'[:140])
            out.append(dict(gid=f'{u["nazev"]} {f["id"]}', volby='kv', uzemi=u['nazev'], misto=f'{u["nazev"]} – {misto}', typ=f['typ'],
                            subjekt=f['subjekt'] + (' · automatický nález, zatím neověřen' if f['stav'] != 'zkontrolováno' else ''),
                            jistota=int(f['jistota']), dopad=f['dopad_kat'], url=f'kv/{u["slug"]}/nalezy.html#{f["id"]}', kraj=u['kraj'], obec=u['typ']))
    for f in SF:
        out.append(dict(gid=f'Senát {f["id"]}', volby='senat', uzemi='Senát 2026', misto=f['misto'], typ=f['typ'], subjekt='', jistota=int(f['jistota']),
                        dopad=f['dopad'], url=f'senat/index.html#{f["id"]}', kraj='', obec=''))
    out.sort(key=lambda d: (-DOPAD_RANK.get(d['dopad'], 1), -d['jistota']))
    return out


def findings_rows(AF, frm):
    return ''.join(
        f'<tr data-volby="{d["volby"]}" data-uzemi="{E(d["uzemi"])}" data-kraj="{E(d["kraj"])}" data-obec="{d["obec"]}" data-jistota="{d["jistota"]}" data-dopad="{DOPAD_RANK.get(d["dopad"], 1)}">'
        f'<td class="id" data-v="{E(d["gid"])}"><a href="{link(frm, d["url"])}">{E(d["gid"])}</a></td><td>{E(d["misto"])}</td>'
        f'<td>{E(d["typ"])}' + (f'<br><span class="sub">{E(d["subjekt"])}</span>' if d['subjekt'] else '') + '</td>'
        f'<td data-v="{d["jistota"]}">{badge_j(d["jistota"])}</td><td data-v="{DOPAD_RANK.get(d["dopad"], 1)}">{badge_d(d["dopad"])}</td></tr>' for d in AF)


FIND_HEAD = '<thead><tr><th>ID</th><th>Místo</th><th>Typ a subjekt</th><th>Jistota chyby</th><th>Dopad</th></tr></thead>'


def page_all_findings(AF):
    body = ('<h1>Všechny nálezy</h1><p class="lead">Společný registr nálezů ze všech zpracovaných voleb a území, seřazený podle dopadu a jistoty. '
            'Filtrem lze zúžit výběr; kliknutím na ID otevřete detail s důkazy a odkazy na volby.gov.cz.</p>'
            '<p class="sub">Jistota = pravděpodobnost, že zveřejněný údaj neodpovídá skutečnosti (Jistá – deterministický rozpor; Velmi vysoká ≥ 95 %; Vysoká 80–95 %; '
            'Střední 50–80 %; Nízká &lt; 50 % = riziko, nikoli zjištěná chyba). Dopad = výsledek simulace opravy.</p>')
    body += filters('t-all', [
        ('volby', 'Volby', [('kv', 'Komunální 2026'), ('senat', 'Senát 2026')]),
        ('kraj', 'Kraj', sorted({(d['kraj'], d['kraj']) for d in AF if d['kraj']})),
        ('obec', 'Obec', OBEC_FILTR),
        ('uzemi', 'Území', sorted({(d['uzemi'], d['uzemi']) for d in AF})),
        ('jistota', 'Jistota alespoň', [(5, 'Jistá'), (4, 'Velmi vysoká'), (3, 'Vysoká'), (2, 'Střední')]),
        ('dopad', 'Dopad alespoň', [(3, 'Mění / může změnit výsledek'), (2, 'Těsný výsledek')])])
    body += f'<div class="card tw"><table id="t-all" class="sortable">{FIND_HEAD}<tbody>{findings_rows(AF, "nalezy.html")}</tbody></table></div>'
    _page('nalezy.html', 'Všechny nálezy', body, 'Registr všech nálezů forenzního auditu voleb 2026', section='nalezy',
          crumbs=[('Přehled', 'index.html'), ('Všechny nálezy', None)])


_SUMM = {}


def summ_of(u):
    if u['slug'] not in _SUMM:
        p = os.path.join(ROOT, 'data', 'results', 'kv', u['slug'], 'summary.json')
        _SUMM[u['slug']] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
    return _SUMM[u['slug']]


def norm(t):
    return unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode().lower()


TYPLAB = {'krajske': 'krajské město', 'orp': 'ORP', 'pou': 'POU'}
DRUH1 = {'města': 'město', 'obce': 'obec', 'městyse': 'městys'}
OBEC_FILTR = [('krajske', 'krajská města'), ('orp', 'obce s rozšířenou působností'), ('pou', 'obce s pověřeným obecním úřadem'), ('obec', 'ostatní obce')]


def typ_lab(u):
    return TYPLAB.get(u['typ'], DRUH1[u.get('druh', 'obce')])


def okresy():
    G = {}
    for u in UL:
        G.setdefault(u['okres'], []).append(u)
    return sorted(G.values(), key=lambda g: (g[0]['krajkod'], norm(g[0]['okres_nazev'])))


def klice(s):
    """Klíče nálezů obce (starší souhrny bez klíče: podle typu)."""
    if not s:
        return set()
    return {f.get('klic') or ('tight' if f['typ'].startswith('Výsledek těsnější') else ('batches' if f['typ'].startswith('Opraveno během') else f['id']))
            for f in s['findings']}


def unit_summary(u):
    """Souhrnné ukazatele zpracované jednotky (Praha z ručního registru, ostatní města ze summary.json)."""
    if u['stav'] != 'hotovo':
        return None
    if u['kod'] != MAGISTRAT:
        s = summ_of(u)
        return dict(nal_vysl=s['nal_vysl'], nal=s['nal'], rez=int(s['rez']) if s['rez'] is not None else 0, rez_z=s['rez_z'])
    kr = fr.iloc[0]
    return dict(nal_vysl=int(F.dopad_kat.isin(['Mění mandáty', 'Může změnit mandáty', 'Mění zvolené']).sum()), nal=int(len(F)),
                typos=int(len(pd.read_pickle(f'{RES}/typos_2026.pkl'))), rez=int(kr.krit), rez_z=kr.z)


def page_kv_index():
    rows = ''
    for u in sorted((u for u in UL if u['stranka'] or u['typ'] != 'obec'), key=lambda u: (u['stav'] != 'hotovo', -u['volicu'])):
        s = unit_summary(u) if u['stranka'] else None
        done = s is not None
        name = f'<a href="{link("kv/index.html", u["url"])}">{E(u["nazev"])}</a>' if done else E(u['nazev'])
        st = '<span class="st st-done">zpracováno</span>' if done else '<span class="st st-plan">v přípravě</span>'
        rez_txt = f'{n0(s["rez"])} hl. – {E(s["rez_z"])}' if done else '–'
        rows += (f'<tr id="u-{u["kod"]}" data-kraj="{E(u["kraj"])}" data-stav="{u["stav"]}" data-typ="{u["typ"]}"><td data-v="{E(u["nazev"])}">{name}'
                 f' <span class="sub">{typ_lab(u)}</span></td><td><a href="{link("kv/index.html", okres_url(u))}">{E(u["okres_nazev"])}</a></td>'
                 f'<td class="num">{len(u["mc"])}</td><td class="num" data-v="{u["okrsku"]}">{n0(u["okrsku"])}</td><td class="num" data-v="{u["volicu"]}">{n0(u["volicu"])}</td>'
                 f'<td>{st}</td><td class="num" data-v="{s["nal_vysl"] if done else -1}">{s["nal_vysl"] if done else "–"}</td>'
                 f'<td class="num" data-v="{s["nal"] if done else -1}">{s["nal"] if done else "–"}</td>'
                 f'<td data-v="{s["rez"] if done else 1e9}">{rez_txt}</td></tr>')
    orows = ''
    for g in okresy():
        u0 = g[0]; S = [summ_of(u) for u in g]
        orows += (f'<tr data-kraj="{E(u0["kraj"])}"><td data-v="{E(norm(u0["okres_nazev"]))}"><a href="{link("kv/index.html", okres_url(u0))}">{E(okres_label(u0))}</a></td>'
                  f'<td>{E(u0["kraj"])}</td><td class="num">{len(g)}</td><td class="num">{sum(u["stranka"] for u in g)}</td>'
                  f'<td class="num">{sum(s["nal_vysl"] for u, s in zip(g, S) if s and u["stranka"])}</td><td class="num">{sum("tight" in klice(s) for s in S)}</td></tr>')
    obce = [u for u in UL if u['volby']]
    n_done = sum(u['stav'] == 'hotovo' for u in obce)
    n_str = sum(u['stranka'] for u in UL)
    volicu_mil = f'{sum(u["volicu"] for u in UL) / 1e6:.1f}'.replace('.', ',')
    nk = sum(u['typ'] == 'krajske' for u in UL); no = sum(u['typ'] == 'orp' for u in UL); np_ = sum(u['typ'] == 'pou' for u in UL)
    nob = sum(u['typ'] == 'obec' for u in obce)
    sk = f'{nk} krajských měst, {no} dalších obcí s rozšířenou působností (ORP), {np_} dalších obcí s pověřeným obecním úřadem (POU) a {n0(nob)} ostatních obcí'
    stav_txt = (f'Zpracovány jsou všechny obce, v nichž se volilo: {sk}.' if n_done == len(obce) else
                f'Zpracováno {n0(n_done)} z {n0(len(obce))} obcí ({sk}); ostatní připravujeme.')
    bez = [u for u in UL if not u['volby']]
    bez_txt = f' V {len(bez)} obcích se volby nekonaly ({", ".join(E(u["nazev"]) for u in bez)}).' if bez else ''
    body = f'''<h1>Komunální volby 2026</h1>
<p class="lead">Forenzní analýza okrskových dat pro zastupitelstva obcí a jejich městských částí či obvodů. {stav_txt}
Obec nebo městskou část najdete i vyhledáváním v záhlaví.</p>
<div class="tiles">
<div class="tile"><div class="l">Obcí</div><div class="v">{n0(len(obce))}</div><div class="s">{n0(n_str)} s vlastní stránkou, ostatní v přehledu okresu</div></div>
<div class="tile"><div class="l">Okrsků</div><div class="v">{n0(sum(u["okrsku"] for u in UL))}</div><div class="s">ve všech obcích</div></div>
<div class="tile"><div class="l">Městských částí / obvodů</div><div class="v">{sum(len(u["mc"]) for u in UL)}</div><div class="s">s vlastním zastupitelstvem</div></div>
<div class="tile"><div class="l">Voličů</div><div class="v">{volicu_mil} mil.</div><div class="s">v seznamech</div></div>
</div>
<h2 id="okresy">Okresy</h2><p class="sub">Přehled okresu obsahuje všechny jeho obce včetně výsledků kontrol u obcí bez vlastní stránky. Těsné výsledky = zastupitelstva obcí,
kde o mandátu rozhodlo nejvýše 30 hlasů nebo hlasy nejvýše 3 voličů.{bez_txt}</p>'''
    body += filters('t-okresy', [('kraj', 'Kraj', sorted({(u['kraj'], u['kraj']) for u in UL}))])
    body += ('<div class="card tw"><table id="t-okresy" class="sortable"><thead><tr><th>Okres</th><th>Kraj</th><th class="num">Obcí</th><th class="num">S vlastní stránkou</th>'
             f'<th class="num">Nálezy s dopadem</th><th class="num">Těsné výsledky</th></tr></thead><tbody>{orows}</tbody></table></div>')
    body += ('<h2 id="obce">Obce s vlastní stránkou</h2><p class="sub">Krajská města, obce s rozšířenou působností (ORP) a s pověřeným obecním úřadem (POU), obce se 4 a více okrsky '
             'a menší obce, kde detektory něco našly. Nálezy s dopadem = mění nebo mohou změnit mandáty či zvolené kandidáty. Rozhodující rezerva = nejmenší počet hlasů, který by v některém '
             'zastupitelstvu obce změnil rozdělení mandátů nebo vedl k rovnosti rozhodované losem. Řadit lze kliknutím na záhlaví sloupce.</p>')
    body += filters('t-units', [('kraj', 'Kraj', sorted({(u['kraj'], u['kraj']) for u in UL})), ('typ', 'Obec', OBEC_FILTR),
                                ('stav', 'Stav', [('hotovo', 'zpracováno'), ('pripravuje', 'v přípravě')])])
    body += ('<div class="card tw"><table id="t-units" class="sortable"><thead><tr><th>Obec</th><th>Okres</th><th class="num">MČ / MO</th><th class="num">Okrsků</th>'
             '<th class="num">Voličů</th><th>Stav</th><th class="num">Nálezy s dopadem</th><th class="num">Nálezů celkem</th><th>Rozhodující rezerva</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div>')
    body += ('<h2>Jak číst výsledky obce</h2><ul class="l"><li><strong>Přehled</strong> – závěr, registr nálezů obce, těsné výsledky a tabulka městských částí.</li>'
             '<li><strong>Nálezy</strong> – detail každého nálezu s důkazy, mírou jistoty, simulací dopadu a odkazy na volby.gov.cz.</li>'
             '<li><strong>Mapa okrsků</strong> – kde se nálezy nacházejí.</li><li><strong>Forenzní testy</strong> – globální testy celé populace okrsků a srovnání s lety 2018 a 2022.</li>'
             '<li><strong>Přehled okresu</strong> – všechny obce okresu; u menších obcí bez vlastní stránky výsledky kontrol přímo v tabulce.</li></ul>')
    _page('kv/index.html', 'Komunální volby 2026', body, 'Přehled okresů a obcí s forenzní analýzou komunálních voleb 2026', section='kv',
          crumbs=[('Přehled', 'index.html'), ('Komunální volby 2026', None)])


def pct(v):
    return f'{100 * v:.1f} %'.replace('.', ',') if v else '–'


def page_okresy():
    """Přehled okresu: všechny obce; menší obce bez vlastní stránky mají výsledky kontrol přímo v řádku (kotva #o-<kód obce>)."""
    for g in okresy():
        u0 = g[0]; path = okres_url(u0); lab = okres_label(u0)
        rows = ''
        for u in sorted(g, key=lambda u: norm(u['nazev'])):
            sm = summ_of(u) if u['kod'] != MAGISTRAT else None
            k = klice(sm)
            nm = u['nazev'].replace(f' (okres {u["okres_nazev"]})', '').replace(f'okres {u["okres_nazev"]}, ', '')
            vg = f'{VG_APP}!__1_{u["krajkod"]}_{u["okres"]}_{u["kod"]}'
            name = f'<a href="{link(path, u["url"])}">{E(nm)}</a>' if u['stranka'] else E(nm)
            pozn = []
            if not u['volby']:
                pozn.append('volby se nekonaly')
            elif sm is None and u['kod'] != MAGISTRAT:
                pozn.append('zatím nezpracováno')
            if 'tight' in k:
                pozn.append('těsný výsledek')
            if 'batches' in k:
                pozn.append('opraveno během volební noci')
            if sm is not None and sm.get('los'):
                pozn.append('o mandátu rozhodl los (shodný počet hlasů)')
            if sm is not None and sm.get('rep_ok') is False:
                pozn.append('přepočet mandátů se liší od oficiálního')
            if sm is not None and not u['stranka'] and not pozn:
                pozn.append('bez nálezu')
            if u['kod'] == MAGISTRAT:
                nal = f'<a href="{link(path, u["url"])}">registr Prahy</a>'
            elif u['stranka'] and sm is not None:
                nal = f'<a href="{link(path, u["url"].replace("index.html", "nalezy.html"))}">{sm["nal"]}</a>' if sm['nal'] else '0'
                nal += f' <span class="sub">({sm["nal_vysl"]} s dopadem)</span>' if sm['nal_vysl'] else ''
            else:
                nal = '–'
            rz = sm.get('rez_obec') if sm else None
            rz_txt = '–' if rz is None else (f'<strong>{n0(rz)}</strong>' if 'tight' in k else n0(rz))
            rows += (f'<tr id="o-{u["kod"]}" data-typ="{u["typ"]}"><td data-v="{E(norm(nm))}">{name}<br><span class="sub">{typ_lab(u)} · '
                     f'<a href="{vg}" target="_blank" rel="noopener">výsledky na volby.gov.cz</a></span></td>'
                     f'<td class="num">{u["okrsku"]}</td><td class="num" data-v="{u["volicu"]}">{n0(u["volicu"])}</td>'
                     f'<td class="num" data-v="{u["ucast"] or 0}">{pct(u["ucast"])}</td>'
                     f'<td class="num">{u["mandatu"]}</td><td class="num">{sm.get("kandidatek", "–") if sm else "–"}</td><td data-v="{sm["nal"] if sm else -1}">{nal}</td>'
                     f'<td class="num" data-v="{rz if rz is not None else 1e9}">{rz_txt}</td><td>{", ".join(pozn)}</td></tr>')
        S = [summ_of(u) for u in g]
        n_str = sum(u['stranka'] for u in g)
        nv = sum(s['nal_vysl'] for u, s in zip(g, S) if s and u['stranka'])
        nt = sum('tight' in klice(s) for s in S)
        body = f'''<h1>{E(lab)} – komunální volby 2026</h1>
<p class="lead">Všech {len(g)} obcí okresu ({E(u0["kraj"])}). Obce s vlastní stránkou mají odkaz; u ostatních uvádí výsledky kontrol přímo tabulka.</p>
<div class="tiles">
<div class="tile"><div class="l">Obcí</div><div class="v">{len(g)}</div><div class="s">{n_str} s vlastní stránkou</div></div>
<div class="tile"><div class="l">Okrsků</div><div class="v">{n0(sum(u["okrsku"] for u in g))}</div><div class="s">{n0(sum(u["volicu"] for u in g))} voličů</div></div>
<div class="tile"><div class="l">Nálezy s dopadem</div><div class="v">{nv}</div><div class="s">mění / mohou změnit mandáty</div></div>
<div class="tile"><div class="l">Těsné výsledky</div><div class="v">{nt}</div><div class="s">zastupitelstev obcí</div></div>
</div>
<p class="sub">U obcí bez vlastní stránky (méně než 4 okrsky a žádný nález) jsme ověřili aritmetiku zápisů, součty hlasů stran a kandidátů proti oficiálním výsledkům,
nezávislý přepočet mandátů, překlepy u kandidátů a opakovaně zaslané okrsky z volební noci; srovnání se sousedními okrsky u obce s jediným okrskem možné není.
Rozhodující rezerva = nejmenší počet hlasů, který by v zastupitelstvu obce změnil rozdělení mandátů nebo vedl k rovnosti rozhodované losem; <strong>tučně</strong> těsné výsledky
(nejvýše 30 hlasů nebo hlasy nejvýše 3 voličů – každý volič má tolik hlasů, kolik je mandátů). Řadit lze kliknutím na záhlaví sloupce.</p>'''
        body += filters('t-obce', [('typ', 'Obec', OBEC_FILTR)])
        body += ('<div class="card tw"><table id="t-obce" class="sortable"><thead><tr><th>Obec</th><th class="num">Okrsků</th><th class="num">Voličů</th><th class="num">Účast</th>'
                 '<th class="num">Mandátů</th><th class="num">Kandidátek</th><th>Nálezy</th><th class="num">Rozhodující rezerva (hlasů)</th><th>Poznámka</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div>')
        _page(path, f'{lab} – komunální volby 2026', body, f'Forenzní audit komunálních voleb 2026 – všechny obce: {lab}', section='kv',
              crumbs=[('Přehled', 'index.html'), ('Komunální volby 2026', 'kv/index.html'), (lab, None)])


def page_home(AF):
    # na úvodní stránce: vše, co mění nebo může změnit výsledek; těsné výsledky jen pro Prahu, krajská města a Senát (ORP v registru)
    top = [d for d in AF if DOPAD_RANK.get(d['dopad'], 1) >= 3 or (DOPAD_RANK.get(d['dopad'], 1) == 2 and d['obec'] not in ('orp', 'pou', 'obec'))]
    n_done = sum(u['stav'] == 'hotovo' for u in UL)
    nk_done = sum(u['stav'] == 'hotovo' and u['typ'] == 'krajske' for u in UL)
    no_done = sum(u['stav'] == 'hotovo' and u['typ'] == 'orp' for u in UL)
    np_done = sum(u['stav'] == 'hotovo' and u['typ'] == 'pou' for u in UL)
    nob_done = sum(u['stav'] == 'hotovo' and u['typ'] == 'obec' for u in UL)
    nob_str = sum(u['stav'] == 'hotovo' and u['typ'] == 'obec' and u['stranka'] for u in UL)
    other_txt = ''
    for grp, lab, n in (('krajske', 'Ostatní krajská města', nk_done - 1), ('orp', 'Obce s rozšířenou působností', no_done),
                        ('pou', 'Obce s pověřeným obecním úřadem', np_done), ('obec', 'Ostatní obce s vlastní stránkou', nob_str)):
        oth = [d for d in AF if d['volby'] == 'kv' and d['uzemi'] != 'Praha' and d['obec'] == grp]
        if not oth:
            continue
        ov = [d for d in oth if DOPAD_RANK.get(d['dopad'], 1) >= 3]
        n_ok = sum(1 for d in oth if 'zatím neověřen' not in d['subjekt'])
        other_txt += (f'<p><strong>{lab}</strong> ({n}): {len(oth)} nálezů, z toho {len(ov)} s vlivem nebo možným vlivem na výsledek'
                      + (': ' + '; '.join(f'<a href="{d["url"]}">{E(d["gid"])}</a> {E(d["typ"].lower())} ({E(d["dopad"].lower())})' for d in ov) if ov and len(ov) <= 12 else
                         (' (viz tabulka níže)' if ov else ''))
                      + f'. Registry těchto obcí sestavuje šablona; jednotlivě v datech ověřeno (AI kontrolou) {n_ok} z {len(oth)} nálezů.</p>')
    body = f'''<h1>Forenzní audit voleb 2026</h1>
<p class="lead">Nezávislá analýza okrskových dat ČSÚ z voleb 9.–10. 10. 2026: komunální volby v {n0(n_done)} obcích ({nk_done} krajských městech,
{no_done} dalších obcích s rozšířenou působností, {np_done} dalších obcích s pověřeným obecním úřadem a {n0(nob_done)} ostatních obcích) a 1. kolo senátních voleb ve 27 obvodech. Hledáme chyby v zápisech okrskových komisí a známky manipulace a posuzujeme, zda mohly změnit výsledek.</p>
<form class="searchbig" role="search" onsubmit="return false"><label class="vh" for="q-home">Najít obec, městskou část nebo senátní obvod</label>
<input id="q-home" type="search" data-search placeholder="Najděte obec, městskou část nebo senátní obvod…" autocomplete="off" enterkeyhint="search"></form>
<div class="verdict"><p><strong>Závěr:</strong> V datech nejsou známky systematické ani koordinované manipulace; výsledky jsou ze součtu okrsků plně reprodukovatelné.
Našli jsme ale konkrétní chyby v zápisech: v <strong>Praze 10</strong> překlep, který mění 2 mandáty, v <strong>Praze 15</strong> chybějící hlasy, které mohou změnit 1 mandát.
V senátním obvodu <strong>Žďár nad Sázavou</strong> rozhodl o postupu do 2. kola jediný hlas.</p>{other_txt}</div>
<div class="hubs">
<a class="hub" href="kv/index.html"><h3>Komunální volby 2026 →</h3><p>Zpracováno {n0(n_done)} obcí ({n0(sum(u["okrsku"] for u in UL if u["stav"] == "hotovo"))} okrsků).
Přehledy okresů a obcí s počty nálezů a rozhodujícími rezervami.</p></a>
<a class="hub" href="senat/index.html"><h3>Senát 2026, 1. kolo →</h3><p>5 021 okrsků ve 27 obvodech, srovnání s komunálními volbami okrsek po okrsku.
Proč bylo senátních obálek o 13 % méně a kde rozhodly jednotky hlasů.</p></a>
<a class="hub" href="nalezy.html"><h3>Všechny nálezy →</h3><p>Společný registr {len(AF)} nálezů s filtrem podle voleb, území, jistoty a dopadu.</p></a>
</div>
<h2>Nálezy, které mění nebo mohou změnit výsledek, a těsné výsledky</h2>
<p class="sub">Těsné výsledky v obcích s rozšířenou působností, s pověřeným obecním úřadem a v ostatních obcích jsou v <a href="nalezy.html">registru všech nálezů</a> (filtr Dopad)
a v <a href="kv/index.html#okresy">přehledech okresů</a>.</p>
<div class="card tw"><table class="sortable">{FIND_HEAD}<tbody>{findings_rows(top, "index.html")}</tbody></table></div>
<p class="sub"><a href="nalezy.html">Zobrazit všech {len(AF)} nálezů →</a></p>
<h2>O analýze</h2><ul class="l">
<li>Zdrojem jsou výhradně otevřená data ČSÚ (volby.gov.cz); každý nález má odkaz na výsledky okrsku v oficiální aplikaci.</li>
<li>Postupy, omezení a literaturu popisuje <a href="metodika.html">Metodika</a>; mezivýsledky jsou v sekci <a href="data.html">Data</a>, výpočet lze zopakovat skripty v repozitáři.</li>
<li>Analýza vznikla s pomocí AI modelu Claude Opus 5.5 a může obsahovat chyby. Statistický nález není důkazem úmyslu; závazné jsou jen výsledky vyhlášené Státní volební komisí.</li></ul>'''
    _page('index.html', 'Přehled', body, 'Forenzní audit komunálních a senátních voleb 2026 z otevřených dat ČSÚ', section='home')


def search_entries(AF, se_obvody):
    S = []
    for u in UL:
        S.append((f'{u.get("nazev_plny", u["nazev"])} – komunální volby' + ('' if u['stav'] == 'hotovo' or not u['volby'] else ' (v přípravě)')
                  + ('' if u['volby'] else ' (nekonaly se)'), u['url']))
    for g in okresy():
        S.append((f'{okres_label(g[0])} – přehled obcí', okres_url(g[0])))
    for u in UL:
        for m in u['mc']:
            if u['stav'] == 'hotovo' and u['stranka']:
                S.append((f'{m["nazev"]} – městská část ({u["nazev"]})', f'{u["url"].rsplit("/", 1)[0]}/index.html#mc-{m["kod"]}'))
            else:
                S.append((f'{m["nazev"]} – městská část/obvod ({u["nazev"]}, v přípravě)', u['url']))
    for o, nm in se_obvody:
        S.append((f'Senát – obvod {o} {nm}', f'senat/index.html#obvod-{o}'))
    for d in AF:
        S.append((f'{d["gid"]} – {d["typ"]} ({d["misto"]})', d['url']))
    S += [('Všechny nálezy', 'nalezy.html'), ('Metodika a zdroje', 'metodika.html'), ('Data ke stažení', 'data.html')]
    return S


fig_years = chart_years(); fig_margins = chart_margins(); fig_intent = chart_intent()
import build_senat
se_files = build_senat.build(_page, fig, badge_j, badge_d, AUTHOR_URL)
AF = all_findings(build_senat.findings())
page_index(); page_findings(); page_map(); page_tests(); page_method(); page_data(se_files)
page_kv_index(); page_okresy(); page_all_findings(AF); page_home(AF)
write_assets(search_entries(AF, [(int(o), n) for o, n in build_senat.obvn.items() if o in set(build_senat.t5.OBVOD)]))
for old in ('mapa.html', 'testy.html', 'senat.html'):  # stránky z původní (jen pražské) struktury
    if os.path.exists(os.path.join(OUT, old)):
        os.remove(os.path.join(OUT, old))
print('site built in', OUT, os.listdir(OUT))
