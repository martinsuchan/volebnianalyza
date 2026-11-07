# ČSÚ – volební software pro OVK a obce (rešerše)

Podklady pro jednání s Českým statistickým úřadem o rozšíření kontrol v programu pro okrskové volební komise (OVK).
Rešerše z veřejných zdrojů, stav k 7. 11. 2026.

## Obsah složky

| Cesta | Obsah |
|---|---|
| `README.md` | tato rešerše |
| `zdroje/` | stažené PDF z volby.gov.cz (originály, beze změn) |
| `text/` | text vytažený z PDF (`pdftotext -layout`), pro vyhledávání |
| `kvokrsek/REVIEW.md` | code review programu pro OVK (KV 2026) |
| `kvokrsek/stazeno/`, `rozbaleno/`, `frontend*/` | instalátory a extrahovaný kód, jen lokálně (`.gitignore`), necommitovat |

## 1. Jaký software ČSÚ poskytuje

**Program pro okrskové volební komise.** ČSÚ ho vytváří podle § 65 odst. 3 zákona č. 88/2024 Sb., o správě voleb.
Pro komunální volby 2026 se jmenoval *„Volby do zastupitelstev obcí – program pro okrskové volební komise“*,
instalace `KVokrsek.exe`, na ploše ikona „Obce-pořízení číslo_okrsku“.

- **Účel:** pořízení výsledků okrsku, jejich kontrola a oprava, tisk zápisu T/3 a souhrnného hlasovacího lístku
  a export dat na USB pro přebírací místo ČSÚ.
- **Platforma:** Windows 10/11 a Microsoft Edge WebView2 ve verzi 120 nebo novější. Uživatelské rozhraní tedy
  nejspíš běží ve webové technologii (HTML/JS) uvnitř nativního okna.
- **Instalace a data:**
  - Na jednom počítači lze nainstalovat jen jednu obec, zato libovolný počet okrsků.
  - Při instalaci se zadává číslo obce a okrsku, ve výchozím stavu do `c:\volby`.
  - Kandidátky (strany, kandidáti, odvolaní kandidáti) jsou v programu předem.
  - Program zná i *očekávaný počet voličů okrsku* (kontrola I06), tedy dostává data po okrscích.
- **Používání je dobrovolné.** Pokyny jsou psané pro ruční zpracování, počítač je jen možnost.
  Program se ovládá přes 5 záložek:
  - **T/3 odd. I:** průběh hlasování;
  - **T/3 odd. II:** voliči, obálky, lístky, hlasy celkem;
  - **T/3 odd. II pokračování:** dopočítá se automaticky;
  - **HL:** hlasy kandidátů po stranách, hlasy strany se sečtou automaticky;
  - **T/3 odd. III:** komise.
- **Vstup:** pracovní tiskopis T/3 a vyčleněný hlasovací lístek nebo *pomocné sčítací archy* s čárkami.
  Komise do programu přepisuje už sečtené počty čárek.

**Pomocné sčítací archy.** Vytiskne je program nebo se stáhnou jako PDF na volby.gov.cz (`/op_pdf/kv/`).
Na jeden řádek kandidáta se vejde určitý počet čárek a na stránku určitý počet kandidátů
([kv_okrsek_uplny.pdf](zdroje/kv_okrsek_uplny.pdf), kap. 2):

| Varianta | Kandidátů na stránku | Čárek na řádek |
|---|---|---|
| A4 na šířku | **33** (od 34. kandidáta druhá stránka) | 150 |
| A4 na výšku | 55 | 80 |
| A3 na výšku | všichni | 150 |

