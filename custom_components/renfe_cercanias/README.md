# 🚆 Renfe Cercanías Madrid para Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![version](https://img.shields.io/badge/version-1.2.0-blue.svg)](manifest.json)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-brightgreen.svg)](https://www.home-assistant.io/)

Integración personalizada para **Home Assistant** que monitoriza en **tiempo real** los trenes de **Renfe Cercanías Madrid**.

Combina el catálogo oficial de horarios estáticos GTFS con los feeds en tiempo real (**GTFS-RT: retrasos y posiciones**) ofrecidos por el portal de datos abiertos de Renfe.

---

## 🌟 Características Principales

* ⚡ **Minutos en Tiempo Real:** El estado principal del sensor muestra los minutos restantes exactos hasta la salida del próximo tren, calculando automáticamente los retrasos reportados por Renfe.
* 🎯 **Filtro de Destino (Dirección):** Evita mezclar trenes que van en direcciones opuestas en la misma estación (por ejemplo, en Atocha puedes filtrar solo trenes hacia *Móstoles* o hacia *Guadalajara*).
* 🛤️ **Filtro por Línea:** Permite monitorizar una línea específica (`C1`, `C2`, `C3`, `C4`, `C5`, `C7`, `C8`, `C10`) o todas las que pasen por la estación.
* 🕒 **Ventanas Horarias Activas:** Puedes configurar horas activas (ej. `07:30` - `09:30`) para no consultar ni saturar los sensores fuera de tus horas habituales de desplazamiento.
* 🔄 **Soporte Multi-trayecto:** Configura tantos trayectos como necesites (Ida al trabajo, Vuelta a casa, trayecto de fin de semana).
* 🧭 **Modo Explorador Temporal:** Consulta las próximas salidas de cualquier estación al vuelo mediante un servicio, sin necesidad de crear un sensor fijo permanente.
* 🎛️ **Totalmente Configurable desde la Interfaz:** Asistente paso a paso (Config Flow) y edición posterior (Options Flow) con buscador predictivo de estaciones y selector de destinos.
* 🚀 **Alto Rendimiento y Cero Bloqueos:** Base de datos SQLite local indexada con descargas automáticas periódicas del GTFS estático sin bloquear el hilo principal de Home Assistant.

---

## 📦 Instalación

### Método 1: Manual
1. Copia la carpeta `renfe_cercanias` dentro del directorio `custom_components/` de tu instalación de Home Assistant:
   ```text
   config/
   └── custom_components/
       └── renfe_cercanias/
           ├── __init__.py
           ├── manifest.json
           ├── sensor.py
           └── ...
   ```
2. Reinicia Home Assistant.

### Método 2: HACS (como repositorio personalizado)
1. En Home Assistant, abre **HACS** > **Integraciones**.
2. Pulsa en los tres puntos superiores > **Repositorios personalizados**.
3. Añade la URL de este repositorio con la categoría **Integración**.
4. Pulsa **Descargar** y reinicia Home Assistant.

---

## ⚙️ Configuración

### Configuración desde la Interfaz Web (Recomendado)

1. En Home Assistant, ve a **Ajustes** > **Dispositivos y servicios**.
2. Pulsa en **Añadir integración** y busca **Renfe Cercanías Madrid**.
3. El asistente te guiará en 4 sencillos pasos:
   * **Paso 1 - Parámetros:** Nombre del trayecto (ej. *Trabajo C5*), filtro de línea opcional, número de salidas a mostrar (1-5) y ventana horaria opcional (`HH:MM`).
   * **Paso 2 - Búsqueda de Origen:** Escribe el nombre de la estación (ej. *Atocha*, *Sol*, *Alcorcón*) o su ID exacto.
   * **Paso 3 - Selección de Estación:** Elige la estación de la lista de coincidencias.
   * **Paso 4 - Selección de Destino (Dirección):** Selecciona hacia qué estación te diriges para filtrar únicamente los trenes en esa dirección (o elige *Cualquier destino* si te sirven todos).
   * **Paso 5 - Previsualización:** Revisa las próximas salidas reales calculadas antes de confirmar la creación.

> [!TIP]
> **Modificar un trayecto creado:** En cualquier momento puedes pulsar en **Configurar** sobre la tarjeta de la integración para cambiar la línea, horarios, estación de origen o destino sin tener que recrear el sensor.

---

