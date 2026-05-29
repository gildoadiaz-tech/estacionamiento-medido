import os
import hmac
import hashlib
import httpx

MP_ACCESS_TOKEN = os.getenv(
    "MP_ACCESS_TOKEN",
    "TEST-1234567890-123456-abc123def456",
)
MP_CLIENT_SECRET = os.getenv("MP_CLIENT_SECRET", "")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def verificar_firma_webhook(body: bytes, x_signature: str) -> bool:
    """Validate Mercado Pago webhook signature using HMAC-SHA256."""
    if not MP_CLIENT_SECRET or not x_signature:
        return False
    try:
        parts = {k: v for k, v in (p.split("=") for p in x_signature.split(","))}
        ts = parts.get("ts", "")
        v1 = parts.get("v1", "")
        if not ts or not v1:
            return False
        data_id = ""
        import json
        try:
            parsed = json.loads(body)
            data_id = parsed.get("data", {}).get("id", "")
        except Exception:
            pass
        manifest = f"id:{data_id};request-id:;ts:{ts};"
        expected = hmac.new(MP_CLIENT_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, v1)
    except Exception:
        return False


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
            "success": f"{BASE_URL}/pago/success",
            "failure": f"{BASE_URL}/pago/failure",
            "pending": f"{BASE_URL}/pago/pending",
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
            init_point = data.get("init_point") or data.get("sandbox_init_point", "")
            preference_id = data.get("id", "")
            if init_point:
                return {
                    "init_point": init_point,
                    "preference_id": preference_id,
                }
        except Exception:
            pass

    # Fallback: simulated Mercado Pago
    sim_id = f"SIM_{external_reference}" if external_reference else f"SIM_{os.urandom(4).hex()}"
    return {
        "init_point": f"{BASE_URL}/conductor/pago-mercadopago/{external_reference}",
        "preference_id": sim_id,
        "simulated": True,
    }


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
