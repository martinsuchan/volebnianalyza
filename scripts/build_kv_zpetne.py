"""Zpětná analýza komunálních voleb 2018 a 2022 (listopad 2026): souhrnná stránka report/kv<rok>/index.html a stránka nálezů za každý kraj.

Nálezy vznikají stejnou pipeline jako pro rok 2026 (AUDIT_YEAR=<rok>: u roku 2018 navíc anomalies_rok.py, pak materiality.py a findings_auto.py
včetně pravidel řady M) a leží v data/results/kv/<slug>/findings_<rok>.json; kontrola nálezů s vlivem na výsledek je v review/<rok>/<slug>.json
a <slug>_m.json. Srovnání se soudy: soudy/podani_<rok>.csv (scripts/soudy_historie.py) a opravené záznamy ČSÚ (pozdější DATUMVOLEB).
Spuštění: python scripts/build_kv_zpetne.py [2022|2018] (bez argumentu oba roky; volá ho i build_site.py)."""
import csv, json, os, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pandas as pd
from common import ROOT, RES0, P0, MAIN_DATE
from sablona import page, fig, badge_j, badge_d, filters, link, DOPAD_RANK
from svg import E, hbars, table as svg_table, legend
import units

D, ROK, T = 'kv2022', 2022, {}  # nastaví build(rok)
UL = []
MAT = ('Mění mandáty', 'Mění zvolené', 'Může změnit mandáty')
n0 = lambda v: f'{int(round(v)):,}'.replace(',', ' ')
TYP_SKUP = [  # (popisek, test na typ nálezu)
    ('Překlep u kandidáta (vložená / vypadlá číslice)', lambda t: t.startswith('Překlep')),
    ('Propad kandidáta pod lístky s křížkem u strany', lambda t: t.startswith('Propad hlasů kandidáta')),
    ('Posunutý úsek nebo rozptýlené nuly v kandidátce', lambda t: t.startswith('Posunutý úsek') or t.startswith('Rozptýlené nuly')),
    ('Neúplně opsaný řádek kandidátů', lambda t: t.startswith('Neúplně opsaný')),
    ('Chybějící balík lístků strany / nulová strana', lambda t: t.startswith('Chybějící balík') or t.startswith('Nulové hlasy') or t.startswith('Nezapsaná strana')),
    ('Nezapsané hlasy části lístků (okrsek jako celek)', lambda t: t.startswith('Nezapsané hlasy')),
    ('Možná záměna hlasů dvou stran', lambda t: t.startswith('Možná záměna')),
    ('Aritmetický rozpor v zápisu', lambda t: t.startswith('Odevzdáno více') or 'rozpor' in t.lower()),
    ('Těsný výsledek', lambda t: t.startswith('Výsledek těsnější') or t.startswith('Kritické hodnoty')),
]


def vg():
    return f'https://volby.gov.cz/pls/kv{ROK}/kv?xjazyk=CZ&xid=1'


def od():
    return f'https://www.volby.cz/opendata/kv{ROK}/kv{ROK}_opendata.htm'


def skupina(t):
    return next((lab for lab, f in TYP_SKUP if f(t)), 'Ostatní')


def nacti(rok):
    """Všechny nálezy roku `rok` ze všech jednotek s údaji o obci (kraj, okres, odkaz na stránku obce 2026)."""
    out = []
    for u in UL:
        p = os.path.join(RES0, 'kv', u['slug'], f'findings_{rok}.json')
        if not os.path.exists(p):
            continue
        for f in json.load(open(p, encoding='utf-8')):
            f = dict(f)
            f.update(slug=u['slug'], obec=u['nazev'], kraj=u['kraj'], okres=u.get('okres_nazev') or '', utyp=u['typ'], u=u,
                     gid=f"{u['slug']}-{f['id']}", skup=skupina(str(f['typ'])), jistota=int(f['jistota']))
            out.append(f)
    return out


def misto(f):
    o = str(f.get('OID') or '')
    z = str(f.get('zastupitelstvo') or '')
    if o.count('/') == 1:
        return f'{z} · okrsek {o.split("/")[1]}'
    return z + (f' ({f["MC"]})' if f.get('MC') and str(f['MC']) not in ('nan', '') and len(str(f['MC'])) < 80 else '')


def kraj_url(k):
    return f'{D}/{units.slug(k)}.html'


def obec_odkaz(frm, f):
    u = f['u']
    return f'<a href="{link(frm, u["url"])}" title="Stránka obce – analýza 2026">{E(f["obec"])}</a>'


def karta(frm, f):
    kon = f.get('kontrola') or ''
    return (f'<article class="card find p{1 if f["dopad_kat"] in MAT else 3}" id="{E(f["gid"])}"><h3>{E(f["obec"])} {E(f["id"])} · {E(f["typ"])}</h3>'
            f'<p class="sub">{obec_odkaz(frm, f)} · {E(misto(f))} · {E(f["okres"])}</p>'
            f'<div style="margin-top:8px">{badge_j(f["jistota"])} {badge_d(f["dopad_kat"])}</div><dl>'
            f'<dt>Subjekt</dt><dd>{E(str(f.get("subjekt") or ""))}</dd>'
            f'<dt>Zjištění</dt><dd>{E(str(f["zjisteni"]))}</dd><dt>Důkaz</dt><dd>{E(str(f.get("dukaz") or ""))}</dd>'
            f'<dt>Dopad</dt><dd>{E(str(f.get("dopad") or ""))}</dd>'
            + (f'<dt>Kontrola v datech (AI)</dt><dd>{E(kon)}</dd>' if kon else '<dt>Kontrola</dt><dd>Automatický nález, jednotlivě neověřen.</dd>')
            + '</dl></article>')


