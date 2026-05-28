import os
import httpx

MP_ACCESS_TOKEN = os.getenv(
    "MP_ACCESS_TOKEN",
    "TEST-1234567890-123456-abc123def456",
)


async def crear_preferencia_pago(
    monto: float,
    concepto: str,
    conductor_email: str,
    notification_url: str = "",
    external_reference: str = "",
) -> dict:
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
                "unit_price": float(monto),
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
    if notification_url:
        payload["notification_url"] = notification_url
    if external_reference:
        payload["external_reference"] = external_reference

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://api.mercadopago.com/checkout/preferences",
                headers=headers,
                json=payload,
                timeout=15,
            )
            data = resp.json()
            return {
                "init_point": data.get("init_point") or data.get("sandbox_init_point", ""),
                "preference_id": data.get("id", ""),
            }
        except Exception as e:
            return {"init_point": "", "preference_id": "", "error": str(e)}


async def procesar_pago_webhook(payment_id: str) -> dict:
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers=headers,
                timeout=15,
            )
            return resp.json()
        except Exception:
            return {"status": "error"}
