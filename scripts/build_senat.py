"""Stránka report/senat.html – forenzní audit 1. kola senátních voleb 2026 a srovnání s KV 2026.
Volá se z build_site.py (sdílí šablonu stránky, styly a grafy)."""
import json, os
import numpy as np, pandas as pd
import svg
from svg import E, fmt
from common import ROOT, RES

OUT = os.path.join(ROOT, 'report')
SE_APP = 'https://volby.gov.cz/app/senat/20261009/cs/results/'
SE_JSON = 'https://volby.gov.cz/appdata/senat/20261009/vysled/okrsek/'
KV_APP = 'https://volby.gov.cz/app/kv2026/cs/20261009/results/'
KV_JSON = 'https://volby.gov.cz/appdata/kv2026/20261009/vysled/okrsek/'
A = 'target="_blank" rel="noopener"'

n0 = lambda v: f'{int(round(v)):,}'.replace(',', ' ')
pct = lambda v, d=1: f'{v * 100:.{d}f} %'.replace('.', ',')

# ------------------------------------------------------------------ data
t5 = pd.read_pickle(os.path.join(ROOT, 'data/processed/se_t5_2026.pkl'))
rk = pd.read_pickle(os.path.join(ROOT, 'data/processed/se_rk_2026.pkl'))
obvn = pd.read_pickle(os.path.join(ROOT, 'data/processed/se_obv_2026.pkl')).set_index('OBVOD').NAZEV_OBV
co = pd.read_csv(os.path.join(ROOT, 'data/raw/se2026/SE2026ciselniky20261011_csv/csv/secoco.csv'), sep=';', encoding='cp1250')
KRAJ = co.drop_duplicates('OBEC').set_index('OBEC').KRAJ; OKRES = co.drop_duplicates('OBEC').set_index('OBEC').OKRES
X = {y: pd.read_pickle(f'{RES}/se_kv_{y}.pkl') for y in (2018, 2022, 2026)}
x26 = X[2026]
summ = json.load(open(f'{RES}/se_summary.json', encoding='utf8'))
fpr = {d['rok']: d for d in json.load(open(f'{RES}/se_fingerprints.json'))}
mg = pd.read_pickle(f'{RES}/se_margins.pkl')
integ = pd.read_pickle(f'{RES}/se_integrity.pkl')
swaps = pd.read_pickle(f'{RES}/se_swaps.pkl')
zeros = pd.read_pickle(f'{RES}/se_zeros.pkl')
inv = pd.read_pickle(f'{RES}/se_invalid.pkl')
bch = pd.read_pickle(f'{RES}/se_batch_changes.pkl')
recsw = pd.read_pickle(f'{RES}/se_record_swaps.pkl')
cand = {y: pd.read_pickle(f'{RES}/se_cand_{y}.pkl') for y in (2018, 2020, 2022, 2026)}
NAZ = x26.set_index('OID').NAZOBEC.to_dict()
OBV = x26.set_index('OID').OBVOD.to_dict()


def oname(o):
    return f'{obvn[o]} ({o})'


# ------------------------------------------------------------------ odkazy
def se_url(obvod, oid=None):
    if oid is None:
        return SE_APP + f'!_{int(obvod)}'
    obec, okr = oid.split('/')
    return SE_APP + f'!_{int(obvod)}_{obec}__{okr}'


def kv_url(oid):
    obec, okr = map(int, oid.split('/'))
    return KV_APP + f'!__0_{KRAJ[obec]}_{OKRES[obec]}_{obec}___{okr}'


def links(oid, kv=True):
    obvod = OBV[oid]; obec, okr = oid.split('/')
    s = (f'<a href="{se_url(obvod, oid)}" {A}>{E(NAZ.get(oid, obec))}, okrsek {okr} – Senát</a> '
         f'<a class="json" href="{SE_JSON}{obvod}/{obec}_{okr}.json" {A} title="Strojová data ČSÚ pro okrsek">(data)</a>')
    if kv and int(obec) in OKRES.index:
        s += (f' · <a href="{kv_url(oid)}" {A}>komunální volby</a> '
              f'<a class="json" href="{KV_JSON}{OKRES[int(obec)]}/{obec}_{okr}.json" {A} title="Strojová data KV pro okrsek">(data)</a>')
    return s


def dist_link(o):
    return f'<a href="{se_url(o)}" {A}>výsledky obvodu {E(oname(o))}</a>'


# ------------------------------------------------------------------ výpočty pro text
m = x26.KV_ODEVZ.notna()
S = x26[m]
tot = dict(kv_vol=S.KV_VOL.sum(), se_vol=S.VOL_SEZNAM.sum(), kv_vyd=S.KV_VYD.sum(), se_vyd=S.VYD_OBALKY.sum(),
           se_odevz=S.ODEVZ_OBAL.sum(), kv_odevz=S.KV_ODEVZ.sum(), vp=S.VP.sum(), pl=S.PL_HL_CELK.sum())
