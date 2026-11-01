"""Aktualizace stavu soudních řízení ke komunálním volbám 2026 z elektronických úředních desek soudů.

Použití:  python scripts/soudy_stav.py [--zapsat]

Pro každé řízení ze soudy/podani_2026.csv:
  - stáhne aktuální výpis úřední desky příslušného soudu (včetně poboček) přes API infodeska.gov.cz,
  - najde vyvěšená usnesení a rozsudky, stáhne je do data/raw/soudy/ a vytáhne z nich výrok („takto:“),
  - zapíše přehled do soudy/stav_<datum>.csv (spis, dokumenty, navržený stav, výrok).
S --zapsat doplní navržený stav a datum do prázdných sloupců rozhodnuti / datum_rozhodnuti v soudy/podani_2026.csv
(ručně vyplněné hodnoty nepřepisuje).

Text z PDF se získává programem pdftotext (Poppler); když chybí, výrok se nevytáhne a ve výstupu zůstane jen seznam dokumentů.
Úřední deska ukazuje jen právě vyvěšené dokumenty – kontrolu je proto vhodné spouštět průběžně, než soudy dokumenty svěsí.
"""
import csv, datetime, json, os, re, shutil, subprocess, sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CSV = os.path.join(ROOT, 'soudy', 'podani_2026.csv')
RAW = os.path.join(ROOT, 'data', 'raw', 'soudy')
API = 'https://infodeska.gov.cz/eudpub/api/v1/vyveseni'
# hlavní soud -> úřední desky, na kterých se jeho volební věci vyvěšují (pobočky mají vlastní desku)
DESKY = {'201000': ['201000'], '202000': ['202000'], '203000': ['203000', '203001'], '204000': ['204000'],
         '205000': ['205000', '205001'], '206000': ['206000', '206001'], '207000': ['207000', '207001', '207002'],
         '208000': ['208000', '208001']}
PDFTOTEXT = shutil.which('pdftotext')


def vyveseni(kod):
    req = urllib.request.Request(f'{API}/vyhledej', data=json.dumps({'kodSubjektu': kod}).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def text(soubor_id):
    os.makedirs(RAW, exist_ok=True)
    pdf = os.path.join(RAW, soubor_id + '.pdf')
    if not os.path.exists(pdf):
        urllib.request.urlretrieve(f'{API}/soubor/{soubor_id}/download', pdf)
    if not PDFTOTEXT:
        return ''
    txt = pdf[:-4] + '.txt'
    if not os.path.exists(txt):
        subprocess.run([PDFTOTEXT, '-enc', 'UTF-8', pdf, txt], capture_output=True)
    return re.sub(r'\s+', ' ', open(txt, encoding='utf-8', errors='ignore').read()) if os.path.exists(txt) else ''


def vyrok(t):
    """Výrok rozhodnutí: text za „takto:“ v usnesení či rozsudku (ne návrh výroku citovaný z podání)."""
    if not re.search(r'U ?S ?N ?E ?S ?E ?N ?Í|R ?O ?Z ?S ?U ?D ?E ?K', t[:1500]):
        return ''
    m = re.search(r't ?a ?k ?t ?o ?:\s*(.{0,600})', t)
    return re.split(r'O ?d ?ů ?v ?o ?d ?n ?ě ?n ?í', m.group(1))[0].strip() if m else ''


def stav(v):
    if re.search(r'je neplatn|[Vv]yslovuje se neplatnost|vyhlašuje se|za zvolen', v): return 'vyhověno'
    if re.search(r'z ?a ?m ?í ?t ?á', v): return 'zamítnuto'
    if re.search(r'o ?d ?m ?í ?t ?á', v): return 'odmítnuto'
    if 'zastavuje' in v: return 'zastaveno'
    if 'postupuje' in v: return 'postoupeno'
    return ''


def main():
    rows = list(csv.DictReader(open(CSV, encoding='utf-8-sig')))
    desky = {}
    for kod in sorted({r['soud_kod'] for r in rows}):
        for d in DESKY[kod]:
            try:
                desky[d] = vyveseni(d)
            except Exception as e:  # pobočka bez vlastní desky apod.
                print(f'  deska {d}: {e}')
                desky[d] = []
    out = []
    for r in rows:
        spis = r['spis'].replace('/2026', '')
        pat = re.compile(r'^' + re.escape(spis).replace(r'\ ', r'\s?') + r'/2026')
        docs = {}
        for d in DESKY[r['soud_kod']]:
            for x in desky[d]:
                if pat.match(x['znacka'] or ''):
                    for s in x['soubory']:
                        docs[s['id']] = (x['datumOd'][:10], x['popis'] or '', s['nazev'])
        rozh = []
        # popisy dokumentů se mezi soudy liší (usnesení bývá i jako „Dokument“), proto se výrok hledá ve všech
        for sid, (dat, popis, nazev) in sorted(docs.items(), key=lambda kv: kv[1][0]):
            v = vyrok(text(sid))
            if v:
                rozh.append((dat, stav(v), v))
        konec = [x for x in rozh if x[1]]
        posl = konec[-1] if konec else (rozh[-1] if rozh else ('', '', ''))
        out.append(dict(soud=r['soud'], spis=r['spis'], obec=r['obec'], mc=r['mc'], vztah=r['vztah'], dokumentu=len(docs),
                        rozhodnuti_navrh=posl[1], datum=posl[0], vyrok=posl[2][:300]))
        if '--zapsat' in sys.argv and posl[1] and not r['rozhodnuti']:
            r['rozhodnuti'], r['datum_rozhodnuti'] = posl[1], posl[0]
    dnes = datetime.date.today().isoformat()
    path = os.path.join(ROOT, 'soudy', f'stav_{dnes}.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, list(out[0])); w.writeheader(); w.writerows(out)
    if '--zapsat' in sys.argv:
        with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    n = sum(1 for o in out if o['rozhodnuti_navrh'])
    print(f'{len(out)} řízení, {n} s rozhodnutím na desce -> {os.path.relpath(path, ROOT)}')
    if not PDFTOTEXT:
        print('  pdftotext nenalezen – výroky nebyly vytaženy')


if __name__ == '__main__':
    main()
