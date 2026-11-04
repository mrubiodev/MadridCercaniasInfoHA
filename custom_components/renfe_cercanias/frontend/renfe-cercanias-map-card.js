/**
 * Renfe Cercanías Map Card para Home Assistant
 * Mapa interactivo en tiempo real con las posiciones GPS de los trenes de Renfe Cercanías.
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
    this._stationMarker = null;
    this._config = {};
    this._hass = null;
    this._leafletLoaded = false;
  }

  setConfig(config) {
    this._config = {
      height: config.height || 420,
      zoom: config.zoom || 11,
      line_filter: config.line_filter || "",
      show_station: config.show_station !== false,
      ...config
    };
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
    return 5;
  }

  _initCard() {
    this._leafletLoaded = true;
    const height = this._config.height || 420;

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
        .train-badge-counter {
          font-size: 0.8rem;
          background: #6f2c91;
          color: white;
          padding: 3px 8px;
          border-radius: 12px;
          font-weight: 600;
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
          background: rgba(255, 255, 255, 0.92);
          backdrop-filter: blur(4px);
          padding: 6px 12px;
          border-radius: 20px;
          font-size: 0.75rem;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
          z-index: 1000;
          display: flex;
          align-items: center;
          gap: 6px;
          color: #333;
          pointer-events: none;
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
        .train-marker-icon:hover {
          transform: scale(1.2);
        }
        .station-marker-icon {
          background: #ffffff;
          border: 2px solid #6f2c91;
          color: #6f2c91;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        }
      </style>
      <ha-card>
        <div class="header-bar">
          <div class="header-title">
            <svg style="width:20px;height:20px;fill:#6f2c91;" viewBox="0 0 24 24">
              <path d="M12,2C8,2 4,2.5 4,6V15.5A3.5,3.5 0 0,0 7.5,19L6,20.5V21H18V20.5L16.5,19A3.5,3.5 0 0,0 20,15.5V6C20,2.5 16.42,2 12,2M12,4C17,4 18,4.5 18,6V10H6V6C6,4.5 7,4 12,4M6,12H18V15.5A1.5,1.5 0 0,1 16.5,17H7.5A1.5,1.5 0 0,1 6,15.5V12M8.5,13A1.5,1.5 0 0,0 7,14.5A1.5,1.5 0 0,0 8.5,16A1.5,1.5 0 0,0 10,14.5A1.5,1.5 0 0,0 8.5,13M15.5,13A1.5,1.5 0 0,0 14,14.5A1.5,1.5 0 0,0 15.5,16A1.5,1.5 0 0,0 17,14.5A1.5,1.5 0 0,0 15.5,13Z"/>
            </svg>
            <span>${this._config.title || "Mapa Cercanías Renfe RT"}</span>
          </div>
          <span id="train-counter" class="train-badge-counter">0 trenes</span>
        </div>

        <div id="map-container"></div>

        <div class="legend-bar">
          <span class="live-dot"></span>
          <span>Posiciones GPS en tiempo real</span>
        </div>
      </ha-card>
    `;

    loadLeaflet(() => {
      this._createMap();
    });
  }

  _createMap() {
    const container = this.shadowRoot.getElementById("map-container");
    if (!container || this._map) return;

    // Centro por defecto Madrid Cercanías: 40.4168, -3.7038
    const defaultLat = 40.4168;
    const defaultLon = -3.7038;
    const zoom = this._config.zoom || 11;

    this._map = window.L.map(container).setView([defaultLat, defaultLon], zoom);

    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(this._map);

    this._markersLayer = window.L.layerGroup().addTo(this._map);

    // Resize observer para que no se quede gris el mapa al insertarse
    setTimeout(() => {
      if (this._map) this._map.invalidateSize();
    }, 250);

    this._updateMarkers();
  }

  _getPositions() {
    if (!this._hass) return [];

    // 1. Intentar desde la entidad seleccionada en config
    if (this._config.entity && this._hass.states[this._config.entity]) {
      const stateObj = this._hass.states[this._config.entity];
      if (stateObj.attributes && Array.isArray(stateObj.attributes.positions)) {
        return stateObj.attributes.positions;
      }
    }

    // 2. Intentar desde sensor.renfe_cercanias_explorador
    const explorerState = this._hass.states["sensor.renfe_cercanias_explorador"];
    if (explorerState?.attributes?.positions && Array.isArray(explorerState.attributes.positions)) {
      return explorerState.attributes.positions;
    }

    // 3. Buscar cualquier entidad de renfe_cercanias que tenga posiciones
    for (const eid of Object.keys(this._hass.states)) {
      if (eid.startsWith("sensor.renfe_cercanias")) {
        const ent = this._hass.states[eid];
        if (ent?.attributes?.positions && Array.isArray(ent.attributes.positions)) {
          return ent.attributes.positions;
        }
      }
    }

    return [];
  }

  _updateMarkers() {
    if (!this._map || !this._markersLayer || !window.L) return;

    this._markersLayer.clearLayers();

    const positions = this._getPositions();
    const filterLine = (this._config.line_filter || "").trim().toUpperCase();

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
        line = label.substring(0, 2).toUpperCase();
      } else {
        line = "C";
      }

      if (filterLine && line !== filterLine) {
        return;
      }

      visibleCount++;
      const color = getLineColor(line);
      const speed = pos.speed_kmh !== undefined ? `${pos.speed_kmh} km/h` : "N/D";
      const statusRaw = pos.status || "";
      let statusDesc = "En circulación";
      if (statusRaw.includes("STOPPED")) statusDesc = "Detenido en parada";
      if (statusRaw.includes("TRANSIT")) statusDesc = "En trayecto";

      const iconHtml = `
        <div class="train-marker-icon" style="background-color: ${color}; width: 28px; height: 28px;">
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
        <div style="font-family: system-ui, sans-serif; min-width: 150px; font-size: 0.85rem; line-height: 1.4;">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
            <span style="background:${color};color:white;padding:2px 6px;border-radius:4px;font-weight:bold;font-size:0.75rem;">${line}</span>
            <strong style="font-size:0.95rem;">${label || 'Tren Cercanías'}</strong>
          </div>
          <div><strong>Velocidad:</strong> ${speed}</div>
          <div><strong>Estado:</strong> ${statusDesc}</div>
          ${pos.trip_id ? `<div style="color:#777;font-size:0.75rem;margin-top:4px;">Viaje: ${pos.trip_id}</div>` : ''}
        </div>
      `;

      const marker = window.L.marker([lat, lon], { icon: customIcon });
      marker.bindPopup(popupContent);
      this._markersLayer.addLayer(marker);
    });

    const counterEl = this.shadowRoot.getElementById("train-counter");
    if (counterEl) {
      counterEl.textContent = `${visibleCount} trenes`;
    }
  }

  static getConfigElement() {
    return document.createElement("renfe-cercanias-map-card-editor");
  }

  static getStubConfig(hass, entities) {
    const explorer = entities.find(e => e === "sensor.renfe_cercanias_explorador");
    return {
      entity: explorer || "",
      title: "Mapa Cercanías Renfe",
      height: 420,
      zoom: 11,
      line_filter: ""
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
      (eid) => eid.startsWith("sensor.renfe_cercanias")
    );

    const lines = ["", "C1", "C2", "C3", "C4", "C5", "C7", "C8", "C10"];

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
      </style>
      <div class="editor-container">
        <div class="form-row">
          <label>Título de la tarjeta:</label>
          <input type="text" id="title" value="${this._config.title || 'Mapa Cercanías Renfe'}">
        </div>

        <div class="form-row">
          <label>Entidad con datos de posiciones (Explorador o Sensor):</label>
          <select id="entity">
            <option value="">-- Detección automática --</option>
            ${entities.map(e => `<option value="${e}" ${this._config.entity === e ? 'selected' : ''}>${this._hass.states[e].attributes.friendly_name || e}</option>`).join('')}
          </select>
        </div>

        <div class="form-row">
          <label>Filtrar por línea:</label>
          <select id="line_filter">
            ${lines.map(l => `<option value="${l}" ${this._config.line_filter === l ? 'selected' : ''}>${l === "" ? "Todas las líneas" : l}</option>`).join('')}
          </select>
        </div>

        <div class="form-row">
          <label>Altura del mapa (píxeles):</label>
          <input type="number" id="height" min="200" max="800" step="20" value="${this._config.height || 420}">
        </div>

        <div class="form-row">
          <label>Zoom inicial:</label>
          <input type="number" id="zoom" min="9" max="16" value="${this._config.zoom || 11}">
        </div>
      </div>
    `;

    this.shadowRoot.getElementById('title').addEventListener('input', (e) => this._valueChanged('title', e.target.value));
    this.shadowRoot.getElementById('entity').addEventListener('change', (e) => this._valueChanged('entity', e.target.value));
    this.shadowRoot.getElementById('line_filter').addEventListener('change', (e) => this._valueChanged('line_filter', e.target.value));
    this.shadowRoot.getElementById('height').addEventListener('change', (e) => this._valueChanged('height', parseInt(e.target.value, 10)));
    this.shadowRoot.getElementById('zoom').addEventListener('change', (e) => this._valueChanged('zoom', parseInt(e.target.value, 10)));
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
  name: "Mapa Renfe Cercanías",
  preview: true,
  description: "Muestra un mapa interactivo con las posiciones en tiempo real de los trenes de Cercanías Renfe."
});
