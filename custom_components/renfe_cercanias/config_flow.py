"""Config flow de Renfe Cercanias con soporte multi trayecto."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACTIVE_FROM,
    CONF_ACTIVE_TO,
    CONF_DESTINATION_ID,
    CONF_DESTINATION_NAME,
    CONF_JOURNEY_NAME,
    CONF_LINE,
    CONF_MANAGED_BY,
    CONF_N_TRAINS,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_N_TRAINS,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_GTFS,
    LINE_OPTIONS,
    MANAGED_BY_UI,
    MANAGED_BY_YAML,
)

_LOGGER = logging.getLogger(__name__)


def _looks_like_stop_id(query: str) -> bool:
    """Heuristica para permitir entrada manual de stop_id."""
    value = (query or "").strip()
    return len(value) >= 3 and " " not in value and any(ch.isdigit() for ch in value)


def _format_trains_preview(trains: list[dict[str, Any]]) -> str:
    """Convierte una lista de trenes en texto breve para placeholders."""
    if not trains:
        return "Sin salidas proximas para esta combinacion ahora mismo."

    lines = []
    for train in trains[:8]:
        delay = train.get("delay_min", 0)
        delay_txt = f" (+{delay}m)" if delay and delay > 0 else ""
        lines.append(
            f"{train.get('departure', '--:--')} · {train.get('line', '-')} · {train.get('headsign', '-')}{delay_txt}"
        )
    return "\\n".join(lines)


def _build_unique_id(data: dict[str, Any]) -> str:
    """Construye un identificador estable para el trayecto (origen+destino+linea)."""
    origin = data.get(CONF_STOP_ID, '')
    destination = data.get(CONF_DESTINATION_ID, '')
    line = data.get(CONF_LINE, '')
    # Include destination to ensure unique IDs when same origin has multiple destinations
    return f"{origin}_{destination}_{line}_{data.get(CONF_JOURNEY_NAME, '')}"


def _normalize_journey(data: dict[str, Any], *, managed_by: str) -> dict[str, Any]:
    """Normaliza un trayecto desde UI o YAML."""
    normalized = dict(data)
    normalized[CONF_ACTIVE_FROM] = _validate_time(normalized.get(CONF_ACTIVE_FROM, ""))
    normalized[CONF_ACTIVE_TO] = _validate_time(normalized.get(CONF_ACTIVE_TO, ""))
    normalized[CONF_STOP_NAME] = normalized.get(CONF_STOP_NAME, normalized.get(CONF_STOP_ID, ""))
    normalized[CONF_DESTINATION_NAME] = normalized.get(CONF_DESTINATION_NAME, normalized.get(CONF_DESTINATION_ID, ""))
    normalized[CONF_LINE] = (normalized.get(CONF_LINE, "") or "").strip()
    normalized[CONF_MANAGED_BY] = managed_by
    return normalized


def _get_gtfs(hass):
    """Obtiene o crea el singleton de RenfeGtfsManager."""
    from .coordinator import RenfeGtfsManager

    hass.data.setdefault(DOMAIN, {})
    if KEY_GTFS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][KEY_GTFS] = RenfeGtfsManager(hass)
    return hass.data[DOMAIN][KEY_GTFS]


def _journey_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema del paso principal de configuracion."""
    return vol.Schema(
        {
            vol.Required(
                CONF_JOURNEY_NAME,
                default=defaults.get(CONF_JOURNEY_NAME, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Optional(
                CONF_LINE,
                default=defaults.get(CONF_LINE, ""),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=opt["value"], label=opt["label"])
                        for opt in LINE_OPTIONS
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_N_TRAINS,
                default=defaults.get(CONF_N_TRAINS, DEFAULT_N_TRAINS),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_ACTIVE_FROM,
                default=defaults.get(CONF_ACTIVE_FROM, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Optional(
                CONF_ACTIVE_TO,
                default=defaults.get(CONF_ACTIVE_TO, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        }
    )


def _validate_time(value: str) -> str:
    """Valida HH:MM o devuelve vacio si no se define."""
    value = value.strip()
    if not value:
        return ""

    try:
        hours, minutes = value.split(":")
        if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
            raise ValueError
        return f"{int(hours):02d}:{int(minutes):02d}"
    except Exception as err:
        raise vol.Invalid("invalid_time") from err


class RenfeCercaniasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuracion para nuevo trayecto."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._stop_results: list[dict[str, Any]] = []
        self._preview_trains: list[dict[str, Any]] = []
        self._destinations: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Paso 1: parametros del trayecto."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user_input = _normalize_journey(user_input, managed_by=MANAGED_BY_UI)
            except vol.Invalid as err:
                errors["base"] = str(err)
            else:
                self._data.update(user_input)
                return await self.async_step_stop_search()

        return self.async_show_form(
            step_id="user",
            data_schema=_journey_schema(self._data),
            errors=errors,
        )

    async def async_step_stop_search(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Paso 2: buscar parada por nombre o ID."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input.get("stop_query", "").strip()
            if query and len(query) < 2:
                errors["stop_query"] = "query_too_short"
            else:
                try:
                    gtfs = _get_gtfs(self.hass)
                    # Si la busqueda va vacia, mostramos el catalogo completo.
                    self._stop_results = await gtfs.search_stops(
                        query,
                        limit=None if not query else 120,
                    )
                except Exception:
                    _LOGGER.exception("Error buscando paradas GTFS")
                    # Si hay excepción pero parece un ID, intenta validación directa
                    if _looks_like_stop_id(query):
                        try:
                            stop_result = await self.hass.async_add_executor_job(
                                gtfs._get_stop_by_id_sync, query
                            )
                            if stop_result:
                                self._stop_results = [stop_result]
                                return await self.async_step_stop_select()
                            else:
                                errors["stop_query"] = "stop_id_not_found"
                        except Exception:
                            errors["base"] = "gtfs_error"
                    else:
                        errors["base"] = "gtfs_error"
                else:
                    if not self._stop_results:
                        # No hay resultados, pero si parece un ID, validamos contra GTFS
                        if _looks_like_stop_id(query):
                            # Intenta buscar exactamente por ID en GTFS
                            stop_result = None
                            try:
                                stop_result = await self.hass.async_add_executor_job(
                                    gtfs._get_stop_by_id_sync, query
                                )
                            except Exception:
                                pass
                            
                            if stop_result:
                                # ID válido encontrado en GTFS
                                self._stop_results = [stop_result]
                                return await self.async_step_stop_select()
                            else:
                                # ID no encontrado en GTFS
                                errors["stop_query"] = "stop_id_not_found"
                        else:
                            # No es un ID y tampoco hay resultados por nombre
                            errors["stop_query"] = "no_results"
                    else:
                        return await self.async_step_stop_select()

        return self.async_show_form(
            step_id="stop_search",
            data_schema=vol.Schema(
                {
                    vol.Required("stop_query"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    )
                }
            ),
            errors=errors,
            description_placeholders={
                "all_hint": "Deja vacio para mostrar todas las estaciones",
            },
        )

    async def async_step_stop_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Paso 3: seleccionar parada encontrada."""
        if user_input is not None:
            selected_id = user_input[CONF_STOP_ID]
            if selected_id == "__search_again__":
                return await self.async_step_stop_search()

            selected_name = next(
                (
                    result["name"]
                    for result in self._stop_results
                    if result["stop_id"] == selected_id
                ),
                selected_id,
            )
            self._data[CONF_STOP_ID] = selected_id
            self._data[CONF_STOP_NAME] = selected_name

            return await self.async_step_destination_select()

        stop_options = [
            SelectOptionDict(
                value=result["stop_id"],
                label=f"{result['name']} ({result['stop_id']})",
            )
            for result in self._stop_results
        ]
        stop_options.append(
            SelectOptionDict(value="__search_again__", label="Buscar de nuevo")
        )

        return self.async_show_form(
            step_id="stop_select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=stop_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={"results_count": str(len(self._stop_results))},
        )

    async def async_step_destination_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Paso 3b: Seleccionar destino final (IMPORTANTE para filtrar dirección).
        
        Una estación puede tener múltiples destinos en diferentes líneas/direcciones.
        Por eso es necesario seleccionar explícitamente hacia dónde va el tren.
        """
        if user_input is not None:
            dest_id = user_input.get(CONF_DESTINATION_ID)
            if dest_id and dest_id != "__no_filter__":
                self._data[CONF_DESTINATION_ID] = dest_id
                # Find destination name from the preview
                destination_names = {d["stop_id"]: d["name"] for d in self._destinations}
                dest_name = destination_names.get(dest_id, dest_id)
                self._data[CONF_DESTINATION_NAME] = dest_name
            else:
                # Clear destination if "no filter" is selected
                self._data[CONF_DESTINATION_ID] = ""
                self._data[CONF_DESTINATION_NAME] = ""
            
            return await self.async_step_preview()

        # Get available destinations for the selected stop
        destinations: list[dict[str, str]] = []
        try:
            gtfs = _get_gtfs(self.hass)
            destinations = await self.hass.async_add_executor_job(
                gtfs.get_destinations_for_stop,
                self._data.get(CONF_STOP_ID, ""),
            )
        except Exception:
            _LOGGER.exception("Error obteniendo destinos para la estación")

        self._destinations = destinations
        dest_options = [
            SelectOptionDict(value="__no_filter__", label="Cualquier destino (sin filtro)")
        ]
        dest_options.extend(
            [SelectOptionDict(value=dest["stop_id"], label=dest["name"]) for dest in self._destinations]
        )

        return self.async_show_form(
            step_id="destination_select",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DESTINATION_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=dest_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={
                "stop_name": self._data.get(CONF_STOP_NAME, self._data.get(CONF_STOP_ID)),
                "destinations_count": str(len(self._destinations)),
            },
        )

    async def async_step_preview(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Paso 4: previsualizar datos antes de crear el sensor."""
        if user_input is not None:
            if user_input.get("change_stop"):
                return await self.async_step_stop_search()
            if not user_input.get("confirm_create"):
                return self.async_abort(reason="preview_cancelled")
            title = self._data.get(CONF_JOURNEY_NAME) or self._data.get(CONF_STOP_NAME)
            await self.async_set_unique_id(_build_unique_id(self._data))
            self._abort_if_unique_id_configured(updates=self._data)
            return self.async_create_entry(title=title, data=self._data)

        errors: dict[str, str] = {}
        self._preview_trains = []
        try:
            gtfs = _get_gtfs(self.hass)
            coordinator = self.hass.data.get(DOMAIN, {}).get(KEY_COORDINATOR)
            trip_updates = (coordinator.data or {}).get("trip_updates", {}) if coordinator else {}
            n_preview = max(int(self._data.get(CONF_N_TRAINS, DEFAULT_N_TRAINS)), 5)
            self._preview_trains = await gtfs.get_next_trains(
                self._data.get(CONF_STOP_ID, ""),
                self._data.get(CONF_LINE) or None,
                n_preview,
                trip_updates,
                self._data.get(CONF_DESTINATION_ID) or None,
            )
        except Exception:
            _LOGGER.exception("Error generando previsualizacion del trayecto")
            errors["base"] = "preview_error"

        return self.async_show_form(
            step_id="preview",
            data_schema=vol.Schema(
                {
                    vol.Optional("change_stop", default=False): BooleanSelector(),
                    vol.Required("confirm_create", default=True): BooleanSelector(),
                }
            ),
            errors=errors,
            description_placeholders={
                "preview_stop": self._data.get(CONF_STOP_NAME, self._data.get(CONF_STOP_ID, "-")),
                "preview_stop_id": self._data.get(CONF_STOP_ID, "-"),
                "preview_line": self._data.get(CONF_LINE) or "todas",
                "preview_n": str(self._data.get(CONF_N_TRAINS, DEFAULT_N_TRAINS)),
                "preview_window": (
                    f"{self._data.get(CONF_ACTIVE_FROM) or '00:00'} - {self._data.get(CONF_ACTIVE_TO) or '23:59'}"
                    if (self._data.get(CONF_ACTIVE_FROM) or self._data.get(CONF_ACTIVE_TO))
                    else "siempre"
                ),
                "preview_trains": _format_trains_preview(self._preview_trains),
            },
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> config_entries.FlowResult:
        """Importa o actualiza un trayecto definido en configuration.yaml."""
        normalized = _normalize_journey(import_config, managed_by=MANAGED_BY_YAML)
        title = normalized.get(CONF_JOURNEY_NAME) or normalized.get(CONF_STOP_NAME)

        await self.async_set_unique_id(_build_unique_id(normalized))
        self._abort_if_unique_id_configured(updates=normalized)
        return self.async_create_entry(title=title, data=normalized)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> RenfeCercaniasOptionsFlow:
        """Devuelve el flujo de opciones para editar trayectos."""
        return RenfeCercaniasOptionsFlow(config_entry)


class RenfeCercaniasOptionsFlow(config_entries.OptionsFlow):
    """Permite editar parametros de un trayecto existente."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._data: dict[str, Any] = {**config_entry.data, **config_entry.options}
        self._stop_results: list[dict[str, Any]] = []
        self._destinations: list[dict[str, str]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Paso inicial de opciones."""
        if self._entry.source == SOURCE_IMPORT:
            return self.async_abort(reason="yaml_managed")

        errors: dict[str, str] = {}

        if user_input is not None:
            change_stop = bool(user_input.pop("change_stop", False))
            change_destination = bool(user_input.pop("change_destination", False))
            try:
                user_input = _normalize_journey(user_input, managed_by=MANAGED_BY_UI)
            except vol.Invalid as err:
                errors["base"] = str(err)
            else:
                self._data.update(user_input)
                if change_stop:
                    return await self.async_step_stop_search()
                if change_destination:
                    return await self.async_step_destination_select()
                return self.async_create_entry(title="", data=self._data)

        current_stop = self._data.get(CONF_STOP_NAME, self._data.get(CONF_STOP_ID, "-"))
        current_dest = self._data.get(CONF_DESTINATION_NAME) or self._data.get(CONF_DESTINATION_ID) or "Cualquiera (sin filtro)"
        schema = _journey_schema(self._data).extend(
            {
                vol.Optional("change_stop", default=False): BooleanSelector(),
                vol.Optional("change_destination", default=False): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "current_stop": current_stop,
                "current_dest": current_dest,
            },
        )

    async def async_step_stop_search(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Buscar nueva parada para opciones."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input.get("stop_query", "").strip()
            if query and len(query) < 2:
                errors["stop_query"] = "query_too_short"
            else:
                try:
                    gtfs = _get_gtfs(self.hass)
                    self._stop_results = await gtfs.search_stops(
                        query,
                        limit=None if not query else 120,
                    )
                except Exception:
                    _LOGGER.exception("Error buscando paradas en options flow")
                    # Si hay excepción pero parece un ID, intenta validación directa
                    if _looks_like_stop_id(query):
                        try:
                            stop_result = await self.hass.async_add_executor_job(
                                gtfs._get_stop_by_id_sync, query
                            )
                            if stop_result:
                                self._stop_results = [stop_result]
                                return await self.async_step_stop_select()
                            else:
                                errors["stop_query"] = "stop_id_not_found"
                        except Exception:
                            errors["base"] = "gtfs_error"
                    else:
                        errors["base"] = "gtfs_error"
                else:
                    if not self._stop_results:
                        # No hay resultados, pero si parece un ID, validamos contra GTFS
                        if _looks_like_stop_id(query):
                            # Intenta buscar exactamente por ID en GTFS
                            stop_result = None
                            try:
                                stop_result = await self.hass.async_add_executor_job(
                                    gtfs._get_stop_by_id_sync, query
                                )
                            except Exception:
                                pass
                            
                            if stop_result:
                                # ID válido encontrado en GTFS
                                self._stop_results = [stop_result]
                                return await self.async_step_stop_select()
                            else:
                                # ID no encontrado en GTFS
                                errors["stop_query"] = "stop_id_not_found"
                        else:
                            # No es un ID y tampoco hay resultados por nombre
                            errors["stop_query"] = "no_results"
                    else:
                        return await self.async_step_stop_select()

        return self.async_show_form(
            step_id="stop_search",
            data_schema=vol.Schema(
                {
                    vol.Required("stop_query"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    )
                }
            ),
            errors=errors,
            description_placeholders={
                "all_hint": "Deja vacio para mostrar todas las estaciones",
            },
        )

    async def async_step_stop_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Seleccion de nueva parada en options flow."""
        if user_input is not None:
            selected_id = user_input[CONF_STOP_ID]
            if selected_id == "__search_again__":
                return await self.async_step_stop_search()

            selected_name = next(
                (
                    result["name"]
                    for result in self._stop_results
                    if result["stop_id"] == selected_id
                ),
                selected_id,
            )
            self._data[CONF_STOP_ID] = selected_id
            self._data[CONF_STOP_NAME] = selected_name
            return await self.async_step_destination_select()

        stop_options = [
            SelectOptionDict(
                value=result["stop_id"],
                label=f"{result['name']} ({result['stop_id']})",
            )
            for result in self._stop_results
        ]
        stop_options.append(
            SelectOptionDict(value="__search_again__", label="Buscar de nuevo")
        )

        return self.async_show_form(
            step_id="stop_select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=stop_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_destination_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Paso para seleccionar o cambiar destino en OptionsFlow."""
        if user_input is not None:
            dest_id = user_input.get(CONF_DESTINATION_ID)
            if dest_id and dest_id != "__no_filter__":
                self._data[CONF_DESTINATION_ID] = dest_id
                destination_names = {d["stop_id"]: d["name"] for d in self._destinations}
                dest_name = destination_names.get(dest_id, dest_id)
                self._data[CONF_DESTINATION_NAME] = dest_name
            else:
                self._data[CONF_DESTINATION_ID] = ""
                self._data[CONF_DESTINATION_NAME] = ""

            return self.async_create_entry(title="", data=self._data)

        destinations: list[dict[str, str]] = []
        try:
            gtfs = _get_gtfs(self.hass)
            destinations = await self.hass.async_add_executor_job(
                gtfs.get_destinations_for_stop,
                self._data.get(CONF_STOP_ID, ""),
            )
        except Exception:
            _LOGGER.exception("Error obteniendo destinos en options flow")

        self._destinations = destinations
        dest_options = [
            SelectOptionDict(value="__no_filter__", label="Cualquier destino (sin filtro)")
        ]
        dest_options.extend(
            [SelectOptionDict(value=dest["stop_id"], label=dest["name"]) for dest in self._destinations]
        )

        current_dest_id = self._data.get(CONF_DESTINATION_ID) or "__no_filter__"
        if not any(opt.value == current_dest_id for opt in dest_options):
            current_dest_id = "__no_filter__"

        return self.async_show_form(
            step_id="destination_select",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DESTINATION_ID,
                        default=current_dest_id,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=dest_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={
                "stop_name": self._data.get(CONF_STOP_NAME, self._data.get(CONF_STOP_ID)),
                "destinations_count": str(len(self._destinations)),
            },
        )
