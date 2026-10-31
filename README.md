# ČHMÚ Meteostanice pro Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Release](https://img.shields.io/github/v/release/wombat01/ha_chmi)](https://github.com/wombat01/ha_chmi/releases)
[![Validace](https://github.com/wombat01/ha_chmi/actions/workflows/ci.yml/badge.svg)](https://github.com/wombat01/ha_chmi/actions/workflows/ci.yml)

Aktuální počasí z **automatických meteorologických stanic ČHMÚ** přímo
v Home Assistantu — teplota, vlhkost, tlak, srážky, sluneční svit a vítr,
měřené každých deset minut.

## Instalace

[![Otevřít v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=wombat01&repository=ha_chmi&category=integration)

Nebo v **HACS → ⋮ → Vlastní repozitáře** přidejte
`https://github.com/wombat01/ha_chmi` jako **Integrace**, stáhněte ji
a restartujte Home Assistant.

## Nastavení

[![Přidat integraci](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=chmi)

**Nastavení → Zařízení a služby → Přidat integraci → ČHMÚ Meteostanice** a zadejte kód
stanice, např. `O1KRNO01`. Kódy najdete v
[seznamu meteorologických stanic ČHMÚ](https://www.chmi.cz/namerena-data/umisteni-mericich-stanic/meteorologicke).
Pro víc stanic přidejte integraci znovu.

## Entity

| Entita                                         | Popis                                         | Výchozí |
| ---------------------------------------------- | --------------------------------------------- | :-----: |
| Teplota, Vlhkost, Tlak                         | poslední naměřená hodnota                     |    ✅    |
| Rosný bod, Pocitová teplota                    | dopočítáno                                    |    ✅    |
| Tendence tlaku za 3 h                          | rozdíl oproti hodnotě před třemi hodinami     |    ✅    |
| Intenzita srážek                               | aktuální intenzita v mm/h                     |    ✅    |
| Srážky za 1 h, Srážky dnes                     | úhrn                                          |    ✅    |
| Srážky za 24 h                                 | klouzavý úhrn                                 |    ➖    |
| Sluneční svit dnes                             | hodiny svitu od půlnoci                       |    ✅    |
| Rychlost větru                                 | směr je v atributech `direction` a `cardinal` |    ✅    |
| Nárazy větru, Nejsilnější náraz za 24 h        |                                               |    ➖    |
| Směr větru, Směr nárazů větru                  | ve stupních                                   |    ➖    |
| Minimální teplota dnes, Maximální teplota dnes | extrémy od půlnoci                            |    ✅    |

Entity označené ➖ jsou ve výchozím stavu vypnuté, zapnete je v detailu
zařízení stanice.

## Jak to funguje

- Data se stahují hned po zveřejnění ČHMÚ (v X:01:30, X:11:30, …), zpoždění je
  tak jen kolem minuty.
- Úhrny srážek a svitu se počítají z řady vrácené ČHMÚ (zhruba 48 hodin), takže
  přežijí restart Home Assistantu i výpadek spojení.
- _Intenzita srážek_ je při starých datech nedostupná, aby `utility_meter`
  nesčítal déšť, který nespadl.
- Krátce po půlnoci, než ČHMÚ zveřejní první dnešní měření, jsou denní entity
  nedostupné, aby neukazovaly včerejší hodnoty.
- Po dvou hodinách bez nových dat se entity označí za nedostupné.

## Hlášení chyb

Přes [GitHub Issues](https://github.com/wombat01/ha_chmi/issues), ideálně
s přiloženou **diagnostikou** (detail zařízení → ⋮ → Stáhnout diagnostiku).

---

Data: [Český hydrometeorologický ústav](https://www.chmi.cz). Integrace není
oficiálním produktem ČHMÚ.
