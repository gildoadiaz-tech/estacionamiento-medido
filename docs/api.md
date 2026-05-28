# Documentación de la API

La API corre en `http://localhost:8000`. La documentación interactiva (Swagger)
está disponible en `/docs`.

---

## `POST /api/permisionarios`

Registrar un permisionario.

```json
{
  "nombre": "Juan Pérez",
  "email": "juan@ejemplo.com",
  "telefono": "1155551234"
}
```

**Response:** `201 Created`

```json
{
  "id": 1,
  "nombre": "Juan Pérez",
  "email": "juan@ejemplo.com",
  "telefono": "1155551234"
}
```

---

## `POST /api/conductores`

Registrar un conductor.

---

## `POST /api/espacios`

Crear un espacio de estacionamiento.

```json
{
  "ubicacion": "Av. Corrientes 1234",
  "permisionario_id": 1,
  "precio_por_hora": 50.0
}
```

---

## `POST /api/checkin`

Registrar entrada.

```json
{
  "espacio_id": 1,
  "conductor_id": 1
}
```

**Response:**

```json
{
  "sesion_id": 1,
  "hora_inicio": "2026-05-28T14:30:00Z",
  "qr_salida": "data:image/png;base64,..."
}
```

El `qr_salida` es la imagen en base64 que el conductor debe guardar para
escanear al retirarse.

---

## `POST /api/checkout`

Registrar salida y obtener link de pago.

```json
{
  "sesion_id": 1
}
```

**Response:**

```json
{
  "sesion_id": 1,
  "horas": 2.5,
  "costo_total": 125.0,
  "link_pago": "https://sandbox.mercadopago.com.ar/..."
}
```

---

## `POST /api/reservas`

Solicitar una reserva.

```json
{
  "espacio_id": 1,
  "conductor_id": 1,
  "hora_inicio": "2026-05-29T10:00:00Z",
  "hora_fin": "2026-05-29T12:00:00Z"
}
```

---

## `GET /api/reservas/pendientes/{permisionario_id}`

Obtener reservas pendientes de aprobación.

---

## `POST /api/reservas/aprobar`

Aprobar o rechazar una reserva.

```json
{
  "reserva_id": 1,
  "aprobar": true
}
```

---

## `GET /api/espacios`

Listar todos los espacios disponibles.
