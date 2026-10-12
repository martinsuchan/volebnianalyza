"""Automatický registr nálezů pro město (AUDIT_UNIT ≠ praha) ze všech detektorů – šablonové texty se stejnou strukturou
jako ručně psaný pražský registr (findings.py).

Každý nález má stabilní klíč `klic`; ruční/agentní kontrolu lze zapsat do review/<slug>.json:
  {"<klic>": {"vyradit": true|false, "jistota": 1-5, "dopad_kat": "...", "zjisteni": "...", "dukaz": "...",
              "umysl": "...", "doporuceni": "...", "kontrola": "co bylo ověřeno a jak"}}
Nezkontrolované nálezy jsou označeny stav_kontroly='automaticky'.
"""
import sys, os, json, re
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RES, ROOT, load, MAGISTRAT, UNIT

Y = 2026
JISTOTA = {5: 'Jistá (deterministický rozpor)', 4: 'Velmi vysoká (≥ 95 %)', 3: 'Vysoká (80–95 %)', 2: 'Střední (50–80 %)', 1: 'Nízká (< 50 %)'}
MO_MESTA = {554821, 554791, 555134, 554804}  # Ostrava, Plzeň, Pardubice, Ústí n. L. mají městské obvody (MO)
n0 = lambda v: f'{int(round(v)):,}'.replace(',', ' ')


def pl(n, one, few, many):
    """Český tvar podle čísla: 1 okrsek, 2–4 okrsky, 5+ okrsků."""
    return f'{n} ' + (one if n == 1 else few if 2 <= n <= 4 else many)


def typo_key(r):
    return f'{r.OID}|{int(r.ZK)}|{int(r.strana)}|{int(r.porcislo)}'


def preference_typos(d, T):
    """„Vložené číslice“ u kandidátů, kteří mají výrazný preferenční náskok před sousedy na listině i v ostatních okrscích
    (medián poměru ≥ 1,5) – jde o skutečnou preferenci, ne o překlep (podnět z ruční kontroly Jihlavy)."""
    from common import HCOLS
    hl = d['hl']; out = set()
    for r in T[T.typ == 'vlozena_cislice'].itertuples() if len(T) else []:
        g = hl[(hl.ZK == r.ZK) & (hl.POR_STR_HL == r.strana) & (hl.OID != r.OID)]
        i = int(r.porcislo)
        nb = [HCOLS[j - 1] for j in (i - 1, i + 1) if 1 <= j <= 70]
        ref = g[nb].mean(axis=1)
        ok = ref >= 3
        lim = 1.25 if i == 1 else 1.5  # lídr dostává k hlasům z křížku u strany i preferenční hlasy (kontrola Ostrova, Žatce)
        if ok.sum() >= 3 and float((g.loc[ok, HCOLS[i - 1]] / ref[ok]).median()) >= lim:
            out.add(typo_key(r))
    # propad / vypadlá číslice: hodnota, která není nižší než ostatní kandidáti v řádku (do počtu mandátů), není logicky nemožná
    # – je to jen základ řádku vedle kandidátů s preferenčními hlasy (kontrola Kaplice, Dačic, Telče, Králík, Konice)
    if len(T):
        rk, cm = d['rk'], d['councils']
        valid = rk[rk.PLATNOST == 'A'].groupby(['ZK', 'POR_STR_HL']).PORCISLO.apply(sorted)
        hlx = hl.set_index(['OID', 'ZK', 'POR_STR_HL'])
        for r in T[T.typ.isin(['propad', 'vypadla_cislice'])].itertuples():
            key = (r.OID, int(r.ZK), int(r.strana))
            if key not in hlx.index:
                continue
            row = hlx.loc[key]
            row = row.iloc[0] if isinstance(row, pd.DataFrame) else row
            M = int(cm.MANDATY[int(r.ZK)])
            others = [row[HCOLS[p - 1]] for p in valid.get((int(r.ZK), int(r.strana)), []) if p <= M and p != int(r.porcislo)]
            if others and r.hlasy >= min(others):
                out.add(typo_key(r))
    # tentýž kandidát označený ve více okrscích = trvale odlišná podpora, ne překlep (kontrola Svitav, Tachova)
    if len(T):
        n = T.groupby(['ZK', 'strana', 'porcislo']).OID.transform('nunique')
        out |= {typo_key(r) for r, k in zip(T.itertuples(), n) if k >= 2}
    return out


