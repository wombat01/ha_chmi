DOMAIN = "chmi"
PLATFORMS = ["sensor"]
DEFAULT_SCAN_INTERVAL = 600
DEFAULT_STATION_ID = "O1KRNO01"

CONF_STATION_ID = "station_id"

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Referer": "https://www.chmi.cz/",
    "Accept": "application/json",
}

URL_STATION_DETAIL = "https://data-provider.chmi.cz/api/stations/data/meteo/{}"
URL_PRECIPITATION = (
    "https://data-provider.chmi.cz/api/graphs/graf.meteo-stanice.srazky-10m/{}"
)
URL_TEMPERATURE = (
    "https://data-provider.chmi.cz/api/graphs/graf.meteo-stanice.teplota-10m/{}"
)
URL_CLIMATE = "https://data-provider.chmi.cz/api/graphs/graf.meteo-stanice.klima-10m/{}"
URL_WIND = "https://data-provider.chmi.cz/api/graphs/graf.meteo-stanice.vitr-10m/{}"
URL_STATION_INIT = (
    "https://data-provider.chmi.cz/api/stations/init/meteo-stanice?ghId={}"
)
