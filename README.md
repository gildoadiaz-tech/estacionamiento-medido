# Estacionamiento Medido v2.0 — Salta

Sistema completo de estacionamiento medido inteligente con 4 roles (conductor, permisionario, gestor, admin), búsqueda GPS con datos oficiales IDEMSA, pagos con Mercado Pago (simulado), sesiones en vivo con timer+costo, verificación por email, y PWA offline.

> **Demo sin presupuesto:** sin hosting, sin dominios, sin servicios pagos.
> Usa Cloudflare Tunnel gratuito para exponer localhost.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) |
| Base de datos | SQLite (aiosqlite) — 12 tablas |
| Autenticación | JWT (python-jose) + bcrypt |
| Frontend | Jinja2 templates + CSS vanilla (mobile-first / desktop sidebar) |
| Mapas | IDEMSA GIS embed + Leaflet + OSM |
| QR | qrcode (PIL) server-side |
| Pagos | Mercado Pago Sandbox (con fallback simulado) |
| PWA | Service Worker (network-first API, cache-first static) |
| Mobile | Expo (React Native) + WebView |
| Túneles | Cloudflare Tunnel |

---

## Inicio rápido

```bash
git clone https://github.com/gildoadiaz-tech/estacionamiento-medido.git
cd estacionamiento-medido
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abrir **http://localhost:8000**

### Exponer con Cloudflare Tunnel (para probar desde el celular)

```bash
cloudflared tunnel --url http://localhost:8000
# Genera: https://<random>.trycloudflare.com
```

---

## Usuarios de prueba

### Conductores (login por DNI)

| DNI | Contraseña | Datos |
|-----|-----------|-------|
| `35123456` | `1234` | Pedro López — Auto (Toyota Corolla) + Moto (Honda CG 150), sin exención |
| `36234567` | `1234` | Ana Martínez — Camioneta (Ford Ranger), sin exención |
| `30111222` | `1234` | Carlos Ruiz — Auto (Chevrolet Corsa), **Oblea Discapacidad** |
| `29444555` | `1234` | Lucía Fernández — Auto (VW Gol), **Frentista** |
| `20999888` | `1234` | Roberto Gómez — Auto (Fiat Cronos), **Veterano Malvinas** |
| `37555666` | `1234` | Eva Torres — **Bicicleta** (Venzo Urban), sin exención |

### Permisionarios (login por código)

| Código | Contraseña | Cuadra |
|--------|-----------|--------|
| `PER30456789` | `1234` | Juan Pérez — GENERAL GUEMES 100-200 (par+impar, ~46 espacios) |
| `PER28345678` | `1234` | María García — CASEROS 1100-1200 (par, ~37 espacios) |

### Gestor

| Usuario | Contraseña |
|---------|-----------|
| `gestor1` | `gestor123` |

### Admin

| Usuario | Contraseña |
|---------|-----------|
| `admin` | `admin123` |

---

## Roles y flujos

### 👤 Conductor (mobile-first, fondo negro)

1. **Registro** → formulario único → link de verificación por email (impreso en terminal)
2. **Login** → por DNI + contraseña (verifica email)
3. **Home** → sesión activa con timer (cuenta hacia arriba), costo estimado en tiempo real
4. **Buscar** → texto (calle + altura) o GPS "Buscar ahora" con mapa IDEMSA embebido
5. **Estacionar** → escanea QR de permisionario → check-in automático
6. **Checkout** → ve timer + costo + info del vehículo, elige método de pago
7. **Mercado Pago** → página de pago simulado con confirmación
8. **Perfil** → editar datos, ver historial
9. **Vehículos** → agregar/eliminar vehículos (compartidos)

### 🅿️ Permisionario (mobile-first + desktop sidebar)

1. **Login** → por código (ej: PER30456789)
2. **Panel** → sesiones activas con timer + costo en tiempo real + exenciones
3. **Espacios** → mapa de espacios asignados
4. **Cuadra** → detalle de cuadras asignadas (calle, rango alturas, lado)
5. **Ingreso** → registro manual por patente
6. **Salida** → procesar salida (efectivo finaliza, MP bloquea costo)
7. **QR** → código QR de la cuadra para conductores
8. **Historial** → sesiones del día
9. **Mapa** → espacios en mapa
10. **Reservas** → gestionar solicitudes

### 🔧 Gestor (desktop sidebar)

1. **Dashboard** → stats generales
2. **Permisionarios** → CRUD (crear con calles)
3. **Conductores** → listado completo
4. **Sesiones en vivo** → mapa + lista
5. **Reportes** → ingresos, ocupación
6. **Deudas** → listado

### ⚙️ Admin (desktop sidebar)

1. **Dashboard** → stats generales + config
2. **Conductores** → CRUD + detalle + exportar CSV + desbloquear/suspender
3. **Permisionarios** → CRUD
4. **Gestores** → CRUD
5. **Espacios** → CRUD
6. **Sesiones** → en vivo
7. **Reportes** → ingresos, ocupación
8. **Deudas** → listado completo

---

## Reglas de negocio

### Precios
- **$600/h** auto y camioneta
- **$100/h** moto
- **$0/h** bicicleta
- **Exenciones**: discapacidad (oblea), frentista, veterano Malvinas → todos gratis

### Horarios
- Lun–Vie: 7:00 a 21:00 (diurno), 22:00 a 5:00 (nocturno)
- Sáb: 7:00 a 14:00 (diurno), 22:00 a 5:00 (nocturno)
- Domingos: gratis todo el día
- Fuera de horario: gratis hasta el próximo inicio de horario cobrable

### Sesiones
- Conductor **no puede finalizar** su propia sesión — solo el permisionario procesa salida
- Pago en efectivo: permisionario procesa → sesión finaliza inmediatamente
- Pago por MP: permisionario bloquea costo + hora_fin → conductor confirma pago → sesión finaliza

### Vehículos
- Compartidos entre conductores — cualquier conductor puede usar cualquier vehículo (sin validación de propietario)
- Checkin usa JWT `current_user["id"]`, nunca del body

### Bloqueo
- Deuda >= $10,000 → bloqueo automático
- Admin desbloquea manualmente o conductor paga deuda

### Búsqueda de estacionamiento
- Por texto: calle + altura (ej: "GENERAL GUEMES 150")
- Por GPS: "Buscar ahora" usa geolocalización del browser
- Radio: 500m (texto) / 400m (GPS)
- Resultados agrupados por bloque (calle + altura)
- Mapa IDEMSA embebido como iframe

---

## API — Endpoints principales

### Autenticación
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/auth/login` | Login (DNI/código/username + password), devuelve JWT + role |
| POST | `/api/auth/register/conductor` | Registro con verificación por email |
| GET | `/api/auth/verify-email?token=` | Verificar email por link UUID |
| GET | `/api/auth/me` | Verificar token actual |
| POST | `/api/auth/cambiar-password` | Cambiar contraseña |

