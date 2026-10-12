"""Consolidate all detectors into one prioritised findings register (2026) with confidence & materiality."""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import RES, load, MAGISTRAT

Y = 2026
JISTOTA = {5: 'Jistá (deterministický rozpor)', 4: 'Velmi vysoká (≥ 95 %)', 3: 'Vysoká (80–95 %)', 2: 'Střední (50–80 %)', 1: 'Nízká (< 50 %)'}


def build():
    d = load(Y); cm = d['councils']; ros = d['ros']
    zname = lambda zk: 'Zastupitelstvo hl. m. Prahy' if zk // 100 == MAGISTRAT else f'Zastupitelstvo MČ {cm.NAZEVZAST[zk]}'
    mcmap = d['t3'].drop_duplicates('OID').set_index('OID').MC
    mat = pd.read_pickle(f'{RES}/materiality_{Y}.pkl')
    matd = {r.id: r for r in mat.itertuples()}
    F = []

    def add(**k):
        k.setdefault('MC', mcmap.get(k.get('OID'), ''))
        F.append(k)

    # ---- material / priority findings (hand-verified in deep-dives) ----
    add(id='N01', priorita=1, typ='Překlep – vložená číslice', ZK=50022401, OID='500224/10043', zastupitelstvo=zname(50022401),
        subjekt='Naše Praha 10 – kand. č. 24 Miroslav Křehlík',
        zjisteni='Kandidát má v okrsku 10043 zapsáno 165 hlasů, jeho sousedé na kandidátní listině 16 a 15; ve všech ostatních okrscích Prahy 10 '
                 'odpovídá jeho počet hlasů přesně počtu lístků s křížkem u strany (poměr ≈ 1,0, žádné preferenční hlasy). Hodnota 165 vznikne z 16 nebo 15 vložením jedné číslice.',
        dukaz='Poměr k základu strany 11,0× (v ostatních okrscích nejvýše 1,25×); odebráním jedné číslice vznikne hodnota 16.', jistota=4,
        umysl='Nízká – vzorec odpovídá překlepu; chyba však shodou okolností posouvá stranu právě nad 5% hranici',
        dopad='MĚNÍ SLOŽENÍ ZASTUPITELSTVA: Naše Praha 10 je po opravě pod 5 % (k pádu pod hranici stačila ztráta 105 hlasů) → ztrácí 2 mandáty '
              '(I. Cabrnochová, B. Zoufalík); mandát získají JSME PRAHA 10 (M. Žilinová) a SPD pro Prahu 10 (J. Nerušil). '
              'Změna nastane, kdykoli je skutečný počet ≤ 60 hlasů.', dopad_kat='Mění mandáty',
        doporuceni='Okamžitě ověřit zápis T/3 okrsku 10043 a přepočítat hlasy kandidáta; podnět ČSÚ/MV, případně návrh k Městskému soudu v Praze (§ 60, lhůta 10 dnů od vyhlášení výsledků SVK).')
    add(id='N02', priorita=1, typ='Chybějící balík hlasovacích lístků', ZK=54738701, OID='547387/15003', zastupitelstvo=zname(54738701),
        subjekt='Patnáctka náš domov (a okrsek jako celek)',
        zjisteni='Na lístku MČ připadá na platný lístek jen 60 % možných hlasů (sousedé 97 %, tentýž okrsek v roce 2022: 90 %). '
                 'Chybí zhruba 6 090 hlasů, tj. přibližně 196 lístků. Patnáctka má rovnoměrně ~71 hlasů na kandidáta, v sousedních okrscích 214–287.',
        dukaz='z(hlasy/lístek) = −31 (nejextrémnější hodnota ze všech 2 240 záznamů); deficit strany 191 lístků odpovídá deficitu okrsku 196 lístků (shoda 97 %)', jistota=4,
        umysl='Nízká – typická chyba přepisu (nezapočtený balík / vypadlá stovka u počtu lístků strany)',
        dopad='MŮŽE ZMĚNIT SLOŽENÍ: pokud alespoň 176 z ~196 chybějících lístků patřilo Patnáctce, získá 17. mandát na úkor ANO 2011 (M. Nauč). '
              'Při menším podílu se mandáty nemění.', dopad_kat='Může změnit mandáty',
        doporuceni='Přepočítat hlasovací lístky MČ v okrsku 15003; ověřit zápis T/3.')
    add(id='N03', priorita=2, typ='Nulové hlasy stran na konci lístku', ZK=MAGISTRAT * 100 + 1, OID='500089/2038', zastupitelstvo=zname(MAGISTRAT * 100 + 1),
        subjekt='ANO 2011 (0 hlasů), SEN PRO PRAHU (0), strany č. 19–24',
        zjisteni='Všechny strany na konci magistrátního lístku (č. 19–24) mají 0 nebo téměř 0 hlasů, včetně ANO 2011 (sousední okrsky ~10,6 %, '
                 'na lístku MČ ve stejném okrsku 18,5 %). Okrsku chybí zhruba 3 600 hlasů (56 lístků), což přesně odpovídá nezapsaným stranám.',
        dukaz='P(0 hlasů | očekávaných 24 lístků) < 0,001 i po korekci na overdisperzi; z(magistrát vs MČ) = −7,8; deficit hlasů/lístek z = −12,9', jistota=4,
        umysl='Nízká – identická chyba byla téhož večera zachycena a opravena v okrsku Praha 10/10034 (SPOLU 0 → 4 099)',
        dopad='Bez vlivu na mandáty (ANO by na další mandát potřebovalo +297 568 hlasů). Preferenční hlasy kandidátů ANO ovlivňuje jen o ~25–40 hlasů.',
        dopad_kat='Bez vlivu', doporuceni='Opravit zápis (podnět ČSÚ / MV); zařadit do školení komisí – kontrola „všechny strany zapsány“.')

    S = pd.read_pickle(f'{RES}/stacks_{Y}.pkl'); S = S[S.tri != 'slaby'].sort_values('z_vpb')
    i = 4
    for r in S.itertuples():
        if r.OID == '547387/15003':
            continue
        mid = f'S-{r.OID}-{r.ZK}-{r.strana}-kons'
        m = matd.get(mid)
        add(id=f'N{i:02d}', priorita=2 if r.tri == 'silny' else 3, typ='Chybějící balík hlasovacích lístků', ZK=r.ZK, OID=r.OID,
            zastupitelstvo=zname(r.ZK), subjekt=r.nazev,
            zjisteni=f'Strana má v okrsku jen ~{r.pb_obs:.0f} lístků s křížkem u strany (kandidáti mají po ~{r.pb_obs:.0f} hlasech), očekáváno ~{r.pb_ocek:.0f}; '
                     f'okrsku současně chybí hlasy zhruba {r.chybi_listku_okrsek:.0f} lístků.',
            dukaz=f'z(strana) = {r.z_strana:.1f}; z(hlasy/lístek) = {r.z_vpb:.1f}; shoda obou deficitů {100 * r.shoda:.0f} %',
            jistota=4 if r.tri == 'silny' else 3, umysl='Nízká – opakující se typ chyby (Praha 2018: 8, 2022: 5, 2026: 8 případů); chyby postihují různé strany',
            dopad=('MĚNÍ ' + m.detail) if m is not None and (m.zmena_mandatu or m.zmena_zvolenych) else
                  f'Bez vlivu na mandáty (straně chybí řádově {r.chybi_listku_strana * min(int(cm.MANDATY[r.ZK]), int(ros[(ros.ZK == r.ZK) & (ros.POR_STR_HL == r.strana)].NCAND.iloc[0])):,.0f} hlasů).'.replace(',', ' '),
            dopad_kat='Mění mandáty' if m is not None and m.zmena_mandatu else 'Bez vlivu',
            doporuceni='Opravit zápis, případně přepočítat v rámci soudního přezkumu.')
        i += 1

    # typos: individually listed if material, else aggregated
    T = pd.read_pickle(f'{RES}/typos_{Y}.pkl')
    T['id_m'] = [f'T-{r.OID}-{r.ZK}-{r.strana}-{r.porcislo}' for r in T.itertuples()]
    for r in T.itertuples():
        m = matd.get(r.id_m)
        if m is not None and m.zmena_zvolenych and r.OID != '500224/10043':
            add(id=f'N{i:02d}', priorita=1, typ='Překlep', ZK=r.ZK, OID=r.OID, zastupitelstvo=zname(r.ZK), subjekt=f'{r.nazev_strany} – {r.jmeno}',
                zjisteni=f'{r.hlasy} hlasů, pravděpodobně {r.pravdepodobne}', dukaz=r.typ, jistota=3, umysl='Nízká', dopad=m.detail,
                dopad_kat='Mění zvolené', doporuceni='Ověřit zápis.')
            i += 1
    nT = len(T)
    add(id=f'N{i:02d}', priorita=3, typ='Překlepy a propady u hlasů kandidátů (souhrn)', ZK=0, OID='', MC='více MČ', zastupitelstvo='magistrát i MČ',
        subjekt=f'{nT} hodnot v {T.OID.nunique()} okrscích',
        zjisteni=f'{(T.typ == "vlozena_cislice").sum()}× vložená číslice (např. 88 místo 8), {(T.typ == "vypadla_cislice").sum()}× vypadlá číslice '
                 f'(např. 14 místo 145), {(T.typ == "propad").sum()}× nelogický propad (kandidát uprostřed listiny výrazně pod oběma sousedy).',
        dukaz='Propad uprostřed listiny je logicky nemožný (každý lístek s křížkem u strany dává hlas všem kandidátům do počtu mandátů); u vložených číslic vrací odebrání jedné číslice hodnotu sousedních kandidátů.',
        jistota=3, umysl='Nízká – četnost stabilní napříč volbami (2018: 153, 2022: 112, 2026: 92), směr chyb nahodilý',
        dopad='Kromě N01 bez vlivu na mandáty ani pořadí zvolených (simulace oprav všech 92 hodnot).', dopad_kat='Bez vlivu',
        doporuceni='Zavést v programu ČSÚ kontrolu monotónnosti hlasů kandidátů a varování při více než trojnásobné odchylce od sousedů na listině.')
    i += 1
    # zero invalid ballots on both ballots
    m = pd.read_pickle(f'{RES}/precinct_{Y}.pkl')
    z0 = m[(m.PLAT_LISTKY == m.ODEVZ_OBAL) & (m.PLAT_MC == m.ODEVZ_OBAL) & (m.ODEVZ_OBAL >= 100)]
    add(id=f'N{i:02d}', priorita=3, typ='Nulový počet neplatných lístků na obou lístcích', ZK=0, OID=', '.join(z0.index), MC=', '.join(sorted(set(z0.MC))),
        zastupitelstvo='magistrát i MČ', subjekt=f'{len(z0)} okrsků',
        zjisteni='Počet platných lístků se na obou lístcích rovná počtu odevzdaných obálek. Při pražské míře neplatnosti (4,9 % magistrát, 2,9 % MČ) je očekávaný počet takových okrsků 0,005.',
        dukaz='Pravděpodobnost pro jednotlivé okrsky 10⁻¹⁵ až 10⁻⁵', jistota=3,
        umysl='Nízká – komise pravděpodobně neplatné lístky nevyčlenila a jako platné zapsala počet obálek', dopad='Bez vlivu na mandáty; zkresluje statistiku neplatných hlasů.',
        dopad_kat='Bez vlivu', doporuceni='Kontrola v programu ČSÚ: varování při nulovém počtu neplatných lístků u okrsku s více než 200 obálkami.')
    i += 1
    g = m[m.gap >= 20]
    add(id=f'N{i:02d}', priorita=3, typ='Velký rozdíl vydaných a odevzdaných obálek', ZK=0, OID=', '.join(g.index), MC=', '.join(sorted(set(g.MC))),
        zastupitelstvo='magistrát i MČ', subjekt=f'{len(g)} okrsků (20–33 obálek)',
        zjisteni='Voliči převzali obálku, která však v urně chybí. V roce 2026 jde o 6 okrsků s rozdílem ≥ 20 (v letech 2018 i 2022 vždy jen o 1). V okrsku 13/13040 komise údaj během noci změnila (480 → 496 odevzdaných obálek).',
        dukaz='Poissonův test vůči pražskému průměru p < 10⁻⁶', jistota=2,
        umysl='Nelze posoudit z dat – může jít o voliče, kteří odešli, i o chybu v evidenci obálek', dopad='Výsledek okrsku samotný neovlivňuje (hlasy odpovídají odevzdaným obálkám).',
        dopad_kat='Bez vlivu', doporuceni='Ověřit v zápisech komentář komise (§ 42 odst. 1 písm. i).')
    i += 1
    add(id=f'N{i:02d}', priorita=3, typ='Odevzdáno více obálek, než bylo vydáno', ZK=0, OID='500089/2029, 539694/13048', MC='Praha 2, Praha 13',
        zastupitelstvo='magistrát i MČ', subjekt='2 okrsky (rozdíl 1 obálka)', zjisteni='Počet odevzdaných obálek je o 1 vyšší než počet vydaných; ČSÚ tyto záznamy označil příznakem CHYBA=1.',
        dukaz='Deterministický aritmetický rozpor', jistota=5, umysl='Žádná – drobná chyba evidence', dopad='Bez vlivu.', dopad_kat='Bez vlivu',
        doporuceni='Bez dalších kroků.')
    i += 1
    # tight councils (risk, not error)
    add(id=f'N{i:02d}', priorita=2, typ='Výsledek těsnější než běžná chybovost sčítání', ZK=0, OID='', MC='Petrovice, Praha 13, Praha 21, Praha 20, Praha 18, Křeslice',
        zastupitelstvo='MČ', subjekt='6 zastupitelstev',
        zjisteni='O posledním mandátu rozhodlo: Praha-Petrovice 2 hlasy, Praha 21 18 hlasů, Praha 13 22 hlasů (zde navíc potvrzen chybějící balík STAN v okrsku 13053), '
                 'Praha-Křeslice 28, Praha 20 49, Praha 18 – Naše Česko chybělo k 5 % 52 hlasů.',
        dukaz='Rezerva je menší než 2 voliči (každý volič má 15–35 hlasů); v datech připadá na okrsek ~0,25 detekovatelné chyby a drobné chyby (±1–5 hlasů) nejsou statisticky viditelné.',
        jistota=1, umysl='Bez indikace', dopad='Mandát může změnit jakákoli drobná chyba v kterémkoli okrsku MČ.', dopad_kat='Těsný výsledek',
        doporuceni='Zvážit preventivní kontrolní přepočet (zejména Petrovice a Praha 13).')
    i += 1
    # 10/10034 corrected
    add(id=f'N{i:02d}', priorita=4, typ='Opraveno během zpracování (informativně)', ZK=MAGISTRAT * 100 + 1, OID='500224/10034', zastupitelstvo=zname(MAGISTRAT * 100 + 1),
        subjekt='SPOLU pro Prahu', zjisteni='První přenos: SPOLU 0 hlasů; opakovaný přenos v 0:36: 4 099 hlasů. Opakovaně bylo posláno dalších 5 okrsků (13038, 18006, 18008, 10044, 13040).',
        dukaz='XML dávky ČSÚ č. 72 a 123 (příznak OPAKOVANE=1)', jistota=5, umysl='Žádná – kontrolní mechanismus zafungoval', dopad='Opraveno, ve finálních datech bez vlivu.',
        dopad_kat='Bez vlivu', doporuceni='Obdobnou kontrolu (strana s 0 hlasy při vysokém očekávání) zavést automaticky – v okrsku 2/2038 nezafungovala.')
    i += 1
    # neúplně opsané řádky kandidátů – detektor doplněný po kontrole krajských měst (rows.py), společná simulace dopadu
    from rows import detect as rows_detect
    from materiality import outcome
    RW = rows_detect(d); RW = RW[RW.sila != 'slaby']
    zmena = []
    for zk, g in RW.groupby('ZK'):
        dV, dC = {}, {}
        for r in g.itertuples():
            dV[r.strana] = dV.get(r.strana, 0) + r.chybi
            for k, v in r.dC.items():
                dC[k] = dC.get(k, 0) + v
        s0, e0 = outcome(ros, d['rk'], cm, zk); s1, e1 = outcome(ros, d['rk'], cm, zk, dV, dC)
        if s0 != s1 or e0 != e1:
            zmena.append(zname(zk))
    top = RW.sort_values('chybi', ascending=False).head(4)
    add(id=f'N{i:02d}', priorita=3, typ='Neúplně opsané řádky kandidátů (souhrn)', ZK=0, OID=', '.join(RW.OID.drop_duplicates()), MC=', '.join(sorted(set(RW.OID.map(mcmap).astype(str)))),
        zastupitelstvo='magistrát i MČ', subjekt=f'{len(RW)} řádků v {RW.OID.nunique()} okrscích ({(RW.sila == "silny").sum()} s velmi vysokou jistotou)',
        zjisteni='Kandidáti č. 1–k mají v okrsku zhruba stejně hlasů (lístky s křížkem u strany), další kandidáti do počtu mandátů nulu – řádek zápisu nebyl dopsán. '
                 'Největší případy: ' + '; '.join(f'{r.OID} {r.nazev} ({zname(r.ZK)}): kandidáti 1–{r.posledni_v_bloku} po ~{r.zaklad:.0f}, pak {r.nul} nul, chybí ~' + f'{r.chybi:,}'.replace(',', ' ') + ' hlasů'
                                                 for r in top.itertuples()) + '.',
        dukaz='Nula za blokem by vyžadovala, aby každý lístek s křížkem u strany obsahoval mnoho hlasů pro kandidáty jiných stran; u silných případů (lístky s křížkem × pozice za blokem ≥ 80) je to prakticky vyloučeno.',
        jistota=4, umysl='Nízká – nedopsané řádky zápisu, nahodile napříč stranami',
        dopad=('Společná simulace doplnění všech řádků v každém zastupitelstvu nemění mandáty ani zvolené kandidáty.' if not zmena else
               'Společná simulace mění výsledek v: ' + ', '.join(zmena) + '.'),
        dopad_kat='Bez vlivu' if not zmena else 'Mění zvolené',
        doporuceni='Detektor byl doplněn po kontrole krajských měst; jednotlivé řádky zatím nebyly ručně ověřeny. Zavést v programu ČSÚ kontrolu nul za blokem kandidátů.')
    Fd = pd.DataFrame(F)
    Fd['jistota_text'] = Fd.jistota.map(JISTOTA)
    return Fd


if __name__ == '__main__':
    Fd = build()
    Fd.to_csv(f'{RES}/findings_2026.csv', index=False, encoding='utf-8-sig')
    Fd.to_json(f'{RES}/findings_2026.json', orient='records', force_ascii=False, indent=1)
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
    print(Fd[['id', 'priorita', 'typ', 'MC', 'OID', 'subjekt', 'jistota', 'dopad_kat']].to_string())
