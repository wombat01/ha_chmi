# ČHMÚ pro Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Release](https://img.shields.io/github/v/release/wombat01/ha_chmi)](https://github.com/wombat01/ha_chmi/releases)
[![Validace](https://github.com/wombat01/ha_chmi/actions/workflows/hassfest.yml/badge.svg)](https://github.com/wombat01/ha_chmi/actions/workflows/hassfest.yml)

Aktuální počasí z **automatických meteorologických stanic Českého
hydrometeorologického ústavu** přímo v Home Assistantu. Teplota, vlhkost, tlak,
srážky, sluneční svit a vítr z nejbližší profesionální stanice — měřené každých
deset minut, bez API klíče a bez registrace.

## Co umí

- 🌡️ **Teplota, vlhkost, tlak** včetně dopočítaného rosného bodu a pocitové teploty
- 🌧️ **Srážky** — aktuální intenzita, úhrn za hodinu, za 24 hodin a za dnešek
- ☀️ **Sluneční svit** od půlnoci
- 💨 **Vítr** — rychlost, nárazy, směr ve stupních i jako světová strana (S, SSV, SV…)
- 📈 **Tendence tlaku** za poslední 3 hodiny
- 🔽🔼 **Denní minimum a maximum teploty**
- ⏱️ Data se stahují hned po zveřejnění, takže zpoždění je jen kolem minuty
- 🛡️ Odolné vůči výpadkům — denní úhrny přežijí restart Home Assistantu

## Instalace

### Přes HACS (doporučeno)

[![Otevřít v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=wombat01&repository=ha_chmi&category=integration)

Nebo ručně:

1. Otevřete **HACS** a vpravo nahoře klikněte na **⋮ → Vlastní repozitáře**.
2. Vložte adresu `https://github.com/wombat01/ha_chmi` a jako typ zvolte **Integrace**.
3. Vyhledejte **ČHMÚ**, klikněte na **Stáhnout** a restartujte Home Assistant.

### Ručně

Zkopírujte složku `custom_components/chmi` do `config/custom_components/chmi`
a restartujte Home Assistant.

## Nastavení

[![Přidat integraci](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=chmi)

1. **Nastavení → Zařízení a služby → Přidat integraci → ČHMÚ**
2. Zadejte **kód stanice**, např. `O1KRNO01`.

**Kde najít kód stanice:** na [chmi.cz](https://www.chmi.cz) otevřete stránku
požadované stanice — kód je součástí adresy stránky. Dialog kód hned ověří,
takže překlep odhalí ještě před vytvořením integrace.

Chcete víc stanic? Přidejte integraci znovu s jiným kódem.

## Entity

| Entita | Popis | Výchozí |
| --- | --- | :---: |
| Teplota | poslední naměřená hodnota | ✅ |
| Vlhkost | poslední naměřená hodnota | ✅ |
| Tlak | poslední naměřená hodnota | ✅ |
| Rosný bod | dopočítáno z teploty a vlhkosti | ✅ |
| Pocitová teplota | dopočítáno z teploty, vlhkosti a větru | ✅ |
| Tendence tlaku za 3 h | rozdíl oproti hodnotě před třemi hodinami | ✅ |
| Intenzita srážek | aktuální intenzita v mm/h | ✅ |
| Srážky za 1 h | klouzavý úhrn | ✅ |
| Srážky za 24 h | klouzavý úhrn | ➖ |
| Srážky dnes | úhrn od půlnoci | ✅ |
| Sluneční svit dnes | hodiny svitu od půlnoci | ✅ |
| Rychlost větru | průměrná rychlost; směr je v atributech `direction` a `cardinal` | ✅ |
| Nárazy větru | nejsilnější náraz poslední desetiminutovky | ➖ |
| Nejsilnější náraz za 24 h | maximum za posledních 24 hodin | ➖ |
| Směr větru, Směr nárazu | ve stupních | ➖ |
| Min. / max. teplota dnes | extrémy od půlnoci | ✅ |

Entity označené ➖ jsou ve výchozím stavu vypnuté, aby seznam nebyl zahlcený.
Zapnete je v detailu zařízení stanice.

## Příklad automatizace

Upozornění, když začne pršet:

```yaml
automation:
  - alias: "Začalo pršet"
    trigger:
      - platform: numeric_state
        entity_id: sensor.chmi_o1krno01_precipitation_intensity
        above: 0
    action:
      - service: notify.notify
        data:
          message: "Na stanici ČHMÚ začalo pršet."
```

## Jak to funguje

<details>
<summary><b>Dotazování</b></summary>

ČHMÚ zveřejňuje desetiminutová data zhruba 10,5 minuty po konci intervalu.
Integrace se proto neptá naslepo, ale jednou za interval krátce po zveřejnění
(v X:01:30, X:11:30, …). Když se publikace opozdí, dotaz jednou zopakuje
o tři minuty později.

Používají se jen dva dotazy (`klima-10m` a `vitr-10m`). Detail stanice se
stahuje jen jednou při nastavení — obsahuje totiž i ~200 kB fotografii.

</details>

<details>
<summary><b>Proč jsou srážky řešené takhle</b></summary>

Stanice hlásí **úhrn za deset minut**, ne okamžitou hodnotu. Proto:

- *Intenzita srážek* platí jen pro svůj interval. Když jsou data stará, přejde
  do stavu `nedostupné`, místo aby držela starou hodnotu — jinak by
  `utility_meter` nebo `integration` sčítaly déšť, který nespadl.
- Úhrny (1 h, 24 h, dnes) se počítají z řady vrácené ČHMÚ (zhruba 48 hodin),
  ne z historie Home Assistantu. Přežijí tak restart i výpadek spojení.
- Krátce po půlnoci, než ČHMÚ zveřejní první dnešní měření, jsou denní entity
  (srážky, svit, min./max. teplota) nedostupné, aby neukazovaly včerejší hodnoty.

</details>

<details>
<summary><b>Výpadky</b></summary>

Okamžité veličiny (teplota, tlak, vítr…) se při jednorázovém výpadku drží
z minula, aby v grafu nevznikla díra. Po dvou hodinách bez nových dat se
entity označí za nedostupné.

</details>

## Hlášení chyb

Chyby a nápady hlaste přes [GitHub Issues](https://github.com/wombat01/ha_chmi/issues).
Přiložte prosím **diagnostiku** (detail zařízení → ⋮ → Stáhnout diagnostiku),
obsahuje poslední stažená data a polohu stanice.

## Zdroj dat

Data poskytuje [Český hydrometeorologický ústav](https://www.chmi.cz).
Tato integrace není oficiálním produktem ČHMÚ.
