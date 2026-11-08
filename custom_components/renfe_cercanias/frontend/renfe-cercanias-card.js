/**
 * Renfe Cercanías Card para Home Assistant
 * Tarjeta interactiva para trayectos con cuenta atrás y próximas salidas.
 */

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "renfe-cercanias-card")) {
  window.customCards.push({
    type: "renfe-cercanias-card",
    name: "Renfe Cercanías",
    preview: true,
    description: "Muestra el próximo tren y siguientes salidas de Cercanías Renfe con cuenta atrás y retrasos en tiempo real."
  });
}

const LINE_COLORS = {
  "C1": { bg: "#0099cd", text: "#ffffff" },
  "C2": { bg: "#00954c", text: "#ffffff" },
  "C3": { bg: "#8a4999", text: "#ffffff" },
  "C3a": { bg: "#8a4999", text: "#ffffff" },
  "C4": { bg: "#004b93", text: "#ffffff" },
  "C4a": { bg: "#004b93", text: "#ffffff" },
  "C4b": { bg: "#004b93", text: "#ffffff" },
  "C5": { bg: "#ffcc00", text: "#111111" },
  "C7": { bg: "#e4002b", text: "#ffffff" },
  "C8": { bg: "#757575", text: "#ffffff" },
  "C8a": { bg: "#757575", text: "#ffffff" },
  "C9": { bg: "#f39200", text: "#ffffff" },
  "C10": { bg: "#00a587", text: "#ffffff" },
  "DEFAULT": { bg: "#6f2c91", text: "#ffffff" }
};

function getLineBadgeStyle(lineName) {
  const line = (lineName || "").trim().toUpperCase();
  const theme = LINE_COLORS[line] || LINE_COLORS.DEFAULT;
  return `background-color: ${theme.bg}; color: ${theme.text};`;
}

class RenfeCercaniasCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    this._config = {
      entity: config.entity || "",
      name: config.name || "",
      show_next_only: config.show_next_only === true,
      max_trains: config.max_trains || 5,
      ...config
    };
    this._render();
  }

  set hass(hass) {
    const oldState = this._hass?.states?.[this._config?.entity];
    const newState = hass?.states?.[this._config?.entity];
    this._hass = hass;

    if (oldState !== newState || !this.shadowRoot.innerHTML) {
      this._render();
    }
  }

  getCardSize() {
    return 3;
  }

  _render() {
    if (!this._config || !this._hass) return;

    if (!this._config.entity) {
      this.shadowRoot.innerHTML = `
        <ha-card style="padding: 16px; text-align: center; color: var(--secondary-text-color, #757575);">
          <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 6px; color: var(--primary-text-color, #212121);">Renfe Cercanías</div>
          <div style="font-size: 0.9rem;">Por favor, selecciona una entidad de sensor de Renfe Cercanías en el editor.</div>
        </ha-card>
      `;
      return;
    }

    const stateObj = this._hass.states[this._config.entity];
    if (!stateObj) {
      this.shadowRoot.innerHTML = `
        <ha-card style="padding: 16px; text-align: center; color: var(--secondary-text-color, #757575);">
          <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 6px; color: var(--primary-text-color, #212121);">${this._config.name || "Renfe Cercanías"}</div>
          <div style="font-size: 0.9rem;">Esperando datos de la entidad <code>${this._config.entity}</code>...</div>
        </ha-card>
      `;
      return;
    }

    const attrs = stateObj.attributes || {};
    const title = this._config.name || attrs.journey_name || "Renfe Cercanías";
    const stopName = attrs.stop_name || attrs.stop_id || "Estación";
    const destName = attrs.destination_name || null;
    const lineFilter = attrs.line_filter && attrs.line_filter !== "todas" ? attrs.line_filter : null;
    const isActive = attrs.is_active !== false;
    const trains = attrs.trains || [];
    const trainsCount = attrs.trains_count !== undefined ? attrs.trains_count : trains.length;
    const updatedAt = attrs.updated_at || "";
    const activeWindow = attrs.active_window || "";
    const activeTrainsOnLine = attrs.active_trains_on_line || 0;

    let countdownMinutes = null;
    let nextTrain = null;

    if (trains && trains.length > 0) {
      nextTrain = trains[0];
      countdownMinutes = nextTrain.minutes;
    } else if (stateObj && stateObj.state && !isNaN(parseFloat(stateObj.state))) {
      countdownMinutes = parseFloat(stateObj.state);
    }

    const styles = `
      :host {
        display: block;
      }
      ha-card {
        padding: 16px;
        background: var(--ha-card-background, var(--card-background-color, #ffffff));
        border-radius: var(--ha-card-border-radius, 16px);
        box-shadow: var(--ha-card-box-shadow, 0 4px 12px rgba(0,0,0,0.06));
        color: var(--primary-text-color, #212121);
        font-family: var(--paper-font-body1_-_font-family, system-ui, -apple-system, sans-serif);
        overflow: hidden;
        position: relative;
      }
      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 14px;
        border-bottom: 1px solid var(--divider-color, rgba(0,0,0,0.08));
        padding-bottom: 10px;
      }
      .header-title-group {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .renfe-icon {
        width: 34px;
        height: 34px;
        border-radius: 8px;
        background: #6f2c91;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
      }
      .renfe-icon svg {
        width: 20px;
        height: 20px;
        fill: currentColor;
      }
      .header-text h2 {
        font-size: 1.15rem;
        font-weight: 600;
        margin: 0;
        line-height: 1.2;
      }
      .station-sub {
        font-size: 0.82rem;
        color: var(--secondary-text-color, #757575);
        display: flex;
        align-items: center;
        gap: 4px;
        margin-top: 2px;
      }
      .line-pill {
        display: inline-block;
        padding: 2px 7px;
        font-size: 0.75rem;
        font-weight: bold;
        border-radius: 6px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .inactive-banner {
        background: var(--warning-color, #ff9800);
        color: #fff;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 0.85rem;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
      }
      .hero-countdown {
        background: var(--secondary-background-color, rgba(111, 44, 145, 0.05));
        border: 1px solid rgba(111, 44, 145, 0.15);
        border-radius: 14px;
        padding: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
      }
      .hero-left {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .hero-time-big {
        font-size: 2.3rem;
        font-weight: 800;
        line-height: 1;
        color: var(--primary-color, #6f2c91);
        display: flex;
        align-items: baseline;
        gap: 4px;
      }
      .hero-unit {
        font-size: 1rem;
        font-weight: 600;
        color: var(--secondary-text-color, #757575);
      }
      .hero-subhead {
        font-size: 0.88rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .hero-right {
        text-align: right;
      }
      .dep-clock {
        font-size: 1.3rem;
        font-weight: 700;
      }
      .delay-tag {
        font-size: 0.78rem;
        padding: 2px 8px;
        border-radius: 10px;
        font-weight: 600;
        display: inline-block;
        margin-top: 4px;
      }
      .delay-ontime {
        background: rgba(76, 175, 80, 0.15);
        color: #2e7d32;
      }
      .delay-late {
        background: rgba(244, 67, 54, 0.15);
        color: #d32f2f;
      }
      .delay-early {
        background: rgba(33, 150, 243, 0.15);
        color: #1976d2;
      }
      .train-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .train-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 10px;
        background: var(--table-row-background-color, rgba(0,0,0,0.02));
        border-radius: 8px;
        transition: background 0.2s ease;
      }
      .train-row:hover {
        background: rgba(0,0,0,0.04);
      }
      .train-row-left {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .train-dest-info {
        display: flex;
        flex-direction: column;
      }
      .train-dest-title {
        font-size: 0.9rem;
        font-weight: 600;
      }
      .train-sched-sub {
        font-size: 0.76rem;
        color: var(--secondary-text-color, #757575);
      }
      .train-row-right {
        text-align: right;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
      }
      .train-eta-badge {
        font-size: 0.88rem;
        font-weight: 700;
        color: var(--primary-color, #6f2c91);
      }
      .card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 14px;
        padding-top: 10px;
        border-top: 1px solid var(--divider-color, rgba(0,0,0,0.06));
        font-size: 0.74rem;
        color: var(--secondary-text-color, #8e8e8e);
      }
      .pulse-dot {
        width: 8px;
        height: 8px;
        background: #4caf50;
        border-radius: 50%;
        display: inline-block;
        margin-right: 4px;
        box-shadow: 0 0 0 rgba(76, 175, 80, 0.4);
        animation: pulse 2s infinite;
      }
      @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
        70% { box-shadow: 0 0 0 6px rgba(76, 175, 80, 0); }
        100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
      }
      .empty-state {
        padding: 24px 12px;
        text-align: center;
        color: var(--secondary-text-color, #757575);
      }
      .empty-state svg {
        width: 48px;
        height: 48px;
        opacity: 0.4;
        margin-bottom: 8px;
      }
    `;

    let contentHtml = "";

    if (!isActive) {
      contentHtml += `
        <div class="inactive-banner">
          <svg style="width:20px;height:20px;fill:currentColor" viewBox="0 0 24 24">
            <path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4M12,6A1,1 0 0,0 11,7V12.41L14.71,16.12L16.12,14.71L13,11.59V7A1,1 0 0,0 12,6Z"/>
          </svg>
          <div><strong>Fuera de horario activo</strong> (${activeWindow || 'Horario programado'})</div>
        </div>
      `;
    }

    if (trains.length === 0) {
      contentHtml += `
        <div class="empty-state">
          <svg viewBox="0 0 24 24"><path fill="currentColor" d="M12,2C8,2 4,2.5 4,6V15.5A3.5,3.5 0 0,0 7.5,19L6,20.5V21H18V20.5L16.5,19A3.5,3.5 0 0,0 20,15.5V6C20,2.5 16.42,2 12,2M12,4C17,4 18,4.5 18,6V10H6V6C6,4.5 7,4 12,4M6,12H18V15.5A1.5,1.5 0 0,1 16.5,17H7.5A1.5,1.5 0 0,1 6,15.5V12M8.5,13A1.5,1.5 0 0,0 7,14.5A1.5,1.5 0 0,0 8.5,16A1.5,1.5 0 0,0 10,14.5A1.5,1.5 0 0,0 8.5,13M15.5,13A1.5,1.5 0 0,0 14,14.5A1.5,1.5 0 0,0 15.5,16A1.5,1.5 0 0,0 17,14.5A1.5,1.5 0 0,0 15.5,13Z"/></svg>
          <div>No hay trenes próximos programados o en circulación en este momento.</div>
        </div>
      `;
    } else {
      // Hero next train
      const delay = nextTrain.delay_min || 0;
      let delayTag = `<span class="delay-tag delay-ontime">En hora</span>`;
      if (delay > 0) {
        delayTag = `<span class="delay-tag delay-late">+${Math.round(delay)} min</span>`;
      } else if (delay < 0) {
        delayTag = `<span class="delay-tag delay-early">${Math.round(delay)} min</span>`;
      }

      const countdownText = countdownMinutes <= 0.8
        ? "¡YA!"
        : Math.round(countdownMinutes);

      const countdownUnit = countdownMinutes <= 0.8 ? "" : "min";

      contentHtml += `
        <div class="hero-countdown">
          <div class="hero-left">
            <div class="hero-time-big">
              ${countdownText} <span class="hero-unit">${countdownUnit}</span>
            </div>
            <div class="hero-subhead">
              <span class="line-pill" style="${getLineBadgeStyle(nextTrain.line)}">${nextTrain.line || 'C'}</span>
              <span>${nextTrain.headsign || 'Destino'}</span>
            </div>
          </div>
          <div class="hero-right">
            <div class="dep-clock">${nextTrain.departure || '--:--'}</div>
            ${delayTag}
          </div>
        </div>
      `;

      // Siguientes salidas
      if (!this._config.show_next_only && trains.length > 1) {
        const nextList = trains.slice(1, this._config.max_trains);
        contentHtml += `<div class="train-list">`;
        for (const t of nextList) {
          const tDelay = t.delay_min || 0;
          let delayPill = "";
          if (tDelay > 0) {
            delayPill = `<span style="color:#d32f2f;font-size:0.75rem;">(+${Math.round(tDelay)}m)</span>`;
          }

          contentHtml += `
            <div class="train-row">
              <div class="train-row-left">
                <span class="line-pill" style="${getLineBadgeStyle(t.line)}">${t.line || 'C'}</span>
                <div class="train-dest-info">
                  <div class="train-dest-title">${t.headsign || 'Destino'}</div>
                  <div class="train-sched-sub">Previsto ${t.scheduled || t.departure} ${delayPill}</div>
                </div>
              </div>
              <div class="train-row-right">
                <div class="train-eta-badge">${t.departure}</div>
                <div style="font-size:0.75rem;color:var(--secondary-text-color,#757575);">en ${Math.round(t.minutes)} min</div>
              </div>
            </div>
          `;
        }
        contentHtml += `</div>`;
      }
    }

    const stationLabel = destName
      ? `${stopName} ➜ ${destName}`
      : stopName;

    this.shadowRoot.innerHTML = `
      <style>${styles}</style>
      <ha-card>
        <div class="card-header">
          <div class="header-title-group">
            <div class="renfe-icon">
              <svg viewBox="0 0 24 24">
                <path d="M12,2C8,2 4,2.5 4,6V15.5A3.5,3.5 0 0,0 7.5,19L6,20.5V21H18V20.5L16.5,19A3.5,3.5 0 0,0 20,15.5V6C20,2.5 16.42,2 12,2M12,4C17,4 18,4.5 18,6V10H6V6C6,4.5 7,4 12,4M6,12H18V15.5A1.5,1.5 0 0,1 16.5,17H7.5A1.5,1.5 0 0,1 6,15.5V12M8.5,13A1.5,1.5 0 0,0 7,14.5A1.5,1.5 0 0,0 8.5,16A1.5,1.5 0 0,0 10,14.5A1.5,1.5 0 0,0 8.5,13M15.5,13A1.5,1.5 0 0,0 14,14.5A1.5,1.5 0 0,0 15.5,16A1.5,1.5 0 0,0 17,14.5A1.5,1.5 0 0,0 15.5,13Z"/>
              </svg>
            </div>
            <div class="header-text">
              <h2>${title}</h2>
              <div class="station-sub">
                ${lineFilter ? `<span class="line-pill" style="${getLineBadgeStyle(lineFilter)}">${lineFilter}</span>` : ""}
                <span>${stationLabel}</span>
              </div>
            </div>
          </div>
        </div>

        ${contentHtml}

        <div class="card-footer">
          <div><span class="pulse-dot"></span>En directo Renfe RT</div>
          <div>${updatedAt ? `Act. ${updatedAt}` : ''} ${activeTrainsOnLine > 0 ? `· ${activeTrainsOnLine} trenes en línea` : ''}</div>
        </div>
      </ha-card>
    `;
  }

  static getConfigElement() {
    return document.createElement("renfe-cercanias-card-editor");
  }

  static getStubConfig(hass, entities) {
    const renfeSensors = entities.filter(e => e.startsWith("sensor.") && (e.includes("cercanias") || e.includes("renfe")));
    return {
      entity: renfeSensors.length > 0 ? renfeSensors[0] : "",
      name: "",
      show_next_only: false,
      max_trains: 4
    };
  }
}

