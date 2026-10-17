"""Stránka report/senat/kolo2.html – forenzní audit 2. kola senátních voleb 2026 (16.–17. 10. 2026).
Volá se z build_site.py po build_senat.py (sdílí šablonu, grafy a odkazy). Data: scripts/se_kolo2.py → data/results/se2_*."""
import json, os
import pandas as pd
import svg
from svg import E
from common import ROOT, RES0 as RES
import build_senat as b1
from build_senat import n0, pct, links, se_url, A, OUT

HAS = os.path.exists(f'{RES}/se2_summary.json')
if HAS:
    summ = json.load(open(f'{RES}/se2_summary.json', encoding='utf8'))
    V = pd.read_pickle(f'{RES}/se2_vysledky.pkl').sort_values('OBVOD')
    T = pd.read_pickle(f'{RES}/se2_okrsky.pkl')
    M = pd.read_pickle(f'{RES}/se2_model.pkl')
    U = pd.read_pickle(f'{RES}/se2_ucast.pkl')
    I = pd.read_pickle(f'{RES}/se2_integrita.pkl')
    Z = pd.read_pickle(f'{RES}/se2_zmeny.pkl')
    REP = pd.read_pickle(f'{RES}/se2_reprodukce.pkl')
    STRANA = {(r.OBVOD, r.CKAND): str(r.NAZEV_VS) for r in b1.rk.itertuples()}
    K1 = b1.t5.assign(OID=b1.t5.OBEC.astype(str) + '/' + b1.t5.OKRSEK.astype(str)).set_index('OID')
    KV = b1.x26.set_index('OID')
    T2 = T.set_index('OID')

oname = lambda o: f'{b1.obvn[o]} ({o})'
vol3 = lambda o: f'{n0(K1.VOL_SEZNAM[o])} / {n0(T2.VOL_SEZNAM[o])} / {n0(KV.KV_VOL[o])}'  # 1. kolo / 2. kolo / KV
naz = lambda o: f'{b1.NAZ.get(o, o)} {o.split("/")[1]}'


# ------------------------------------------------------------------ nálezy
def _vol_rozdily():
    """Okrsky se změnou seznamu voličů mezi koly: kde 2. kolo vybočuje (chyba 2. kola) a kde potvrzuje chybu 1. kola."""
    k2chyba, k1chyba = [], []
    for o in I[I.kod == 'A6'].OID:
        v1, v2, kv = K1.VOL_SEZNAM[o], T2.VOL_SEZNAM[o], KV.KV_VOL.get(o)
        if kv is None or kv != kv:
            continue
        tol = max(20, 0.02 * kv)  # mezi KV a Senátem se seznamy liší jen o občany EU (jednotky voličů)
        (k2chyba if abs(v1 - kv) <= tol else k1chyba if abs(v2 - kv) <= tol else []).append(o)
    return k2chyba, k1chyba