### Configuración por `configuration.yaml` (Opcional)

Si prefieres declarar tus trayectos en YAML, puedes añadirlos a `configuration.yaml`:

```yaml
renfe_cercanias:
  - journey_name: "Alcorcón a Atocha"
    stop_id: "18002"            # ID estación Alcorcón
    destination_id: "18000"     # ID estación Atocha
    line: "C5"
    n_trains: 3
    active_from: "07:00"
    active_to: "09:30"

  - journey_name: "Sol a Chamartín"
    stop_id: "98305"            # Sol
    destination_id: "17000"     # Chamartín
    line: "C4"
    n_trains: 3
```

---

## 📊 Entidades y Atributos

Al configurar un trayecto se generan las siguientes entidades:

### 1. Sensor del Trayecto (`sensor.<nombre_del_trayecto>`)
* **Estado:** Minutos restantes hasta la salida del próximo tren (`min`). Si está en la estación o saliendo inmediatamente, el valor es `0.0`. Fuera de la ventana horaria su estado es `unknown`.
* **Icono dinámico:** 
  * `mdi:train` (Tren en hora).
  * `mdi:train-alert` (Retraso superior a 3 minutos).
  * `mdi:clock-time-four-outline` (Fuera de la ventana horaria activa).

#### Atributos principales disponibles:
| Atributo | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `next_train_summary` | `string` | Resumen listo para mostrar en tarjetas | `C5 a Humanes en 6 min (18:24) · En hora` |
| `next_departure` | `string` | Hora calculada de salida (`HH:MM`) | `18:24` |
| `next_departure_time`| `ISO datetime` | Timestamp completo para countdown | `2026-11-04T18:24:00+01:00` |
| `next_line` | `string` | Línea del próximo tren | `C5` |
| `next_headsign` | `string` | Destino que marca la cabecera del tren | `Humanes` |
| `next_delay_min` | `float` | Retraso en minutos (0 si va puntual) | `2.5` |
| `next_delay_text` | `string` | Texto formateado del retraso | `+2.5 min` o `En hora` |
| `second_departure` | `string` | Hora de salida del segundo tren | `18:34` |
| `second_line` | `string` | Línea del segundo tren | `C5` |
| `second_headsign` | `string` | Destino del segundo tren | `Fuenlabrada` |
| `second_minutes` | `float` | Minutos hasta el segundo tren | `16.0` |
| `destination_name`| `string` | Nombre de la estación de destino filtrada | `Madrid Atocha Cercanías` |
| `trains` | `list[dict]`| Lista con los próximos $N$ trenes detallados | `[{line, headsign, departure, minutes, delay_min}, ...]` |
| `active_trains_on_line`| `int` | Número de trenes en circulación en la línea | `14` |
| `is_active` | `bool` | Indica si está dentro de la ventana horaria | `true` |

---

### 2. Botón de Mantenimiento (`button.<nombre_del_trayecto>_refrescar_gtfs`)
Permite forzar la descarga manual del archivo GTFS estático de Renfe y reconstruir la base de datos local SQLite si Renfe ha publicado cambios recientes de horarios.

---

### 3. Sensor Explorador (`sensor.renfe_cercanias_explorador`)
Sensor compartido para búsquedas puntuales activado a través del servicio `renfe_cercanias.explore`.

---

## 🛠️ Servicios Disponibles

### `renfe_cercanias.explore`
Realiza una búsqueda temporal sin crear sensores adicionales. Actualiza `sensor.renfe_cercanias_explorador`:

```yaml
action: renfe_cercanias.explore
data:
  query: "Nuevos Ministerios"
  destination_id: "17000" # Opcional: destino Chamartín
  line: "C4"              # Opcional
  n_trains: 5
```

### `renfe_cercanias.clear_explorer`
Limpia los datos del sensor explorador.

```yaml
action: renfe_cercanias.clear_explorer
```

### `renfe_cercanias.refresh_gtfs`
Fuerza la descarga inmediata del paquete GTFS de Renfe para actualizar las tablas de estaciones y servicios.

```yaml
action: renfe_cercanias.refresh_gtfs
```

---

## 📱 Ejemplos de Tarjetas para el Dashboard

### 1. Tarjeta Markdown con las Próximas Salidas
Muestra de forma compacta y elegante los próximos trenes con sus retrasos en tiempo real:

