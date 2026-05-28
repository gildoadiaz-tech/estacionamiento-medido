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
# venv\Scripts\activate    # Windows

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

| Usuario | Pass | Rol | Datos |
|---------|------|-----|-------|
| admin | admin123 | Admin | — |
| juan | 1234 | Permisionario | Calle: Gral. Güemes |
| maria | 1234 | Permisionario | Calle: Caseros |
| pedro | 1234 | Conductor | Patente: AB123CD |
| ana | 1234 | Conductor | Patente: BC456EF |

Además crea 6 espacios de prueba + sincroniza **6,974 espacios** desde IDEMSA.

## 4. Iniciar el servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abrir **http://localhost:8000**

## 5. Probar con Cloudflare Tunnel (para celular)

```bash
# Instalar cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
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

## 7. Credenciales de Mercado Pago (sandbox)

Para pagos de prueba usar:

| Campo | Valor |
|-------|-------|
| Tarjeta | `5031 7557 3453 0604` |
| CVV | `123` |
| Vencimiento | `11/25` |
| Nombre | `APRUEBA` (éxito) / `RECHAZA` (rechazo) |

Más info: https://www.mercadopago.com.ar/developers/es/docs/your-integrations/test/cards

### Configurar token de MP

El token por defecto es un dummy. Para probar pagos reales en sandbox:

```bash
export MP_ACCESS_TOKEN="TEST-<tu-token-real>"
```

## 8. Flujo completo de prueba

### Conductor

1. Abrir `http://localhost:8000/login`
2. Login como `pedro / 1234`
3. Ver home con sesión activa (si la hay)
4. Ir a "Escanear QR" → escanear QR del permisionario Juan
5. Elegir método de pago (efectivo o MP)
6. Presionar "Estacionar"
7. Esperar a que el permisionario cobre (si es efectivo)
8. Escanear QR de salida para finalizar

### Permisionario

1. Login como `juan / 1234`
2. Ver panel con sesiones activas
3. Presionar "Cobrar efectivo" en una sesión
4. Mostrar QR de salida al conductor

### Admin

1. Login como `admin / admin123`
2. Ver dashboard con estadísticas
3. Ir a "Penalizaciones" para ver/condonar/verificar no-show

## 9. Estructura de archivos importante

```
estacionamiento/
├── app/
│   ├── main.py              # 1297 líneas — TODO el backend
│   ├── models.py            # Modelos SQLAlchemy
│   ├── schemas.py           # Schemas Pydantic
│   ├── database.py          # Conexión async SQLite
│   ├── auth.py              # JWT + bcrypt
│   ├── auth_routes.py       # Login endpoint
│   ├── deps.py              # Dependencias
│   ├── qr_utils.py          # Generación QR
│   ├── mercado_pago.py      # Integración MP
│   ├── mapa_data.py         # Calles del centro
│   ├── idemsa_data.py       # Sincronización GIS
│   └── templates/           # 26 templates Jinja2
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
rm estacionamiento.db
python seed.py
```

**Error de conexión al sincronizar IDEMSA:**
El sistema intenta descargar datos de IDEMSA al iniciar. Si no hay internet, usa datos cacheados o genera espacios de prueba.

**No se puede escanear QR desde la web:**
La cámara web requiere HTTPS (excepto localhost). Usá Cloudflare Tunnel para probar desde el celular, o usá la app mobile Expo con escáner nativo.
