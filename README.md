# Estacionamiento Medido v2.0 — Salta

Sistema completo de estacionamiento medido inteligente con 3 roles (conductor, permisionario, admin), búsqueda GPS con datos oficiales IDEMSA, pagos con Mercado Pago (split 80/20), sesiones en vivo con timer+costo, QR de salida gestionado por permisionario, mapa de calor, y PWA offline.

---

## Equipo

- **Gildo Díaz** — [@gildoadiaz-tech](https://github.com/gildoadiaz-tech)
- **Ariel Lamas**
- **Antonio Chocobar**

## Problema

La Municipalidad de Salta regula el estacionamiento medido en el centro de la ciudad (Ordenanza N.º 12.170). El sistema actual es manual: permisionarios controlan espacios con tarjetas de papel, sin información en tiempo real, sin seguimiento de pagos, y sin transparencia para el conductor.

## Solución

Plataforma web + móvil que digitaliza el estacionamiento medido:

- **Conductor** busca dónde estacionar, escanea QR del permisionario, ve timer y costo en vivo, espera a que el permisionario procese la salida (o paga con Mercado Pago si aplica)
- **Permisionario** gestiona sesiones, procesa salidas, genera QR de entrada y de salida por sesión activa, QR imprimible para conductores sin smartphone, recibe 80% del cobro
- **Admin** supervisa, reporta, administra permisionarios y conductores, mapa de calor en vivo

### Track elegido: Estacionamiento Medido

Cumplimiento de Ordenanza N.º 12.170:
- Tarifas: $700/h auto, $300/h moto, bicicleta gratis
- Fraccionamiento 15 min desde 2da hora
- Tolerancia 5 minutos (gratuito si ≤5 min)
- Descuento 20% pagando con Mercado Pago (absorbido por municipio)
- Exenciones: discapacidad (oblea), frentista, veterano Malvinas
- Feriados nacionales y provinciales de Salta: diurno gratis, nocturno solo en zonas habilitadas
- Zonas nocturnas: Balcarce, Güemes, Alvarado (22:00–5:00)

## Stack técnico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy async |
| Base de datos | PostgreSQL (producción) / SQLite (desarrollo local) |
| Autenticación | JWT (python-jose) + PBKDF2-HMAC-SHA256 + cookies |
| Frontend | Jinja2 templates + CSS vanilla (mobile-first) |
| Mapas | Leaflet + Leaflet.heat (mapa de calor) + OSM |
| QR | qrcode (PIL) server-side + QR de salida generado por permisionario |
| Pagos | Mercado Pago (split 80/20 con collector_id) |
| Seguridad | Rate limiting (slowapi), CORS, HMAC password verify, webhook signature |
| PWA | Service Worker (network-first API, cache-first static) |
| Deploy | Docker Compose (app + PostgreSQL) |

## Herramientas de IA utilizadas

- **OpenCode** (GLM 5.1) — asistente principal de desarrollo, debugging, generación de código

## Datasets

- **IDEMSA** — Segmentos viales oficiales del estacionamiento medido de Salta (datos GIS públicos del visor de IDEMSA). Sin datos personales.

---

## Deploy con Docker (producción)

### Requisitos

- Docker + Docker Compose (v2) instalado
- Puerto 8000 libre (o configurar `APP_PORT`)

### Instrucciones

```bash
git clone https://github.com/gildoadiaz-tech/estacionamiento-medido.git
cd estacionamiento-medido
docker compose up -d
```

La app arranca en **http://localhost:8000**.

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | PostgreSQL interno | URL de conexión (auto-configurada en compose) |
| `JWT_SECRET` | Aleatorio (solo dev) | Secreto para firmar tokens JWT (obligatorio en producción) |
| `BASE_URL` | `http://localhost:8000` | URL base para QR y links |
| `MP_ACCESS_TOKEN` | vacío | Token de acceso Mercado Pago |
| `APP_PORT` | `8000` | Puerto donde escucha la app |
| `DB_PASSWORD` | `estacionamiento2026` | Password de PostgreSQL |

### Cambiar contraseña de producción

```bash
echo "DB_PASSWORD=tu_password_seguro" > .env
echo "JWT_SECRET=tu_jwt_secret_seguro" >> .env
docker compose up -d
```

### Ver logs

```bash
docker compose logs -f app
```

### Detener

```bash
docker compose down
```

### Resetear base de datos

```bash
docker compose down -v   # Elimina volúmenes (borra la DB)
docker compose up -d      # Crea todo de nuevo con seed automático
```

---

## Ejecutar localmente (desarrollo con SQLite)

### Requisitos

- Python 3.11+
- Git

### Instalación y ejecución

```bash
# Clonar el repositorio
git clone https://github.com/gildoadiaz-tech/estacionamiento-medido.git
cd estacionamiento-medido

# Crear entorno virtual e instalar dependencias
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Crear base de datos con datos de prueba
python seed.py
python seed_datos.py

# Iniciar el servidor
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Usuarios de prueba

> Todos los usuarios usan la misma contraseña: **`demo1234`**

### Conductor (login por DNI)

| DNI | Datos |
|-----|-------|
| `87654321` | Pedro López — Auto (Toyota Corolla) + Moto (Honda CG 150), sin exención |
| `36234567` | Ana Martínez — Camioneta (Ford Ranger), sin exención |
| `30111222` | Carlos Ruiz — Auto (Chevrolet Corsa), **Oblea Discapacidad** |
| `29444555` | Lucía Fernández — Auto (VW Gol), **Frentista** |
| `20999888` | Roberto Gómez — Auto (Fiat Cronos), **Veterano Malvinas** |
| `37555666` | Eva Torres — **Bicicleta** (Venzo Urban), sin exención |

### Permisionario (login por código)

| Código | Datos |
|--------|-------|
| `PERM001` | Juan Pérez (Gral. Güemes 100-200) |
| `PERM002` | María García (Caseros 1100-1200) |

### Admin

| Usuario | Contraseña |
|---------|-----------|
| `admin` | `demo1234` |

> La página principal tiene un **Modo Demo** con botones que inician sesión automáticamente.  
> Los datos ficticios se crean con `python seed_datos.py` (30 sesiones, 26 pagos, 3 deudas, mapa de calor).

---

## Roles y flujos

### Conductor (mobile-first)

1. Registro → verificación por email
2. Login por DNI + contraseña
3. Buscar estacionamiento (texto o GPS) → botón "Navegar" (redirige a Google Maps)
4. Escanea QR del permisionario → check-in automático
5. Ve timer + costo en vivo, espera a que el permisionario finalice la sesión
6. Paga con Mercado Pago (si el permisionario seleccionó ese método) o en efectivo al permisionario

### Permisionario (mobile + desktop)

1. Panel de sesiones activas con timer y costo en tiempo real
2. Procesar salidas (efectivo o Mercado Pago)
3. QR de salida por sesión activa (el permisionario genera y muestra el QR)
4. QR imprimible para conductores sin smartphone
5. Reportes financieros, historial

### Admin (dashboard)

1. Dashboard con estadísticas y finanzas
2. CRUD permisionarios (CVU, Collector ID de MP)
3. CRUD conductores, sesiones en vivo, reportes, deudas
4. Mapa de calor de sesiones (Leaflet.heat)

### Modo Demo

La página principal incluye 3 botones de **Modo Demo** que inician sesión automáticamente sin registro:
- **Conductor** → DNI: 87654321
- **Permisionario** → Código: PERM001
- **Admin** → Usuario: admin

---

## Seguridad

- **JWT** con secreto aleatorio en producción (obligatorio configurar `JWT_SECRET`)
- **PBKDF2-HMAC-SHA256** con 100K iteraciones para passwords (sin bcrypt/passlib)
- **Rate limiting**: 20 intentos de login por minuto por IP
- **CORS**: allow all origins (`*`)
- **Auth middleware**: rutas protegidas (`/conductor`, `/permisionario`, `/admin`) redirigen a `/login` sin cookie válida
- **Webhook signature** verification para Mercado Pago
- **Código de salida** generado por permisionario (el conductor ya no hace self-checkout)
- **Permisos** basados en roles (conductor, permisionario, admin)

---

## Reglas de negocio (Ordenanza N.º 12.170)

- **Tarifas**: $700/h auto/camioneta, $300/h moto, bicicleta gratis
- **Fraccionamiento**: 15 minutos desde la 2da hora
- **Tolerancia**: primeros 5 minutos gratuitos
- **Descuento MP**: 20% absorbido por el municipio (permisionario siempre cobra 80%)
- **Exenciones**: discapacidad (oblea), frentista, veterano Malvinas
- **Feriados**: diurno gratis, nocturno solo en zonas habilitadas
- **Zonas nocturnas**: Balcarce, Güemes, Alvarado (22:00–5:00)
- **Flujo del dinero**: permisionario recauda → 80% permisionario / 20% municipio

---

## Estructura del proyecto

```
estacionamiento/
├── app/
│   ├── main.py              # FastAPI app, endpoints, lógica de negocio, auth middleware
│   ├── models.py            # Modelos SQLAlchemy (sin Gestor)
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # Conexión async (SQLite o PostgreSQL)
│   ├── auth.py              # JWT + PBKDF2-HMAC-SHA256 + HMAC compare
│   ├── auth_routes.py       # Login (3 roles), registro, verify
│   ├── deps.py              # Dependencias FastAPI (get_current_user, require_role, auth middleware)
│   ├── qr_utils.py          # Generación QR (PIL)
│   ├── mercado_pago.py       # Integración MP (split 80/20 con collector_id)
│   ├── mapa_data.py         # Calles del centro (Leaflet)
│   ├── idemsa_data.py       # Sincronización IDEMSA (604 segmentos)
│   ├── static/              # manifest, icons, service worker
│   └── templates/           # Jinja2 templates (3 roles)
│       ├── auth/             # Login, registro, verify
│       ├── conductor/       # Buscar, estacionar, checkout, historial, perfil
│       ├── permisionario/   # Panel, QR, salida, historial
│       └── admin/           # Dashboard, CRUDs, reportes, sesiones vivo (mapa de calor)
├── Dockerfile
├── docker-compose.yml
├── seed.py                  # Datos base de prueba
├── seed_datos.py            # Datos ficticios de demo (sesiones, pagos, deudas)
├── requirements.txt
└── README.md
```

---

## Licencia

MIT