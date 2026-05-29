# Documentación de la API

La API corre en `http://localhost:8000`. Documentación interactiva (Swagger) en `/docs`.

Todas las rutas públicas no requieren autenticación. Las rutas protegidas usan JWT en header `Authorization: Bearer <token>` o cookie `token`.

---

## Autenticación

### `POST /api/auth/login`

Login unificado. Busca en conductores (por DNI), permisionarios (por codigo), gestores y admins (por username).

```json
{
  "username": "35123456",
  "password": "1234"
}
```

**Response 200:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "role": "conductor",
  "user_id": 1,
  "nombre": "Pedro López",
  "username": "35123456"
}
```

**Error 401:**
```json
{
  "detail": "Usuario o contraseña incorrectos"
}
```
**Error 403:**
```json
{
  "detail": "Email no verificado. Verificá tu correo primero."
}
```

### `POST /api/auth/register/conductor`

Registro de conductor con auto-checkin por email. Crea Conductor + Vehículo con `email_verified=False`, envía link de verificación por console.

```json
{
  "dni": "40123456",
  "nombre": "Martín",
  "apellido": "García",
  "email": "martin@ejemplo.com",
  "telefono": "3874123456",
  "password": "1234",
  "patente": "AB123CD",
  "tipo_vehiculo": "auto",
  "marca": "Toyota",
  "modelo": "Corolla"
}
```

**Response 200:**
```json
{
  "message": "Cuenta creada. Revisá tu email para verificar tu dirección de correo.",
  "email": "martin@ejemplo.com"
}
```

### `GET /api/auth/verify-email?token=<uuid>`

Verifica el email mediante link. Marca `email_verified=True` en Conductor y `verified=True` en EmailVerification. Renderiza página HTML de resultado.

**Response:** HTML page (`verify_result.html`) con éxito o error.

### `GET /api/auth/me`

Verifica token actual. Header: `Authorization: Bearer <token>`.

**Response 200:**
```json
{
  "user_id": 1,
  "role": "conductor",
  "username": "35123456"
}
```

---

## Conductores

### `GET /api/conductor/me`

Perfil del conductor autenticado con vehículos.

```json
{
  "id": 1,
  "dni": "35123456",
  "nombre": "Pedro",
  "apellido": "López",
  "email": "pedro@ejemplo.com",
  "telefono": "3874345678",
  "email_verified": true,
  "bloqueado": false,
  "saldo_deudor": 0,
  "exencion": "ninguna",
  "vehiculos": [
    {"id": 1, "patente": "AB123CD", "tipo": "auto", "marca": "Toyota", "modelo": "Corolla", "predeterminado": true}
  ]
}
```

### `PUT /api/conductor/me`

Actualizar perfil del conductor autenticado.

```json
{
  "nombre": "Pedro Updated",
  "telefono": "3874000000"
}
```

### `GET /api/conductor/sesion-activa`

Sesión activa del conductor con timer/costo en tiempo real.

```json
{
  "id": 1,
  "espacio_id": 100,
  "hora_inicio": "2026-05-29T10:30:00",
  "ubicacion": "GENERAL GUEMES 150",
  "vehiculo": {"id": 1, "patente": "AB123CD", "tipo": "auto"},
  "exencion": "ninguna",
  "tipo_vehiculo": "auto",
  "tarifa_por_hora": 600.0,
  "costo_estimado": 1200.0,
  "es_gratuito": false,
  "pago_pendiente": false
}
```

### `POST /api/conductor/checkin`

Check-in por espacio_id o permisionario_id. Usa `current_user["id"]` del JWT, no acepta `conductor_id` en body.

```json
{
  "espacio_id": 100,
  "vehiculo_id": 1
}
```
o
```json
{
  "permisionario_id": 1
}
```

**Response 200:**
```json
{
  "ok": true,
  "sesion_id": 1,
  "hora_inicio": "2026-05-29T10:30:00",
  "espacio_id": 100,
  "ubicacion": "GENERAL GUEMES 150",
  "qr_salida": "data:image/png;base64,..."
}
```

### `POST /api/conductor/elegir-pago/{sesion_id}`

Elige método de pago. Calcula costo instantáneo. Para MP devuelve `init_point`.

```json
{
  "metodo": "efectivo"
}
```

**Response 200 (efectivo):**
```json
{
  "ok": true,
  "metodo": "efectivo",
  "costo_total": 1200.0
}
```

**Response 200 (MP):**
```json
{
  "ok": true,
  "metodo": "mercadopago",
  "costo_total": 1200.0,
  "init_point": "https://simulated-mp-page/...",
  "preference_id": "pref_xxx"
}
```

### `POST /api/conductor/confirmar-pago-efectivo/{sesion_id}`

Confirma pago en efectivo. Finaliza sesión, libera espacio.

### `GET /api/conductor/pago-mercadopago/{sesion_id}`

Página HTML de pago MP simulado (cuadrícula de QR estilizada).

### `POST /api/conductor/pago-mercadopago/{sesion_id}/confirmar`

Confirma pago MP simulado. Finaliza sesión, libera espacio.

### `GET /api/conductor/pago-mercadopago/{sesion_id}/estado`

Estado del pago MP.

### `GET /api/conductor/historial?page=1&limit=20`

Historial paginado del conductor autenticado.

### `GET /api/conductor/comprobante/{sesion_id}`

Comprobante detallado de una sesión.

### `POST /api/conductor/password`

Cambiar contraseña.

```json
{
  "current_password": "1234",
  "new_password": "5678"
}
```

### `POST /api/conductor/pagar-multa`

Pagar deuda pendiente. Resetea `saldo_deudor` a 0 y desbloquea.

```json
{
  "monto": 5000.0
}
```

### Gestión de vehículos

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/conductor/vehiculo` | Agregar vehículo |
| DELETE | `/api/conductor/vehiculo/{id}` | Eliminar vehículo |
| PUT | `/api/conductor/vehiculo/{id}/predeterminado` | Marcar como predeterminado |

