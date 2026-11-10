"""Doplňkové nálezy (řada M) z pravidel v pravidla.py – listopad 2026, po srovnání se soudními podáními a jinou analýzou.
Volá je findings.py (Praha) i findings_auto.py (ostatní obce).

Nálezy N zůstávají beze změny. Nové nálezy dostávají čísla M01, M02, …, která jsou zamčená v review/<obec>_m.json (Praha: praha_m.json)
podle klíče nálezu (klic): při dalším běhu má stejný nález stejné číslo, nové nálezy dostanou další volná čísla. Ve stejném souboru je
i výsledek kontroly nálezu v datech (pole kontrola, případně vyradit / jistota / dopad_kat).
Nálezy jsou seskupeny po okrscích a lístcích (jeden zápis = jeden nález), aby odpovídaly tomu, co lze ověřit v jednom zápisu komise.
"""
import json, os
import numpy as np, pandas as pd
from common import RES, ROOT, MAGISTRAT, UNIT, ROK, PREDCHOZI, REVIEW_DIR
import pravidla as PR

VYCHOZI = 'Automaticky podle doplňkových pravidel (listopad 2026), jednotlivě zatím neověřeno; graf hlasů kandidátů je u nálezu.'
Y, YP = ROK, PREDCHOZI[ROK]  # analyzovaný rok a srovnávací předchozí volby
n0 = lambda v: f'{int(round(v)):,}'.replace(',', ' ')
pc = lambda v: f'{100 * v:.1f} %'.replace('.', ',')


def _krit(seats):
    s26 = seats[seats.rok == Y]
    fr = s26.groupby('ZK').agg(gain=('hlasy_k_zisku', 'min'), lose=('hlasy_k_ztrate', 'min'), M=('mandatu', 'first'))
    fr['thr'] = s26[s26.prah_rozhoduje].assign(a=lambda x: x.do_prahu.abs()).groupby('ZK').a.min()
    fr['krit'] = fr[['gain', 'lose', 'thr']].min(axis=1)
    return fr


