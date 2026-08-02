from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "chmi"
PLATFORMS = [Platform.SENSOR]
DEFAULT_STATION_ID = "O1KRNO01"

CONF_STATION_ID = "station_id"
# Statické údaje o stanici se po prvním stažení uloží do config entry,
# aby se 200kB detail (obsahuje fotku stanice) netahal po každém restartu.
CONF_STATION_NAME = "station_name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_ALTITUDE = "altitude"

ATTRIBUTION = "Data: Český hydrometeorologický ústav"

# ČHMÚ publikuje desetiminutovku zhruba 10,5 minuty po konci intervalu (změřeno:
# bod 13:20Z byl dostupný ve 13:30:43Z). Ptáme se proto jednou za interval krátce
# po zveřejnění — jeden dotaz místo slepého pollingu, latence okolo minuty.
POLL_MINUTES = [1, 11, 21, 31, 41, 51]
POLL_SECOND = 30
# Když se publikace opozdí, poslední bod je při dotazu o deset minut starší než
# obvykle — pak dotaz jednou zopakujeme.
EXPECTED_MAX_AGE = timedelta(minutes=25)
STALE_RETRY_DELAY = 180

# Do jakého stáří považujeme poslední bod za "aktuální desetiminutovku".
# Kratší okno by u zpožděné publikace zbytečně mazalo platný úhrn srážek.
#
# Zpoždění se stanici od stanice liší a kolísá i u jedné stanice. Měřeno:
# P1PKAR01 publikuje za 10–11 min, O1KRNO01 za 10–21 min (a občas vydá dva body
# naráz). Poslední bod tedy stárne až na ~31 minut, než dorazí další. Původních
# 30 minut leželo přesně na téhle hranici a intenzita srážek náhodně vypadávala
# do unavailable, zatímco ostatní veličiny se držely přes _CARRY_FORWARD.
FRESH_WINDOW = timedelta(minutes=45)
# Po jak dlouhém tichu stanice prohlásíme entity za nedostupné.
MAX_DATA_AGE = timedelta(hours=2)

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Referer": "https://www.chmi.cz/",
    "Accept": "application/json",
}

URL_STATION_DETAIL = "https://data-provider.chmi.cz/api/stations/data/meteo/{}"
# klima-10m nese T, H, P_hm, SRA10M, SSV10M, D i F — samostatné endpointy
# teplota-10m a srazky-10m jsou proto redundantní a nedotazují se.
URL_CLIMATE = "https://data-provider.chmi.cz/api/graphs/graf.meteo-stanice.klima-10m/{}"
# vitr-10m přidává navíc nárazy (Fmax, Dmax).
URL_WIND = "https://data-provider.chmi.cz/api/graphs/graf.meteo-stanice.vitr-10m/{}"
URL_STATION_INIT = (
    "https://data-provider.chmi.cz/api/stations/init/meteo-stanice?ghId={}"
)

# Kódy veličin, jak je ČHMÚ vrací (viz "dial" v odpovědi API).
KEYS_PRECIPITATION = ("SRA10M", "SRA", "SRA_10M")
KEYS_SUNSHINE = ("SSV10M", "SS", "SS_10M")
KEYS_TEMPERATURE = ("T",)
KEYS_HUMIDITY = ("H",)
KEYS_PRESSURE = ("P_hm", "P")
KEYS_WIND_SPEED = ("F", "F_mean")
KEYS_WIND_GUST = ("Fmax", "F_max")
KEYS_WIND_DIR = ("D", "D_mean")
KEYS_WIND_GUST_DIR = ("Dmax", "D_max")

# Šestnáctidílná růžice v české notaci.
CARDINALS = (
    "S", "SSV", "SV", "VSV", "V", "VJV", "JV", "JJV",
    "J", "JJZ", "JZ", "ZJZ", "Z", "ZSZ", "SZ", "SSZ",
)
