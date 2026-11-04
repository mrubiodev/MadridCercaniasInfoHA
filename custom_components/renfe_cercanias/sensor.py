"""Entidades sensor para trayectos Renfe Cercanias."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pytz
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ACTIVE_FROM,
    CONF_ACTIVE_TO,
    CONF_DESTINATION_ID,
    CONF_JOURNEY_NAME,
    CONF_LINE,
    CONF_MANAGED_BY,
    CONF_N_TRAINS,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_N_TRAINS,
    DOMAIN,
    EXPLORER_MAX_POSITIONS_ATTR,
    KEY_COORDINATOR,
    KEY_EXPLORER,
    KEY_EXPLORER_ENTITY_CREATED,
    KEY_EXPLORER_OWNER_ENTRY,
    KEY_GTFS,
    MANAGED_BY_UI,
    MANAGED_BY_YAML,
    MADRID_LINES,
    SIGNAL_EXPLORER_UPDATED,
    TZ_MADRID,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea la entidad sensor para un trayecto configurado."""
    coordinator = hass.data[DOMAIN][KEY_COORDINATOR]
    gtfs = hass.data[DOMAIN][KEY_GTFS]
    entities: list[SensorEntity] = [RenfeJourneySensor(hass, coordinator, gtfs, entry)]

    hass.data[DOMAIN].setdefault(KEY_EXPLORER_ENTITY_CREATED, False)
    hass.data[DOMAIN].setdefault(KEY_EXPLORER_OWNER_ENTRY, entry.entry_id)
    hass.data[DOMAIN].setdefault(
        KEY_EXPLORER,
        {
            "query": "",
            "stop_id": None,
            "stop_name": None,
            "line": None,
            "destination": None,
            "n_trains": 5,
            "trains": [],
            "last_error": None,
        },
    )

    owner_entry = hass.data[DOMAIN][KEY_EXPLORER_OWNER_ENTRY]
    if entry.entry_id == owner_entry and not hass.data[DOMAIN][KEY_EXPLORER_ENTITY_CREATED]:
        entities.append(RenfeExplorerSensor(hass, coordinator, gtfs))
        hass.data[DOMAIN][KEY_EXPLORER_ENTITY_CREATED] = True

    async_add_entities(entities, True)


