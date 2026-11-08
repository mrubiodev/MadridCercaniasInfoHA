"""Plataforma de entidades select para Renfe Cercanias."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DESTINATION_ID,
    CONF_DESTINATION_NAME,
    CONF_JOURNEY_NAME,
    CONF_LINE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_GTFS,
    MADRID_LINES,
    MADRID_POPULAR_STATIONS,
)

_LOGGER = logging.getLogger(__name__)

ANY_LINE_LABEL = "Cualquier línea"
ANY_DESTINATION_LABEL = "Cualquier destino (sin filtro)"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura las entidades select interactivas para el trayecto."""
    coordinator = hass.data[DOMAIN][KEY_COORDINATOR]
    gtfs = hass.data[DOMAIN][KEY_GTFS]

    entities: list[SelectEntity] = [
        RenfeStationSelect(hass, entry, coordinator, gtfs),
        RenfeLineSelect(hass, entry, coordinator, gtfs),
        RenfeDestinationSelect(hass, entry, coordinator, gtfs),
    ]
    async_add_entities(entities, True)


class _RenfeBaseSelect(SelectEntity):
    """Clase base para entidades select de Renfe Cercanias."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, gtfs) -> None:
        self.hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._gtfs = gtfs

        journey_name = entry.title or entry.data.get(CONF_JOURNEY_NAME, "Renfe Cercanias")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=journey_name,
            manufacturer="Renfe",
            model="Cercanias Madrid",
            entry_type="service",
        )

    @property
    def current_config(self) -> dict[str, Any]:
        """Obtiene la configuracion combinando data y options."""
        return {**self._entry.data, **self._entry.options}


class RenfeStationSelect(_RenfeBaseSelect):
    """Selector interactivo de estacion de origen."""

    _attr_icon = "mdi:train-car"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, gtfs) -> None:
        super().__init__(hass, entry, coordinator, gtfs)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_station_select"
        self._attr_name = "Estación de origen"
        self._label_to_id: dict[str, str] = {}
        self._id_to_label: dict[str, str] = {}
        self._attr_options: list[str] = []

    async def async_added_to_hass(self) -> None:
        """Carga el catalogo de estaciones al agregarse a HA."""
        await super().async_added_to_hass()
        await self._async_load_stations()

    async def _async_load_stations(self) -> None:
        """Carga estaciones desde GTFS o fallback."""
        try:
            stops = await self._gtfs.search_stops("", limit=None)
        except Exception:
            stops = []

        if not stops:
            stops = list(MADRID_POPULAR_STATIONS)

        self._label_to_id.clear()
        self._id_to_label.clear()
        labels = []

        for s in stops:
            sid = str(s.get("stop_id", "")).strip()
            name = str(s.get("name", sid)).strip()
            if not sid:
                continue
            label = f"{name} ({sid})"
            self._label_to_id[label] = sid
            self._id_to_label[sid] = label
            labels.append(label)

        labels.sort()
        self._attr_options = labels

    @property
    def current_option(self) -> str | None:
        """Devuelve la estacion actualmente seleccionada."""
        stop_id = str(self.current_config.get(CONF_STOP_ID, "")).strip()
        if stop_id in self._id_to_label:
            return self._id_to_label[stop_id]
        stop_name = self.current_config.get(CONF_STOP_NAME) or stop_id
        if stop_id:
            label = f"{stop_name} ({stop_id})"
            self._label_to_id[label] = stop_id
            self._id_to_label[stop_id] = label
            if label not in self._attr_options:
                self._attr_options.append(label)
                self._attr_options.sort()
            return label
        return self._attr_options[0] if self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Cambia la estacion de origen del trayecto."""
        stop_id = self._label_to_id.get(option)
        if not stop_id:
            _LOGGER.warning("Estacion desconocida seleccionada: %s", option)
            return

        stop_name = option.split(" (")[0] if " (" in option else option

        new_options = dict(self.current_config)
        new_options[CONF_STOP_ID] = stop_id
        new_options[CONF_STOP_NAME] = stop_name
        # Limpiar destino al cambiar de origen para evitar incoherencias
        new_options[CONF_DESTINATION_ID] = ""
        new_options[CONF_DESTINATION_NAME] = ""

        self.hass.config_entries.async_update_entry(self._entry, options=new_options)


