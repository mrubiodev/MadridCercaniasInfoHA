/**
 * Renfe Cercanías Config & Explorer Panel Card para Home Assistant
 * Menú interactivo para gestionar la integración, refrescar GTFS y explorar estaciones en vivo.
 */

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatAge(seconds) {
  if (!seconds || seconds <= 0) return "recién actualizado";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  if (days > 0) return `hace ${days} día${days > 1 ? 's' : ''}`;
  if (hours > 0) return `hace ${hours} hora${hours > 1 ? 's' : ''}`;
  const minutes = Math.floor((seconds % 3600) / 60);
  return `hace ${minutes} minuto${minutes > 1 ? 's' : ''}`;
}

class RenfeCercaniasConfigCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
    this._searchQuery = "";
    this._selectedLine = "";
    this._isSearching = false;
    this._isRefreshingGtfs = false;
  }

  setConfig(config) {
    this._config = {
      title: config.title || "Panel Renfe Cercanías",
      show_explorer: config.show_explorer !== false,
      show_gtfs: config.show_gtfs !== false,
      show_journeys: config.show_journeys !== false,
      ...config
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _getGtfsButtonState() {
    if (!this._hass) return null;
    for (const eid of Object.keys(this._hass.states)) {
      if (eid.startsWith("button.renfe_cercanias") && eid.includes("refresh_gtfs")) {
        return this._hass.states[eid];
      }
    }
    return null;
  }

  _getJourneys() {
    if (!this._hass) return [];
    const journeys = [];
    for (const eid of Object.keys(this._hass.states)) {
      if (eid.startsWith("sensor.renfe_cercanias") && !eid.includes("explorador")) {
        journeys.push(this._hass.states[eid]);
      }
    }
    return journeys;
  }

  _getExplorerState() {
    if (!this._hass) return null;
    return this._hass.states["sensor.renfe_cercanias_explorador"] || null;
  }

  async _handleRefreshGtfs() {
    if (!this._hass || this._isRefreshingGtfs) return;
    this._isRefreshingGtfs = true;
    this._render();

    try {
      await this._hass.callService("renfe_cercanias", "refresh_gtfs", {});
    } catch (err) {
      console.error("Error al refrescar GTFS:", err);
    } finally {
      this._isRefreshingGtfs = false;
      this._render();
    }
  }

  async _handleSearchExplore() {
    if (!this._hass) return;
    const queryInput = this.shadowRoot.getElementById("explore-query");
    const lineSelect = this.shadowRoot.getElementById("explore-line");
    const query = queryInput ? queryInput.value.trim() : "";
    const line = lineSelect ? lineSelect.value : "";

    if (!query) return;

    this._isSearching = true;
    this._searchQuery = query;
    this._selectedLine = line;
    this._render();

    try {
      await this._hass.callService("renfe_cercanias", "explore", {
        query: query,
        line: line || undefined,
        n_trains: 5
      });
    } catch (err) {
      console.error("Error en explorador:", err);
    } finally {
      this._isSearching = false;
      this._render();
    }
  }

  async _handleClearExplore() {
    if (!this._hass) return;
    this._searchQuery = "";
    this._selectedLine = "";
    try {
      await this._hass.callService("renfe_cercanias", "clear_explorer", {});
    } catch (err) {
      console.error("Error limpiando explorador:", err);
    }
    this._render();
  }

  _render() {
    if (!this._hass) return;

    const gtfsBtn = this._getGtfsButtonState();
    const gtfsAttrs = gtfsBtn ? gtfsBtn.attributes : {};
    const journeys = this._getJourneys();
    const explorerState = this._getExplorerState();
    const expAttrs = explorerState ? explorerState.attributes : {};
    const explorerTrains = expAttrs.trains || [];
    const expStopName = expAttrs.stop_name || expAttrs.stop_id;

    const styles = `
      :host {
        display: block;
      }
      ha-card {
        padding: 18px;
        border-radius: var(--ha-card-border-radius, 16px);
        background: var(--ha-card-background, var(--card-background-color, #ffffff));
        box-shadow: var(--ha-card-box-shadow, 0 4px 12px rgba(0,0,0,0.06));
        color: var(--primary-text-color, #212121);
        font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif);
      }
      .card-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
        color: #6f2c91;
      }
      .section-box {
        background: var(--secondary-background-color, rgba(0,0,0,0.02));
        border: 1px solid var(--divider-color, rgba(0,0,0,0.08));
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 14px;
      }
      .section-header {
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 10px;
        margin-bottom: 12px;
      }
      .stat-card {
        background: var(--card-background-color, #fff);
        padding: 10px;
        border-radius: 8px;
        border: 1px solid rgba(0,0,0,0.05);
      }
      .stat-label {
        font-size: 0.75rem;
        color: var(--secondary-text-color, #757575);
      }
      .stat-value {
        font-size: 1.05rem;
        font-weight: 700;
        margin-top: 2px;
        color: var(--primary-text-color, #212121);
      }
      .btn {
        background: #6f2c91;
        color: white;
        border: none;
        padding: 9px 15px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.88rem;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        transition: opacity 0.2s;
      }
      .btn:hover {
        opacity: 0.9;
      }
      .btn-secondary {
        background: transparent;
        color: var(--primary-text-color, #333);
        border: 1px solid var(--divider-color, #ccc);
      }
      .btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .search-bar {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
        flex-wrap: wrap;
      }
      .search-bar input, .search-bar select {
        padding: 9px 12px;
        border-radius: 8px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff);
        color: inherit;
        font-size: 0.9rem;
      }
      .search-bar input {
        flex: 1;
        min-width: 140px;
      }
      .journey-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 10px;
        background: var(--card-background-color, #fff);
        border-radius: 8px;
        margin-bottom: 6px;
        border: 1px solid rgba(0,0,0,0.04);
      }
      .journey-name {
        font-weight: 600;
        font-size: 0.9rem;
      }
      .journey-desc {
        font-size: 0.78rem;
        color: var(--secondary-text-color, #757575);
      }
      .train-mini-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 0;
        border-bottom: 1px dashed var(--divider-color, rgba(0,0,0,0.08));
        font-size: 0.85rem;
      }
      .train-mini-row:last-child {
        border-bottom: none;
      }
    `;

    const stopsCount = gtfsAttrs.gtfs_stops_count || "200+";
    const dbSize = formatBytes(gtfsAttrs.gtfs_db_size_bytes);
    const cacheAge = formatAge(gtfsAttrs.gtfs_age_seconds);
    const isUsable = gtfsAttrs.gtfs_usable !== false;

    this.shadowRoot.innerHTML = `
      <style>${styles}</style>
      <ha-card>
        <div class="card-title">
          <svg style="width:24px;height:24px;fill:currentColor" viewBox="0 0 24 24">
            <path d="M12,2C8,2 4,2.5 4,6V15.5A3.5,3.5 0 0,0 7.5,19L6,20.5V21H18V20.5L16.5,19A3.5,3.5 0 0,0 20,15.5V6C20,2.5 16.42,2 12,2M12,4C17,4 18,4.5 18,6V10H6V6C6,4.5 7,4 12,4M6,12H18V15.5A1.5,1.5 0 0,1 16.5,17H7.5A1.5,1.5 0 0,1 6,15.5V12M8.5,13A1.5,1.5 0 0,0 7,14.5A1.5,1.5 0 0,0 8.5,16A1.5,1.5 0 0,0 10,14.5A1.5,1.5 0 0,0 8.5,13M15.5,13A1.5,1.5 0 0,0 14,14.5A1.5,1.5 0 0,0 15.5,16A1.5,1.5 0 0,0 17,14.5A1.5,1.5 0 0,0 15.5,13Z"/>
          </svg>
          <span>${this._config.title}</span>
        </div>

        ${this._config.show_gtfs ? `
          <div class="section-box">
            <div class="section-header">
              <span>Estado de la base de datos GTFS Renfe</span>
              <span style="color: ${isUsable ? '#2e7d32' : '#c62828'}; font-size: 0.8rem; font-weight: bold;">
                ${isUsable ? '● Operativa' : '● Requiere descarga'}
              </span>
            </div>
            <div class="stats-grid">
              <div class="stat-card">
                <div class="stat-label">Estaciones</div>
                <div class="stat-value">${stopsCount}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Tamaño SQLite</div>
                <div class="stat-value">${dbSize}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Antigüedad</div>
                <div class="stat-value">${cacheAge}</div>
              </div>
            </div>
            <button id="btn-refresh-gtfs" class="btn" ${this._isRefreshingGtfs ? 'disabled' : ''}>
              ${this._isRefreshingGtfs ? 'Descargando y compilando base de datos...' : 'Refrescar base GTFS ahora'}
            </button>
          </div>
        ` : ''}

        ${this._config.show_explorer ? `
          <div class="section-box">
            <div class="section-header">
              <span>Explorador Rápido de Estaciones</span>
            </div>
            <div class="search-bar">
              <input type="text" id="explore-query" placeholder="Ej: Atocha, Sol, Chamartín..." value="${this._searchQuery}">
              <select id="explore-line">
                <option value="">Línea (todas)</option>
                <option value="C1">C1</option>
                <option value="C2">C2</option>
                <option value="C3">C3</option>
                <option value="C4">C4</option>
                <option value="C5">C5</option>
                <option value="C7">C7</option>
                <option value="C8">C8</option>
                <option value="C10">C10</option>
              </select>
              <button id="btn-search-explore" class="btn" ${this._isSearching ? 'disabled' : ''}>
                ${this._isSearching ? 'Buscando...' : 'Consultar'}
              </button>
              ${this._searchQuery ? `<button id="btn-clear-explore" class="btn btn-secondary">Limpiar</button>` : ''}
            </div>

            ${expStopName ? `
              <div style="background:var(--card-background-color,#fff);border-radius:8px;padding:12px;margin-top:8px;">
                <div style="font-weight:700;font-size:0.95rem;margin-bottom:8px;color:#6f2c91;">
                  Estación: ${expStopName}
                </div>
                ${explorerTrains.length > 0 ? `
                  <div style="display:flex;flex-direction:column;">
                    ${explorerTrains.map(t => `
                      <div class="train-mini-row">
                        <div><strong>${t.line}</strong> ➜ ${t.headsign}</div>
                        <div><strong>${t.departure}</strong> (${Math.round(t.minutes)} min ${t.delay_min > 0 ? `+${Math.round(t.delay_min)}m` : ''})</div>
                      </div>
                    `).join('')}
                  </div>
                ` : `<div style="font-size:0.85rem;color:#757575;">No hay próximas salidas para esta búsqueda.</div>`}
              </div>
            ` : ''}
          </div>
        ` : ''}

        ${this._config.show_journeys ? `
          <div class="section-box" style="margin-bottom:0;">
            <div class="section-header">
              <span>Tus Trayectos Configurados (${journeys.length})</span>
            </div>
            ${journeys.length > 0 ? journeys.map(j => {
              const a = j.attributes;
              const nextTime = a.next_departure ? `${a.next_departure} (en ${Math.round(a.trains?.[0]?.minutes || 0)}m)` : "Sin trenes";
              return `
                <div class="journey-item">
                  <div>
                    <div class="journey-name">${a.journey_name || j.entity_id}</div>
                    <div class="journey-desc">${a.stop_name || a.stop_id} ${a.destination_name ? `➜ ${a.destination_name}` : ''} ${a.line_filter ? `(${a.line_filter})` : ''}</div>
                  </div>
                  <div style="text-align:right;">
                    <div style="font-weight:700;font-size:0.85rem;color:#6f2c91;">${nextTime}</div>
                    <div style="font-size:0.75rem;color:${a.is_active ? '#2e7d32' : '#757575'};">${a.is_active ? 'Activo' : 'Fuera de hora'}</div>
                  </div>
                </div>
              `;
            }).join('') : '<div style="font-size:0.85rem;color:#757575;">No tienes trayectos configurados todavía. Puedes añadir uno desde Ajustes > Dispositivos y Servicios.</div>'}
          </div>
        ` : ''}
      </ha-card>
    `;

    const refreshBtn = this.shadowRoot.getElementById("btn-refresh-gtfs");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => this._handleRefreshGtfs());
    }

    const searchBtn = this.shadowRoot.getElementById("btn-search-explore");
    if (searchBtn) {
      searchBtn.addEventListener("click", () => this._handleSearchExplore());
    }

    const clearBtn = this.shadowRoot.getElementById("btn-clear-explore");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => this._handleClearExplore());
    }

    const queryInput = this.shadowRoot.getElementById("explore-query");
    if (queryInput) {
      queryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") this._handleSearchExplore();
      });
    }
  }

  static getConfigElement() {
    return document.createElement("renfe-cercanias-config-card-editor");
  }

  static getStubConfig() {
    return {
      title: "Panel de Gestión Renfe Cercanías",
      show_gtfs: true,
      show_explorer: true,
      show_journeys: true
    };
  }
}

class RenfeCercaniasConfigCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
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
        input[type="text"] {
          padding: 8px 10px;
          border-radius: 6px;
          border: 1px solid var(--divider-color, #ccc);
          background: var(--card-background-color, #fff);
          color: inherit;
        }
        .checkbox-row {
          display: flex;
          align-items: center;
          gap: 8px;
        }
      </style>
      <div class="editor-container">
        <div class="form-row">
          <label>Título del panel:</label>
          <input type="text" id="title" value="${this._config.title || 'Panel Renfe Cercanías'}">
        </div>

        <div class="checkbox-row">
          <input type="checkbox" id="show_gtfs" ${this._config.show_gtfs !== false ? 'checked' : ''}>
          <label for="show_gtfs">Mostrar estado y refresco GTFS</label>
        </div>

        <div class="checkbox-row">
          <input type="checkbox" id="show_explorer" ${this._config.show_explorer !== false ? 'checked' : ''}>
          <label for="show_explorer">Mostrar explorador rápido de paradas</label>
        </div>

        <div class="checkbox-row">
          <input type="checkbox" id="show_journeys" ${this._config.show_journeys !== false ? 'checked' : ''}>
          <label for="show_journeys">Mostrar lista de trayectos configurados</label>
        </div>
      </div>
    `;

    this.shadowRoot.getElementById('title').addEventListener('input', (e) => this._valueChanged('title', e.target.value));
    this.shadowRoot.getElementById('show_gtfs').addEventListener('change', (e) => this._valueChanged('show_gtfs', e.target.checked));
    this.shadowRoot.getElementById('show_explorer').addEventListener('change', (e) => this._valueChanged('show_explorer', e.target.checked));
    this.shadowRoot.getElementById('show_journeys').addEventListener('change', (e) => this._valueChanged('show_journeys', e.target.checked));
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

customElements.define("renfe-cercanias-config-card", RenfeCercaniasConfigCard);
customElements.define("renfe-cercanias-config-card-editor", RenfeCercaniasConfigCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "renfe-cercanias-config-card",
  name: "Panel Renfe Cercanías",
  preview: true,
  description: "Panel de control para consultar y forzar refresco GTFS, explorar paradas en vivo y ver tus trayectos."
});