def radky(frm, F):
    return ''.join(
        f'<tr id="{E(f["gid"])}" data-okres="{E(f["okres"])}" data-skup="{E(f["skup"])}" data-jistota="{f["jistota"]}" data-dopad="{DOPAD_RANK.get(f["dopad_kat"], 1)}">'
        f'<td data-v="{E(f["obec"])}">{obec_odkaz(frm, f)}<br><span class="sub">{E(f["id"])}</span></td><td>{E(misto(f))}</td>'
        f'<td>{E(str(f["typ"]))}<br><span class="sub">{E(str(f.get("subjekt") or ""))}</span>'
        f'<details><summary>zjištění</summary><p>{E(str(f["zjisteni"]))}</p><p class="sub">{E(str(f.get("dopad") or ""))}</p>'
        + (f'<p class="sub">Kontrola: {E(str(f["kontrola"]))}</p>' if f.get('kontrola') else '') + '</details></td>'
        f'<td data-v="{f["jistota"]}">{badge_j(f["jistota"])}</td><td data-v="{DOPAD_RANK.get(f["dopad_kat"], 1)}">{badge_d(f["dopad_kat"])}</td></tr>' for f in F)


HEAD = '<thead><tr><th>Obec</th><th>Místo</th><th>Typ, subjekt a zjištění</th><th>Jistota chyby</th><th>Dopad</th></tr></thead>'


def razeni(F):
    return sorted(F, key=lambda f: (-DOPAD_RANK.get(f['dopad_kat'], 1), -f['jistota'], f['obec'], f['id']))


def opravy_csu(slug, mc=''):
    """Okrsky obce (MČ), u nichž ČSÚ po rozhodnutí soudu zveřejnil opravený záznam (stejné obálky, pozdější datum): rozdíly hlasů kandidátů."""
    p = os.path.join(P0, 'kv', slug)
    try:
        t3 = pd.read_pickle(os.path.join(p, f't3_{ROK}.pkl')); hl = pd.read_pickle(os.path.join(p, f'hl_{ROK}.pkl'))
        rz = pd.read_pickle(os.path.join(p, f'rz_{ROK}.pkl'))
    except FileNotFoundError:
        return []
    if mc:  # jen okrsky dané MČ/MO (kód obce MČ = kód jejího zastupitelstva)
        kod = set(rz[(rz.TYPZASTUP == 2) & (rz.NAZEVZAST.astype(str).str.replace('–', '-') == mc.replace('–', '-'))].KODZASTUP)
        t3 = t3[t3.OBEC.isin(kod)]
    m = MAIN_DATE[ROK]; H = [c for c in hl.columns if c.startswith('HLASY_')]
    out = []
    for (ob, ok, ty), g in t3[t3.DATUMVOLEB != m].groupby(['OBEC', 'OKRSEK', 'TYPZASTUP']):
        o = t3[(t3.OBEC == ob) & (t3.OKRSEK == ok) & (t3.TYPZASTUP == ty) & (t3.DATUMVOLEB == m)]
        n = g.iloc[0]
        if not len(o) or any(int(o.iloc[0][c]) != int(n[c]) for c in ('VOL_SEZNAM', 'VYD_OBALKY', 'ODEVZ_OBAL')):
            continue  # nové nebo opakované hlasování, ne oprava zápisu
        a = hl[(hl.OBEC == ob) & (hl.OKRSEK == ok) & (hl.TYPZASTUP == ty) & (hl.DATUMVOLEB == m)].set_index('POR_STR_HL')[H].fillna(0)
        b = hl[(hl.OBEC == ob) & (hl.OKRSEK == ok) & (hl.TYPZASTUP == ty) & (hl.DATUMVOLEB == n.DATUMVOLEB)].set_index('POR_STR_HL')[H].fillna(0)
        ix = a.index.union(b.index)
        zm = int((b.reindex(ix).fillna(0) - a.reindex(ix).fillna(0)).abs().sum().sum())
        out.append(dict(okrsek=int(ok), typ=int(ty), datum=int(n.DATUMVOLEB), hlasy=(int(o.iloc[0].PL_HL_CELK), int(n.PL_HL_CELK)), zmena_hlasu=zm))
    return out


