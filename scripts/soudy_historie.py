"""Evidence soudních řízení ke komunálním volbám 2018 a 2022 (pro srovnání se zpětnou analýzou, report/kv2018/ a report/kv2022/).

Použití:  python scripts/soudy_historie.py 2022|2018
  1. Vyhledávač NSS (vyhledavac.nssoud.cz): fulltext „neplatnost volby kandidáta“, „neplatnost hlasování“, „neplatnost voleb“,
     rozhodnutí vydaná v období po volbách (CFG); ponechá spisové značky agendy A/<rok>.
  2. Stáhne anonymizovaná rozhodnutí do data/raw/soudy<rok>/ a převede je programem pdftotext.
  3. Vytáhne obec, výrok (vyhověno / zamítnuto / odmítnuto / zastaveno) a zmíněné okrsky; přiřadí obec k jednotce (slug).
  4. Zapíše soudy/podani_<rok>.csv. Ruční údaje (které věci nejsou volební, kde soud skutečně přepočítal hlasy, poznámky) jsou v tabulkách níže.
Do CSV se nezapisují jména účastníků.
"""
import csv, html, http.cookiejar, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import ROOT
import units

NSS = 'https://vyhledavac.nssoud.cz'
DOTAZY = ['neplatnost volby kandidáta', 'neplatnost hlasování', 'neplatnost voleb']
# ruční čtení odůvodnění (listopad 2026) – rok 2022
VYRAZ = {'707995', '707600', '706605', '706557', '705775', '705597', '706007', '708177'}  # zánik mandátu, místní referendum, stavební věc
RUCNE = {'707061': 'Praha 11', '705739': 'Kladno', '705959': 'Mohelnice (okres Plzeň-jih)', '705478': 'Svojkovice'}
RUCNE_SLUG = {'705943': 'kostelec-okres-hodonin'}  # odpůrce MěÚ Kyjov
PREPOCET = {'705943', '706108', '705870', '705872', '705947', '705724', '705449'}  # soud skutečně přepočítal hlasy / přezkoumal lístky
POZN = {
    '705943': 'program OVK hlásil chybu 22 (součet hlasů stran ≠ platné hlasy); komise zjistila chybné vyhodnocení lístků s křížkem u strany a sčítala znovu; soudní přepočet hlasů stran bez vlivu na mandáty',
    '706108': 'přepočet lístků v okrsku 5: pomocné sčítací listy odpovídají výsledkům, u některých kandidátů odchylky o 1 až několik hlasů, bez vlivu',
    '705870': 'přepočet hlasů dvou kandidátů ve všech okrscích potvrdil vyhlášené výsledky',
    '705872': 'kontrola hlasů jedné strany v okrsku 3 bez zjištění chyby',
    '705947': 'remíza 412 : 412 rozhodnutá losem; přepočet (ověřený ČSÚ) 413 : 412, odchylky ±1–2 hlasy u 7 kandidátů; změna většiny',
    '705724': 'kandidáti Občanů Stanovic měli méně hlasů, než kolik voličů písemně potvrdilo křížek u strany; přepočet: 6 mandátů místo 5',
    '705449': 'komise vyřadila 5 lístků jako neplatné, 2 byly platné (křížek u strany + kandidáti jiné strany, poznámka na lístku); posun mandátu uvnitř strany',
    '707996': 'voliči nezákonně vyškrtnuti ze seznamu; hlasování neplatné, opakováno 7. 1. 2023',
}
HRCAVA = dict(soud='KS Ostrava', spis='21 A 6/2022', obec='Hrčava', slug='hrcava', mc='', rozhodnuti='vyhověno', prepocet='ne',
              poznamka='účelové přihlašování k pobytu; volby neplatné, opakovány 18. 2. 2023', okrsky='',
              odkaz='https://justice.cz/documents/16809/0/21+A+6+2022/672317cf-666d-4d86-ab8b-bfa5dd0b415e')
