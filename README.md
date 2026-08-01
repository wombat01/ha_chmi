# ČHMÚ pro Home Assistant

Integrace načítá data z automatických meteorologických stanic Českého
hydrometeorologického ústavu (`data-provider.chmi.cz`). Stanice měří po
**desetiminutovkách**, čemuž je podřízené chování všech entit.

## Instalace

Nakopírujte obsah repozitáře do `config/custom_components/chmi/` a restartujte
Home Assistant. Poté *Nastavení → Zařízení a služby → Přidat integraci → ČHMÚ*
a zadejte kód stanice (např. `O1KRNO01`).

Kód stanice najdete v adrese stránky stanice na chmi.cz. Dialog kód rovnou ověří
proti API — u překlepu vypíše chybu místo toho, aby vytvořil integraci bez dat.
Při té příležitosti si stáhne jméno stanice a polohu, takže po nastavení už se
detail stanice nikdy netahá.

## Entity

| Entita | Popis |
| --- | --- |
| Teplota, Vlhkost, Tlak | poslední naměřená hodnota |
| Rosný bod | dopočítáno (Magnusova aproximace) |
| Pocitová teplota | dopočítáno (Apparent Temperature) |
| Tendence tlaku za 3 h | rozdíl oproti hodnotě před třemi hodinami |
| Srážky za 10 min | úhrn poslední desetiminutovky |
| Intenzita srážek | tentýž úhrn přepočtený na mm/h |
| Srážky za 1 h / 24 h | klouzavý úhrn |
| Srážky dnes | úhrn od místní půlnoci |
| Sluneční svit za 10 min / dnes | délka svitu (max. 600 s za interval) |
| Rychlost větru, Nárazy, Směr | poslední hodnoty; entita rychlosti nese směr v atributech `direction` (°) a `cardinal` (S, SSV, SV, …), takže samostatnou entitu směru zapínat nemusíš |
| Nejsilnější náraz za 24 h | maximum z řady |
| Min./max. teplota za 24 h | extrémy z řady |

Část entit je ve výchozím stavu vypnutá, aby seznam nebyl zahlcený — zapnete je
v nastavení zařízení.

Všechny entity nesou v atributech `station_id`, `station_name` a čas měření.
Poloha stanice se do atributů nedává — najdete ji v diagnostice integrace.

## Proč jsou srážky řešené takhle

`SRA10M` je **úhrn za deset minut**, ne okamžitá hodnota. Proto:

- entita *Srážky za 10 min* platí jen pro svůj interval. Když stanice mlčí déle
  než 25 minut, přejde do stavu `unavailable` místo aby držela starou hodnotu —
  jinak by každý další polling „napršel“ znovu a `utility_meter` nebo
  `integration` by sčítaly déšť, který nespadl;
- kumulativní entity (1 h, 24 h, dnes) se počítají **z celé řady vrácené API**
  (pokrývá zhruba 48 hodin), ne z historie Home Assistantu. Přežijí tak restart
  i výpadek spojení.

Okamžité veličiny (teplota, tlak, vítr…) se naopak při jednorázovém výpadku
drží z minula, aby v grafu nevznikla díra. Po dvou hodinách ticha stanice se
i ty označí za nedostupné.

## Dotazování

ČHMÚ zveřejňuje desetiminutovku zhruba 10,5 minuty po konci intervalu (bod
13:20 UTC byl dostupný ve 13:30:43 UTC). Integrace se proto ptá jednou za
interval krátce po zveřejnění — v X:01:30, X:11:30, … Když se publikace opozdí,
pozná to podle stáří posledního bodu a dotaz jednou zopakuje o tři minuty
později.

Používají se jen dva endpointy: `klima-10m` (teplota, vlhkost, tlak, srážky,
svit, vítr) a `vitr-10m` (nárazy). Detail stanice — jméno, poloha, ale také
vložená fotografie o velikosti ~200 kB — se stahuje **jednou při prvním
nastavení** a hodnoty se uloží do konfiguračního záznamu, takže po restartu se
už netahá vůbec.

## Zdroj dat

Data: Český hydrometeorologický ústav, https://www.chmi.cz