def opravy_text(op):
    if not op:
        return 'bez opravy zápisu (opakované hlasování či volby, nebo se změnili jen zvolení)'
    zm = [o for o in op if o['zmena_hlasu']]
    t = '; '.join(f'okrsek {o["okrsek"]}: platné hlasy {n0(o["hlasy"][0])} → {n0(o["hlasy"][1])}, změna hlasů kandidátů o {n0(o["zmena_hlasu"])}' for o in zm[:4])
    if len(zm) > 4:
        t += f'; další {len(zm) - 4} okrsky se změnou'
    if len(op) > len(zm):
        t += ('; ' if t else '') + f'{len(op) - len(zm)} záznamů okrsků znovu zveřejněno beze změny hlasů'
    return t


def soudy():
    p = os.path.join(ROOT, 'soudy', f'podani_{ROK}.csv')
    return list(csv.DictReader(open(p, encoding='utf-8-sig'))) if os.path.exists(p) else []


def _shoda(c, f):
    """Řízení a nález se týkají stejného zastupitelstva: stejná MČ/MO, nebo řízení o celém městě a nález na lístku města."""
    z = str(f.get('zastupitelstvo') or '')
    if c['mc']:
        return str(f.get('MC') or '') == c['mc'] or c['mc'] in z
    return not (' MČ ' in z or ' MO ' in z)


def vztah(c, FS):
    """Vztah soudního řízení k nálezům roku v téže obci (MČ): přesná = nález ve zmíněném okrsku, obec = nález jinde v obci, žádná."""
    fs = [f for f in FS.get(c['slug'], []) if _shoda(c, f)]
    okr = set(c['okrsky'].split())
    pres = [f for f in fs if str(f.get('OID') or '').count('/') == 1 and f['OID'].split('/')[1] in okr]
    if pres:
        return 'přesná', pres
    if fs:
        return 'obec', fs
    return 'žádná', []


def soudy_nalezu(f, S):
    """Řízení ke stejné obci (u měst s MČ/MO jen ke stejné MČ nebo k celému městu)."""
    return [c for c in S if c['slug'] == f['slug'] and _shoda(c, f)]


def build(rok=None):
    """Stránky zpětné analýzy pro rok `rok` (bez argumentu pro všechny roky v TEXTY)."""
    global UL, D, ROK, T
    if rok is None:
        return [build(r) for r in sorted(TEXTY, reverse=True)]
    D, ROK, T = f'kv{rok}', rok, TEXTY[rok]
    UL = units.units()
    F = nacti(rok)
    F26 = nacti(2026)
    FS = defaultdict(list)
    for f in F:
        FS[f['slug']].append(f)
    kraje = sorted({f['kraj'] for f in F} | {u['kraj'] for u in UL}, key=lambda k: (k != 'Hlavní město Praha', k))
    S = soudy()
    for k in kraje:
        path = kraj_url(k)
        FK = razeni([f for f in F if f['kraj'] == k])
        mat = [f for f in FK if f['dopad_kat'] in MAT]
        tes = [f for f in FK if f['dopad_kat'] == 'Těsný výsledek']
        ost = [f for f in FK if f['dopad_kat'] not in MAT and f['dopad_kat'] != 'Těsný výsledek']
        nob = len({u['slug'] for u in UL if u['kraj'] == k})
        nfo = len({f['slug'] for f in FK if f['dopad_kat'] != 'Těsný výsledek'})
        body = (f'<h1>Komunální volby {ROK} – {E(k)}</h1><p class="lead">Zpětná analýza okrskových výsledků voleb {T["datum"]} stejnými detektory a pravidly jako rok 2026: '
                f'{n0(nob)} obcí, {n0(len(FK))} nálezů v {n0(len({f["slug"] for f in FK}))} obcích (bez těsných výsledků v {n0(nfo)} obcích). '
                f'{len(mat)} nálezů mění nebo může změnit výsledek.</p>'
                '<p class="sub">Jistota = pravděpodobnost, že zveřejněný údaj neodpovídá skutečnosti; dopad = výsledek simulace opravy (přepočet mandátů a pořadí kandidátů). '
                f'Nálezy s vlivem na výsledek jsme jednotlivě zkontrolovali v datech s pomocí AI; ostatní jsou automatické. Data roku {ROK} neobsahují počet platných lístků '
                f'(nahrazen odevzdanými obálkami) a XML dávky z volební noci. Oficiální výsledky: <a href="{vg()}">volby.gov.cz – KV {ROK}</a>. '
                'Odkaz u obce vede na její stránku s analýzou roku 2026.</p>')
        sk = [c for c in S if c['slug'] and any(u['slug'] == c['slug'] and u['kraj'] == k for u in UL)]
        if mat:
            body += '<h2>Nálezy, které mění nebo mohou změnit výsledek</h2>' + ''.join(karta(path, f) for f in mat)
        if sk:
            body += (f'<h2>Soudní řízení v kraji (KV {ROK})</h2><div class="card tw"><table class="sortable"><thead><tr><th>Soud, sp. zn.</th><th>Obec</th><th>Rozhodnutí</th>'
                     f'<th>Přepočet</th><th>Nálezy analýzy {ROK}</th></tr></thead><tbody>')
            for c in sk:
                vz, fs = vztah(c, FS)
                body += (f'<tr><td><a href="{E(c["odkaz"])}">{E(c["soud"])} {E(c["spis"])}</a></td><td>{E(c["obec"])}' + (f' ({E(c["mc"])})' if c['mc'] else '') + '</td>'
                         f'<td>{E(c["rozhodnuti"] or "–")}</td><td>{E(c["prepocet"] or "–")}</td><td>{E(vz)}'
                         + (': ' + ', '.join(f'<a href="#{E(f["gid"])}">{E(f["id"])}</a>' for f in fs[:6]) if fs else '') + '</td></tr>')
            body += '</tbody></table></div>'
        if ost:
            body += ('<h2>Ostatní nálezy</h2>' + filters(f't-{units.slug(k)}', [
                ('okres', 'Okres', sorted({(f['okres'], f['okres']) for f in ost})),
                ('skup', 'Typ', sorted({(f['skup'], f['skup']) for f in ost})),
                ('jistota', 'Jistota alespoň', [(5, 'Jistá'), (4, 'Velmi vysoká'), (3, 'Vysoká'), (2, 'Střední')])])
                + f'<div class="card tw"><table id="t-{units.slug(k)}" class="sortable">{HEAD}<tbody>{radky(path, ost)}</tbody></table></div>')
        if tes:
            body += ('<h2>Těsné výsledky</h2><p class="sub">Zastupitelstva, kde o mandátu nebo 5% hranici rozhodlo jen několik hlasů – drobné chyby sčítání '
                     '(±1–5 hlasů) nejsou v datech statisticky viditelné, ale mohou výsledek změnit (soudní případ Matějov 2022: remíza rozhodnutá losem, přepočet 413 : 412).</p>'
                     + f'<div class="card tw"><table class="sortable">{HEAD}<tbody>{radky(path, tes)}</tbody></table></div>')
        page(path, f'KV {ROK} – {k}', body, f'Nálezy zpětné analýzy komunálních voleb {ROK} – {k}', section='kv',
             crumbs=[('Přehled', 'index.html'), (f'Komunální volby {ROK}', f'{D}/index.html'), (k, None)])
    souhrn(F, F26, FS, kraje, S)
    return F