def build_m(d, zname, mcmap, outcome, kryto, kryto_okrsky, mag='magistrát', jed='MČ', oba='magistrát i MČ', stav=False, male=False):
    """kryto: {(OID, ZK, strana)} už pokryté nálezy N; kryto_okrsky: {(OID, ZK)} okrsky s nálezem N na úrovni celého okrsku.
    mag / jed / oba: označení lístku města, městských částí a obou v souhrnech; stav=True doplní stav_kontroly (šablona obcí).
    male=True (obce mimo krajská města, ORP a POU): bez souhrnů neplatných lístků a těsných výsledků, nižší jistota u krátkých kandidátek
    (v malých obcích voliči běžně označují jednotlivé kandidáty) a navíc srovnání okrsků s rokem 2022 proti ostatním okrskům obce (P5b)."""
    REVIEW = os.path.join(REVIEW_DIR, f'{UNIT}_m.json')
    os.makedirs(REVIEW_DIR, exist_ok=True)
    from anomalies import prep
    _, t3, hl, ros, nb = prep(Y)
    rk, cm = d['rk'], d['councils']
    MS = pd.read_pickle(f'{RES}/missing_{Y}.pkl')
    if 'z_vpb' not in MS:  # malé obce: využití hlasů proti okolí se nepočítá
        MS = pd.DataFrame(columns=['OID', 'ZK', 'MC', 'M', 'PLAT_LISTKY', 'vpb', 'vpb_ocek', 'z_vpb', 'chybi_hlasu', 'chybi_listku'])
    p22 = f'{RES}/missing_{YP}.pkl'  # nízké využití hlasů už v předchozích volbách = místní zvyk
    MS22 = pd.read_pickle(p22) if os.path.exists(p22) else pd.DataFrame(columns=['OID', 'ZK', 'vpb', 'vpb_ocek', 'z_vpb'])
    MS22 = MS22.set_index(['OID', 'ZK'])
    SH = pd.read_pickle(f'{RES}/shares_{Y}.pkl')
    if 'e' not in SH:
        SH = pd.DataFrame(columns=['OID', 'ZK', 'strana', 'e'])
    PM = pd.read_pickle(f'{RES}/precinct_{Y}.pkl')
    seats = pd.read_csv(f'{RES}/seats.csv'); fr = _krit(seats)
    vecs = PR.vektory(d, nb)
    R = pd.concat([PR.p1_p2_p3(vecs, PR.odstoupivsi(d), konec_nc=male), PR.p4(vecs, MS)], ignore_index=True)
    for c in ('pravidlo', 'ZK', 'strana', 'nazev', 'OID', 'K', 'M', 'posun', 'sila', 'chybi', 'z_vpb', 'shoda', 'hodnoty', 'od', 'do', 'pozice', 'hodnota', 'zaklad'):
        if c not in R:  # pravidla, která v obci nic nenašla, nedodají své sloupce
            R[c] = pd.Series(dtype=object)
    R = R[np.array([(r.OID, int(r.ZK), int(r.strana)) not in kryto for r in R.itertuples()], dtype=bool)]  # prázdný seznam by vybral sloupce
    R5 = PR.p5(MS)
    if not len(R5):
        R5 = pd.DataFrame(columns=['OID', 'ZK'])
    R5 = R5[np.array([(r.OID, int(r.ZK)) not in kryto_okrsky for r in R5.itertuples()], dtype=bool)]
    jm = {(int(r.ZK), int(r.POR_STR_HL), int(r.PORCISLO)): f'{r.JMENO} {r.PRIJMENI}' for r in rk.itertuples()}
    pn = {(int(r.ZK), int(r.POR_STR_HL)): str(r.ZKRATKAO30) for r in ros.itertuples()}

    def jistota(r):
        if male and r.K < 20 and r.pravidlo == 'P1':  # krátká kandidátka v malé obci: propad může být skutečně menší podpora kandidáta
            hod = r.hodnota if isinstance(r.hodnota, list) else [r.hodnota]
            return 3 if max(hod) <= 0.1 * r.zaklad and r.zaklad >= 20 else 2
        if male and r.K < 20 and r.pravidlo == 'P3':
            return 2
        if r.pravidlo == 'P1':
            return 4 if r.chybi >= max(15, 0.5 * r.zaklad) and r.zaklad >= 20 else 3
        if r.pravidlo == 'P2':
            # vzor, který lístky s křížkem u strany vytvořit nemohou (dlouhá kandidátka): úsek téměř nulový, propad na začátku
            # kandidátky nebo propad uprostřed, za nímž se hodnoty vrátí na původní úroveň (dělené hlasování dává jen plynulý pokles ke konci)
            h = np.asarray(r.hodnoty, float); od, do = int(r.od), int(r.do); seg = h[od - 1:do]; zb = np.delete(h, np.arange(od - 1, do)); mz = np.median(zb)
            za = h[do:]
            nemozny = r.K >= 20 and mz >= 5 and (seg.max() <= 0.25 * mz or od == 1 or
                                                 (len(za) and za.mean() >= 0.8 * mz and seg.mean() <= 0.6 * mz))
            return 4 if r.sila >= 15 or nemozny else 3
        if r.pravidlo == 'P3':
            if r.K >= 20:  # na dlouhé kandidátce nemohou nuly mezi stejnými nenulovými hodnotami vzniknout z žádné kombinace lístků
                return 4
            return 3 if sum(r.hodnoty) < 0.5 * r.zaklad * r.K else 2
        if r.pravidlo == 'P4':
            if r.posun > 0:
                return 2 if r.z_vpb >= 4 else 1
            return 4 if r.z_vpb <= -6 and 0.6 <= r.shoda <= 1.4 else (3 if r.z_vpb <= -4 else 2)
        return 2

    t22 = None
    if male:
        from common import load
        try:
            t22 = load(YP)['t3']
        except Exception:  # v obci se v předchozích volbách nevolilo
            t22 = None
    DL = PR.pokles_2022(t3, t22) if t22 is not None and len(t22) else {}
    R['jistota'] = [jistota(r) for r in R.itertuples()]
    if male:  # malé obce: okolí tvoří jiné části obce, schodek hlasů musí potvrdit i pokles proti roku 2022
        R.loc[[r.pravidlo == 'P4' and DL.get((r.OID, int(r.ZK)), 0) > -0.08 for r in R.itertuples()], 'jistota'] = 1
        R5 = R5[np.array([DL.get((r.OID, int(r.ZK)), 0) <= -0.08 for r in R5.itertuples()], dtype=bool)]
    slabe = R[(R.pravidlo == 'P4') & (R.jistota <= 2)]
    R = R[~((R.pravidlo == 'P4') & (R.jistota <= 2))]
    ms = MS.set_index(['OID', 'ZK'])
    keys = sorted(set(zip(R.OID, R.ZK.astype(int))) | set(zip(R5.OID, R5.ZK.astype(int))))
    F = []
    for oid, zk in keys:
        g = R[(R.OID == oid) & (R.ZK == zk)].sort_values(['jistota', 'sila'], ascending=False)
        m = ms.loc[(oid, zk)] if (oid, zk) in ms.index else None
        p5 = m is not None and m.z_vpb <= -5 and m.chybi_listku >= 10
        zvyk = (oid, zk) in MS22.index and MS22.loc[(oid, zk)].z_vpb <= -3
        okr = oid.split('/')[1]
        casti, dC, dV = [], {}, {}
        for r in g.itertuples():
            nm = r.nazev; p = int(r.strana)
            if r.pravidlo == 'P1':
                kand = ', '.join(f'č. {k} {jm.get((zk, p, k), "")}' for k in r.pozice)
                hod = r.hodnota if isinstance(r.hodnota, list) else [r.hodnota]
                casti.append(f'{nm}: {kand} má {", ".join(map(str, hod))} hlasů, ostatní kandidáti kolem {n0(r.zaklad)}')
                for k, h in zip(r.pozice, hod):
                    dC[(p, k)] = max(dC.get((p, k), 0), int(round(r.zaklad - h)))
            elif r.pravidlo == 'P2':
                if r.od == 2 and r.do == r.K:
                    casti.append(f'{nm}: hlasy z lístků s křížkem u strany jsou připsány jen kandidátovi č. 1, kandidáti č. 2–{int(r.do)} mají o ~{n0(-r.posun)} hlasů méně než v okolí')
                else:
                    casti.append(f'{nm}: kandidáti č. {int(r.od)}–{int(r.do)} mají o ~{n0(-r.posun)} hlasů méně než zbytek kandidátky (proti sousedním okrskům), chybí ~{n0(r.chybi)} hlasů')
                for k in range(int(r.od), int(r.do) + 1):
                    dC[(p, k)] = max(dC.get((p, k), 0), int(round(-r.posun)))
            elif r.pravidlo == 'P3':
                casti.append(f'{nm}: {len(r.pozice)} z {r.K} kandidátů má 0 hlasů (rozeseto po celé kandidátce), ostatní mají po ~{n0(r.zaklad)}')
                for k in r.pozice:
                    dC[(p, k)] = max(dC.get((p, k), 0), int(round(r.zaklad)))
            elif r.pravidlo == 'P4':
                smer = 'nižší' if r.posun < 0 else 'vyšší'
                casti.append(f'{nm}: celá kandidátka je proti sousedním okrskům {smer} o ~{n0(abs(r.posun))} hlasů na kandidáta '
                             f'({"chybí" if r.posun < 0 else "přebývá"} ~{n0(abs(r.chybi))} hlasů, tj. lístky ~{n0(abs(r.posun))} voličů s křížkem u strany)')
                for k in range(1, r.K + 1):  # posun dolů i nahoru; s posunutým úsekem téže strany se nesčítá (bere se větší oprava)
                    o = -int(round(r.posun)); dC[(p, k)] = o if (p, k) not in dC else (max(dC[(p, k)], o) if o > 0 else min(dC[(p, k)], o))
        for (p, k), v in dC.items():  # doplněné hlasy strany = součet oprav jejích kandidátů (bez dvojího započtení)
            dV[p] = dV.get(p, 0) + v
        if p5 or (m is not None and m.z_vpb <= -3 and len(g)):
            casti.append(f'okrsek jako celek má na tomto lístku jen {pc(m.vpb)} možných hlasů (sousední okrsky {pc(m.vpb_ocek)}), chybí ~{n0(m.chybi_hlasu)} hlasů, '
                         f'tj. hlasy ~{n0(m.chybi_listku)} lístků' + (f' (nízké využití hlasů měl okrsek i v roce {YP}: {pc(MS22.loc[(oid, zk)].vpb)} proti {pc(MS22.loc[(oid, zk)].vpb_ocek)})' if zvyk else ''))
        if not casti:
            continue
        hlavni = g.iloc[0] if len(g) else None
        jist = int(g.jistota.max()) if len(g) else (3 if m.z_vpb <= -8 else 2)
        if hlavni is not None and p5 and not zvyk and hlavni.pravidlo in ('P2', 'P4') and hlavni.posun < 0:
            jist = max(jist, 4)  # dvě nezávislé linie: vzor v kandidátce a schodek hlasů okrsku
        if zvyk and (hlavni is None or hlavni.pravidlo in ('P4', 'P5')):
            jist = max(1, jist - 1)
        typ = {'P1': 'Propad hlasů kandidáta pod počet lístků s křížkem u strany', 'P2': 'Posunutý úsek kandidátky (nedopsané hlasy části kandidátů)',
               'P3': 'Rozptýlené nuly v kandidátce', 'P4': 'Chybějící balík hlasovacích lístků' if hlavni is not None and hlavni.posun < 0 else 'Možný balík lístků navíc (k ověření)'
               }.get(hlavni.pravidlo if hlavni is not None else 'P5', 'Nezapsané hlasy části lístků')
        if len(g.nazev.unique()) > 1:
            typ += ' (více stran)'
        dukaz = []
        prav = set(g.pravidlo)
        if prav & {'P1', 'P2', 'P3'}:
            dukaz.append('Lístek s křížkem u strany dává hlas všem prvním kandidátům do počtu mandátů, takže kandidáti mají aspoň tolik hlasů, kolik je takových lístků. '
                         'Propad, posunutý úsek nebo nuly uprostřed jinak vyrovnané kandidátky by vyžadovaly, aby voliči s křížkem u strany právě tyto kandidáty jednotlivě vynechali.')
        if 'P4' in prav:
            dukaz.append('Dvě nezávislé linie: posun celé kandidátky proti profilu 8 sousedních okrsků a stejně velký schodek (přebytek) hlasů celého okrsku.')
        if 'P2' in prav:
            dukaz.append('Profil kandidátky v sousedních okrscích takový zlom nemá (t = ' + f'{g[g.pravidlo == "P2"].sila.max():.0f}'.replace('.', ',') + ').')
        if p5:
            dukaz.append(f'Využití hlasů okrsku proti okolí: z = {m.z_vpb:.1f}'.replace('.', ',') + '.')
        # dopad
        s0, e0 = outcome(d['ros'], rk, cm, zk)
        if dV:
            s1, e1 = outcome(d['ros'], rk, cm, zk, dV, dC)
            zm = [f'{pn.get((zk, p), p)} {s0[p]} → {s1[p]}' for p in s0 if s0[p] != s1[p]]
            plus = sorted(e1 - e0); minus = sorted(e0 - e1)
            if zm:
                dk, dt = 'Mění mandáty', 'Simulace opravy mění mandáty: ' + '; '.join(zm) + '.'
            elif plus:
                dk, dt = 'Mění zvolené', ('Simulace opravy mění zvolené: ' + ', '.join(f'{jm.get((zk,) + k, k)} ({pn.get((zk, k[0]))})' for k in plus) + ' místo '
                                          + ', '.join(f'{jm.get((zk,) + k, k)} ({pn.get((zk, k[0]))})' for k in minus) + '.')
            else:
                dk, dt = 'Bez vlivu', f'Simulace doplnění ~{n0(sum(dV.values()))} hlasů nemění mandáty ani zvolené kandidáty.'
        else:
            krit = fr.krit.get(zk)
            e = SH[(SH.OID == oid) & (SH.ZK == zk)].set_index('strana').e.dropna()
            if male:  # malé obce: strany bývají kandidátky jednotlivých vesnic – rozdělit podle podílů v okrsku samotném
                g_ = d['hl'][(d['hl'].ZK == zk) & (d['hl'].OID == oid)]
                e = pd.Series({int(q): float(x[[c for c in PR.HC if c in x.index]].sum()) for q, x in g_.set_index('POR_STR_HL').iterrows()}) if len(g_) else e
            dVp = {int(q): int(round(m.chybi_hlasu * w / e.sum())) for q, w in e.items()} if len(e) and e.sum() > 0 else {}
            s1, _ = outcome(d['ros'], rk, cm, zk, dVp, None) if dVp else (s0, None)
            zm = [f'{pn.get((zk, q), q)} {s0[q]} → {s1[q]}' for q in s0 if s0[q] != s1[q]]
            if zm:
                dk, dt = 'Může změnit mandáty', f'Při rozdělení chybějících ~{n0(m.chybi_hlasu)} hlasů podle podílů stran v {"okrsku" if male else "sousedních okrscích"} se mění mandáty: ' + '; '.join(zm) + '.'
            else:
                dk, dt = 'Bez vlivu', (f'Při rozdělení chybějících ~{n0(m.chybi_hlasu)} hlasů podle podílů stran v {"okrsku" if male else "sousedních okrscích"} se mandáty nemění'
                                       + (f' (rozhodující rezerva zastupitelstva {n0(krit)} hlasů).' if krit == krit else '.'))
        F.append(dict(klic=f'm:{oid}:{zk}', priorita=1 if dk in ('Mění mandáty', 'Mění zvolené', 'Může změnit mandáty') else (2 if jist >= 4 else 3), typ=typ, ZK=zk, OID=oid,
                      zastupitelstvo=zname(zk), subjekt=str(hlavni.nazev) if hlavni is not None else 'okrsek jako celek',
                      zjisteni=f'Okrsek {okr}: ' + '; '.join(casti) + '.', dukaz=' '.join(dukaz), jistota=jist,
                      umysl='Nízká – vzorec odpovídá chybě přepisu zápisu', dopad=dt, dopad_kat=dk,
                      doporuceni='Ověřit zápis okrsku (hlasy uvedených kandidátů), případně přepočítat hlasovací lístky.',
                      _sila=float(g.sila.max()) if len(g) else float(-m.z_vpb), strana_m=int(hlavni.strana) if hlavni is not None else None))
    # --- malé obce: okrsek s poklesem využití hlasů proti roku 2022 výrazně větším než v ostatních okrscích obce (P5b)
    if male:
        R5b = PR.p5_kontrola(t3, t22) if t22 is not None and len(t22) else pd.DataFrame()
        hl_ = d['hl']
        for r in R5b.itertuples():
            if (r.OID, int(r.ZK)) in kryto_okrsky:
                continue
            zk, oid = int(r.ZK), r.OID
            txt = (f'okrsek má na lístku jen {pc(r.vpb)} možných hlasů (v roce {YP} {pc(r.vpb22)}), kontrolní okrsky obce se změnily o '
                   f'{100 * r.kontrola:+.1f}'.replace('.', ',') + f' p. b. (medián okrsků s aspoň 50 lístky a podobnou velikostí jako v roce {YP})' + f'; chybí ~{n0(r.chybi_hlasu)} hlasů, tj. hlasy ~{n0(r.chybi_listku)} lístků')
            hit = [f for f in F if f['klic'] == f'm:{oid}:{zk}']
            if hit and f'v roce {YP}' in hit[0]['zjisteni']:
                continue
            if hit:
                hit[0]['zjisteni'] = hit[0]['zjisteni'].rstrip('.') + '; ' + txt + '.'
                continue
            g = hl_[(hl_.ZK == zk) & (hl_.OID == oid)]
            pv = {int(q): float(x[[c for c in PR.HC if c in x.index]].sum()) for q, x in g.set_index('POR_STR_HL').iterrows()} if len(g) else {}
            tot = sum(pv.values())
            dVp = {q: int(round(r.chybi_hlasu * v / tot)) for q, v in pv.items()} if tot > 0 else {}
            s0, _ = outcome(d['ros'], rk, cm, zk); s1, _ = outcome(d['ros'], rk, cm, zk, dVp, None) if dVp else (s0, None)
            zm = [f'{pn.get((zk, q), q)} {s0[q]} → {s1[q]}' for q in s0 if s0[q] != s1[q]]
            krit = fr.krit.get(zk)
            dk, dt = (('Může změnit mandáty', f'Při rozdělení chybějících ~{n0(r.chybi_hlasu)} hlasů podle podílů stran v okrsku se mění mandáty: ' + '; '.join(zm) + '.') if zm else
                      ('Bez vlivu', f'Při rozdělení chybějících ~{n0(r.chybi_hlasu)} hlasů podle podílů stran v okrsku se mandáty nemění'
                       + (f' (rozhodující rezerva zastupitelstva {n0(krit)} hlasů).' if krit == krit and krit is not None else '.')))
            jist = 3 if r.rel <= -0.25 and r.chybi_listku >= 20 else 2
            F.append(dict(klic=f'm:{oid}:{zk}', priorita=1 if dk != 'Bez vlivu' else 3, typ='Nezapsané hlasy části lístků (srovnání s rokem 2022)' if Y == 2026 else f'Nezapsané hlasy části lístků (srovnání s rokem {YP})', ZK=zk, OID=oid,
                          zastupitelstvo=zname(zk), subjekt='okrsek jako celek', zjisteni=f'Okrsek {oid.split("/")[1]}: ' + txt + '.',
                          dukaz=f'Srovnání využití hlasů okrsku s rokem {YP} a se změnou v ostatních okrscích téže obce, které volily ze stejných kandidátek '
                                f'(změny kandidátek se tak odečtou). V roce {YP} chybí počet platných lístků, použit je počet odevzdaných obálek.',
                          jistota=jist, umysl='Nelze posoudit – může jít o nezapsaný balík lístků i o jiné chování voličů v části obce', dopad=dt, dopad_kat=dk,
                          doporuceni='Ověřit zápis okrsku (počet platných lístků a hlasy stran).', _sila=float(-r.rel * 20), strana_m=None))
    # --- souhrny
    R6 = PR.p6(PM) if not male else pd.DataFrame()
    if len(R6):
        R6 = R6.sort_values('z', ascending=False)
        F.append(dict(klic='m:neplatne', priorita=3, typ='Neobvykle mnoho neplatných lístků (souhrn)', ZK=0, OID=', '.join(R6.OID.drop_duplicates()), MC=', '.join(sorted(set(R6.MC.astype(str)))),
                      zastupitelstvo=oba, subjekt=f'{len(R6)} lístků v {R6.OID.nunique()} okrscích',
                      zjisteni='Podíl neplatných lístků je aspoň trojnásobkem sousedních okrsků: ' + '; '.join(
                          f'{r.OID.split("/")[1]} ({mag if r.listek == "mag" else r.MC}): {r.neplatnych} z {n0(r.obalek)} ({pc(r.podil)}, okolí {pc(r.okoli)})' for r in R6.head(12).itertuples()) + '.',
                      dukaz='Robustní z-skóre podílu neplatných lístků proti 8 sousedním okrskům ≥ 5. Vzor „balík lístků uznaný za neplatný“ (jako u Senátu) by se projevil i schodkem některé strany.',
                      jistota=1, umysl='Nelze posoudit – protestní hlasování, lístky jiného zastupitelstva v obálce i chybné vyčlenění platných lístků', dopad='Nesimulováno – strana nebyla určena.',
                      dopad_kat='Bez vlivu', doporuceni='Prověřit zápisy okrsků s nejvyšším podílem; při současném schodku strany ověřit, zda nejde o balík platných lístků.', _sila=0.0, strana_m=None))
    if len(slabe):
        F.append(dict(klic='m:balik_slabe', priorita=3, typ='Možné chybějící balíky lístků – slabší případy (souhrn)', ZK=0, OID=', '.join(slabe.OID.drop_duplicates()),
                      MC=', '.join(sorted(set(slabe.OID.map(mcmap).astype(str)))), zastupitelstvo=oba, subjekt=f'{len(slabe)} kandidátek v {slabe.OID.nunique()} okrscích',
                      zjisteni='Celá kandidátka je proti okolí posunutá a okrsku chybí (přebývá) obdobně velký počet hlasů, ale odchylka okrsku je jen mírná (|z| 3–4): ' + '; '.join(
                          f'{r.OID.split("/")[1]} {r.nazev} ({mag if r.ZK // 100 == MAGISTRAT else mcmap.get(r.OID, "")}): {"−" if r.posun < 0 else "+"}{n0(abs(r.posun))} na kandidáta'
                          for r in slabe.sort_values('sila', ascending=False).head(12).itertuples()) + '.',
                      dukaz='Stejný vzor jako u chybějícího balíku, ale schodek hlasů okrsku je v pásmu běžné variability; odlišit od nižší podpory strany v okrsku nelze.',
                      jistota=1, umysl='Bez indikace', dopad='Nesimulováno jednotlivě.', dopad_kat='Bez vlivu', doporuceni='Ověřit jen při jiném podnětu.', _sila=0.0, strana_m=None))
    # u rezervy pod 10 hlasů změní výsledek jakákoli drobná chyba – seznam kritických hodnot má smysl až od 10 hlasů
    tight = fr[(fr.krit >= 10) & (fr.krit <= 50)].sort_values('krit') if not male else fr.iloc[:0]
    mini = fr[fr.krit < 10].sort_values('krit') if not male else fr.iloc[:0]
    crit = []
    for zk, r in tight.iterrows():
        x = PR.p7(d, int(zk), outcome, max(int(r.krit), 1))
        if len(x):
            crit.append((int(zk), int(r.krit), x))
    if crit:
        txt = []
        for zk, k, x in crit:
            x = x.drop_duplicates(['OID', 'strana', 'porcislo']).head(6)
            txt.append(f'{cm.NAZEVZAST[zk] if zk // 100 != MAGISTRAT else mag} (rezerva {n0(k)} hl.): ' + ', '.join(
                f'okrsek {o.split("/")[1]} {pn.get((zk, s), s)} č. {c} {z} → {v}' for o, s, c, z, v in zip(x.OID, x.strana, x.porcislo, x.zapsano, x.varianta)))
        F.append(dict(klic='m:citlivost', priorita=2, typ='Kritické hodnoty těsných výsledků (k ověření v zápisech)', ZK=0, OID=', '.join(sorted({o for _, _, x in crit for o in x.OID})),
                      MC=', '.join(cm.NAZEVZAST[zk] for zk, _, _ in crit), zastupitelstvo=jed if all(zk // 100 != MAGISTRAT for zk, _, _ in crit) else (mag if len(crit) == 1 else oba), subjekt=f'{len(crit)} zastupitelstev',
                      zjisteni='Okrskové hodnoty, jejichž věrohodný překlep (záměna dvou číslic nebo jedna jiná číslice, výsledek v rozpětí kandidátky v okrsku) by změnil mandát nebo zvoleného kandidáta: '
                               + '; '.join(txt) + '.' + (' U rezervy pod 10 hlasů (' + ', '.join(f'{cm.NAZEVZAST[int(z)]} {n0(k)} hl.' for z, k in mini.krit.items()) +
                                                        ') změní výsledek jakákoli chyba o několik hlasů v kterémkoli okrsku; seznam hodnot by nic nerozlišil.' if len(mini) else ''),
                      dukaz='Simulace přepočtu mandátů a pořadí kandidátů pro každou variantu. Zapsaná i opravená hodnota jsou statisticky stejně věrohodné – rozhodne jen zápis nebo lístky '
                            '(obdobný případ: Býkev 2026, 114 místo 141 hlasů, soud volbu kandidáta zrušil).',
                      jistota=1, umysl='Bez indikace', dopad='Mandát nebo zvolení by změnila chyba v kterékoli z uvedených hodnot.', dopad_kat='Těsný výsledek',
                      doporuceni='Při ověřování zápisů nebo přepočtu v těchto zastupitelstvech zkontrolovat přednostně uvedené hodnoty.', _sila=0.0, strana_m=None))
    # --- kontrola a zamčená čísla
    rv = json.load(open(REVIEW, encoding='utf-8')) if os.path.exists(REVIEW) else {}
    used = {int(v['id'][1:]) for v in rv.values() if 'id' in v}
    nove = sorted((f for f in F if f['klic'] not in rv), key=lambda f: (f['priorita'], -f['jistota'], -f['_sila'], f['klic']))
    for f in nove:
        n = max(used, default=0) + 1; used.add(n)
        rv[f['klic']] = dict(id=f'M{n:02d}')
    if rv or os.path.exists(REVIEW):  # obce bez nálezu M soubor nedostanou
        json.dump(rv, open(REVIEW, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    out = []
    for f in F:
        r = rv[f['klic']]
        if r.get('vyradit'):
            continue
        for k in ('jistota', 'dopad_kat', 'dopad', 'zjisteni', 'dukaz', 'umysl', 'doporuceni', 'typ', 'subjekt', 'priorita'):
            if k in r:
                f[k] = r[k]
        if 'jistota' in r and 'priorita' not in r and f['priorita'] in (2, 3) and f['ZK']:
            f['priorita'] = 2 if f['jistota'] >= 4 else 3
        f['id'] = r['id']; f['kontrola'] = r.get('kontrola') or ('' if stav else VYCHOZI)
        if stav:
            f['stav_kontroly'] = 'zkontrolováno' if r.get('kontrola') else 'automaticky'
        f.setdefault('MC', mcmap.get(f['OID'], ''))
        f.pop('_sila', None)
        out.append(f)
    return sorted(out, key=lambda f: int(f['id'][1:]))