ratio = tot['se_odevz'] / tot['kv_odevz']
ratio_y = {y: X[y][X[y].KV_ODEVZ.notna()].ODEVZ_OBAL.sum() / X[y][X[y].KV_ODEVZ.notna()].KV_ODEVZ.sum() for y in X}
dist = S.groupby('OBVOD').agg(se=('ODEVZ_OBAL', 'sum'), kv=('KV_ODEVZ', 'sum'), sevyd=('VYD_OBALKY', 'sum'), kvvyd=('KV_VYD', 'sum'))
dist['r'] = dist.se / dist.kv
mg = mg.assign(nazev=[oname(o) for o in mg.OBVOD])
mg['presun_postup'] = mg.rozdil_2_3 // 2 + 1
mg['presun_50'] = np.where(mg.zvolen_1k, (mg.rozdil_nad_50 + 1) // 2, (-mg.rozdil_nad_50) // 2 + 1)


# ------------------------------------------------------------------ grafy
def chart_envelopes(fig):
    cats = ['KV: vydané obálky', 'KV: odevzdané obálky', 'Senát: vydané obálky', 'Senát: odevzdané obálky', 'Senát: platné hlasy']
    vals = [tot['kv_vyd'], tot['kv_odevz'], tot['se_vyd'], tot['se_odevz'], tot['pl']]
    ch = svg.hbars(cats, [('Počet', vals)], ['--series-1'], label_w=230, value_fmt=lambda v: n0(v))
    tb = svg.table(['Krok', 'Počet', 'Podíl z obálek KV'], [[c, n0(v), pct(v / tot['kv_odevz'])] for c, v in zip(cats, vals)])
    return fig('Kde se ztrácí 13 % obálek: většina voličů senátní obálku vůbec nepřevzala',
               f'Součty za {n0(len(S))} okrsků, v nichž se konaly obojí volby (9.–10. 10. 2026)', ch, '', tb,
               f'Rozdíl mezi vydanými komunálními a vydanými senátními obálkami ({n0(tot["kv_vyd"] - tot["se_vyd"])}) tvoří voliči, kteří senátní obálku '
               f'při hlasování nepřevzali. Dalších {n0(tot["se_vyd"] - tot["se_odevz"])} senátních obálek bylo vydáno, ale nevrátilo se do urny; '
               f'{n0(tot["se_odevz"] - tot["pl"])} odevzdaných obálek bylo neplatných nebo prázdných.')


def chart_districts(fig):
    d = dist.sort_values('r')
    cats = [oname(o) for o in d.index]; vals = [round(r * 100, 1) for r in d.r]
    ch = svg.hbars(cats, [('Senátní / komunální obálky', vals)], ['--series-1'], label_w=230, unit='',
                   value_fmt=lambda v: f'{v:.1f} %'.replace('.', ','), ticks=[0, 25, 50, 75, 100])
    tb = svg.table(['Obvod', 'Senát: odevzdané obálky', 'KV: odevzdané obálky', 'Poměr'],
                   [[oname(o), n0(r.se), n0(r.kv), pct(r.r)] for o, r in d.iterrows()])
    return fig('Poměr senátních a komunálních obálek podle obvodu',
               'Ve velkých městech (Praha, Plzeň, Brno) bere senátní obálku přes 95 % voličů komunálních voleb, na venkově zhruba čtyři pětiny', ch, '', tb)


def chart_ratio_hist(fig):
    xs = list(range(40, 122, 2))
    ser = []
    for y in (2018, 2022, 2026):
        xx = X[y][X[y].KV_ODEVZ.notna() & (X[y].KV_ODEVZ >= 50)]
        r = (xx.ODEVZ_OBAL / xx.KV_ODEVZ * 100).clip(40, 120.99)
        h = np.histogram(r, bins=list(range(40, 124, 2)))[0]
        ser.append((str(y), [round(v / len(xx) * 100, 2) for v in h]))
    ch = svg.lines(xs, ser, ['--series-1', '--series-2', '--series-3'], xlabel='Senátní / komunální obálky v okrsku (%)', ylabel='% okrsků')
    leg = svg.legend([('2018', '--series-1', 'line'), ('2022', '--series-2', 'line'), ('2026', '--series-3', 'line')])
    return fig('Rozdělení poměru v okrscích je ve všech třech letech podobné',
               'Okrsky s alespoň 50 odevzdanými obálkami KV; senátní volby 2018, 2022 a 2026 se konaly souběžně s komunálními (pokaždé jiná třetina obvodů)', ch, leg, '',
               'Pravý okraj (poměr nad 100 %) tvoří hlavně okrsky v nemocnicích a domovech seniorů a okrsky s voliči na voličský průkaz, kteří mohou hlasovat jen do Senátu.')


def chart_margins(fig):
    rows = []
    for r in mg.itertuples():
        if not r.zvolen_1k:
            rows.append((f'{r.nazev}: 2. vs 3. místo', r.rozdil_2_3, f'{r.druhy} – {r.treti}', r.presun_postup))
            rows.append((f'{r.nazev}: 1. místo do 50 %', -r.rozdil_nad_50, f'{r.prvni} (chybí do nadpoloviční většiny)', r.presun_50))
        else:
            rows.append((f'{r.nazev}: zvolen v 1. kole', r.rozdil_nad_50, f'{r.prvni} (rezerva nad 50 %)', r.presun_50))
    rows.sort(key=lambda t: t[3])
    top = rows[:12]
    ch = svg.hbars([t[0] for t in top], [('Stačí přesunout hlasů', [t[3] for t in top])], ['--series-1'], label_w=360, value_fmt=lambda v: n0(v))
    tb = svg.table(['Obvod a rozhodnutí', 'Kandidáti', 'Rozdíl hlasů', 'Stačí přesunout hlasů'], [[t[0], t[2], n0(t[1]), n0(t[3])] for t in rows])
    return fig('Kde o výsledku 1. kola rozhodují jednotky hlasů',
               'Nejmenší počet hlasů, který by přesunem mezi kandidáty změnil postup do 2. kola nebo zvolení v 1. kole', ch, '', tb,
               'Žďár nad Sázavou: o postupu rozhodl 1 hlas (Klement 11 373, Černý 11 372). Takový rozdíl je pod rozlišovací schopností jakékoli statistické kontroly.')


def chart_turnout(fig):
    xs = list(range(0, 100, 2))
    ser = []
    for y in (2018, 2020, 2022, 2026):
        h = np.array(fpr[y]['turnout_hist']); ser.append((str(y), [round(v / h.sum() * 100, 2) for v in h]))
    ch = svg.lines(xs, ser, ['--series-1', '--muted', '--series-2', '--series-3'], xlabel='Volební účast v okrsku (%)', ylabel='% okrsků')
    leg = svg.legend([('2018 (s KV)', '--series-1', 'line'), ('2020 (s krajskými)', '--muted', 'line'), ('2022 (s KV)', '--series-2', 'line'), ('2026 (s KV)', '--series-3', 'line')])
    return fig('Účast v okrscích: hladké jednovrcholové rozdělení bez podezřelých shluků',
               'Okrsky s alespoň 50 voliči; rok 2020 = stejné obvody jako 2026', ch, leg)


# ------------------------------------------------------------------ nálezy
def findings():
    F = []
    r51 = mg[mg.OBVOD == 51].iloc[0]
    gaps51 = integ[(integ.rok == 2026) & (integ.OBVOD == 51) & (integ.kod == 'S6')]
    F.append(dict(id='S01', typ='Rozhodl 1 hlas', misto=f'Obvod {oname(51)}', jistota=1, dopad='Těsný výsledek',
                  zjisteni=f'Do 2. kola postoupil Josef Klement (KDU-ČSL) s {n0(r51.v2)} hlasy, třetí Radek Černý má {n0(r51.v3)}. Rozdíl je 1 hlas z {n0(r51.platne)} platných.',
                  dukaz=f'Ve 265 okrscích obvodu jsme nenašli žádný deterministický rozpor ani záměnu kandidátů. V {len(gaps51)} okrscích se nevrátilo do urny 10 a více vydaných obálek '
                        '(např. Bystřice nad Pernštejnem 1 a 2: −33 a −40), to se ale sečtených hlasů netýká. Největší odchylka v hlasech Klementa a Černého '
                        '(Herálec: Černý 380 hlasů proti asi 199 podle okolí) odpovídá místní podpoře kandidáta ze Žďáru.',
                  hodnoceni='Nejde o zjištěnou chybu, ale o riziko: jediný chybně přiřazený, nezapočtený nebo nesprávně uznaný hlas v kterémkoli z 265 okrsků mohl rozhodnout. '
                            'Běžná chybovost ručního sčítání se pohybuje v jednotkách hlasů na obvod.',
                  doporuceni='Ověřit zápisy okrskových komisí v obvodu 51, v případě pochybností přepočet. Soudní přezkum: návrh k Nejvyššímu správnímu soudu (§ 87 a 88 zák. č. 247/1995 Sb.) do 10 dnů '
                             'po vyhlášení výsledků voleb Státní volební komisí, a to po 2. kole; předčasné návrhy NSS odmítá. Návrh může podat volič zapsaný v okrsku obvodu nebo volební strana.',
                  odkazy=dist_link(51)))
    r75 = mg[mg.OBVOD == 75].iloc[0]
    F.append(dict(id='S02', typ='Těsný postup', misto=f'Obvod {oname(75)}', jistota=1, dopad='Těsný výsledek',
                  zjisteni=f'Druhý Petr Kazík ({n0(r75.v2)}) postoupil o {n0(r75.rozdil_2_3)} hlasů, třetí skončila Mariam Szyja ({n0(r75.v3)}); stačilo by přesunout {n0(r75.presun_postup)} hlasů.',
                  dukaz='Ve 105 okrscích obvodu žádný rozpor ani záměna. Největší odchylky mezi oběma kandidáty jsou ±50 hlasů v jednotlivých okrscích a vyrovnávají se. '
                        'Ve Stonavě se nevrátilo 57 vydaných obálek (2020: 7).',
                  hodnoceni='Riziko, nikoli zjištěná chyba.', doporuceni='Při podnětu kandidáta přednostně ověřit zápisy z Karviné a Stonavy.', odkazy=dist_link(75)))
    r66 = mg[mg.OBVOD == 66].iloc[0]
    F.append(dict(id='S03', typ='Těsný postup + nevrácené obálky', misto=f'Obvod {oname(66)}', jistota=2, dopad='Těsný výsledek',
                  zjisteni=f'Martin Škurek ({n0(r66.v2)}) postoupil před Michaelem Kohajdou ({n0(r66.v3)}) o {n0(r66.rozdil_2_3)} hlasů. '
                           'V okrsku Šumvald bylo vydáno 615 senátních obálek, ale odevzdáno jen 473 – chybí 142 obálek, téměř tolik, kolik činí rozdíl.',
                  dukaz='Komunálních obálek bylo v Šumvaldu vydáno také přesně 615 a odevzdáno 611. Při senátních volbách 2020 chybělo v tomtéž okrsku jen 9 obálek. '
                        'Poměr odevzdaných senátních a komunálních obálek (77 %) je přitom vyšší než u sousedních okrsků (68 %).',
                  hodnoceni='Nejpravděpodobnější vysvětlení: komise zapsala jako vydané senátní obálky všem voličům, i těm, kteří je odmítli. Sečtené hlasy to neovlivňuje. '
                            'Méně pravděpodobné, ale v těsném obvodu podstatné: část obálek nebyla započtena.',
                  doporuceni='Ověřit zápis okrskové komise v Šumvaldu (počet obálek v urně).', odkazy=links('505218/1') + '<br>' + dist_link(66)))
    F.append(dict(id='S04', typ='Záměna okrskových zápisů', misto='Obvod Příbram (18), Příbram – okrsky 2 a 25', jistota=4, dopad='Bez vlivu',
                  zjisteni='Senátní výsledky okrsků 2 a 25 jsou zjevně prohozené: okrsek 2 má v senátních datech 492 zapsaných voličů, okrsek 25 má 719. '
                           'V komunálních volbách je to přesně naopak (724 a 492).',
                  dukaz='Historie potvrzuje komunální údaje: okrsek 2 měl 746 voličů (Senát 2020) a 740 (KV 2022), okrsek 25 525 a 518. '
                        'Sedí i vydané obálky: senátní okrsek 2 223 / komunální okrsek 25 226; senátní okrsek 25 263 / komunální okrsek 2 276.',
                  hodnoceni='Logický rozpor potvrzený dvěma zdroji. Chyba nejspíš vznikla při zadání čísla okrsku.',
                  doporuceni='Opravit data okrsků (ČSÚ). Oba okrsky leží ve stejném obvodu, součty a výsledek se tedy nemění.',
                  odkazy=links('539911/2') + '<br>' + links('539911/25')))
    F.append(dict(id='S05', typ='Překlep v počtu vydaných obálek', misto='Obvod Frýdek-Místek (69), Frýdek-Místek – okrsek 33', jistota=3, dopad='Bez vlivu',
                  zjisteni='Vydaných senátních obálek je zapsáno 250, odevzdaných 204. V komunálních volbách bylo ve stejném okrsku vydáno jen 222 obálek.',
                  dukaz='Senátních obálek nemohlo být vydáno více než komunálních (okrsek nemá voliče s voličským průkazem). Hodnota 205 místo 250 (přehozené číslice) '
                        'by dala rozdíl 1 obálky, běžný i v okolí.',
                  hodnoceni='Vysoká jistota překlepu v údaji o vydaných obálkách; ovlivňuje jen vykázanou účast (o 6 p. b.).', doporuceni='Opravit údaj (ČSÚ).',
                  odkazy=links('598003/33')))
    F.append(dict(id='S06', typ='Překlep v počtu vydaných obálek', misto='Obvod Plzeň-město (9), Plzeň 9-Malesice – okrsek 9001', jistota=3, dopad='Bez vlivu',
                  zjisteni='Vydaných senátních obálek je zapsáno 524, odevzdaných 423; v komunálních volbách 427 vydaných a 427 odevzdaných.',
                  dukaz='101 „ztracených“ obálek a víc vydaných senátních než komunálních obálek jsou spolu nepravděpodobné. Hodnota 424 (jedna číslice) vysvětluje oba rozpory.',
                  hodnoceni='Vysoká jistota překlepu; ovlivňuje jen vykázanou účast okrsku (72 % místo 58 %).', doporuceni='Opravit údaj (ČSÚ).', odkazy=links('559199/9001')))
    F.append(dict(id='S07', typ='Neobvykle mnoho neplatných obálek', misto='Obvod Praha 9 (24), Praha 19 – okrsek 19001', jistota=2, dopad='Bez vlivu',
                  zjisteni='Neplatných nebo prázdných je 136 z 548 senátních obálek (25 %); okolí by čekalo asi 30. V roce 2020 jich tu bylo 3.',
                  dukaz='David Smoljak má v okrsku 146 hlasů proti asi 231 podle okolí (−85), ostatní kandidáti jsou v normě nebo nad ní. '
                        'Deficit jednoho kandidáta a současný přebytek neplatných obálek odpovídá vzorci, kdy je balík lístků jednoho kandidáta omylem uznán za neplatný.',
                  hodnoceni='Střední jistota chyby. Alternativa: hromadně prázdné obálky (protest) nebo komunální lístky vložené do senátní obálky.',
                  doporuceni='Ověřit zápis; na výsledek vliv nemá: Smoljak postupuje a do zvolení v 1. kole mu chybělo 889 hlasů.', odkazy=links('547344/19001')))
    F.append(dict(id='S08', typ='Možná záměna hlasů dvou kandidátů', misto='Obvod Strakonice (12), Nišovice – okrsek 1', jistota=2, dopad='Bez vlivu',
                  zjisteni='Tomáš Fiala (č. 2) má 14 hlasů proti asi 65 podle okolí, Miroslav Ušatý (č. 3) 80 proti asi 23. Po prohození by oba odpovídali okolí.',
                  dukaz='Kandidáti jsou na hlasovacích lístcích pod sousedními čísly (2 a 3), což je typický zdroj záměny při přepisu zápisu. '
                        'Ušatý v obci nebydlí (Albrechtice nad Vltavou), místní vazba ale vyloučit nejde.',
                  hodnoceni='Střední jistota.', doporuceni='Ověřit zápis. Fiala byl zvolen v 1. kole s 55,4 %; oprava by jeho náskok jen zvýšila.', odkazy=links('536962/1')))
    F.append(dict(id='S09', typ='Záměna kandidátů opravená ČSÚ', misto='Obvod Pelhřimov (15), Bednáreček – okrsek 1', jistota=5, dopad='Bez vlivu',
                  zjisteni='Okrsek byl na volební noc zaslán dvakrát. První verze (dávka 13) měla 11 hlasů u kandidáta č. 2 (Hodáč) a 0 u č. 3 (Med); opravená verze (dávka 61) obráceně.',
                  dukaz='Rozdíl dávek XML ČSÚ (příznak OPAKOVANE). Konečná data odpovídají opravené verzi, která je s okolím v souladu (Med je silný kandidát obvodu).',
                  hodnoceni='Jistá záměna, opravená ještě během zpracování. Dokládá, že k záměnám dochází a kontrola je někdy zachytí.', doporuceni='Žádné.',
                  odkazy=links('561053/1', kv=False)))
    F.append(dict(id='S10', typ='Nesoulad seznamů voličů Senát × KV', misto='Žatec 7, Slušovice 2, Ostrožská Nová Ves 2, Příbram 21', jistota=2, dopad='Bez vlivu',
                  zjisteni='V senátních datech je o 95–111 zapsaných voličů méně než v komunálních, přestože se oba seznamy liší jen občany EU (obvykle o 0–3 voliče).',
                  dukaz='Historie potvrzuje komunální údaje: Žatec 7 – Senát 2020 869, KV 2022 820, KV 2026 795, Senát 2026 693; Slušovice 2 – 1 295 / 1 287 / 1 274 / 1 163; '
                        'Ostrožská Nová Ves 2 – 1 189 / 1 174 / 1 142 / 1 042 (rozdíl jediné číslice); Příbram 21 – 657 / 637 / 658 / 563.',
                  hodnoceni='Pravděpodobné chyby v údaji o zapsaných voličích v zápisu T/5. Ovlivňují jen vykázanou účast.', doporuceni='Opravit údaje (ČSÚ).',
                  odkazy='<br>'.join(links(o) for o in ['566985/7', '585777/2', '592463/2', '539911/21'])))
    F.append(dict(id='S11', typ='Neobvykle nízký podíl senátních obálek', misto='Podlesí, Únanov, Tři Dvory a další', jistota=1, dopad='Bez vlivu',
                  zjisteni='V Podlesí (obvod 18) odevzdalo senátní obálku 76 % voličů komunálních voleb, v okolních okrscích 99,7 %. Podobně Únanov (77 % proti 94 %) a Tři Dvory (75 % proti 94 %).',
                  dukaz='Rozdíl vzniká už při vydávání obálek (Podlesí: vydáno 442 senátních a 591 komunálních obálek), hlasy kandidátů odpovídají okolí.',
                  hodnoceni='Spíše rozdílná praxe komise (aktivní nabídka senátního lístku) než chyba. Nízká jistota chyby.', doporuceni='Žádné; ponecháno pro úplnost.',
                  odkazy='<br>'.join(links(o) for o in ['564486/1', '595021/1', '533769/1'])))
    return F


# ------------------------------------------------------------------ tabulky testů
def tests_table():
    I = integ.groupby(['rok', 'kod']).size()
    g = lambda y, k: int(I.get((y, k), 0))
    rows = []
    for y in (2018, 2020, 2022, 2026):
        c = cand[y]
        ivy = inv[inv.rok == y]
        sw = swaps[swaps.rok == y] if len(swaps) else swaps
        kvz = X[y] if y in X else None
        rows.append([y, n0(summ['reprodukce'][str(y)]['kandidatu']), '100 %',
                     n0(len(c)), f'{(c.z.abs() >= 5).mean() * 1000:.1f} ‰'.replace('.', ','), int((c.z <= -5).sum()),
                     int((zeros.rok == y).sum()), len(sw), int((ivy.z_inv >= 5).sum()),
                     g(y, 'S2'), g(y, 'S7'),
                     int((kvz.z_obal.abs() >= 5).sum()) if kvz is not None else '–',
                     int((recsw.rok == y).sum()) if kvz is not None else '–'])
    head = ['Rok', 'Kandidátů', 'Reprodukce', 'Buněk okrsek × kandidát', '|z| ≥ 5', 'z ≤ −5', 'Nulové hlasy', 'Záměny kandidátů',
            'Neplatné z ≥ 5', 'Odevzdáno > vydáno', '0 neplatných (≥ 300 obálek)', 'Senát × KV |z| ≥ 5', 'Záměny zápisů']
    return ('<div class="card tw"><table><thead><tr>' + ''.join(f'<th>{E(h)}</th>' for h in head) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td class=num>{E(str(v))}</td>' for v in r) + '</tr>' for r in rows) + '</tbody></table></div>')


def fp_table():
    rows = []
    for y in (2018, 2020, 2022, 2026):
        d = fpr[y]
        rows.append([y, n0(d['okrsku']), pct(d['ucast']), pct(d['neplatne']), int(d['klimek_hi']),
                     f"{d['last_digit_p']:.2f}".replace('.', ','), f"{d['bl2_mean']:.2f}".replace('.', ','),
                     f"{d['kobak_obs']} / {d['kobak_sim_mean']:.0f}".replace('.', ',')])
    head = ['Rok', 'Okrsků', 'Účast', 'Neplatné obálky', 'Klimek: účast i vítěz > 80 %', 'Poslední číslice p', '2BL průměr (Benford 4,19)', 'Celá % účasti: skutečnost / simulace']
    return ('<div class="card tw"><table><thead><tr>' + ''.join(f'<th>{E(h)}</th>' for h in head) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td class=num>{E(str(v))}</td>' for v in r) + '</tr>' for r in rows) + '</tbody></table></div>')


def swaps_table():
    if not len(swaps):
        return ''
    s = swaps[swaps.rok == 2026]
    note = {'593605/1': 'kandidát Fládr v obci bydlí – skutečná místní podpora', '536962/1': 'viz nález S08', '541991/1': 'kandidáti nemají sousední čísla, ostatní údaje okrsku sedí s KV; spíše místní podpora, záměna nepotvrzena'}
    rows = ''.join(f'<tr><td>{links(r.OID, kv=False)}</td><td>{E(r.kandA)} (č. {r.A}): {r.hlasyA} / ~{r.ocekA:.0f}</td><td>{E(r.kandB)} (č. {r.B}): {r.hlasyB} / ~{r.ocekB:.0f}</td>'
                   f'<td>{E(note.get(r.OID, ""))}</td></tr>' for r in s.itertuples())
    return ('<div class="card tw"><table><thead><tr><th>Okrsek</th><th>Kandidát A: zapsáno / okolí</th><th>Kandidát B: zapsáno / okolí</th><th>Posouzení</th></tr></thead><tbody>'
            + rows + '</tbody></table></div>')


def batch_table():
    rows = ''.join(f'<tr><td>{links(r.OID, kv=False)}</td><td class=num>{r.davka_pred} → {r.davka_po}</td><td>{E(r.cas_po.replace("T", " "))}</td><td>{E(r.zmeny)}</td></tr>'
                   for r in bch.itertuples())
    return ('<div class="card tw"><table><thead><tr><th>Okrsek</th><th>Dávka</th><th>Čas opravy</th><th>Změna</th></tr></thead><tbody>' + rows + '</tbody></table></div>')


# ------------------------------------------------------------------ CSV
def write_csv():
    files = []
    p = lambda f: os.path.join(OUT, 'data', f)
    cols = ['OID', 'NAZOBEC', 'OBVOD', 'NAZOBV', 'OKRSEK', 'VOL_SEZNAM', 'KV_VOL', 'VYD_OBALKY', 'KV_VYD', 'VP', 'ODEVZ_OBAL', 'KV_ODEVZ', 'PL_HL_CELK',
            'r', 'r_exp', 'z_obal', 'dvol', 'gap_se', 'gap_kv']
    x26[cols].merge(inv[inv.rok == 2026][['OID', 'INV', 'inv_ocek', 'z_inv']], on='OID', how='left').to_csv(p('senat_okrsky_kv_2026.csv'), index=False, encoding='utf-8-sig')
    files.append(('senat_okrsky_kv_2026.csv', 'Senát 2026: okrsky – obálky a voliči ve srovnání s KV, neplatné obálky, z-skóre'))
    pd.DataFrame(findings()).drop(columns=['odkazy']).to_csv(p('senat_nalezy_2026.csv'), index=False, encoding='utf-8-sig')
    files.append(('senat_nalezy_2026.csv', 'Senát 2026: registr nálezů'))
    mg.to_csv(p('senat_obvody_rezervy_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('senat_obvody_rezervy_2026.csv', 'Senát 2026: rozdíly hlasů rozhodující o postupu a zvolení'))
    c = cand[2026]; c[c.z.abs() >= 3].drop(columns=['ix']).to_csv(p('senat_kandidati_odchylky_2026.csv'), index=False, encoding='utf-8-sig')
    files.append(('senat_kandidati_odchylky_2026.csv', 'Senát 2026: hlasy kandidátů odchýlené od okolí (|z| ≥ 3)'))
    pd.read_pickle(f'{RES}/se_batches.pkl').to_csv(p('senat_xml_davky_2026.csv'), index=False, encoding='utf-8-sig')
    files.append(('senat_xml_davky_2026.csv', 'Senát 2026: všechny záznamy z XML dávek volební noci'))
    integ.to_csv(p('senat_integrita_2018_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('senat_integrita_2018_2026.csv', 'Senát 2018–2026: deterministické kontroly zápisů'))
    return files


# ------------------------------------------------------------------ stránka
def build(page, fig, badge_j, badge_d, AUTHOR_URL):
    F = findings()
    reg = ''.join(f'<tr><td><a href="#{f["id"]}">{f["id"]}</a></td><td>{E(f["misto"])}</td><td>{E(f["typ"])}</td><td>{badge_j(f["jistota"])}</td><td>{badge_d(f["dopad"])}</td></tr>' for f in F)
    cards = ''.join(f'<article class="card find p{1 if f["dopad"] != "Bez vlivu" else 3}" id="{f["id"]}"><h3>{f["id"]} · {E(f["typ"])}</h3><p class="sub">{E(f["misto"])}</p>'
                    f'<div style="margin-top:8px">{badge_j(f["jistota"])} {badge_d(f["dopad"])}</div><dl>'
                    f'<dt>Zjištění</dt><dd>{E(f["zjisteni"])}</dd><dt>Důkaz</dt><dd>{E(f["dukaz"])}</dd><dt>Hodnocení</dt><dd>{E(f["hodnoceni"])}</dd>'
                    f'<dt>Doporučení</dt><dd>{E(f["doporuceni"])}</dd><dt>Ověřit na volby.gov.cz</dt><dd>{f["odkazy"]}</dd></dl></article>' for f in F)
    rmin, rmax = dist.r.min(), dist.r.max()
    n_ok = len(t5)
    body = f'''<p class="kicker">Samostatná analýza · navazuje na <a href="index.html">audit komunálních voleb v Praze</a></p>
<h1>Senátní volby 2026, 1. kolo: forenzní audit a srovnání s komunálními volbami</h1>
<p class="lead">Analýza všech {n0(n_ok)} okrsků ve 27 senátních obvodech (9.–10. 10. 2026), {len(rk)} kandidátů a 156 XML dávek volební noci,
porovnaná okrsek po okrsku s komunálními volbami konanými ve stejný den a se senátními volbami 2018, 2020 a 2022.</p>
<p class="sub">Autor: <a href="{AUTHOR_URL}">Martin Suchan</a> · 11. 10. 2026 · Každý nález obsahuje proklik na výsledky okrsku na volby.gov.cz.</p>
<div class="verdict" id="zaver"><p><strong>Závěr:</strong> Data nenesou známky systematické ani koordinované manipulace. Oficiální výsledky všech 154 kandidátů
jsou ze součtu okrsků reprodukovatelné na 100 % a přepočet postupujících i zvolených v 1. kole souhlasí. Globální testy (Klimek, poslední číslice, 2BL, celá procenta účasti)
jsou v normě a odpovídají letům 2018–2022.</p>
<p><strong>Zásadní je těsnost výsledků:</strong> v obvodu <strong>Žďár nad Sázavou rozhodl o postupu do 2. kola jediný hlas</strong> (Klement 11 373, Černý 11 372),
v Karviné 50 hlasů a v Litovli 146. V Litovli je navíc okrsek Šumvald, kde se do urny nevrátilo 142 vydaných obálek.
Kromě toho jsme našli prohozené zápisy dvou okrsků v Příbrami, dva překlepy v počtu vydaných obálek, pravděpodobnou záměnu kandidátů v Nišovicích a podezřelý balík
neplatných obálek v Praze 19. Na postupující a zvolené nemá žádná z nalezených chyb vliv.</p></div>
<div class="tiles">
<div class="tile"><div class="l">Okrsků analyzováno</div><div class="v">{n0(n_ok)}</div><div class="s">27 obvodů, 100 % pokrytí, 5 019 spárováno s KV</div></div>
<div class="tile"><div class="l">Reprodukce výsledků</div><div class="v">100 %</div><div class="s">154 kandidátů, postup i zvolení v 1. kole</div></div>
<div class="tile"><div class="l">Nejtěsnější postup</div><div class="v">1 hlas</div><div class="s">Žďár nad Sázavou (51)</div></div>
<div class="tile"><div class="l">Senátní / komunální obálky</div><div class="v">{pct(ratio)}</div><div class="s">2018: {pct(ratio_y[2018])}, 2022: {pct(ratio_y[2022])}</div></div>
<div class="tile"><div class="l">Známky manipulace</div><div class="v">žádné</div><div class="s">chyby jsou ojedinělé a nahodilé</div></div>
</div>
<h2 id="obalky">Odpovídá počet senátních obálek komunálním? Ne – a je to normální</h2>
<div class="card"><p>V okrscích, kde se volilo do obou orgánů, bylo odevzdáno <strong>{n0(tot['kv_odevz'])} komunálních</strong> a jen <strong>{n0(tot['se_odevz'])} senátních obálek</strong>,
tedy o {pct(1 - ratio)} méně. Stejný jev je vidět i v minulých souběžných volbách (2018: {pct(1 - ratio_y[2018])}, 2022: {pct(1 - ratio_y[2022])}); letos je rozdíl o necelé 2 p. b. větší.</p>
<ul class="l">
<li><strong>Odmítnutí senátního lístku ({n0(tot['kv_vyd'] - tot['se_vyd'])} voličů, 12,0 %).</strong> Volič si v místnosti převezme jen obálku a lístky pro volby, kterých se chce účastnit.
Rozdíl vzniká už u stolu komise: vydaných senátních obálek je o tolik méně než komunálních.</li>
<li><strong>Nevrácené obálky ({n0(tot['se_vyd'] - tot['se_odevz'])}, 1,5 %).</strong> Senátní obálka vydaná, ale nevhozená do urny; u komunálních voleb jen {n0(S.KV_VYD.sum() - S.KV_ODEVZ.sum())}.
Část komisí zapisuje jako vydané senátní obálky všem voličům (v {n0((S.VYD_OBALKY == S.KV_VYD).sum())} okrscích se počty vydaných obálek shodují přesně).</li>
<li><strong>Rozdílné seznamy voličů (0,35 %).</strong> V komunálních volbách volí i občané EU s trvalým pobytem, v senátních ne
(seznam pro Senát je o {n0(tot['kv_vol'] - tot['se_vol'])} voličů kratší, nejvíce v centru Prahy).</li>
<li><strong>Opačným směrem působí voličské průkazy ({n0(tot['vp'])} voličů)</strong> a okrsky v nemocnicích a domovech seniorů: do Senátu lze volit kdekoli v obvodu, komunální volby jen v místě bydliště.</li>
</ul>
<p>Poměr se mezi obvody liší od {pct(rmin)} do {pct(rmax)}: ve velkých městech (Praha, Plzeň, Brno) bere senátní lístek téměř každý, na venkově s velkou účastí v komunálních volbách
zhruba čtyři pětiny voličů. Odchylky jednotlivých okrsků od okolí jsme použili jako další detektor chyb (nálezy S04–S06, S10, S11).</p></div>
{chart_envelopes(fig)}{chart_districts(fig)}{chart_ratio_hist(fig)}
<h2 id="tesne">Těsné výsledky a materialita</h2>
<p class="sub">Pro každý obvod: o kolik hlasů šlo při postupu do 2. kola (2. vs 3. místo) a při zvolení v 1. kole (hranice nadpoloviční většiny platných hlasů).
„Stačí přesunout“ = nejmenší počet hlasů, který by při přesunu od jednoho kandidáta k druhému změnil výsledek.</p>
{chart_margins(fig)}
<h2 id="registr">Registr nálezů</h2>
<p class="sub">Jistota = pravděpodobnost, že zveřejněný údaj neodpovídá skutečnosti (Jistá – deterministický rozpor; Velmi vysoká ≥ 95 %; Vysoká 80–95 %; Střední 50–80 %; Nízká &lt; 50 % = riziko, nikoli zjištěná chyba).</p>
<div class="card tw"><table><thead><tr><th>ID</th><th>Místo</th><th>Typ</th><th>Jistota chyby</th><th>Dopad</th></tr></thead><tbody>{reg}</tbody></table></div>
<h2 id="nalezy">Detailní nálezy</h2>{cards}
<h2 id="testy">Statistické testy a srovnání s minulými lety</h2>
<p>Stejné detektory jsme spustili na senátní volby 2018, 2020 a 2022 (pokaždé jiná třetina obvodů; 2020 = stejné obvody jako 2026). Rok 2026 nevybočuje: počet odlehlých hlasů kandidátů je
naopak nejnižší, i když kandidátů je méně (5,7 na obvod proti 8,8 v roce 2018), a to i v přepočtu na jednu buňku okrsek × kandidát.</p>
{tests_table()}
<p class="sub">Model hlasů kandidátů: očekávaný podíl kandidáta v okrsku z 8 nejbližších okrsků téhož obvodu (těžiště okrsků 2022), beta-binomická overdisperze odhadnutá robustně pro každého kandidáta.
Kladné odchylky jsou většinou bydliště kandidáta nebo sousední obce. Záměna kandidátů = prohození hlasů dvou kandidátů sníží součet z² alespoň o 40 a obě hodnoty se vrátí do pásma |z| &lt; 3.</p>
<h3>Kandidáti na záměnu hlasů v roce 2026</h3>{swaps_table()}
<h3>Globální otisky (election forensics)</h3>{fp_table()}
<p class="sub">Klimek: okrsky s účastí i podílem vítěze obvodu nad 80 % (vzorec „vhazování“) – žádné. Poslední číslice: počty hlasů ≥ 100, očekávání z vyhlazené hustoty
(klesající hustota mírně zvýhodňuje nižší číslice); p &gt; 0,05 = v normě, mírná odchylka jen v roce 2022. 2BL: průměr druhé číslice, vždy kolem 4,0, ve všech letech stejně. Celá procenta účasti (Kobak a kol.): počet okrsků s účastí přesně na celém procentu proti 300 binomickým simulacím – bez přebytku.</p>
{chart_turnout(fig)}
<h2 id="davky">XML dávky volební noci</h2>
<p>Stáhli jsme všech 156 dávek ČSÚ ({summ['davky']['prvni'].replace('T', ' ')} až {summ['davky']['posledni'].replace('T', ' ')}). Obsahují 5 025 záznamů za 5 021 okrsků; konečné hodnoty se shodují s finálními daty CSV (0 neshod).
Čtyři okrsky byly zaslány opakovaně:</p>{batch_table()}
<h2 id="metodika">Metodika, omezení a zdroje</h2>
<div class="card"><ol class="l">
<li><strong>Reprodukce:</strong> součet okrsků proti oficiálním výsledkům kandidátů (registr <code>serk</code>) a nezávislý přepočet postupu (nadpoloviční většina, jinak první dva).</li>
<li><strong>Deterministické kontroly zápisů T/5:</strong> vydané ≤ zapsaní, odevzdané ≤ vydané, platné ≤ odevzdané, součet kandidátů = platné hlasy, hlasy jen pro registrované kandidáty, úplnost okrsků podle číselníku obvodů.</li>
<li><strong>Párování s KV:</strong> okrsek = kód obce/MČ + číslo okrsku; spárováno 5 019 z 5 021 (obce Píšť a Krchleby v datech KV 2026 chybí, komunální volby se tam patrně nekonaly).
Detektory: poměr odevzdaných obálek vůči 8 sousedům (robustní z), rozdíl seznamů voličů, záměna zápisů dvou okrsků (seznam voličů A odpovídá KV okrsku B a naopak), vydané senátní obálky &gt; vydané komunální.</li>
<li><strong>Hlasy kandidátů:</strong> prostorový model vůči sousedům, test nulových hlasů, test záměny dvou kandidátů, test neplatných obálek (balík uznaný za neplatný).</li>
<li><strong>Historie:</strong> senátní volby 2020 ve stejných obvodech, KV 2022, souběžné volby 2018 a 2022 pro srovnání četnosti nálezů.</li>
<li><strong>Omezení:</strong> statistika neprokáže úmysl ani neodhalí chyby v jednotkách hlasů. Bez originálních zápisů a lístků nelze žádnou chybu potvrdit definitivně; nálezy jsou podnětem k ověření.
U výsledku rozhodnutého 1 hlasem nemůže žádná analýza dat nahradit přepočet.</li>
<li><strong>Lhůty:</strong> návrh na neplatnost hlasování nebo volby podle § 87 zákona č. 247/1995 Sb. se podává u Nejvyššího správního soudu do 10 dnů po vyhlášení výsledků voleb Státní volební komisí.
U senátních voleb se výsledky vyhlašují až po 2. kole a dřívější návrhy NSS odmítá jako předčasné. V konkrétním případě doporučujeme právní konzultaci.</li>
</ol>
<p><strong>Zdroje:</strong> <a href="https://volby.gov.cz/opendata/se2026/se2026_opendata.htm" {A}>Otevřená data ČSÚ – Senát 2026</a> (set5, serk, secoco, XML dávky
<code>appdata/senat/20261009/odata/okrsky/K1/</code>) ·
<a href="https://volby.gov.cz/opendata/kv2026/kv2026_opendata.htm" {A}>Otevřená data ČSÚ – KV 2026</a> ·
<a href="https://volby.gov.cz/opendata/se2020/se2020_opendata.htm" {A}>Senát 2020</a> · <a href="https://volby.gov.cz/opendata/se2022/se2022_opendata.htm" {A}>Senát 2022</a> ·
<a href="https://volby.gov.cz/opendata/se2018/se2018_opendata.htm" {A}>Senát 2018</a> · <a href="https://volby.gov.cz/app/senat/20261009/cs/results" {A}>Výsledky Senát 2026 na volby.gov.cz</a> ·
<a href="https://www.zakonyprolidi.cz/cs/1995-247" {A}>Zákon č. 247/1995 Sb.</a> (§ 87, § 88). Výpočet: <code>scripts/se_etl.py</code> → <code>se_audit.py</code> → <code>build_senat.py</code>.</p>
<p class="sub">Odkazy na okrsky: Senát <code>results/!_&lt;obvod&gt;_&lt;kód obce nebo MČ/MO&gt;__&lt;okrsek&gt;</code>, komunální volby <code>results/!__0_&lt;kraj&gt;_&lt;okres&gt;_&lt;kód obce nebo MČ/MO&gt;___&lt;okrsek&gt;</code>.</p></div>'''
    page('senat.html', 'Senát 2026 – 1. kolo', body, 'Forenzní audit 1. kola senátních voleb 2026 a srovnání s komunálními volbami',
         brand='Forenzní audit · Senát 2026, 1. kolo')
    return write_csv()