def souhrn(F, F26, FS, kraje, S):
    path = f'{D}/index.html'
    mat = razeni([f for f in F if f['dopad_kat'] in MAT])
    nob = len({u['slug'] for u in UL if os.path.exists(os.path.join(RES0, 'kv', u['slug'], f'findings_{ROK}.json'))})
    cnt = lambda FF: Counter(f['skup'] for f in FF if f['dopad_kat'] != 'Těsný výsledek')
    c1, c26 = cnt(F), cnt(F26)
    cats = [lab for lab, _ in TYP_SKUP if lab != 'Těsný výsledek' and (c1[lab] or c26[lab])]
    ch = hbars(cats, [(str(ROK), [c1[c] for c in cats]), ('2026', [c26[c] for c in cats])], ['--series-2', '--series-1'], label_w=330)
    tb = svg_table(['Typ nálezu', str(ROK), '2026'], [[c, c1[c], c26[c]] for c in cats])
    m1 = Counter(f['dopad_kat'] for f in F)
    body = (f'<h1>Komunální volby {ROK} – zpětná analýza</h1><p class="lead">Stejné detektory a pravidla jako u voleb 2026 jsme v listopadu 2026 použili na původní okrskové '
            f'výsledky komunálních voleb {T["datum"]} ve všech {n0(nob)} obcích. Výsledkem je {n0(len(F))} nálezů, z toho <strong>{len(mat)} mění nebo může změnit výsledek</strong> '
            f'({m1["Mění mandáty"]} mění mandáty, {m1["Mění zvolené"]} mění zvolené kandidáty, {m1["Může změnit mandáty"]} může změnit mandáty). '
            f'Na závěr analýzu porovnáváme s rozhodnutími soudů o volbách {ROK}.</p>')
    body += souhrn_text(F, S)
    jine = [r for r in sorted(TEXTY) if r != ROK]
    body += ('<p class="sub">Zpětná analýza dalších voleb: ' + ', '.join(f'<a href="{link(path, f"kv{r}/index.html")}">komunální volby {r}</a>' for r in jine)
             + f'; analýza voleb 2026: <a href="{link(path, "kv/index.html")}">komunální volby 2026</a>.</p>')
    body += '<h2>Nálezy podle krajů</h2><div class="hubs">' + ''.join(
        f'<a class="hub" href="{link(path, kraj_url(k))}"><h3>{E(k)} →</h3><p>{sum(1 for f in F if f["kraj"] == k)} nálezů, '
        f'{sum(1 for f in F if f["kraj"] == k and f["dopad_kat"] in MAT)} s vlivem na výsledek.</p></a>' for k in kraje) + '</div>'
    body += ('<h2>Nálezy, které mění nebo mohou změnit výsledek</h2><p class="sub">Seřazeno podle dopadu a jistoty; detail s důkazy je na stránce kraje.</p>'
             f'<div class="card tw"><table class="sortable"><thead><tr><th>Obec</th><th>Místo</th><th>Typ a subjekt</th><th>Jistota chyby</th><th>Dopad</th><th>Soud {ROK}</th></tr></thead><tbody>')
    for f in mat:
        cs = soudy_nalezu(f, S)
        body += (f'<tr><td>{obec_odkaz(path, f)}<br><span class="sub">{E(f["kraj"])}</span></td><td>{E(misto(f))}</td>'
                 f'<td><a href="{link(path, kraj_url(f["kraj"]))}#{E(f["gid"])}">{E(f["id"])}</a> {E(str(f["typ"]))}<br><span class="sub">{E(str(f.get("subjekt") or ""))}</span></td>'
                 f'<td data-v="{f["jistota"]}">{badge_j(f["jistota"])}</td><td data-v="{DOPAD_RANK.get(f["dopad_kat"], 1)}">{badge_d(f["dopad_kat"])}</td>'
                 f'<td>{"; ".join(E(c["spis"] + " – " + (c["rozhodnuti"] or "?")) for c in cs) or "bez návrhu"}</td></tr>')
    body += '</tbody></table></div>'
    body += fig('Stejné detektory, dvoje volby: počty nálezů podle typu', f'Všechny obce, komunální volby {ROK} a 2026 (bez těsných výsledků)', ch,
                legend([(str(ROK), '--series-2', 'rect'), ('2026', '--series-1', 'rect')]), tb,
                f'Rok 2026 má navíc nálezy z kontroly v datech (vyřazené plané poplachy) a přesnější údaje (počet platných lístků). Nálezy {ROK} s vlivem na výsledek jsme zkontrolovali, '
                'ostatní jsou automatické, takže obsahují i plané poplachy, které by kontrola vyřadila (u roku 2026 to byla zhruba třetina nálezů M v obcích).')
    body += soudy_sekce(path, F, FS, S)
    body += metodika()
    page(path, f'Komunální volby {ROK}', body, f'Zpětná forenzní analýza komunálních voleb {ROK} stejnými metodami jako volby 2026, srovnání se soudy', section='kv',
         crumbs=[('Přehled', 'index.html'), (f'Komunální volby {ROK}', None)])


