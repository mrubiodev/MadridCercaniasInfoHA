"""Constantes de la integracion Renfe Cercanias."""

DOMAIN = "renfe_cercanias"
CONF_JOURNEYS = "journeys"
CONF_MANAGED_BY = "managed_by"
MANAGED_BY_UI = "ui"
MANAGED_BY_YAML = "configuration.yaml"

# URLs oficiales Renfe (CC BY 4.0)
GTFS_STATIC_URL = "https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip"
RT_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates.json"
RT_POSITIONS_URL = "https://gtfsrt.renfe.com/vehicle_positions.json"

# Claves de configuracion por trayecto
CONF_JOURNEY_NAME = "journey_name"
CONF_STOP_ID = "stop_id"
CONF_STOP_NAME = "stop_name"
CONF_DESTINATION_ID = "destination_id"  # Estacion final (destino) - IMPORTANTE para filtrar direccion
CONF_DESTINATION_NAME = "destination_name"
CONF_LINE = "line"
CONF_N_TRAINS = "n_trains"
CONF_ACTIVE_FROM = "active_from"  # "HH:MM" o "" (siempre activo)
CONF_ACTIVE_TO = "active_to"

# Claves internas hass.data
KEY_GTFS = "gtfs_manager"
KEY_COORDINATOR = "coordinator"
KEY_EXPLORER = "explorer_state"
KEY_EXPLORER_ENTITY_CREATED = "explorer_entity_created"
KEY_EXPLORER_OWNER_ENTRY = "explorer_owner_entry"

# Explorador (consulta temporal sin crear trayecto fijo)
SERVICE_EXPLORE = "explore"
SERVICE_CLEAR_EXPLORER = "clear_explorer"
SIGNAL_EXPLORER_UPDATED = "renfe_cercanias_explorer_updated"
EXPLORER_MAX_POSITIONS_ATTR = 250

# Lineas del nucleo Madrid
MADRID_LINES = ["C1", "C2", "C3", "C4", "C5", "C7", "C8", "C9", "C10"]
LINE_OPTIONS = [{"value": "", "label": "Cualquier linea"}] + [
    {"value": line, "label": line} for line in MADRID_LINES
]

# Estaciones populares de Madrid (fallback inmediato para selectores)
MADRID_POPULAR_STATIONS = [
    {"stop_id": "18000", "name": "Madrid - Atocha Cercanías"},
    {"stop_id": "17000", "name": "Madrid - Chamartín"},
    {"stop_id": "18001", "name": "Madrid - Nuevos Ministerios"},
    {"stop_id": "18003", "name": "Madrid - Sol"},
    {"stop_id": "18005", "name": "Madrid - Méndez Álvaro"},
    {"stop_id": "18004", "name": "Madrid - Recoletos"},
    {"stop_id": "98305", "name": "Madrid - Príncipe Pío"},
    {"stop_id": "10001", "name": "Aeropuerto T4"},
    {"stop_id": "18002", "name": "Alcalá de Henares"},
    {"stop_id": "18008", "name": "Alcalá Universidad"},
    {"stop_id": "35002", "name": "Alcobendas - S.S. Reyes"},
    {"stop_id": "19001", "name": "Alcorcón"},
    {"stop_id": "60000", "name": "Aranjuez"},
    {"stop_id": "11000", "name": "Aravaca"},
    {"stop_id": "18009", "name": "Azuqueca"},
    {"stop_id": "13006", "name": "Cercedilla"},
    {"stop_id": "60002", "name": "Ciempozuelos"},
    {"stop_id": "35004", "name": "Colmenar Viejo"},
    {"stop_id": "18006", "name": "Coslada"},
    {"stop_id": "19003", "name": "Cuatro Vientos"},
    {"stop_id": "13000", "name": "El Escorial"},
    {"stop_id": "37002", "name": "Fuenlabrada"},
    {"stop_id": "12002", "name": "Galapagar - La Navata"},
    {"stop_id": "37000", "name": "Getafe Central"},
    {"stop_id": "60005", "name": "Getafe Sector 3"},
    {"stop_id": "18010", "name": "Guadalajara"},
    {"stop_id": "37004", "name": "Humanes"},
    {"stop_id": "19002", "name": "Las Retamas"},
    {"stop_id": "12000", "name": "Las Rozas"},
    {"stop_id": "37001", "name": "Leganés"},
    {"stop_id": "11002", "name": "Majadahonda"},
    {"stop_id": "19000", "name": "Móstoles"},
    {"stop_id": "19004", "name": "Móstoles - El Soto"},
    {"stop_id": "37005", "name": "Parla"},
    {"stop_id": "60004", "name": "Pinto"},
    {"stop_id": "11001", "name": "Pozuelo"},
    {"stop_id": "19005", "name": "San José de Valderas"},
    {"stop_id": "18007", "name": "San Fernando de Henares"},
    {"stop_id": "12001", "name": "Torrelodones"},
    {"stop_id": "18011", "name": "Torrejón de Ardoz"},
    {"stop_id": "60003", "name": "Valdemoro"},
    {"stop_id": "18012", "name": "Vallecas"},
    {"stop_id": "18013", "name": "Vicálvaro"},
    {"stop_id": "12004", "name": "Villalba"},
    {"stop_id": "37006", "name": "Villaverde Alto"},
    {"stop_id": "60006", "name": "Villaverde Bajo"},
    {"stop_id": "37007", "name": "Zarzaquemada"},
]

# Configuracion por defecto
DEFAULT_N_TRAINS = 3
SCAN_INTERVAL_SECS = 30
GTFS_MAX_AGE_SECS = 7 * 24 * 3600
GTFS_BATCH_SIZE = 10_000
TZ_MADRID = "Europe/Madrid"