def build():
    d = load(Y); cm = d['councils']; ros = d['ros']; t3 = d['t3']
    jednotka = 'MO' if MAGISTRAT in MO_MESTA else 'MČ'
    mesto = cm.NAZEVZAST[MAGISTRAT * 100 + 1]
    zname = lambda zk: 'Zastupitelstvo města' if int(zk) // 100 == MAGISTRAT else f'Zastupitelstvo {jednotka} {cm.NAZEVZAST[int(zk)]}'
    pname = ros.set_index(['ZK', 'POR_STR_HL']).ZKRATKAO30
    mcmap = t3.drop_duplicates('OID').set_index('OID').MC
    mat = pd.read_pickle(f'{RES}/materiality_{Y}.pkl')
    matd = {r.id: r for r in mat.itertuples()}
    seats = pd.read_csv(f'{RES}/seats.csv'); s26 = seats[seats.rok == Y]
    fr = s26.groupby('ZK').agg(z=('zastupitelstvo', 'first'), M=('mandatu', 'first'), gain=('hlasy_k_zisku', 'min'), lose=('hlasy_k_ztrate', 'min'))
    fr['thr'] = s26[s26.prah_rozhoduje].assign(a=lambda x: x.do_prahu.abs()).groupby('ZK').a.min()  # jen strany, jimž hranice mění mandáty
    fr['krit'] = fr[['gain', 'lose', 'thr']].min(axis=1)
    has_mc = (t3.TYPZASTUP == 2).any()
    F = []

    cname = {(r.ZK, r.POR_STR_HL, r.PORCISLO): f'{r.JMENO} {r.PRIJMENI}' for r in d['rk'].itertuples()}

    def detail(m):
        """Text simulace: čísla stran nahradí zkratkami, dvojice (strana, pořadí) jmény kandidátů."""
        s = re.sub(r'strana (\d+): (\d+)→(\d+)', lambda x: f'{pname.get((m.ZK, int(x.group(1))), "strana " + x.group(1))} {x.group(2)} → {x.group(3)} mandátů', m.detail)
        kand = lambda txt: ', '.join(f'{cname.get((m.ZK, int(a), int(b)), f"kand. č. {b}")} ({pname.get((m.ZK, int(a)), a)}, č. {b})'
                                      for a, b in re.findall(r'\((\d+), (\d+)\)', txt))
        mm = re.search(r'zvoleni navíc \[(.*?)\], vypadli \[(.*?)\]', s)
        if mm:
            pre = s[:s.index(' | zvoleni navíc')] if ' | zvoleni navíc' in s else ''
            s = (pre + '; ' if pre else '') + f'po opravě by byl(a) zvolen(a) {kand(mm.group(1))} místo {kand(mm.group(2))}'
        return s[0].upper() + s[1:] if s else s

    def mat_kat(m):
        if m is None:
            return None
        return 'Mění mandáty' if m.zmena_mandatu else ('Mění zvolené' if m.zmena_zvolenych else 'Bez vlivu')

    def add(**k):
        k.setdefault('MC', mcmap.get(k.get('OID'), ''))
        F.append(k)

    def heur(zk, hlasy):
        """Dopad bez simulace: porovnání rozsahu chyby s rozhodující rezervou zastupitelstva."""
        krit = fr.krit.get(zk)
        if krit is not None and not np.isnan(krit) and hlasy >= krit:
            return 'Může změnit mandáty', f'Rozsah chyby (~{n0(hlasy)} hlasů) je větší než rozhodující rezerva zastupitelstva ({n0(krit)} hlasů) – výsledek může ovlivnit.'
        return 'Bez vlivu', f'Rozsah chyby (~{n0(hlasy)} hlasů) je menší než rozhodující rezerva zastupitelstva ({n0(krit) if krit is not None and not np.isnan(krit) else "–"} hlasů).'

    from materiality import outcome as _outcome
    R_sh = pd.read_pickle(f'{RES}/shares_{Y}.pkl')

    def sim_missing(r):
        """Chybějící hlasy rozdělí mezi strany podle očekávaných podílů (sousední okrsky) a přepočítá mandáty."""
        e = R_sh[(R_sh.ZK == r.ZK) & (R_sh.OID == r.OID)].set_index('strana').e.dropna()
        if not len(e) or e.sum() <= 0:
            return heur(r.ZK, r.chybi_hlasu)
        dV = {int(p): int(round(r.chybi_hlasu * w / e.sum())) for p, w in e.items()}
        s0, e0 = _outcome(ros, d['rk'], cm, r.ZK); s1, e1 = _outcome(ros, d['rk'], cm, r.ZK, dV, None)
        krit = fr.krit.get(r.ZK)
        ktxt = f' Rozhodující rezerva zastupitelstva je {n0(krit)} hlasů.' if krit is not None and krit == krit else ''
        if s1 != s0:
            return 'Může změnit mandáty', (f'Při rozdělení chybějících ~{n0(r.chybi_hlasu)} hlasů podle podílů stran v sousedních okrscích se mění mandáty: '
                                          + '; '.join(f'{pname.get((r.ZK, p), p)} {s0[p]} → {s1[p]}' for p in s0 if s0[p] != s1[p]) + '.' + ktxt)
        return 'Bez vlivu', f'Při rozdělení chybějících ~{n0(r.chybi_hlasu)} hlasů podle podílů stran v sousedních okrscích se mandáty nemění.' + ktxt

    covered = set()  # (ZK, OID) vysvětlené silnějším nálezem
    # 1) chybějící balíky lístků
    S = pd.read_pickle(f'{RES}/stacks_{Y}.pkl')
    S = S[S.tri != 'slaby'].sort_values('z_vpb') if len(S) else S
    for r in S.itertuples():
        m = matd.get(f'S-{r.OID}-{r.ZK}-{r.strana}-kons'); kat = mat_kat(m) or 'Bez vlivu'
        nc = int(ros[(ros.ZK == r.ZK) & (ros.POR_STR_HL == r.strana)].NCAND.fillna(0).iloc[0])
        width = max(min(int(cm.MANDATY[r.ZK]), nc), 1)
        add(klic=f'stack:{r.OID}:{r.ZK}:{r.strana}', typ='Nezapsaná strana (všichni kandidáti 0 hlasů)' if r.hlasy == 0 else 'Chybějící balík hlasovacích lístků', ZK=r.ZK, OID=r.OID, zastupitelstvo=zname(r.ZK), subjekt=r.nazev,
            zjisteni=f'Strana má v okrsku jen ~{r.pb_obs:.0f} lístků s křížkem u strany (kandidáti mají po ~{r.pb_obs:.0f} hlasech), očekáváno ~{r.pb_ocek:.0f}; '
                     f'okrsku současně chybí hlasy zhruba {r.chybi_listku_okrsek:.0f} lístků.',
            dukaz=f'z(strana) = {r.z_strana:.1f}; z(hlasy/lístek) = {r.z_vpb:.1f}; shoda obou deficitů {100 * r.shoda:.0f} %'.replace('.', ','),
            jistota=4 if r.tri == 'silny' else 3, umysl='Nízká – typická chyba přepisu (nezapočtený balík lístků s křížkem u strany)',
            dopad=(detail(m) if kat != 'Bez vlivu' else f'Bez vlivu na mandáty (straně chybí řádově {n0(r.chybi_listku_strana * width)} hlasů).'),
            dopad_kat=kat, doporuceni='Ověřit zápis okrsku, případně přepočítat hlasovací lístky.')
        covered.add((r.ZK, r.OID))
    # 2) nulové hlasy strany
    Z = pd.read_pickle(f'{RES}/zeros_{Y}.pkl')
    Z = Z[Z.p_conservative < 1e-3] if len(Z) else Z
    for r in Z.itertuples():
        if (r.ZK, r.OID) in covered:
            continue
        m = matd.get(f'Z-{r.OID}-{r.ZK}-{r.strana}-kons'); kat = mat_kat(m) or 'Bez vlivu'
        add(klic=f'zero:{r.OID}:{r.ZK}:{r.strana}', typ='Nulové hlasy strany', ZK=r.ZK, OID=r.OID, zastupitelstvo=zname(r.ZK), subjekt=f'{r.nazev} (0 hlasů)',
            zjisteni=f'Strana má v okrsku 0 hlasů, podle sousedních okrsků se čeká zhruba {r.exp_ballots:.0f} lístků s jejími hlasy (podíl {100 * r.e:.1f} %).'.replace('.', ',', 1),
            dukaz=f'Pravděpodobnost nuly po korekci na rozptyl p = {r.p_conservative:.1e}'.replace('.', ','),
            jistota=4 if (r.p_conservative < 1e-6 and r.exp_ballots >= 10) else 3,
            umysl='Nízká – odpovídá nezapsané straně v zápisu (vzor NSS Blansko 2025)',
            dopad=detail(m) if kat != 'Bez vlivu' else 'Bez vlivu na mandáty podle simulace doplnění očekávaných lístků.', dopad_kat=kat,
            doporuceni='Ověřit zápis okrsku; strana s nulou při vysokém očekávání je typický příznak nezapsaného řádku.')
        covered.add((r.ZK, r.OID))
    # 3) nezapsané hlasy části lístků (bez identifikované strany)
    Mi = pd.read_pickle(f'{RES}/missing_{Y}.pkl')
    for r in Mi[(Mi.z_vpb <= -8) & (Mi.chybi_listku >= 20)].sort_values('z_vpb').itertuples():
        if (r.ZK, r.OID) in covered:
            continue
        kat, txt = sim_missing(r)
        add(klic=f'missing:{r.OID}:{r.ZK}', typ='Nezapsané hlasy části lístků', ZK=r.ZK, OID=r.OID, zastupitelstvo=zname(r.ZK), subjekt='okrsek jako celek',
            zjisteni=f'Na platný lístek připadá jen {100 * r.vpb:.0f} % možných hlasů (sousední okrsky {100 * r.vpb_ocek:.0f} %); chybí zhruba {n0(r.chybi_hlasu)} hlasů, '
                     f'tj. přibližně {n0(r.chybi_listku)} lístků.' + (f' Nejvíce pod očekáváním: {r.podezrele_strany}.' if isinstance(r.podezrele_strany, str) and r.podezrele_strany else ''),
            dukaz=f'z(hlasy/lístek) = {r.z_vpb:.1f} vůči sousedním okrskům'.replace('.', ','), jistota=2,
            umysl='Nelze posoudit – může jít o nezapsaný balík lístků i o neobvyklé chování voličů', dopad=txt, dopad_kat=kat,
            doporuceni='Ověřit zápis okrsku (počet platných lístků a hlasy stran).')
        covered.add((r.ZK, r.OID))
    # 3b) neúplně opsané řádky kandidátů (blok se stejným počtem hlasů, pak nuly)
    from rows import detect as rows_detect, detect_holes
    from materiality import outcome
    RW = rows_detect(d).assign(diry=None)
    HW = detect_holes(d)
    HW = HW[np.array([(a, b, c) not in set(zip(RW.OID, RW.ZK, RW.strana)) for a, b, c in zip(HW.OID, HW.ZK, HW.strana)], dtype=bool)]
    rowparty = set(zip(RW.ZK, RW.OID, RW.strana)) | set(zip(HW.ZK, HW.OID, HW.strana))  # řádky s dírami: překlepy v nich jsou falešné
    RW = pd.concat([RW[RW.sila != 'slaby'], HW[HW.sila != 'slaby']], ignore_index=True)
    base_out = {}
    covered_pred = set(covered)  # vícero neúplných řádků v jednom okrsku se vykazuje každý zvlášť
    cap = t3.set_index(['ZK', 'OID'])
    cap = (cap.PLAT_LISTKY * cap.MANDATY - cap.PL_HL_CELK).to_dict()  # kolik hlasů se do okrsku ještě „vejde“
    for r in RW.itertuples():
        if (r.ZK, r.OID) in covered_pred:
            continue
        if r.chybi > cap.get((r.ZK, r.OID), np.inf):  # doplnění by překročilo platné lístky × mandáty (kontrola Jemnice)
            continue
        if r.ZK not in base_out:
            base_out[r.ZK] = outcome(ros, d['rk'], cm, r.ZK)
        s0, e0 = base_out[r.ZK]
        s1, e1 = outcome(ros, d['rk'], cm, r.ZK, {r.strana: r.chybi}, r.dC)
        m = type('M', (), dict(ZK=r.ZK, detail='; '.join(f'strana {p}: {s0[p]}→{s1[p]}' for p in s0 if s0[p] != s1[p]) +
                                ('' if e0 == e1 else f' | zvoleni navíc {sorted(e1 - e0)}, vypadli {sorted(e0 - e1)}')))
        kat = 'Mění mandáty' if s0 != s1 else ('Mění zvolené' if e0 != e1 else 'Bez vlivu')
        add(klic=f'row:{r.OID}:{r.ZK}:{r.strana}', typ='Neúplně opsaný řádek kandidátů', ZK=r.ZK, OID=r.OID, zastupitelstvo=zname(r.ZK), subjekt=r.nazev,
            zjisteni=(f'Kandidáti č. 1–{r.posledni_v_bloku} mají v okrsku zhruba stejně hlasů (~{r.zaklad:.0f}, tj. lístky s křížkem u strany), '
                      f'u dalších kandidátů do počtu mandátů je {pl(r.nul, "nula", "nuly", "nul")}. Chybí odhadem {n0(r.chybi)} hlasů.') if r.diry is None else
                     (f'Řádek kandidátů má „díry“: kandidáti mají většinou zhruba stejně hlasů (~{r.zaklad:.0f}, tj. lístky s křížkem u strany), ale '
                      f'{pl(r.nul, "kandidát", "kandidáti", "kandidátů")} uprostřed řádku má nulu (č. {", ".join(map(str, r.diry))}). Chybí odhadem {n0(r.chybi)} hlasů.'),
            dukaz=(f'Nula za blokem by znamenala, že každý z ~{r.zaklad:.0f} lístků s křížkem u strany obsahoval nejméně {r.potreba_jinych} hlasů pro kandidáty jiných stran'
                   + (' – prakticky vyloučeno.' if r.sila == 'silny' else ' – málo pravděpodobné.')) if r.diry is None else
                  'Lístek s křížkem u strany dává hlas souvislé řadě kandidátů od začátku listiny; nula uprostřed řádku, za níž následují kandidáti '
                  'na úrovni lístků s křížkem, tomu odporuje – typicky vynechané buňky při přepisu zápisu.',
            jistota=4 if r.sila == 'silny' else 2, umysl='Nízká – nedopsaný řádek zápisu (typicky přechod na další stranu tiskopisu)',
            dopad=(detail(m) if kat != 'Bez vlivu' else f'Bez vlivu na mandáty ani zvolené (simulace doplnění {n0(r.chybi)} hlasů).'), dopad_kat=kat,
            doporuceni='Ověřit zápis okrsku – hlasy kandidátů strany.')
        covered.add((r.ZK, r.OID))
    # 3c) záměna hlasů dvou stran
    W = pd.read_pickle(f'{RES}/swaps_{Y}.pkl')
    obal = t3.drop_duplicates('OID').set_index('OID').ODEVZ_OBAL
    for r in (W[W.zisk_chi2 >= 60].itertuples() if len(W) else []):
        if (r.ZK, r.OID) in covered or obal.get(r.OID, 0) < 100:  # malé okrsky: časté falešné záměny (kontrola Ústí n. L.)
            continue
        add(klic=f'swap:{r.OID}:{r.ZK}:{r.strana_a}:{r.strana_b}', typ='Možná záměna hlasů dvou stran', ZK=r.ZK, OID=r.OID, zastupitelstvo=zname(r.ZK),
            subjekt=f'{r.nazev_a} × {r.nazev_b}',
            zjisteni=f'{r.nazev_a} má {n0(r.hlasy_a)} hlasů (sousední okrsky čekají ~{n0(r.ocek_a)}), {r.nazev_b} {n0(r.hlasy_b)} (~{n0(r.ocek_b)}). '
                     'Po prohození hodnot by obě strany odpovídaly okolí.',
            dukaz=f'Prohození zlepší shodu s okolím o Δχ² = {r.zisk_chi2:.0f}'.replace('.', ','), jistota=2,
            umysl='Nízká – záměna řádků při přepisu zápisu', dopad='Nesimulováno – k ověření.', dopad_kat='Bez vlivu',
            doporuceni='Ověřit zápis okrsku (pořadí řádků stran).')
        covered.add((r.ZK, r.OID))
    # 4) překlepy u kandidátů – jednotlivě, pokud mění zvolené, jinak souhrn
    T = pd.read_pickle(f'{RES}/typos_{Y}.pkl')
    pref = preference_typos(d, T)
    # „překlepy“ v řádcích s dírami nebo neúplných řádcích jsou artefakt nulových sousedů (kontrola Mostu)
    pref |= {typo_key(r) for r in T.itertuples() if (int(r.ZK), r.OID, int(r.strana)) in rowparty} if len(T) else set()
    json.dump(sorted(pref), open(f'{RES}/typos_preference_{Y}.json', 'w', encoding='utf-8'), ensure_ascii=False)  # vyřazené z překlepů
    T = T[[typo_key(r) not in pref for r in T.itertuples()]] if len(T) else T
    for r in T.itertuples():
        m = matd.get(f'T-{r.OID}-{r.ZK}-{r.strana}-{r.porcislo}')
        if m is not None and (m.zmena_zvolenych or m.zmena_mandatu):
            add(klic=f'typo:{r.OID}:{r.ZK}:{r.strana}:{r.porcislo}', typ='Překlep – ' + {'vlozena_cislice': 'vložená číslice', 'vypadla_cislice': 'vypadlá číslice', 'propad': 'nelogický propad'}[r.typ],
                ZK=r.ZK, OID=r.OID, zastupitelstvo=zname(r.ZK), subjekt=f'{r.nazev_strany} – kand. č. {r.porcislo} {r.jmeno}',
                zjisteni=f'Kandidát má v okrsku zapsáno {r.hlasy} hlasů, sousední kandidáti na listině ~{r.reference}; pravděpodobná správná hodnota {r.pravdepodobne}.',
                dukaz='Jedna vložená/vypuštěná číslice vrací hodnotu na úroveň sousedů na listině' if r.typ != 'propad' else
                      'Propad uprostřed listiny je logicky nemožný (lístek s křížkem u strany dává hlas všem kandidátům do počtu mandátů)',
                jistota=3, umysl='Nízká – vzorec odpovídá překlepu', dopad=detail(m), dopad_kat=mat_kat(m), doporuceni='Ověřit zápis okrsku a hlasy kandidáta.')
    if len(T):
        add(klic='typos:souhrn', typ='Překlepy a propady u hlasů kandidátů (souhrn)', ZK=0, OID='', MC='více částí města', zastupitelstvo='všechna zastupitelstva',
            subjekt=f'{pl(len(T), "hodnota", "hodnoty", "hodnot")} v {pl(T.OID.nunique(), "okrsku", "okrscích", "okrscích")}',
            zjisteni=f'{(T.typ == "vlozena_cislice").sum()}× vložená číslice, {(T.typ == "vypadla_cislice").sum()}× vypadlá číslice, {(T.typ == "propad").sum()}× nelogický propad uprostřed listiny.',
            dukaz='U vložených/vypadlých číslic vrací úprava jedné číslice hodnotu sousedních kandidátů; propad uprostřed listiny je logicky nemožný.',
            jistota=3, umysl='Nízká – nahodilé chyby přepisu', dopad='Simulace oprav všech hodnot: ' + ('bez vlivu na mandáty i pořadí zvolených.' if not any(
                (matd.get(f'T-{r.OID}-{r.ZK}-{r.strana}-{r.porcislo}') is not None and (matd[f'T-{r.OID}-{r.ZK}-{r.strana}-{r.porcislo}'].zmena_zvolenych or matd[f'T-{r.OID}-{r.ZK}-{r.strana}-{r.porcislo}'].zmena_mandatu)) for r in T.itertuples())
                else 'mění zvolené – viz samostatné nálezy.'),
            dopad_kat='Bez vlivu', doporuceni='Opravit data; seznam hodnot je v tabulce na stránce nálezů.')
    # 5) deterministické rozpory v zápisech
    try:
        I = pd.read_csv(f'{RES}/integrity.csv')
    except pd.errors.EmptyDataError:  # žádný deterministický rozpor (prázdný soubor bez hlavičky)
        I = pd.DataFrame(columns=['rok', 'kod', 'popis', 'zavaznost', 'OID', 'MC', 'KODZASTUP', 'TYPZASTUP', 'hodnota'])
    I = I[I.rok == Y]
    for kod, g in I[~I.kod.isin(['A2', 'A12'])].groupby('kod'):
        for r in g.itertuples():
            add(klic=f'integ:{kod}:{r.OID}:{r.KODZASTUP}', typ=r.popis, ZK=int(r.KODZASTUP) * 100 + 1, OID=r.OID if isinstance(r.OID, str) else '',
                zastupitelstvo=zname(int(r.KODZASTUP) * 100 + 1), subjekt=str(r.hodnota), zjisteni=f'{r.popis}: {r.hodnota}.', dukaz='Deterministická kontrola aritmetiky zápisu',
                jistota=5, umysl='Nelze posoudit z dat', dopad='Dopad nebyl simulován.', dopad_kat='Bez vlivu', doporuceni='Ověřit zápis okrsku.')
    a2 = I[I.kod == 'A2'].drop_duplicates('OID')
    if len(a2):
        add(klic='integ:A2', typ='Odevzdáno více obálek, než bylo vydáno', ZK=0, OID=', '.join(a2.OID), MC=', '.join(sorted(set(a2.MC.astype(str)))),
            zastupitelstvo='všechna zastupitelstva', subjekt=pl(len(a2), 'okrsek', 'okrsky', 'okrsků'), zjisteni='; '.join(f'{o}: {h}' for o, h in zip(a2.OID, a2.hodnota)) + '.',
            dukaz='Deterministický aritmetický rozpor', jistota=5, umysl='Žádná – drobná chyba evidence obálek', dopad='Bez vlivu.', dopad_kat='Bez vlivu', doporuceni='Bez dalších kroků.')
    # 6) nulový počet neplatných lístků
    m = pd.read_pickle(f'{RES}/precinct_{Y}.pkl')
    z0 = m[(m.PLAT_LISTKY == m.ODEVZ_OBAL) & ((m.PLAT_MC == m.ODEVZ_OBAL) | m.PLAT_MC.isna()) & (m.ODEVZ_OBAL >= 100)]
    # očekávaný počet okrsků bez neplatných lístků při městské míře neplatnosti (u MČ/MO na obou lístcích zároveň)
    big = m[m.ODEVZ_OBAL >= 100]
    # robustní míra neplatnosti: medián okrsků (průměr zkreslují části města s mimořádně vysokou neplatností)
    r_mag = float((1 - big.PLAT_LISTKY / big.ODEVZ_OBAL).median())
    r_mc = float((1 - big.PLAT_MC / big.ODEVZ_OBAL).dropna().median()) if big.PLAT_MC.notna().any() else 0.0
    p0 = (1 - r_mag) ** big.ODEVZ_OBAL * np.where(big.PLAT_MC.notna(), (1 - r_mc) ** big.ODEVZ_OBAL, 1.0)
    exp0 = float(p0.sum())
    from scipy import stats as _st
    p_exc = float(_st.poisson.sf(len(z0) - 1, max(exp0, 1e-9))) if len(z0) else 1.0
    if len(z0) and p_exc < 0.01 and len(z0) >= 2 * exp0:
        add(klic='inv0', typ='Nulový počet neplatných lístků' + (' na obou lístcích' if z0.PLAT_MC.notna().all() else ''), ZK=0, OID=', '.join(z0.index), MC=', '.join(sorted(set(z0.MC.astype(str)))),
            zastupitelstvo='všechna zastupitelstva', subjekt=pl(len(z0), 'okrsek', 'okrsky', 'okrsků'),
            zjisteni=f'Počet platných lístků se rovná počtu odevzdaných obálek v {len(z0)} okrscích se 100 a více obálkami; při městské míře neplatnosti '
                     f'(medián okrsků {100 * r_mag:.1f} %) se čeká zhruba {exp0:.1f} takových okrsků.'.replace('.', ','),
            dukaz=f'Poissonův test nadbytku: p = {p_exc:.1e} (bez modelu rozptylu neplatnosti mezi okrsky, proto jen orientačně)'.replace('.', ','),
            jistota=2 if p_exc < 0.001 else 1,
            umysl='Nízká – komise pravděpodobně neplatné lístky nevyčlenila', dopad='Bez vlivu na mandáty; zkresluje statistiku neplatných hlasů.', dopad_kat='Bez vlivu',
            doporuceni='Kontrola v programu ČSÚ: varování při nulovém počtu neplatných lístků.')
    # 7) velký rozdíl vydaných a odevzdaných obálek
    g = m[m.gap >= 20]
    if len(g):
        add(klic='gap', typ='Velký rozdíl vydaných a odevzdaných obálek', ZK=0, OID=', '.join(g.index), MC=', '.join(sorted(set(g.MC.astype(str)))),
            zastupitelstvo='všechna zastupitelstva', subjekt=f'{len(g)} okrsků ({int(g.gap.min())}–{int(g.gap.max())} obálek)',
            zjisteni='Voliči převzali obálku, která v urně chybí.', dukaz='Poissonův test vůči průměru města', jistota=2,
            umysl='Nelze posoudit z dat – voliči, kteří odešli, i chyba evidence', dopad='Výsledek okrsku neovlivňuje (hlasy odpovídají odevzdaným obálkám).',
            dopad_kat='Bez vlivu', doporuceni='Ověřit komentář komise v zápisu.')
    # 8) rozpory mezi lístkem města a MČ/MO (k ověření)
    X = pd.read_pickle(f'{RES}/cross_{Y}.pkl')
    if len(X):
        X = X.assign(zmax=X[['z_mag', 'z_mc']].abs().max(axis=1))
        # jen strany s dostatkem lístků na obou lístcích (u malých čísel vznikají falešné poplachy)
        Mz = cm.MANDATY
        X = X[(X[['hlasy_mc', 'ocek_hlasy_mc']].max(axis=1) / X.ZK.map(Mz) >= 4) & (X[['hlasy_mag', 'ocek_hlasy_mag']].max(axis=1) / Mz[MAGISTRAT * 100 + 1] >= 4)]
        X = X[(X.zmax >= 8) & ~X.apply(lambda r: (MAGISTRAT * 100 + 1, r.OID) in covered or (r.ZK, r.OID) in covered, axis=1)]
        if len(X):
            top = X.sort_values('zmax', ascending=False).drop_duplicates('OID').head(12)
            add(klic='cross', typ=f'Výrazný rozdíl mezi lístkem města a {jednotka} (k ověření)', ZK=0, OID=', '.join(top.OID), MC=', '.join(sorted(set(top.MC.astype(str)))),
                zastupitelstvo=f'město i {jednotka}', subjekt=pl(X.OID.nunique(), 'okrsek', 'okrsky', 'okrsků'),
                zjisteni='Podíl téže strany na lístku města a na lístku ' + jednotka + ' se liší víc, než je v dané části města obvyklé: ' +
                         '; '.join(f'{r.OID} {r.nazev_mc}: {jednotka} {r.hlasy_mc:.0f} (čekáno ~{r.ocek_hlasy_mc:.0f}), město {r.hlasy_mag:.0f} (~{r.ocek_hlasy_mag:.0f})' for r in top.head(6).itertuples()) + '.',
                dukaz='Robustní z-skóre poměru podílů ≥ 8; skutečné místní preference se obvykle projeví na obou lístcích', jistota=1,
                umysl='Bez indikace', dopad='Nesimulováno – jde o kandidáty na chybu k ověření.', dopad_kat='Bez vlivu', doporuceni='Prověřit jednotlivé okrsky (detail v datech).')
    # 9) těsné výsledky
    tight = fr[(fr.krit <= 30) | (fr.krit / fr.M <= 3)].sort_values('krit')  # do 30 hlasů nebo do 3 voličů se všemi hlasy
    if len(tight):
        add(klic='tight', typ='Výsledek těsnější než běžná chybovost sčítání', ZK=0, OID='', MC=', '.join(tight.z), zastupitelstvo=f'zastupitelstva města a {jednotka}',
            subjekt=pl(len(tight), 'zastupitelstvo', 'zastupitelstva', 'zastupitelstev'),
            zjisteni='O mandátu nebo 5% hranici rozhodlo jen několik hlasů: ' + ', '.join(
                f'{r.z} ({"zastupitelstvo města" if int(r.Index) // 100 == MAGISTRAT else jednotka}, {r.M} mandátů) {pl(int(r.krit), "hlas", "hlasy", "hlasů")}'
                for r in tight.itertuples()) + '.',
            dukaz='Rezerva je menší než hlasy jednoho až dvou voličů; drobné chyby (±1–5 hlasů) nejsou statisticky viditelné.', jistota=1,
            umysl='Bez indikace', dopad='Mandát může změnit jakákoli drobná chyba v kterémkoli okrsku zastupitelstva.', dopad_kat='Těsný výsledek',
            doporuceni='Zvážit preventivní kontrolní přepočet.')
    # 10) opravy během volební noci (informativně)
    B = pd.read_pickle(f'{RES}/batch_changes_{Y}.pkl')
    if len(B):
        ch = [o for (o, k), r in B.iterrows() if any(r[c] != r[c + '_last'] for c in ('ZAPSANI_VOLICI', 'VYDANE_OBALKY', 'ODEVZDANE_OBALKY', 'PLATNE_LISTKY', 'PLATNE_HLASY'))]
        only_hl = not any(r[c] != r[c + '_last'] for (o, k), r in B.iterrows() for c in ('ZAPSANI_VOLICI', 'VYDANE_OBALKY', 'ODEVZDANE_OBALKY', 'PLATNE_LISTKY'))
        add(klic='batches', typ='Opraveno během zpracování (informativně)', ZK=0, OID=', '.join(sorted(set(ch))) if ch else ', '.join(sorted(set(o for o, k in B.index))),
            zastupitelstvo='všechna zastupitelstva', subjekt=pl(len(set(o for o, k in B.index)), 'opakovaně zaslaný okrsek', 'opakovaně zaslané okrsky', 'opakovaně zaslaných okrsků'),
            zjisteni=f'Během volební noci byly okrsky zaslány opakovaně; ve {len(set(ch))} z nich se změnily údaje zápisu.'
                     + (' Počty voličů, obálek a platných lístků zůstaly stejné; změnil se součet platných hlasů (doplnění nebo oprava hlasů stran).' if ch and only_hl else ''),
            dukaz='XML dávky ČSÚ (příznak OPAKOVANE)',
            jistota=5, umysl='Žádná – oprava během zpracování', dopad='Ve finálních datech bez vlivu.', dopad_kat='Bez vlivu', doporuceni='Žádné.')

    # ---- kontrola (review) a pořadí
    rv_path = os.path.join(ROOT, 'review', f'{UNIT}.json')
    rv = json.load(open(rv_path, encoding='utf-8')) if os.path.exists(rv_path) else {}
    out = []
    for f in F:
        r = rv.get(f['klic'], {})
        if r.get('vyradit'):
            continue
        for k in ('jistota', 'dopad_kat', 'dopad', 'zjisteni', 'dukaz', 'umysl', 'doporuceni', 'typ', 'subjekt'):
            if k in r:
                if k == 'dopad_kat' and f['klic'] in ('tight', 'typos:souhrn'):  # souhrny: dopad se počítá u samostatných nálezů (bez dvojího započtení)
                    continue
                f[k] = r[k]
        f['kontrola'] = r.get('kontrola', '')
        f['stav_kontroly'] = 'zkontrolováno' if r else 'automaticky'
        out.append(f)
    rank = {'Mění mandáty': 0, 'Mění zvolené': 1, 'Může změnit mandáty': 1, 'Těsný výsledek': 2, 'Bez vlivu': 3}
    druh = lambda f: 2 if f['klic'] == 'batches' else (1 if f['klic'] == 'cross' else 0)  # informativní a „k ověření“ na konec
    out.sort(key=lambda f: (rank.get(f['dopad_kat'], 3), druh(f), -f['jistota'], f['klic']))
    for i, f in enumerate(out, 1):
        f['id'] = f'N{i:02d}'
        f['priorita'] = 1 if f['dopad_kat'] in ('Mění mandáty', 'Mění zvolené', 'Může změnit mandáty') else (
            4 if f['klic'] == 'batches' else (2 if f['jistota'] >= 4 or f['dopad_kat'] == 'Těsný výsledek' else 3))
    Fd = pd.DataFrame(out)
    if len(Fd):
        Fd['jistota_text'] = Fd.jistota.map(JISTOTA)
    return Fd, mesto


if __name__ == '__main__':
    Fd, mesto = build()
    Fd.to_csv(f'{RES}/findings_{Y}.csv', index=False, encoding='utf-8-sig')
    Fd.to_json(f'{RES}/findings_{Y}.json', orient='records', force_ascii=False, indent=1)
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 70)
    print(mesto, len(Fd))
    if len(Fd):
        print(Fd[['id', 'priorita', 'typ', 'MC', 'OID', 'subjekt', 'jistota', 'dopad_kat', 'stav_kontroly']].to_string())
