"""PDF přehledy soudních podání ke komunálním volbám 2026 (Praha a kraje) ze soudy/podani_2026.csv.

Použití:  python scripts/soudy_pdf.py [výstupní adresář]      (výchozí soudy/)
Vyžaduje reportlab (pip install reportlab) a písmo Arial z C:/Windows/Fonts.
Vytvoří soudni_podani_praha_2026.pdf a soudni_podani_kraje_2026.pdf. Sloupec „Nálezy M“ ukazuje nálezy doplňkových
pravidel (listopad 2026) ve stejném okrsku, jaký podání napadá (sloupce nalezy_m / odkaz_m v CSV).
"""
import collections, csv, datetime, os, re, sys
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CSV = os.path.join(ROOT, 'soudy', 'podani_2026.csv')
WEB = 'https://volebnianalyza.suchan.cz/'
for n, f in (('Arial', 'arial.ttf'), ('Arial-Bold', 'arialbd.ttf'), ('Arial-Italic', 'ariali.ttf')):
    pdfmetrics.registerFont(TTFont(n, f'C:/Windows/Fonts/{f}'))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold', italic='Arial-Italic', boldItalic='Arial-Bold')

INK, MUTED, ACCENT = colors.HexColor('#1f2933'), colors.HexColor('#5f6b7a'), colors.HexColor('#1d4e89')
RULE, HEAD_BG, ZEBRA = colors.HexColor('#c9d2dc'), colors.HexColor('#e8eef5'), colors.HexColor('#f6f8fa')
TAGC = {'přesná': '#1b7f3b', 'částečná': '#9a6700', 'obecná': '#5f6b7a', 'nejistá': '#5f6b7a', 'mezera': '#b42318', 'žádná': '#9aa5b1'}
ROZC = {'vyhověno': '#1b7f3b', 'zamítnuto': '#5f6b7a', 'odmítnuto': '#5f6b7a', 'zastaveno': '#5f6b7a'}
title = ParagraphStyle('t', fontName='Arial-Bold', fontSize=18, leading=22, textColor=INK, spaceAfter=4)
sub = ParagraphStyle('s', fontName='Arial', fontSize=10, leading=13, textColor=MUTED, spaceAfter=8)
h2 = ParagraphStyle('h2', fontName='Arial-Bold', fontSize=12.5, leading=16, textColor=ACCENT, spaceBefore=8, spaceAfter=4)
h3 = ParagraphStyle('h3', fontName='Arial-Bold', fontSize=10, leading=13, textColor=INK, spaceBefore=6, spaceAfter=3)
body = ParagraphStyle('b', fontName='Arial', fontSize=9.5, leading=13, textColor=INK, spaceAfter=5)
bullet = ParagraphStyle('bl', parent=body, leftIndent=12, bulletIndent=2, spaceAfter=3)
cell = ParagraphStyle('c', fontName='Arial', fontSize=7.5, leading=9.3, textColor=INK)
cellb = ParagraphStyle('cb', parent=cell, fontName='Arial-Bold')
hcell = ParagraphStyle('h', parent=cell, fontName='Arial-Bold')
note = ParagraphStyle('n', parent=body, fontSize=8.5, leading=11.5, textColor=MUTED)
ORDER = ['Středočeský kraj', 'Jihočeský kraj', 'Plzeňský kraj', 'Karlovarský kraj', 'Ústecký kraj', 'Liberecký kraj', 'Královéhradecký kraj',
         'Pardubický kraj', 'Kraj Vysočina', 'Jihomoravský kraj', 'Olomoucký kraj', 'Zlínský kraj', 'Moravskoslezský kraj']
ROZH = ('vyhověno', 'zamítnuto', 'odmítnuto', 'zastaveno')


def a(url, text):
    return f'<link href="{escape(url)}" color="#1d4e89"><u>{escape(text)}</u></link>' if url else escape(text)


def P(x, st=cell):
    return Paragraph(x, st)


def datum_cz(d):
    return f'{int(d[8:10])}. {int(d[5:7])}.' if re.match(r'\d{4}-\d\d-\d\d', d or '') else ''


_OKRES = {}