def soudy_sekce(path, F, FS, S):
    if not S:
        return ''
    zmena = [c for c in S if c['rozhodnuti'] == 'vyhověno']
    s = f'<h2 id="soudy">Srovnání se soudními řízeními k volbám {ROK}</h2>' + T['soudy_text']
    s += ('<h3>Soudem změněné výsledky (vyhovující rozhodnutí)</h3><div class="card tw"><table><thead><tr><th>Obec, soud</th><th>Co soud zjistil</th>'
          f'<th>Opravený záznam ČSÚ</th><th>Analýza {ROK}</th></tr></thead><tbody>')
    for c in sorted(zmena, key=lambda c: c['obec']):
        op = opravy_csu(c['slug'], c['mc']) if c['slug'] else []
        vz, fs = vztah(c, FS)
        s += (f'<tr><td><a href="{E(c["odkaz"])}">{E(c["obec"])}{" (" + E(c["mc"]) + ")" if c["mc"] and c["mc"] != c["obec"] else ""}</a><br><span class="sub">{E(c["soud"])} {E(c["spis"])}</span></td>'
              f'<td>{E(T["soud_popis"].get(c["spis"], c["poznamka"]))}</td><td>{E(opravy_text(op))}</td>'
              f'<td>{E(T["vysledek_soud"].get(c["spis"], vz))}' + (': ' + ', '.join(f'<a href="{link(path, kraj_url(f["kraj"]))}#{E(f["gid"])}">{E(f["id"])}</a> ({E(f["typ"].lower())})' for f in fs[:4]) if fs else '') + '</td></tr>')
    s += '</tbody></table></div>'
    ost = [c for c in S if c['rozhodnuti'] != 'vyhověno']
    vz = [(c,) + vztah(c, FS) for c in ost]
    cn = Counter(v for _, v, _ in vz)
    s += (f'<h3>Ostatní návrhy ({len(ost)})</h3><p>Ve {cn["přesná"]} řízeních máme nález přímo v okrsku, o který se návrh opíral, v dalších {cn["obec"]} nález jinde v téže obci '
          f'a v {cn["žádná"]} řízeních žádný nález. ' + T['ostatni_text'] + '</p>'
          f'<div class="card tw"><table class="sortable"><thead><tr><th>Soud, sp. zn.</th><th>Obec</th><th>Rozhodnutí</th><th>Přepočet</th><th>Okrsky v rozhodnutí</th><th>Nálezy analýzy {ROK}</th></tr></thead><tbody>')
    for c, v, fs in sorted(vz, key=lambda x: ({'přesná': 0, 'obec': 1, 'žádná': 2}[x[1]], x[0]['obec'])):
        s += (f'<tr><td><a href="{E(c["odkaz"])}">{E(c["soud"])} {E(c["spis"])}</a></td><td>{E(c["obec"])}' + (f' ({E(c["mc"])})' if c['mc'] else '') + '</td>'
              f'<td>{E(c["rozhodnuti"] or "–")}</td><td>{E(c["prepocet"] or "–")}</td><td>{E(c["okrsky"] or "–")}</td><td>{E(v)}'
              + (': ' + ', '.join(f'<a href="{link(path, kraj_url(f["kraj"]))}#{E(f["gid"])}">{E(f["id"])}</a>' for f in fs[:5]) if fs else '') + '</td></tr>')
    return s + '</tbody></table></div>'