class RenfeLineSelect(_RenfeBaseSelect):
    """Selector interactivo de linea de Cercanias."""

    _attr_icon = "mdi:subway-variant"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, gtfs) -> None:
        super().__init__(hass, entry, coordinator, gtfs)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_line_select"
        self._attr_name = "Línea"
        self._attr_options = [ANY_LINE_LABEL] + list(MADRID_LINES)

    @property
    def current_option(self) -> str | None:
        """Devuelve la linea activa del trayecto."""
        line = (self.current_config.get(CONF_LINE, "") or "").strip().upper()
        if line and line in MADRID_LINES:
            return line
        return ANY_LINE_LABEL

    async def async_select_option(self, option: str) -> None:
        """Cambia el filtro de linea del trayecto."""
        new_line = "" if option == ANY_LINE_LABEL else option.strip()
        new_options = dict(self.current_config)
        new_options[CONF_LINE] = new_line

        self.hass.config_entries.async_update_entry(self._entry, options=new_options)


class RenfeDestinationSelect(_RenfeBaseSelect):
    """Selector interactivo de estacion de destino (direccion)."""

    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, gtfs) -> None:
        super().__init__(hass, entry, coordinator, gtfs)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_destination_select"
        self._attr_name = "Destino (dirección)"
        self._dest_to_id: dict[str, str] = {ANY_DESTINATION_LABEL: ""}
        self._id_to_dest: dict[str, str] = {"": ANY_DESTINATION_LABEL}
        self._attr_options = [ANY_DESTINATION_LABEL]

    async def async_added_to_hass(self) -> None:
        """Carga destinos disponibles para la estacion actual."""
        await super().async_added_to_hass()
        await self._async_load_destinations()

    async def _async_load_destinations(self) -> None:
        """Carga destinos disponibles para la parada configurada."""
        stop_id = str(self.current_config.get(CONF_STOP_ID, "")).strip()
        if not stop_id:
            self._attr_options = [ANY_DESTINATION_LABEL]
            return

        try:
            destinations = await self.hass.async_add_executor_job(
                self._gtfs.get_destinations_for_stop, stop_id
            )
        except Exception:
            destinations = []

        self._dest_to_id = {ANY_DESTINATION_LABEL: ""}
        self._id_to_dest = {"": ANY_DESTINATION_LABEL}
        options = [ANY_DESTINATION_LABEL]

        for d in destinations:
            did = str(d.get("stop_id", "")).strip()
            dname = str(d.get("name", did)).strip()
            if did and dname:
                label = f"{dname} ({did})"
                self._dest_to_id[label] = did
                self._id_to_dest[did] = label
                options.append(label)

        self._attr_options = options

    @property
    def current_option(self) -> str | None:
        """Devuelve el destino actualmente seleccionado."""
        dest_id = str(self.current_config.get(CONF_DESTINATION_ID, "")).strip()
        if not dest_id:
            return ANY_DESTINATION_LABEL
        if dest_id in self._id_to_dest:
            return self._id_to_dest[dest_id]
        dest_name = self.current_config.get(CONF_DESTINATION_NAME) or dest_id
        label = f"{dest_name} ({dest_id})"
        self._dest_to_id[label] = dest_id
        self._id_to_dest[dest_id] = label
        if label not in self._attr_options:
            self._attr_options.append(label)
        return label

    async def async_select_option(self, option: str) -> None:
        """Cambia el filtro de destino del trayecto."""
        dest_id = self._dest_to_id.get(option, "")
        dest_name = option.split(" (")[0] if (" (" in option and option != ANY_DESTINATION_LABEL) else ""

        new_options = dict(self.current_config)
        new_options[CONF_DESTINATION_ID] = dest_id
        new_options[CONF_DESTINATION_NAME] = dest_name

        self.hass.config_entries.async_update_entry(self._entry, options=new_options)