# rok 2018 (ruční doplnění obcí; anonymizované obce „O.“, „S.“, „Ř.“, „B.“ nelze určit)
RUCNE18 = {'448231': 'Praha (hl. m.)', '450866': 'Mankovice', '445989': 'Kostelec nad Černými lesy', '450434': 'Dobev', '449215': 'Jesenice (okres Praha-západ)',
           '450181': 'Liběšice (okres Litoměřice)', '449737': 'O. (správní obvod Cheb)', '449732': 'S. (správní obvod Horšovský Týn)',
           '449537': 'Ř. (správní obvod Slaný)', '449463': 'B. (správní obvod Kamenice nad Lipou)'}
RUCNE_SLUG18 = {'450866': 'mankovice', '445989': 'kostelec-nad-cernymi-lesy', '450434': 'dobev', '449215': 'jesenice-okres-praha-zapad',
                '450181': 'libesice-okres-litomerice'}
RUCNE_MC18 = {'448706': ('brno', 'Brno-Kohoutovice'), '450321': ('ostrava', 'Poruba'), '450508': ('praha', 'Praha-Šeberov'), '447533': ('praha', 'Praha-Suchdol'),
              '448942': ('praha', 'Praha 19'), '448231': ('praha', '')}
# soudem změněné výsledky 2018 (rešerše soudy/historie_2018_2022.md) – soud přepočítal hlasy
PREPOCET18 = {'450955', '450434', '450254', '448706', '448709', '449540'}
POZN18 = {
    '450955': 'lídr ČSSD v okrsku 3 měl v zápisu 411 hlasů, fyzicky 41; mandát přešel na ODS',
    '450434': 'v okrsku 1 měli tři kandidáti strany 3 zapsáno 200, 131 a 127 hlasů místo 99, 81 a 77',
    '450254': 'program OVK hlásil nesoulad součtů, komise dopisovala nevyužité hlasy kandidátům podle pořadí',
    '448706': 'nezapočteno nejméně 26 lístků s křížkem jen u KSČM (≥ 546 hlasů), zjištěno podle okrsku 11001',
    '448709': 'lístky s křížkem jen u Zelených v okrscích 23049 a 23007 započteny jen zčásti (kandidáti č. 40–45 bez hlasu), chybělo 417 hlasů',
    '449540': 'zvolený kandidát neměl v obci trvalý pobyt; při přepočtu drobné odchylky bez vlivu',
    '449013': 'kandidát nebyl ke dni voleb přihlášen k trvalému pobytu', '449837': 'kandidát se před volbami odhlásil z trvalého pobytu',
    '446055': 'kandidát s trvalým pobytem v Praze 6, posun náhradníků', '449196': 'kandidát s trvalým pobytem v Praze 6, posun náhradníků',
    '448893': 'zneužití přenosné volební schránky, nadpočetné úřední obálky; hlasování opakováno',
    '449463': 'schránka šla otevřít bez porušení pečeti; hlasování neplatné',
    '448924': 'nepravdivá kampaň; po vrácení Ústavním soudem volby neplatné (17. 5. 2019), opakovány',
}
PRAHA4_18 = dict(soud='MS Praha', spis='14 A 213/2018', obec='Praha 4', slug='praha', mc='Praha 4', rozhodnuti='vyhověno', prepocet='ano',
                 poznamka='ANO mělo v okrsku 237 hlasů (1,87 %), v okrscích ve stejné budově 17–22 %; přepočet (podle Ferfecký, Scheuer, Šíp, ČPVP 4/2020)',
                 okrsky='4041', odkaz='https://doi.org/10.5817/CPVP2020-4-5')
CFG = {
    2022: dict(obdobi=('1.10.2022', '31.12.2022'), vyraz=VYRAZ, rucne=RUCNE, rucne_slug=RUCNE_SLUG, rucne_mc={}, prepocet=PREPOCET, pozn=POZN, navic=[HRCAVA], prepocet_uplny=True),
    2018: dict(obdobi=('1.10.2018', '31.1.2019'), vyraz=set(), rucne=RUCNE18, rucne_slug=RUCNE_SLUG18, rucne_mc=RUCNE_MC18,
               prepocet=PREPOCET18, pozn=POZN18, rozh={'448924': 'vyhověno'}, navic=[PRAHA4_18]),
}
GEN = {'Znojma': 'Znojmo', 'Karviné': 'Karviná', 'Kladna': 'Kladno', 'Ústí nad Labem – Severní Terasa': 'Severní Terasa'}
MC = {'Praha 4': ('praha', 'Praha 4'), 'Praha 7': ('praha', 'Praha 7'), 'Praha 10': ('praha', 'Praha 10'), 'Praha 11': ('praha', 'Praha 11'),
      'Praha 15': ('praha', 'Praha 15'), 'Praha-Lysolaje': ('praha', 'Praha-Lysolaje'), 'Brno-střed': ('brno', 'Brno-střed'),
      'Vítkovice': ('ostrava', 'Vítkovice'), 'Severní Terasa': ('usti-nad-labem', 'Ústí n.L.-Severní Terasa'), 'Pardubice VI': ('pardubice', 'Pardubice VI')}