class RenfeCercaniasCardEditor extends HTMLElement {
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
      (eid) => eid.startsWith("sensor.") && (eid.includes("cercanias") || eid.includes("renfe"))
    );

    this.shadowRoot.innerHTML = `
      <style>
        .editor-container {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 8px 0;
          font-family: inherit;
        }
        .form-row {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        label {
          font-weight: 500;
          font-size: 0.9rem;
          color: var(--primary-text-color, #212121);
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
          <label>Entidad del Trayecto:</label>
          <select id="entity">
            <option value="">-- Selecciona un sensor --</option>
            ${entities.map(e => `<option value="${e}" ${this._config.entity === e ? 'selected' : ''}>${this._hass.states[e].attributes.friendly_name || e}</option>`).join('')}
          </select>
        </div>

        <div class="form-row">
          <label>Título personalizado (opcional):</label>
          <input type="text" id="name" value="${this._config.name || ''}" placeholder="Dejar vacío para nombre por defecto">
        </div>

        <div class="form-row">
          <label>Máximo de trenes a mostrar:</label>
          <input type="number" id="max_trains" min="1" max="10" value="${this._config.max_trains || 4}">
        </div>

        <div class="checkbox-row">
          <input type="checkbox" id="show_next_only" ${this._config.show_next_only ? 'checked' : ''}>
          <label for="show_next_only">Mostrar únicamente el próximo tren</label>
        </div>
      </div>
    `;

    this.shadowRoot.getElementById('entity').addEventListener('change', (e) => this._valueChanged('entity', e.target.value));
    this.shadowRoot.getElementById('name').addEventListener('input', (e) => this._valueChanged('name', e.target.value));
    this.shadowRoot.getElementById('max_trains').addEventListener('change', (e) => this._valueChanged('max_trains', parseInt(e.target.value, 10)));
    this.shadowRoot.getElementById('show_next_only').addEventListener('change', (e) => this._valueChanged('show_next_only', e.target.checked));
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

if (!customElements.get("renfe-cercanias-card")) {
  customElements.define("renfe-cercanias-card", RenfeCercaniasCard);
}
if (!customElements.get("renfe-cercanias-card-editor")) {
  customElements.define("renfe-cercanias-card-editor", RenfeCercaniasCardEditor);
}
