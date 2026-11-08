"""Gestor GTFS y coordinador RT para Renfe Cercanias."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import sqlite3
import unicodedata
import zipfile
from datetime import date, datetime, timedelta
from typing import Any

import pytz
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    GTFS_BATCH_SIZE,
    GTFS_MAX_AGE_SECS,
    GTFS_STATIC_URL,
    MADRID_POPULAR_STATIONS,
    RT_POSITIONS_URL,
    RT_UPDATES_URL,
    SCAN_INTERVAL_SECS,
    TZ_MADRID,
)

_LOGGER = logging.getLogger(__name__)

# Cache timezone at module level to avoid blocking I/O in async functions
_TZ_MADRID = pytz.timezone(TZ_MADRID)


def _normalize_text(value: str) -> str:
    """Normaliza texto para busquedas tolerantes a mayusculas y acentos."""
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


class RenfeGtfsManager:
    """Gestiona descarga y cache del GTFS estatico en SQLite."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._db_path = hass.config.path("renfe_cercanias", "gtfs.db")
        self._lock = asyncio.Lock()

    def _needs_refresh(self) -> bool:
        if not os.path.exists(self._db_path):
            return True
        age = datetime.now().timestamp() - os.path.getmtime(self._db_path)
        return age > GTFS_MAX_AGE_SECS

    def _is_db_usable(self) -> bool:
        """Valida que la cache SQLite tenga datos minimos de paradas."""
        if not os.path.exists(self._db_path):
            return False
        try:
            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(1) FROM stops")
            count = int(c.fetchone()[0])
            conn.close()
            return count > 0
        except Exception:
            return False

    def get_cache_status(self) -> dict[str, Any]:
        """Devuelve estado de la cache GTFS local para diagnostico."""
        exists = os.path.exists(self._db_path)
        status: dict[str, Any] = {
            "db_path": self._db_path,
            "downloaded": exists,
            "usable": False,
            "stops_count": 0,
            "db_size_bytes": 0,
            "last_download": None,
            "age_seconds": None,
        }

        if not exists:
            return status

        try:
            mtime = os.path.getmtime(self._db_path)
            status["last_download"] = datetime.fromtimestamp(mtime).isoformat()
            status["age_seconds"] = int(datetime.now().timestamp() - mtime)
            status["db_size_bytes"] = os.path.getsize(self._db_path)

            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(1) FROM stops")
            status["stops_count"] = int(c.fetchone()[0])
            conn.close()

            status["usable"] = status["stops_count"] > 0
        except Exception:
            _LOGGER.exception("Error leyendo estado de cache GTFS")

        return status

    async def force_refresh(self) -> None:
        """Fuerza refresco del GTFS estatico, ignorando edad de cache."""
        async with self._lock:
            _LOGGER.info("Forzando refresco manual de GTFS estatico...")
            zip_bytes = await self.hass.async_add_executor_job(self._download_sync)
            await self.hass.async_add_executor_job(self._build_db_sync, zip_bytes)
            _LOGGER.info("Refresco manual GTFS completado: %s", self._db_path)

    async def ensure_gtfs(self) -> None:
        """Descarga y reconstruye la BD si esta caducada."""
        async with self._lock:
            if not self._needs_refresh() and self._is_db_usable():
                return
            _LOGGER.info("Descargando GTFS estatico de Renfe...")
            zip_bytes = await self.hass.async_add_executor_job(self._download_sync)
            await self.hass.async_add_executor_job(self._build_db_sync, zip_bytes)
            _LOGGER.info("GTFS cargado en SQLite: %s", self._db_path)

    def _download_sync(self) -> bytes:
        import warnings
        import requests

        try:
            resp = requests.get(GTFS_STATIC_URL, timeout=90)
            resp.raise_for_status()
            return resp.content
        except requests.exceptions.SSLError:
            _LOGGER.warning("Certificado SSL de Renfe genero error de verificacion, reintentando sin verificar...")
            warnings.filterwarnings("ignore", message="Unverified HTTPS request")
            resp = requests.get(GTFS_STATIC_URL, timeout=90, verify=False)
            resp.raise_for_status()
            return resp.content

    def _build_db_sync(self, zip_bytes: bytes) -> None:
        """Construye la BD SQLite a partir del zip GTFS."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        tmp_path = self._db_path + ".tmp"
        # Eliminar tmp anterior si quedó bloqueado (Windows)
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        conn = sqlite3.connect(tmp_path)
        try:
            c = conn.cursor()
            c.execute("PRAGMA journal_mode=DELETE")

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                names = zf.namelist()

                c.execute("DROP TABLE IF EXISTS stops")
                c.execute(
                    """CREATE TABLE stops (
                    stop_id TEXT PRIMARY KEY,
                    stop_name TEXT,
                    stop_lat REAL,
                    stop_lon REAL
                )"""
                )
                with zf.open("stops.txt") as f:
                    reader = csv.DictReader(line.decode("utf-8-sig") for line in f)
                    c.executemany(
                        "INSERT OR IGNORE INTO stops VALUES (?,?,?,?)",
                        [
                            (
                                row["stop_id"].strip(),
                                row["stop_name"].strip(),
                                float(row.get("stop_lat") or 0),
                                float(row.get("stop_lon") or 0),
                            )
                            for row in reader
                        ],
                    )

                c.execute("DROP TABLE IF EXISTS routes")
                c.execute(
                    """CREATE TABLE routes (
                    route_id TEXT PRIMARY KEY,
                    route_short_name TEXT
                )"""
                )
                with zf.open("routes.txt") as f:
                    reader = csv.DictReader(line.decode("utf-8-sig") for line in f)
                    c.executemany(
                        "INSERT OR IGNORE INTO routes VALUES (?,?)",
                        [
                            (
                                row["route_id"].strip(),
                                row.get("route_short_name", "").strip(),
                            )
                            for row in reader
                        ],
                    )

                c.execute("DROP TABLE IF EXISTS trips")
                c.execute(
                    """CREATE TABLE trips (
                    trip_id TEXT PRIMARY KEY,
                    route_id TEXT,
                    service_id TEXT,
                    trip_headsign TEXT
                )"""
                )
                with zf.open("trips.txt") as f:
                    reader = csv.DictReader(line.decode("utf-8-sig") for line in f)
                    c.executemany(
                        "INSERT OR IGNORE INTO trips VALUES (?,?,?,?)",
                        [
                            (
                                row["trip_id"].strip(),
                                row["route_id"].strip(),
                                row["service_id"].strip(),
                                row.get("trip_headsign", "").strip(),
                            )
                            for row in reader
                        ],
                    )

                c.execute("DROP TABLE IF EXISTS stop_times")
                c.execute(
                    """CREATE TABLE stop_times (
                    trip_id TEXT,
                    departure_time TEXT,
                    stop_id TEXT,
                    stop_sequence INTEGER
                )"""
                )
                with zf.open("stop_times.txt") as f:
                    reader = csv.DictReader(line.decode("utf-8-sig") for line in f)
                    # Log headers to debug field names
                    _LOGGER.debug("stop_times.txt fields: %s", reader.fieldnames)
                    batch: list[tuple[str, str, str, int]] = []
                    for row in reader:
                        dep = (row.get("departure_time") or row.get("arrival_time") or "").strip()
                        seq_raw = row.get("stop_sequence") or row.get("stop_seq") or "0"
                        batch.append(
                            (
                                row["trip_id"].strip(),
                                dep,
                                row["stop_id"].strip(),
                                int(seq_raw) if seq_raw.strip().isdigit() else 0,
                            )
                        )
                        if len(batch) >= GTFS_BATCH_SIZE:
                            c.executemany("INSERT INTO stop_times VALUES (?,?,?,?)", batch)
                            batch.clear()
                    if batch:
                        c.executemany("INSERT INTO stop_times VALUES (?,?,?,?)", batch)
                c.execute("CREATE INDEX IF NOT EXISTS idx_st_stop ON stop_times(stop_id)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_st_trip ON stop_times(trip_id)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_st_trip_stop_seq ON stop_times(trip_id, stop_id, stop_sequence)")

                c.execute("DROP TABLE IF EXISTS calendar")
                c.execute(
                    """CREATE TABLE calendar (
                    service_id TEXT PRIMARY KEY,
                    monday INT,
                    tuesday INT,
                    wednesday INT,
                    thursday INT,
                    friday INT,
                    saturday INT,
                    sunday INT,
                    start_date TEXT,
                    end_date TEXT
                )"""
                )
                if "calendar.txt" in names:
                    with zf.open("calendar.txt") as f:
                        reader = csv.DictReader(line.decode("utf-8-sig") for line in f)
                        c.executemany(
                            "INSERT OR IGNORE INTO calendar VALUES (?,?,?,?,?,?,?,?,?,?)",
                            [
                                (
                                    row["service_id"].strip(),
                                    int(row.get("monday", 0)),
                                    int(row.get("tuesday", 0)),
                                    int(row.get("wednesday", 0)),
                                    int(row.get("thursday", 0)),
                                    int(row.get("friday", 0)),
                                    int(row.get("saturday", 0)),
                                    int(row.get("sunday", 0)),
                                    row.get("start_date", "").strip(),
                                    row.get("end_date", "").strip(),
                                )
                                for row in reader
                            ],
                        )

                c.execute("DROP TABLE IF EXISTS calendar_dates")
                c.execute(
                    """CREATE TABLE calendar_dates (
                    service_id TEXT,
                    date TEXT,
                    exception_type INT
                )"""
                )
                if "calendar_dates.txt" in names:
                    with zf.open("calendar_dates.txt") as f:
                        reader = csv.DictReader(line.decode("utf-8-sig") for line in f)
                        c.executemany(
                            "INSERT INTO calendar_dates VALUES (?,?,?)",
                            [
                                (
                                    row["service_id"].strip(),
                                    row["date"].strip(),
                                    int(row["exception_type"]),
                                )
                                for row in reader
                            ],
                        )
                c.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cd ON calendar_dates(service_id,date)"
                )

            conn.commit()
        finally:
            conn.close()
        os.replace(tmp_path, self._db_path)

    async def search_stops(self, query: str, limit: int | None = 60) -> list[dict[str, Any]]:
        """Busca paradas por nombre parcial o devuelve catalogo completo."""
        await self.ensure_gtfs()
        return await self.hass.async_add_executor_job(self._search_stops_sync, query, limit)

    def _search_stops_sync(self, query: str, limit: int | None = 60) -> list[dict[str, Any]]:
        all_rows = []
        if os.path.exists(self._db_path):
            try:
                conn = sqlite3.connect(self._db_path)
                c = conn.cursor()
                c.execute(
                    "SELECT stop_id, stop_name, stop_lat, stop_lon "
                    "FROM stops",
                )
                all_rows = c.fetchall()
                conn.close()
            except Exception as err:
                _LOGGER.warning("Error leyendo stops de SQLite: %s", err)

        if not all_rows:
            # Fallback a estaciones populares de Madrid si la BD aun no esta disponible
            query_raw = (query or "").strip().lower()
            if not query_raw:
                return list(MADRID_POPULAR_STATIONS)
            return [
                s for s in MADRID_POPULAR_STATIONS
                if query_raw in s["name"].lower() or query_raw in s["stop_id"].lower()
            ]

        query_raw = (query or "").strip()
        query_norm = _normalize_text(query_raw)
        query_raw_lower = query_raw.lower()

        if not query_raw:
            all_rows.sort(key=lambda row: ((row[1] or ""), (row[0] or "")))
            selected_rows = all_rows if limit is None else all_rows[:limit]
            return [
                {
                    "stop_id": row[0],
                    "name": row[1],
                    "lat": row[2],
                    "lon": row[3],
                }
                for row in selected_rows
            ]

        def rank(row: tuple[str, str, float, float]) -> int:
            stop_id = (row[0] or "")
            stop_name = (row[1] or "")
            stop_id_lower = stop_id.lower()
            stop_name_norm = _normalize_text(stop_name)
            if stop_id_lower == query_raw_lower:
                return 0
            if stop_name_norm == query_norm:
                return 1
            if stop_id_lower.startswith(query_raw_lower):
                return 2
            if stop_name_norm.startswith(query_norm):
                return 3
            return 4

        filtered = [
            row
            for row in all_rows
            if query_raw_lower in (row[0] or "").lower()
            or query_norm in _normalize_text(row[1] or "")
        ]
        filtered.sort(key=lambda row: (rank(row), (row[1] or ""), (row[0] or "")))

        selected_rows = filtered if limit is None else filtered[:limit]

        return [
            {
                "stop_id": row[0],
                "name": row[1],
                "lat": row[2],
                "lon": row[3],
            }
            for row in selected_rows
        ]

    def _get_stop_by_id_sync(self, stop_id: str) -> dict[str, Any] | None:
        """Busca una parada exacta por stop_id en GTFS."""
        try:
            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            c.execute(
                "SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops WHERE stop_id = ?",
                (stop_id,),
            )
            row = c.fetchone()
            conn.close()
            if row:
                return {
                    "stop_id": row[0],
                    "name": row[1],
                    "lat": row[2],
                    "lon": row[3],
                }
        except Exception:
            pass
        return None

    def get_destinations_for_stop(self, stop_id: str) -> list[dict[str, str]]:
        """Obtiene paradas por las que pasan trenes desde una estación.
        
        Retorna lista de paradas (posibles destinos) incluyendo intermedias.
        IMPORTANTE: Estos pueden ser destinos finales O estaciones intermedias.
        El usuario elige a dónde quiere ir, no solo a dónde termina el tren.
        """
        if not os.path.exists(self._db_path):
            return []
        
        try:
            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            # Obtiene todas las paradas (excepto el origen) por las que pasan trenes desde stop_id
            c.execute(
                """
                SELECT DISTINCT s.stop_id, s.stop_name
                FROM stop_times st
                JOIN stop_times st2 ON st.trip_id = st2.trip_id
                JOIN stops s ON st2.stop_id = s.stop_id
                WHERE st.stop_id = ?
                  AND st2.stop_sequence > st.stop_sequence
                ORDER BY s.stop_name
                """,
                (stop_id,),
            )
            rows = c.fetchall()
            conn.close()
            # Retorna lista de dicts con stop_id y nombre
            return [{"stop_id": row[0], "name": row[1]} for row in rows if row[0]]
        except Exception:
            _LOGGER.exception("Error obteniendo paradas destino para %s", stop_id)
            return []

    async def get_next_trains(
        self,
        stop_id: str,
        line: str | None,
        n: int,
        trip_updates: dict[str, dict[str, int]],
        destination_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Calcula proximas salidas aplicando retrasos RT.
        
        Si destination_id se proporciona, filtra solo trenes que pasan por esa parada
        (puede ser intermedia o final).
        """
        await self.ensure_gtfs()
        return await self.hass.async_add_executor_job(
            self._get_next_trains_sync,
            stop_id,
            line,
            n,
            trip_updates,
            destination_id,
        )

    def _get_next_trains_sync(
        self,
        stop_id: str,
        line: str | None,
        n: int,
        trip_updates: dict[str, dict[str, int]],
        destination_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Obtiene proximos trenes con filtro opcional de parada destino.
        
        El destino puede ser una parada intermedia o final del trayecto.
        """
        tz = pytz.timezone(TZ_MADRID)
        now_mad = datetime.now(tz)
        today = now_mad.date()
        now_secs = now_mad.hour * 3600 + now_mad.minute * 60 + now_mad.second

        conn = sqlite3.connect(self._db_path)
        today_services = self._active_services(conn, today)
        tomorrow = today + timedelta(days=1)
        tomorrow_services = self._active_services(conn, tomorrow) if now_mad.hour >= 21 else set()
        c = conn.cursor()

        line_filter = "AND r.route_short_name = ?" if line else ""

        # Optimización: Filtrar destino en la misma consulta SQL (JOIN) en vez de N+1 queries
        if destination_id:
            sql = f"""
            SELECT st.trip_id, st.departure_time,
                   r.route_short_name, t.trip_headsign, t.service_id
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.trip_id
            JOIN routes r ON t.route_id = r.route_id
            JOIN stop_times st_dest ON st.trip_id = st_dest.trip_id
                 AND st_dest.stop_id = ?
                 AND st_dest.stop_sequence > st.stop_sequence
            WHERE st.stop_id = ? {line_filter}
            ORDER BY st.departure_time
            """
            params: list[Any] = [destination_id, stop_id]
            if line:
                params.append(line)
        else:
            sql = f"""
            SELECT st.trip_id, st.departure_time,
                   r.route_short_name, t.trip_headsign, t.service_id
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.trip_id
            JOIN routes r ON t.route_id = r.route_id
            WHERE st.stop_id = ? {line_filter}
            ORDER BY st.departure_time
            """
            params = [stop_id]
            if line:
                params.append(line)

        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()

        trains: list[dict[str, Any]] = []
        for trip_id, dep_time, route, headsign, svc_id in rows:
            if not dep_time:
                continue

            sched_secs = self._gtfs_time_to_secs(dep_time)
            delay_secs = trip_updates.get(trip_id, {}).get(stop_id, 0)
            real_secs = sched_secs + delay_secs
            diff = real_secs - now_secs

            # Soporte cambio de día / medianoche
            is_valid_service = False
            if svc_id in today_services:
                is_valid_service = True
            elif now_mad.hour >= 21 and sched_secs < 14400 and svc_id in tomorrow_services:
                # Tren de madrugada de mañana calculado desde noche de hoy
                diff += 86400
                is_valid_service = True
            elif now_mad.hour < 4 and sched_secs >= 86400 and svc_id in today_services:
                # Tren GTFS codificado > 24h
                is_valid_service = True

            if not is_valid_service:
                continue

            # Mantener ventana de -60s hasta 3 horas (10800s)
            if diff < -60 or diff > 10800:
                continue

            trains.append(
                {
                    "trip_id": trip_id,
                    "line": route,
                    "headsign": headsign,
                    "scheduled": dep_time[:5],
                    "delay_min": round(delay_secs / 60, 1),
                    "minutes": max(0.0, round(diff / 60, 1)),
                    "departure": (
                        now_mad + timedelta(seconds=max(0, diff))
                    ).strftime("%H:%M"),
                }
            )
            if len(trains) >= n:
                break

        return trains

    @staticmethod
    def _gtfs_time_to_secs(raw_time: str) -> int:
        """Convierte HH:MM:SS GTFS a segundos desde medianoche."""
        h, m, s = raw_time.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    @staticmethod
    def _active_services(conn: sqlite3.Connection, today: date) -> set[str]:
        """Calcula service_ids activos aplicando calendar y excepciones."""
        day_col = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ][today.weekday()]
        date_str = today.strftime("%Y%m%d")
        c = conn.cursor()

        c.execute(
            f"SELECT service_id FROM calendar "
            f"WHERE {day_col}=1 "
            f"AND (start_date IS NULL OR start_date='' OR start_date<=?) "
            f"AND (end_date IS NULL OR end_date='' OR end_date>=?)",
            (date_str, date_str),
        )
        services = {row[0] for row in c.fetchall()}

        c.execute(
            "SELECT service_id, exception_type FROM calendar_dates WHERE date=?",
            (date_str,),
        )
        for svc_id, exc_type in c.fetchall():
            if exc_type == 1:
                services.add(svc_id)
            elif exc_type == 2:
                services.discard(svc_id)

        return services


class RenfeRTCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinador RT compartido: trip updates + posiciones de trenes."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECS),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        try:
            trip_raw, pos_raw = await asyncio.gather(
                self._fetch_json(session, RT_UPDATES_URL),
                self._fetch_json(session, RT_POSITIONS_URL),
            )
            return {
                "trip_updates": self._parse_trip_updates(trip_raw),
                "positions": self._parse_positions(pos_raw),
                "fetched_at": datetime.now(_TZ_MADRID),
            }
        except Exception as err:
            raise UpdateFailed(f"Error obteniendo RT Renfe: {err}") from err

    @staticmethod
    async def _fetch_json(session, url: str) -> dict[str, Any]:
        import aiohttp

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    @staticmethod
    def _parse_trip_updates(data: dict[str, Any]) -> dict[str, dict[str, int]]:
        delays: dict[str, dict[str, int]] = {}
        for entity in data.get("entity") or []:
            if not isinstance(entity, dict):
                continue

            trip_update = entity.get("trip_update") or {}
            if not isinstance(trip_update, dict):
                continue

            trip = trip_update.get("trip") or {}
            if not isinstance(trip, dict):
                continue

            trip_id = trip.get("tripId", "")
            if not trip_id:
                continue

            stop_delays: dict[str, int] = {}
            for stop_update in trip_update.get("stopTimeUpdate") or []:
                if not isinstance(stop_update, dict):
                    continue

                stop_id = stop_update.get("stopId", "")
                dep_or_arr = stop_update.get("departure") or stop_update.get("arrival") or {}
                if not isinstance(dep_or_arr, dict):
                    dep_or_arr = {}
                if stop_id:
                    stop_delays[stop_id] = dep_or_arr.get("delay", 0)

            if stop_delays:
                delays[trip_id] = stop_delays

        return delays

    @staticmethod
    def _parse_positions(data: dict[str, Any]) -> list[dict[str, Any]]:
        vehicles: list[dict[str, Any]] = []
        for entity in data.get("entity") or []:
            if not isinstance(entity, dict):
                continue

            vehicle_data = entity.get("vehicle") or {}
            if not isinstance(vehicle_data, dict):
                continue

            position = vehicle_data.get("position") or {}
            trip = vehicle_data.get("trip") or {}
            vehicle_meta = vehicle_data.get("vehicle") or {}

            if not isinstance(position, dict):
                position = {}
            if not isinstance(trip, dict):
                trip = {}
            if not isinstance(vehicle_meta, dict):
                vehicle_meta = {}

            lat = position.get("latitude")
            lon = position.get("longitude")
            if lat is None or lon is None:
                continue

            vehicles.append(
                {
                    "trip_id": trip.get("tripId", ""),
                    "route_id": trip.get("routeId", ""),
                    "label": vehicle_meta.get("label", ""),
                    "lat": lat,
                    "lon": lon,
                    "speed_kmh": round((position.get("speed") or 0) * 3.6, 1),
                    "status": vehicle_data.get("currentStatus", ""),
                    "stop_id": vehicle_data.get("stopId", ""),
                }
            )

        return vehicles
