# Estacionamiento Medido — Salta

Sistema digital de gestión de estacionamiento medido en la vía pública, desarrollado específicamente para la ciudad de Salta siguiendo su ordenanza municipal.

## Actores

| Actor | Descripción | Panel |
|-------|-------------|-------|
| **Conductor** | Usuario que estaciona. Escanea QR de permisionario para check-in, elige método de pago, escanea QR de salida para finalizar | 9 vistas (Uber-style, fondo negro forzado) |
| **Permisionario** | Dueño de una cuadra. Cobra en efectivo o recibe pagos por MP. Aprueba/rechaza reservas. Ve sesiones activas en tiempo real | 5 vistas (panel, reservas, QR, mapa) |
| **Admin** | Super-usuario. CRUD de todo, penalizaciones, reportes, desbloqueo | 8 vistas (dashboard, CRUD, penalizaciones, reportes) |

## Funcionalidades clave

- **Check-in por QR de permisionario**: conductor escanea QR de la cuadra → se asigna espacio disponible automáticamente
- **Pago en efectivo o Mercado Pago**: al salir, el permisionario cobra o el conductor paga por MP
- **Tarifa plana $600/h**: solo en horario operativo (lun-vie 7-21, sáb 7-14). Noches, domingos y feriados gratis
- **Reservas**: conductor solicita, permisionario aprueba/rechaza
- **Penalizaciones por no-show**: si no se usa una reserva aprobada → $60 de penalidad
- **Bloqueo automático**: >5 penalizaciones/mes o deuda >$10,000 → conductor bloqueado. Desbloqueo: $5,000
- **Mapa interactivo**: datos oficiales IDEMSA (604 segmentos, 6,974 espacios) con capas medido/prohibido/libre
- **App mobile**: wrapper Expo con WebView + escáner QR nativo

## Flujo principal

```
Conductor escanea QR del permisionario
  → Check-in automático (asigna espacio de esa cuadra)
  → Elige método de pago (efectivo / MP)
  → Estaciona (timer cuenta hacia arriba)
  → (Opcional: permisionario presiona "Cobrar" si es efectivo)
  → Escanea QR de salida
  → Se calcula costo según tiempo en horario operativo
  → Sesión finalizada
```

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12 + FastAPI (asyncio) |
| DB | SQLite + SQLAlchemy async |
| Auth | JWT (HS256) + bcrypt |
| Frontend | Jinja2 + CSS vanilla (forced dark) |
| Mapas | Leaflet + OSM + MarkerCluster |
| QR jsQR (web) / expo-camera (nativo) |
| Pagos | Mercado Pago Sandbox |
| Mobile | Expo (React Native) + WebView |
| Tunnel | Cloudflare Tunnel (gratuito) |