class RenfeJourneySensor(CoordinatorEntity[dict[str, Any]], SensorEntity):
    """Sensor de un trayecto configurado por el usuario."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        gtfs,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._gtfs = gtfs

        cfg = {**entry.data, **entry.options}

        self._journey_name = cfg.get(CONF_JOURNEY_NAME, "Cercanias")
        self._stop_id = cfg[CONF_STOP_ID]
        self._stop_name = cfg.get(CONF_STOP_NAME, self._stop_id)
        self._destination_id = cfg.get(CONF_DESTINATION_ID) or None
        self._destination_name = cfg.get(CONF_DESTINATION_NAME) or None
        self._line = cfg.get(CONF_LINE) or None
        self._n_trains = int(cfg.get(CONF_N_TRAINS, DEFAULT_N_TRAINS))
        self._active_from = cfg.get(CONF_ACTIVE_FROM, "") or None
        self._active_to = cfg.get(CONF_ACTIVE_TO, "") or None
        self._managed_by = cfg.get(
            CONF_MANAGED_BY,
            MANAGED_BY_YAML if entry.source == SOURCE_IMPORT else MANAGED_BY_UI,
        )

        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}"
        self._attr_name = self._journey_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=self._journey_name,
            manufacturer="Renfe",
            model=f"Cercanias {self._line or 'Madrid'}",
            entry_type="service",
        )

        self._trains: list[dict[str, Any]] = []
        self._last_update: datetime | None = None

    def _is_active_now(self) -> bool:
        """Comprueba si el trayecto esta activo en su ventana horaria."""
        if not self._active_from and not self._active_to:
            return True

        now_str = datetime.now(pytz.timezone(TZ_MADRID)).strftime("%H:%M")
        if self._active_from and now_str < self._active_from:
            return False
        if self._active_to and now_str > self._active_to:
            return False
        return True

    def _filter_positions(self) -> list[dict[str, Any]]:
        """Filtra posiciones RT de trenes por linea del trayecto o nucleo Madrid."""
        positions = (self.coordinator.data or {}).get("positions", [])
        if self._line:
            prefix = f"{self._line.upper()}-"
            return [
                train for train in positions
                if str(train.get("label", "")).upper().startswith(prefix)
            ]

        return [
            train for train in positions
            if any(
                str(train.get("label", "")).upper().startswith(f"{line}-")
                for line in MADRID_LINES
            )
        ]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Dispara recalculo de proximos trenes al llegar datos RT nuevos."""
        self.hass.async_create_task(self._async_refresh_trains())

    async def _async_refresh_trains(self) -> None:
        if not self._is_active_now():
            self._trains = []
            self._last_update = datetime.now(pytz.timezone(TZ_MADRID))
            self.async_write_ha_state()
            return

        trip_updates = (self.coordinator.data or {}).get("trip_updates", {})
        try:
            self._trains = await self._gtfs.get_next_trains(
                self._stop_id,
                self._line,
                self._n_trains,
                trip_updates,
                self._destination_id,
            )
        except Exception:
            _LOGGER.exception(
                "Error calculando proximos trenes para %s",
                self._journey_name,
            )
            self._trains = []

        self._last_update = (self.coordinator.data or {}).get(
            "fetched_at", datetime.now(pytz.timezone(TZ_MADRID))
        )
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Minutos al proximo tren o None si no hay datos."""
        if not self._trains:
            return None
        return self._trains[0].get("minutes")

    @property
    def icon(self) -> str:
        """Icono dinámico según estado y retraso."""
        if not self._is_active_now():
            return "mdi:clock-time-four-outline"
        if not self._trains:
            return "mdi:train-variant"
        first = self._trains[0]
        if (first.get("delay_min") or 0) > 3:
            return "mdi:train-alert"
        return "mdi:train"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Atributos de estado para plantillas y dashboards."""
        active = self._is_active_now()
        positions = self._filter_positions()

        attrs: dict[str, Any] = {
            "journey_name": self._journey_name,
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "destination_id": self._destination_id,
            "destination_name": self._destination_name,
            "line_filter": self._line or "todas",
            "managed_by": self._managed_by,
            "configuration_read_only": self._managed_by == MANAGED_BY_YAML,
            "active_window": (
                f"{self._active_from or '00:00'} - {self._active_to or '23:59'}"
                if (self._active_from or self._active_to)
                else "siempre"
            ),
            "is_active": active,
            "trains": self._trains,
            "trains_count": len(self._trains),
            "active_trains_on_line": len(positions),
            "updated_at": self._last_update.strftime("%H:%M:%S") if self._last_update else None,
        }

        if self._trains:
            first = self._trains[0]
            diff_min = first.get("minutes", 0.0)
            delay = first.get("delay_min", 0.0)
            attrs["next_departure"] = first.get("departure")
            attrs["next_line"] = first.get("line")
            attrs["next_headsign"] = first.get("headsign")
            attrs["next_delay_min"] = delay

            if delay > 0:
                attrs["next_delay_text"] = f"+{delay} min"
            elif delay < 0:
                attrs["next_delay_text"] = f"{delay} min"
            else:
                attrs["next_delay_text"] = "En hora"

            now_mad = datetime.now(pytz.timezone(TZ_MADRID))
            dep_dt = now_mad + timedelta(minutes=diff_min)
            attrs["next_departure_time"] = dep_dt.isoformat()

            attrs["next_train_summary"] = (
                f"{first.get('line', '')} a {first.get('headsign', '')} "
                f"en {round(diff_min)} min ({first.get('departure', '')}) · {attrs['next_delay_text']}"
            ).strip()

            if len(self._trains) > 1:
                second = self._trains[1]
                attrs["second_departure"] = second.get("departure")
                attrs["second_line"] = second.get("line")
                attrs["second_headsign"] = second.get("headsign")
                attrs["second_minutes"] = second.get("minutes")
                attrs["second_delay_min"] = second.get("delay_min", 0.0)

        return attrs

    @property
    def available(self) -> bool:
        """Disponibilidad del sensor basada en el coordinador RT."""
        return self.coordinator.last_update_success


