"""Inicializacion de la integracion Renfe Cercanias."""

from __future__ import annotations

import logging
import os
import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    CONF_ACTIVE_FROM,
    CONF_ACTIVE_TO,
    CONF_DESTINATION_ID,
    CONF_JOURNEY_NAME,
    CONF_LINE,
    CONF_N_TRAINS,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_N_TRAINS,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_EXPLORER,
    KEY_EXPLORER_ENTITY_CREATED,
    KEY_EXPLORER_OWNER_ENTRY,
    KEY_GTFS,
    SERVICE_CLEAR_EXPLORER,
    SERVICE_EXPLORE,
    SIGNAL_EXPLORER_UPDATED,
)
from .coordinator import RenfeGtfsManager, RenfeRTCoordinator

PLATFORMS: list[str] = ["sensor", "button", "select"]

_JOURNEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_JOURNEY_NAME): cv.string,
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_STOP_NAME): cv.string,
        vol.Optional(CONF_LINE, default=""): cv.string,
        vol.Optional(CONF_N_TRAINS, default=DEFAULT_N_TRAINS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=5)
        ),
        vol.Optional(CONF_ACTIVE_FROM, default=""): cv.string,
        vol.Optional(CONF_ACTIVE_TO, default=""): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_JOURNEY_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Registra automaticamente las tarjetas Lovelace en Home Assistant."""
    if hass.data.get(DOMAIN, {}).get("frontend_registered"):
        return

    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    if not os.path.exists(frontend_dir):
        return

    # 1. Registrar ruta estática
    try:
        if hasattr(hass.http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPathConfig
            await hass.http.async_register_static_paths([
                StaticPathConfig(
                    "/renfe_cercanias_frontend",
                    frontend_dir,
                    cache_headers=False,
                )
            ])
        elif hasattr(hass.http, "register_static_path"):
            hass.http.register_static_path(
                "/renfe_cercanias_frontend",
                frontend_dir,
                cache_headers=False,
            )
    except Exception as err:
        _LOGGER.debug("Ruta estatica ya registrada o no disponible: %s", err)

    cards = [
        "/renfe_cercanias_frontend/renfe-cercanias-card.js",
        "/renfe_cercanias_frontend/renfe-cercanias-map-card.js",
        "/renfe_cercanias_frontend/renfe-cercanias-config-card.js",
    ]

    # 2. Inyectar en frontend global (extra_js_url)
    try:
        from homeassistant.components.frontend import add_extra_js_url
        for card_url in cards:
            add_extra_js_url(hass, card_url)
    except Exception as err:
        _LOGGER.debug("No se pudo inyectar extra_js_url: %s", err)

    # 3. Registrar directamente en recursos de Lovelace para asegurar disponibilidad
    async def _async_register_lovelace_resources(_event=None) -> None:
        try:
            lovelace = hass.data.get("lovelace")
            if not lovelace:
                return

            resources = getattr(lovelace, "resources", None)
            if resources is None and isinstance(lovelace, dict):
                resources = lovelace.get("resources")

            if resources is None:
                return

            if hasattr(resources, "async_is_loaded") and not resources.async_is_loaded:
                await resources.async_load()

            existing_items = resources.async_items() if hasattr(resources, "async_items") else []
            for card_url in cards:
                base_url = card_url.split("?")[0]
                matching = [
                    item for item in existing_items
                    if item.get("url", "").split("?")[0] == base_url
                ]
                if not matching and hasattr(resources, "async_create"):
                    await resources.async_create({"res_type": "module", "url": card_url})
                elif matching and hasattr(resources, "async_update_item"):
                    for item in matching:
                        if item.get("url") != card_url:
                            await resources.async_update_item(
                                item["id"], {"res_type": "module", "url": card_url}
                            )
        except Exception as err:
            _LOGGER.debug("No se pudieron registrar recursos Lovelace automáticos: %s", err)

    await _async_register_lovelace_resources()
    hass.bus.async_listen_once("homeassistant_started", _async_register_lovelace_resources)

    hass.data.setdefault(DOMAIN, {})["frontend_registered"] = True

SERVICE_REFRESH_GTFS = "refresh_gtfs"

_EXPLORE_SCHEMA = vol.Schema(
    {
        vol.Optional("query", default=""): cv.string,
        vol.Optional(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_DESTINATION_ID): cv.string,
        vol.Optional(CONF_LINE, default=""): cv.string,
        vol.Optional(CONF_N_TRAINS, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=10)
        ),
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Importa trayectos declarados en configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)

    for journey in config.get(DOMAIN, []):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=journey,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura una entrada de trayecto."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)

    if KEY_GTFS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][KEY_GTFS] = RenfeGtfsManager(hass)

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_GTFS):

        async def _async_handle_refresh_gtfs(call) -> None:
            """Servicio para forzar refresco GTFS y recargar sensores."""
            await hass.data[DOMAIN][KEY_GTFS].force_refresh()
            for cfg in hass.config_entries.async_entries(DOMAIN):
                await hass.config_entries.async_reload(cfg.entry_id)

        async_register_admin_service(
            hass,
            DOMAIN,
            SERVICE_REFRESH_GTFS,
            _async_handle_refresh_gtfs,
            schema=vol.Schema({}),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_EXPLORE):

        async def _async_handle_explore(call) -> None:
            """Busca estacion/linea temporal y publica resultado para el Explorador."""
            gtfs = hass.data[DOMAIN][KEY_GTFS]
            coordinator = hass.data[DOMAIN][KEY_COORDINATOR]

            query = (call.data.get("query") or "").strip()
            stop_id = (call.data.get(CONF_STOP_ID) or "").strip()
            destination_id = (call.data.get(CONF_DESTINATION_ID) or "").strip()
            line = (call.data.get(CONF_LINE) or "").strip()
            n_trains = int(call.data.get(CONF_N_TRAINS, 5))

            state = {
                "query": query,
                "stop_id": None,
                "stop_name": None,
                "destination": destination_id or None,
                "line": line or None,
                "n_trains": n_trains,
                "trains": [],
                "last_error": None,
            }

            try:
                stop_result = None
                if stop_id:
                    stop_result = await hass.async_add_executor_job(
                        gtfs._get_stop_by_id_sync,
                        stop_id,
                    )
                    if not stop_result:
                        state["last_error"] = f"stop_id_not_found:{stop_id}"
                elif query:
                    stop_results = await gtfs.search_stops(query, limit=30)
                    if stop_results:
                        stop_result = stop_results[0]
                    else:
                        state["last_error"] = f"no_results:{query}"

                if stop_result:
                    state["stop_id"] = stop_result.get("stop_id")
                    state["stop_name"] = stop_result.get("name")
                    trip_updates = (coordinator.data or {}).get("trip_updates", {})
                    state["trains"] = await gtfs.get_next_trains(
                        state["stop_id"],
                        state["line"],
                        state["n_trains"],
                        trip_updates,
                        state["destination"],
                    )
            except Exception as err:
                state["last_error"] = f"explore_error:{err}"

            hass.data[DOMAIN][KEY_EXPLORER] = state
            async_dispatcher_send(hass, SIGNAL_EXPLORER_UPDATED)

        async_register_admin_service(
            hass,
            DOMAIN,
            SERVICE_EXPLORE,
            _async_handle_explore,
            schema=_EXPLORE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_EXPLORER):

        async def _async_handle_clear_explorer(call) -> None:
            """Limpia el estado del explorador temporal."""
            hass.data[DOMAIN][KEY_EXPLORER] = {
                "query": "",
                "stop_id": None,
                "stop_name": None,
                "line": None,
                "n_trains": 5,
                "trains": [],
                "last_error": None,
            }
            async_dispatcher_send(hass, SIGNAL_EXPLORER_UPDATED)

        async_register_admin_service(
            hass,
            DOMAIN,
            SERVICE_CLEAR_EXPLORER,
            _async_handle_clear_explorer,
            schema=vol.Schema({}),
        )

    if KEY_COORDINATOR not in hass.data[DOMAIN]:
        coordinator = RenfeRTCoordinator(hass)
        hass.data[DOMAIN][KEY_COORDINATOR] = coordinator
        await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarga una entrada de configuracion."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    remaining = [
        cfg for cfg in hass.config_entries.async_entries(DOMAIN)
        if cfg.entry_id != entry.entry_id
    ]
    if remaining:
        owner_entry = hass.data.get(DOMAIN, {}).get(KEY_EXPLORER_OWNER_ENTRY)
        if owner_entry == entry.entry_id:
            hass.data[DOMAIN][KEY_EXPLORER_ENTITY_CREATED] = False
            hass.data[DOMAIN][KEY_EXPLORER_OWNER_ENTRY] = remaining[0].entry_id
            await hass.config_entries.async_reload(remaining[0].entry_id)

    if not remaining:
        if hass.services.has_service(DOMAIN, SERVICE_REFRESH_GTFS):
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH_GTFS)
        if hass.services.has_service(DOMAIN, SERVICE_EXPLORE):
            hass.services.async_remove(DOMAIN, SERVICE_EXPLORE)
        if hass.services.has_service(DOMAIN, SERVICE_CLEAR_EXPLORER):
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_EXPLORER)
        hass.data.pop(DOMAIN, None)

    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recarga la entrada al guardar opciones."""
    await hass.config_entries.async_reload(entry.entry_id)
