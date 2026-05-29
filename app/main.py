import asyncio
import csv
import io
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import os

from app.database import init_db, get_db, async_session
from app.models import (
    Permisionario, Conductor, Espacio, Admin,
    SesionEstacionamiento, Reserva, EstadoReserva,
    PatenteSecundaria, Favorito,
)
from app.schemas import (
    CheckInRequest, CheckInPorPermRequest, CheckInResponse, CheckOutRequest, CheckOutResponse,
    ReservaCreate, ReservaOut, ReservaAprobar, ElegirPagoRequest, PasswordChangeRequest,
    PermisionarioCreate, PermisionarioUpdate, PermisionarioOut,
    ConductorCreate, ConductorOut, ConductorUpdate, ConductorStatus,
    EspacioCreate, EspacioUpdate, EspacioOut, PenalizacionOut,
    PatenteSecundariaOut, FavoritoOut, FavoritoCreate,
)
from app.qr_utils import generar_qr_base64
from app.mercado_pago import crear_preferencia_pago
from app.mapa_data import CALLES, CENTRO_SALTA
from app.idemsa_data import get_all_calles_cached, get_espacios_cached, sync_espacios_db
from app.auth_routes import router as auth_router
from app.deps import get_current_user, require_role
from app.auth import hash_password, verify_password

_espacios_cache = None

def _get_espacios():
    global _espacios_cache
    if _espacios_cache is None:
        _espacios_cache = get_espacios_cached()
    return _espacios_cache


_no_show_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as session:
        await sync_espacios_db(session)
    global _no_show_task
    _no_show_task = asyncio.create_task(tarea_no_show())
    yield
    if _no_show_task:
        _no_show_task.cancel()


app = FastAPI(title="Estacionamiento Medido", lifespan=lifespan)

app.include_router(auth_router)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ─── HELPERS ────────────────────────────────────────

def now_naive():
    return datetime.utcnow()


def calcular_costo_estacionamiento(inicio: datetime, fin: datetime) -> float:
    """
    Lun-Vie: cobra 7-21hs | Sáb: 7-14hs | Dom: gratis | Noche: gratis
    Si pasa a otro día se reinicia el conteo diario.
    """
    if inicio >= fin:
        return 0.0
    total = 0.0
    current = inicio
    while current < fin:
        wd = current.weekday()
        if wd == 6:
            current = current.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        apertura, cierre = (7, 14) if wd == 5 else (7, 21)
        day_start = current.replace(hour=apertura, minute=0, second=0, microsecond=0)
        day_end = current.replace(hour=cierre, minute=0, second=0, microsecond=0)
        if current < day_start:
            current = day_start
            continue
        if current >= day_end:
            current = day_end + timedelta(days=1)
            continue
        chunk = min(fin, day_end)
        horas = (chunk - current).total_seconds() / 3600
        total += horas * PRECIO_POR_HORA
        current = chunk
    return round(total, 2)


def sesion_to_dict(s):
    return {
        "id": s.id, "espacio_id": s.espacio_id, "conductor_id": s.conductor_id,
        "hora_inicio": s.hora_inicio.isoformat() if s.hora_inicio else None,
        "hora_fin": s.hora_fin.isoformat() if s.hora_fin else None,
        "costo_total": s.costo_total, "pagado": s.pagado, "pago_id": s.pago_id,
        "metodo_pago": s.metodo_pago, "lista_para_salir": s.lista_para_salir,
    }


def reserva_to_dict(r):
    return {
        "id": r.id, "espacio_id": r.espacio_id, "conductor_id": r.conductor_id,
        "hora_inicio": r.hora_inicio.isoformat() if r.hora_inicio else None,
        "hora_fin": r.hora_fin.isoformat() if r.hora_fin else None,
        "estado": r.estado.value if r.estado else None,
        "creada_en": r.creada_en.isoformat() if r.creada_en else None,
        "ubicacion": r.espacio.ubicacion if r.espacio else None,
        "usada": r.usada,
        "checkin_time": r.checkin_time.isoformat() if r.checkin_time else None,
    }


# ─── PENALIZACIONES ────────────────────────────────

PRECIO_POR_HORA = 600.0  # $600/h fijo
HORARIO_CIERRE = 21  # lun-vie cierra 21hs
HORARIO_CIERRE_SAB = 14  # sáb cierra 14hs
TOLERANCIA_MINUTOS = 5
MAX_PENALIZACIONES_MES = 5
DEUDA_MAXIMA = 10000.0
MULTA_BLOQUEO = 5000.0


async def verificar_bloqueo(conductor_id: int, db: AsyncSession) -> dict:
    """Verifica si un conductor está bloqueado y por qué."""
    from app.models import Conductor, Penalizacion
    from sqlalchemy import select, func

    cond = await db.get(Conductor, conductor_id)
    if not cond:
        return {"bloqueado": True, "motivo": "Conductor no encontrado"}

    if cond.bloqueado:
        return {"bloqueado": True, "motivo": "Bloqueado por el sistema"}

    if cond.saldo_deudor and cond.saldo_deudor >= DEUDA_MAXIMA:
        cond.bloqueado = True
        await db.commit()
        return {"bloqueado": True, "motivo": f"Deuda superior a ${DEUDA_MAXIMA:,.0f}"}

    # Contar penalizaciones del mes
    now = now_naive()
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(Penalizacion.id))
        .where(Penalizacion.conductor_id == conductor_id)
        .where(Penalizacion.fecha >= inicio_mes)
    )
    count = result.scalar() or 0
    if count >= MAX_PENALIZACIONES_MES:
        cond.bloqueado = True
        await db.commit()
        return {"bloqueado": True, "motivo": f"Demasiadas penalizaciones este mes ({count})"}

    return {"bloqueado": False, "motivo": None}


async def penalizar_conductor(conductor_id: int, reserva_id: int | None, monto: float, motivo: str, db: AsyncSession):
    """Crea una penalización y actualiza la deuda del conductor."""
    from app.models import Penalizacion, Conductor

    pen = Penalizacion(
        conductor_id=conductor_id,
        reserva_id=reserva_id,
        monto=monto,
        motivo=motivo,
    )
    db.add(pen)

    cond = await db.get(Conductor, conductor_id)
    if cond:
        cond.saldo_deudor = (cond.saldo_deudor or 0) + monto
    await db.commit()
    return pen


async def verificar_no_show_periodico(db: AsyncSession):
    """Penaliza reservas aprobadas cuya hora_fin pasó y nunca se usaron."""
    from app.models import Penalizacion, Conductor

    ahora = now_naive()
    result = await db.execute(
        select(Reserva)
        .where(Reserva.estado == EstadoReserva.aprobada)
        .where(Reserva.usada == False)
        .where(Reserva.hora_fin < ahora)
    )
    vencidas = result.scalars().all()
    penalizadas = 0
    for r in vencidas:
        r.usada = True
        r.estado = EstadoReserva.rechazada
        monto = round(PRECIO_POR_HORA * 0.1, 2)
        await penalizar_conductor(
            conductor_id=r.conductor_id,
            reserva_id=r.id,
            monto=monto,
            motivo=f"No-show: reserva #{r.id} venció el {r.hora_fin.strftime('%d/%m %H:%M')} sin check-in",
            db=db,
        )
        penalizadas += 1
    return penalizadas


async def tarea_no_show():
    """Ejecuta verificar_no_show cada 60 segundos en background."""
    while True:
        try:
            async with async_session() as db:
                n = await verificar_no_show_periodico(db)
                if n:
                    print(f"[no-show] {n} reserva(s) penalizada(s)")
        except Exception as e:
            print(f"[no-show] error: {e}")
        await asyncio.sleep(60)


# ─── AUTH ───────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {})


@app.get("/manifest.json")
async def manifest():
    return RedirectResponse(url="/static/manifest.json")


@app.get("/sw.js")
async def service_worker():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(static_dir, "service-worker.js"), media_type="application/javascript")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/login")


# ═══════════════════════════════════════════════════════
# PANEL 1: CONDUCTOR APP (mobile-first)
# ═══════════════════════════════════════════════════════

@app.get("/conductor", response_class=HTMLResponse)
async def conductor_home(request: Request):
    return templates.TemplateResponse(request, "conductor/index.html", {})


@app.get("/conductor/checkin", response_class=HTMLResponse)
async def conductor_checkin(request: Request):
    return templates.TemplateResponse(request, "conductor/checkin.html", {"conductor_id": 1})