class RenfeExplorerSensor(CoordinatorEntity[dict[str, Any]], SensorEntity):
    """Sensor global para modo explorador temporal."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:compass-outline"
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, coordinator, gtfs) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._gtfs = gtfs
        self._attr_unique_id = f"{DOMAIN}_explorer"
        self._attr_name = "Explorador"
        self._state_data: dict[str, Any] = hass.data[DOMAIN].get(KEY_EXPLORER, {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "explorer")},
            name="Renfe Cercanias Explorador",
            manufacturer="Renfe",
            model="Cercanias Explorer",
            entry_type="service",
        )

    async def async_added_to_hass(self) -> None:
        """Suscribe a cambios del servicio de exploracion."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_EXPLORER_UPDATED,
                self._handle_explorer_update,
            )
        )

    @callback
    def _handle_explorer_update(self) -> None:
        self._state_data = self.hass.data[DOMAIN].get(KEY_EXPLORER, {})
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresca trenes explorados con cada ciclo RT si hay parada seleccionada."""
        stop_id = (self._state_data or {}).get("stop_id")
        if stop_id:
            self.hass.async_create_task(self._async_refresh_trains())
        else:
            self.async_write_ha_state()

    async def _async_refresh_trains(self) -> None:
        state = self.hass.data[DOMAIN].get(KEY_EXPLORER, {})
        stop_id = state.get("stop_id")
        if not stop_id:
            self._state_data = state
            self.async_write_ha_state()
            return

        try:
            trip_updates = (self.coordinator.data or {}).get("trip_updates", {})
            trains = await self._gtfs.get_next_trains(
                stop_id,
                state.get("line") or None,
                int(state.get("n_trains", 5)),
                trip_updates,
                state.get("destination") or None,
            )
            state["trains"] = trains
            state["last_error"] = None
        except Exception:
            _LOGGER.exception("Error actualizando modo explorador")
            state["trains"] = []
            state["last_error"] = "refresh_error"

        self.hass.data[DOMAIN][KEY_EXPLORER] = state
        self._state_data = state
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        trains = (self._state_data or {}).get("trains") or []
        if not trains:
            return None
        return trains[0].get("minutes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self._state_data or {}
        positions_all = (self.coordinator.data or {}).get("positions", [])
        line = state.get("line")

        positions_filtered = positions_all
        if line:
            prefix = f"{str(line).upper()}-"
            positions_filtered = [
                pos for pos in positions_all
                if str(pos.get("label", "")).upper().startswith(prefix)
            ]

        # Evita atributos masivos en Recorder: guardamos una muestra compacta.
        positions_sample = positions_filtered[:EXPLORER_MAX_POSITIONS_ATTR]
        compact_positions = [
            {
                "trip_id": p.get("trip_id", ""),
                "route_id": p.get("route_id", ""),
                "label": p.get("label", ""),
                "lat": p.get("lat"),
                "lon": p.get("lon"),
                "speed_kmh": p.get("speed_kmh", 0),
                "status": p.get("status", ""),
                "stop_id": p.get("stop_id", ""),
            }
            for p in positions_sample
        ]

        return {
            "mode": "explorer",
            "query": state.get("query", ""),
            "stop_id": state.get("stop_id"),
            "stop_name": state.get("stop_name"),
            "line_filter": line or "todas",
            "n_trains": state.get("n_trains", 5),
            "trains": state.get("trains") or [],
            "last_error": state.get("last_error"),
            "positions": compact_positions,
            "positions_count": len(compact_positions),
            "positions_total_count": len(positions_filtered),
            "positions_truncated": len(positions_filtered) > len(compact_positions),
            "positions_all_count": len(positions_all),
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success
