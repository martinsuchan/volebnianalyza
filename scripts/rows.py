"""Detektor neúplně opsaných řádků kandidátů (podnět z ruční kontroly Brna).

Křížek u strany dává hlas prvním M kandidátům listiny; pokud volič současně označí k kandidátů jiných stran, dostane strana hlasy
jen pro prvních M − k kandidátů. Nula u kandidáta na pozici p proto znamená, že každý lístek s křížkem u strany obsahoval alespoň
M − p + 1 jiných hlasů. Vzorec „blok kandidátů se zhruba stejným počtem hlasů (= lístky s křížkem u strany), pak nuly“ je proto
logicky nemožný, když je za blokem ještě mnoho pozic a lístků s křížkem je hodně – typicky nedopsaný řádek zápisu.
"""
import numpy as np, pandas as pd


def detect(d):
    hl, rk, ros, cm = d['hl'], d['rk'], d['ros'], d['councils']
    valid = rk[rk.PLATNOST == 'A'].groupby(['ZK', 'POR_STR_HL']).PORCISLO.apply(sorted)
    names = ros.set_index(['ZK', 'POR_STR_HL']).ZKRATKAO30
    out = []
    for r in hl.itertuples():
        pos = valid.get((r.ZK, r.POR_STR_HL))
        if pos is None or len(pos) < 6:
            continue
        M = int(cm.MANDATY[r.ZK]); pos = [p for p in pos if p <= M]
        v = np.array([getattr(r, f'HLASY_{p:02d}') for p in pos])
        if len(v) < 6 or v[0] < 5:
            continue
        b0 = float(np.median(v[:5])); thr = max(5, 0.6 * b0)
        L = 0
        while L < len(v) and v[L] >= thr:  # vedoucí blok kandidátů na úrovni lístků s křížkem u strany
            L += 1
        rest = v[L:]
        z = int((rest == 0).sum())
        if L < 5 or z < 3 or z < 0.5 * len(rest):
            continue
        need = M - pos[L - 1]  # kolik jiných hlasů by musel mít každý lístek s křížkem u strany, aby další kandidát dostal 0
        # síla důkazu: kolik hlasů pro kandidáty jiných stran by vzorec vyžadoval celkem (lístky s křížkem × pozice za blokem)
        sila = 'silny' if need >= 5 and b0 >= 5 and need * b0 >= 80 else ('stredni' if need >= 5 and b0 >= 5 else 'slaby')
        dC = {(int(r.POR_STR_HL), int(p)): int(round(max(0.0, b0 - x))) for p, x in zip(pos[L:], rest)}
        out.append(dict(OID=r.OID, ZK=int(r.ZK), strana=int(r.POR_STR_HL), nazev=names.get((r.ZK, r.POR_STR_HL)), M=M, n=len(v), blok=L,
                        posledni_v_bloku=int(pos[L - 1]), nul=z, zaklad=b0, chybi=int(sum(dC.values())), potreba_jinych=int(need), sila=sila, dC=dC))
    return pd.DataFrame(out, columns=['OID', 'ZK', 'strana', 'nazev', 'M', 'n', 'blok', 'posledni_v_bloku', 'nul', 'zaklad', 'chybi',
                                      'potreba_jinych', 'sila', 'dC'])


def detect_holes(d):
    """Řádek kandidátů s rozptýlenými „dírami“ (podnět z kontroly Mostu): většina kandidátů do počtu mandátů má zhruba stejný počet hlasů
    (lístky s křížkem u strany), ale uprostřed řádku jsou nuly, za nimiž následují opět kandidáti na základní úrovni. Nula na pozici p
    znamená, že žádný lístek s křížkem u strany pozici p nedosáhl – pak nemůže další kandidát na listině mít hlasy na úrovni těchto lístků."""
    hl, rk, ros, cm = d['hl'], d['rk'], d['ros'], d['councils']
    valid = rk[rk.PLATNOST == 'A'].groupby(['ZK', 'POR_STR_HL']).PORCISLO.apply(sorted)
    names = ros.set_index(['ZK', 'POR_STR_HL']).ZKRATKAO30
    out = []
    for r in hl.itertuples():
        pos = valid.get((r.ZK, r.POR_STR_HL))
        if pos is None or len(pos) < 6:
            continue
        M = int(cm.MANDATY[r.ZK]); pos = [p for p in pos if p <= M]
        v = np.array([getattr(r, f'HLASY_{p:02d}') for p in pos])
        nz = v[v > 0]
        if len(v) < 6 or len(nz) < 4:
            continue
        b0 = float(np.median(nz))
        # hodnoty mimo díry musí ležet v úzkém pásu (lístky s křížkem); u stran s několika voliči jsou nuly uprostřed řádku běžné (kontrola Kroměříže)
        if b0 < 8 or ((nz >= 0.6 * b0) & (nz <= 1.6 * b0)).mean() < 0.8:
            continue
        hi = np.where(v >= 0.6 * b0)[0]
        holes = [i for i in np.where(v == 0)[0] if len(hi) and i < hi.max()]  # nula, za níž ještě následuje kandidát na základní úrovni
        if len(holes) < 2:
            continue
        sila = 'silny' if len(holes) >= 3 and len(holes) * b0 >= 80 else ('stredni' if len(holes) * b0 >= 30 else 'slaby')
        dC = {(int(r.POR_STR_HL), int(pos[i])): int(round(b0)) for i in holes}
        out.append(dict(OID=r.OID, ZK=int(r.ZK), strana=int(r.POR_STR_HL), nazev=names.get((r.ZK, r.POR_STR_HL)), M=M, n=len(v), blok=len(nz),
                        posledni_v_bloku=int(pos[hi.max()]), nul=len(holes), zaklad=b0, chybi=int(sum(dC.values())), potreba_jinych=0, sila=sila, dC=dC,
                        diry=[int(pos[i]) for i in holes]))
    return pd.DataFrame(out, columns=['OID', 'ZK', 'strana', 'nazev', 'M', 'n', 'blok', 'posledni_v_bloku', 'nul', 'zaklad', 'chybi',
                                      'potreba_jinych', 'sila', 'dC', 'diry'])