@app.get("/conductor/checkin/perm/{perm_id}", response_class=HTMLResponse)
async def conductor_checkin_por_perm(request: Request, perm_id: int, db: AsyncSession = Depends(get_db)):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")
    return templates.TemplateResponse(request, "conductor/checkin_auto.html", {
        "perm": perm,
    })


@app.get("/conductor/checkout/{sesion_id}", response_class=HTMLResponse)
async def conductor_checkout(request: Request, sesion_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.id == sesion_id)
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(404, "Sesión no encontrada")
    result = await db.execute(select(Espacio).where(Espacio.id == sesion.espacio_id))
    espacio = result.scalar_one()
    result = await db.execute(select(Conductor).where(Conductor.id == sesion.conductor_id))
    conductor = result.scalar_one_or_none()
    # Find permisionario for this space
    perm = None
    if espacio and espacio.permisionario_id:
        perm = await db.get(Permisionario, espacio.permisionario_id)
    return templates.TemplateResponse(request, "conductor/checkout.html", {
        "sesion": sesion, "espacio": espacio, "conductor": conductor, "perm": perm,
    })


@app.get("/conductor/reservar", response_class=HTMLResponse)
async def conductor_reservar(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio))
    espacios = result.scalars().all()
    return templates.TemplateResponse(request, "conductor/reservar.html", {"espacios": espacios})


@app.get("/conductor/mis-reservas", response_class=HTMLResponse)
async def conductor_mis_reservas(request: Request):
    return templates.TemplateResponse(request, "conductor/mis_reservas.html", {})


@app.get("/conductor/perfil", response_class=HTMLResponse)
async def conductor_perfil(request: Request):
    return templates.TemplateResponse(request, "conductor/perfil.html", {})


@app.get("/conductor/historial", response_class=HTMLResponse)
async def conductor_historial(request: Request):
    return templates.TemplateResponse(request, "conductor/historial.html", {})


@app.get("/conductor/mapa", response_class=HTMLResponse)
async def conductor_mapa(request: Request, db: AsyncSession = Depends(get_db)):
    import json
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.hora_fin == None)
    )
    sesiones = result.scalars().all()
    return templates.TemplateResponse(request, "conductor/mapa.html", {
        "calles_json": json.dumps([{
            "nombre": c["nombre"],
            "tipo": c["tipo"].value,
            "tarifa": c["tarifa"],
            "puntos": c["puntos"],
        } for c in CALLES]),
        "espacios_json": json.dumps(_get_espacios()),
        "sesiones_json": json.dumps([sesion_to_dict(s) for s in sesiones]),
    })


@app.get("/api/mapa/cercanos")
async def mapa_cercanos(lat: float, lng: float, radio: float = 300):
    cercanos = []
    for e in _get_espacios():
        if e["tipo"] != "estacionamiento_medido":
            continue
        dist = ((e["lat"] - lat) ** 2 + (e["lng"] - lng) ** 2) ** 0.5 * 111320
        if dist <= radio:
            cercanos.append({**e, "distancia": round(dist, 1)})
    cercanos.sort(key=lambda x: x["distancia"])
    return cercanos[:20]


@app.get("/api/mapa/idemsa-calles")
async def idemsa_calles():
    calles = get_all_calles_cached()
    return calles


# ═══════════════════════════════════════════════════════
# BUSQUEDA DE ESTACIONAMIENTO (GEOCODING + NEAREST)
# ═══════════════════════════════════════════════════════

async def geocodificar(direccion: str) -> tuple[float, float] | None:
    """Convierte dirección a coordenadas usando Nominatim (OSM)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": f"{direccion}, Salta, Argentina", "format": "json", "limit": 1},
                headers={"User-Agent": "EstacionamientoMedido/1.0"},
                timeout=10,
            )
            data = resp.json()
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        pass
    return None


def _normalizar(s: str) -> str:
    """Normaliza texto: lowercase, sin acentos, reemplaza abreviaciones."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace(",", "").replace(".", "").replace("  ", " ").strip()
    replacements = {
        "gral ": "general ", "gral.": "general", "av ": "av. ", "av.": "av. ",
        "san ": "san ", "sta ": "santa ", "dr ": "doctor ", "dr.": "doctor",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    return s


def buscar_calle_en_idemsa(q: str) -> tuple[float, float] | None:
    """Busca la calle directamente en los datos de IDEMSA (fallback offline)."""
    q_norm = _normalizar(q)
    for c in get_all_calles_cached():
        nombre = _normalizar(c.get("nombre", "") or "")
        if q_norm in nombre or nombre in q_norm:
            pts = c.get("puntos", [])
            if pts:
                mid = len(pts) // 2
                return (pts[mid][0], pts[mid][1])
    return None


@app.get("/api/buscar-estacionamiento")
async def buscar_estacionamiento(q: str = "", db: AsyncSession = Depends(get_db)):
    if not q:
        return {"error": "Dirección requerida"}

    coords = await geocodificar(q)

    # Si Nominatim devolvió coordenadas lejos del área IDEMSA, ignorarlas
    if coords:
        lat_c, lng_c = coords
        espacios = _get_espacios()
        if espacios:
            centro_lat = (min(e["lat"] for e in espacios) + max(e["lat"] for e in espacios)) / 2
            centro_lng = (min(e["lng"] for e in espacios) + max(e["lng"] for e in espacios)) / 2
            dist_al_centro = ((lat_c - centro_lat) ** 2 + (lng_c - centro_lng) ** 2) ** 0.5 * 111320
            if dist_al_centro > 5000:
                coords = None

    if not coords:
        coords = buscar_calle_en_idemsa(q)
    if not coords:
        return {"error": "No se pudo encontrar la dirección. Probá con el nombre de una calle (ej: Mitre)"}

    lat, lng = coords

    # Buscar espacios disponibles cercanos (usando IDEMSA in-memory)
    cercanos = []
    for e in _get_espacios():
        if e["tipo"] != "estacionamiento_medido":
            continue
        dist = ((e["lat"] - lat) ** 2 + (e["lng"] - lng) ** 2) ** 0.5 * 111320
        if dist <= 500:
            cercanos.append({**e, "distancia": round(dist, 1)})
    cercanos.sort(key=lambda x: x["distancia"])
    top = cercanos[:10]

    # Cruzar con DB para ver disponibilidad real y precio (match aproximado)
    TOL = 0.00005
    result = []
    for s in top:
        db_esp = await db.execute(
            select(Espacio).where(
                func.abs(Espacio.lat - s["lat"]) < TOL,
                func.abs(Espacio.lng - s["lng"]) < TOL,
            ).limit(1)
        )
        e = db_esp.scalar_one_or_none()
        result.append({
            "calle": s.get("calle", s.get("nombre", "")),
            "lat": s["lat"],
            "lng": s["lng"],
            "distancia": s["distancia"],
            "disponible": e.disponible if e else True,
            "espacio_id": e.id if e else None,
            "precio_por_hora": e.precio_por_hora if e else 600.0,
            "altura": s.get("altura", ""),
        })

    # Agrupar por calle+altura (bloques)
    from collections import defaultdict
    bloques = defaultdict(lambda: {"calle": "", "altura": "", "total": 0, "disponibles": 0, "distancia_min": 9999})
    for r in result:
        key = f"{r['calle']}|{r['altura']}"
        b = bloques[key]
        b["calle"] = r["calle"]
        b["altura"] = r["altura"]
        b["total"] += 1
        if r["disponible"]:
            b["disponibles"] += 1
        if r["distancia"] < b["distancia_min"]:
            b["distancia_min"] = r["distancia"]
            b["lat"] = r["lat"]
            b["lng"] = r["lng"]

    return {
        "consulta": q,
        "destino": {"lat": lat, "lng": lng},
        "resultados": result,
        "bloques": list(bloques.values()),
    }


@app.get("/conductor/buscar", response_class=HTMLResponse)
async def conductor_buscar(request: Request):
    return templates.TemplateResponse(request, "conductor/buscar.html", {})


# ═══════════════════════════════════════════════════════
# PANEL 2: PERMISIONARIO APP (mobile-first)
# ═══════════════════════════════════════════════════════

@app.get("/permisionario", response_class=HTMLResponse)
async def permisionario_home(request: Request):
    return templates.TemplateResponse(request, "permisionario/index.html", {})


@app.get("/permisionario/{perm_id}/panel", response_class=HTMLResponse)
async def permisionario_panel(request: Request, perm_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Permisionario).where(Permisionario.id == perm_id))
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")

    result = await db.execute(select(Espacio).where(Espacio.permisionario_id == perm_id))
    espacios = result.scalars().all()

    return templates.TemplateResponse(request, "permisionario/panel.html", {
        "permisionario": perm, "espacios": espacios,
    })


