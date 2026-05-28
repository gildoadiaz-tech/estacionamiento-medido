import os
import httpx
import json

MP_ACCESS_TOKEN = os.getenv(
    "MP_ACCESS_TOKEN",
    "TEST-1234567890-123456-abc123def456",
)


async def crear_preferencia_pago(monto: float, concepto: str, conductor_email: str) -> str:
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "items": [
            {
                "title": concepto,
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": monto,
            }
        ],
        "payer": {"email": conductor_email},
        "back_urls": {
            "success": "http://localhost:8000/pago/success",
            "failure": "http://localhost:8000/pago/failure",
            "pending": "http://localhost:8000/pago/pending",
        },
        "auto_return": "approved",
        "binary_mode": True,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.mercadopago.com/checkout/preferences",
            headers=headers,
            json=payload,
        )
        data = resp.json()
        return data.get("init_point", data.get("sandbox_init_point", ""))


async def procesar_pago_webhook(payment_id: str) -> dict:
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers=headers,
        )
        return resp.json()
