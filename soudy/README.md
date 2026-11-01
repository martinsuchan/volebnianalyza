# Soudní podání ke komunálním volbám 2026

Evidence všech řízení o neplatnosti voleb, hlasování nebo volby kandidáta ke komunálním volbám 9.–10. 10. 2026,
která byla k 1. 11. 2026 vyvěšena na elektronických úředních deskách soudů, a jejich vazba na nálezy této analýzy.
Slouží k závěrečnému vyhodnocení po rozhodnutí soudů: **které nálezy ukázaly na skutečnou chybu a kde oprava změnila
složení zastupitelstva.**

Složka není součástí publikovaného webu (`report/`).

## Soubory

| Soubor | Obsah |
|---|---|
| `podani_2026.csv` | Jeden řádek na řízení (207): 33 Městský soud v Praze, 174 krajské soudy. Stav k 1. 11. 2026 a prázdné sloupce pro výsledek. |
| `stav_<datum>.csv` | Výstup `scripts/soudy_stav.py` – rozhodnutí nalezená na deskách k danému dni (navržený stav a výrok). |
| `../scripts/soudy_stav.py` | Stáhne aktuální úřední desky, najde usnesení k řízením z CSV a vytáhne výrok. |

Stažené PDF se ukládají do `data/raw/soudy/` (není v gitu).

## Sloupce `podani_2026.csv`

- `soud_kod`, `soud`, `spis` – kód subjektu na infodeska.gov.cz (201000 MS Praha, 202000–208000 krajské soudy) a spisová značka.
- `kraj`, `obec`, `slug`, `mc` – místo; `slug` odpovídá `kv/<slug>/` na webu, `mc` městská část či obvod.
- `navrhovatel` – volební strana, nebo „volič“ (jména soukromých osob neuvádíme; u Prahy uvedeni kandidáti z veřejných kandidátních listin).
- `predmet`, `okrsky_v_podani` – co podání napadá (stručně) a okrsky v něm zmíněné (u krajů vytaženo automaticky, může obsahovat šum).
- `stav_2026_11_01` – stav k 1. 11. 2026: běží / běží (spojeno) / odmítnuto / zamítnuto / zastaveno / vyhověno.
- `nalezy`, `vztah`, `nalez_popis`, `odkaz_nalez` – vazba na náš nález (ID v registru obce) a její síla:
  - **přesná** – podání napadá stejný okrsek a stejnou vadu jako nález;
  - **částečná** – shoda u části napadených okrsků;
  - **obecná** – analýza obec vedla jen jako „výsledek těsnější než běžná chybovost sčítání“;
  - **nejistá** – souvislost nelze ověřit (návrh nezveřejněn nebo nečitelný);
  - **mezera** – soud nebo navrhovatel doložil chybu, kterou analýza nevykázala;
  - **žádná** – podání se nálezů netýká (kampaň, volitelnost kandidátů, průběh hlasování…).
- `odkaz_navrh`, `sveseni` – odkaz na soubor návrhu na úřední desce a datum svěšení (po něm odkaz přestane fungovat).
- **K doplnění po rozhodnutí:**
  - `rozhodnuti` – vyhověno / zamítnuto / odmítnuto / zastaveno;
  - `datum_rozhodnuti`;
  - `prepocet` – ano / ne (zda soud přepočítal hlasovací lístky);
  - `nalez_potvrzen` – ano / ne / částečně (zda přepočet potvrdil chybu, kterou nález označil);
  - `zmena_slozeni` – ano / ne (zda se změnilo složení zastupitelstva nebo zvolení kandidáti);
  - `poznamka` – zjištěné skutečné počty hlasů apod.

## Stav k 1. 11. 2026 – souhrn

| Vztah | Praha | Kraje | Celkem |
|---|---|---|---|
| přesná | 9 | 10 | 19 |
| částečná | 6 | 3 | 9 |
| obecná | 2 | 58 | 60 |
| nejistá | 2 | 3 | 5 |
| mezera | 1 | 2 | 3 |
| žádná | 13 | 98 | 111 |

**Přesné shody, na které je třeba po rozhodnutí doplnit výsledek:**

