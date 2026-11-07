# Code review: program ČSÚ pro okrskové volební komise (KV 2026)

Statická analýza veřejně distribuované definitivní verze programu `KVokrsek` pro komunální volby 9.–10. 10. 2026.
Cílem bylo zjistit, jaké kontroly program skutečně implementuje, zda odpovídají dokumentaci a zda jsou implementované správně.
Stav k 7. 11. 2026.

## Shrnutí

1. **Kontroly hlasů jsou implementované správně.** Číselné kontroly z dokumentace (Z09, Z20, Z22, Z23, Z25, Z46, I02, I05, I06, I16)
   odpovídají [návodu ČSÚ](../zdroje/kv_okrsek_uplny.pdf) jak ve frontendu (JavaScript), tak v backendu (Rust).
   Logická chyba, která by propustila chybná data, jsem nenašel.
2. **Kontrola I16 („málo platných hlasů“) ve frontendu nikdy nevypadne.** Chybí jí vstup (počet platných kandidátů).
   Backend ji ale při dávkové kontrole po uložení počítá správně, takže upozornění se objeví až v protokolu o kontrolách,
   ne hned při psaní.
3. **I16 je jediná kontrola na chybějící hlasy a je velmi benevolentní.** Nad daty KV 2026 by upozornila u **18 z 16 649**
   záznamů okrsek × zastupitelstvo (0,1 %). Z 306 nálezů typu chybějící balík, nezapsané hlasy, posun nebo propad by zachytila **6**
   a z 15 nálezů s vlivem na mandáty jen **2**.
4. **Program nemá žádnou kontrolu tvaru kandidátky.** Kandidát s nulou uprostřed jinak silné kandidátky, posunutý úsek ani skok
   na hranici stránky sčítacího archu (33/34) nevyvolají žádné hlášení. To potvrzuje mezery popsané v [../README.md](../README.md), kap. 4.
5. **Drobné nesoulady mezi kódem a dokumentací:**
   - podmínky I03 a I04 se liší od návodu;
   - 19 technických kontrol T01–T22 není v návodu popsáno;
   - frontend a backend se liší u I03.

## Metoda