def okres_kotva(slug):
    """Malé obce bez vlastní stránky jsou řádkem na stránce okresu (kotva o-<kód obce>)."""
    if not _OKRES:
        kody = {r['slug']: r['kod'] for r in csv.DictReader(open(os.path.join(ROOT, 'data', 'obce_2026.csv'), encoding='utf-8'))}
        d = os.path.join(ROOT, 'report', 'kv', 'okres')
        kotvy = {}
        for f in os.listdir(d) if os.path.isdir(d) else []:
            for k in re.findall(r'id="o-(\d+)"', open(os.path.join(d, f), encoding='utf-8').read()):
                kotvy[k] = f
        _OKRES.update({s: f'{WEB}kv/okres/{kotvy[k]}#o-{k}' for s, k in kody.items() if k in kotvy})
    return _OKRES.get(slug, '')


def cil(r, fid):
    """URL nálezu fid obce z řádku r: stránka nálezů obce, jinak řádek obce na stránce okresu."""
    if r['slug'] and os.path.exists(os.path.join(ROOT, 'report', 'kv', r['slug'], 'nalezy.html')):
        return f'{WEB}kv/{r["slug"]}/nalezy.html#{fid}'
    return okres_kotva(r['slug'])


def nalezy_n(r):
    ids = [i for i in r['nalezy'].split() if i.startswith('N')]
    pop = r['nalez_popis'] or ''
    if r['vztah'] in ('žádná', ''):
        return '—'
    if not pop or not re.search(r'\b[NM]\d+\b', pop):  # popis bez ID – odkazy předřadit
        pop = ', '.join(ids) + (f' – {pop}' if pop else '')
    # každé ID v popisu se stane odkazem na nález
    return re.sub(r'\b([NM]\d+)\b', lambda m: a(cil(r, m.group(1)), m.group(1)), escape(pop)) or '—'


def nalezy_m(r):
    ids = r.get('nalezy_m', '').split() or [i for i in r['nalezy'].split() if i.startswith('M')]
    if not ids:
        return '—'
    return ', '.join(a(cil(r, i), i) for i in ids)


def stav(r):
    roz = r['rozhodnuti']
    if roz:
        c = ROZC.get(roz, '#5f6b7a')
        s = f'<font color="{c}"><b>{escape(roz)}</b></font> {datum_cz(r["datum_rozhodnuti"])}'
        if r['zmena_slozeni'] == 'ano':
            s += '<br/><b>mění složení</b>'
        return s
    s = r['stav_2026_11_01'] or 'běží'
    return escape('běží' if s.startswith('nevyvěšeno') else s)


def tag(v):
    return f'<font color="{TAGC.get(v, "#5f6b7a")}"><b>{escape(v)}</b></font>'


def table(head, data, widths):
    t = Table([[P(h, hcell) for h in head]] + data, colWidths=widths, repeatRows=1)
    st = [('BACKGROUND', (0, 0), (-1, 0), HEAD_BG), ('LINEBELOW', (0, 0), (-1, 0), 0.8, ACCENT), ('LINEBELOW', (0, 1), (-1, -1), 0.3, RULE),
          ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 3.5), ('RIGHTPADDING', (0, 0), (-1, -1), 3.5),
          ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]
    st += [('BACKGROUND', (0, i), (-1, i), ZEBRA) for i in range(2, len(data) + 1, 2)]
    t.setStyle(TableStyle(st))
    return t


def radek(r, misto):
    return [P(a(r['odkaz_navrh'], r['spis']), cellb), P(escape(misto)), P(escape(r['navrhovatel'])), P(escape(r['predmet'])),
            P(nalezy_n(r)), P(nalezy_m(r)), P(tag(r['vztah'] or 'žádná')), P(stav(r))]


HEAD = ['Sp. zn.', 'Místo', 'Navrhovatel', 'Co podání napadá', 'Nález analýzy (N)', 'Nálezy M', 'Vztah', 'Stav']
W = [2.0 * cm, 2.6 * cm, 3.0 * cm, 7.2 * cm, 5.4 * cm, 2.0 * cm, 1.6 * cm, 2.9 * cm]