def souhrn_text(F, S):
    """Závěr: nálezy s vysokou jistotou, které mění výsledek, a jejich vztah k soudům."""
    path = f'{D}/index.html'
    hl = razeni([f for f in F if f['dopad_kat'] in MAT and f['jistota'] >= 3])
    li = ''.join(f'<li><a href="{link(path, kraj_url(f["kraj"]))}#{E(f["gid"])}">{E(f["obec"])} {E(f["id"])}</a> ({E(misto(f))}): {E(str(f["typ"]).lower())} – '
                 f'{E(str(f.get("dopad") or ""))} <span class="sub">{"Řízení u soudu ke stejnému zastupitelstvu (ne nutně k této chybě): " + ", ".join(c["spis"] + " (" + (c["rozhodnuti"] or "?") + ")" for c in soudy_nalezu(f, S)) + "." if soudy_nalezu(f, S) else "Návrh k soudu podán nebyl."}</span></li>' for f in hl)
    bez = sum(1 for f in hl if not soudy_nalezu(f, S))
    return (f'<div class="verdict"><p><strong>Závěr:</strong> Nálezy roku {ROK} nevykazují vzorec koordinované manipulace; chyby mají stejný charakter jako v roce 2026 '
            f'(překlepy při přepisu, nezapočtené balíky lístků s křížkem u strany, neúplně opsané řádky). {len(hl)} nálezů s vysokou jistotou podle simulace měnilo '
            f'mandáty nebo zvolené kandidáty a {bez} z nich nebylo předmětem žádného soudního řízení ke stejnému zastupitelstvu' + (' – zastupitelstva tak pravděpodobně pracovala ve složení, které neodpovídalo '
            'odevzdaným hlasům' if bez else '') + ':</p><ul class="l">' + li + '</ul>' + T['zaver_soudy'] + '</div>')


def metodika():
    pred = T['predchozi']
    return f'''<h2>Jak zpětná analýza vznikla</h2><ul class="l">
<li><strong>Stejné metody jako 2026:</strong> detektory řady N (překlepy u kandidátů, chybějící balíky a nulové strany, neúplně opsané řádky, záměny stran, aritmetika zápisů,
těsné výsledky) a doplňková pravidla řady M (propad kandidáta pod počet lístků s křížkem u strany, posunuté úseky a nuly v kandidátce, chybějící balík, nezapsané hlasy
okrsku{f"; v malých obcích srovnání okrsku s rokem {pred}" if pred else ""}). Dopad každého nálezu je simulován přepočtem mandátů a pořadí kandidátů.</li>
<li><strong>Původní záznamy:</strong> analyzují se výsledky vyhlášené po volbách ({T["datum"]}), ne pozdější opravy po rozhodnutí soudu.</li>
<li><strong>Méně údajů než 2026:</strong> data {ROK} neobsahují počet platných lístků – využití hlasů se počítá z odevzdaných obálek (zahrnují i neplatné lístky), detektory
chybějících lístků jsou proto méně citlivé a test nulového počtu neplatných lístků nelze provést. XML dávky z volební noci (opravy během zpracování) nejsou k dispozici.
{"Data předchozích voleb (2014) v analýze nejsou, srovnání okrsků s minulými volbami (pravidlo P5b v malých obcích, nízké využití hlasů jako místní zvyk) proto chybí." if not pred else ""}</li>
<li><strong>Kontrola nálezů:</strong> každý nález, který podle simulace mění nebo může změnit výsledek, jsme jednotlivě prošli v datech (s pomocí AI): hodnoty kandidátů
proti ostatním kandidátům strany a proti sousedním okrskům{f", využití hlasů v roce {pred}" if pred else ""}. Nejčastějším planým poplachem byly „překlepy“ v malých obcích – kandidát
z místní části dostane v malém okrsku hlasy velké části voličů, nebo voliči volí jednotlivé kandidáty a hlasy kandidátky se silně liší. Ostatní nálezy (bez vlivu na výsledek)
jsou automatické a obsahují i plané poplachy.</li>
<li><strong>Zdroje:</strong> <a href="{od()}">otevřená data ČSÚ KV {ROK}</a> (původní i opravené záznamy), <a href="{vg()}">výsledky KV {ROK} na volby.gov.cz</a>.
Postupy detektorů popisuje <a href="../metodika.html">Metodika</a> a <a href="../pravidla.html">přehled pravidel M</a>.</li></ul>'''