SOUD = {'Krajský soud v Brně': 'KS Brno', 'Krajský soud v Hradci Králové': 'KS Hradec Králové', 'pobočka Pardubice': 'KS HK, pob. Pardubice',
        'Krajský soud v Ostravě': 'KS Ostrava', 'pobočka Olomouc': 'KS Ostrava, pob. Olomouc', 'Krajský soud v Plzni': 'KS Plzeň',
        'Krajský soud v Praze': 'KS Praha', 'Krajský soud v Ústí nad Labem': 'KS Ústí n. L.', 'pobočka Liberec': 'KS ÚL, pob. Liberec',
        'Krajský soud v Českých Budějovicích': 'KS České Budějovice', 'Městský soud v Praze': 'MS Praha'}
KRAJ_SOUDU = {'KS Brno': {'Jihomoravský kraj', 'Zlínský kraj', 'Kraj Vysočina'}, 'KS Hradec Králové': {'Královéhradecký kraj'},
              'KS HK, pob. Pardubice': {'Pardubický kraj'}, 'KS Ostrava': {'Moravskoslezský kraj'}, 'KS Ostrava, pob. Olomouc': {'Olomoucký kraj'},
              'KS Plzeň': {'Plzeňský kraj', 'Karlovarský kraj'}, 'KS Praha': {'Středočeský kraj'}, 'KS Ústí n. L.': {'Ústecký kraj'},
              'KS ÚL, pob. Liberec': {'Liberecký kraj'}, 'KS České Budějovice': {'Jihočeský kraj'}, 'MS Praha': {'Hlavní město Praha'}}

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [('User-Agent', 'Mozilla/5.0 (research)')]


def get(url, data=None, raw=False):
    with op.open(url, data=data, timeout=90) as r:
        b = r.read()
    return b if raw else b.decode('utf-8', 'replace')


def hledej(text, obdobi):
    """Výsledky fulltextového hledání: {id dokumentu: text řádku výsledku}."""
    page = get(f'{NSS}/Home/Index?formular=1')
    body = (re.search(r'<form id="findform"[^>]*>(.*?)</form>', page, re.S) or [None, page])[1]
    SET = {'vyhledavaciSekce[3].vyhledavaciPodminka[0].vyhledavaciPodminkaHodnota[0].HodnotaText': text,
           'vyhledavaciSekce[1].vyhledavaciPodminka[0].vyhledavaciPodminkaHodnota[0].HodnotaDatumACasOd': obdobi[0],
           'vyhledavaciSekce[1].vyhledavaciPodminka[0].vyhledavaciPodminkaHodnota[0].HodnotaDatumACasDo': obdobi[1]}
    fields = []
    for t in re.findall(r'<input\b[^>]*>', body):
        n = re.search(r'name="([^"]*)"', t)
        if not n:
            continue
        typ = (re.search(r'type="([^"]*)"', t) or [None, 'text'])[1]
        if typ in ('radio', 'checkbox') and 'checked' not in t:
            continue
        name = html.unescape(n.group(1))
        fields.append((name, SET.get(name, html.unescape((re.search(r'value="([^"]*)"', t) or [None, ''])[1]))))
    res = get(f'{NSS}/Home/Index?formular=1&zobrazeniVysledkuVolba=2', urllib.parse.urlencode(fields).encode())
    params = json.loads('"' + re.search(r"currParams = '(.*?)';", res).group(1) + '"')
    view = re.search(r"currViewId = '(\d+)'", res).group(1)
    sort = (re.search(r"currSort = '([^']*)'", res) or [None, ''])[1]
    out = {}
    for p in range(60):
        rows = get(f'{NSS}/Home/MyResTRowsCont', urllib.parse.urlencode(
            {'vyhledavaciPodminky': params, 'zobrazeniVysledkuId': view, 'pageNum': p, 'resultOrder': sort}).encode())
        new = 0
        for tr in re.findall(r'<tr.*?</tr>', rows, re.S):
            ids = re.findall(r'/DokumentOriginal/Index/(\d+)', tr)
            if ids and ids[0] not in out:
                out[ids[0]] = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', tr))).strip()[:400]; new += 1
        if not new:
            break
    return out