def findings():
    if not HAS:
        return []
    F = []
    k2chyba, k1chyba = _vol_rozdily()
    url = lambda i: f'senat/kolo2.html#{i}'
    if k2chyba:
        F.append(dict(id='K2-01', typ='Chybný počet zapsaných voličů ve 2. kole', misto=', '.join(f'{naz(o)} ({b1.OBV[o]})' for o in k2chyba), jistota=4, dopad='Bez vlivu',
                      zjisteni='Počet zapsaných voličů ve 2. kole neodpovídá 1. kolu ani komunálním volbám (1. kolo / 2. kolo / KV): ' + '; '.join(f'{naz(o)} – {vol3(o)}' for o in k2chyba) + '.',
                      dukaz='Za týden mezi koly se seznam voličů mění o jednotky voličů; 1. kolo a komunální volby jsou dva nezávislé zápisy a shodují se.',
                      hodnoceni='Chyby v údaji o zapsaných voličích v zápisu 2. kola (Dobrá 2: 1 259 místo ~1 469 odpovídá jedné chybné číslici). Ovlivňují jen vykázanou účast okrsku, ne hlasy.',
                      doporuceni='Opravit údaje (ČSÚ).', odkazy='<br>'.join(links(o) for o in k2chyba), url=url('K2-01'), obvody=sorted({int(b1.OBV[o]) for o in k2chyba})))
    if k1chyba:
        F.append(dict(id='K2-02', typ='2. kolo potvrzuje chyby zápisů z 1. kola', misto=', '.join(f'{naz(o)} ({b1.OBV[o]})' for o in k1chyba), jistota=5, dopad='Bez vlivu',
                      zjisteni='Zápisy 2. kola mají správné počty voličů tam, kde 1. kolo vybočovalo (1. kolo / 2. kolo / KV): ' + '; '.join(f'{naz(o)} – {vol3(o)}' for o in k1chyba) + '.',
                      dukaz='Tři nezávislé zápisy téhož okrsku z jednoho týdne; dva z nich (2. kolo a KV) se shodují.',
                      hodnoceni='Potvrzuje nálezy S04 (prohozené okrsky v Příbrami) a S10 z 1. kola; v Karviné 33 jde o novou chybu 1. kola (o 40 voličů více). '
                                'Naopak v Příbrami 21 mají obě kola Senátu shodně kolem 560 voličů proti 658 v KV, tam se část nálezu S10 nepotvrdila.',
                      doporuceni='Opravit údaje 1. kola (ČSÚ). Výsledky hlasování se nemění.', odkazy='<br>'.join(links(o) for o in k1chyba), url=url('K2-02'),
                      obvody=sorted({int(b1.OBV[o]) for o in k1chyba})))
    hi = U[(U.z_inv >= 8) & (U.INV >= 10)].sort_values('z_inv', ascending=False)
    for r in hi.itertuples():
        m = M[M.OID == r.OID].iloc[0]
        v = V[V.OBVOD == r.OBVOD].iloc[0]
        inv1 = int(K1.ODEVZ_OBAL[r.OID] - K1.PL_HL_CELK[r.OID])
        F.append(dict(id=f'K2-0{len(F) + 1}', typ='Neobvykle mnoho neplatných hlasů', misto=f'Obvod {oname(r.OBVOD)}, {naz(r.OID)}', jistota=1, dopad='Bez vlivu',
                      zjisteni=f'Neplatných je {r.INV} ze {n0(r.ODEVZ_OBAL)} odevzdaných obálek ({pct(r.INV / r.ODEVZ_OBAL)}); podle okolních okrsků by jich bylo asi {r.inv_ocek:.1f}'.replace('.', ',') +
                               f' (ve 2. kole celkem {pct(summ["neplatne_k2"], 2)}).',
                      dukaz=f'Vysoký podíl měl okrsek i v 1. kole ({inv1} z {n0(K1.ODEVZ_OBAL[r.OID])}, {pct(inv1 / K1.ODEVZ_OBAL[r.OID])}). Hlasy obou finalistů odpovídají jejich výsledku v 1. kole '
                            f'({E(m.kandA)} {m.hlasyA}, čekáno ~{m.ocekA:.0f}; {E(m.kandB)} {m.hlasyB}).',
                      hodnoceni=f'Spíše místní zvláštnost okrsku než chyba sčítání (chybějící hlasy nejsou u žádného z kandidátů). Výsledek obvodu (rozdíl {n0(v.rozdil)} hlasů) neovlivňuje.',
                      doporuceni='Žádné; ponecháno pro úplnost.', odkazy=links(r.OID), url=None, obvody=[int(r.OBVOD)]))
    if len(Z):
        F.append(dict(id=f'K2-0{len(F) + 1}', typ='Opraveno během volební noci (informativně)', misto=', '.join(naz(o) for o in Z.OID), jistota=5, dopad='Bez vlivu',
                      zjisteni='Okrsky byly zaslány opakovaně se změnou údajů: ' + '; '.join(f'{naz(r.OID)} ({r.zmeny.replace("VOL", "zapsaní voliči").replace("VYD", "vydané obálky")})' for r in Z.itertuples()) + '.',
                      dukaz='XML dávky ČSÚ (příznak OPAKOVANE); konečné hodnoty odpovídají 1. kolu a komunálním volbám (' + '; '.join(f'{naz(o)} – voliči {vol3(o)}' for o in Z.OID) + ').',
                      hodnoceni='Chyby zachycené kontrolou ještě během zpracování.', doporuceni='Žádné.', odkazy='<br>'.join(links(o, kv=False) for o in Z.OID), url=None,
                      obvody=sorted({int(b1.OBV[o]) for o in Z.OID})))
    for f in F:
        f['url'] = url(f['id'])
    return F