### Conductor (protegido, role=conductor)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/conductor/me` | Perfil + vehículos |
| PUT | `/api/conductor/me` | Actualizar perfil |
| GET | `/api/conductor/sesion-activa` | Sesión activa con timer + costo |
| POST | `/api/conductor/checkin` | Check-in (por espacio o permisionario) |
| POST | `/api/conductor/elegir-pago/{id}` | Elegir método de pago |
| POST | `/api/conductor/confirmar-pago-efectivo/{id}` | Confirmar efectivo |
| POST | `/api/conductor/pago-mercadopago/{id}/confirmar` | Confirmar MP simulado |
| GET | `/api/conductor/pago-mercadopago/{id}/estado` | Estado del pago |
| GET | `/api/conductor/historial` | Historial paginado |
| GET | `/api/conductor/comprobante/{id}` | Comprobante detallado |
| POST | `/api/conductor/password` | Cambiar contraseña |
| POST | `/api/conductor/pagar-multa` | Pagar deuda |
| POST | `/api/conductor/vehiculo` | Agregar vehículo |
| DELETE | `/api/conductor/vehiculo/{id}` | Eliminar vehículo |
| PUT | `/api/conductor/vehiculo/{id}/predeterminado` | Marcar predeterminado |

### Permisionario (protegido, role=permisionario)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/permisionario/me` | Perfil + manos + espacios |
| GET | `/api/permisionario/espacios` | Espacios con sesión activa |
| GET | `/api/permisionario/sesiones-activas` | Sesiones activas con timer |
| POST | `/api/permisionario/registro-manual` | Registro manual por patente |
| POST | `/api/permisionario/salida` | Procesar salida |
| POST | `/api/permisionario/reportar-deuda` | Reportar deuda |
| GET | `/api/permisionario/historial` | Historial del día |
| GET | `/api/permisionario/qr-data` | Datos del QR |
| POST | `/api/permisionario/confirmar-ingreso/{id}` | Confirmar ingreso |

### Búsqueda
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/buscar-estacionamiento` | Buscar por texto o GPS (datos IDEMSA) |

### Espacios
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/espacios` | Listar (con filtros) |
| GET | `/api/espacios/disponibles` | Solo disponibles |
| GET | `/api/espacio/by-location` | Más cercano por coordenadas |

### Mapas
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/mapa-data` | Calles IDEMSA + centro + espacios |
| GET | `/api/mapa/cercanos` | Espacios cercanos (radio) |

### Mercado Pago
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/mp/webhook` | Webhook de MP |

