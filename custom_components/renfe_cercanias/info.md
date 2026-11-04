# 🚆 Renfe Cercanías Madrid para Home Assistant

Integración completa para monitorizar en tiempo real los trenes de Cercanías Madrid mediante datos oficiales de Renfe (GTFS estático + GTFS-RT en directo).

## ✨ Características
* **Minutos en tiempo real al próximo tren:** Cuenta atrás dinámica y retrasos calculados.
* **Filtro de dirección/destino:** Para evitar trenes en sentido contrario.
* **Filtro por línea:** C1, C2, C3, C4, C5, C7, C8, C10.
* **Ventanas horarias:** Activa solo en tus horas de viaje.
* **Tarjetas Lovelace incluidas:**
  - `renfe-cercanias-card`: Tarjeta bonita con cuenta atrás e información de próximas salidas.
  - `renfe-cercanias-map-card`: Mapa interactivo en tiempo real con las posiciones GPS de los trenes.
  - `renfe-cercanias-config-card`: Panel de control, salud de la base de datos y explorador rápido de estaciones.

## ⚙️ Configuración
Ve a **Ajustes** -> **Dispositivos y servicios** -> **Añadir integración** y busca **Renfe Cercanías Madrid**.