- Praha 10, okrsek 10043 (N01, Křehlík 165 místo ~16; Naše Praha 10 by klesla pod 5 %) – 9 A 68, 9 A 70, 18 A 53, 10 A 67, 3 A 116, 5 A 68. ÚMČ Praha 10 ve vyjádření připouští písařskou chybu.
- Praha 10, okrsky 10028, 10082, 10106, 10100 (N17, N12, N11) – 10 A 67 (eventuální petit), 5 A 71, 5 A 68, 18 A 54.
- Praha 15, okrsek 15003 (N02, chybějící balík ~196 lístků, možný 17. mandát Patnáctky) – 17 A 63, 12 A 90.
- Praha 3, okrsek 3038 (N11, Papež 65→5) – 10 A 64; okrsek 3052 (N11, Kusáková 353→35) – 15 A 67 (jen z médií).
- Praha 2, okrsek 2029 (N14) – 17 A 66; Praha 1, okrsek 1019 (N13) – 12 A 92; Praha 12, okrsky 12048, 12005, 12028 (N11) – 3 A 115.
- Plzeň 1, okrsek 1024 (N01, Chvalová 325 místo ~35; mění zvolenou kandidátku) – 77 A 87, 77 A 88.
- Most, okrsek 30 (N01, VIZE pro Most; mění mandáty) – 115 A 6.
- Liberec, okrsky 72 a 50 (N02, Zámečník 11 místo ~116, Levko 4 místo ~46) – 64 A 11.
- Kladno, okrsek 29 (N01, chybějící balík KLADEŇÁCI) – 51 A 85, 51 A 86.
  Analýza odhadla schodek 2 300–2 700 hlasů, ke změně mandátu je třeba 3 339; členka komise uvádí přes 3 200 hlasů místo 287.
- Uherské Hradiště, okrsek 13 (N01, nezapsané hlasy) – 73 A 33. Analýza odhadla schodek ANO ~381 při rezervě 481; návrh uvádí až 1 485.
- Brno-střed, okrsek 23038 (N31, Blatecká 99 místo ~9) – 67 A 24; Brno-Líšeň, okrsek 14015 (N12) – 67 A 23.
- Černá v Pošumaví (N01, 0 hlasů zesnulého kandidáta P. Badáně – komise je nezapočítala) – 52 A 13.

**Mezery analýzy (k poučení pro detektory):**

- Praha 12, okrsek 12025 – TOP 09 má u 27 z 35 kandidátů 0, Občané dvanáctky +492 hlasů; Občané dvanáctky nad 5 % jen o 145 hlasů (17 A 65, 3 A 115).
  Analýza to zachytila jen v porovnání lístků MČ a magistrátu (z = −3,7), nález nevykázala; nuly nejsou na konci kandidátky.
- Býkev – kandidátovi zapsáno 114 místo 141 (přehozené číslice); **soud vyhověl** (54 A 55, volba L. Kolmana neplatná). Detektor překlepů záměnu číslic nemodeluje.
- Kolín, okrsek 10 – soud při přepočtu našel chybu komise (3 kandidáti ODS s 0), bez vlivu na mandáty (41 A 88, zamítnuto).

Tři podání naši analýzu přímo citují: 10 A 67 (příloha 3 – tisk stránky nálezů Prahy), 17 A 63 (odkaz na #N02) a 12 A 90 (web jako důkaz).

## Zdroj dat a jeho veřejnost

Elektronické úřední desky soudů na <https://infodeska.gov.cz/eudpub/>; výpis desky vrací
`POST https://infodeska.gov.cz/eudpub/api/v1/vyveseni/vyhledej` s tělem `{"kodSubjektu": "<kód>"}`,
soubory `GET .../vyveseni/soubor/<id>/download`. Pobočky mají vlastní desky (203001 Tábor, 205001 Liberec, 206001 Pardubice,
207001 Jihlava, 207002 Zlín, 208001 Olomouc); volební věci poboček se zrcadlí i na desce hlavního soudu.

Ve volebních věcech soud doručuje vyvěšením na úřední desce (§ 93 odst. 5 s. ř. s.), proto jsou návrhy, výzvy i rozhodnutí veřejně
dostupné – ale jen dočasně (zpravidla 15–30 dní). Úplnost k 1. 11. byla ověřena pro KS Praha proti jeho samostatnému seznamu
podaných návrhů (27 z 27); u ostatních soudů mohou chybět věci rozhodnuté a svěšené dříve. Řízení o místním referendu
a o volbách do Senátu nejsou zahrnuta. Popisy podání a vazby na nálezy byly sestaveny s pomocí AI z textů dokumentů;
naskenované návrhy byly posuzovány podle obrazu stránek či podle výzev soudu.

## Postup pro závěrečné vyhodnocení

1. Průběžně (dokud soudy dokumenty nesvěsí) spouštět `python scripts/soudy_stav.py` – vznikne `soudy/stav_<datum>.csv`.
   Volba `--zapsat` doplní rozhodnutí do prázdných sloupců `rozhodnuti` / `datum_rozhodnuti`. Výrok je vždy vhodné zkontrolovat
   – navržený stav se odvozuje z textu, který z části PDF (skeny) vytáhnout nelze.
2. U řízení se vztahem přesná / částečná / mezera přečíst usnesení (odůvodnění obsahuje výsledek přepočtu) a doplnit
   `prepocet`, `nalez_potvrzen`, `zmena_slozeni`, `poznamka`.
3. Po vyhlášení opravených výsledků stáhnout znovu data ČSÚ (`scripts/download.py`) a porovnat opravené okrsky s nálezy.
4. Závěrečná tabulka: řádky s `nalez_potvrzen` = ano/částečně, sloupce nález, okrsek, odhad analýzy, skutečnost po přepočtu,
   `zmena_slozeni`.