# ---- texty podle roku (po kontrole nálezů, listopad 2026); klíče soud_popis / vysledek_soud = spisová značka
_NSS = '<a href="https://vyhledavac.nssoud.cz/">vyhledávače NSS</a>'
TEXTY = {
    2022: dict(
        datum='23.–24. 9. 2022', predchozi=2018,
        soudy_text=('<p>Zdroje: přehled ČSÚ o výsledcích změněných rozhodnutím soudu (<a href="https://volby.gov.cz/pls/kv2022/kvs?xjazyk=CZ">volby.gov.cz</a>, stav 15. 11. 2022), '
                    f'anonymizovaná rozhodnutí krajských soudů z {_NSS} (fulltext, rozhodnutí z října až prosince 2022) '
                    'a rozhodnutí o Hrčavě. Celkem 78 řízení o neplatnosti volby kandidáta, hlasování nebo voleb (evidence <code>soudy/podani_2022.csv</code>, skript '
                    '<code>scripts/soudy_historie.py</code>). Vyhledávač nemusí obsahovat všechna rozhodnutí; řízení u Městského soudu v Praze jsou v něm zastoupena jen zčásti. '
                    'Otevřená data ČSÚ uchovávají u obcí, kde soud výsledek změnil, původní i opravený záznam okrsku (pozdější datum voleb) – analýza pracuje '
                    's původními záznamy, opravené slouží jako ověřený vzorek skutečných chyb.</p>'),
        soud_popis={
            '31 A 29/2022': 'Deset voličů písemně potvrdilo křížek u strany Občané Stanovic, tři její kandidáti přitom měli jen 4, 8 a 6 hlasů. Přepočet: 6 mandátů místo 5.',
            '73 A 4/2022': 'Remíza 412 : 412 rozhodnutá losem; přepočet (ověřený i ČSÚ) dal 413 : 412 – odchylky ±1–2 hlasy u 7 kandidátů. Změnila se většina.',
            '55 A 72/2022': 'Komise vyřadila 5 lístků jako neplatné, 2 z nich byly platné. Mandát se posunul uvnitř strany.',
            '115 A 5/2022': 'Voliči byli nezákonně vyškrtnuti ze seznamu voličů; hlasování neplatné, opakováno 7. 1. 2023.',
            '21 A 6/2022': 'Účelové přihlašování osob k pobytu; volby neplatné, opakovány 18. 2. 2023.',
        },
        vysledek_soud={
            '31 A 29/2022': 'Jako chyba nezachyceno – obec má jediný okrsek, srovnání s okolím chybí. Využití hlasů obce kleslo z 97 % (2018) na 44 % (druhý největší pokles '
                            'v ČR), v roce 2018 ale kandidovala jediná kandidátka, takže pokles sám chybu neprokazuje. Opravený záznam: strana 2 měla po přepočtu '
                            '21–34 hlasů na kandidáta místo 4–17, tj. nezapočteno ~17 lístků s křížkem u strany. Analýza vykázala jen těsný výsledek',
            '73 A 4/2022': 'Zachyceno jako riziko – těsný výsledek (odchylky o 1–2 hlasy statisticky viditelné nejsou)',
            '55 A 72/2022': 'Mimo dosah dat – posouzení platnosti lístků se v okrskových výsledcích neprojeví; analýza vykázala těsný výsledek',
            '115 A 5/2022': 'Mimo dosah dat (seznam voličů)',
            '21 A 6/2022': 'Mimo dosah dat (složení voličstva)',
        },
        ostatni_text=('Soudy návrhy, které se opíraly jen o statistiku nebo obecné podezření, zamítaly bez přepočtu („zvlášť významná indicie“ chyběla). '
                      'Skutečně přepočítávaly jen v několika případech (Kostelec, Mníšek pod Brdy, Krupka, Měcholupy) a ve všech potvrdily vyhlášený výsledek '
                      'nebo našly jen odchylky bez vlivu. V Kostelci program OVK hlásil chybu součtu („chyba 22“) a komise zjistila, že chybně vyhodnocovala lístky '
                      's křížkem u strany – stejný typ chyby, jaký hledají pravidla řady M. '
                      '<strong>Karviná (24 A 4/2022)</strong> je nezávislé potvrzení pravidel M: navrhovatel tvrdil, že v okrsku 8 dal křížek celé kandidátce Pirátů '
                      '(39 hlasů), strana přitom měla v okrsku zapsáno jen 29 hlasů – a pravidla v témže okrsku našla rozptýlené nuly v kandidátce Pirátů '
                      '(23 z 39 kandidátů s nulou). Soud návrh zamítl, protože ani doplnění hlasů by mandáty nezměnilo; stejně vychází i naše simulace.'),
        zaver_soudy=('<p>Soudy v roce 2022 změnily výsledek v 5 obcích; tři z nich (Stanovice, Matějov, Sovínky) kvůli chybám sčítání nebo posouzení lístků. Žádný z těchto '
                     'případů se v okrskových datech neprojevil jako zjevná chyba – všechny tři ale analýza označila jako těsný výsledek (<a href="#soudy">srovnání se soudy</a>).</p>'),
    ),
    2018: dict(
        datum='5.–6. 10. 2018', predchozi=None,
        soudy_text=('<p>Zdroje: přehled ČSÚ o výsledcích změněných rozhodnutím soudu (<a href="https://volby.gov.cz/pls/kv2018/kvs?xjazyk=CZ">volby.gov.cz</a>), '
                    f'anonymizovaná rozhodnutí krajských soudů z {_NSS} (fulltext, rozhodnutí z října 2018 až ledna 2019), rozhodnutí o Praze 4 podle odborné analýzy '
                    '(Ferfecký, Scheuer, Šíp, Časopis pro právní vědu a praxi 4/2020). Celkem 174 řízení (evidence <code>soudy/podani_2018.csv</code>, skript '
                    '<code>scripts/soudy_historie.py</code>); podle zmíněné analýzy bylo podáno 239 návrhů. Část obcí je ve zveřejněných rozhodnutích anonymizována '
                    '(„obec O.“) a nelze je přiřadit. Údaj o přepočtu je doplněn jen u řízení, kde soud výsledek změnil. Otevřená data ČSÚ uchovávají u obcí, kde soud '
                    'výsledek změnil, původní i opravený záznam okrsku (pozdější datum voleb) – analýza pracuje s původními záznamy.</p>'),
        soud_popis={},
        vysledek_soud={
            '14 A 213/2018': 'Zachyceno přesně: nezapočtený balík lístků ANO v okrsku 4041 (N01), simulace mění mandáty (ANO 7 → 8); opravený záznam ČSÚ to potvrzuje',
            '63 A 8/2018': 'Zachyceno: v okrsku 23007 neúplně opsaný řádek Zelených (kandidáti č. 41–45 s nulou, N03) a v okrsku 23049 nezapsané hlasy ~48 lístků (M15). '
                           'Dopad simulace podcenila – hlasy v okrsku 23049 nešlo přiřadit konkrétní straně, soud přepočtem zjistil 417 chybějících hlasů Zelených',
            '63 A 4/2018': 'Nezachyceno – chybějící balík KSČM v okrsku 11001 analýza nevykázala (v MČ jen chybějící balík ANO na lístku města v jiném okrsku); '
                           'opravený záznam ČSÚ okrskové hlasy nemění',
            '21 A 7/2018': 'Nezachyceno – detektor překlepů vynechává lídry kandidátek (lídr dostává i preferenční hlasy); 411 hlasů proti ~50 u ostatních kandidátů je '
                           'přitom zjevné. Analýza vykázala jen těsný výsledek',
            '52 A 4/2018': 'Nezachyceno – nadhodnocení tří kandidátů v okrsku 1 (200, 131 a 127 místo 99, 81 a 77) detektory nevykázaly; nález v okrsku 2 kontrola vyřadila '
                           'jako preferenční hlasy. Analýza vykázala těsný výsledek',
            '30 A 117/2018': 'Nezachyceno – komise dopsala nevyužité hlasy kandidátům podle pořadí; v obci s jediným okrskem to srovnání s okolím neodhalí',
            '54 A 118/2018': 'Mimo dosah dat (volitelnost kandidáta); odchylky přepočtu o 1–10 hlasů statisticky viditelné nejsou',
            '54 A 143/2018': 'Mimo dosah dat (volitelnost kandidáta)', '43 A 119/2018': 'Mimo dosah dat (volitelnost kandidáta)',
            '11 A 224/2018': 'Mimo dosah dat (volitelnost kandidáta)',
            '14 A 216/2018': 'Vyhověno kvůli volitelnosti kandidáta. Ve stejném řízení navrhovatel napadl i okrsek 8084, kde mají kandidáti ČSSD č. 1–23 po 6–12 hlasech '
                             'a č. 24–45 nulu – analýza tu vykazuje neúplně opsaný řádek (N21). Soud tuto část zamítl, protože navrhovatel netvrdil, že pro stranu hlasoval',
            '51 A 9/2018': 'Mimo dosah dat (průběh hlasování)', '52 A 7/2018': 'Mimo dosah dat (zabezpečení volební schránky)', '52 A 16/2018': 'Mimo dosah dat (volební kampaň)',
        },
        ostatni_text=('Mezi zamítnutými návrhy jsou i případy, kdy navrhovatel tvrdil přesně to, co ukazují pravidla analýzy: v <strong>Praze 10</strong> (9 A 209/2018 a další) '
                      'kandidáti navrhovatele v okrsku 10008 od 26. místa neměli žádný hlas – analýza tam vykazuje neúplně opsané řádky u několika kandidátek. '
                      'Soudy statistický argument bez svědectví konkrétního voliče nepřijímaly a přepočet nenařizovaly.'),
        zaver_soudy=('<p>Soudy v roce 2018 změnily výsledek ve 13 obcích a městských částech, v šesti kvůli chybám sčítání (Šenov, Dobev, Rašín, Brno-Kohoutovice, '
                     'Brno-střed, Praha 4). Analýza zachytila dvě z nich: <strong>Prahu 4</strong> přesně i s dopadem na mandáty a <strong>Brno-střed</strong> (neúplně opsaný '
                     'řádek Zelených, dopad podceněn). Překlep u lídra (Šenov), nadhodnocení kandidátů (Dobev), dopsané hlasy (Rašín) a chybějící balík v Kohoutovicích '
                     'nezachytila (<a href="#soudy">srovnání se soudy</a>).</p>'),
    ),
}

if __name__ == '__main__':
    for r in ([int(sys.argv[1])] if len(sys.argv) > 1 else sorted(TEXTY, reverse=True)):
        F = build(r)
        print(f'KV {r}:', len(F), 'nálezů ->', os.path.join(ROOT, 'report', D))
