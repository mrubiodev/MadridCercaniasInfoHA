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
EXPLORER_MAX_POSITIONS_ATTR = 30

# Lineas del nucleo Madrid
MADRID_LINES = ["C1", "C2", "C3", "C4", "C5", "C7", "C8", "C10"]
LINE_OPTIONS = [{"value": "", "label": "Cualquier linea"}] + [
    {"value": line, "label": line} for line in MADRID_LINES
]

# Configuracion por defecto
DEFAULT_N_TRAINS = 3
SCAN_INTERVAL_SECS = 30
GTFS_MAX_AGE_SECS = 7 * 24 * 3600
GTFS_BATCH_SIZE = 10_000
TZ_MADRID = "Europe/Madrid"