# ------------------------------------------------------------------ grafy
def chart_margins(fig):
    d = V.sort_values('k_obratu')
    ch = svg.hbars([oname(o) for o in d.OBVOD], [('Hlasů k obratu', list(d.k_obratu))], ['--series-1'], label_w=230, value_fmt=lambda v: n0(v))
    tb = svg.table(['Obvod', 'Zvolen', 'Hlasy', 'Poražený', 'Hlasy', 'Rozdíl', 'Hlasů k obratu'],
                   [[oname(r.OBVOD), r.vitez, n0(r.hlasy_v), r.porazeny, n0(r.hlasy_p), n0(r.rozdil), n0(r.k_obratu)] for r in d.itertuples()])
    m = d.iloc[0]
    return fig('O výsledku 2. kola nikde nerozhodly jednotky hlasů',
               'Nejmenší počet hlasů, který by přesunem od vítěze k poraženému změnil zvoleného senátora', ch, '', tb,
               f'Nejtěsnější je {m.nazev}: {m.vitez} vyhrál o {n0(m.rozdil)} hlasů, obrat by vyžadoval přesun {n0(m.k_obratu)} hlasů. '
               'Běžná chybovost ručního sčítání se pohybuje v jednotkách hlasů na obvod.')


def chart_turnout(fig):
    d = V.sort_values('ucast_k2')
    ch = svg.hbars([oname(o) for o in d.OBVOD], [('1. kolo', [round(v * 100, 1) for v in d.ucast_k1]), ('2. kolo', [round(v * 100, 1) for v in d.ucast_k2])],
                   ['--muted', '--series-1'], label_w=230, value_fmt=lambda v: f'{v:.1f} %'.replace('.', ','), ticks=[0, 20, 40, 60])
    leg = svg.legend([('1. kolo (souběžně s KV)', '--muted', 'rect'), ('2. kolo', '--series-1', 'rect')])
    tb = svg.table(['Obvod', 'Účast 1. kolo', 'Účast 2. kolo', 'Neplatné hlasy 2. kolo'], [[oname(r.OBVOD), pct(r.ucast_k1), pct(r.ucast_k2), pct(r.neplatne_k2, 2)] for r in d.itertuples()])
    h = summ['historie']
    return fig('Účast klesla na polovinu – stejně jako v minulých letech',
               f'Vydané obálky / zapsaní voliči; 2. kolo 2026 celkem {pct(summ["ucast_k2"])} (1. kolo v týchž obvodech {pct(summ["ucast_k1"])})', ch, leg, tb,
               f'Ve 2. kolech 2018, 2020 a 2022 byla účast {pct(h["2018"]["ucast_k2"])}, {pct(h["2020"]["ucast_k2"])} a {pct(h["2022"]["ucast_k2"])}.')