- **Stažení:**
  - demoverze [KVokrsek1_demo.exe](https://volby.gov.cz/prg/KVokrsek1_demo.exe) (18. 9. 2026);
  - definitivní verze `https://volby.gov.cz/op_pdf/kv/prg/KVokrsek1100.exe` (8. 10. 2026, Praha, verze souboru 7.0.33):
    - SHA-256 `be70c9ec6918c293e6fab1fe63c9e856fbcd7c9bd59fad74bac13d59dafa4a5c`;
    - instalátor NSIS.
- **Nic se nespouštělo.** Instalátor jsem jen rozbalil 7-Zipem. Aplikace je postavená na Tauri 2.11 (backend Rust, 32bitový x86;
  frontend SvelteKit ve WebView2).
- **Frontend:** soubory jsou v exe uložené komprimované (brotli) v mapě assetů Tauri. Vytáhl jsem je vlastním extraktorem
  a zformátoval Prettierem.
- **Backend:** disassembly konkrétních funkcí (capstone). Kontroly jsou v tabulce *(funkce, kód kontroly)*, kterou šlo dohledat
  přes odkazy na texty kódů.
- **Šifrovaná data jsem nedešifroval.** Registry kandidátů a okrsků (`*.kjson`) jsou šifrované klíčem v aplikaci
  a nebyly potřeba, logika kontrol je mimo ně.
- **Lokální soubory:** `stazeno/`, `rozbaleno/`, `frontend/` a `frontend_citelny/` jsou jen lokální a jsou v `.gitignore`.
  Jde o autorské dílo ČSÚ, necommitovat ani nezveřejňovat.

## Architektura kontrol

| Vrstva | Kde | Kdy běží | Poznámka |
|---|---|---|---|
| Frontend | `nodes/3.*.js`, pole pravidel `{code, fields, phases, onlyModes, onlyElectionTypes, validate}` | interaktivně při opuštění pole (`blur`), při přechodu stránky, při uložení (`submit`) | **jeden engine pro KV i Senát a pro tři režimy:** `okrsek` (OVK), `pm` (přebírací místo), `centrum` |
| Backend | Rust crate `kontroly` (z cest v binárce), tabulka 62 kontrol | dávkově po stisku Uložit; výsledek je „Protokol o kontrolách“ | export je zablokovaný, dokud data obsahují chyby nebo nebyly po editaci spuštěny kontroly |

**Kódy v backendu:**
- **Z:** Z01–Z05, Z07–Z14, Z17, Z19, Z20, Z22, Z23, Z25–Z27, Z30–Z32, Z34, Z35, Z38, Z44–Z46;
- **P:** P01–P04, P06, P07;
- **I:** I01–I07, I15, I16;
- **T:** T01–T07, T09, T10, T14–T22.

Kontroly T jsou technické kontroly záznamů (kontrolní součty `KC_SUM`, typ formuláře, příznaky, licence a časové údaje).
Návod je nezmiňuje.

**Zajímavost pro jednání s ČSÚ:** stejný engine pravidel běží v režimech `pm` (přebírací místo) a `centrum`. Některé kontroly mají
`onlyModes: [pm]` (Z10–Z14) nebo `[pm, centrum]` (Z45). **Infrastruktura pro kontroly specifické pro přebírací místo tedy už
existuje** a nové kontroly ze srovnání s jinými okrsky nebo s minulými volbami by do ní šlo přidat bez zásahu do programu OVK.

## Ověření jednotlivých kontrol

Podmínky jsou zapsané tak, jak je kód implementuje: hlášení vypadne, když platí uvedená podmínka.

| Kód | Dokumentace | Frontend (JS) | Backend (Rust) | Verdikt |
|---|---|---|---|---|
| Z09 | hlasy ≤ lístky × mandáty | `PL_HL_CELK > PLAT_LISTKY × M` | `cmp [PL_HL_CELK], M*[PLAT_LISTKY]; jbe ok` | ✅ |
| Z20 | Σ hlasů stran = hlasy celkem | jen režim `okrsek` | Σ `POC_HLASU` stran ≠ `PL_HL_CELK` | ✅ |
| Z22 | kandidát ≤ hlasy strany | ano | ano | ✅ (hlasy strany se sčítají z kandidátů, takže tato kontrola nemůže vypadnout) |
| Z23 | kandidát ≤ platné lístky | ano | ano | ✅ |
| Z25 | Σ kandidátů = hlasy strany | ano | ano | ✅ (opět automaticky splněno) |
| Z46 | hlasy ≥ lístky | ano | `PL_HL_CELK ≥ PLAT_LISTKY` | ✅ |
| I02 | odevzdané < 80 % vydaných a rozdíl > 10 | ano | `⌊odevzd·100/vyd⌋ ≤ 79 ∧ vyd−odevzd ≥ 11` | ✅ |
| I05 | lístky < 85 % obálek a rozdíl > 2 | ano | ano (85,0; rozdíl ≥ 3) | ✅ |
| I06 | −9…+14 nebo −17 %…+30 % od očekávaného | ano (83–130 %, zaokrouhleno) | ano (83,0–130,0, zaokrouhleno) | ✅ |
| **I16** | hlasy < 60 % × lístky × M, při méně kandidátech úměrně méně | **nikdy nevypadne**: `context.pocetPlatnychKandidatu` se nikde nenastavuje | práh = 60 / max(2M / kandidátů; 1) / 100 × lístky × M; hlášení při `PL_HL_CELK ≤ práh` | ⚠️ frontend nefunkční, backend ✅ |
| I03 | voličů ≥ 2000 | hlášení **potlačí**, pokud počet sedí s očekávanou hodnotou okrsku | hlásí vždy při ≥ 2000 | ⚠️ nesoulad frontend × backend |
| I04 | účast < 10 % | navíc jen při vydaných obálkách ≤ 150 | totéž (≤ 150, < 10,0 %) | ⚠️ podmínka chybí v návodu |
| Z10–Z13 | v návodu jako závažné | jen v režimu `pm` | registrované | ℹ️ v programu OVK se hodnoty vyplňují automaticky |
| T01–T22 | – | seznam kódů je jen v příznaku `CHYBA` | implementované | ℹ️ nezdokumentováno |

### Nález 1: I16 ve frontendu je mrtvý kód (nízká závažnost)

```js
// frontend_citelny/3.BPOx5KML.js, ř. 3980–3995 (zkráceno)
const ai = { code: "I16", fields: [E.PL_HL_CELK], phases: [u.BLUR, u.SUBMIT, u.FULL],
  validate(e) {
    const t = Number(e.t3?.PL_HL_CELK ?? 0), n = Number(e.t3?.PLAT_LISTKY ?? 0),
          r = ri(e), c = Number(e.context?.pocetPlatnychKandidatu ?? 0);
    if (n <= 0 || r == null || r <= 0 || c <= 0) return null;   // c je vždy 0 → konec
    ...
```

- **Proč nevypadne:** klíč `pocetPlatnychKandidatu` se v celém frontendu vyskytuje jen na tomto jediném místě.
  Žádný ze tří validačních kontextů ho nenastavuje: stránka T/3 (ř. 4394), stránka HL (ř. 4930) ani oddíl III (ř. 5612).
  Demoverze je na tom stejně.
- **Dopad:** komise nedostane upozornění hned po zadání počtu platných hlasů, ale až v protokolu po uložení.
  Tam ho backend vyhodnotí správně.
- **Oprava:** doplnit počet platných kandidátů zastupitelstva do kontextu, např. na stránce T/3 vedle `mandaty`.

### Nález 2: I16 je jako detektor chybějících hlasů prakticky neúčinná (koncepční)

- **Simulace:** stejný vzorec jako v backendu nad všemi okrsky KV 2026 (data ČSÚ, 16 649 záznamů okrsek × zastupitelstvo):

  | | Počet |
  |---|---|
  | Upozornění I16 celkem | **18** (0,1 %) |
  | Využití hlasů (zapsané hlasy / lístky × mandáty): 1. percentil / 5. percentil / medián | 55,7 % / 69,0 % / 91,5 % |
  | Naše nálezy (balík, nezapsané hlasy, posun, propad, nuly) zachycené I16 | **6 z 306** |
  | Z toho nálezy s možným vlivem na mandáty | **2 z 15** |

- **Proč tak málo:** práh 60 % leží hluboko pod běžným rozpětím. Chybějící balík lístků jedné strany sníží využití typicky
  o 5–20 p. b., tedy na 70–85 %. To je pořád vysoko nad prahem.
- **Návrh:**
  - porovnávat využití hlasů s **vlastním okrskem v minulých volbách** a s **ostatními okrsky obce**;
  - data k tomu program už dostává stejným kanálem jako očekávaný počet voličů pro I06;
  - nebo kontrolu přesunout na přebírací místo, kde jsou data všech okrsků (režim `pm`).

### Nález 3: chybí kontroly tvaru kandidátky (koncepční)

- **Co program kontroluje u kandidátů:** jen horní meze (Z22, Z23) a součty (Z25).
- **Co nemůže kontrolovat nic:** z pravidel hlasování plyne, že každý lístek s křížkem u strany dá hlas prvním K = min(počet kandidátů, M)
  kandidátům. Nula nebo prudký propad uprostřed kandidátky s návratem, posunutý úsek kandidátky nebo skok mezi 33. a 34. kandidátem
  (hranice stránky sčítacího archu A4 na šířku) proto v reálných datech nastat nemůže, a přesto žádné hlášení nevyvolá.
- **Návrh:** nový typ *upozornění* (I) vyhodnocený na stránce HL po dokončení strany. Nepotřebuje žádná další data,
  stačí hlasy strany a počet lístků.

### Nález 4: drobnosti v kódu

- **I03 se liší mezi frontendem a backendem.** Frontend potlačí upozornění, když počet voličů ≥ 2000 odpovídá očekávané hodnotě.
  Backend hlásí vždy. Komise tak může při zadávání nevidět nic a v protokolu pak dostat upozornění.
- **Návod je neúplný:**
  - podmínka „vydaných obálek ≤ 150“ u I04 v návodu chybí;
  - kontroly T01–T22 nejsou v návodu popsané.
- **Seznam kódů pro příznak `CHYBA` je neúplný.** Seznam ignorovaných kódů, podle kterého frontend nastavuje `t3.CHYBA`,
  neobsahuje Z17, Z26, Z32, Z35 ani Z45 (`chunks/D9-I-Eps.js`). Vliv je pravděpodobně jen kosmetický, protože závažné chyby
  stejně zablokuje backend.
- **Zahozená návratová hodnota:** v obsluze pole `inp-0` (číslo obce) se volá `Z.slice(0, 6)` bez přiřazení.
  Pole je ale needitovatelné, takže bez dopadu.
- **Úplné cesty z prostředí, kde se program sestavoval, v binárce:** obsahují mimo jiné uživatelské jméno vývojáře.
  Doporučení: sestavovat s `--remap-path-prefix`.

## Co by šlo s ČSÚ probrat

1. **Dostupnost kódu nebo specifikace kontrol.** Program je postavený moderně a kontroly jsou dobře oddělené v deklarativním enginu.
   Zveřejnit seznam pravidel nebo testovací sadu by bylo snadné.
2. **Nové kontroly do režimu `pm`.** Infrastruktura v kódu existuje. Srovnání s ostatními okrsky obce a s minulými volbami
   má největší účinek a nevyžaduje změnu programu OVK.
3. **Kontroly tvaru kandidátky v režimu `okrsek`.** Jsou levné, deterministické a nepotřebují data.
4. **Kalibrace I16.** Případně nahradit srovnáním s historickým využitím hlasů okrsku.
5. **Sjednocení frontendu a backendu.** Opravit I16 ve frontendu, sjednotit I03 a doplnit návod (I04, T kódy).