### Admin/Gestor
| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| POST | `/api/gestor/permisionario` | gestor, admin | Crear permisionario |
| GET | `/api/gestor/permisionarios` | gestor, admin | Listar |
| PUT | `/api/gestor/permisionario/{id}` | gestor, admin | Editar |
| GET | `/api/gestor/conductores` | gestor, admin | Listar conductores |
| GET | `/api/gestor/sesiones-vivo` | gestor, admin | Sesiones activas |
| GET | `/api/gestor/reportes` | gestor, admin | Reportes |
| GET | `/api/gestor/deudas` | gestor, admin | Deudas |
| POST | `/api/admin/gestor` | admin | Crear gestor |
| GET | `/api/admin/gestores` | admin | Listar gestores |
| DELETE | `/api/admin/gestor/{id}` | admin | Desactivar gestor |
| GET | `/api/admin/conductores` | admin | Listar conductores |
| PUT | `/api/admin/conductores/{id}` | admin | Editar conductor |
| DELETE | `/api/admin/conductores/{id}` | admin | Eliminar conductor |
| POST | `/api/admin/conductores/{id}/desbloquear` | admin | Desbloquear |
| POST | `/api/admin/conductores/{id}/suspender` | admin | Suspender |
| GET | `/api/admin/conductores/{id}/detalle` | admin | Detalle completo |
| GET | `/api/admin/conductores/buscar` | admin | Buscar |
| GET | `/api/admin/conductores/{id}/exportar-csv` | admin | Exportar CSV |
| GET | `/api/admin/config` | admin | Constantes |
| GET | `/api/admin/reportes` | admin | Reportes |
| GET | `/api/admin/deudas` | admin | Deudas |

---

## Datos geoespaciales (IDEMSA)

El sistema sincroniza **~6,974 espacios** generados a partir de **604 segmentos viales oficiales** extraídos del visor GIS de IDEMSA Municipalidad de Salta:

- `idemsa_data.py` → descarga/parsea archivos JS públicos de IDEMSA
- `sync_espacios_db()` → genera puntos grid cada ~7m, los persiste en SQLite
- Categorías: `estacionamiento_medido` (única usada para asignación)
- Permisionarios tienen manos (cuadras) con calle + rango de altura + lado
- Filtrado por `ubicacion.startswith(mano.calle)` + rango de `numero`
- Sin distinción par/impar (IDEMSA usa block-level, no house-level)

---

## Mobile App (Expo)

```
mobile-app/
├── App.js                    # Stack navigator (Home, QRScanner, Config)
├── app.json                  # Expo config (dark UI, camera permissions)
├── context/
│   └── ServerUrlContext.js    # Server URL persistence (AsyncStorage)
├── screens/
│   ├── WebViewScreen.js       # Full-screen WebView + floating QR & gear
│   ├── QRScannerScreen.js     # Native QR scanner (expo-camera)
│   └── ConfigScreen.js        # Server URL input
└── assets/                    # Placeholder icons
```

### Correr la app mobile

```bash
cd mobile-app
npm install
npx expo start
```

Escaneá el QR con Expo Go en tu celular, o presioná `a` para Android emulator / `i` para iOS simulator.

Configurá la URL del servidor (localhost o Cloudflare Tunnel) desde el ícono de engranaje ⚙️.

---

## Estructura del proyecto

```
estacionamiento/
├── app/
│   ├── main.py              # 2368 líneas — rutas API + HTML + lógica
│   ├── models.py            # 10 modelos SQLAlchemy (12 tablas)
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # Conexión async SQLite
│   ├── auth.py              # JWT + bcrypt
│   ├── auth_routes.py       # Login + register + verify email
│   ├── deps.py              # Dependencias (get_current_user, require_role)
│   ├── qr_utils.py          # Generación QR (PIL)
│   ├── mercado_pago.py      # Integración MP sandbox + simulado
│   ├── mapa_data.py         # Calles del centro (Leaflet)
│   ├── idemsa_data.py       # Sincronización IDEMSA (604 segmentos)
│   ├── static/              # Archivos estáticos (JS, CSS, imágenes, manifest, sw.js)
│   └── templates/           # Jinja2 templates
│       ├── auth/            # Login, registro, verify_result
│       ├── conductor/       # 8 vistas (index, buscar, estacionar, checkout, historial, perfil, vehiculos, pago_mp)
│       ├── permisionario/   # 10 vistas (panel, espacios, cuadra, ingreso, salida, QR, historial, mapa, reservas)
│       ├── gestor/          # 1 dashboard
│       └── admin/           # 8 vistas (dashboard, CRUDs, sesiones, reportes, deudas)
├── mobile-app/              # Expo React Native wrapper
├── docs/                    # Documentación adicional
├── seed.py                  # Datos de prueba
├── requirements.txt
└── README.md
```

---

## Configuración

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `JWT_SECRET` | `estacionamiento-salta-secret-key-2024` | Secreto para firmar tokens JWT |
| `MP_ACCESS_TOKEN` | `TEST-...` | Token de acceso de Mercado Pago Sandbox |
| `BASE_URL` | `http://localhost:8000` | URL base para QR y links |

### Constantes del sistema (en `main.py`)

| Constante | Valor | Descripción |
|-----------|-------|-------------|
| `PRECIO_AUTO` | 600.0 | Tarifa por hora autos/camionetas |
| `PRECIO_MOTO` | 100.0 | Tarifa por hora motos |
| `HORARIO_CIERRE` | 21 | Hora de cierre lun-vie |
| `HORARIO_CIERRE_SAB` | 14 | Hora de cierre sábado |
| `DEUDA_MAXIMA` | 10000.0 | Deuda máxima antes de bloqueo |

---

## Licencia

MIT