@app.get("/permisionario/{perm_id}/reservas", response_class=HTMLResponse)
async def permisionario_reservas(request: Request, perm_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Permisionario).where(Permisionario.id == perm_id))
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")
    return templates.TemplateResponse(request, "permisionario/reservas.html", {"permisionario": perm})


@app.get("/permisionario/{perm_id}/qr", response_class=HTMLResponse)
async def permisionario_qr(request: Request, perm_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Permisionario).where(Permisionario.id == perm_id))
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    qr_data = f"{base_url}/conductor/checkin/perm/{perm.id}"
    qr_b64 = generar_qr_base64(qr_data)

    return templates.TemplateResponse(request, "permisionario/qr.html", {
        "permisionario": perm, "qr_b64": qr_b64,
    })


@app.get("/permisionario/{perm_id}/mapa", response_class=HTMLResponse)
async def permisionario_mapa(request: Request, perm_id: int, db: AsyncSession = Depends(get_db)):
    import json
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")
    result = await db.execute(
        select(Espacio).where(Espacio.permisionario_id == perm_id)
    )
    espacios = result.scalars().all()
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.hora_fin == None)
    )
    sesiones = result.scalars().all()
    return templates.TemplateResponse(request, "permisionario/mapa.html", {
        "perm_id": perm_id,
        "calles_json": json.dumps([{
            "nombre": c["nombre"], "tipo": c["tipo"].value,
            "tarifa": c["tarifa"], "puntos": c["puntos"],
        } for c in CALLES]),
        "espacios_json": json.dumps([{
            "id": e.id, "lat": e.lat, "lng": e.lng,
            "ubicacion": e.ubicacion, "precio_por_hora": e.precio_por_hora,
        } for e in espacios]),
        "sesiones_json": json.dumps([sesion_to_dict(s) for s in sesiones]),
    })


# ═══════════════════════════════════════════════════════
# PANEL 3: ADMIN PANEL (web)
# ═══════════════════════════════════════════════════════

@app.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request):
    return templates.TemplateResponse(request, "admin/index.html", {})


@app.get("/admin/permisionarios", response_class=HTMLResponse)
async def admin_permisionarios(request: Request):
    return templates.TemplateResponse(request, "admin/permisionarios.html", {})


@app.get("/admin/conductores", response_class=HTMLResponse)
async def admin_conductores(request: Request):
    return templates.TemplateResponse(request, "admin/conductores.html", {})


@app.get("/admin/espacios", response_class=HTMLResponse)
async def admin_espacios(request: Request):
    return templates.TemplateResponse(request, "admin/espacios.html", {})


@app.get("/admin/sesiones", response_class=HTMLResponse)
async def admin_sesiones(request: Request):
    return templates.TemplateResponse(request, "admin/sesiones.html", {})


@app.get("/admin/reservas", response_class=HTMLResponse)
async def admin_reservas(request: Request):
    return templates.TemplateResponse(request, "admin/reservas.html", {})


@app.get("/admin/reportes", response_class=HTMLResponse)
async def admin_reportes(request: Request):
    return templates.TemplateResponse(request, "admin/reportes.html", {})


@app.get("/admin/sesiones-vivo", response_class=HTMLResponse)
async def admin_sesiones_vivo_page(request: Request):
    return templates.TemplateResponse(request, "admin/sesiones_vivo.html", {})


@app.get("/admin/penalizaciones", response_class=HTMLResponse)
async def admin_penalizaciones(request: Request):
    return templates.TemplateResponse(request, "admin/penalizaciones.html", {})


# ═══════════════════════════════════════════════════════
# API: PERMISIONARIOS
# ═══════════════════════════════════════════════════════

@app.get("/api/permisionarios", response_model=list[PermisionarioOut])
async def listar_permisionarios(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Permisionario))
    return result.scalars().all()


@app.post("/api/permisionarios", response_model=PermisionarioOut)
async def crear_permisionario(data: PermisionarioCreate, db: AsyncSession = Depends(get_db)):
    perm = Permisionario(**data.model_dump())
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return perm


# ═══════════════════════════════════════════════════════
# API: CONDUCTORES
# ═══════════════════════════════════════════════════════

@app.get("/api/conductores", response_model=list[ConductorOut])
async def listar_conductores(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conductor))
    return result.scalars().all()


@app.get("/api/conductores/{conductor_id}/status")
async def conductor_status(conductor_id: int, db: AsyncSession = Depends(get_db)):
    from app.models import Penalizacion
    from sqlalchemy import func

    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404, "Conductor no encontrado")

    now = now_naive()
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(Penalizacion.id))
        .where(Penalizacion.conductor_id == conductor_id)
        .where(Penalizacion.fecha >= inicio_mes)
    )
    pen_mes = result.scalar() or 0

    # Verificar bloqueo por deuda
    estado = await verificar_bloqueo(conductor_id, db)

    return {
        "bloqueado": estado["bloqueado"],
        "motivo_bloqueo": estado["motivo"],
        "saldo_deudor": cond.saldo_deudor or 0,
        "penalizaciones_mes": pen_mes,
        "max_penalizaciones": MAX_PENALIZACIONES_MES,
        "deuda_maxima": DEUDA_MAXIMA,
        "multa_bloqueo": MULTA_BLOQUEO,
    }


@app.get("/api/conductores/{conductor_id}/penalizaciones")
async def conductor_penalizaciones(conductor_id: int, db: AsyncSession = Depends(get_db)):
    from app.models import Penalizacion
    result = await db.execute(
        select(Penalizacion)
        .where(Penalizacion.conductor_id == conductor_id)
        .order_by(Penalizacion.fecha.desc())
    )
    return result.scalars().all()


