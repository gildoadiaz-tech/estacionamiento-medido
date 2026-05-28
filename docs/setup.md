# Guía de instalación y puesta en marcha

## Requisitos

- Python 3.10+
- Git
- (Opcional) cloudflared para exponer localhost

## 1. Clonar el repositorio

```bash
git clone <repo-url>
cd estacionamiento
```

## 2. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

## 3. Configurar variables de entorno (opcional)

```bash
export MP_ACCESS_TOKEN="TEST-xxxx-xxxx"   # Token de Mercado Pago sandbox
export BASE_URL="http://localhost:8000"    # URL base para QR
```

## 4. Iniciar el servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abrir http://localhost:8000

## 5. Cargar datos de prueba

Ejecutar el seed script:

```bash
python seed.py
```

## 6. Exponer con Cloudflare Tunnel (opcional)

```bash
cloudflared tunnel --url http://localhost:8000
```

## 7. Credenciales de Mercado Pago (sandbox)

Para pagos de prueba usar:

- **Tarjeta**: 5031 7557 3453 0604
- **CVV**: 123
- **Vencimiento**: 11/25
- **Nombre**: APRUEBA (para pagos exitosos) / RECHAZA (para pagos rechazados)

Más info: https://www.mercadopago.com.ar/developers/es/docs/your-integrations/test/cards

## 8. Probar el flujo completo

1. Abrir http://localhost:8000
2. Ir al panel del permisionario (botón "Panel Permisionario")
3. Crear un permisionario via API
4. Crear espacios
5. Escanear QR de entrada (simulado)
6. Cerrar sesión y pagar
