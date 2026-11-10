# Návrh pravidel P8 a P9 (zatím mimo pipeline)

Prototyp ze 9.–10. 11. 2026. Do pipeline (`pravidla.py` / `findings_m.py`) se zařadí až po uzavření všech soudních řízení ke KV 2026.
Skripty nic nezapisují do `review/` ani `report/`. Výstupy ukládají do `data/results/_p8p9/` (mimo git).

- **P8 – přesun hlasů mezi stranami v okrsku** (podle Kladna 51 A 85, okrsek 1). Kandidát na nález:
  - strana X má schodek (z ≤ −3) a strana Y přebytek (z ≥ +3), každý aspoň 3 lístky;
  - schodek a přebytek jsou podobně velké (vyváženost ≥ 0,5);
  - po přesunu jsou obě strany v normálu (|z| < 2,5).

  Filtry:
  - druhý lístek: odchylka musí být jen na jednom lístku; když ji strana má i na druhém, jde o místní podporu a případ se vyřadí;
  - očekávání musí vycházet z ≥ 4 sousedních okrsků téhož zastupitelstva;
  - podobně rozevřený okrsek v minulých volbách snižuje jistotu na 2.
- **P9 – izolovaný nadbytek kandidáta** (podle Prahy-Petrovic 8 A 70, okrsek 44001). Kandidát na nález: nadbytek ≥ 40 hlasů, ≥ 4× obvyklý nadbytek téhož kandidáta a z ≥ 8. Vyřadí se, když:
  - spolu s ním vyčnívají ≥ 3 kandidáti téže strany (to je vzor P2/P4);
  - nadbytek se přelévá do sousedních okrsků;
  - kandidát má nadbytek i na druhém lístku (≥ 0,4 nadbytku);
  - případ se opakuje z roku 2022;
  - už ho zachytil detektor překlepů.

  Samostatný nález jen když oprava mění výsledek.

## Výsledky a kalibrace (2026 proti kontrolnímu roku 2022)

- **Praha:**
  - P9 – samostatný nález jen Petrovice / 44001 (potvrzeno soudem);
  - P8 – samostatný nález jen Praha 14 / 14032 (NAŠE Čtrnáctka → STAN, mění mandáty);
  - kontrola 2022: 1 případ P8 (Kbely, nejspíš místní struktura).
- **Kladno:** P8 zachytí okrsek 1. P9 v témže okrsku zachytí kandidáta VOLBY PRO KLADNO č. 21 (nadbytek 97), soud tam VOLBĚ PRO KLADNO odečetl 101 hlasů. Případ je ale bez vlivu na výsledek, takže zůstává pod prahem samostatného nálezu.
- **Krajská města a ORP – P9:**
  - silný vzor (≥ 4× sousední kandidáti a ≥ 2× vlastní maximum v ostatních okrscích) a změna zvolených: 3 případy v roce 2026, 0 v roce 2022;
  - jde o Brno-Řečkovice a Mokrá Hora / 19007 (Šimáčková 270, nejspíš 27), Havířov / 28 (Křístek 121) a Olomouc / 91 (Vašíř 150).
- **Krajská města a ORP – P8:**
  - bez druhého lístku vychází 13 případů s jistotou ≥ 3 v roce 2026 proti 9 v roce 2022, takže nerozlišuje chybu od místních rozdílů;
  - používat jen jako podpůrný důkaz, mimo Prahu jen s jistotou 2;
  - přesvědčivé jsou jen Kladno / 1 a Plzeň / 2031; ke kontrole zbývá Žďár n. S. / 11.
- **Vedlejší zjištění:** detektor překlepů (`typos.py`) má toleranci ±max(2; 10 %) a minul 270 proti očekávaným 24.

## Spuštění

```
AUDIT_UNIT=praha python scripts/navrh_p8_p9/pravidla_p8_p9.py 2026        # jedna jednotka (AUDIT_YEAR=2022 pro kontrolu)
python scripts/navrh_p8_p9/run_p8p9.py 2026                               # krajská města + ORP (6 procesů)
python scripts/navrh_p8_p9/souhrn_p8p9.py 2026                            # souhrn + vazba na nálezy a soudy
python scripts/navrh_p8_p9/p8_predchozi.py 2026 data/results/_p8p9/souhrn_p8_2026.pkl
python scripts/navrh_p8_p9/detail_p9.py 2026
```

Při zařazení do pipeline: nové nálezy dostanou další volná ID řady M přes zámky `review/<slug>_m.json`, stávající čísla se nemění.
Dopad je třeba počítat i společně s ostatními nálezy téhož zastupitelstva (Kladno) a ošetřit případy těsně u 5% hranice (Karviná / 2).