@app.post("/api/conductores/{conductor_id}/pagar-multa")
async def pagar_multa(conductor_id: int, db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    if not cond.bloqueado:
        raise HTTPException(400, "No estás bloqueado")

    # Simular pago de multa
    cond.bloqueado = False
    cond.saldo_deudor = max((cond.saldo_deudor or 0) - MULTA_BLOQUEO, 0)
    await db.commit()
    return {"ok": True, "mensaje": f"Multa de ${MULTA_BLOQUEO:,.0f} pagada. Ya podés usar el sistema."}


# ═══════════════════════════════════════════════════════
# API: ADMIN - PENALIZACIONES Y BLOQUEOS
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/penalizaciones")
async def admin_listar_penalizaciones(db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    from app.models import Penalizacion, Conductor
    result = await db.execute(
        select(Penalizacion).order_by(Penalizacion.fecha.desc()).limit(200)
    )
    pens = result.scalars().all()
    # Hydrate conductor names
    cond_ids = list({p.conductor_id for p in pens})
    conds = {}
    if cond_ids:
        r = await db.execute(select(Conductor).where(Conductor.id.in_(cond_ids)))
        for c in r.scalars().all():
            conds[c.id] = c.nombre
    return [
        {
            "id": p.id,
            "conductor_id": p.conductor_id,
            "conductor_nombre": conds.get(p.conductor_id, "?"),
            "motivo": p.motivo,
            "monto": p.monto,
            "fecha": p.fecha.isoformat(),
        }
        for p in pens
    ]


@app.get("/api/admin/penalizaciones/stats")
async def admin_penalizaciones_stats(db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    from app.models import Penalizacion, Conductor
    from sqlalchemy import func
    now = now_naive()
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    r1 = await db.execute(
        select(func.count(Penalizacion.id))
        .where(Penalizacion.fecha >= inicio_mes)
    )
    total_pen = r1.scalar() or 0
    r2 = await db.execute(
        select(func.coalesce(func.sum(Penalizacion.monto), 0))
        .where(Penalizacion.fecha >= inicio_mes)
    )
    monto_pen = r2.scalar() or 0
    r3 = await db.execute(
        select(func.count(Conductor.id)).where(Conductor.bloqueado == True)
    )
    total_bloq = r3.scalar() or 0
    r4 = await db.execute(
        select(func.coalesce(func.sum(Conductor.saldo_deudor), 0))
    )
    total_deuda = float(r4.scalar() or 0)
    return {
        "total_penalizaciones_mes": total_pen,
        "monto_penalizaciones_mes": float(monto_pen),
        "total_bloqueados": total_bloq,
        "deuda_total": total_deuda,
    }


@app.post("/api/admin/penalizaciones/{penalizacion_id}/waiver")
async def admin_waiver_penalizacion(penalizacion_id: int, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    from app.models import Penalizacion
    pen = await db.get(Penalizacion, penalizacion_id)
    if not pen:
        raise HTTPException(404)
    await db.delete(pen)
    await db.commit()
    return {"ok": True}


@app.get("/api/admin/conductores/bloqueados")
async def admin_conductores_bloqueados(db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    from app.models import Conductor
    result = await db.execute(
        select(Conductor).where(Conductor.bloqueado == True)
    )
    return result.scalars().all()


@app.post("/api/admin/conductores/{conductor_id}/desbloquear")
async def admin_desbloquear_conductor(conductor_id: int, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    cond.bloqueado = False
    await db.commit()
    return {"ok": True, "mensaje": f"{cond.nombre} desbloqueado"}


@app.get("/api/conductores/{conductor_id}", response_model=ConductorOut)
async def obtener_conductor(conductor_id: int, db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404, "Conductor no encontrado")
    return cond


@app.put("/api/conductores/{conductor_id}")
async def actualizar_conductor(conductor_id: int, data: ConductorUpdate, db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404, "Conductor no encontrado")
    if data.nombre is not None:
        cond.nombre = data.nombre
    if data.email is not None:
        cond.email = data.email
    if data.telefono is not None:
        cond.telefono = data.telefono
    if data.patente is not None:
        cond.patente = data.patente
    await db.commit()
    await db.refresh(cond)
    return cond


@app.post("/api/conductores", response_model=ConductorOut)
async def crear_conductor(data: ConductorCreate, db: AsyncSession = Depends(get_db)):
    cond = Conductor(**data.model_dump())
    db.add(cond)
    await db.commit()
    await db.refresh(cond)
    return cond


# ═══════════════════════════════════════════════════════
# API: ESPACIOS
# ═══════════════════════════════════════════════════════

@app.get("/api/espacios", response_model=list[EspacioOut])
async def listar_espacios(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio))
    return result.scalars().all()


@app.get("/api/espacios/disponibles")
async def espacios_disponibles(db: AsyncSession = Depends(get_db)):
    """Retorna espacios libres (reservables)."""
    result = await db.execute(
        select(Espacio).where(Espacio.disponible == True)
    )
    return result.scalars().all()


@app.get("/api/espacios/con-estado")
async def espacios_con_estado(db: AsyncSession = Depends(get_db)):
    """Retorna conteo de libres/ocupados."""
    result = await db.execute(select(Espacio.disponible, func.count(Espacio.id)).group_by(Espacio.disponible))
    conteo = {"libres": 0, "ocupados": 0}
    for disp, cnt in result:
        if disp:
            conteo["libres"] = cnt
        else:
            conteo["ocupados"] = cnt
    return conteo


@app.post("/api/espacios", response_model=EspacioOut)
async def crear_espacio(data: EspacioCreate, db: AsyncSession = Depends(get_db)):
    esp = Espacio(**data.model_dump())
    db.add(esp)
    await db.commit()
    await db.refresh(esp)
    return esp


# ═══════════════════════════════════════════════════════
# API: CHECK-IN / CHECK-OUT
# ═══════════════════════════════════════════════════════

@app.get("/api/espacio/by-location")
async def espacio_by_location(lat: float, lng: float, db: AsyncSession = Depends(get_db)):
    """Encuentra el espacio DB más cercano a las coordenadas dadas."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT id, ubicacion, precio_por_hora, disponible, lat, lng,
                   ( (lat - :lat) * (lat - :lat) + (lng - :lng) * (lng - :lng) ) as dist_sq
            FROM espacios
            WHERE disponible = 1 AND lat IS NOT NULL AND lng IS NOT NULL
            ORDER BY dist_sq ASC
            LIMIT 1
        """),
        {"lat": lat, "lng": lng}
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "No se encontró espacio cercano")
    return {
        "id": row[0], "ubicacion": row[1],
        "precio_por_hora": row[2], "disponible": row[3],
        "lat": row[4], "lng": row[5],
    }

@app.post("/api/checkin", response_model=CheckInResponse)
async def checkin(data: CheckInRequest, db: AsyncSession = Depends(get_db)):
    # Verificar bloqueo
    estado = await verificar_bloqueo(data.conductor_id, db)
    if estado["bloqueado"]:
        raise HTTPException(403, f"Conductor bloqueado: {estado['motivo']}")

    result = await db.execute(select(Espacio).where(Espacio.id == data.espacio_id))
    espacio = result.scalar_one_or_none()
    if not espacio:
        raise HTTPException(404, "Espacio no encontrado")
    if not espacio.disponible:
        raise HTTPException(400, "Espacio no disponible")

    sesion = SesionEstacionamiento(
        espacio_id=data.espacio_id,
        conductor_id=data.conductor_id,
        hora_inicio=now_naive(),
    )
    db.add(sesion)

    # Verificar si hay una reserva activa para este espacio y conductor
    result = await db.execute(
        select(Reserva)
        .where(Reserva.espacio_id == data.espacio_id)
        .where(Reserva.conductor_id == data.conductor_id)
        .where(Reserva.estado == EstadoReserva.aprobada)
        .where(Reserva.usada == False)
        .order_by(Reserva.hora_inicio.desc())
    )
    reserva = result.scalar_one_or_none()
    ahora = now_naive()

    if reserva:
        reserva.usada = True
        reserva.checkin_time = ahora
        # Verificar tolerancia de 5 minutos
        diff_min = (ahora - reserva.hora_inicio).total_seconds() / 60
        if diff_min > TOLERANCIA_MINUTOS:
            monto_penal = round(PRECIO_POR_HORA * 0.1, 2)
            await penalizar_conductor(
                conductor_id=data.conductor_id,
                reserva_id=reserva.id,
                monto=monto_penal,
                motivo=f"Check-in tardío: {diff_min:.0f}min (tolerancia: {TOLERANCIA_MINUTOS}min)",
                db=db,
            )

    espacio.disponible = False
    await db.commit()
    await db.refresh(sesion)

    qr_data = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/conductor/checkout/{sesion.id}"
    qr_b64 = generar_qr_base64(qr_data)

    return CheckInResponse(
        sesion_id=sesion.id,
        hora_inicio=sesion.hora_inicio,
        qr_salida=qr_b64,
    )


@app.post("/api/checkin-por-perm", response_model=CheckInResponse)
async def checkin_por_perm(data: CheckInPorPermRequest, db: AsyncSession = Depends(get_db)):
    estado = await verificar_bloqueo(data.conductor_id, db)
    if estado["bloqueado"]:
        raise HTTPException(403, f"Conductor bloqueado: {estado['motivo']}")

    perm = await db.get(Permisionario, data.permisionario_id)
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")

    # Buscar primer espacio disponible del permisionario
    result = await db.execute(
        select(Espacio)
        .where(Espacio.permisionario_id == data.permisionario_id)
        .where(Espacio.disponible == True)
        .limit(1)
    )
    espacio = result.scalar_one_or_none()
    if not espacio:
        raise HTTPException(400, "No hay espacios disponibles en esta cuadra")

    sesion = SesionEstacionamiento(
        espacio_id=espacio.id,
        conductor_id=data.conductor_id,
        hora_inicio=now_naive(),
    )
    db.add(sesion)

    espacio.disponible = False
    await db.commit()
    await db.refresh(sesion)

    qr_data = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/conductor/checkout/{sesion.id}"
    qr_b64 = generar_qr_base64(qr_data)

    return CheckInResponse(
        sesion_id=sesion.id,
        hora_inicio=sesion.hora_inicio,
        qr_salida=qr_b64,
    )


@app.post("/api/sesion/{sesion_id}/elegir-pago")
async def elegir_pago(sesion_id: int, body: ElegirPagoRequest, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion or sesion.hora_fin:
        raise HTTPException(404, "Sesion no encontrada o ya finalizada")
    if body.metodo not in ("efectivo", "mercadopago"):
        raise HTTPException(400, "Metodo de pago invalido")

    sesion.metodo_pago = body.metodo

    if body.patente:
        cond = await db.get(Conductor, sesion.conductor_id)
        if cond:
            cond.patente = body.patente.upper()

    await db.commit()

    resp = {"ok": True, "metodo": body.metodo}

    if body.metodo == "mercadopago":
        cond = await db.get(Conductor, sesion.conductor_id)
        monto_est = calcular_costo_estacionamiento(sesion.hora_inicio, now_naive()) or 2000.0
        mp_result = await crear_preferencia_pago(
            monto=monto_est,
            concepto=f"Estacionamiento #{sesion.id}",
            conductor_email=cond.email if cond else "conductor@email.com",
            notification_url=f"{os.getenv('BASE_URL', 'http://localhost:8000')}/api/mercadopago/webhook",
            external_reference=str(sesion.id),
        )
        resp["init_point"] = mp_result.get("init_point", "")
        resp["preference_id"] = mp_result.get("preference_id", "")

    return resp


@app.post("/api/sesion/{sesion_id}/confirmar-pago-efectivo")
async def confirmar_pago_efectivo(sesion_id: int, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion or sesion.hora_fin:
        raise HTTPException(404, "Sesion no encontrada o ya finalizada")
    if sesion.metodo_pago != "efectivo":
        raise HTTPException(400, "Esta sesion no esta configurada para pago en efectivo")

    ahora = now_naive()
    sesion.costo_total = calcular_costo_estacionamiento(sesion.hora_inicio, ahora)
    sesion.pagado = True
    sesion.lista_para_salir = True
    sesion.hora_fin = ahora

    espacio = await db.get(Espacio, sesion.espacio_id)
    if espacio:
        espacio.disponible = True

    await db.commit()

    qr_data = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/conductor/checkout/{sesion.id}"
    qr_b64 = generar_qr_base64(qr_data)
    return {"ok": True, "qr_salida": qr_b64, "costo_total": sesion.costo_total}


@app.get("/api/sesion/{sesion_id}/exit-qr")
async def obtener_exit_qr(sesion_id: int, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion or sesion.hora_fin:
        raise HTTPException(404, "Sesion no encontrada o ya finalizada")
    if not sesion.lista_para_salir:
        raise HTTPException(400, "Aun no esta habilitado el QR de salida (esperando pago)")

    qr_data = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/conductor/checkout/{sesion.id}"
    qr_b64 = generar_qr_base64(qr_data)
    return {"qr_salida": qr_b64}


@app.post("/api/sesion/{sesion_id}/finalizar-por-scan")
async def finalizar_por_scan(sesion_id: int, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.hora_fin:
        raise HTTPException(400, "Sesion ya finalizada")
    if not sesion.pagado:
        raise HTTPException(400, "El pago no esta confirmado. No se puede finalizar.")

    ahora = now_naive()
    espacio = await db.get(Espacio, sesion.espacio_id)
    if not sesion.costo_total:
        sesion.costo_total = calcular_costo_estacionamiento(sesion.hora_inicio, ahora)
    sesion.hora_fin = ahora

    if espacio:
        espacio.disponible = True

    await db.commit()
    return {"ok": True, "sesion_id": sesion.id, "costo_total": sesion.costo_total}


@app.post("/api/permisionario/{perm_id}/registro-manual")
async def registro_manual(perm_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    patente = body.get("patente", "").upper().strip()
    espacio_id = body.get("espacio_id")
    if not patente or not espacio_id:
        raise HTTPException(400, "patente y espacio_id requeridos")

    espacio = await db.get(Espacio, espacio_id)
    if not espacio:
        raise HTTPException(404, "Espacio no encontrado")
    if not espacio.disponible:
        raise HTTPException(400, "Espacio no disponible")
    if espacio.permisionario_id != perm_id:
        raise HTTPException(403, "Este espacio no te pertenece")

    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")

    # Find or create conductor by patente
    result = await db.execute(select(Conductor).where(Conductor.patente == patente).limit(1))
    conductor = result.scalar_one_or_none()
    if not conductor:
        # Create a guest conductor
        conductor = Conductor(
            nombre=f"Manual - {patente}",
            email=f"manual_{patente.lower()}@guest.app",
            username=f"guest_{patente.lower()}",
            password_hash="",
            patente=patente,
        )
        db.add(conductor)
        await db.flush()

    sesion = SesionEstacionamiento(
        espacio_id=espacio_id,
        conductor_id=conductor.id,
        hora_inicio=now_naive(),
    )
    db.add(sesion)
    espacio.disponible = False
    await db.commit()
    await db.refresh(sesion)

    return {"ok": True, "sesion_id": sesion.id, "conductor_id": conductor.id, "conductor_nombre": conductor.nombre}


@app.post("/api/permisionario/{perm_id}/finalizar/{sesion_id}")
async def perm_finalizar(perm_id: int, sesion_id: int, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.hora_fin:
        raise HTTPException(400, "Sesion ya finalizada")

    espacio = await db.get(Espacio, sesion.espacio_id)
    if not espacio or espacio.permisionario_id != perm_id:
        raise HTTPException(403, "Esta sesion no pertenece a un espacio tuyo")

    ahora = now_naive()
    sesion.costo_total = calcular_costo_estacionamiento(sesion.hora_inicio, ahora)
    sesion.hora_fin = ahora
    sesion.pagado = True
    espacio.disponible = True

    await db.commit()
    return {"ok": True, "sesion_id": sesion.id, "costo_total": sesion.costo_total}


@app.get("/api/checkin-qr/{sesion_id}")
async def checkin_qr(sesion_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SesionEstacionamiento).where(SesionEstacionamiento.id == sesion_id))
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(404, "Sesión no encontrada")
    qr_data = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/conductor/checkout/{sesion.id}"
    qr_b64 = generar_qr_base64(qr_data)
    return {"qr": qr_b64}


@app.post("/api/checkout", response_model=CheckOutResponse)
async def checkout(data: CheckOutRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.id == data.sesion_id)
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.hora_fin:
        raise HTTPException(400, "Sesion ya finalizada")

    result = await db.execute(select(Espacio).where(Espacio.id == sesion.espacio_id))
    espacio = result.scalar_one()
    result = await db.execute(select(Conductor).where(Conductor.id == sesion.conductor_id))
    conductor = result.scalar_one()

    ahora = now_naive()
    minutos = max((ahora - sesion.hora_inicio).total_seconds() / 60, 0)
    sesion.costo_total = calcular_costo_estacionamiento(sesion.hora_inicio, ahora)

    sesion.hora_fin = ahora
    espacio.disponible = True

    mp_data = await crear_preferencia_pago(
        monto=sesion.costo_total,
        concepto=f"Estacionamiento - {espacio.ubicacion}",
        conductor_email=conductor.email,
        notification_url=f"{os.getenv('BASE_URL', 'http://localhost:8000')}/api/mercadopago/webhook",
        external_reference=str(sesion.id),
    )
    sesion.pago_id = mp_data.get("preference_id", "")
    sesion.pagado = False

    conductor.saldo_deudor = (conductor.saldo_deudor or 0) + sesion.costo_total

    await db.commit()

    return CheckOutResponse(
        sesion_id=sesion.id,
        costo_total=sesion.costo_total,
        link_pago=mp_data.get("init_point", ""),
    )


# ═══════════════════════════════════════════════════════
# MERCADO PAGO WEBHOOK
# ═══════════════════════════════════════════════════════

@app.post("/api/mercadopago/webhook")
async def mercadopago_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    from app.mercado_pago import procesar_pago_webhook

    try:
        body = await request.json()
    except Exception:
        body = {}

    # MP envía: {"action": "payment.created", "data": {"id": "12345"}}
    payment_id = body.get("data", {}).get("id")
    if not payment_id:
        # Verificar si viene como query param
        payment_id = request.query_params.get("id")

    if not payment_id:
        return {"ok": False, "error": "no payment_id"}

    payment = await procesar_pago_webhook(str(payment_id))
    status = payment.get("status", "")

    if status == "approved":
        # Buscar por external_reference (sesion_id)
        ext_ref = payment.get("external_reference", "")
        sesion = None
        if ext_ref:
            sesion = await db.get(SesionEstacionamiento, int(ext_ref))

        # Fallback: buscar por preference_id
        if not sesion:
            pref_id = payment.get("preference_id", "")
            if pref_id:
                result = await db.execute(
                    select(SesionEstacionamiento).where(SesionEstacionamiento.pago_id == pref_id)
                )
                sesion = result.scalar_one_or_none()

        if sesion and not sesion.pagado:
            ahora = now_naive()
            if not sesion.costo_total:
                sesion.costo_total = calcular_costo_estacionamiento(sesion.hora_inicio, ahora)
            sesion.pagado = True
            sesion.lista_para_salir = True
            conductor = await db.get(Conductor, sesion.conductor_id)
            if conductor:
                conductor.saldo_deudor = max((conductor.saldo_deudor or 0) - (sesion.costo_total or 0), 0)
            await db.commit()

    return {"ok": True}


# ═══════════════════════════════════════════════════════
# MERCADO PAGO REDIRECTS
# ═══════════════════════════════════════════════════════

@app.get("/pago/success", response_class=HTMLResponse)
async def pago_success(request: Request):
    return templates.TemplateResponse(request, "conductor/pago_resultado.html", {
        "titulo": "✅ Pago aprobado",
        "mensaje": "Tu estacionamiento fue pagado con éxito.",
        "icono": "✅",
    })


@app.get("/pago/failure", response_class=HTMLResponse)
async def pago_failure(request: Request):
    return templates.TemplateResponse(request, "conductor/pago_resultado.html", {
        "titulo": "❌ Pago rechazado",
        "mensaje": "El pago no pudo completarse. El monto se acumuló a tu deuda.",
        "icono": "❌",
    })


@app.get("/pago/pending", response_class=HTMLResponse)
async def pago_pending(request: Request):
    return templates.TemplateResponse(request, "conductor/pago_resultado.html", {
        "titulo": "⏳ Pago pendiente",
        "mensaje": "Tu pago está siendo procesado.",
        "icono": "⏳",
    })


# ═══════════════════════════════════════════════════════
# API: SESIONES
# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════

@app.get("/api/sesiones")
async def listar_sesiones(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    return [sesion_to_dict(s) for s in result.scalars().all()]


@app.get("/api/sesiones/activas")
async def sesiones_activas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.hora_fin == None)
    )
    sesiones = result.scalars().all()
    return [sesion_to_dict(s) for s in sesiones]



@app.get("/api/sesiones/conductor/{conductor_id}")
async def sesiones_por_conductor(conductor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.conductor_id == conductor_id)
        .order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    return [sesion_to_dict(s) for s in result.scalars().all()]


async def get_espacio_ids_por_perm(perm_id: int, db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(Espacio.id).where(Espacio.permisionario_id == perm_id)
    )
    return result.scalars().all()


@app.get("/api/sesiones/activas/{permisionario_id}")
async def sesiones_activas_por_permisionario(permisionario_id: int, db: AsyncSession = Depends(get_db)):
    espacio_ids = await get_espacio_ids_por_perm(permisionario_id, db)
    if not espacio_ids:
        return []
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.espacio_id.in_(espacio_ids))
        .order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    return [sesion_to_dict(s) for s in result.scalars().all()]


@app.get("/api/sesiones/ingresos/{permisionario_id}")
async def ingresos_permisionario(permisionario_id: int, db: AsyncSession = Depends(get_db)):
    espacio_ids = await get_espacio_ids_por_perm(permisionario_id, db)
    if not espacio_ids:
        return []
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.espacio_id.in_(espacio_ids))
        .where(SesionEstacionamiento.pagado == True)
        .where(SesionEstacionamiento.costo_total != None)
        .order_by(SesionEstacionamiento.hora_inicio.asc())
    )
    return [sesion_to_dict(s) for s in result.scalars().all()]


@app.get("/api/sesiones/activa/{conductor_id}")
async def sesion_activa_conductor(conductor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.conductor_id == conductor_id)
        .where(SesionEstacionamiento.hora_fin == None)
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        return None
    d = sesion_to_dict(sesion)
    esp = await db.get(Espacio, sesion.espacio_id)
    if esp:
        d["ubicacion"] = esp.ubicacion
    cond = await db.get(Conductor, sesion.conductor_id)
    if cond and cond.patente:
        d["patente"] = cond.patente
    return d


@app.get("/api/sesiones/permisionario/{permisionario_id}/detalle")
async def sesiones_permisionario_detalle(permisionario_id: int, db: AsyncSession = Depends(get_db)):
    """Retorna sesiones activas + completadas con patente y ubicación para el dashboard del permisionario."""
    espacio_ids = await get_espacio_ids_por_perm(permisionario_id, db)
    if not espacio_ids:
        return {"activas": [], "completadas": [], "pagadas_hoy": 0}

    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.espacio_id.in_(espacio_ids))
        .order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    sesiones = result.scalars().all()

    activas = []
    completadas = []
    pagadas_hoy = 0.0
    today = now_naive().strftime("%Y-%m-%d")

    for s in sesiones:
        d = sesion_to_dict(s)
        esp = await db.get(Espacio, s.espacio_id)
        if esp:
            d["ubicacion"] = esp.ubicacion
        cond = await db.get(Conductor, s.conductor_id)
        if cond:
            d["conductor_nombre"] = cond.nombre
            d["patente"] = cond.patente or "—"
            d["email"] = cond.email

        if s.hora_fin is None:
            activas.append(d)
        else:
            completadas.append(d)
            if s.pagado and s.hora_fin and s.hora_fin.strftime("%Y-%m-%d") == today:
                pagadas_hoy += s.costo_total or 0

    return {"activas": activas, "completadas": completadas, "pagadas_hoy": round(pagadas_hoy, 2)}


# ═══════════════════════════════════════════════════════
# API: RESERVAS
# ═══════════════════════════════════════════════════════

@app.get("/api/reservas", response_model=list[ReservaOut])
async def listar_reservas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reserva).order_by(Reserva.creada_en.desc()))
    return result.scalars().all()


@app.get("/api/reservas/conductor/{conductor_id}")
async def reservas_por_conductor(conductor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Reserva)
        .where(Reserva.conductor_id == conductor_id)
        .order_by(Reserva.creada_en.desc())
    )
    return [reserva_to_dict(r) for r in result.scalars().all()]