def text(i, raw):
    pdf, txt = os.path.join(raw, f'{i}.pdf'), os.path.join(raw, f'{i}.txt')
    if not os.path.exists(pdf):
        open(pdf, 'wb').write(get(f'{NSS}/DokumentOriginal/Index/{i}', raw=True)); time.sleep(0.5)
    if not os.path.exists(txt):
        subprocess.run([shutil.which('pdftotext'), '-enc', 'UTF-8', '-layout', pdf, txt], capture_output=True)
    return re.sub(r'\s+', ' ', open(txt, encoding='utf-8', errors='ignore').read())


def stav(v):
    z = v.replace(' ', '').lower()
    if re.search(r'jeneplatn|vyslovujeseneplatnost|vyhlašuje|zazvolen|řádnězvolen|zvolenýmčlenem|pořadínáhradník', z): return 'vyhověno'
    if re.search(r'zamít(á|aj)', z): return 'zamítnuto'
    if re.search(r'odmít(á|aj)', z): return 'odmítnuto'
    if 'zastavuje' in z: return 'zastaveno'
    return ''


def _n(x):
    return re.sub(r'[\s\-–.]', '', x).lower()


def mapa_mc():
    """Normalizovaný název MČ/MO -> (slug města, název MČ podle registru); i bez předpony města (Severní Terasa, Neštěmice)."""
    out = {}
    for u in units.units():
        for m in u['mc']:
            nm = m['nazev']
            out[_n(nm)] = (u['slug'], nm)
            for pre in ('Ústí nad Labem', 'Brno', 'Plzeň'):
                if nm.startswith(pre + '-'):
                    out.setdefault(_n(nm[len(pre) + 1:]), (u['slug'], nm))
    return out


GEN_KONC = [('ně', 'eň'), ('a', ''), ('u', ''), ('y', 'a'), ('ě', 'eň'), ('a', 'o'), ('e', 'a'), ('i', 'e'), ('ku', 'ek'), ('í', 'e')]


def kandidati_jmena(nm):
    """Název obce z textu rozhodnutí -> možné tvary 1. pádu (genitiv: Šenova -> Šenov, Mostu -> Most, Plzně -> Plzeň, Brna -> Brno)."""
    nm = re.split(r'\.\s|\s(?:byl|byla|bylo|činila|řádně|soud|v návrhu|zaregistrován)', nm)[0].strip(' -–')
    nm = re.sub(r'^.*městské části\s+', '', nm)
    nm = re.sub(r'^(?:obce|města|městyse|statutárního města)\s+', '', nm).split(' a do ')[0].strip()
    out = [nm, GEN.get(nm, nm)]
    for a, b in GEN_KONC:
        if nm.endswith(a):
            out.append(nm[:-len(a)] + b)
    if '-' in nm:  # Frýdku-Místku -> Frýdek-Místek
        cs = [kandidati_jmena(x) for x in nm.split('-')]
        out += ['-'.join(z) for z in zip(*[(c + [c[0]] * 9)[:9] for c in cs])]
    return [x for i, x in enumerate(out) if x and x not in out[:i]]


def volebni(t, vy):
    """Řízení o neplatnosti volby / hlasování / voleb (ne místní referendum, zánik mandátu apod.)."""
    if re.search(r'místní\w* referend', t[:4000]) or re.search(r'zánik\w* mandátu', vy):
        return False
    return 'astupitel' in t