---

## Permisionarios

### `GET /api/permisionario/me`

Perfil del permisionario con manos y espacios.

### `GET /api/permisionario/espacios`

Espacios del permisionario con sesión activa (si tiene).

### `GET /api/permisionario/sesiones-activas`

Sesiones activas con timer/costo en tiempo real, exenciones.

### `POST /api/permisionario/registro-manual`

Registro manual de vehículo por patente. Crea conductor si no existe.

```json
{
  "patente": "ZZ999AA",
  "permisionario_id": 1,
  "espacio_id": null
}
```

### `POST /api/permisionario/salida`

Procesa salida. Efectivo finaliza inmediato; MP bloquea costo y espera confirmación.

```json
{
  "sesion_id": 1,
  "metodo_pago": "efectivo"
}
```

### `POST /api/permisionario/reportar-deuda`

Reporta deuda por salida sin pago.

### `GET /api/permisionario/historial`

Sesiones del día de hoy.

### `GET /api/permisionario/qr-data`

Datos para QR del permisionario (base64 + raw URL).

### `POST /api/permisionario/confirmar-ingreso/{sesion_id}`

Confirma ingreso manual (solo metodo_ingreso="aqui").

---

## Gestor / Admin

| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| POST | `/api/gestor/permisionario` | gestor, admin | Crear permisionario |
| GET | `/api/gestor/permisionarios` | gestor, admin | Listar permisionarios |
| PUT | `/api/gestor/permisionario/{id}` | gestor, admin | Editar permisionario |
| GET | `/api/gestor/conductores` | gestor, admin | Listar conductores |
| GET | `/api/gestor/sesiones-vivo` | gestor, admin | Sesiones activas en vivo |
| GET | `/api/gestor/reportes` | gestor, admin | Estadísticas generales |
| GET | `/api/gestor/deudas` | gestor, admin | Deudas reportadas |
| POST | `/api/admin/gestor` | admin | Crear gestor |
| GET | `/api/admin/gestores` | admin | Listar gestores |
| DELETE | `/api/admin/gestor/{id}` | admin | Desactivar gestor |
| POST | `/api/admin/permisionario` | admin | Crear permisionario |
| GET | `/api/admin/conductores` | admin | Listar conductores |
| PUT | `/api/admin/conductores/{id}` | admin | Editar conductor |
| DELETE | `/api/admin/conductores/{id}` | admin | Eliminar conductor |
| PUT | `/api/admin/permisionarios/{id}` | admin | Editar permisionario |
| DELETE | `/api/admin/permisionarios/{id}` | admin | Eliminar permisionario |
| GET | `/api/admin/sesiones-vivo` | admin | Sesiones activas |
| GET | `/api/admin/reportes` | admin | Reportes |
| GET | `/api/admin/deudas` | admin | Deudas |
| GET | `/api/admin/config` | admin | Constantes del sistema |
| POST | `/api/admin/conductores/{id}/desbloquear` | admin | Desbloquear conductor |
| POST | `/api/admin/conductores/{id}/suspender?dias=N` | admin | Suspender/desuspender |
| GET | `/api/admin/conductores/{id}/detalle` | admin | Detalle completo |
| GET | `/api/admin/conductores/buscar?q=` | admin | Buscar conductores |
| GET | `/api/admin/conductores/{id}/exportar-csv` | admin | Exportar historial CSV |

---