@app.get("/api/reservas/permisionario/{permisionario_id}")
async def reservas_por_permisionario(permisionario_id: int, db: AsyncSession = Depends(get_db)):
    espacio_ids = await get_espacio_ids_por_perm(permisionario_id, db)
    if not espacio_ids:
        return []
    result = await db.execute(
        select(Reserva)
        .where(Reserva.espacio_id.in_(espacio_ids))
        .order_by(Reserva.creada_en.desc())
    )
    return [reserva_to_dict(r) for r in result.scalars().all()]


@app.get("/api/reservas/pendientes/{permisionario_id}")
async def reservas_pendientes(permisionario_id: int, db: AsyncSession = Depends(get_db)):
    espacio_ids = await get_espacio_ids_por_perm(permisionario_id, db)
    if not espacio_ids:
        return []
    result = await db.execute(
        select(Reserva)
        .where(Reserva.espacio_id.in_(espacio_ids))
        .where(Reserva.estado == EstadoReserva.pendiente)
    )
    return [reserva_to_dict(r) for r in result.scalars().all()]


@app.post("/api/reservas", response_model=ReservaOut)
async def crear_reserva(data: ReservaCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio).where(Espacio.id == data.espacio_id))
    espacio = result.scalar_one_or_none()
    if not espacio:
        raise HTTPException(404, "Espacio no encontrado")

    reserva = Reserva(
        espacio_id=data.espacio_id,
        conductor_id=data.conductor_id,
        hora_inicio=data.hora_inicio,
        hora_fin=data.hora_fin,
    )
    db.add(reserva)
    await db.commit()
    await db.refresh(reserva)
    return reserva