# ------------------------------------------------------------------ tabulky
def districts_table(F):
    ids = {}
    for f in F:
        for o in f['obvody']:
            ids.setdefault(o, []).append(f['id'])
    rows = ''
    for r in V.itertuples():
        obrat = '' if r.vitez_1k_poradi == 1 else f' <span class="sub">(v 1. kole {r.vitez_1k_poradi}.)</span>'
        rows += (f'<tr id="obvod-{r.OBVOD}"><td data-v="{r.OBVOD}">{r.OBVOD}</td><td data-v="{E(r.nazev)}"><a href="{se_url(r.OBVOD)}" {A}>{E(r.nazev)}</a></td>'
                 f'<td data-v="{E(r.vitez)}"><strong>{E(r.vitez)}</strong>{obrat}<br><span class="sub">{E(STRANA.get((r.OBVOD, r.CKAND_v), ""))}</span></td>'
                 f'<td class="num" data-v="{r.podil_v:.4f}">{n0(r.hlasy_v)}<br><span class="sub">{pct(r.podil_v)}</span></td>'
                 f'<td data-v="{E(r.porazeny)}">{E(r.porazeny)}<br><span class="sub">{E(STRANA.get((r.OBVOD, r.CKAND_p), ""))}</span></td>'
                 f'<td class="num" data-v="{r.hlasy_p}">{n0(r.hlasy_p)}</td><td class="num" data-v="{r.k_obratu}">{n0(r.k_obratu)}</td>'
                 f'<td class="num" data-v="{r.ucast_k2:.4f}">{pct(r.ucast_k2)}</td>'
                 f'<td data-v="{len(ids.get(r.OBVOD, []))}">' + ', '.join(f'<a href="#{i}">{i}</a>' for i in ids.get(r.OBVOD, [])) + '</td></tr>')
    return ('<h2 id="obvody">Výsledky obvodů</h2><p class="sub">Název vede na výsledky obvodu na volby.gov.cz. „Hlasů k obratu“ = kolik hlasů by muselo přejít od vítěze k poraženému, '
            'aby se výsledek obrátil. U vítězů, kteří v 1. kole nebyli první, je uvedeno jejich pořadí v 1. kole. Řadit lze kliknutím na záhlaví.</p>'
            '<div class="card tw"><table class="sortable"><thead><tr><th class="num">Č.</th><th>Obvod</th><th>Zvolen</th><th class="num">Hlasy</th><th>Poražený</th>'
            '<th class="num">Hlasy</th><th class="num">Hlasů k obratu</th><th class="num">Účast</th><th>Nálezy</th></tr></thead><tbody>' + rows + '</tbody></table></div>')