def main(rok):
    cfg = CFG[rok]
    raw = os.path.join(ROOT, 'data', 'raw', f'soudy{rok}')
    out = os.path.join(ROOT, 'soudy', f'podani_{rok}.csv')
    os.makedirs(raw, exist_ok=True)
    nalez = {}
    for q in DOTAZY:
        nalez.update(hledej(q, cfg['obdobi']))
    nalez = {k: t for k, t in nalez.items() if ' A ' in t and f'/{rok}' in t and k not in cfg['vyraz']}
    by_name = {}
    for u in units.units():
        for nm in {u['nazev'], u.get('nazev_plny') or u['nazev'], re.sub(r' \(okres .*\)$', '', u['nazev'])}:
            by_name.setdefault(nm, {})[u['slug']] = u
    MCM = mapa_mc()
    rows, vyr = [], 0
    for k, hdr in nalez.items():
        t = text(k, raw)
        v = re.search(r't ?a ?k ?t ?o ?:\s*(.{0,700})', t)
        vy = re.split(r'O ?d ?ů ?v ?o ?d ?n ?ě ?n ?í', v.group(1))[0] if v else ''
        if not volebni(t, vy):
            vyr += 1; continue
        spz = (re.search(rf'(\d+ A \d+/{rok})', hdr) or [None, ''])[1]
        soud = next((v for kk, v in SOUD.items() if kk in hdr), hdr)
        m = re.search(r'(?:do|zastupitelstva)\s+(?:Z|z)astupitelstva\s+(?:obce|města|městyse|městské části|městského obvodu|statutárního města)\s+([^,;()]{2,60}?)'
                      r'(?:,|\s+kona|\s+ve dnech|\s+ze dne|\s+v roce|\s+v\s|\s+ve\s|\s+vyplynulo|\s+bylo|\s+\()', t)
        nm = cfg['rucne'].get(k) or (m.group(1).strip() if m else '')
        slug, mc = cfg['rucne_slug'].get(k, ''), ''
        for c in ([nm] if k in cfg['rucne'] else kandidati_jmena(nm)):
            if _n(c) in MCM or c in by_name:
                nm = c; break
        if k in cfg['rucne_mc']:
            slug, mc = cfg['rucne_mc'][k]
        elif _n(nm) in MCM:
            slug, mc = MCM[_n(nm)]
        elif not slug and nm in by_name:
            kand = [u for u in by_name[nm].values() if u['kraj'] in KRAJ_SOUDU.get(soud, {u['kraj']})] or list(by_name[nm].values())
            if len(kand) > 1:
                kand = [u for u in kand if u.get('okres_nazev') and u['okres_nazev'] in t] or kand
            slug = kand[0]['slug'] if len(kand) == 1 else ''
        okr = sorted(set(re.findall(r'okrsk\w* (?:č\. ?)?(\d{1,5})', t)), key=int)
        prep = 'ano' if k in cfg['prepocet'] else ('ne' if cfg.get('prepocet_uplny') else '')
        rows.append(dict(soud=soud, spis=spz, obec=nm, slug=slug, mc=mc, rozhodnuti=cfg.get('rozh', {}).get(k) or stav(vy), prepocet=prep,
                         poznamka=cfg['pozn'].get(k, ''), okrsky=' '.join(okr[:12]), odkaz=f'{NSS}/DokumentOriginal/Index/{k}'))
    rows += cfg.get('navic', [])
    # stejná věc může mít ve vyhledávači více dokumentů (usnesení a opravné usnesení) – ponechat jeden řádek, přednostně s výrokem
    uniq = {}
    for r in rows:
        k = (r['soud'], r['spis'])
        if k not in uniq or (not uniq[k]['rozhodnuti'] and r['rozhodnuti']):
            uniq[k] = r
    rows = list(uniq.values())
    rows.sort(key=lambda x: (x['soud'], x['obec'], x['spis']))
    with open(out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    bez = [f"{r['spis']} ({r['obec'] or '?'})" for r in rows if not r['slug']]
    print(f'{len(rows)} řízení (vyřazeno jako nevolební {vyr}) -> {os.path.relpath(out, ROOT)}' + (f'; bez přiřazené obce: {", ".join(bez)}' if bez else ''))


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2022)
