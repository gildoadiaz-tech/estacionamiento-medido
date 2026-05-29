import httpx
import json
import re
import os

IDEMSA_BASE = "https://idemsa.municipalidadsalta.gob.ar/visor/maps/data"
CACHE_DIR = "/tmp/idemsa_cache"

DATA_FILES = {
    "estacionamiento_medido": f"{IDEMSA_BASE}/estacionamiento_medido_Oct2024.js",
    "estacionamiento_prohibido": f"{IDEMSA_BASE}/estacionamiento_prohibido_Oct2024.js",
    "estacionamiento_libre": f"{IDEMSA_BASE}/estacionamiento_libre_Oct2024.js",
}

TIPO_MAP = {
    "estacionamiento_medido": "estacionamiento_medido",
    "estacionamiento_prohibido": "prohibido_estacionar",
    "estacionamiento_libre": "estacionamiento_libre",
}

COLOR_MAP = {
    "estacionamiento_medido": "#22c55e",
    "estacionamiento_prohibido": "#ef4444",
    "estacionamiento_libre": "#3b82f6",
}


def _extract_json(js_text: str) -> dict | None:
    match = re.search(r"\{[^{]*\"type\":\s*\"FeatureCollection\"", js_text, re.DOTALL)
    if not match:
        return None
    start = match.start()
    rest = js_text[start:]
    depth = 0
    for i, ch in enumerate(rest):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                raw = rest[: i + 1]
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None
    return None


def _fetch_js(url: str) -> str | None:
    try:
        r = httpx.get(url, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def _feature_to_calle(feature: dict, tipo: str) -> dict | None:
    props = feature.get("properties", {}) or {}
    geo = feature.get("geometry", {}) or {}
    if geo.get("type") != "LineString":
        return None
    coords = geo.get("coordinates", [])
    if len(coords) < 2:
        return None
    puntos = [[lat, lng] for lng, lat in coords]
    nombre = (props.get("Name") or "").strip()
    return {
        "nombre": nombre,
        "tipo": TIPO_MAP.get(tipo, tipo),
        "puntos": puntos,
        "color": COLOR_MAP.get(tipo, "#6b7280"),
        "altura": props.get("ALTURA") or props.get("Altura") or "",
        "mano": props.get("MANO") or props.get("mano_prohibida") or "",
        "orientacion": props.get("ORIENTACION") or props.get("Orientacion") or "",
    }


def fetch_all_calles() -> list[dict]:
    all_calles = []
    for tipo, url in DATA_FILES.items():
        js = _fetch_js(url)
        if not js:
            print(f"Warning: could not fetch {tipo}")
            continue
        data = _extract_json(js)
        if not data:
            print(f"Warning: could not parse JSON from {tipo}")
            continue
        features = data.get("features", [])
        for f in features:
            calle = _feature_to_calle(f, tipo)
            if calle:
                all_calles.append(calle)
    return all_calles


def _haversine(lat1, lng1, lat2, lng2):
    import math
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _interpolar_puntos(p1, p2, paso_m=7):
    lat1, lng1 = p1
    lat2, lng2 = p2
    dist = _haversine(lat1, lng1, lat2, lng2)
    if dist < paso_m:
        return [(lat1, lng1)]
    n = int(dist / paso_m)
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((lat1 + (lat2 - lat1) * t, lng1 + (lng2 - lng1) * t))
    return pts


def generar_espacios_desde_calles(calles: list[dict], paso_m=7) -> list[dict]:
    espacios = []
    for c in calles:
        if c["tipo"] != "estacionamiento_medido":
            continue
        pts = c["puntos"]
        todos = []
        for i in range(len(pts) - 1):
            interp = _interpolar_puntos(pts[i], pts[i + 1], paso_m)
            if i > 0 and interp:
                interp = interp[1:]
            todos.extend(interp)
        for lat, lng in todos:
            espacios.append({
                "id": len(espacios) + 1,
                "calle": c["nombre"],
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "tarifa": 600,
                "tipo": "estacionamiento_medido",
                "altura": c.get("altura", ""),
                "mano": c.get("mano", ""),
            })
    return espacios


def get_espacios_cached() -> list[dict]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, "idemsa_espacios.json")
    try:
        if os.path.exists(cache_path):
            mtime = os.path.getmtime(cache_path)
            age = __import__("time").time() - mtime
            if age < 3600:
                with open(cache_path) as f:
                    return json.load(f)
    except Exception:
        pass
    calles = get_all_calles_cached()
    espacios = generar_espacios_desde_calles(calles)
    try:
        with open(cache_path, "w") as f:
            json.dump(espacios, f)
    except Exception:
        pass
    return espacios


def get_all_calles_cached() -> list[dict]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, "idemsa_calles.json")
    try:
        if os.path.exists(cache_path):
            mtime = os.path.getmtime(cache_path)
            age = __import__("time").time() - mtime
            if age < 3600:
                with open(cache_path) as f:
                    return json.load(f)
    except Exception:
        pass
    calles = fetch_all_calles()
    try:
        with open(cache_path, "w") as f:
            json.dump(calles, f)
    except Exception:
        pass
    return calles


async def sync_espacios_db(db_session):
    """Sincroniza los espacios generados de IDEMSA en la tabla Espacio de la DB."""
    from app.models import Espacio
    from sqlalchemy import select, func

    result = await db_session.execute(select(func.count(Espacio.id)))
    count = result.scalar()
    if count and count > 200:
        return  # ya hay datos

    calles = get_all_calles_cached()
    espacios = generar_espacios_desde_calles(calles)

    batch = []
    for i, e in enumerate(espacios):
        altura_val = e.get("altura", "") or ""
        ubicacion = f"{e['calle']} {altura_val}".strip() if altura_val else e["calle"]
        try:
            numero_int = int(altura_val) if altura_val else None
        except ValueError:
            numero_int = None
        batch.append(Espacio(
            ubicacion=ubicacion,
            precio_por_hora=e["tarifa"],
            disponible=True,
            lat=e["lat"],
            lng=e["lng"],
            numero=numero_int,
        ))
        if len(batch) >= 500:
            db_session.add_all(batch)
            await db_session.commit()
            batch = []
    if batch:
        db_session.add_all(batch)
        await db_session.commit()
    print(f"Synced {len(espacios)} spaces from IDEMSA into DB")