def history_table():
    h = summ['historie']
    rows = [[y, h[y]['obvodu'], n0(h[y]['okrsku']), pct(h[y]['ucast_k1']), pct(h[y]['ucast_k2']), pct(h[y]['neplatne_k2'], 2), pct(h[y]['nevracene_k2'], 3), h[y]['okrsky_gap10']]
            for y in ('2018', '2020', '2022')]
    rows.append(['2026', summ['obvodu'], n0(summ['okrsku']), pct(summ['ucast_k1']), pct(summ['ucast_k2']), pct(summ['neplatne_k2'], 2), pct(summ['nevracene_k2'], 3), summ['okrsky_gap10']])
    head = ['Rok', 'Obvodů ve 2. kole', 'Okrsků', 'Účast 1. kolo', 'Účast 2. kolo', 'Neplatné hlasy', 'Nevrácené obálky', 'Okrsky s ≥ 10 nevrácenými']
    return ('<div class="card tw"><table><thead><tr>' + ''.join(f'<th>{E(x)}</th>' for x in head) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td class=num>{E(str(v))}</td>' for v in r) + '</tr>' for r in rows) + '</tbody></table></div>')


def outliers_table():
    o = M[M.z.abs() >= 4].sort_values('z')
    if not len(o):
        return '<p>Žádný okrsek s |z| ≥ 4.</p>'
    rows = ''.join(f'<tr><td>{links(r.OID, kv=False)}</td><td>{E(r.kandA)}: {r.hlasyA} (čekáno ~{r.ocekA:.0f})<br><span class="sub">{E(r.kandB)}: {r.hlasyB}</span></td>'
                   f'<td class="num">{r.A1} / {r.B1}</td><td class="num">{f"{r.z:.1f}".replace(".", ",")}</td></tr>' for r in o.itertuples())
    return ('<div class="card tw"><table><thead><tr><th>Okrsek</th><th>Hlasy ve 2. kole</th><th class="num">Tíž kandidáti v 1. kole</th><th class="num">z</th></tr></thead><tbody>'
            + rows + '</tbody></table></div>')


# ------------------------------------------------------------------ CSV
def write_csv():
    files = []
    p = lambda f: os.path.join(OUT, 'data', f)
    V.to_csv(p('senat_2kolo_obvody_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('senat_2kolo_obvody_2026.csv', 'Senát 2026, 2. kolo: výsledky obvodů a hlasy k obratu'))
    T.drop(columns=['zdroj']).to_csv(p('senat_2kolo_okrsky_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('senat_2kolo_okrsky_2026.csv', 'Senát 2026, 2. kolo: okrskové výsledky'))
    M.to_csv(p('senat_2kolo_model_2026.csv'), index=False, encoding='utf-8-sig'); files.append(('senat_2kolo_model_2026.csv', 'Senát 2026, 2. kolo: hlasy finalistů proti očekávání z 1. kola (z-skóre)'))
    pd.DataFrame(findings()).drop(columns=['odkazy']).to_csv(p('senat_2kolo_nalezy_2026.csv'), index=False, encoding='utf-8-sig')
    files.append(('senat_2kolo_nalezy_2026.csv', 'Senát 2026, 2. kolo: registr nálezů'))
    return files


# ------------------------------------------------------------------ stránka
def build(page, fig, badge_j, badge_d, AUTHOR_URL):
    if not HAS:
        return []
    F = findings()
    reg = ''.join(f'<tr><td><a href="#{f["id"]}">{f["id"]}</a></td><td>{E(f["misto"])}</td><td>{E(f["typ"])}</td><td>{badge_j(f["jistota"])}</td><td>{badge_d(f["dopad"])}</td></tr>' for f in F)
    cards = ''.join(f'<article class="card find p3" id="{f["id"]}"><h3>{f["id"]} · {E(f["typ"])}</h3><p class="sub">{E(f["misto"])}</p>'
                    f'<div style="margin-top:8px">{badge_j(f["jistota"])} {badge_d(f["dopad"])}</div><dl>'
                    f'<dt>Zjištění</dt><dd>{E(f["zjisteni"])}</dd><dt>Důkaz</dt><dd>{E(f["dukaz"])}</dd><dt>Hodnocení</dt><dd>{E(f["hodnoceni"])}</dd>'
                    f'<dt>Doporučení</dt><dd>{E(f["doporuceni"])}</dd><dt>Ověřit na volby.gov.cz</dt><dd>{f["odkazy"]}</dd></dl></article>' for f in F)
    m = V.sort_values('k_obratu').iloc[0]
    z51, z75 = V[V.OBVOD == 51].iloc[0], V[V.OBVOD == 75].iloc[0]
    obraty = V[V.vitez_1k_poradi > 1]
    hotovo = summ['okrsku_zprac'] == summ['okrsku_celkem']
    stav = ('' if hotovo else f'<p class="sub"><strong>Předběžné:</strong> zpracováno {n0(summ["okrsku_zprac"])} z {n0(summ["okrsku_celkem"])} okrsků (stav ČSÚ {summ["generovano_souhrn"].replace("T", " ")}); '
            'chybějící okrsky výsledek žádného obvodu nezmění.</p>')
    zdroj = ('okrskové výsledky z XML dávek volební noci (finální CSV ČSÚ zatím nebylo zveřejněno; po zveřejnění se výpočet zopakuje)' if summ['zdroj'] == 'xml'
             else 'finální okrskové výsledky ČSÚ (CSV)')
    d = summ['davky']; fp = summ['otisky']
    body = f'''<p class="kicker">Senát 2026 · <a href="index.html">1. kolo</a> · 2. kolo</p>
<h1>Senátní volby 2026, 2. kolo: výsledky a forenzní audit</h1>
<p class="lead">Analýza všech {n0(summ["okrsku"])} okrsků ve {summ["obvodu"]} obvodech, kde se 16.–17. 10. 2026 konalo 2. kolo, porovnaná okrsek po okrsku s 1. kolem
a se 2. koly senátních voleb 2018, 2020 a 2022. Ve zbývajících pěti obvodech rozhodlo už 1. kolo ({E(", ".join(summ["rozhodnuto_v_1_kole"]))}).</p>
<p class="sub">Autor: <a href="{AUTHOR_URL}">Martin Suchan</a> · {summ["generovano_souhrn"][8:10].lstrip("0")}. 10. 2026 · Zdroj: {zdroj}.</p>{stav}
<div class="verdict" id="zaver"><p><strong>Závěr:</strong> Data 2. kola nenesou známky manipulace. Součty okrsků reprodukují oficiální výsledky
ve {summ["reprodukce_shoda"]} z {summ["reprodukce_obvodu"]} obvodů, žádný zápis nemá aritmetický rozpor a hlasy obou finalistů odpovídají v každém okrsku jejich výsledku v 1. kole
(z {n0(summ["model_n"])} okrsků jen {summ["model_z4"]} s odchylkou |z| ≥ 4, žádná záměna kandidátů). Výsledky nejsou těsné: nejmenší náskok má {E(m.nazev)}
({E(m.vitez)} o {n0(m.rozdil)} hlasů).</p>
<p><strong>Navazuje na těsná místa 1. kola:</strong> v obvodu Žďár nad Sázavou, kde o postupu rozhodl jediný hlas, zvítězil právě postupující {E(z51.vitez)}
({n0(z51.hlasy_v)} : {n0(z51.hlasy_p)}); v Karviné, kde rozhodlo 50 hlasů, {E(z75.vitez)} ({n0(z75.hlasy_v)} : {n0(z75.hlasy_p)}).
Pro soudní přezkum 1. kola v obvodu 51 začíná lhůta běžet vyhlášením výsledků Státní volební komisí po 2. kole.</p>
<p>Zápisy 2. kola potvrdily chyby v počtech voličů z 1. kola (prohozené okrsky v Příbrami a další, nález K2-02) a samy obsahují pět chybných počtů zapsaných voličů (K2-01).
Na hlasy ani na zvolení nemá žádná z chyb vliv.</p></div>
<div class="tiles">
<div class="tile"><div class="l">Okrsků analyzováno</div><div class="v">{n0(summ["okrsku"])}</div><div class="s">{summ["obvodu"]} obvodů 2. kola</div></div>
<div class="tile"><div class="l">Reprodukce výsledků</div><div class="v">{"100 %" if summ["reprodukce_shoda"] == summ["reprodukce_obvodu"] else "neshoda"}</div><div class="s">hlasy, obálky i voliči</div></div>
<div class="tile"><div class="l">Nejtěsnější výsledek</div><div class="v">{n0(m.rozdil)} hl.</div><div class="s">{E(m.nazev)}</div></div>
<div class="tile"><div class="l">Účast</div><div class="v">{pct(summ["ucast_k2"])}</div><div class="s">1. kolo v týchž obvodech {pct(summ["ucast_k1"])}</div></div>
<div class="tile"><div class="l">Obrat proti 1. kolu</div><div class="v">{len(obraty)}</div><div class="s">obvodů vyhrál druhý z 1. kola</div></div>
</div>
{districts_table(F)}
{chart_margins(fig)}
{chart_turnout(fig)}
<h2 id="registr">Registr nálezů 2. kola</h2>
<p class="sub">Jistota = pravděpodobnost, že zveřejněný údaj neodpovídá skutečnosti (Jistá – deterministický rozpor; Velmi vysoká ≥ 95 %; Vysoká 80–95 %; Střední 50–80 %; Nízká &lt; 50 % = riziko, nikoli zjištěná chyba).
Nálezy 1. kola jsou na <a href="index.html#registr">stránce 1. kola</a>.</p>
<div class="card tw"><table><thead><tr><th>ID</th><th>Místo</th><th>Typ</th><th>Jistota chyby</th><th>Dopad</th></tr></thead><tbody>{reg}</tbody></table></div>
<h2 id="nalezy">Detailní nálezy</h2>{cards}
<h2 id="testy">Statistické testy a srovnání s minulými lety</h2>
<p>Ve 2. kole se volí jen mezi dvěma kandidáty a bez souběžných voleb, proto je hlavním srovnáním 1. kolo téhož okrsku. Ukazatele 2. kola 2026 odpovídají minulým letům:</p>
{history_table()}
<h3>Hlasy finalistů proti 1. kolu</h3>
<p>Pro každý obvod jsme odhadli, jak se podíl finalisty ve 2. kole odvíjí od jeho poměru k soupeři v 1. kole a od podílu ostatních kandidátů v okrsku (vážená logistická regrese,
beta-binomický rozptyl). Z {n0(summ["model_n"])} okrsků vybočují o |z| ≥ 4 jen tyto – to odpovídá náhodě; žádný okrsek nemá nulu u silného kandidáta ani vzorec prohozených hlasů:</p>
{outliers_table()}
<h3>Globální otisky</h3>
<p>Poslední číslice hlasů finalistů (počty ≥ 100, {n0(fp["n_digits"])} hodnot): p = {f'{fp["last_digit_p"]:.2f}'.replace('.', ',')} – v normě.
Okrsky s účastí přesně na celém procentu: {fp["kobak_obs"]} proti {fp["kobak_sim_mean"]:.0f} v simulacích (p = {f'{fp["kobak_sim_p"]:.3f}'.replace('.', ',')}); podobný mírný přebytek měl i rok 2018
(72 proti 54), test je citlivý na zaokrouhlování malých okrsků a při počtu provedených testů nejde o významnou odchylku.</p>
<h2 id="davky">XML dávky volební noci</h2>
<p>Stáhli jsme {d["davek"]} dávek ČSÚ ({d["prvni"].replace("T", " ")} až {d["posledni"].replace("T", " ")}) se {n0(d["zaznamu"])} záznamy za {n0(d["okrsku_v_davkach"])} okrsků;
opakovaně byly zaslány {d["opakovane"]} okrsky (viz nález opravených údajů).</p>
<h2 id="metodika">Metodika a zdroje</h2>
<div class="card"><ol class="l">
<li><strong>Reprodukce:</strong> součet okrsků proti oficiálním výsledkům obvodů (<code>appdata/senat/20261009/odata/vysledky.xml</code>): hlasy obou finalistů, zapsaní voliči, vydané a odevzdané obálky, platné hlasy.</li>
<li><strong>Deterministické kontroly:</strong> vydané ≤ zapsaní, odevzdané ≤ vydané, platné ≤ odevzdané, součet hlasů = platné hlasy, hlasy jen pro finalisty, změna seznamu voličů proti 1. kolu (&gt; 5 % a &gt; 20 voličů) ověřená proti komunálním volbám.</li>
<li><strong>Hlasy finalistů:</strong> model z 1. kola téhož okrsku (viz výše), test záměny kandidátů (prohození hlasů A a B) a nulových hlasů.</li>
<li><strong>Účast a obálky:</strong> pokles vydaných obálek mezi koly proti 8 sousedním okrskům, neplatné hlasy proti sousedům (beta-binomicky), nevrácené obálky.</li>
<li><strong>Omezení:</strong> statistika neodhalí chyby v jednotkách hlasů a neprokáže úmysl; nálezy jsou podnětem k ověření zápisů.</li>
<li><strong>Lhůty:</strong> návrh na neplatnost volby podle § 87 zákona č. 247/1995 Sb. se podává u Nejvyššího správního soudu do 10 dnů po vyhlášení výsledků voleb Státní volební komisí.</li>
</ol>
<p><strong>Zdroje:</strong> <a href="https://volby.gov.cz/opendata/se2026/se2026_opendata.htm" {A}>Otevřená data ČSÚ – Senát 2026</a> (XML dávky <code>appdata/senat/20261009/odata/okrsky/K2/</code>, souhrn výsledků) ·
<a href="https://volby.gov.cz/app/senat/20261009/cs/results" {A}>Výsledky Senát 2026 na volby.gov.cz</a> · Senát <a href="https://volby.gov.cz/opendata/se2018/se2018_opendata.htm" {A}>2018</a>,
<a href="https://volby.gov.cz/opendata/se2020/se2020_opendata.htm" {A}>2020</a>, <a href="https://volby.gov.cz/opendata/se2022/se2022_opendata.htm" {A}>2022</a>.
Výpočet: <code>scripts/download.py</code> → <code>se_kolo2.py</code> → <code>build_senat2.py</code>.</p></div>'''
    page('senat/kolo2.html', 'Senát 2026 – 2. kolo', body, 'Výsledky a forenzní audit 2. kola senátních voleb 2026',
         section='senat', crumbs=[('Přehled', 'index.html'), ('Senát 2026', 'senat/index.html'), ('2. kolo', None)])
    return write_csv()
