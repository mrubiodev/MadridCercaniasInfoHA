/**
 * Renfe Cercanías Map Card para Home Assistant
 * Mapa interactivo en tiempo real con las posiciones GPS de los trenes de Renfe Cercanías.
 * Soporta visualización de todas las líneas de Madrid y filtrado interactivo por línea.
 */

const LINE_COLORS = {
  "C1": "#0099cd",
  "C2": "#00954c",
  "C3": "#8a4999",
  "C3A": "#8a4999",
  "C4": "#004b93",
  "C4A": "#004b93",
  "C4B": "#004b93",
  "C5": "#e6b800",
  "C7": "#e4002b",
  "C8": "#757575",
  "C8A": "#757575",
  "C9": "#f39200",
  "C10": "#00a587",
  "DEFAULT": "#6f2c91"
};

const MADRID_KEY_STATIONS = [
  { name: "Atocha Cercanías", lat: 40.4065, lon: -3.6896 },
  { name: "Chamartín", lat: 40.4721, lon: -3.6824 },
  { name: "Nuevos Ministerios", lat: 40.4462, lon: -3.6917 },
  { name: "Sol", lat: 40.4169, lon: -3.7036 },
  { name: "Méndez Álvaro", lat: 40.3957, lon: -3.6781 },
  { name: "Príncipe Pío", lat: 40.4208, lon: -3.7197 },
  { name: "Recoletos", lat: 40.4227, lon: -3.6912 },
  { name: "Móstoles Central", lat: 40.3223, lon: -3.8643 },
  { name: "Fuenlabrada", lat: 40.2829, lon: -3.7937 },
  { name: "Leganés Central", lat: 40.3308, lon: -3.7667 },
  { name: "Alcalá de Henares", lat: 40.4879, lon: -3.3644 },
  { name: "Getafe Central", lat: 40.3061, lon: -3.7314 },
  { name: "Alcorcón", lat: 40.3496, lon: -3.8294 },
  { name: "Aeropuerto T4", lat: 40.4918, lon: -3.5936 },
  { name: "Coslada", lat: 40.4269, lon: -3.5358 },
  { name: "Villalba", lat: 40.6306, lon: -4.0084 },
  { name: "Aranjuez", lat: 40.0345, lon: -3.6186 }
];

function getLineColor(line) {
  const clean = (line || "").trim().toUpperCase();
  return LINE_COLORS[clean] || LINE_COLORS.DEFAULT;
}

function loadLeaflet(callback) {
  if (window.L) {
    callback();
    return;
  }
  const existingScript = document.getElementById("leaflet-js");
  if (existingScript) {
    existingScript.addEventListener("load", callback);
    return;
  }
  const script = document.createElement("script");
  script.id = "leaflet-js";
  script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  script.crossOrigin = "";
  script.onload = () => callback();
  document.head.appendChild(script);
}

class RenfeCercaniasMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._map = null;
    this._markersLayer = null;
    this._stationsLayer = null;
    this._config = {};
    this._hass = null;
    this._leafletLoaded = false;
    this._activeFilter = ""; // "" = todas
    this._showStations = true;
  }

  setConfig(config) {
    this._config = {
      height: config.height || 440,
      zoom: config.zoom || 11,
      line_filter: config.line_filter || "",
      show_stations: config.show_stations !== false,
      show_filter_bar: config.show_filter_bar !== false,
      ...config
    };
    if (this._config.line_filter && !this._activeFilter) {
      this._activeFilter = this._config.line_filter.toUpperCase();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._leafletLoaded) {
      this._initCard();
    } else {
      this._updateMarkers();
    }
  }

  getCardSize() {
    return 6;
  }

  _initCard() {
    this._leafletLoaded = true;
    const height = this._config.height || 440;
    const lines = ["C1", "C2", "C3", "C4", "C5", "C7", "C8", "C9", "C10"];

    this.shadowRoot.innerHTML = `
      <style>
        @import url("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
        :host {
          display: block;
        }
        ha-card {
          border-radius: var(--ha-card-border-radius, 16px);
          overflow: hidden;
          background: var(--ha-card-background, var(--card-background-color, #ffffff));
          box-shadow: var(--ha-card-box-shadow, 0 4px 12px rgba(0,0,0,0.06));
          position: relative;
        }
        .header-bar {
          padding: 12px 16px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--divider-color, rgba(0,0,0,0.08));
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #212121);
        }
        .header-title {
          font-size: 1.05rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .header-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .train-badge-counter {
          font-size: 0.8rem;
          background: #6f2c91;
          color: white;
          padding: 3px 10px;
          border-radius: 12px;
          font-weight: 600;
          box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        .center-btn {
          background: none;
          border: 1px solid var(--divider-color, #ddd);
          border-radius: 6px;
          cursor: pointer;
          padding: 3px 6px;
          display: flex;
          align-items: center;
          color: inherit;
          font-size: 0.75rem;
          gap: 4px;
        }
        .center-btn:hover {
          background: rgba(0,0,0,0.05);
        }

        /* Barra de filtros de líneas interactiva */
        .filter-bar {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 12px;
          background: var(--secondary-background-color, #f7f7f9);
          overflow-x: auto;
          white-space: nowrap;
          border-bottom: 1px solid var(--divider-color, rgba(0,0,0,0.06));
          scrollbar-width: thin;
        }
        .filter-pill {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 4px 10px;
          border-radius: 14px;
          font-size: 0.75rem;
          font-weight: 700;
          cursor: pointer;
          border: 2px solid transparent;
          transition: all 0.2s ease;
          user-select: none;
          color: white;
        }
        .filter-pill:hover {
          opacity: 0.9;
          transform: translateY(-1px);
        }
        .filter-pill.active {
          box-shadow: 0 0 0 2px white, 0 0 0 4px #6f2c91;
          transform: scale(1.05);
        }
        .filter-pill.pill-all {
          background: #6f2c91;
        }

        #map-container {
          width: 100%;
          height: ${height}px;
          position: relative;
          z-index: 1;
        }
        .legend-bar {
          position: absolute;
          bottom: 12px;
          left: 12px;
          background: var(--card-background-color, rgba(255, 255, 255, 0.94));
          color: var(--primary-text-color, #333);
          border: 1px solid var(--divider-color, rgba(0,0,0,0.1));
          backdrop-filter: blur(4px);
          padding: 6px 12px;
          border-radius: 20px;
          font-size: 0.75rem;
          box-shadow: 0 2px 8px rgba(0,0,0,0.18);
          z-index: 1000;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .live-dot {
          width: 8px;
          height: 8px;
          background: #2e7d32;
          border-radius: 50%;
          display: inline-block;
          animation: mapPulse 2s infinite;
        }
        @keyframes mapPulse {
          0% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0.7); }
          70% { box-shadow: 0 0 0 6px rgba(46, 125, 50, 0); }
          100% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0); }
        }
        .train-marker-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          color: white;
          font-weight: 800;
          font-size: 11px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.4);
          border: 2px solid #ffffff;
          transition: transform 0.2s ease;
        }
        .train-marker-icon.c5-badge {
          color: #222 !important;
        }
        .train-marker-icon:hover {
          transform: scale(1.25);
          z-index: 9999 !important;
        }
        .station-dot-icon {
          background: #ffffff;
          border: 2px solid #333;
          border-radius: 50%;
          width: 10px;
          height: 10px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }
      </style>
      <ha-card>
        <div class="header-bar">
          <div class="header-title">
            <svg style="width:20px;height:20px;fill:#6f2c91;" viewBox="0 0 24 24">
              <path d="M12,2C8,2 4,2.5 4,6V15.5A3.5,3.5 0 0,0 7.5,19L6,20.5V21H18V20.5L16.5,19A3.5,3.5 0 0,0 20,15.5V6C20,2.5 16.42,2 12,2M12,4C17,4 18,4.5 18,6V10H6V6C6,4.5 7,4 12,4M6,12H18V15.5A1.5,1.5 0 0,1 16.5,17H7.5A1.5,1.5 0 0,1 6,15.5V12M8.5,13A1.5,1.5 0 0,0 7,14.5A1.5,1.5 0 0,0 8.5,16A1.5,1.5 0 0,0 10,14.5A1.5,1.5 0 0,0 8.5,13M15.5,13A1.5,1.5 0 0,0 14,14.5A1.5,1.5 0 0,0 15.5,16A1.5,1.5 0 0,0 17,14.5A1.5,1.5 0 0,0 15.5,13Z"/>
            </svg>
            <span>${this._config.title || "Trenes en Vivo Madrid RT"}</span>
          </div>
          <div class="header-actions">
            <button id="center-madrid" class="center-btn" title="Centrar mapa en Madrid">
              <svg style="width:14px;height:14px;fill:currentColor;" viewBox="0 0 24 24"><path d="M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M3.05,13H1V11H3.05C3.5,6.83 6.83,3.5 11,3.05V1H13V3.05C17.17,3.5 20.5,6.83 20.95,11H23V13H20.95C20.5,17.17 17.17,20.5 13,20.95V23H11V20.95C6.83,20.5 3.5,17.17 3.05,13M12,5A7,7 0 0,0 5,12A7,7 0 0,0 12,19A7,7 0 0,0 19,12A7,7 0 0,0 12,5Z"/></svg>
              Madrid
            </button>
            <span id="train-counter" class="train-badge-counter">0 trenes</span>
          </div>
        </div>

        ${this._config.show_filter_bar ? `
          <div class="filter-bar" id="filter-bar">
            <span class="filter-pill pill-all ${this._activeFilter === "" ? 'active' : ''}" data-line="">Todas</span>
            ${lines.map(line => `
              <span class="filter-pill ${this._activeFilter === line ? 'active' : ''}" 
                    style="background: ${getLineColor(line)}; ${line === 'C5' ? 'color:#222;' : ''}" 
                    data-line="${line}">${line}</span>
            `).join('')}
          </div>
        ` : ''}

        <div id="map-container"></div>

        <div class="legend-bar">
          <span class="live-dot"></span>
          <span id="legend-text">Posiciones GPS en tiempo real</span>
        </div>
      </ha-card>
    `;

    // Listeners de los filtros interactivos
    const filterBar = this.shadowRoot.getElementById("filter-bar");
    if (filterBar) {
      filterBar.addEventListener("click", (e) => {
        const target = e.target.closest(".filter-pill");
        if (!target) return;
        const line = target.getAttribute("data-line") || "";
        this._activeFilter = line;
        filterBar.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
        target.classList.add("active");
        this._updateMarkers();
      });
    }

    const centerBtn = this.shadowRoot.getElementById("center-madrid");
    if (centerBtn) {
      centerBtn.addEventListener("click", () => {
        if (this._map) {
          this._map.setView([40.4168, -3.7038], this._config.zoom || 11);
        }
      });
    }

    loadLeaflet(() => {
      this._createMap();
    });
  }

  _createMap() {
    const container = this.shadowRoot.getElementById("map-container");
    if (!container || this._map) return;

    const defaultLat = 40.4168;
    const defaultLon = -3.7038;
    const zoom = this._config.zoom || 11;

    this._map = window.L.map(container).setView([defaultLat, defaultLon], zoom);

    const isDarkMode = this._hass?.themes?.darkMode || document.querySelector("html")?.getAttribute("theme") === "dark";
    const tileTheme = isDarkMode ? "dark_all" : "rastertiles/voyager";
    const tileUrl = `https://{s}.basemaps.cartocdn.com/${tileTheme}/{z}/{x}/{y}{r}.png`;

    window.L.tileLayer(tileUrl, {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(this._map);

    this._stationsLayer = window.L.layerGroup().addTo(this._map);
    this._markersLayer = window.L.layerGroup().addTo(this._map);

    if (this._config.show_stations) {
      this._addStationMarkers();
    }

    setTimeout(() => {
      if (this._map) this._map.invalidateSize();
    }, 250);

    this._updateMarkers();
  }

  _addStationMarkers() {
    if (!this._map || !this._stationsLayer || !window.L) return;

    this._stationsLayer.clearLayers();
    MADRID_KEY_STATIONS.forEach(st => {
      const icon = window.L.divIcon({
        className: 'station-dot-div',
        html: `<div class="station-dot-icon" title="${st.name}"></div>`,
        iconSize: [10, 10],
        iconAnchor: [5, 5]
      });

      const marker = window.L.marker([st.lat, st.lon], { icon });
      marker.bindTooltip(`<b>${st.name}</b>`, { direction: 'top', offset: [0, -5] });
      this._stationsLayer.addLayer(marker);
    });
  }

  _getPositions() {
    if (!this._hass) return [];

    let positions = [];
    const seenTrips = new Set();

    const addList = (list) => {
      if (!Array.isArray(list)) return;
      list.forEach(p => {
        const key = p.trip_id || `${p.lat}_${p.lon}_${p.label}`;
        if (!seenTrips.has(key)) {
          seenTrips.add(key);
          positions.push(p);
        }
      });
    };

    // 1. Si hay entidad específica configurada
    if (this._config.entity && this._hass.states[this._config.entity]) {
      const st = this._hass.states[this._config.entity];
      if (st.attributes?.positions) {
        addList(st.attributes.positions);
      }
    }

    // 2. Comprobar explorador (suele tener todos los trenes de Madrid)
    const explorerState = this._hass.states["sensor.renfe_cercanias_explorador"];
    if (explorerState?.attributes?.positions) {
      addList(explorerState.attributes.positions);
    }

    // 3. Agregar de cualquier otra entidad de cercanías existente
    for (const eid of Object.keys(this._hass.states)) {
      if (eid.startsWith("sensor.renfe_cercanias") || eid.startsWith("sensor.cercanias")) {
        const ent = this._hass.states[eid];
        if (ent?.attributes?.positions) {
          addList(ent.attributes.positions);
        }
      }
    }

    return positions;
  }

  _updateMarkers() {
    if (!this._map || !this._markersLayer || !window.L) return;

    this._markersLayer.clearLayers();

    const positions = this._getPositions();
    const filterLine = (this._activeFilter || "").trim().toUpperCase();

    let visibleCount = 0;

    positions.forEach((pos) => {
      const lat = parseFloat(pos.lat);
      const lon = parseFloat(pos.lon);
      if (isNaN(lat) || isNaN(lon)) return;

      const label = (pos.label || "").trim();
      let line = "";
      if (label.includes("-")) {
        line = label.split("-")[0].toUpperCase();
      } else if (label.startsWith("C")) {
        line = label.substring(0, 3).trim().toUpperCase();
        if (line.endsWith("-")) line = line.substring(0, 2);
      } else {
        line = "C";
      }

      if (filterLine && !line.startsWith(filterLine)) {
        return;
      }

      visibleCount++;
      const color = getLineColor(line);
      const speed = pos.speed_kmh !== undefined ? `${pos.speed_kmh} km/h` : "N/D";
      const statusRaw = pos.status || "";
      let statusDesc = "En circulación";
      if (statusRaw.includes("STOPPED")) statusDesc = "Detenido en parada";
      if (statusRaw.includes("TRANSIT")) statusDesc = "En trayecto";

      const isC5 = line.startsWith("C5");
      const iconHtml = `
        <div class="train-marker-icon ${isC5 ? 'c5-badge' : ''}" style="background-color: ${color}; width: 28px; height: 28px;">
          ${line}
        </div>
      `;

      const customIcon = window.L.divIcon({
        className: 'custom-div-icon',
        html: iconHtml,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -14]
      });

      const popupContent = `
        <div style="font-family: system-ui, -apple-system, sans-serif; min-width: 170px; font-size: 0.85rem; line-height: 1.45;">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;border-bottom:1px solid #eee;padding-bottom:4px;">
            <span style="background:${color};color:${isC5 ? '#222' : 'white'};padding:2px 7px;border-radius:4px;font-weight:bold;font-size:0.75rem;">${line}</span>
            <strong style="font-size:0.95rem;">${label || 'Tren Cercanías'}</strong>
          </div>
          <div><strong>Velocidad:</strong> ${speed}</div>
          <div><strong>Estado:</strong> ${statusDesc}</div>
          ${pos.stop_id ? `<div><strong>Parada ID:</strong> ${pos.stop_id}</div>` : ''}
          ${pos.trip_id ? `<div style="color:#777;font-size:0.75rem;margin-top:4px;">Viaje: ${pos.trip_id}</div>` : ''}
        </div>
      `;

      const marker = window.L.marker([lat, lon], { icon: customIcon });
      marker.bindPopup(popupContent);
      this._markersLayer.addLayer(marker);
    });

    const counterEl = this.shadowRoot.getElementById("train-counter");
    if (counterEl) {
      if (filterLine) {
        counterEl.textContent = `${filterLine}: ${visibleCount} trenes`;
      } else {
        counterEl.textContent = `Madrid: ${visibleCount} trenes`;
      }
    }

    const legendText = this.shadowRoot.getElementById("legend-text");
    if (legendText) {
      legendText.textContent = filterLine 
        ? `Línea ${filterLine} · ${visibleCount} trenes en vivo`
        : `Toda la red · ${visibleCount} trenes activos`;
    }
  }

  static getConfigElement() {
    return document.createElement("renfe-cercanias-map-card-editor");
  }

  static getStubConfig(hass, entities) {
    const explorer = entities.find(e => e === "sensor.renfe_cercanias_explorador");
    return {
      entity: explorer || "",
      title: "Trenes en Vivo Madrid RT",
      height: 440,
      zoom: 11,
      line_filter: "",
      show_filter_bar: true,
      show_stations: true
    };
  }
}

class RenfeCercaniasMapCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) return;

    const entities = Object.keys(this._hass.states).filter(
      (eid) => eid.startsWith("sensor.renfe_cercanias") || eid.startsWith("sensor.cercanias")
    );

    const lines = ["", "C1", "C2", "C3", "C4", "C5", "C7", "C8", "C9", "C10"];

    this.shadowRoot.innerHTML = `
      <style>
        .editor-container {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 8px 0;
        }
        .form-row {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        label {
          font-weight: 500;
          font-size: 0.9rem;
        }
        select, input[type="text"], input[type="number"] {
          padding: 8px 10px;
          border-radius: 6px;
          border: 1px solid var(--divider-color, #ccc);
          background: var(--card-background-color, #fff);
          color: inherit;
          font-size: 0.9rem;
        }
        .checkbox-row {
          display: flex;
          align-items: center;
          gap: 8px;
        }
      </style>
      <div class="editor-container">
        <div class="form-row">
          <label>Título de la tarjeta:</label>
          <input type="text" id="title" value="${this._config.title || 'Trenes en Vivo Madrid RT'}">
        </div>

        <div class="form-row">
          <label>Entidad con datos de posiciones (Explorador o Sensor):</label>
          <select id="entity">
            <option value="">-- Detección automática de toda la red --</option>
            ${entities.map(e => `<option value="${e}" ${this._config.entity === e ? 'selected' : ''}>${this._hass.states[e].attributes.friendly_name || e}</option>`).join('')}
          </select>
        </div>

        <div class="form-row">
          <label>Línea por defecto:</label>
          <select id="line_filter">
            ${lines.map(l => `<option value="${l}" ${this._config.line_filter === l ? 'selected' : ''}>${l === "" ? "Todas las líneas (Comunidad de Madrid)" : l}</option>`).join('')}
          </select>
        </div>

        <div class="form-row">
          <label>Altura del mapa (píxeles):</label>
          <input type="number" id="height" min="250" max="900" step="20" value="${this._config.height || 440}">
        </div>

        <div class="form-row">
          <label>Zoom inicial:</label>
          <input type="number" id="zoom" min="9" max="16" value="${this._config.zoom || 11}">
        </div>

        <div class="checkbox-row">
          <input type="checkbox" id="show_filter_bar" ${this._config.show_filter_bar !== false ? 'checked' : ''}>
          <label for="show_filter_bar">Mostrar barra interactiva de selección de líneas en el mapa</label>
        </div>

        <div class="checkbox-row">
          <input type="checkbox" id="show_stations" ${this._config.show_stations !== false ? 'checked' : ''}>
          <label for="show_stations">Mostrar estaciones principales de Madrid en el mapa</label>
        </div>
      </div>
    `;

    this.shadowRoot.getElementById('title').addEventListener('input', (e) => this._valueChanged('title', e.target.value));
    this.shadowRoot.getElementById('entity').addEventListener('change', (e) => this._valueChanged('entity', e.target.value));
    this.shadowRoot.getElementById('line_filter').addEventListener('change', (e) => this._valueChanged('line_filter', e.target.value));
    this.shadowRoot.getElementById('height').addEventListener('change', (e) => this._valueChanged('height', parseInt(e.target.value, 10)));
    this.shadowRoot.getElementById('zoom').addEventListener('change', (e) => this._valueChanged('zoom', parseInt(e.target.value, 10)));
    this.shadowRoot.getElementById('show_filter_bar').addEventListener('change', (e) => this._valueChanged('show_filter_bar', e.target.checked));
    this.shadowRoot.getElementById('show_stations').addEventListener('change', (e) => this._valueChanged('show_stations', e.target.checked));
  }

  _valueChanged(key, value) {
    if (!this._config) return;
    const newConfig = { ...this._config, [key]: value };
    const event = new CustomEvent("config-changed", {
      detail: { config: newConfig },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }
}

customElements.define("renfe-cercanias-map-card", RenfeCercaniasMapCard);
customElements.define("renfe-cercanias-map-card-editor", RenfeCercaniasMapCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "renfe-cercanias-map-card",
  name: "Mapa Renfe Cercanías RT",
  preview: true,
  description: "Mapa interactivo con posiciones GPS en tiempo real de toda la red de Cercanías Madrid o filtrado por líneas."
});
