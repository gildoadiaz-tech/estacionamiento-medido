# 🅿️ Estacionamiento Medido

Sistema de estacionamiento inteligente con gestión de espacios por cuadra, reservas con aprobación de permisionarios y pagos integrados con Mercado Pago.

## 🚀 Inicio rápido

```bash
git clone <repo-url>
cd estacionamiento
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abrir http://localhost:8000

## 🌐 Exponer con Cloudflare Tunnel (gratis)

```bash
cloudflared tunnel --url http://localhost:8000
```

Genera una URL como `https://random.trycloudflare.com` para probar desde cualquier celular.

## 🏗️ Arquitectura

```
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│  Conductor   │────▶│   FastAPI    │────▶│  SQLite  │
│  (celular)   │     │  (backend)   │     │   (DB)   │
└─────────────┘     └──────┬───────┘     └──────────┘
                           │
                    ┌──────▼───────┐
                    │ Mercado Pago │
                    │  (sandbox)   │
                    └──────────────┘
```

### Flujo principal

1. **Permisionario** genera QR por cada espacio de su cuadra
2. **Conductor** escanea QR de entrada → se registra hora de inicio
3. Al retirarse, escanea QR de salida → se calcula tiempo y costo
4. Paga vía Mercado Pago (link de pago generado automáticamente)
5. **Reservas**: conductor solicita, permisionario aprueba/ rechaza

## 🧱 Stack técnico

| Capa        | Tecnología               |
|-------------|--------------------------|
| Backend     | Python + FastAPI         |
| DB          | SQLite (aiosqlite)       |
| QR          | qrcode (PIL)             |
| Pagos       | Mercado Pago API (sandbox)|
| Frontend    | HTML + Tailwind (CDN)    |
| Tunel       | Cloudflare Tunnel        |

## 📁 Estructura del proyecto

```
estacionamiento/
├── app/
│   ├── main.py           # Rutas API + HTML
│   ├── models.py         # Modelos SQLAlchemy
│   ├── schemas.py        # Schemas Pydantic
│   ├── database.py       # Conexión DB
│   ├── qr_utils.py       # Generación de QR
│   ├── mercado_pago.py   # Integración MP
│   └── templates/        # Jinja2 templates
├── docs/
│   ├── index.md
│   ├── arquitectura.md
│   ├── api.md
│   └── setup.md
├── README.md
└── requirements.txt
```

## 🔌 Endpoints de la API

| Método | Ruta                        | Descripción                     |
|--------|-----------------------------|---------------------------------|
| POST   | `/api/checkin`              | Registrar entrada               |
| POST   | `/api/checkout`             | Finalizar y calcular costo      |
| POST   | `/api/reservas`             | Crear solicitud de reserva      |
| GET    | `/api/reservas/pendientes/` | Reservas pendientes por perm.   |
| POST   | `/api/reservas/aprobar`     | Aprobar/rechazar reserva        |
| POST   | `/api/permisionarios`       | Registrar permisionario         |
| POST   | `/api/conductores`          | Registrar conductor             |
| POST   | `/api/espacios`             | Crear espacio de estacionamiento|

## 🧪 Datos de prueba

```bash
# Activar venv y arrancar
source venv/bin/activate
uvicorn app.main:app --reload
```

Luego crear datos desde la consola:

```python
# python seed.py (proximamente)
```

## 📄 Licencia

MIT
