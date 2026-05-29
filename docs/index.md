# Estacionamiento Medido — Salta

Sistema digital de gestión de estacionamiento medido en la vía pública, desarrollado específicamente para la ciudad de Salta siguiendo su ordenanza municipal.

## Actores

| Actor | Descripción | Panel |
|-------|-------------|-------|
| **Conductor** | Usuario que estaciona. Busca espacios por GPS o texto (IDEMSA), escanea QR de permisionario para check-in, paga por MP simulado o efectivo, ve timer+costo en tiempo real | 7 vistas (Uber-style, fondo negro forzado) |
| **Permisionario** | Dueño de una o más cuadras. Registra ingresos manuales, procesa salidas (efectivo/MP), ve sesiones activas con timer+costo, asigna espacios | 10 vistas (panel, espacios, cuadra, ingreso, salida, QR, historial, mapa, reservas) |
| **Gestor** | Operador municipal. CRUD de permisionarios, listado de conductores, sesiones en vivo, reportes, deudas | 1 dashboard |
| **Admin** | Super-usuario. CRUD de todo (conductores, permisionarios, gestores, espacios), desbloqueo/suspensión, reportes, exportación CSV | 8 vistas (dashboard, CRUD, reportes, deudas) |

## Funcionalidades clave

- **Registro con verificación por email**: link único vía UUID, sin código de 6 dígitos
- **Check-in por QR de permisionario**: conductor escanea QR de la cuadra → se asigna espacio disponible automáticamente
- **Búsqueda de estacionamiento**: por dirección (texto) o GPS "Buscar ahora" con datos reales IDEMSA y mapa embebido
- **Pago en efectivo o Mercado Pago simulado**: permisionario procesa salida, o conductor paga por MP simulado
- **Timer+costo en tiempo real**: tarifa por hora se actualiza en vivo, muestra exenciones y tipo de vehículo
- **Precios**: auto/camioneta $600/h, moto $100/h, bicicleta gratis
- **Exenciones**: discapacidad (oblea), frentista, veterano Malvinas — todos gratis
- **Horarios**: Lun-Vie 7-21hs, Sáb 7-14hs, Nocturno 22-5hs, Domingos gratis
- **Vehiculos compartidos**: cualquier conductor puede usar cualquier vehículo (sin validación de dueño)
- **Sesiones en vivo**: mapa y lista para gestor/admin con ubicación, patente, tiempo
- **PWA**: service worker con offline map tiles, manifest para instalación
- **Deudas**: permisionario reporta salida sin pago → deuda queda registrada, bloqueo automático
- **App mobile**: wrapper Expo con WebView + escáner QR nativo

## Flujo principal

```
Conductor se registra → verifica email por link → login por DNI
  → Busca estacionamiento (texto o GPS) con datos IDEMSA
  → Escanea QR del permisionario → check-in automático
  → Timer cuenta hacia arriba con costo estimado
  → Elige método de pago (efectivo / MP simulado)
  → Permisionario procesa salida (efectivo finaliza, MP espera confirmación)
  → Conductor confirma pago MP → espacio liberado
```

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12 + FastAPI (asyncio) |
| DB | SQLite + SQLAlchemy async |
| Auth | JWT (HS256) + bcrypt |
| Frontend | Jinja2 + CSS vanilla (forced dark/light según rol) |
| Mapas | IDEMSA iframe embebido + Leaflet para gestor/admin |
| QR | qrcode (PIL) server-side |
| Pagos | Mercado Pago Sandbox (simulado: página propia con confirmación) |
| PWA | Service Worker (network-first API, cache-first static) |
| Mobile | Expo (React Native) + WebView |
| Tunnel | Cloudflare Tunnel (gratuito) |
