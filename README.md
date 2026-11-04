# 🚆 Renfe Cercanías Madrid para Home Assistant

<div align="center">

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge&logo=home-assistant)](https://github.com/hacs/default)
[![version](https://img.shields.io/badge/Versión-v1.2.0-blue.svg?style=for-the-badge&logo=git)](manifest.json)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-brightgreen.svg?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)
[![License](https://img.shields.io/badge/Licencia-MIT-green.svg?style=for-the-badge)](LICENSE)

[![Lines](https://img.shields.io/badge/Líneas-C1%20a%20C10%20Madrid-purple.svg?style=for-the-badge&logo=subway)](https://www.renfe.com)
[![GTFS RT](https://img.shields.io/badge/Datos-GTFS--RT%20Oficial%20Renfe-red.svg?style=for-the-badge&logo=live)](https://gtfsrt.renfe.com)
[![Cards](https://img.shields.io/badge/Lovelace%20Cards-3%20Tarjetas%20Incluidas-00a587.svg?style=for-the-badge&logo=material-design-icons)](#-tarjetas-lovelace-incluidas)

<p align="center">
  <strong>Monitorización en tiempo real, cuenta atrás exacta, mapa GPS en directo de trenes y panel de control para el núcleo de Renfe Cercanías Madrid en Home Assistant.</strong>
</p>

</div>

---

## 📑 Índice
1. [🌟 Novedades de la versión 1.2.0](#-novedades-de-la-versión-120)
2. [🎨 Tarjetas Lovelace Incluidas](#-tarjetas-lovelace-incluidas)
   * [1. renfe-cercanias-card (Trayectos)](#1-renfe-cercanias-card---tarjeta-de-trayecto)
   * [2. renfe-cercanias-map-card (Mapa GPS RT)](#2-renfe-cercanias-map-card---mapa-de-trenes-en-vivo)
   * [3. renfe-cercanias-config-card (Panel y Explorador)](#3-renfe-cercanias-config-card---panel-de-gestión-y-explorador)
3. [🚀 Características Principales](#-características-principales)
4. [📦 Instalación](#-instalación)
   * [Método 1: HACS (Recomendado)](#método-1-hacs-recomendado)
   * [Método 2: Manual](#método-2-manual)
5. [⚙️ Configuración de Trayectos](#️-configuración-de-trayectos)
   * [Desde la Interfaz Gráfica (UI)](#desde-la-interfaz-gráfica-ui---recomendado)
   * [Desde configuration.yaml](#desde-configurationyaml-opcional)
6. [📊 Entidades y Atributos](#-entidades-y-atributos)
7. [🛠️ Servicios Disponibles](#️-servicios-disponibles)
8. [🤖 Ejemplos de Automatizaciones](#-ejemplos-de-automatizaciones)
9. [❓ Preguntas Frecuentes](#-preguntas-frecuentes-y-diagnóstico)
10. [📄 Licencia y Fuentes](#-licencia-y-fuentes-de-datos)

---

## 🌟 Novedades de la versión 1.2.0

* 🎨 **3 Tarjetas Lovelace Nativas:** Ya no necesitas montar plantillas complejas; la integración incluye y registra automáticamente sus propias tarjetas visuales.
* 🗺️ **Mapa en Vivo con Posiciones GPS:** Visualización en tiempo real de los trenes en tránsito con velocidad en km/h, estado y color por línea.
* 🧭 **Panel de Control y Explorador Rápido:** Consulta salidas en cualquier estación al vuelo y revisa la base de datos GTFS desde una sola tarjeta.
* ⚡ **Integración Plug & Play con HACS:** Las tarjetas frontend se auto-inyectan en Home Assistant al arrancar el componente, sin tener que copiar archivos a `www` manualmente.
* 🎯 **Filtro de Destino Perfeccionado:** Búsqueda precisa de direcciones para evitar mezclar andenes opuestos.

---

## 🎨 Tarjetas Lovelace Incluidas

La integración inyecta automáticamente 3 tarjetas personalizadas que puedes usar directamente en cualquier panel de Lovelace:

### 1. `renfe-cercanias-card` - Tarjeta de Trayecto
Tarjeta principal con cuenta atrás destacada en minutos ("¡YA!", "4 min"), indicador de puntualidad o retraso en tiempo real (`En hora`, `+2 min`, etc.), distintivos de línea con los colores oficiales de Cercanías y listado de salidas posteriores.

<div align="center">

```
┌────────────────────────────────────────────────────────┐
│  (🚆) Mañana C5                 [C5] Atocha ➜ Móstoles │
├────────────────────────────────────────────────────────┤
│   3 min                        08:17                   │
│   [C5] Móstoles-El Soto        [+2 min]                │
├────────────────────────────────────────────────────────┤
│   [C5] Móstoles-El Soto        08:30 (en 16 min)       │
│   [C5] Fuenlabrada             08:42 (en 28 min)       │
├────────────────────────────────────────────────────────┤
│  🟢 En directo Renfe RT            Act. 08:14 · 12 trenes│
└────────────────────────────────────────────────────────┘
```

</div>

#### Configuración en Lovelace:
```yaml
type: custom:renfe-cercanias-card
entity: sensor.manana_c5
max_trains: 4
show_next_only: false
```
*Dispone de editor visual GUI integrado para configurar sin tocar código YAML.*

---

### 2. `renfe-cercanias-map-card` - Mapa de Trenes en Vivo
Mapa interactivo Leaflet que dibuja las posiciones GPS en tiempo real de todos los trenes del núcleo de Cercanías Madrid reportados por Renfe.

* **Iconos dinámicos:** Cada tren lleva el círculo distintivo con la letra y color de su línea (`C1`, `C2`, `C3`, `C4`, `C5`, `C7`, `C8`, `C10`).
* **Popups al pulsar:** Muestra velocidad instantánea (`km/h`), estado (`En trayecto` / `Detenido en parada`) e identificador de viaje.
* **Filtro por línea:** Permite ver toda la red o aislar una línea específica.

#### Configuración en Lovelace:
```yaml
type: custom:renfe-cercanias-map-card
entity: sensor.renfe_cercanias_explorador
height: 420
zoom: 11
line_filter: ""   # Deja vacío para ver todos o escribe "C5", "C3", etc.
```

---

### 3. `renfe-cercanias-config-card` - Panel de Gestión y Explorador
Panel multifuncional para tu dashboard de control:
* **Salud de la base de datos GTFS:** Muestra el número de estaciones indexadas, tamaño en disco y fecha de última descarga.
* **Botón de refresco manual:** Fuerza la actualización del catálogo de Renfe con 1 clic.
* **Explorador interactivo de estaciones:** Escribe cualquier estación (ej. *Sol*, *Atocha*, *Nuevos Ministerios*) y consulta salidas al vuelo sin crear un sensor fijo.
* **Gestor de trayectos:** Lista de todos tus trayectos configurados y su estado.

#### Configuración en Lovelace:
```yaml
type: custom:renfe-cercanias-config-card
title: "Panel Renfe Cercanías"
show_gtfs: true
show_explorer: true
show_journeys: true
```

---

## 🚀 Características Principales

* ⚡ **Cálculo Exacto en Tiempo Real:** Combina los horarios estáticos oficiales con los retrasos en directo de `trip_updates.json` cada 30 segundos.
* 🎯 **Filtro por Destino (Dirección):** Selecciona hacia qué estación viajas para que no aparezcan trenes en sentido contrario que pasen por el mismo andén o estación.
* 🕒 **Ventanas Horarias Inteligentes:** Configura horas activas (ej. `07:00` - `09:30`) para que el sensor solo esté activo cuando lo necesitas y no consuma recursos el resto del día.
* 🗃️ **Base de datos SQLite local:** Se descarga y compila de forma asíncrona en segundo plano sin ralentizar Home Assistant.
* 🧭 **Modo Explorador:** Consulta cualquier estación temporalmente mediante servicio o desde la tarjeta panel.

---

## 📦 Instalación

### Método 1: HACS (Recomendado)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MarioRubio&repository=ha-renfe-cercanias&category=integration)

1. Abre **HACS** en tu Home Assistant.
2. Pulsa en el menú de los tres puntos (arriba a la derecha) > **Repositorios personalizados**.
3. Añade la URL del repositorio:
   ```text
   https://github.com/MarioRubio/ha-renfe-cercanias
   ```
4. Selecciona la categoría **Integración** y pulsa **Añadir**.
5. Busca **Renfe Cercanías Madrid**, pulsa **Descargar** y reinicia Home Assistant.

### Método 2: Manual
1. Descarga el contenido del repositorio.
2. Copia la carpeta `custom_components/renfe_cercanias` dentro del directorio `config/custom_components/` de tu Home Assistant.
3. Reinicia Home Assistant.

---

## ⚙️ Configuración de Trayectos

### Desde la Interfaz Gráfica (UI) - Recomendado

1. En Home Assistant ve a **Ajustes** > **Dispositivos y servicios**.
2. Pulsa en **Añadir integración** y busca **Renfe Cercanías Madrid**.
3. El asistente te guiará paso a paso:
   * **1. Parámetros:** Nombre (ej. *Trabajo C5*), línea opcional, número de trenes y ventana horaria.
   * **2. Búsqueda de Origen:** Escribe el nombre o ID de tu estación (ej. *Atocha*, *Alcorcón*).
   * **3. Selección de Estación:** Elige la estación en la lista desplegable.
   * **4. Destino (Dirección):** Elige tu estación de destino para filtrar la dirección correcta del viaje.
   * **5. Previsualización en Vivo:** Comprueba las salidas calculadas en ese instante antes de guardar.

> [!TIP]
> Puedes pulsar en **Configurar** sobre cualquier trayecto ya creado para cambiar el destino, la estación o la línea sin tener que borrar el sensor.

---

### Desde `configuration.yaml` (Opcional)

Si prefieres declarar tus trayectos en código:

```yaml
renfe_cercanias:
  - journey_name: "Alcorcón a Atocha"
    stop_id: "18002"            # Estación origen Alcorcón
    destination_id: "18000"     # Estación destino Atocha
    line: "C5"
    n_trains: 4
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

Cada trayecto genera un sensor (`sensor.<nombre_del_trayecto>`):

| Atributo | Tipo | Descripción |
| :--- | :--- | :--- |
| `state` | `float` | Minutos restantes hasta la salida del próximo tren (`min`). |
| `next_departure` | `string` | Hora calculada de salida (`HH:MM`). |
| `next_line` | `string` | Línea del próximo tren (`C1` a `C10`). |
| `next_headsign` | `string` | Destino final del tren. |
| `next_delay_min` | `float` | Retraso en minutos (positivo si va retrasado, negativo si va adelantado). |
| `next_delay_text`| `string` | Texto descriptivo (`En hora`, `+3 min`). |
| `trains` | `list` | Lista de todos los próximos trenes con horario, línea, retraso y minutos. |
| `is_active` | `bool` | `true` si está dentro de la ventana horaria configurada. |
| `active_trains_on_line` | `int` | Número de trenes circulando en directo en esa línea. |

---

## 🛠️ Servicios Disponibles

### `renfe_cercanias.refresh_gtfs`
Fuerza la descarga del archivo GTFS estático oficial de Renfe y reconstruye la base de datos local SQLite.

### `renfe_cercanias.explore`
Permite consultar temporalmente cualquier estación o línea sin necesidad de crear un sensor fijo. El resultado se publica inmediatamente en `sensor.renfe_cercanias_explorador`.

```yaml
service: renfe_cercanias.explore
data:
  query: "Atocha"
  line: "C5"
  n_trains: 5
```

### `renfe_cercanias.clear_explorer`
Limpia la consulta temporal del explorador.

---

## 🤖 Ejemplos de Automatizaciones

### Aviso en Telegram si tu tren habitual va con retraso
```yaml
alias: "🚆 Cercanías - Aviso de Retraso"
trigger:
  - platform: numeric_state
    entity_id: sensor.alcorcon_a_atocha
    attribute: next_delay_min
    above: 4
condition:
  - condition: time
    after: "07:30:00"
    before: "09:00:00"
action:
  - service: notify.telegram_personal
    data:
      title: "⚠️ Retraso en Cercanías"
      message: >
        El tren {{ state_attr('sensor.alcorcon_a_atocha', 'next_line') }} hacia
        {{ state_attr('sensor.alcorcon_a_atocha', 'next_headsign') }}
        lleva un retraso de {{ state_attr('sensor.alcorcon_a_atocha', 'next_delay_min') }} minutos.
        Salida prevista: {{ state_attr('sensor.alcorcon_a_atocha', 'next_departure') }}.
```

---

## 🎨 Líneas y Colores Oficiales

| Línea | Color | Cabeceras Principales |
| :---: | :---: | :--- |
| **C1** | `Azul Cielo` (`#0099cd`) | Príncipe Pío - Atocha - Chamartín - Aeropuerto T4 |
| **C2** | `Verde` (`#00954c`) | Guadalajara - Alcalá de Henares - Atocha - Chamartín |
| **C3** | `Púrpura` (`#8a4999`) | Aranjuez - Atocha - Sol - Chamartín |
| **C4** | `Azul Marino` (`#004b93`) | Parla - Atocha - Sol - Chamartín - Alcobendas / Colmenar Viejo |
| **C5** | `Amarillo` (`#ffcc00`) | Móstoles El Soto - Atocha - Fuenlabrada - Humanes |
| **C7** | `Rojo` (`#e4002b`) | Alcalá de Henares - Atocha - Chamartín - Príncipe Pío |
| **C8** | `Gris` (`#757575`) | Guadalajara - Atocha - Chamartín - Cercedilla |
| **C10**| `Turquesa` (`#00a587`) | Villalba - Príncipe Pío - Atocha - Chamartín - Aeropuerto T4 |

---

## ❓ Preguntas Frecuentes y Diagnóstico

### ¿Cada cuánto se actualizan los trenes?
* **Posiciones GPS y retrasos en tiempo real (GTFS-RT):** Se consultan cada **30 segundos**.
* **Horarios base y estaciones (GTFS estático):** Se almacenan localmente y se renuevan automáticamente cada **7 días** sin interrumpir las consultas.

### ¿Dónde veo si la base de datos está cargada?
Puedes añadir la tarjeta `renfe-cercanias-config-card` a tu panel para ver el tamaño de la base de datos y las estaciones en tiempo real, o revisar la entidad `button.renfe_cercanias_refrescar_gtfs`.

---

## 📄 Licencia y Fuentes de Datos

* Este proyecto está publicado bajo licencia [MIT](LICENSE).
* Datos abiertos proporcionados bajo licencia **CC BY 4.0** por **Renfe Operadora** y el **Ministerio de Transportes y Movilidad Sostenible**:
  * Horarios estáticos: `https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip`
  * Retrasos en tiempo real: `https://gtfsrt.renfe.com/trip_updates.json`
  * Posiciones GPS en tiempo real: `https://gtfsrt.renfe.com/vehicle_positions.json`