**Software pro obce a registrační úřady.** Veřejně dostupný program jsem nenašel.
- Kandidátní listiny se v roce 2026 podávaly papírově nebo datovou schránkou, protože ISSV (informační systém správy voleb) byl odložen.
- Data z kandidátních listin ČSÚ přebírá od registračních úřadů a kontroluje duplicity
  ([MV – registrační řízení 2026](https://mv.gov.cz/volby/soubor/registracni-rizeni-ve-volbach-do-zastupitelstev-obci-v-roce-2026.aspx)).
- Obce pomáhají OVK hlavně s počítačem a tiskárnou.

**Zpracování u ČSÚ.** Asi 500 přebíracích míst je propojeno sítí MPLS s centrálním zpracováním,
odkud jdou data jednosměrně do prezentační databáze volby.gov.cz.
- Na přebíracím místě musí zástupce OVK vysvětlit každou propustitelnou chybu a každé upozornění
  a podepsat k nim protokol (kap. 5.1 návodu).
- Software přebíracích míst a centrálního zpracování veřejně popsaný není.

## 2. Dostupnost ke stažení (ověřeno 7. 11. 2026)

| Soubor | Stav | Poznámka |
|---|---|---|
| [kv_okrsek_uplny.pdf](https://volby.gov.cz/prg/kv_okrsek_uplny.pdf) | dostupný | podrobný návod KV 2026 (8. 10. 2026), **obsahuje úplný seznam kontrol** |
| [kv_okrsek.pdf](https://volby.gov.cz/prg/kv_okrsek.pdf), [kv_okrsek_demo.pdf](https://volby.gov.cz/prg/kv_okrsek_demo.pdf) | dostupné | stručný návod k definitivní verzi a k demoverzi |
| [KVokrsek1_demo.exe](https://volby.gov.cz/prg/KVokrsek1_demo.exe) / [KVokrsek2_demo.exe](https://volby.gov.cz/prg/KVokrsek2_demo.exe) | dostupné | demoverze pro jeden a pro dva typy zastupitelstev (18. 9. 2026, ~7 MB), fiktivní obec 999999 |
| `https://volby.gov.cz/op_pdf/kv/prg/KVokrsek<kód>00.exe` | dostupné | **definitivní verze z 8. 10. 2026**, jeden instalátor na kraj nebo okres (např. `KVokrsek1100.exe`, 5,8 MB), rozcestník [op_pdf/kv/op.html](https://volby.gov.cz/op_pdf/kv/op.html) |
| `https://volby.gov.cz/prg/KVokrsek.exe` | 404 | obecný název uvedený v návodu |
| [SEokrsek2.exe](https://volby.gov.cz/prg/SEokrsek2.exe), [PSokrsek.exe](https://volby.gov.cz/prg/PSokrsek.exe) | dostupné | Senát 2026 (2. kolo) a sněmovní volby 2025 |
| [Pokyny_ZO_2026.pdf](https://volby.gov.cz/prg/Pokyny_ZO_2026.pdf) | dostupný | Pokyny ČSÚ pro OVK, KV 2026 (postup sčítání, sčítací archy, posuzování platnosti) |
| [infookrsky.htm](https://volby.gov.cz/cz/infookrsky.htm) | dostupný | stránka programů pro OVK, teď ukazuje jen Senát; verze z doby KV v [Wayback Machine](https://web.archive.org/web/20261010221953/https://volby.gov.cz/cz/infookrsky.htm) |

**Zdrojové kódy** ČSÚ veřejně nezveřejňuje. Nenašel jsem žádný repozitář, licenci open source ani zmínku o nich.
Program má „licenční číslo“ zobrazené po spuštění.

**Code review aplikace:** viz [kvokrsek/REVIEW.md](kvokrsek/REVIEW.md). Jde o statickou analýzu definitivní verze 7.0.33,
aplikace se nespouštěla. Je postavená na Tauri: Rust backend a SvelteKit frontend s kontrolami v JavaScriptu.

## 3. Co program kontroluje – úplný seznam (KV 2026)

Zdroj: [kv_okrsek_uplny.pdf](zdroje/kv_okrsek_uplny.pdf), kap. 7.
Kontroly běží průběžně při pořizování a znovu dávkově při uložení.

Chyby jsou tří typů:
- **Závažné:** zablokují tisk zápisu i export dat.
- **Propustitelné:** jde je potvrdit, na přebíracím místě se k nim podepisuje protokol.
- **Upozornění:** jen informují.

### a) Závažné chyby (Z)

| Kód | Kontrola |
|---|---|
| Z03, Z05, Z07, Z17 | nepřípustné zastupitelstvo, obvod nebo typ; hlasy pro stranu, která v obvodu nekandiduje |
| Z08 | vydané obálky ≤ zapsaní voliči |
| **Z09** | platné hlasy ≤ platné lístky × počet mandátů |
| Z10, Z11, Z35 | počet stran na lístku; počet stran s hlasy ≤ počet stran; souhlasí se skutečně vyplněnými stranami |
| Z12, Z13 | hlasy > 0 ⇔ aspoň jedna strana s hlasy |
| Z19, Z20 | hlasy strany ≤ hlasy celkem; součet stran = hlasy celkem |
| **Z22, Z23** | hlasy kandidáta ≤ hlasy strany; **hlasy kandidáta ≤ platné lístky** |
| Z25 | součet kandidátů = hlasy strany (v programu se hlasy strany sčítají automaticky) |
| Z26, Z32 | hlasy u neexistujícího nebo odvolaného kandidáta |
| Z34 | vyplnění údajů o komisi (nadpoloviční přítomnost, jména) |
| Z44 | voličské průkazy ≤ vydané obálky |
| **Z46** | platné hlasy ≥ platné lístky |

Navíc platí kontrola dvou typů zastupitelstev (město + MČ/MO): počty voličů a obálek musí být v obou zápisech
shodné, jinak přebírací místo zápis odmítne.

### b) Propustitelné chyby (P)

| Kód | Kontrola |
|---|---|
| P01–P03, P07 | nula zapsaných voličů, vydaných obálek, odevzdaných obálek nebo platných lístků |
| P04 | odevzdané obálky ≤ vydané |
| P06 | platné lístky ≤ odevzdané obálky |

### c) Upozornění (I)

| Kód | Kontrola |
|---|---|
| I01, I04, I07 | účast 100 %, pod 10 %, nad 90 % |
| I02 | odevzdané obálky < 80 % vydaných a rozdíl > 10 |
| I03 | zapsaných voličů ≥ 2000 |
| I05 | platné lístky < 85 % odevzdaných obálek a rozdíl > 2 |
| **I06** | zapsaní voliči mimo rozmezí −9 až +14 nebo −17 % až +30 % od **očekávané hodnoty** (program má data okrsku) |
| I15 | voličské průkazy > 10 % vydaných obálek |
| **I16** | **málo platných hlasů**: hlasy < 60 % z (lístky × mandáty), práh se snižuje úměrně, když je kandidátů méně než dvojnásobek mandátů |

## 4. První srovnání s našimi nálezy – kde jsou mezery

Kontroly programu hlídají **aritmetiku a horní meze**: součty sedí a nic nepřekračuje počet lístků.
Na **chybějící hlasy** je jen jediná slabá kontrola (I16 s prahem 60 %). Žádná kontrola se nedívá na **tvar kandidátky**
a program nemá s čím okrsek srovnat (jiné okrsky, minulé volby). Přesně tyto chyby přitom naše analýza našla.

| Typ chyby z analýzy | Zachytí ji program? | Co by šlo přidat |
|---|---|---|
| **Chybějící balík lístků strany** (celá kandidátka posunutá o stejný počet) | ne – součty sedí, protože chybí důsledně všude | *v OVK:* srovnání se 2022 (viz níže); *na přebíracím místě:* srovnání podílu strany s ostatními okrsky obce |
| **Nízké využití hlasů** (P5, P5b; typicky 64–80 % proti 90–95 % v okolí) | jen pod 60 % (I16) | upozornění na využití hlasů proti **vlastnímu okrsku v minulých volbách**; program už dnes dostává očekávaný počet voličů (I06), stejně by mohl dostat očekávané využití |
| **Propad kandidáta, nuly uprostřed kandidátky, posunutý úsek** (P1–P3) | ne | **kontrola tvaru kandidátky bez externích dat**: u dlouhé kandidátky dostane prvních K = min(počet kandidátů, mandáty) kandidátů každý lístek s křížkem u strany, takže hlasy nemohou klesnout pod úroveň konce kandidátky; nula nebo prudký propad uprostřed s návratem je nemožný |
| **Úsek posunutý od 34. kandidáta** (opakovaný vzorec v analýze) | ne | **potvrzeno návodem**: sčítací arch A4 na šířku má 33 kandidátů na stránku, takže 34. kandidát začíná na druhé stránce. Upozornění, když jsou hlasy kandidátů 34+ (nebo 56+ u A4 na výšku) skokově jiné než u 33 a níž |
| **Překlep u kandidáta** (vložená nebo vypadlá číslice) | jen když hodnota překročí počet lístků (Z23) | upozornění na hodnotu výrazně mimo sousedy na kandidátce (např. 10×, nebo pod úrovní konce kandidátky) |
| **Kritické hodnoty těsných výsledků** | ne (lokální program výsledek nezná) | na přebíracím místě nebo centrálně: seznam okrsků, kde by chyba o pár hlasů změnila mandát, ke kontrole zápisu |

**Kam kontroly patří:**
1. **Do programu OVK (offline, bez dalších dat):** kontroly tvaru kandidátky a návaznost stránek sčítacího archu.
   Jsou deterministické a levné. Patří mezi *upozornění*, ne mezi závažné chyby, a komise je vysvětlí na přebíracím místě.
2. **Do programu OVK s přibalenými daty:** využití hlasů a podíly stran okrsku v minulých volbách.
   Precedens je očekávaný počet voličů u I06.
3. **Na přebíracím místě nebo v centrálním zpracování:** srovnání s ostatními okrsky obce (balík, z-skóre využití hlasů)
   a citlivost mandátů. Tam jsou k dispozici všechna data a komise je ještě na místě, takže případná oprava zápisu
   je nejlevnější.

**Hypotéza k ověření v našich datech:** sčítací arch má na řádek 150 čárek (A4 na výšku jen 80).
Kandidáti s počtem hlasů těsně nad touto hranicí mohou být chybně sečteni (přetečení na další řádek nebo arch).
Ověřit rozdělení hodnot kolem 80 a 150 a srovnat ho s rokem 2022.

## 5. Otevřené otázky pro ČSÚ

1. Kolik OVK v roce 2026 použilo program a kolik zpracovalo zápis ručně? Liší se chybovost?
2. Které kontroly běží na přebíracím místě a v centrálním zpracování navíc oproti programu OVK? Existuje jejich seznam?
3. Jak často OVK propouštějí upozornění (hlavně I16), a jsou protokoly z přebíracích míst k dispozici?
4. Je technicky možné přibalit do programu údaje okrsku z minulých voleb, stejně jako dnes očekávaný počet voličů?
5. Používá se při sčítání víc A4 na šířku, nebo A3? Vzorec od 34. kandidáta ukazuje na A4 na šířku.
6. Jaká je možnost spolupráce na specifikaci kontrol (formát, testovací data), případně přístupu ke zdrojovému kódu nebo k testovací verzi?

## Zdroje

- [Volby.gov.cz – Informace pro okrskové komise](https://volby.gov.cz/cz/infookrsky.htm) (archivní verze z doby KV: [10. 10. 2026](https://web.archive.org/web/20261010221953/https://volby.gov.cz/cz/infookrsky.htm))
- [Program pro OVK – podrobný návod, KV 2026](https://volby.gov.cz/prg/kv_okrsek_uplny.pdf)
- [Pokyny ČSÚ pro OVK, KV 2026](https://volby.gov.cz/prg/Pokyny_ZO_2026.pdf)
- [Rozcestník definitivních programů OVK, KV 2026](https://volby.gov.cz/op_pdf/kv/op.html), [pomocné sčítací archy](https://volby.gov.cz/op_pdf/kv/index.html)
- [Podrobný návod, sněmovní volby 2025](https://volby.gov.cz/prg/ps_okrsek_uplny.pdf), [Senát 2026](https://volby.gov.cz/prg/se_okrsek_uplny.pdf)
- [ČSÚ – Informace o využití výpočetní techniky v práci OVK (PS 2025)](https://csu.gov.cz/docs/107823/3ffc1530-3d9f-c9b9-f50f-e86b671522fa/Info%20o%20VT_PS2025.pdf?version=1.0)
- [MV – Registrační řízení ve volbách do zastupitelstev obcí 2026](https://mv.gov.cz/volby/soubor/registracni-rizeni-ve-volbach-do-zastupitelstev-obci-v-roce-2026.aspx)