@app.post("/api/reservas/aprobar")
async def aprobar_reserva(data: ReservaAprobar, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reserva).where(Reserva.id == data.reserva_id))
    reserva = result.scalar_one_or_none()
    if not reserva:
        raise HTTPException(404, "Reserva no encontrada")

    if data.aprobar:
        reserva.estado = EstadoReserva.aprobada
    else:
        reserva.estado = EstadoReserva.rechazada

    await db.commit()
    return {"ok": True, "estado": reserva.estado.value}


@app.post("/api/admin/verificar-no-show")
async def admin_verificar_no_show(db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    n = await verificar_no_show_periodico(db)
    return {"ok": True, "penalizadas": n}


# ═══════════════════════════════════════════════════════
# PASSWORD CHANGE (ALL ROLES)
# ═══════════════════════════════════════════════════════

@app.post("/api/auth/cambiar-password")
async def cambiar_password(body: PasswordChangeRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.auth import hash_password, verify_password
    models = {"conductor": Conductor, "permisionario": Permisionario, "admin": Admin}
    model = models.get(current_user["role"])
    if not model:
        raise HTTPException(400, "Rol no soportado")
    user = await db.get(model, current_user["id"])
    if not user or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Contraseña actual incorrecta")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True, "mensaje": "Contraseña actualizada"}


# ═══════════════════════════════════════════════════════
# PERMISIONARIO UPDATE
# ═══════════════════════════════════════════════════════

@app.put("/api/permisionarios/{perm_id}", response_model=PermisionarioOut)
async def actualizar_permisionario(perm_id: int, data: PermisionarioUpdate, db: AsyncSession = Depends(get_db), current_user=Depends(require_role("permisionario", "admin"))):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    if current_user["role"] != "admin" and current_user["id"] != perm.id:
        raise HTTPException(403, "No podés editar otro perfil")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(perm, field, value)
    await db.commit()
    await db.refresh(perm)
    return perm


@app.get("/api/permisionarios/{perm_id}", response_model=PermisionarioOut)
async def obtener_permisionario(perm_id: int, db: AsyncSession = Depends(get_db)):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    return perm


# ═══════════════════════════════════════════════════════
# ADMIN: EDIT/DELETE CRUD
# ═══════════════════════════════════════════════════════

@app.put("/api/admin/conductores/{conductor_id}")
async def admin_editar_conductor(conductor_id: int, data: ConductorUpdate, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cond, field, value)
    await db.commit()
    await db.refresh(cond)
    return cond


@app.delete("/api/admin/conductores/{conductor_id}")
async def admin_eliminar_conductor(conductor_id: int, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    await db.delete(cond)
    await db.commit()
    return {"ok": True}


@app.put("/api/admin/permisionarios/{perm_id}")
async def admin_editar_permisionario(perm_id: int, data: PermisionarioUpdate, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(perm, field, value)
    await db.commit()
    await db.refresh(perm)
    return perm


@app.delete("/api/admin/permisionarios/{perm_id}")
async def admin_eliminar_permisionario(perm_id: int, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    await db.delete(perm)
    await db.commit()
    return {"ok": True}


@app.put("/api/admin/espacios/{espacio_id}", response_model=EspacioOut)
async def admin_editar_espacio(espacio_id: int, data: EspacioUpdate, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    esp = await db.get(Espacio, espacio_id)
    if not esp:
        raise HTTPException(404)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(esp, field, value)
    await db.commit()
    await db.refresh(esp)
    return esp


@app.delete("/api/admin/espacios/{espacio_id}")
async def admin_eliminar_espacio(espacio_id: int, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    esp = await db.get(Espacio, espacio_id)
    if not esp:
        raise HTTPException(404)
    await db.delete(esp)
    await db.commit()
    return {"ok": True}


@app.get("/api/admin/conductores/{conductor_id}/detalle")
async def admin_conductor_detalle(conductor_id: int, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    from app.models import Penalizacion
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    sr = await db.execute(select(SesionEstacionamiento).where(SesionEstacionamiento.conductor_id == conductor_id).order_by(SesionEstacionamiento.hora_inicio.desc()).limit(50))
    sesiones = [sesion_to_dict(s) for s in sr.scalars().all()]
    pr = await db.execute(select(Penalizacion).where(Penalizacion.conductor_id == conductor_id).order_by(Penalizacion.fecha.desc()).limit(50))
    pens = [{"id": p.id, "monto": p.monto, "motivo": p.motivo, "fecha": p.fecha.isoformat(), "pagada": p.pagada} for p in pr.scalars().all()]
    rr = await db.execute(select(Reserva).where(Reserva.conductor_id == conductor_id).order_by(Reserva.creada_en.desc()).limit(50))
    reservas = [reserva_to_dict(r) for r in rr.scalars().all()]
    return {
        "conductor": {"id": cond.id, "nombre": cond.nombre, "email": cond.email, "patente": cond.patente,
                      "bloqueado": cond.bloqueado, "saldo_deudor": cond.saldo_deudor,
                      "telefono": cond.telefono, "username": cond.username},
        "sesiones": sesiones, "penalizaciones": pens, "reservas": reservas,
    }


# ═══════════════════════════════════════════════════════
# LOGOUT
# ═══════════════════════════════════════════════════════

@app.post("/api/auth/logout")
async def logout(current_user=Depends(get_current_user)):
    return {"ok": True, "mensaje": "Sesión cerrada"}


# ═══════════════════════════════════════════════════════
# CASH REGISTER / DAILY CLOSE (PERMISIONARIO)
# ═══════════════════════════════════════════════════════

@app.get("/api/permisionario/{perm_id}/cierre-diario")
async def cierre_diario(perm_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(require_role("permisionario", "admin"))):
    if current_user["role"] != "admin" and current_user["id"] != perm_id:
        raise HTTPException(403, "No podés ver otro cierre")
    espacio_ids = await get_espacio_ids_por_perm(perm_id, db)
    if not espacio_ids:
        return {"total": 0, "cantidad": 0, "por_dia": []}
    today = now_naive().strftime("%Y-%m-%d")
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.espacio_id.in_(espacio_ids))
        .where(SesionEstacionamiento.pagado == True)
        .where(func.date(SesionEstacionamiento.hora_fin) == today)
        .order_by(SesionEstacionamiento.hora_inicio.asc())
    )
    sesiones = result.scalars().all()
    total = sum(s.costo_total or 0 for s in sesiones)
    return {
        "fecha": today,
        "total": round(total, 2),
        "cantidad": len(sesiones),
        "sesiones": [sesion_to_dict(s) for s in sesiones],
    }


# ═══════════════════════════════════════════════════════
# AUDIT LOG (ADMIN — in-memory)
# ═══════════════════════════════════════════════════════

AUDIT_LOG = []

@app.get("/api/admin/audit")
async def listar_audit(limit: int = 100, admin=Depends(require_role("admin"))):
    return list(reversed(AUDIT_LOG))[:limit]


# ═══════════════════════════════════════════════════════
# SYSTEM CONFIG (ADMIN)
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/config")
async def get_config(admin=Depends(require_role("admin"))):
    return {
        "PRECIO_POR_HORA": PRECIO_POR_HORA,
        "HORARIO_CIERRE": HORARIO_CIERRE,
        "HORARIO_CIERRE_SAB": HORARIO_CIERRE_SAB,
        "TOLERANCIA_MINUTOS": TOLERANCIA_MINUTOS,
        "MAX_PENALIZACIONES_MES": MAX_PENALIZACIONES_MES,
        "DEUDA_MAXIMA": DEUDA_MAXIMA,
        "MULTA_BLOQUEO": MULTA_BLOQUEO,
    }


# ═══════════════════════════════════════════════════════
# MULTIPLE PATENTES (CONDUCTOR)
# ═══════════════════════════════════════════════════════

@app.get("/api/conductores/{conductor_id}/patentes", response_model=list[PatenteSecundariaOut])
async def listar_patentes_secundarias(conductor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PatenteSecundaria).where(PatenteSecundaria.conductor_id == conductor_id)
    )
    return result.scalars().all()


@app.post("/api/conductores/{conductor_id}/patentes")
async def crear_patente_secundaria(conductor_id: int, body: PatenteSecundariaOut, db: AsyncSession = Depends(get_db)):
    pat = PatenteSecundaria(conductor_id=conductor_id, patente=body.patente.upper())
    db.add(pat)
    await db.commit()
    await db.refresh(pat)
    return pat


@app.delete("/api/conductores/{conductor_id}/patentes/{patente_id}")
async def eliminar_patente_secundaria(conductor_id: int, patente_id: int, db: AsyncSession = Depends(get_db)):
    pat = await db.get(PatenteSecundaria, patente_id)
    if not pat or pat.conductor_id != conductor_id:
        raise HTTPException(404)
    await db.delete(pat)
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# FAVORITOS (CONDUCTOR)
# ═══════════════════════════════════════════════════════

@app.get("/api/conductores/{conductor_id}/favoritos", response_model=list[FavoritoOut])
async def listar_favoritos(conductor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Favorito).where(Favorito.conductor_id == conductor_id)
    )
    return result.scalars().all()


@app.post("/api/conductores/{conductor_id}/favoritos")
async def crear_favorito(conductor_id: int, body: FavoritoCreate, db: AsyncSession = Depends(get_db)):
    fav = Favorito(conductor_id=conductor_id, espacio_id=body.espacio_id, nombre=body.nombre)
    db.add(fav)
    await db.commit()
    await db.refresh(fav)
    return fav


@app.delete("/api/conductores/{conductor_id}/favoritos/{favorito_id}")
async def eliminar_favorito(conductor_id: int, favorito_id: int, db: AsyncSession = Depends(get_db)):
    fav = await db.get(Favorito, favorito_id)
    if not fav or fav.conductor_id != conductor_id:
        raise HTTPException(404)
    await db.delete(fav)
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# EXTENDER SESION
# ═══════════════════════════════════════════════════════

@app.post("/api/sesion/{sesion_id}/extender")
async def extender_sesion(sesion_id: int, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.hora_fin:
        raise HTTPException(400, "Sesion ya finalizada")

    ahora = now_naive()
    if not sesion.pagado:
        sesion.costo_total = calcular_costo_estacionamiento(sesion.hora_inicio, ahora)
    elif sesion.lista_para_salir:
        sesion.lista_para_salir = False

    await db.commit()
    return {"ok": True, "mensaje": "Sesion extendida", "hora_inicio": sesion.hora_inicio.isoformat()}


# ═══════════════════════════════════════════════════════
# COMPROBANTE DIGITAL
# ═══════════════════════════════════════════════════════

@app.get("/api/sesion/{sesion_id}/comprobante")
async def obtener_comprobante(sesion_id: int, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404)
    if not sesion.hora_fin:
        raise HTTPException(400, "Sesion no finalizada aun")

    espacio = await db.get(Espacio, sesion.espacio_id)
    conductor = await db.get(Conductor, sesion.conductor_id)
    return {
        "sesion_id": sesion.id,
        "conductor": conductor.nombre if conductor else "",
        "patente": conductor.patente if conductor else "",
        "ubicacion": espacio.ubicacion if espacio else "",
        "hora_inicio": sesion.hora_inicio.isoformat(),
        "hora_fin": sesion.hora_fin.isoformat(),
        "costo_total": sesion.costo_total or 0,
        "metodo_pago": sesion.metodo_pago or "",
        "pagado": sesion.pagado,
    }


# ═══════════════════════════════════════════════════════
# DONDE DEJE EL AUTO (ULTIMA SESION ACTIVA)
# ═══════════════════════════════════════════════════════

@app.get("/api/conductores/{conductor_id}/ultimo-estacionamiento")
async def ultimo_estacionamiento(conductor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.conductor_id == conductor_id)
        .order_by(SesionEstacionamiento.hora_inicio.desc())
        .limit(1)
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        return None
    espacio = await db.get(Espacio, sesion.espacio_id)
    return {
        "sesion_id": sesion.id,
        "activa": sesion.hora_fin is None,
        "ubicacion": espacio.ubicacion if espacio else "",
        "lat": espacio.lat if espacio else None,
        "lng": espacio.lng if espacio else None,
        "hora_inicio": sesion.hora_inicio.isoformat(),
        "hora_fin": sesion.hora_fin.isoformat() if sesion.hora_fin else None,
    }


# ═══════════════════════════════════════════════════════
# HISTORIAL DE PAGOS
# ═══════════════════════════════════════════════════════

@app.get("/api/conductores/{conductor_id}/pagos")
async def historial_pagos(conductor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.conductor_id == conductor_id)
        .where(SesionEstacionamiento.pagado == True)
        .order_by(SesionEstacionamiento.hora_inicio.desc())
        .limit(100)
    )
    sesiones = result.scalars().all()
    data = []
    for s in sesiones:
        esp = await db.get(Espacio, s.espacio_id)
        data.append({
            "id": s.id,
            "ubicacion": esp.ubicacion if esp else "",
            "hora_inicio": s.hora_inicio.isoformat(),
            "hora_fin": s.hora_fin.isoformat() if s.hora_fin else None,
            "costo_total": s.costo_total or 0,
            "metodo_pago": s.metodo_pago or "",
            "fecha": s.hora_inicio.strftime("%Y-%m-%d"),
        })
    return data


# ═══════════════════════════════════════════════════════
# NOTIFICACIONES (POLLING)
# ═══════════════════════════════════════════════════════

@app.get("/api/conductores/{conductor_id}/notificaciones")
async def notificaciones_conductor(conductor_id: int, db: AsyncSession = Depends(get_db)):
    notifs = []

    # Sesion activa por vencer (proximo al cierre)
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.conductor_id == conductor_id)
        .where(SesionEstacionamiento.hora_fin == None)
        .limit(1)
    )
    sesion = result.scalar_one_or_none()
    if sesion:
        ahora = now_naive()
        hora_cierre = ahora.replace(hour=HORARIO_CIERRE, minute=0, second=0)
        if ahora.hour >= HORARIO_CIERRE - 1 and ahora.hour < HORARIO_CIERRE:
            notifs.append({
                "tipo": "cierre",
                "mensaje": f"El estacionamiento cierra a las {HORARIO_CIERRE}:00. Retirá tu auto.",
                "leida": False,
            })

    # Penalizaciones recientes no pagas
    from app.models import Penalizacion
    result2 = await db.execute(
        select(Penalizacion)
        .where(Penalizacion.conductor_id == conductor_id)
        .where(Penalizacion.pagada == False)
        .order_by(Penalizacion.fecha.desc())
        .limit(3)
    )
    pens = result2.scalars().all()
    for p in pens:
        dias = (now_naive() - p.fecha.replace(tzinfo=None)).days
        if dias <= 7:
            notifs.append({
                "tipo": "penalizacion",
                "mensaje": f"Penalización de ${p.monto:.0f} por: {p.motivo}",
                "leida": False,
            })

    return notifs


# ═══════════════════════════════════════════════════════
# ADMIN: BUSCAR CONDUCTORES
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/conductores/buscar")
async def admin_buscar_conductores(q: str = "", db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    if not q:
        result = await db.execute(select(Conductor).order_by(Conductor.id.desc()).limit(100))
        return result.scalars().all()
    result = await db.execute(
        select(Conductor).where(
            (Conductor.nombre.ilike(f"%{q}%")) |
            (Conductor.email.ilike(f"%{q}%")) |
            (Conductor.patente.ilike(f"%{q}%"))
        ).order_by(Conductor.id.desc()).limit(100)
    )
    return result.scalars().all()


# ═══════════════════════════════════════════════════════
# ADMIN: EXPORTAR HISTORIAL CONDUCTOR CSV
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/conductores/{conductor_id}/exportar-csv")
async def admin_exportar_conductor_csv(conductor_id: int, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)

    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.conductor_id == conductor_id)
        .order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    sesiones = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Espacio", "Inicio", "Fin", "Costo", "Pagado", "Metodo"])
    for s in sesiones:
        esp = await db.get(Espacio, s.espacio_id)
        writer.writerow([
            s.id, esp.ubicacion if esp else "",
            s.hora_inicio.strftime("%Y-%m-%d %H:%M"),
            s.hora_fin.strftime("%Y-%m-%d %H:%M") if s.hora_fin else "",
            s.costo_total or 0, "Si" if s.pagado else "No", s.metodo_pago or "",
        ])

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=conductor_{conductor_id}_historial.csv"},
    )


# ═══════════════════════════════════════════════════════
# ADMIN: SUSPENDER CONDUCTOR TEMPORALMENTE
# ═══════════════════════════════════════════════════════

@app.post("/api/admin/conductores/{conductor_id}/suspender")
async def admin_suspender_conductor(conductor_id: int, dias: int = 0, db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    if dias <= 0:
        cond.bloqueado = False
        cond.bloqueado_hasta = None
    else:
        cond.bloqueado = True
        cond.bloqueado_hasta = now_naive() + timedelta(days=dias)
    await db.commit()
    return {"ok": True, "bloqueado": cond.bloqueado, "bloqueado_hasta": cond.bloqueado_hasta.isoformat() if cond.bloqueado_hasta else None}


# ═══════════════════════════════════════════════════════
# ADMIN: SESIONES ACTIVAS EN VIVO (MAP DATA)
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/sesiones-vivo")
async def admin_sesiones_vivo(db: AsyncSession = Depends(get_db), admin=Depends(require_role("admin"))):
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.hora_fin == None)
    )
    sesiones = result.scalars().all()
    data = []
    for s in sesiones:
        esp = await db.get(Espacio, s.espacio_id)
        cond = await db.get(Conductor, s.conductor_id)
        data.append({
            "id": s.id,
            "lat": esp.lat if esp else None,
            "lng": esp.lng if esp else None,
            "ubicacion": esp.ubicacion if esp else "",
            "conductor": cond.nombre if cond else "",
            "patente": cond.patente if cond else "",
            "hora_inicio": s.hora_inicio.isoformat(),
            "metodo_pago": s.metodo_pago or "",
            "pagado": s.pagado,
        })
    return data