def zmeny_tab(R):
    """Řízení, v nichž soud změnil výsledek, s poznámkou o tom, co zjistil."""
    data = []
    for r in R:
        misto = r['mc'] or r['obec']
        nal = nalezy_n(r)
        extra = [i for i in r.get('nalezy_m', '').split() if i not in (r['nalez_popis'] or '') + ' ' + r['nalezy']]
        if extra:
            nal += '; ve stejném okrsku ' + ', '.join(a(cil(r, i), i) for i in extra)
        pot = {'ano': '<font color="#1b7f3b"><b>ano</b></font>', 'částečně': '<font color="#9a6700"><b>částečně</b></font>'}.get(r['nalez_potvrzen'], escape(r['nalez_potvrzen'] or '—'))
        if r['vztah'] == 'mezera':
            pot = '<font color="#b42318"><b>analýza nevykázala</b></font>'
        data.append([P(a(r['odkaz_navrh'], r['spis']), cellb), P(escape(misto)), P(escape(r['poznamka'] or r['predmet'])), P(nal), P(pot),
                     P(datum_cz(r['datum_rozhodnuti']))])
    return table(['Sp. zn.', 'Místo', 'Co soud zjistil a rozhodl', 'Nález analýzy', 'Nález potvrzen', 'Rozhodnuto'], data,
                 [2.1 * cm, 2.6 * cm, 11.4 * cm, 5.6 * cm, 2.6 * cm, 2.4 * cm])


def zdroje(s, praha, dnes):
    s.append(Paragraph('Odkud data pocházejí', h2))
    soudy = ('Úřední deska Městského soudu v Praze – jediného soudu příslušného pro volby na území hl. m. Prahy (§ 61 zákona č. 491/2001 Sb.)'
             if praha else 'Úřední desky krajských soudů včetně poboček; krajský soud je příslušný podle sídla registračního úřadu (§ 61 zákona č. 491/2001 Sb.), '
             'proto se některé obce objevují u soudu sousedního kraje')
    for b in [f'<b>{soudy}</b> – {a("https://infodeska.gov.cz/eudpub/", "infodeska.gov.cz")}. Ze záznamů agendy správního soudnictví (A) byly vybrány '
              'volební věci a staženy zveřejněné návrhy, výzvy, vyjádření a rozhodnutí. Stav řízení a výroky rozhodnutí byly aktualizovány '
              f'k {dnes}; řízení vyvěšená až po 1. 11. 2026 jsou doplněna. Řízení o místním referendu a o volbách do Senátu nejsou zahrnuta.',
              'Výsledky přepočtů ve sloupci „Co soud zjistil“ jsou převzaty z odůvodnění rozhodnutí. Rozhodnutí volebních soudů jsou konečná, '
              'proti nim lze podat jen ústavní stížnost.',
              'Nálezy analýzy vycházejí výhradně z otevřených dat Českého statistického úřadu (volby.gov.cz) – výsledků za jednotlivé okrsky. '
              f'Nálezy řady N vznikly hned po volbách, nálezy řady M přidala {a(WEB + "pravidla.html", "doplňková pravidla")} '
              'z listopadu 2026 (nemožné tvary kandidátky, chybějící balíky, deficit využití hlasů); v sloupci „Nálezy M“ jsou nálezy ve stejném '
              'okrsku, jaký podání napadá.']:
        s.append(Paragraph(b, bullet, bulletText='•'))
    s.append(Paragraph('Jde o veřejná data', h2))
    s.append(Paragraph(
        'Ve volebních věcech soud podle § 93 odst. 5 zákona č. 150/2002 Sb., soudního řádu správního, doručuje návrhy, výzvy a rozhodnutí '
        '<b>vyvěšením na úřední desce</b>; doručení nastává dnem vyvěšení. Obsah řízení je tak veřejně dostupný, aby se k němu mohli včas vyjádřit '
        'všichni dotčení. Dokumenty jsou na desce vyvěšeny dočasně (zpravidla 15–30 dní) a po svěšení již nemusí být online dostupné. '
        'Některé dokumenty obsahují osobní údaje účastníků; v přehledu proto neuvádíme jména navrhovatelů, kteří jsou soukromými osobami – '
        'jen volební strany a kandidáty z veřejných kandidátních listin.', body))
    s.append(Paragraph(
        f'Přehled popisuje, co navrhovatelé tvrdí a jak soudy k {dnes} rozhodly. Byl sestaven s pomocí AI z textů zveřejněných dokumentů; '
        'u naskenovaných podání nelze vyloučit nepřesnost při čtení. Pro aktuální stav je rozhodující úřední deska příslušného soudu.', note))


