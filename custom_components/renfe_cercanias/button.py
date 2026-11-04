"""Entidades boton para utilidades de Renfe Cercanias."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_JOURNEY_NAME, DOMAIN, KEY_COORDINATOR, KEY_GTFS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea el boton para refresco manual de GTFS."""
    coordinator = hass.data[DOMAIN][KEY_COORDINATOR]
    gtfs = hass.data[DOMAIN][KEY_GTFS]
    async_add_entities([RenfeRefreshGtfsButton(entry, coordinator, gtfs)], True)


class RenfeRefreshGtfsButton(ButtonEntity):
    """Boton para forzar descarga y reconstruccion de GTFS."""

    _attr_icon = "mdi:database-refresh"
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, gtfs) -> None:
        self._entry = entry
        self._coordinator = coordinator
        self._gtfs = gtfs
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_refresh_gtfs"
        self._attr_name = "Refrescar GTFS"

        journey_name = entry.title or entry.data.get(CONF_JOURNEY_NAME, "Renfe Cercanias")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=journey_name,
            manufacturer="Renfe",
            model="Cercanias Madrid",
            entry_type="service",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose estado de cache GTFS junto al boton."""
        status = self._gtfs.get_cache_status()
        return {
            "gtfs_downloaded": status.get("downloaded"),
            "gtfs_usable": status.get("usable"),
            "gtfs_stops_count": status.get("stops_count"),
            "gtfs_db_size_bytes": status.get("db_size_bytes"),
            "gtfs_last_download": status.get("last_download"),
            "gtfs_age_seconds": status.get("age_seconds"),
        }

    async def async_press(self) -> None:
        """Ejecuta refresco GTFS manual y actualiza RT."""
        await self._gtfs.force_refresh()
        await self._coordinator.async_request_refresh()
        self.async_write_ha_state()
