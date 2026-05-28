# Documentación de la API

La API corre en `http://localhost:8000`. Documentación interactiva (Swagger) en `/docs`.

Todas las rutas públicas no requieren autenticación. Las rutas protegidas usan JWT en header `Authorization: Bearer <token>` o cookie `token`.

---

## Autenticación

### `POST /api/auth/login`

Login unificado. Busca en conductores, permisionarios y admins en ese orden.

```json
{
  "username": "pedro",
  "password": "1234"
}
```

**Response 200:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "role": "conductor",
  "user_id": 1,
  "nombre": "Pedro López"
}
```

**Error 401:**
```json
{
  "detail": "Usuario o contraseña incorrectos"
}
```

### `GET /api/auth/me`

Verifica token actual. Header: `Authorization: Bearer <token>`.

**Response 200:**
```json
{
  "user_id": 1,
  "role": "conductor",
  "username": "pedro"
}
```

---

## Conductores

### `GET /api/conductores`

Lista todos los conductores.

### `GET /api/conductores/{id}`

```json
{
  "id": 1,
  "nombre": "Pedro López",
  "email": "pedro@ejemplo.com",
  "telefono": "1166660101",
  "patente": "AB123CD",
  "bloqueado": false,
  "saldo_deudor": 0.0
}
```

### `PUT /api/conductores/{id}`

Actualizar nombre, email, teléfono o patente.

```json
{
  "patente": "AB123CD"
}
```

### `GET /api/conductores/{id}/status`

Estado completo con constantes del sistema.

```json
{
  "bloqueado": false,
  "motivo_bloqueo": null,
  "saldo_deudor": 0.0,
  "penalizaciones_mes": 0,
  "max_penalizaciones": 5,
  "deuda_maxima": 10000.0,
  "multa_bloqueo": 5000.0
}
```

### `GET /api/conductores/{id}/penalizaciones`

Historial de penalizaciones del conductor.

```json
[
  {
    "id": 1,
    "conductor_id": 1,
    "reserva_id": 3,
    "monto": 60.0,
    "motivo": "No-show: reserva #3 venció...",
    "fecha": "2026-05-28T15:30:00",
    "pagada": false
  }
]
```

### `POST /api/conductores/{id}/pagar-multa`

Paga la multa de desbloqueo ($5,000). Reduce `saldo_deudor` y desbloquea.

```json
{
  "ok": true,
  "mensaje": "Multa de $5,000 pagada. Ya podés usar el sistema."
}
```

---

## Permisionarios

### `GET /api/permisionarios`

Lista todos.

### `POST /api/permisionarios`

Crear.

---

## Espacios

### `GET /api/espacios`

Todos los espacios.

### `GET /api/espacios/disponibles`

```json
[
  {"id": 1, "ubicacion": "Gral. Güemes 150", "precio_por_hora": 600.0, "disponible": true}
]
```

### `GET /api/espacios/con-estado`

Espacios con estado actual (libre/ocupado). Incluye datos del conductor si está ocupado.

### `GET /api/espacio/by-location?ubicacion=Güemes`

Buscar espacios por ubicación (LIKE).

---

## Sesiones (Check-in / Check-out)

### `POST /api/checkin`

Check-in tradicional por espacio_id.

```json
{
  "espacio_id": 1,
  "conductor_id": 1
}
```

**Response 200:**
```json
{
  "sesion_id": 1,
  "hora_inicio": "2026-05-28T14:30:00",
  "qr_salida": "data:image/png;base64,..."
}
```

Incluye verificación de bloqueo. Si el conductor está bloqueado, devuelve 400.

### `POST /api/checkin-por-perm`

Check-in escaneando QR de permisionario. Busca el primer espacio disponible en la calle del permisionario.

```json
{
  "permisionario_id": 1,
  "conductor_id": 1
}
```

Si es una reserva aprobada (match por conductor + espacio), vincula la sesión a la reserva y aplica tolerancia de 5 min.

**Response 200:** igual que `/api/checkin`.

### `POST /api/sesion/{id}/elegir-pago`

Elige método de pago y opcionalmente actualiza patente.

```json
{
  "metodo": "efectivo",
  "patente": "AB123CD"
}
```

`metodo` puede ser `"efectivo"` o `"mercadopago"`.

### `POST /api/sesion/{id}/confirmar-pago-efectivo`

Confirma pago en efectivo. Calcula costo con `calcular_costo_estacionamiento`, marca `pagado=True`, `lista_para_salir=True`, suma al `saldo_deudor`.

**Response 200:**
```json
{
  "ok": true,
  "costo_total": 1200.0,
  "qr_salida": "data:image/png;base64,...",
  "mensaje": "Pago en efectivo confirmado"
}
```

### `GET /api/sesion/{id}/exit-qr`

Obtiene el QR de salida (solo si `lista_para_salir=True`).

### `POST /api/sesion/{id}/finalizar-por-scan`

Finaliza sesión cuando el conductor escanea el QR de salida. Calcula costo si no estaba calculado.

**Response 200:**
```json
{
  "ok": true,
  "costo_total": 1200.0,
  "metodo_pago": "efectivo",
  "pagado": true
}
```

### `GET /api/checkin-qr/{sesion_id}`

QR de check-in de una sesión activa.

### `POST /api/checkout`

Check-out tradicional (por sesion_id).

```json
{
  "sesion_id": 1
}
```

**Response 200:**
```json
{
  "sesion_id": 1,
  "costo_total": 1200.0,
  "link_pago": "https://sandbox.mercadopago.com.ar/..."
}
```

### `GET /api/sesiones`

Todas las sesiones.

### `GET /api/sesiones/activas`

Solo sesiones activas (sin hora_fin).

### `GET /api/sesiones/conductor/{id}`

Sesiones de un conductor (con datos del espacio).

### `GET /api/sesiones/activas/{permisionario_id}`

Sesiones activas filtradas por calle del permisionario.

### `GET /api/sesiones/activa/{conductor_id}`

Sesión activa actual de un conductor (una sola).

**Response 200:**
```json
{
  "id": 1,
  "espacio_id": 1,
  "conductor_id": 1,
  "hora_inicio": "2026-05-28T14:30:00",
  "hora_fin": null,
  "costo_total": null,
  "pagado": false,
  "metodo_pago": "efectivo",
  "lista_para_salir": false,
  "ubicacion": "Gral. Güemes 150",
  "patente": "AB123CD"
}
```

### `GET /api/sesiones/ingresos/{permisionario_id}`

Ingresos semanales del permisionario (solo sesiones pagadas).

```json
{
  "total": 7200.0,
  "por_dia": [
    {"dia": "2026-05-22", "total": 1200.0, "cantidad": 2},
    {"dia": "2026-05-23", "total": 600.0, "cantidad": 1}
  ],
  "cantidad_total": 3
}
```

### `GET /api/sesiones/permisionario/{id}/detalle`

Sesiones activas del permisionario con ubicación y datos del conductor.

---

## Mercado Pago

### `POST /api/mercadopago/webhook`

Webhook de notificación de pago. Recibe `POST` de MP, busca la sesión por `external_reference` (sesion_id), calcula costo si no estaba, marca `pagado=True` y `lista_para_salir=True`.

---

## Reservas

### `GET /api/reservas`

Todas.

### `GET /api/reservas/conductor/{id}`

De un conductor.

### `GET /api/reservas/permisionario/{id}`

De un permisionario.

### `GET /api/reservas/pendientes/{permisionario_id}`

Pendientes de aprobación de un permisionario (match por calle).

### `POST /api/reservas`

Solicitar reserva.

```json
{
  "espacio_id": 1,
  "conductor_id": 1,
  "hora_inicio": "2026-05-29T10:00:00",
  "hora_fin": "2026-05-29T12:00:00"
}
```

### `POST /api/reservas/aprobar`

Aprobar o rechazar.

```json
{
  "reserva_id": 1,
  "aprobar": true
}
```

---

## Penalizaciones (Admin)

### `GET /api/admin/penalizaciones`

Todas las penalizaciones (sin paginar).

### `GET /api/admin/penalizaciones/stats`

```json
{
  "total": 5,
  "monto_total": 300.0,
  "pendientes": 2,
  "monto_pendiente": 120.0,
  "pagadas": 3,
  "monto_pagado": 180.0
}
```

### `POST /api/admin/penalizaciones/{id}/waiver`

Condonar (perdonar) una penalización. Marca `pagada=True` y descuenta del `saldo_deudor` del conductor.

### `GET /api/admin/conductores/bloqueados`

Lista de conductores bloqueados.

### `POST /api/admin/conductores/{id}/desbloquear`

Desbloquea manualmente (solo admin).

### `POST /api/admin/verificar-no-show`

Ejecuta manualmente la verificación de no-show (normalmente corre cada 60s en background).

---

## Mapas

### `GET /api/mapa/cercanos?lat=-24.7883&lng=-65.4106&radio=300`

Espacios cercanos en un radio (metros).

```json
[
  {
    "id": 1,
    "ubicacion": "Gral. Güemes 150",
    "lat": -24.7885,
    "lng": -65.41,
    "precio_por_hora": 600.0,
    "disponible": true
  }
]
```

### `GET /api/mapa/idemsa-calles`

Calles desde IDEMSA con segmentos y colores para renderizar en el mapa Leaflet.

---

## Páginas HTML (Frontend)

| Ruta | Template | Descripción |
|------|----------|-------------|
| `/` | `index.html` | Landing page |
| `/login` | `auth/login.html` | Login |
| `/conductor` | `conductor/index.html` | Home conductor |
| `/conductor/checkin` | `conductor/checkin.html` | Checkin manual |
| `/conductor/checkin/perm/{id}` | `conductor/checkin_auto.html` | Auto checkin vía QR |
| `/conductor/checkout/{id}` | `conductor/checkout.html` | Checkout + elegir pago |
| `/conductor/reservar` | `conductor/reservar.html` | Solicitar reserva |
| `/conductor/mis-reservas` | `conductor/mis_reservas.html` | Mis reservas |
| `/conductor/perfil` | `conductor/perfil.html` | Editar perfil |
| `/conductor/historial` | `conductor/historial.html` | Historial |
| `/conductor/mapa` | `conductor/mapa.html` | Mapa interactivo |
| `/permisionario/{id}/panel` | `permisionario/panel.html` | Dashboard |
| `/permisionario/{id}/reservas` | `permisionario/reservas.html` | Gestionar reservas |
| `/permisionario/{id}/qr` | `permisionario/qr.html` | QR de la cuadra |
| `/permisionario/{id}/mapa` | `permisionario/mapa.html` | Mapa |
| `/admin` | `admin/index.html` | Dashboard admin |
| `/admin/permisionarios` | `admin/permisionarios.html` | CRUD |
| `/admin/conductores` | `admin/conductores.html` | CRUD |
| `/admin/espacios` | `admin/espacios.html` | CRUD |
| `/admin/sesiones` | `admin/sesiones.html` | Listado |
| `/admin/reservas` | `admin/reservas.html` | Listado |
| `/admin/reportes` | `admin/reportes.html` | Reportes |
| `/admin/penalizaciones` | `admin/penalizaciones.html` | Penalizaciones |