def dokument(out, nadpis, popis, s, pata):
    def footer(c, doc):
        c.saveState(); c.setFont('Arial', 7.5); c.setFillColor(MUTED)
        c.drawString(1.5 * cm, 0.9 * cm, pata)
        c.drawRightString(landscape(A4)[0] - 1.5 * cm, 0.9 * cm, f'strana {doc.page}')
        c.restoreState()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.1 * cm, bottomMargin=1.4 * cm,
                            title=nadpis, author='Martin Suchan', subject=popis)
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print('ok', out)


def souhrn(R):
    V = collections.Counter(r['vztah'] for r in R)
    S = collections.Counter(r['rozhodnuti'] for r in R if r['rozhodnuti'])
    return V, S, sum(S[k] for k in ROZH)


def praha(R, out, dnes):
    V, S, dec = souhrn(R)
    vliv = [r for r in R if r['rozhodnuti'] == 'vyhověno' and r['zmena_slozeni'] == 'ano']
    def hlavni_rizeni(r):  # u spojených řízení jen to, pod kterým soud rozhodl
        m = re.match(r'spojeno do (\d+ A \d+/\d{4})', r['poznamka'] or '')
        return not m or m.group(1) == r['spis']
    hlavni = [r for r in vliv if hlavni_rizeni(r)]
    mc = sorted({r['mc'] for r in hlavni})
    s = [Paragraph('Soudní podání ke komunálním volbám 2026 v Praze', title),
         Paragraph(f'Návrhy u Městského soudu v Praze, jejich výsledek a vztah k nálezům forenzní analýzy volebnianalyza.suchan.cz · stav k {dnes}', sub),
         Paragraph('Shrnutí', h2)]
    for b in [
        f'K volbám do Zastupitelstva hl. m. Prahy a zastupitelstev městských částí je evidováno <b>{len(R)} volebních řízení</b>. '
        f'Soud rozhodl ve <b>{dec}</b> z nich: {S["vyhověno"]}× vyhověl, {S["zamítnuto"]}× zamítl, {S["odmítnuto"]}× odmítl'
        + (f', {S["zastaveno"]}× zastavil' if S['zastaveno'] else '') + '.',
        f'<b>Soud změnil výsledek ve {len(mc)} městských částech</b> ({", ".join(mc)}) a ve všech případech šlo o chybu, kterou analýza předem označila: '
        'Praha 10 (okrsek 10043, Křehlík 15 hlasů místo 165 – N01; okrsek 10028 – N17), Praha 15 (okrsek 15003, nezapočtený balík – N02) '
        'a Praha 3 (okrsek 3052, 35 místo 353 – N11, změna pořadí náhradníků).',
        f'<b>{V["přesná"]}</b> podání napadá přesně okrsek a vadu z nálezu, u <b>{V["částečná"]}</b> se kryje část okrsků. '
        'Doplňková pravidla z listopadu 2026 (nálezy řady M) přidala nálezy ve stejných okrscích u dalších podání – mj. Praha 12, okrsek 12025 '
        '(M66, rozptýlené nuly u TOP 09), který byl k 1. 11. veden jako mezera analýzy.',
        'Tři podání analýzu přímo citují: 10 A 67/2026 (Praha 10) ji přikládá jako přílohu, 17 A 63/2026 a 12 A 90/2026 (Praha 15) ji uvádějí mezi důkazy.',
    ]:
        s.append(Paragraph(b, bullet, bulletText='•'))
    s.append(KeepTogether([Paragraph('Řízení, v nichž soud změnil výsledek voleb', h2), zmeny_tab(hlavni)]))
    s.append(Paragraph('A. Podání, která se týkají nálezů analýzy', h2))
    s.append(Paragraph('Sloupec <i>Vztah</i>: <b>přesná</b> = podání napadá stejný okrsek a stejnou vadu jako nález; <b>částečná</b> = shoda u části '
                       'napadených okrsků; <b>obecná</b> = analýza MČ označila jen jako těsný výsledek; <b>nejistá</b> = návrh není zveřejněn; '
                       '<b>mezera</b> = analýza vadu nevykázala. Spisová značka odkazuje na soubor na úřední desce (dostupný jen do svěšení), '
                       'odkazy N.. a M.. na nález na webu.', note))
    A_ = [r for r in R if r['vztah'] not in ('žádná', '')]
    s.append(table(HEAD, [radek(r, r['mc'] or r['obec']) for r in A_], W))
    B_ = [r for r in R if r['vztah'] in ('žádná', '')]
    s.append(Spacer(1, 4))
    s.append(Paragraph('B. Ostatní podání (nesouvisí s nálezy analýzy)', h2))
    s.append(Paragraph('Podání se týkají vad, které z výsledkových dat zjistit nelze (volitelnost a bydliště kandidátů, informování voličů, '
                       'posuzování jednotlivých lístků, kampaň). Neznamenají rozpor s analýzou – leží mimo její rozsah.', note))
    s.append(table(['Sp. zn.', 'Místo', 'Navrhovatel', 'Předmět podání', 'Stav'],
                   [[P(a(r['odkaz_navrh'], r['spis']), cellb), P(escape(r['mc'] or r['obec'])), P(escape(r['navrhovatel'])), P(escape(r['predmet'])), P(stav(r))] for r in B_],
                   [2.2 * cm, 2.8 * cm, 4.4 * cm, 13.0 * cm, 4.3 * cm]))
    zdroje(s, True, dnes)
    dokument(out, 'Soudní podání – komunální volby Praha 2026', 'Návrhy u Městského soudu v Praze a jejich vztah k nálezům forenzní analýzy', s,
             f'Soudní podání – komunální volby Praha 2026 · stav k {dnes} · volebnianalyza.suchan.cz')


