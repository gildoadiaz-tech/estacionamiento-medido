# Guía de instalación y puesta en marcha

## Requisitos

- Python 3.10+
- Git
- `pip` (comes with Python)
- (Opcional) `cloudflared` para exponer localhost
- (Opcional) Node.js 18+ para la app mobile Expo

---

## 1. Clonar y entrar al proyecto

```bash
git clone git@github.com:gildoadiaz-tech/estacionamiento-medido.git
cd estacionamiento-medido
```

## 2. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

**Nota sobre bcrypt:** Si usás bcrypt 4.1+, pasá a 4.0.1 para compatibilidad con passlib:
```bash
pip install bcrypt==4.0.1
```

## 3. Sembrar datos de prueba

```bash
python seed.py
```

Esto crea:

### Conductores (login por DNI)

| DNI | Pass | Nombre | Datos |
|-----|------|--------|-------|
| 35123456 | 1234 | Pedro López | Auto (Toyota Corolla) + Moto (Honda CG 150), sin exención |
| 36234567 | 1234 | Ana Martínez | Camioneta (Ford Ranger), sin exención |
| 30111222 | 1234 | Carlos Ruiz | Auto (Chevrolet Corsa), OBLEA DISCAPACIDAD |
| 29444555 | 1234 | Lucía Fernández | Auto (VW Gol), FRENTISTA |
| 20999888 | 1234 | Roberto Gómez | Auto (Fiat Cronos), VETERANO MALVINAS |
| 37555666 | 1234 | Eva Torres | BICICLETA (Venzo Urban), sin exención |

### Permisionarios (login por código)

| Código | Pass | Nombre | Cuadra |
|--------|------|--------|--------|
| PER30456789 | 1234 | Juan Pérez | GENERAL GUEMES 100-200 (par+impar) |
| PER28345678 | 1234 | María García | CASEROS 1100-1200 (par) |

### Gestores

| Usuario | Pass | Nombre |
|---------|------|--------|
| gestor1 | gestor123 | Carlos Méndez |

### Admin

| Usuario | Pass | Nombre |
|---------|------|--------|
| admin | admin123 | Administrador |

Además sincroniza **~6,974 espacios** desde datos oficiales IDEMSA y asigna ~46 a Juan (GENERAL GUEMES) y ~37 a María (CASEROS 1100-1200).

## 4. Iniciar el servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abrir **http://localhost:8000**

## 5. Probar con Cloudflare Tunnel (para celular)

```bash
cloudflared tunnel --url http://localhost:8000
```

Genera una URL como `https://<random>.trycloudflare.com` que podés abrir desde cualquier celular.

## 6. (Opcional) App mobile Expo

```bash
cd mobile-app
npm install
npx expo start
```

Escaneá el QR con Expo Go o presioná `a` para Android emulator. Configurá la URL del servidor desde el ícono ⚙️ en la app.

## 7. Credenciales de Mercado Pago (sandbox simulado)

El sistema incluye una simulación de Mercado Pago. No requiere API key real. La página `/conductor/pago-mercadopago/{id}` simula el flujo de pago con confirmación.

Para pagos reales en sandbox, configurar:

```bash
export MP_ACCESS_TOKEN="TEST-<tu-token-real>"
```

## 8. Flujo completo de prueba

### Registro de conductor

1. Ir a `/registro`
2. Completar formulario (DNI, nombre, email, patente, tipo vehículo)
3. Enviar → ver pantalla "Revisá tu email"
4. En la terminal del servidor, copiar el link de verificación
5. Abrir el link → email verificado
6. Ir a `/login` con DNI + contraseña

### Conductor existente

1. Login como `35123456 / 1234` (Pedro, auto)
2. Ir a "Buscar" → texto "GENERAL GUEMES 150" o GPS "Buscar ahora"
3. Ver resultados con mapa IDEMSA embed
4. Seleccionar espacio → check-in automático
5. Ir a checkout → ver timer + costo estimado
6. Elegir "Pagar con Mercado Pago" → página MP simulada → Pagar
7. O esperar que permisionario procese salida en efectivo

### Permisionario

1. Login como `PER30456789 / 1234` (Juan Pérez)
2. Ver panel con sesiones activas + timers
3. Ir a "Espacios" → ver mapa de espacios
4. Ir a "Cuadra" → ver detalles de cuadra asignada
5. Ir a "Ingreso" → registrar patente manualmente
6. Ir a "Salida" → procesar salida (efectivo o MP)

### Gestor

1. Login como `gestor1 / gestor123`
2. Ver dashboard con estadísticas
3. CRUD de permisionarios, listado de conductores
4. Sesiones en vivo, reportes, deudas

### Admin

1. Login como `admin / admin123`
2. CRUD completo (conductores, permisionarios, gestores, espacios)
3. Sesiones activas, reportes, deudas
4. Desbloquear/suspender conductores

## 9. Estructura de archivos importante

```
estacionamiento/
├── app/
│   ├── main.py              # 2368 líneas — TODO el backend
│   ├── models.py            # 10 modelos SQLAlchemy
│   ├── schemas.py           # Schemas Pydantic
│   ├── database.py          # Conexión async SQLite
│   ├── auth.py              # JWT + bcrypt
│   ├── auth_routes.py       # Login + registro + verificación email
│   ├── deps.py              # Dependencias (get_current_user, require_role)
│   ├── qr_utils.py          # Generación QR
│   ├── mercado_pago.py      # Integración MP (simulada)
│   ├── mapa_data.py         # Calles del centro
│   ├── idemsa_data.py       # Sincronización GIS IDEMSA
│   └── templates/           # 30+ templates Jinja2
├── mobile-app/              # Expo React Native
├── docs/                    # Documentación
├── seed.py                  # Datos de prueba
├── requirements.txt
└── README.md
```

## 10. Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `JWT_SECRET` | `estacionamiento-salta-secret-key-2024` | Secreto JWT |
| `MP_ACCESS_TOKEN` | `TEST-1234567890-...` | Token MP sandbox |
| `BASE_URL` | `http://localhost:8000` | URL base para QR |

## Troubleshooting

**Error `bcrypt` al iniciar:**
```bash
pip install bcrypt==4.0.1
```

**Error de base de datos (tabla no existe):**
```bash
rm estacionamiento.db*
python seed.py
```

**Error de conexión al sincronizar IDEMSA:**
El sistema intenta descargar datos de IDEMSA al iniciar. Si no hay internet, usa datos cacheados o genera espacios de prueba.

**No se puede escanear QR desde la web:**
La cámara web requiere HTTPS (excepto localhost). Usá Cloudflare Tunnel para probar desde el celular, o usá la app mobile Expo con escáner nativo.