## Espacios (públicos)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/espacios` | Listar (filtros: calle, disponible, permisionario_id, lat/lng/radio) |
| GET | `/api/espacios/{id}` | Obtener espacio |
| POST | `/api/espacios` | Crear espacio |
| PUT | `/api/admin/espacios/{id}` | Editar espacio |
| DELETE | `/api/admin/espacios/{id}` | Eliminar espacio |
| GET | `/api/espacios/disponibles` | Solo disponibles |
| GET | `/api/espacios/con-estado` | Conteo libre/ocupado |
| GET | `/api/espacio/by-location?lat=&lng=` | Espacio más cercano |

---

## Búsqueda de estacionamiento

### `POST /api/buscar-estacionamiento`

Búsqueda por texto o GPS. Usa datos IDEMSA reales.

```json
{
  "q": "GENERAL GUEMES 150",
  "lat": null,
  "lng": null,
  "radio": 500
}
```
o
```json
{
  "q": null,
  "lat": -24.7883,
  "lng": -65.4106,
  "radio": 400
}
```

**Response 200:**
```json
{
  "consulta": "GENERAL GUEMES 150",
  "destino": {"lat": -24.7869, "lng": -65.4054},
  "resultados": [...],
  "bloques": [
    {"calle": "GENERAL GUEMES", "altura": "150", "total": 10, "disponibles": 8, "distancia_min": 12.5, "lat": -24.7869, "lng": -65.4054}
  ],
  "radio": 500
}
```

---

## Mapas

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/mapa-data` | Calles IDEMSA + centro + espacios |
| GET | `/api/mapa/cercanos?lat=&lng=&radio=` | Espacios cercanos (público) |
| GET | `/api/mapa/idemsa-calles` | Calles IDEMSA (segmentos) |

---

## Mercado Pago

### `POST /api/mp/webhook`

Webhook de MP. Recibe notificación, busca sesión por `external_reference`, calcula costo, finaliza sesión.

---

## Auth compartido

### `POST /api/auth/cambiar-password`

Cambiar contraseña (cualquier rol autenticado).

---

## Frontend — Páginas HTML

| Ruta | Template | Descripción |
|------|----------|-------------|
| `/` | `index.html` | Landing page |
| `/login` | `auth/login.html` | Login |
| `/registro` | `auth/registro.html` | Registro conductor (2 pasos) |
| `/conductor` | `conductor/index.html` | Home conductor (sesión activa + timer) |
| `/conductor/buscar` | `conductor/buscar.html` | Buscar estacionamiento (IDEMSA iframe + GPS) |
| `/conductor/estacionar` | `conductor/estacionar.html` | Check-in por QR permisionario |
| `/conductor/checkout/{id}` | `conductor/checkout.html` | Checkout (timer + info + pago) |
| `/conductor/historial` | `conductor/historial.html` | Historial de sesiones |
| `/conductor/perfil` | `conductor/perfil.html` | Editar perfil |
| `/conductor/vehiculos` | `conductor/vehiculos.html` | Gestionar vehículos |
| `/conductor/pago-mercadopago/{id}` | `conductor/pago_mercadopago.html` | Pago MP simulado |
| `/permisionario` | `permisionario/index.html` | Home permisionario |
| `/permisionario/panel` | `permisionario/panel.html` | Dashboard con sesiones activas |
| `/permisionario/qr` | `permisionario/qr.html` | QR de la cuadra |
| `/permisionario/espacios` | `permisionario/espacios.html` | Espacios asignados |
| `/permisionario/cuadra` | `permisionario/cuadra.html` | Mis cuadras asignadas |
| `/permisionario/ingreso` | `permisionario/ingreso.html` | Registro manual de ingreso |
| `/permisionario/salida` | `permisionario/salida.html` | Procesar salida |
| `/permisionario/historial` | `permisionario/historial.html` | Historial del día |
| `/permisionario/mapa` | `permisionario/mapa.html` | Mapa de espacios |
| `/permisionario/reservas` | `permisionario/reservas.html` | Gestionar reservas |
| `/gestor` | `gestor/index.html` | Dashboard gestor |
| `/admin` | `admin/index.html` | Dashboard admin |
| `/admin/conductores` | `admin/conductores.html` | CRUD conductores |
| `/admin/permisionarios` | `admin/permisionarios.html` | CRUD permisionarios |
| `/admin/gestores` | `admin/gestores.html` | CRUD gestores |
| `/admin/espacios` | `admin/espacios.html` | CRUD espacios |
| `/admin/sesiones` | `admin/sesiones_vivo.html` | Sesiones activas |
| `/admin/reportes` | `admin/reportes.html` | Reportes |
| `/admin/deudas` | `admin/deudas.html` | Deudas |