```yaml
type: markdown
title: 🚆 Próximos Cercanías
content: >
  {% set s = 'sensor.alcorcon_a_atocha' %}
  **Estación:** {{ state_attr(s, 'stop_name') }} → {{ state_attr(s, 'destination_name') or 'Todos' }}
  
  **Próximo tren:** {{ state_attr(s, 'next_train_summary') or 'Sin trenes' }}

  ---
  {% for t in state_attr(s, 'trains') %}
  * **{{ t.departure }}** (en {{ t.minutes | round(0) }}m) · **{{ t.line }}** a {{ t.headsign }}
    {%- if t.delay_min > 0 %} <span style="color:orange;">(+{{ t.delay_min }}m)</span>{% endif %}
  {% else %}
  *No hay salidas programadas en las próximas horas.*
  {% endfor %}
```

---

### 2. Tarjeta Mushroom (Template Card)
```yaml
type: custom:mushroom-template-card
primary: >
  {{ state_attr('sensor.alcorcon_a_atocha', 'next_headsign') or 'Cercanías' }}
secondary: >
  {% if states('sensor.alcorcon_a_atocha') not in ['unknown', 'unavailable'] %}
    En {{ states('sensor.alcorcon_a_atocha') | round(0) }} min ({{ state_attr('sensor.alcorcon_a_atocha', 'next_departure') }}) · {{ state_attr('sensor.alcorcon_a_atocha', 'next_delay_text') }}
  {% else %}
    Sin servicio actualmente
  {% endif %}
icon: mdi:train
icon_color: >
  {% if state_attr('sensor.alcorcon_a_atocha', 'next_delay_min') | float(0) > 3 %}
    orange
  {% else %}
    red
  {% endif %}
badge_icon: >
  {% if state_attr('sensor.alcorcon_a_atocha', 'next_delay_min') | float(0) > 3 %}
    mdi:alert
  {% endif %}
badge_color: orange
```

---

## 🤖 Ejemplos de Automatizaciones

### Aviso por Telegram si el tren va con más de 5 minutos de retraso
```yaml
- id: alert_renfe_delay
  alias: "⚠️ Cercanías - Alerta de Retraso"
  trigger:
    - platform: numeric_state
      entity_id: sensor.alcorcon_a_atocha
      attribute: next_delay_min
      above: 5
  condition:
    - condition: time
      after: "07:00:00"
      before: "09:00:00"
  action:
    - service: script.notifications_central_hub
      data:
        notify_message: |
          ⚠️ **RETRASO EN CERCANÍAS**

          El tren de la línea {{ state_attr('sensor.alcorcon_a_atocha', 'next_line') }}
          con destino {{ state_attr('sensor.alcorcon_a_atocha', 'next_headsign') }}
          lleva un retraso de **{{ state_attr('sensor.alcorcon_a_atocha', 'next_delay_min') }} minutos**.

          ⏰ Nueva hora estimada: {{ state_attr('sensor.alcorcon_a_atocha', 'next_departure') }}
        priority: media
        notification_types:
          - telegram
          - home_assistant
        ha_title: "⚠️ Retraso Cercanías"
```

---

## ❓ Preguntas Frecuentes y Diagnóstico

### ¿Cada cuánto tiempo se actualizan los datos?
* **Retrasos y posiciones en tiempo real (GTFS-RT):** Se consultan cada **30 segundos** automáticamente.
* **Horarios y catálogo de paradas (GTFS estático):** Se almacena localmente en SQLite y se renueva automáticamente cada **7 días**. Puedes forzar una actualización cuando quieras pulsando el botón **Refrescar GTFS**.

### ¿Cómo sé si la base de datos GTFS está cargada?
Puedes consultar los atributos del botón `button.<nombre_del_trayecto>_refrescar_gtfs` en **Herramientas para desarrolladores** > **Estados**. Verás el número de estaciones (`gtfs_stops_count`), tamaño en disco y fecha de descarga.

---

## 📄 Licencia y Fuentes de Datos
* Datos provistos bajo licencia **CC BY 4.0** por **Renfe Operadora** y el **Ministerio de Transportes y Movilidad Sostenible**.
* Fuentes oficiales utilizadas:
  * Horarios estáticos: `https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip`
  * Retrasos en tiempo real: `https://gtfsrt.renfe.com/trip_updates.json`
  * Posiciones de vehículos: `https://gtfsrt.renfe.com/vehicle_positions.json`