def kraje(R, out, dnes):
    V, S, dec = souhrn(R)
    vliv = [r for r in R if r['rozhodnuti'] == 'vyhověno' and r['zmena_slozeni'] == 'ano']
    nove = sum(1 for r in R if r['stav_2026_11_01'].startswith('nevyvěšeno'))
    pot = [r for r in vliv if r['nalez_potvrzen'] in ('ano', 'částečně')]
    s = [Paragraph('Soudní podání ke komunálním volbám 2026 mimo Prahu', title),
         Paragraph(f'Návrhy u krajských soudů, jejich výsledek a vztah k nálezům forenzní analýzy volebnianalyza.suchan.cz · stav k {dnes}', sub),
         Paragraph('Shrnutí', h2)]
    for b in [
        f'Na úředních deskách krajských soudů je ke komunálním volbám evidováno <b>{len(R)} řízení</b> z 13 krajů '
        f'({nove} z nich bylo vyvěšeno až po 1. 11. 2026). Soudy rozhodly ve <b>{dec}</b> věcech: {S["vyhověno"]}× vyhověly, '
        f'{S["zamítnuto"]}× zamítly, {S["odmítnuto"]}× odmítly a {S["zastaveno"]}× řízení zastavily.',
        f'<b>Výsledek voleb soud změnil v {len(vliv)} obcích.</b> V {len(pot)} z nich šlo o chybu, kterou analýza předem označila – '
        + ', '.join(f'{escape(r["mc"] or r["obec"])} ({escape(r["nalezy_m"] or r["nalezy"])})' for r in pot) + '.',
        '<b>Mezery analýzy:</b> v ' + str(len([r for r in vliv if r['vztah'] == 'mezera'])) + ' obcích soud doložil chybu, kterou analýza nevykázala – '
        + '; '.join(f'{escape(r["obec"])}' for r in vliv if r['vztah'] == 'mezera')
        + '. Jde o přehozené číslice (Býkev) a o nezapočtené lístky s křížkem u strany v malých obcích s jediným okrskem nebo u posledních '
        'kandidátů kandidátky, kde chybí srovnání s jinými okrsky – podněty pro další úpravu pravidel.',
        f'<b>{V["přesná"]}</b> podání napadá přesně chybu z nálezu analýzy, u <b>{V["částečná"]}</b> se kryje část okrsků, '
        f'u <b>{V["obecná"]}</b> analýza obec vedla jen jako těsný výsledek. Nálezy řady M (doplňková pravidla, listopad 2026) přibyly '
        've stejném okrsku u podání v Havířově (M01 – soud vyhověl), Brně-Bystrci (M01), Uherském Hradišti (M01) a dalších.',
    ]:
        s.append(Paragraph(b, bullet, bulletText='•'))
    s.append(Paragraph('Řízení, v nichž soud změnil výsledek voleb', h2))
    s.append(zmeny_tab(sorted(vliv, key=lambda r: (ORDER.index(r['kraj']) if r['kraj'] in ORDER else 99, r['obec']))))
    by = collections.defaultdict(list)
    for r in R:
        by[r['kraj']].append(r)
    sumrows = []
    for k in ORDER:
        X = by.get(k, [])
        if not X:
            continue
        c = collections.Counter(r['vztah'] for r in X)
        sumrows.append([P(k, cellb), P(str(len(X))), P(str(c['přesná'] + c['částečná'])), P(str(c['obecná'])), P(str(c['mezera'])),
                        P(str(sum(1 for r in X if r['nalezy_m']))), P(str(sum(1 for r in X if r['rozhodnuti'] in ROZH))),
                        P(str(sum(1 for r in X if r['rozhodnuti'] == 'vyhověno' and r['zmena_slozeni'] == 'ano')))])
    s.append(KeepTogether([Paragraph('Přehled po krajích', h3),
                           table(['Kraj', 'Řízení', 'Přesná / částečná shoda', 'Těsný výsledek', 'Mezera analýzy', 'S nálezem M', 'Rozhodnuto', 'Změna výsledku'],
                                 sumrows, [5.0 * cm, 1.8 * cm, 3.4 * cm, 2.6 * cm, 2.6 * cm, 2.4 * cm, 2.4 * cm, 2.6 * cm])]))
    s.append(Paragraph('Sloupec <i>Vztah</i>: <b>přesná</b> = stejný okrsek a vada jako nález; <b>částečná</b> = shoda u části okrsků; <b>obecná</b> = analýza '
                       'obec označila jen jako těsný výsledek; <b>nejistá</b> = souvislost nelze ověřit; <b>mezera</b> = soud nebo navrhovatel doložil chybu, '
                       'kterou analýza nevykázala; <b>žádná</b> = podání se nálezů netýká. Spisová značka odkazuje na soubor na úřední desce, odkazy N.. a M.. '
                       'na nález na webu. Jména navrhovatelů, kteří jsou soukromými osobami, neuvádíme.', note))
    for k in ORDER:
        X = by.get(k, [])
        if not X:
            continue
        X = sorted(X, key=lambda r: (r['vztah'] in ('žádná', ''), r['obec'], r['spis']))
        s.append(Spacer(1, 6))
        s.append(Paragraph(f'{k} <font color="#5f6b7a" size="9">· {len(X)} řízení · {", ".join(sorted({r["soud"] for r in X}))}</font>', h2))
        s.append(table(HEAD, [radek(r, r['obec'] + (f' – {r["mc"]}' if r['mc'] else '')) for r in X], W))
    s.append(PageBreak())
    zdroje(s, False, dnes)
    dokument(out, 'Soudní podání – komunální volby 2026 mimo Prahu', 'Návrhy u krajských soudů a jejich vztah k nálezům forenzní analýzy', s,
             f'Soudní podání – komunální volby 2026 mimo Prahu · stav k {dnes} · volebnianalyza.suchan.cz')


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'soudy')
    rows = list(csv.DictReader(open(CSV, encoding='utf-8-sig')))
    for r in rows:
        r.setdefault('nalezy_m', ''); r.setdefault('odkaz_m', '')
    d = datetime.date.today()
    dnes = f'{d.day}. {d.month}. {d.year}'
    praha([r for r in rows if r['soud_kod'] == '201000'], os.path.join(outdir, 'soudni_podani_praha_2026.pdf'), dnes)
    kraje([r for r in rows if r['soud_kod'] != '201000'], os.path.join(outdir, 'soudni_podani_kraje_2026.pdf'), dnes)


if __name__ == '__main__':
    main()
