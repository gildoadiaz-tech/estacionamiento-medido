import csv, io, httpx, random, math, secrets
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os

from app.database import init_db, get_db, async_session
from app.models import (
    Conductor, Permisionario, Admin, Espacio, Mano,
    SesionEstacionamiento, Pago, Deuda, Penalizacion,
    EmailVerification, Vehiculo, CuotaPermisionario,
    EstadoSesion, MetodoPago, MetodoIngreso, TipoVehiculo, LadoMano, ExencionTipo,
)
from app.schemas import *
from app.qr_utils import generar_qr_base64
from app.mercado_pago import crear_preferencia_pago
from app.mapa_data import CENTRO_SALTA
from app.idemsa_data import get_all_calles_cached, get_espacios_cached, sync_espacios_db
from app.auth_routes import router as auth_router
from app.deps import get_current_user, require_role, require_auth_page, require_role_page
from app.auth import hash_password, verify_password

PRECIO_AUTO = 700.0
PRECIO_MOTO = 300.0
HORARIO_CIERRE = 21
HORARIO_CIERRE_SAB = 14
DEUDA_MAXIMA = 10000.0
TOLERANCIA_MINUTOS = 5

ZONAS_NOCTURNAS = ["BALCARCE", "GÜEMES", "GUEMES", "ALVARADO"]
MP_DESCUENTO = 0.20  # 20% off for Mercado Pago

FERIADOS_2026 = {
    (1, 1),     # Año Nuevo
    (16, 2),    # Carnaval
    (17, 2),    # Carnaval
    (20, 2),    # Batalla de Salta (provincial)
    (24, 3),    # Memoria
    (2, 4),     # Malvinas / Jueves Santo
    (3, 4),     # Viernes Santo
    (1, 5),     # Día del Trabajador
    (25, 5),    # Revolución de Mayo
    (15, 6),    # Güemes (nacional, trasladado)
    (17, 6),    # Güemes (provincial, inamovible en Salta)
    (20, 6),    # Belgrano
    (9, 7),     # Independencia
    (17, 8),    # San Martín
    (15, 9),    # Virgen del Milagro (provincial)
    (12, 10),   # Diversidad Cultural
    (23, 11),   # Soberanía Nacional (trasladado)
    (8, 12),    # Inmaculada Concepción
    (25, 12),   # Navidad
}

DIAS_NO_LABORABLES_2026 = {
    (23, 3),    # puente turístico
    (10, 7),    # puente turístico
    (7, 12),    # puente turístico
}


def es_feriado(dt: datetime) -> bool:
    return (dt.day, dt.month) in FERIADOS_2026 or (dt.day, dt.month) in DIAS_NO_LABORABLES_2026


def es_zona_nocturna(ubicacion: str | None) -> bool:
    if not ubicacion:
        return False
    u = ubicacion.upper().strip()
    for z in ZONAS_NOCTURNAS:
        if z in u:
            return True
    return False


def _filtrar_espacios_por_mano(espacios: list, mano) -> list:
    result = []
    calle_upper = mano.calle.upper().strip()
    for e in espacios:
        if not e.ubicacion.upper().strip().startswith(calle_upper):
            continue
        parts = e.ubicacion.strip().split()
        if not parts:
            continue
        try:
            altura = int(parts[-1])
        except ValueError:
            result.append(e)
            continue
        if mano.altura_desde is not None and altura < mano.altura_desde:
            continue
        if mano.altura_hasta is not None and altura > mano.altura_hasta:
            continue
        result.append(e)
    return result

_espacios_cache = None

def _get_espacios():
    global _espacios_cache
    if _espacios_cache is None:
        _espacios_cache = get_espacios_cached()
    return _espacios_cache


async def ensure_test_users():
    if os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL"):
        return
    try:
        from app.database import init_db
        await init_db()
    except Exception:
        pass
    async with async_session() as db:
        existing = await db.execute(select(Admin))
        if existing.scalars().first():
            return

        admin = Admin(nombre="Administrador", username="admin", password_hash=hash_password("demo1234"))
        db.add(admin)

        juan = Permisionario(
            codigo="PERM001", nombre="Juan", apellido="Pérez",
            dni="30456789", email="juan@ejemplo.com", telefono="3874123456",
            password_hash=hash_password("demo1234"),
        )
        maria = Permisionario(
            codigo="PERM002", nombre="María", apellido="García",
            dni="28345678", email="maria@ejemplo.com", telefono="3874234567",
            password_hash=hash_password("demo1234"),
        )
        db.add_all([juan, maria])
        await db.flush()

        manos = [
            Mano(permisionario_id=juan.id, calle="GENERAL GUEMES", altura_desde=100, altura_hasta=200, lado="par", lat=-24.7869, lng=-65.4054),
            Mano(permisionario_id=juan.id, calle="GENERAL GUEMES", altura_desde=100, altura_hasta=200, lado="impar", lat=-24.7869, lng=-65.4054),
            Mano(permisionario_id=maria.id, calle="CASEROS", altura_desde=1100, altura_hasta=1200, lado="par", lat=-24.7892, lng=-65.4204),
        ]
        db.add_all(manos)
        await db.flush()

        conductores = [
            Conductor(dni="87654321", nombre="Pedro", apellido="López", email="pedro@ejemplo.com", telefono="3874345678", password_hash=hash_password("demo1234"), email_verified=True, exencion=ExencionTipo.ninguna),
            Conductor(dni="36234567", nombre="Ana", apellido="Martínez", email="ana@ejemplo.com", telefono="3874456789", password_hash=hash_password("demo1234"), email_verified=True, exencion=ExencionTipo.ninguna),
            Conductor(dni="30111222", nombre="Carlos", apellido="Ruiz", email="carlos.disc@ejemplo.com", telefono="3874567890", password_hash=hash_password("demo1234"), email_verified=True, exencion=ExencionTipo.discapacidad),
            Conductor(dni="29444555", nombre="Lucía", apellido="Fernández", email="lucia.frentista@ejemplo.com", telefono="3874678901", password_hash=hash_password("demo1234"), email_verified=True, exencion=ExencionTipo.frentista),
            Conductor(dni="20999888", nombre="Roberto", apellido="Gómez", email="roberto.veterano@ejemplo.com", telefono="3874789012", password_hash=hash_password("demo1234"), email_verified=True, exencion=ExencionTipo.veterano_malvinas),
            Conductor(dni="37555666", nombre="Eva", apellido="Torres", email="eva.bici@ejemplo.com", telefono="3874890123", password_hash=hash_password("demo1234"), email_verified=True, exencion=ExencionTipo.ninguna),
        ]
        db.add_all(conductores)
        await db.flush()

        vehiculos = [
            Vehiculo(conductor_id=conductores[0].id, patente="AB123CD", tipo=TipoVehiculo.auto, marca="Toyota", modelo="Corolla", predeterminado=True),
            Vehiculo(conductor_id=conductores[0].id, patente="AB456EF", tipo=TipoVehiculo.moto, marca="Honda", modelo="CG 150"),
            Vehiculo(conductor_id=conductores[1].id, patente="BC789GH", tipo=TipoVehiculo.camioneta, marca="Ford", modelo="Ranger", predeterminado=True),
            Vehiculo(conductor_id=conductores[2].id, patente="CD111AA", tipo=TipoVehiculo.auto, marca="Chevrolet", modelo="Corsa", predeterminado=True),
            Vehiculo(conductor_id=conductores[3].id, patente="EF222BB", tipo=TipoVehiculo.auto, marca="Volkswagen", modelo="Gol", predeterminado=True),
            Vehiculo(conductor_id=conductores[4].id, patente="GH333CC", tipo=TipoVehiculo.auto, marca="Fiat", modelo="Cronos", predeterminado=True),
            Vehiculo(conductor_id=conductores[5].id, patente="BI001BICI", tipo=TipoVehiculo.bicicleta, marca="Venzo", modelo="Urban", predeterminado=True),
        ]
        db.add_all(vehiculos)
        await db.commit()
        print("[SEED] Test users created")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception as e:
        print(f"[INIT] DB init failed: {e}")
    try:
        async with async_session() as session:
            await sync_espacios_db(session)
    except Exception as e:
        print(f"[INIT] IDEMSA sync failed: {e}")
    try:
        await ensure_test_users()
    except Exception as e:
        print(f"[INIT] Seed failed: {e}")
    yield


app = FastAPI(title="Estacionamiento Medido v2.0", lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROTECTED_PREFIXES = ("/conductor", "/permisionario", "/admin")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    needs_auth = any(path.startswith(p) for p in PROTECTED_PREFIXES)
    if needs_auth:
        token = request.cookies.get("token", "")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token and request.query_params.get("token"):
            token = request.query_params["token"]
        from app.auth import decode_token as _decode
        if not _decode(token):
            return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)


@app.get("/api/health")
async def health():
    import sys
    from app.database import DATABASE_URL as DB_URL
    db_type = "unknown"
    if "postgresql" in (DB_URL or ""):
        db_type = "postgresql"
    elif "sqlite" in (DB_URL or ""):
        db_type = "sqlite"
    if not os.getenv("DATABASE_URL") and not os.getenv("POSTGRES_URL"):
        db_type += " (/tmp - ephemeral)"
    return {
        "status": "ok",
        "python": sys.version,
        "database": db_type,
    }

app.include_router(auth_router, prefix="/api/auth")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def now_naive():
    return datetime.utcnow()


def calcular_costo_estacionamiento(inicio: datetime, fin: datetime, tipo_vehiculo: str = "auto", exencion: str = "ninguna", ubicacion: str | None = None) -> tuple[float, float]:
    if exencion and exencion != "ninguna":
        return 0.0, 0.0
    if tipo_vehiculo == "bicicleta":
        return 0.0, 0.0
    precio_hora = PRECIO_MOTO if tipo_vehiculo == "moto" else PRECIO_AUTO
    if inicio >= fin:
        return 0.0, 0.0
    if (fin - inicio).total_seconds() / 60 <= TOLERANCIA_MINUTOS:
        return 0.0, 0.0
    zona_nocturna = es_zona_nocturna(ubicacion)
    total = 0.0
    horas_no_diurnas = 0.0
    current = inicio
    while current < fin:
        wd = current.weekday()
        h = current.hour
        es_feriado_hoy = es_feriado(current)
        # Domingo: todo es no diurno (gratis)
        if wd == 6:
            prox = current.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            chunk = min(fin, prox)
            horas_no_diurnas += (chunk - current).total_seconds() / 3600
            current = chunk
            continue
        # Sabado: 7-14 diurno
        if wd == 5:
            diurno_inicio, diurno_fin = 7, 14
        else:
            diurno_inicio, diurno_fin = 7, 21
        nocturno_inicio, nocturno_fin = 22, 5
        # horario diurno → se cobra siempre (excepto feriados)
        if diurno_inicio <= h < diurno_fin:
            fin_rango = current.replace(hour=diurno_fin, minute=0, second=0, microsecond=0)
            chunk = min(fin, fin_rango)
            horas = (chunk - current).total_seconds() / 3600
            if es_feriado_hoy:
                horas_no_diurnas += horas
            else:
                total += horas * precio_hora
            current = chunk
            continue
        # horario nocturno (22-5)
        if h >= nocturno_inicio or h < nocturno_fin:
            if h >= nocturno_inicio:
                fin_rango = current.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1, hours=nocturno_fin)
            else:
                fin_rango = current.replace(hour=nocturno_fin, minute=0, second=0, microsecond=0)
            chunk = min(fin, fin_rango)
            horas = (chunk - current).total_seconds() / 3600
            if zona_nocturna:
                total += horas * precio_hora
            else:
                horas_no_diurnas += horas
            current = chunk
            continue
        # Fuera de horario (gaps: 21-22, 14-22 sab, 5-7) → no se cobra, va a pendientes
        if h < diurno_inicio:
            prox = current.replace(hour=diurno_inicio, minute=0, second=0, microsecond=0)
        elif h >= diurno_fin and h < nocturno_inicio:
            prox = current.replace(hour=nocturno_inicio, minute=0, second=0, microsecond=0)
        else:
            current += timedelta(hours=1)
            continue
        chunk = min(fin, prox)
        horas_no_diurnas += (chunk - current).total_seconds() / 3600
        current = chunk
    # Fraccionamiento 15 min desde 2da hora (Ordenanza 12.170)
    if total > 0:
        horas_cobradas = total / precio_hora
        if horas_cobradas <= 1:
            total = precio_hora
        else:
            extra_horas = horas_cobradas - 1
            bloques_15 = math.ceil(extra_horas * 4)
            total = precio_hora + (bloques_15 / 4) * precio_hora
    return round(total, 2), round(horas_no_diurnas, 2)


def get_precio_por_tipo(tipo_vehiculo: str) -> float:
    if tipo_vehiculo == "bicicleta":
        return 0.0
    return PRECIO_MOTO if tipo_vehiculo == "moto" else PRECIO_AUTO


async def get_exencion(conductor_id: int, db: AsyncSession) -> str:
    cond = await db.get(Conductor, conductor_id)
    if cond and hasattr(cond, 'exencion') and cond.exencion:
        return cond.exencion.value if hasattr(cond.exencion, 'value') else str(cond.exencion)
    return "ninguna"


def exencion_efectiva(exencion: str, frentista_calle: str | None, ubicacion: str | None) -> str:
    if exencion == "frentista" and frentista_calle and ubicacion:
        if not ubicacion.upper().startswith(frentista_calle.upper()):
            return "ninguna"
    return exencion


async def get_exencion_con_ubicacion(conductor_id: int, ubicacion: str, db: AsyncSession) -> str:
    cond = await db.get(Conductor, conductor_id)
    if cond and hasattr(cond, 'exencion') and cond.exencion:
        raw = cond.exencion.value if hasattr(cond.exencion, 'value') else str(cond.exencion)
        fcalle = getattr(cond, 'frentista_calle', None)
        return exencion_efectiva(raw, fcalle, ubicacion)
    return "ninguna"


async def calcular_costo_con_pendientes(
    sesion, conductor_id: int, ahora: datetime, db: AsyncSession,
    tipo: str | None = None, exencion: str | None = None, actualizar_pendientes: bool = False,
    ubicacion: str | None = None
) -> tuple[float, float, float, float]:
    """Calcula costo incluyendo horas_pendientes del conductor.
    Returns (costo_total, horas_no_diurnas_nuevas, horas_pendientes_viejas, costo_diurno)."""
    if tipo is None and sesion.vehiculo_id:
        veh = await db.get(Vehiculo, sesion.vehiculo_id)
        if veh:
            tipo = veh.tipo.value if hasattr(veh.tipo, 'value') else str(veh.tipo)
    if tipo is None:
        tipo = "auto"
    if ubicacion is None:
        espacio = await db.get(Espacio, sesion.espacio_id)
        ubicacion = espacio.ubicacion if espacio else ""
    if exencion is None:
        exencion = await get_exencion_con_ubicacion(conductor_id, ubicacion, db)

    costo_diurno, horas_no_diurnas = calcular_costo_estacionamiento(
        sesion.hora_inicio, ahora, tipo_vehiculo=tipo, exencion=exencion, ubicacion=ubicacion
    )
    cond = await db.get(Conductor, conductor_id)
    horas_pendientes_viejas = getattr(cond, 'horas_pendientes', 0.0) or 0.0
    precio_hora = get_precio_por_tipo(tipo)
    costo_total = costo_diurno + (horas_pendientes_viejas * precio_hora)

    if actualizar_pendientes:
        cond.horas_pendientes = horas_no_diurnas

    return round(costo_total, 2), horas_no_diurnas, horas_pendientes_viejas, costo_diurno


async def verificar_bloqueo(conductor_id: int, db: AsyncSession) -> dict:
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        return {"bloqueado": True, "motivo": "Conductor no encontrado"}
    if cond.bloqueado:
        return {"bloqueado": True, "motivo": "Bloqueado por el sistema"}
    if cond.saldo_deudor and cond.saldo_deudor >= DEUDA_MAXIMA:
        cond.bloqueado = True
        await db.commit()
        return {"bloqueado": True, "motivo": f"Deuda superior a ${DEUDA_MAXIMA:,.0f}"}
    return {"bloqueado": False, "motivo": None}


async def geocodificar(direccion: str) -> tuple[float, float] | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": f"{direccion}, Salta, Argentina", "format": "json", "limit": 1},
                headers={"User-Agent": "EstacionamientoMedido/2.0"},
                timeout=10,
            )
            data = resp.json()
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        pass
    return None


def _normalizar(s: str) -> str:
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
    q_norm = _normalizar(q)
    for c in get_all_calles_cached():
        nombre = _normalizar(c.get("nombre", "") or "")
        if q_norm in nombre or nombre in q_norm:
            pts = c.get("puntos", [])
            if pts:
                mid = len(pts) // 2
                return (pts[mid][0], pts[mid][1])
    return None


# ═══════════════════════════════════════════════════════
# PAGES
# ═══════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request):
    return templates.TemplateResponse(request, "demo.html", {})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {})


@app.get("/registro", response_class=HTMLResponse)
async def registro_page(request: Request):
    return templates.TemplateResponse(request, "auth/registro.html", {})


@app.get("/conductor", response_class=HTMLResponse)
async def conductor_home(request: Request):
    return templates.TemplateResponse(request, "conductor/index.html", {})


@app.get("/conductor/buscar", response_class=HTMLResponse)
async def conductor_buscar(request: Request):
    return templates.TemplateResponse(request, "conductor/buscar.html", {})


@app.get("/conductor/estacionar", response_class=HTMLResponse)
async def conductor_estacionar(request: Request):
    return templates.TemplateResponse(request, "conductor/estacionar.html", {})


@app.get("/conductor/checkout/{id}", response_class=HTMLResponse)
async def conductor_checkout(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SesionEstacionamiento).where(SesionEstacionamiento.id == id))
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    espacio = await db.get(Espacio, sesion.espacio_id)
    conductor = await db.get(Conductor, sesion.conductor_id)
    vehiculo = None
    if sesion.vehiculo_id:
        vehiculo = await db.get(Vehiculo, sesion.vehiculo_id)
    perm = None
    if espacio and espacio.permisionario_id:
        perm = await db.get(Permisionario, espacio.permisionario_id)
    return templates.TemplateResponse(request, "conductor/checkout.html", {
        "sesion": sesion, "espacio": espacio, "conductor": conductor,
        "vehiculo": vehiculo, "perm": perm,
    })


@app.get("/conductor/historial", response_class=HTMLResponse)
async def conductor_historial(request: Request):
    return templates.TemplateResponse(request, "conductor/historial.html", {})


@app.get("/conductor/perfil", response_class=HTMLResponse)
async def conductor_perfil(request: Request):
    return templates.TemplateResponse(request, "conductor/perfil.html", {})


@app.get("/conductor/vehiculos", response_class=HTMLResponse)
async def conductor_vehiculos(request: Request):
    return templates.TemplateResponse(request, "conductor/vehiculos.html", {})


@app.get("/permisionario", response_class=HTMLResponse)
async def permisionario_home(request: Request):
    return templates.TemplateResponse(request, "permisionario/index.html", {})


@app.get("/permisionario/panel", response_class=HTMLResponse)
async def permisionario_panel(request: Request):
    return templates.TemplateResponse(request, "permisionario/panel.html", {})


@app.get("/permisionario/qr", response_class=HTMLResponse)
async def permisionario_qr(request: Request):
    return templates.TemplateResponse(request, "permisionario/qr.html", {})


@app.get("/permisionario/espacios", response_class=HTMLResponse)
async def permisionario_espacios(request: Request):
    return templates.TemplateResponse(request, "permisionario/espacios.html", {})


@app.get("/permisionario/cuadra", response_class=HTMLResponse)
async def permisionario_cuadra(request: Request):
    return templates.TemplateResponse(request, "permisionario/cuadra.html", {})


@app.get("/permisionario/ingreso", response_class=HTMLResponse)
async def permisionario_ingreso(request: Request):
    return templates.TemplateResponse(request, "permisionario/ingreso.html", {})


@app.get("/permisionario/salida", response_class=HTMLResponse)
async def permisionario_salida(request: Request):
    return templates.TemplateResponse(request, "permisionario/salida.html", {})


@app.get("/permisionario/historial", response_class=HTMLResponse)
async def permisionario_historial(request: Request):
    return templates.TemplateResponse(request, "permisionario/historial.html", {})

@app.get("/permisionario/mapa", response_class=HTMLResponse)
async def permisionario_mapa(request: Request):
    return templates.TemplateResponse(request, "permisionario/mapa.html", {})

@app.get("/permisionario/reservas", response_class=HTMLResponse)
async def permisionario_reservas(request: Request):
    return templates.TemplateResponse(request, "permisionario/reservas.html", {})





@app.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request):
    return templates.TemplateResponse(request, "admin/index.html", {})


@app.get("/admin/conductores", response_class=HTMLResponse)
async def admin_conductores_page(request: Request):
    return templates.TemplateResponse(request, "admin/conductores.html", {})


@app.get("/admin/permisionarios", response_class=HTMLResponse)
async def admin_permisionarios_page(request: Request):
    return templates.TemplateResponse(request, "admin/permisionarios.html", {})


@app.get("/admin/permisionarios/{perm_id}/qr", response_class=HTMLResponse)
async def admin_permisionario_qr_page(request: Request, perm_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] not in ("admin",):
        raise HTTPException(403)
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    qr_data = f"{base_url}/conductor/estacionar?perm={perm.id}"
    qr_b64 = generar_qr_base64(qr_data)
    manos_result = await db.execute(select(Mano).where(Mano.permisionario_id == perm.id))
    manos = manos_result.scalars().all()
    return templates.TemplateResponse(request, "permisionario/qr_print.html", {
        "request": request,
        "perm": perm,
        "qr_base64": qr_b64,
        "qr_data": qr_data,
        "manos": manos,
    })





@app.get("/admin/espacios", response_class=HTMLResponse)
async def admin_espacios_page(request: Request):
    return templates.TemplateResponse(request, "admin/espacios.html", {})


@app.get("/admin/sesiones", response_class=HTMLResponse)
async def admin_sesiones_page(request: Request):
    return templates.TemplateResponse(request, "admin/sesiones_vivo.html", {})


@app.get("/admin/sesiones_vivo", response_class=HTMLResponse)
async def admin_sesiones_vivo_page(request: Request):
    return templates.TemplateResponse(request, "admin/sesiones_vivo.html", {})


@app.get("/admin/reportes", response_class=HTMLResponse)
async def admin_reportes_page(request: Request):
    return templates.TemplateResponse(request, "admin/reportes.html", {})


@app.get("/admin/deudas", response_class=HTMLResponse)
async def admin_deudas_page(request: Request):
    return templates.TemplateResponse(request, "admin/deudas.html", {})


# ═══════════════════════════════════════════════════════
# API: CONDUCTOR
# ═══════════════════════════════════════════════════════

@app.get("/api/conductor/me")
async def conductor_me(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    cond = await db.get(Conductor, current_user["id"])
    if not cond:
        raise HTTPException(404, "Conductor no encontrado")
    vehiculos_result = await db.execute(select(Vehiculo).where(Vehiculo.conductor_id == cond.id))
    vehiculos = vehiculos_result.scalars().all()
    return {
        "id": cond.id,
        "dni": cond.dni,
        "nombre": cond.nombre,
        "apellido": cond.apellido,
        "email": cond.email,
        "telefono": cond.telefono,
        "email_verified": cond.email_verified,
        "bloqueado": cond.bloqueado,
        "saldo_deudor": cond.saldo_deudor or 0,
        "horas_pendientes": getattr(cond, 'horas_pendientes', 0.0) or 0.0,
        "exencion": cond.exencion.value if hasattr(cond.exencion, 'value') else (cond.exencion or "ninguna"),
        "vehiculos": [
            {
                "id": v.id, "patente": v.patente, "tipo": v.tipo.value if hasattr(v.tipo, 'value') else v.tipo,
                "marca": v.marca, "modelo": v.modelo, "anio": v.anio,
                "predeterminado": v.predeterminado,
            }
            for v in vehiculos
        ],
    }


@app.put("/api/conductor/me")
async def conductor_update_me(
    data: ConductorUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    cond = await db.get(Conductor, current_user["id"])
    if not cond:
        raise HTTPException(404)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cond, field, value)
    await db.commit()
    await db.refresh(cond)
    return {
        "id": cond.id, "dni": cond.dni, "nombre": cond.nombre, "apellido": cond.apellido,
        "email": cond.email, "telefono": cond.telefono, "email_verified": cond.email_verified,
        "bloqueado": cond.bloqueado, "saldo_deudor": cond.saldo_deudor or 0,
    }


@app.post("/api/conductor/vehiculo")
async def conductor_add_vehiculo(
    data: VehiculoCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    existing = await db.execute(select(Vehiculo).where(Vehiculo.patente == data.patente.upper()))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Ya existe un vehiculo con esa patente")
    veh = Vehiculo(
        conductor_id=current_user["id"],
        patente=data.patente.upper(),
        tipo=data.tipo,
        marca=data.marca,
        modelo=data.modelo,
        anio=data.anio,
        predeterminado=data.predeterminado,
    )
    db.add(veh)
    await db.commit()
    await db.refresh(veh)
    return {
        "id": veh.id, "patente": veh.patente, "tipo": veh.tipo.value if hasattr(veh.tipo, 'value') else veh.tipo,
        "marca": veh.marca, "modelo": veh.modelo, "anio": veh.anio, "predeterminado": veh.predeterminado,
    }


@app.delete("/api/conductor/vehiculo/{vehiculo_id}")
async def conductor_remove_vehiculo(
    vehiculo_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    veh = await db.get(Vehiculo, vehiculo_id)
    if not veh or veh.conductor_id != current_user["id"]:
        raise HTTPException(404, "Vehiculo no encontrado")
    active = await db.execute(
        select(SesionEstacionamiento).where(
            SesionEstacionamiento.vehiculo_id == vehiculo_id,
            SesionEstacionamiento.estado == EstadoSesion.activa,
        )
    )
    if active.scalar_one_or_none():
        raise HTTPException(400, "No podes eliminar un vehiculo con sesion activa")
    await db.delete(veh)
    await db.commit()
    return {"ok": True}


@app.put("/api/conductor/vehiculo/{vehiculo_id}/predeterminado")
async def conductor_set_predeterminado(vehiculo_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    veh = await db.get(Vehiculo, vehiculo_id)
    if not veh or veh.conductor_id != current_user["id"]:
        raise HTTPException(404, "Vehiculo no encontrado")
    result = await db.execute(select(Vehiculo).where(Vehiculo.conductor_id == current_user["id"]))
    for v in result.scalars().all():
        v.predeterminado = (v.id == vehiculo_id)
    await db.commit()
    return {"ok": True}


@app.post("/api/conductor/pagar-multa")
async def conductor_pagar_multa(body: dict, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    cond = await db.get(Conductor, current_user["id"])
    if not cond:
        raise HTTPException(404, "Conductor no encontrado")
    monto = float(body.get("monto", cond.saldo_deudor or 0))
    if monto <= 0:
        raise HTTPException(400, "No hay deuda pendiente")
    cond.saldo_deudor = 0
    cond.bloqueado = False
    cond.bloqueado_hasta = None
    await db.commit()
    return {"ok": True, "monto_pagado": monto}


@app.get("/api/conductor/sesion-activa")
async def conductor_sesion_activa(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    cond = await db.get(Conductor, current_user["id"])
    if not cond:
        raise HTTPException(404, "Conductor no encontrado")
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.conductor_id == current_user["id"])
        .where(SesionEstacionamiento.estado == EstadoSesion.activa)
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        return None
    espacio = await db.get(Espacio, sesion.espacio_id)
    vehiculo = None
    if sesion.vehiculo_id:
        v = await db.get(Vehiculo, sesion.vehiculo_id)
        if v:
            vehiculo = {"id": v.id, "patente": v.patente, "tipo": v.tipo.value if hasattr(v.tipo, 'value') else v.tipo}
    tipo = (vehiculo and vehiculo["tipo"]) or "auto"
    exencion_raw = cond.exencion.value if hasattr(cond.exencion, 'value') else (cond.exencion or "ninguna")
    fcalle = getattr(cond, 'frentista_calle', None)
    ubic = (espacio.ubicacion if espacio else None)
    exencion_eff = exencion_efectiva(exencion_raw, fcalle, ubic)
    esGratis = exencion_eff != "ninguna" or tipo == "bicicleta"
    tarifa = 0 if esGratis else get_precio_por_tipo(tipo)
    if sesion.hora_fin is not None and sesion.costo_total is not None:
        costo = sesion.costo_total
        horas_pend_viejas = 0
        costo_diurno = costo
    else:
        ahora = now_naive()
        costo, _, horas_pend_viejas, costo_diurno = await calcular_costo_con_pendientes(
            sesion, sesion.conductor_id, ahora, db, tipo=tipo, exencion=exencion_eff
        )
    return {
        "id": sesion.id,
        "espacio_id": sesion.espacio_id,
        "conductor_id": sesion.conductor_id,
        "vehiculo_id": sesion.vehiculo_id,
        "hora_inicio": sesion.hora_inicio.isoformat(),
        "metodo_ingreso": sesion.metodo_ingreso.value if sesion.metodo_ingreso else None,
        "estado": sesion.estado.value,
        "ubicacion": ubic,
        "vehiculo": vehiculo,
        "exencion": exencion_raw,
        "tipo_vehiculo": tipo,
        "tarifa_por_hora": tarifa,
        "costo_estimado": 0 if esGratis else costo,
        "horas_pendientes_previas": horas_pend_viejas,
        "costo_diurno": costo_diurno,
        "es_gratuito": esGratis,
        "pago_pendiente": sesion.hora_fin is not None and not sesion.pagado,
        "codigo_salida": sesion.codigo_salida,
    }


@app.post("/api/conductor/checkin")
async def conductor_checkin(data: CheckInRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    conductor_id = current_user["id"]
    existing = await db.execute(
        select(SesionEstacionamiento).where(
            SesionEstacionamiento.conductor_id == conductor_id,
            SesionEstacionamiento.estado == EstadoSesion.activa,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Ya tenes una sesion activa. Finalizala antes de iniciar una nueva.")
    estado = await verificar_bloqueo(conductor_id, db)
    if estado["bloqueado"]:
        raise HTTPException(403, f"Conductor bloqueado: {estado['motivo']}")

    vehiculo_id = data.vehiculo_id
    if not vehiculo_id:
        result = await db.execute(
            select(Vehiculo).where(Vehiculo.conductor_id == conductor_id, Vehiculo.predeterminado == True)
        )
        veh = result.scalar_one_or_none()
        if not veh:
            result2 = await db.execute(select(Vehiculo).where(Vehiculo.conductor_id == conductor_id))
            veh = result2.scalars().first()
        if veh:
            vehiculo_id = veh.id
    else:
        veh = await db.get(Vehiculo, vehiculo_id)
        if not veh:
            raise HTTPException(404, "Vehiculo no encontrado")

    permisionario_id = data.permisionario_id
    espacio_id = data.espacio_id

    if not espacio_id and permisionario_id:
        result = await db.execute(
            select(Espacio).where(
                Espacio.permisionario_id == permisionario_id,
                Espacio.disponible == True
            ).limit(1)
        )
        espacio = result.scalar_one_or_none()
        if not espacio:
            raise HTTPException(400, "No hay espacios disponibles para este permisionario")
        espacio_id = espacio.id

    if not espacio_id:
        raise HTTPException(400, "Debe especificar espacio o permisionario")

    espacio = await db.get(Espacio, espacio_id)
    if not espacio:
        raise HTTPException(404, "Espacio no encontrado")
    if not espacio.disponible:
        raise HTTPException(400, "Espacio no disponible")

    if not permisionario_id and espacio.permisionario_id:
        permisionario_id = espacio.permisionario_id

    metodo_ingreso = MetodoIngreso.qr
    if data.metodo_ingreso:
        try:
            metodo_ingreso = MetodoIngreso(data.metodo_ingreso)
        except ValueError:
            pass

    codigo_salida = str(secrets.randbelow(9000) + 1000)
    sesion = SesionEstacionamiento(
        espacio_id=espacio_id,
        conductor_id=conductor_id,
        vehiculo_id=vehiculo_id,
        permisionario_id=permisionario_id,
        hora_inicio=now_naive(),
        metodo_ingreso=metodo_ingreso,
        codigo_salida=codigo_salida,
        estado=EstadoSesion.activa,
        pagado=False,
    )
    db.add(sesion)
    espacio.disponible = False
    await db.commit()
    await db.refresh(sesion)

    qr_data = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/conductor/checkout/{sesion.id}"
    qr_b64 = generar_qr_base64(qr_data)

    return {
        "ok": True,
        "sesion_id": sesion.id,
        "hora_inicio": sesion.hora_inicio.isoformat(),
        "espacio_id": sesion.espacio_id,
        "ubicacion": espacio.ubicacion,
        "vehiculo_id": sesion.vehiculo_id,
        "metodo_ingreso": sesion.metodo_ingreso.value,
        "codigo_salida": sesion.codigo_salida,
        "qr_salida": qr_b64,
    }


@app.get("/api/conductor/sesion-qr/{sesion_id}")
async def conductor_sesion_qr(sesion_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion or sesion.conductor_id != current_user["id"]:
        raise HTTPException(404, "Sesion no encontrada")
    qr_data = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/conductor/checkout/{sesion.id}"
    qr_b64 = generar_qr_base64(qr_data)
    return {"qr": qr_b64}


@app.post("/api/conductor/checkout/{sesion_id}")
async def conductor_checkout_api(sesion_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.estado != EstadoSesion.activa:
        raise HTTPException(400, "Sesion no esta activa")

    espacio = await db.get(Espacio, sesion.espacio_id)
    vehiculo = await db.get(Vehiculo, sesion.vehiculo_id) if sesion.vehiculo_id else None
    tipo = vehiculo.tipo.value if vehiculo and hasattr(vehiculo.tipo, 'value') else "auto"

    ahora = now_naive()
    costo_total, horas_no_diurnas, horas_pend_viejas, costo_diurno = await calcular_costo_con_pendientes(
        sesion, sesion.conductor_id, ahora, db, tipo=tipo
    )

    return {
        "sesion_id": sesion.id,
        "hora_inicio": sesion.hora_inicio.isoformat(),
        "costo_estimado": costo_total,
        "tipo_vehiculo": tipo,
        "precio_por_hora": get_precio_por_tipo(tipo),
        "ubicacion": espacio.ubicacion if espacio else None,
        "horas_pendientes_previas": horas_pend_viejas,
        "costo_diurno": costo_diurno,
    }


@app.post("/api/conductor/elegir-pago/{sesion_id}")
async def conductor_elegir_pago(sesion_id: int, body: ElegirPagoRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion or sesion.estado != EstadoSesion.activa:
        raise HTTPException(404, "Sesion no encontrada o no activa")
    if body.metodo not in ("efectivo", "mercadopago"):
        raise HTTPException(400, "Metodo de pago invalido")

    sesion.metodo_pago = MetodoPago.efectivo if body.metodo == "efectivo" else MetodoPago.mercadopago

    ahora = now_naive()
    monto_original, _, _, _ = await calcular_costo_con_pendientes(
        sesion, sesion.conductor_id, ahora, db
    )

    if body.metodo == "mercadopago":
        costo_final = round(monto_original * (1 - MP_DESCUENTO), 2)
        comision_municipio = 0.0  # municipio absorbe el descuento
        comision_permisionario = round(monto_original * 0.8, 2)
    else:
        costo_final = monto_original
        comision_municipio = round(monto_original * 0.2, 2)
        comision_permisionario = round(monto_original * 0.8, 2)

    sesion.costo_total = costo_final

    pago = Pago(
        sesion_id=sesion.id,
        monto=costo_final,
        monto_original=monto_original,
        metodo=sesion.metodo_pago,
        comision_municipio=comision_municipio,
        comision_permisionario=comision_permisionario,
        confirmado=False,
    )

    resp = {"ok": True, "metodo": body.metodo, "costo_total": costo_final, "monto_original": monto_original, "descuento_mp": MP_DESCUENTO if body.metodo == "mercadopago" else 0}

    if body.metodo == "mercadopago":
        cond = await db.get(Conductor, sesion.conductor_id)
        perm = await db.get(Permisionario, sesion.permisionario_id) if sesion.permisionario_id else None
        mp_result = await crear_preferencia_pago(
            monto=costo_final,
            concepto=f"Estacionamiento #{sesion.id}",
            conductor_email=cond.email if cond else "conductor@email.com",
            notification_url=f"{os.getenv('BASE_URL', 'http://localhost:8000')}/api/mp/webhook",
            external_reference=str(sesion.id),
            collector_id=perm.mp_collector_id if perm else None,
            marketplace_fee=comision_municipio,
        )
        pago.mp_preference_id = mp_result.get("preference_id", "")
        pago.mp_status = "pending"
        resp["init_point"] = mp_result.get("init_point", "")
        resp["preference_id"] = mp_result.get("preference_id", "")

    db.add(pago)
    await db.commit()
    return resp


@app.post("/api/conductor/self-checkout/{sesion_id}")
async def conductor_self_checkout(sesion_id: int, body: SelfCheckoutRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion or sesion.conductor_id != current_user["id"]:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.estado != EstadoSesion.activa:
        raise HTTPException(400, "La sesion no esta activa")
    if not sesion.codigo_salida:
        raise HTTPException(400, "Esta sesion no tiene codigo de salida")
    if sesion.codigo_salida != body.codigo_salida:
        raise HTTPException(403, "Codigo de salida incorrecto")
    if body.metodo not in ("efectivo", "mercadopago"):
        raise HTTPException(400, "Metodo de pago invalido")

    metodo_pago_enum = MetodoPago.efectivo if body.metodo == "efectivo" else MetodoPago.mercadopago
    sesion.metodo_pago = metodo_pago_enum

    ahora = now_naive()
    monto_original, _, _, _ = await calcular_costo_con_pendientes(
        sesion, sesion.conductor_id, ahora, db
    )

    if body.metodo == "mercadopago":
        costo_final = round(monto_original * (1 - MP_DESCUENTO), 2)
        comision_municipio = 0.0
        comision_permisionario = round(monto_original * 0.8, 2)
    else:
        costo_final = monto_original
        comision_municipio = round(monto_original * 0.2, 2)
        comision_permisionario = round(monto_original * 0.8, 2)

    sesion.costo_total = costo_final

    pago = Pago(
        sesion_id=sesion.id,
        monto=costo_final,
        monto_original=monto_original,
        metodo=sesion.metodo_pago,
        comision_municipio=comision_municipio,
        comision_permisionario=comision_permisionario,
        confirmado=False,
    )
    db.add(pago)

    if body.metodo == "efectivo":
        sesion.pagado = True
        sesion.hora_fin = ahora
        sesion.estado = EstadoSesion.finalizada
        pago.confirmado = True
        espacio = await db.get(Espacio, sesion.espacio_id)
        if espacio:
            espacio.disponible = True
        await db.commit()
        return {"ok": True, "metodo": "efectivo", "costo_total": costo_final, "monto_original": monto_original}
    else:
        cond = await db.get(Conductor, sesion.conductor_id)
        perm = await db.get(Permisionario, sesion.permisionario_id) if sesion.permisionario_id else None
        mp_result = await crear_preferencia_pago(
            monto=costo_final,
            concepto=f"Estacionamiento #{sesion.id}",
            conductor_email=cond.email if cond else "conductor@email.com",
            notification_url=f"{os.getenv('BASE_URL', 'http://localhost:8000')}/api/mp/webhook",
            external_reference=str(sesion.id),
            collector_id=perm.mp_collector_id if perm else None,
            marketplace_fee=comision_municipio,
        )
        pago.mp_preference_id = mp_result.get("preference_id", "")
        pago.mp_status = "pending"
        await db.commit()
        return {
            "ok": True,
            "metodo": "mercadopago",
            "costo_total": costo_final,
            "monto_original": monto_original,
            "descuento_mp": MP_DESCUENTO,
            "init_point": mp_result.get("init_point", ""),
            "preference_id": mp_result.get("preference_id", ""),
        }


@app.post("/api/conductor/confirmar-pago-efectivo/{sesion_id}")
async def conductor_confirmar_pago_efectivo(sesion_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion or sesion.estado != EstadoSesion.activa:
        raise HTTPException(404, "Sesion no encontrada o no activa")
    if sesion.metodo_pago != MetodoPago.efectivo:
        raise HTTPException(400, "Esta sesion no esta configurada para pago en efectivo")

    ahora = now_naive()
    costo_total, _, _, _ = await calcular_costo_con_pendientes(
        sesion, sesion.conductor_id, ahora, db, actualizar_pendientes=True
    )
    sesion.costo_total = costo_total
    sesion.pagado = True
    sesion.hora_fin = ahora
    sesion.estado = EstadoSesion.finalizada

    espacio = await db.get(Espacio, sesion.espacio_id)
    if espacio:
        espacio.disponible = True

    pago_result = await db.execute(select(Pago).where(Pago.sesion_id == sesion.id))
    pago = pago_result.scalar_one_or_none()
    if pago:
        pago.confirmado = True

    await db.commit()
    return {"ok": True, "costo_total": sesion.costo_total}


@app.get("/conductor/pago-mercadopago/{sesion_id}", response_class=HTMLResponse)
async def conductor_pago_mp_simulado(request: Request, sesion_id: int, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        return templates.TemplateResponse(request, "conductor/pago_resultado.html", {
            "titulo": "Sesión no encontrada",
            "mensaje": "No se encontró la sesión de estacionamiento.",
            "icono": "error",
        })
    costo = sesion.costo_total or 0
    veh = await db.get(Vehiculo, sesion.vehiculo_id) if sesion.vehiculo_id else None
    esp = await db.get(Espacio, sesion.espacio_id) if sesion.espacio_id else None
    return templates.TemplateResponse(request, "conductor/pago_mercadopago.html", {
        "sesion_id": sesion.id,
        "costo": round(costo, 2),
        "ubicacion": esp.ubicacion if esp else f"Espacio #{sesion.espacio_id}",
        "patente": veh.patente if veh else "",
    })


@app.post("/api/conductor/pago-mercadopago/{sesion_id}/confirmar")
async def conductor_pago_mp_confirmar(sesion_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.pagado:
        return {"ok": True, "mensaje": "Ya estaba pagado"}
    sesion.pagado = True
    sesion.estado = EstadoSesion.finalizada
    pago = await db.execute(
        select(Pago).where(Pago.sesion_id == sesion_id).order_by(Pago.id.desc())
    )
    pago_obj = pago.scalar_one_or_none()
    if pago_obj:
        pago_obj.confirmado = True
        pago_obj.mp_status = "approved"
    espacio = await db.get(Espacio, sesion.espacio_id)
    if espacio:
        espacio.disponible = True
    await db.commit()
    return {"ok": True, "mensaje": "Pago simulado con exito", "costo": sesion.costo_total}


@app.get("/api/conductor/pago-mercadopago/{sesion_id}/estado")
async def conductor_pago_mp_estado(sesion_id: int, db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    return {
        "pagado": sesion.pagado,
        "estado": sesion.estado.value if hasattr(sesion.estado, 'value') else str(sesion.estado),
        "costo": sesion.costo_total or 0,
    }


@app.get("/api/conductor/historial")
async def conductor_historial_api(
    page: int = 1,
    limit: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] != "conductor":
        raise HTTPException(403, "Solo conductores")
    offset = (page - 1) * limit
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.conductor_id == current_user["id"])
        .order_by(SesionEstacionamiento.hora_inicio.desc())
        .offset(offset)
        .limit(limit)
    )
    sesiones = result.scalars().all()
    data = []
    for s in sesiones:
        esp = await db.get(Espacio, s.espacio_id)
        veh = await db.get(Vehiculo, s.vehiculo_id) if s.vehiculo_id else None
        data.append({
            "id": s.id,
            "espacio_id": s.espacio_id,
            "ubicacion": esp.ubicacion if esp else "",
            "vehiculo_patente": veh.patente if veh else "",
            "vehiculo_tipo": veh.tipo.value if veh and hasattr(veh.tipo, 'value') else "",
            "hora_inicio": s.hora_inicio.isoformat(),
            "hora_fin": s.hora_fin.isoformat() if s.hora_fin else None,
            "costo_total": s.costo_total or 0,
            "metodo_pago": s.metodo_pago.value if s.metodo_pago else None,
            "metodo_ingreso": s.metodo_ingreso.value if s.metodo_ingreso else None,
            "estado": s.estado.value,
            "pagado": s.pagado,
        })
    return {"sesiones": data, "page": page, "limit": limit}


@app.get("/api/conductor/comprobante/{sesion_id}")
async def conductor_comprobante(sesion_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404)
    if sesion.conductor_id != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(403)
    espacio = await db.get(Espacio, sesion.espacio_id)
    conductor = await db.get(Conductor, sesion.conductor_id)
    vehiculo = await db.get(Vehiculo, sesion.vehiculo_id) if sesion.vehiculo_id else None
    perm = await db.get(Permisionario, sesion.permisionario_id) if sesion.permisionario_id else None
    return {
        "sesion_id": sesion.id,
        "conductor": f"{conductor.nombre} {conductor.apellido}" if conductor else "",
        "patente": vehiculo.patente if vehiculo else "",
        "tipo_vehiculo": vehiculo.tipo.value if vehiculo and hasattr(vehiculo.tipo, 'value') else "",
        "ubicacion": espacio.ubicacion if espacio else "",
        "hora_inicio": sesion.hora_inicio.isoformat(),
        "hora_fin": sesion.hora_fin.isoformat() if sesion.hora_fin else None,
        "costo_total": sesion.costo_total or 0,
        "metodo_pago": sesion.metodo_pago.value if sesion.metodo_pago else "",
        "estado": sesion.estado.value,
        "permisionario": f"{perm.nombre} {perm.apellido}" if perm else "",
    }


@app.post("/api/conductor/password")
async def conductor_password(
    body: PasswordChangeRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cond = await db.get(Conductor, current_user["id"])
    if not cond or not verify_password(body.current_password, cond.password_hash):
        raise HTTPException(400, "Contraseña actual incorrecta")
    cond.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True, "mensaje": "Contraseña actualizada"}


# ═══════════════════════════════════════════════════════
# API: PERMISIONARIO
# ═══════════════════════════════════════════════════════

@app.get("/api/permisionario/me")
async def permisionario_me(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403, "Solo permisionarios")
    perm = await db.get(Permisionario, current_user["id"])
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")
    manos_result = await db.execute(select(Mano).where(Mano.permisionario_id == perm.id))
    manos = manos_result.scalars().all()
    espacio_ids = []
    espacio_list = []
    raw_espacios = []
    for m in manos:
        esp_result = await db.execute(select(Espacio).where(Espacio.mano_id == m.id))
        for e in esp_result.scalars().all():
            if e.id not in espacio_ids:
                espacio_ids.append(e.id)
                raw_espacios.append(e)
    if not raw_espacios and manos:
        calles = [m.calle.upper().strip() for m in manos]
        cond = Espacio.ubicacion.in_(calles)
        for c in calles:
            cond = cond | Espacio.ubicacion.like(f"%{c}%")
        esp_result = await db.execute(select(Espacio).where(cond))
        raw_espacios = esp_result.scalars().all()
    seen_ids = set()
    espacio_list = []
    for m in manos:
        for e in _filtrar_espacios_por_mano(raw_espacios, m):
            if e.id not in seen_ids:
                seen_ids.add(e.id)
                espacio_list.append({
                    "id": e.id, "ubicacion": e.ubicacion,
                    "precio_por_hora": e.precio_por_hora, "disponible": e.disponible,
                    "lat": e.lat, "lng": e.lng,
                })
    if not espacio_list and manos:
        calles = [m.calle.upper().strip() for m in manos]
        cond = Espacio.ubicacion.in_(calles)
        for c in calles:
            cond = cond | Espacio.ubicacion.like(f"%{c}%")
        esp_result = await db.execute(select(Espacio).where(cond))
        all_espacios = esp_result.scalars().all()
        for m in manos:
            for e in _filtrar_espacios_por_mano(all_espacios, m):
                if e.id not in espacio_ids:
                    espacio_ids.append(e.id)
                    espacio_list.append({
                        "id": e.id, "ubicacion": e.ubicacion,
                        "precio_por_hora": e.precio_por_hora, "disponible": e.disponible,
                        "lat": e.lat, "lng": e.lng,
                    })
    return {
        "id": perm.id, "codigo": perm.codigo,
        "nombre": perm.nombre, "apellido": perm.apellido,
        "dni": perm.dni, "email": perm.email, "telefono": perm.telefono,
        "activo": perm.activo,
        "manos": [
            {
                "id": m.id, "calle": m.calle,
                "altura_desde": m.altura_desde, "altura_hasta": m.altura_hasta,
                "lado": m.lado.value if hasattr(m.lado, 'value') else m.lado,
            }
            for m in manos
        ],
        "espacios": espacio_list,
    }


@app.get("/api/permisionario/espacios")
async def permisionario_espacios_api(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403)
    manos_result = await db.execute(select(Mano).where(Mano.permisionario_id == current_user["id"]))
    manos = manos_result.scalars().all()
    if not manos:
        return []
    mano_ids = [m.id for m in manos]
    esp_result = await db.execute(select(Espacio).where(Espacio.mano_id.in_(mano_ids)))
    raw_espacios = esp_result.scalars().all()
    if not raw_espacios:
        calles = [m.calle.upper().strip() for m in manos]
        cond = Espacio.ubicacion.in_(calles)
        for c in calles:
            cond = cond | Espacio.ubicacion.like(f"%{c}%")
        esp_result = await db.execute(select(Espacio).where(cond))
        raw_espacios = esp_result.scalars().all()
    seen_ids = set()
    espacios = []
    for m in manos:
        for e in _filtrar_espacios_por_mano(raw_espacios, m):
            if e.id not in seen_ids:
                seen_ids.add(e.id)
                espacios.append(e)
    data = []
    for e in espacios:
        sesion_activa = None
        result_s = await db.execute(
            select(SesionEstacionamiento).where(
                SesionEstacionamiento.espacio_id == e.id,
                SesionEstacionamiento.estado == EstadoSesion.activa,
            )
        )
        s = result_s.scalar_one_or_none()
        if s:
            veh = await db.get(Vehiculo, s.vehiculo_id) if s.vehiculo_id else None
            scond = await db.get(Conductor, s.conductor_id) if s.conductor_id else None
            sesion_activa = {
                "id": s.id,
                "patente": veh.patente if veh else "",
                "tipo_vehiculo": veh.tipo.value if veh and hasattr(veh.tipo, 'value') else "",
                "vehiculo": {"id": veh.id, "patente": veh.patente, "tipo": veh.tipo.value if veh and hasattr(veh.tipo, 'value') else ""} if veh else None,
                "exencion": scond.exencion.value if scond and hasattr(scond.exencion, 'value') else (scond.exencion or "ninguna") if scond else "ninguna",
                "hora_inicio": s.hora_inicio.isoformat(),
                "metodo_ingreso": s.metodo_ingreso.value if s.metodo_ingreso else None,
            }
        data.append({
            "id": e.id, "ubicacion": e.ubicacion,
            "precio_por_hora": e.precio_por_hora, "disponible": e.disponible,
            "lat": e.lat, "lng": e.lng,
            "sesion_activa": sesion_activa,
        })
    return data


@app.get("/api/permisionario/sesiones-activas")
async def permisionario_sesiones_activas(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403)
    manos_result = await db.execute(select(Mano).where(Mano.permisionario_id == current_user["id"]))
    manos = manos_result.scalars().all()
    mano_ids = [m.id for m in manos]
    if not mano_ids:
        return []
    esp_result = await db.execute(select(Espacio).where(Espacio.mano_id.in_(mano_ids)))
    raw_espacios = esp_result.scalars().all()
    if not raw_espacios:
        calles = [m.calle.upper().strip() for m in manos]
        cond = Espacio.ubicacion.in_(calles)
        for c in calles:
            cond = cond | Espacio.ubicacion.like(f"%{c}%")
        esp_result = await db.execute(select(Espacio).where(cond))
        raw_espacios = esp_result.scalars().all()
    seen_ids = set()
    espacio_ids = []
    for m in manos:
        for e in _filtrar_espacios_por_mano(raw_espacios, m):
            if e.id not in seen_ids:
                seen_ids.add(e.id)
                espacio_ids.append(e.id)
    if not espacio_ids:
        return []
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.espacio_id.in_(espacio_ids))
        .where(SesionEstacionamiento.estado == EstadoSesion.activa)
        .order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    sesiones = result.scalars().all()
    data = []
    ahora = now_naive()
    for s in sesiones:
        esp = await db.get(Espacio, s.espacio_id)
        cond = await db.get(Conductor, s.conductor_id)
        veh = await db.get(Vehiculo, s.vehiculo_id) if s.vehiculo_id else None
        tipo = veh.tipo.value if veh and hasattr(veh.tipo, 'value') else "auto"
        exencion_val = cond.exencion.value if cond and hasattr(cond.exencion, 'value') else (cond.exencion or "ninguna") if cond else "ninguna"
        fcalle = getattr(cond, 'frentista_calle', None) if cond else None
        ubic = esp.ubicacion if esp else ""
        exencion_eff = exencion_efectiva(exencion_val, fcalle, ubic)
        es_gratuito = exencion_eff != "ninguna" or tipo == "bicicleta"
        tarifa = get_precio_por_tipo(tipo)
        if s.hora_fin is not None and s.costo_total is not None:
            costo = s.costo_total
            pago_pendiente = not s.pagado
        else:
            costo, _, _, _ = await calcular_costo_con_pendientes(
                s, s.conductor_id, ahora, db, tipo=tipo, exencion=exencion_eff
            )
            pago_pendiente = False
        data.append({
            "id": s.id, "espacio_id": s.espacio_id,
            "ubicacion": ubic,
            "conductor_nombre": f"{cond.nombre} {cond.apellido}" if cond else "",
            "patente": veh.patente if veh else "",
            "tipo_vehiculo": tipo,
            "vehiculo": {"id": veh.id, "patente": veh.patente, "tipo": tipo} if veh else None,
            "exencion": exencion_val,
            "tarifa_por_hora": tarifa,
            "costo_estimado": round(costo, 2),
            "es_gratuito": es_gratuito,
            "pago_pendiente": pago_pendiente,
            "hora_inicio": s.hora_inicio.isoformat(),
            "metodo_ingreso": s.metodo_ingreso.value if s.metodo_ingreso else None,
            "estado": s.estado.value,
        })
    return data


@app.post("/api/permisionario/registro-manual")
async def permisionario_registro_manual(body: RegistroManualRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403, "Solo permisionarios")
    perm = await db.get(Permisionario, body.permisionario_id)
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")
    espacio = None
    if body.espacio_id:
        espacio = await db.get(Espacio, body.espacio_id)
    else:
        manos_result = await db.execute(select(Mano).where(Mano.permisionario_id == body.permisionario_id))
        manos = manos_result.scalars().all()
        mano_ids = [m.id for m in manos]
        raw_espacios = []
        if mano_ids:
            result = await db.execute(
                select(Espacio).where(Espacio.mano_id.in_(mano_ids), Espacio.disponible == True)
            )
            raw_espacios = result.scalars().all()
        if not raw_espacios and manos:
            calles = [m.calle.upper().strip() for m in manos]
            cond = Espacio.ubicacion.in_(calles)
            for c in calles:
                cond = cond | Espacio.ubicacion.like(f"%{c}%")
            result = await db.execute(select(Espacio).where(cond, Espacio.disponible == True))
            raw_espacios = result.scalars().all()
        for m in manos:
            matched = _filtrar_espacios_por_mano(raw_espacios, m)
            if matched:
                espacio = matched[0]
                break
    if not espacio:
        raise HTTPException(404, "No hay espacio disponible")
    if not espacio.disponible:
        raise HTTPException(400, "Espacio no disponible")

    result = await db.execute(select(Vehiculo).where(Vehiculo.patente == body.patente.upper()).limit(1))
    vehiculo = result.scalar_one_or_none()
    conductor = None
    if vehiculo:
        conductor = await db.get(Conductor, vehiculo.conductor_id)
    if not conductor:
        conductor = Conductor(
            dni=f"MANUAL_{body.patente.upper()}",
            nombre=f"Manual - {body.patente.upper()}",
            apellido="",
            email=f"manual_{body.patente.lower()}@guest.app",
            password_hash="",
            email_verified=True,
        )
        db.add(conductor)
        await db.flush()
    if not vehiculo:
        vehiculo = Vehiculo(
            conductor_id=conductor.id,
            patente=body.patente.upper(),
            tipo=TipoVehiculo.auto,
            predeterminado=True,
        )
        db.add(vehiculo)
        await db.flush()

    sesion = SesionEstacionamiento(
        espacio_id=espacio.id,
        conductor_id=conductor.id,
        vehiculo_id=vehiculo.id if vehiculo else None,
        permisionario_id=perm.id,
        hora_inicio=now_naive(),
        metodo_ingreso=MetodoIngreso.manual,
        estado=EstadoSesion.activa,
        pagado=False,
    )
    db.add(sesion)
    espacio.disponible = False
    await db.commit()
    await db.refresh(sesion)
    return {
        "ok": True, "sesion_id": sesion.id,
        "conductor_id": conductor.id, "conductor_nombre": f"{conductor.nombre} {conductor.apellido}".strip(),
    }


@app.post("/api/permisionario/confirmar-ingreso/{sesion_id}")
async def permisionario_confirmar_ingreso(sesion_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403, "Solo permisionarios")
    sesion = await db.get(SesionEstacionamiento, sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.estado != EstadoSesion.activa:
        raise HTTPException(400, "Sesion no esta activa")
    if sesion.metodo_ingreso != MetodoIngreso.aqui:
        raise HTTPException(400, "Solo se pueden confirmar ingresos 'aqui'")
    return {"ok": True, "sesion_id": sesion.id, "estado": sesion.estado.value}


@app.post("/api/permisionario/salida")
async def permisionario_salida(body: SalidaRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403, "Solo permisionarios")
    sesion = await db.get(SesionEstacionamiento, body.sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")
    if sesion.estado != EstadoSesion.activa:
        raise HTTPException(400, "Sesion no esta activa")

    ahora = now_naive()
    costo, _, _, _ = await calcular_costo_con_pendientes(
        sesion, sesion.conductor_id, ahora, db, actualizar_pendientes=True
    )

    metodo_pago = MetodoPago.efectivo
    if body.metodo_pago == "mercadopago":
        metodo_pago = MetodoPago.mercadopago
        costo = round(costo * (1 - MP_DESCUENTO), 2)

    sesion.costo_total = costo
    sesion.hora_fin = ahora
    sesion.metodo_pago = metodo_pago

    if metodo_pago == MetodoPago.efectivo:
        sesion.pagado = True
        sesion.estado = EstadoSesion.finalizada
        espacio = await db.get(Espacio, sesion.espacio_id)
        if espacio:
            espacio.disponible = True
    else:
        sesion.pagado = False
        sesion.estado = EstadoSesion.activa

    pago = Pago(
        sesion_id=sesion.id,
        monto=costo,
        metodo=metodo_pago,
        confirmado=metodo_pago == MetodoPago.efectivo,
    )
    db.add(pago)

    if metodo_pago == MetodoPago.mercadopago:
        cond = await db.get(Conductor, sesion.conductor_id)
        perm = await db.get(Permisionario, sesion.permisionario_id) if sesion.permisionario_id else None
        mp_result = await crear_preferencia_pago(
            monto=costo,
            concepto=f"Estacionamiento #{sesion.id}",
            conductor_email=cond.email if cond else "conductor@email.com",
            notification_url=f"{os.getenv('BASE_URL', 'http://localhost:8000')}/api/mp/webhook",
            external_reference=str(sesion.id),
            collector_id=perm.mp_collector_id if perm else None,
            marketplace_fee=0.0,
        )
        pago.mp_preference_id = mp_result.get("preference_id", "")
        pago.mp_status = "pending"

    await db.commit()

    resp = {"ok": True, "sesion_id": sesion.id, "costo_total": costo}
    if metodo_pago == MetodoPago.mercadopago and pago.mp_preference_id:
        resp["init_point"] = mp_result.get("init_point", "")
        resp["preference_id"] = pago.mp_preference_id
    return resp


@app.post("/api/permisionario/reportar-deuda")
async def permisionario_reportar_deuda(body: ReporteDeudaRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403, "Solo permisionarios")
    sesion = await db.get(SesionEstacionamiento, body.sesion_id)
    if not sesion:
        raise HTTPException(404, "Sesion no encontrada")

    ahora = now_naive()
    costo, _, _, _ = await calcular_costo_con_pendientes(
        sesion, sesion.conductor_id, ahora, db, actualizar_pendientes=True
    )

    sesion.costo_total = costo
    sesion.hora_fin = ahora
    sesion.estado = EstadoSesion.deuda
    sesion.pagado = False

    conductor = await db.get(Conductor, sesion.conductor_id)
    if conductor:
        conductor.saldo_deudor = (conductor.saldo_deudor or 0) + costo

    deuda = Deuda(
        conductor_id=sesion.conductor_id,
        sesion_id=sesion.id,
        monto=costo,
        reported_by=body.permisionario_id,
        motivo=body.motivo or "Salida sin pago",
    )
    db.add(deuda)

    espacio = await db.get(Espacio, sesion.espacio_id)
    if espacio:
        espacio.disponible = True

    await db.commit()
    return {"ok": True, "deuda_id": deuda.id, "monto": costo}


@app.get("/api/permisionario/historial")
async def permisionario_historial_api(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403)
    manos_result = await db.execute(select(Mano).where(Mano.permisionario_id == current_user["id"]))
    manos = manos_result.scalars().all()
    mano_ids = [m.id for m in manos]
    if not mano_ids:
        return []
    esp_result = await db.execute(select(Espacio).where(Espacio.mano_id.in_(mano_ids)))
    espacio_ids = [e.id for e in esp_result.scalars().all()]
    if not espacio_ids:
        return []
    today = now_naive().strftime("%Y-%m-%d")
    result = await db.execute(
        select(SesionEstacionamiento)
        .where(SesionEstacionamiento.espacio_id.in_(espacio_ids))
        .where(func.date(SesionEstacionamiento.hora_inicio) == today)
        .order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    sesiones = result.scalars().all()
    data = []
    for s in sesiones:
        esp = await db.get(Espacio, s.espacio_id)
        cond = await db.get(Conductor, s.conductor_id)
        veh = await db.get(Vehiculo, s.vehiculo_id) if s.vehiculo_id else None
        data.append({
            "id": s.id, "espacio_id": s.espacio_id,
            "ubicacion": esp.ubicacion if esp else "",
            "conductor_nombre": f"{cond.nombre} {cond.apellido}" if cond else "",
            "patente": veh.patente if veh else "",
            "hora_inicio": s.hora_inicio.isoformat(),
            "hora_fin": s.hora_fin.isoformat() if s.hora_fin else None,
            "costo_total": s.costo_total or 0,
            "metodo_pago": s.metodo_pago.value if s.metodo_pago else None,
            "estado": s.estado.value,
            "pagado": s.pagado,
        })
    return data


@app.get("/api/permisionario/qr-data")
async def permisionario_qr_data(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403)
    perm = await db.get(Permisionario, current_user["id"])
    if not perm:
        raise HTTPException(404)
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    qr_data = f"{base_url}/conductor/estacionar?perm={perm.id}"
    qr_b64 = generar_qr_base64(qr_data)
    manos_result = await db.execute(select(Mano).where(Mano.permisionario_id == perm.id))
    manos = manos_result.scalars().all()
    return {
        "permisionario_id": perm.id,
        "codigo": perm.codigo,
        "nombre": f"{perm.nombre} {perm.apellido}",
        "qr_base64": qr_b64,
        "qr_data": qr_data,
        "manos": [
            {
                "id": m.id, "calle": m.calle,
                "lado": m.lado.value if hasattr(m.lado, 'value') else m.lado,
                "altura_desde": m.altura_desde, "altura_hasta": m.altura_hasta,
            }
            for m in manos
        ],
}


@app.get("/api/admin/permisionarios/{perm_id}/qr")
async def admin_permisionario_qr(perm_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] not in ("admin",):
        raise HTTPException(403)
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    qr_data = f"{base_url}/conductor/estacionar?perm={perm.id}"
    qr_b64 = generar_qr_base64(qr_data)
    manos_result = await db.execute(select(Mano).where(Mano.permisionario_id == perm.id))
    manos = manos_result.scalars().all()
    return {
        "permisionario_id": perm.id,
        "codigo": perm.codigo,
        "nombre": f"{perm.nombre} {perm.apellido}",
        "qr_base64": qr_b64,
        "qr_data": qr_data,
        "manos": [
            {
                "id": m.id, "calle": m.calle,
                "lado": m.lado.value if hasattr(m.lado, 'value') else m.lado,
                "altura_desde": m.altura_desde, "altura_hasta": m.altura_hasta,
            }
            for m in manos
        ],
    }


@app.get("/api/reservas/pendientes/{perm_id}")
async def reservas_pendientes(perm_id: int, db: AsyncSession = Depends(get_db)):
    return []

@app.get("/api/reservas/permisionario/{perm_id}")
async def reservas_permisionario(perm_id: int, db: AsyncSession = Depends(get_db)):
    return []

@app.post("/api/reservas/aprobar")
async def reservas_aprobar(body: dict = None, db: AsyncSession = Depends(get_db)):
    return {"ok": True}


# ═════════════════════════════════════════════════════════
# API: GESTOR
# ═══════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════
# API: ADMIN
# ═══════════════════════════════════════════════════════

@app.post("/api/admin/permisionario")
async def admin_create_permisionario(data: PermisionarioCreate, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Permisionario).where(Permisionario.dni == data.dni))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Ya existe un permisionario con ese DNI")
    existing_email = await db.execute(select(Permisionario).where(Permisionario.email == data.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(400, "Ya existe un permisionario con ese email")
    codigo = f"PER{data.dni}"
    perm = Permisionario(
        codigo=codigo, nombre=data.nombre, apellido=data.apellido,
        dni=data.dni, email=data.email, telefono=data.telefono, cvu=data.cvu,
        password_hash=hash_password(secrets.token_hex(4)), activo=True,
    )
    db.add(perm)
    await db.flush()
    for i, calle in enumerate(data.calles):
        lado = data.lados[i] if i < len(data.lados) else "par"
        try:
            lado_enum = LadoMano(lado)
        except ValueError:
            lado_enum = LadoMano.par
        mano = Mano(permisionario_id=perm.id, calle=calle, lado=lado_enum)
        db.add(mano)
    await db.commit()
    await db.refresh(perm)
    return {"ok": True, "id": perm.id, "codigo": perm.codigo}


@app.get("/api/admin/conductores")
async def admin_list_conductores(current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conductor).order_by(Conductor.id.desc()).limit(200))
    data = []
    for c in result.scalars().all():
        veh_result = await db.execute(select(Vehiculo).where(Vehiculo.conductor_id == c.id))
        vehiculos = veh_result.scalars().all()
        data.append({
            "id": c.id, "dni": c.dni, "nombre": c.nombre, "apellido": c.apellido,
            "email": c.email, "telefono": c.telefono,
            "email_verified": c.email_verified, "bloqueado": c.bloqueado,
            "saldo_deudor": c.saldo_deudor or 0,
            "horas_pendientes": getattr(c, 'horas_pendientes', 0.0) or 0.0,
            "exencion": c.exencion.value if hasattr(c.exencion, 'value') else str(c.exencion),
            "frentista_calle": getattr(c, 'frentista_calle', None),
            "vehiculos": [
                {"id": v.id, "patente": v.patente, "tipo": v.tipo.value if hasattr(v.tipo, 'value') else v.tipo}
                for v in vehiculos
            ],
        })
    return data


@app.put("/api/admin/conductores/{conductor_id}")
async def admin_edit_conductor(conductor_id: int, data: ConductorUpdate, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cond, field, value)
    await db.commit()
    await db.refresh(cond)
    return {"ok": True, "id": cond.id}


@app.delete("/api/admin/conductores/{conductor_id}")
async def admin_delete_conductor(conductor_id: int, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    await db.delete(cond)
    await db.commit()
    return {"ok": True}


@app.put("/api/admin/permisionarios/{perm_id}")
async def admin_edit_permisionario(perm_id: int, data: PermisionarioUpdate, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(perm, field, value)
    await db.commit()
    await db.refresh(perm)
    return {"ok": True, "id": perm.id}


@app.delete("/api/admin/permisionarios/{perm_id}")
async def admin_delete_permisionario(perm_id: int, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    await db.delete(perm)
    await db.commit()
    return {"ok": True}


@app.get("/api/admin/sesiones-vivo")
async def admin_sesiones_vivo(current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).order_by(SesionEstacionamiento.hora_inicio.desc()).limit(200)
    )
    sesiones = result.scalars().all()
    data = []
    for s in sesiones:
        esp = await db.get(Espacio, s.espacio_id)
        cond = await db.get(Conductor, s.conductor_id)
        veh = await db.get(Vehiculo, s.vehiculo_id) if s.vehiculo_id else None
        data.append({
            "id": s.id, "lat": esp.lat if esp else None, "lng": esp.lng if esp else None,
            "ubicacion": esp.ubicacion if esp else "",
            "conductor": f"{cond.nombre} {cond.apellido}" if cond else "",
            "patente": veh.patente if veh else "",
            "tipo_vehiculo": veh.tipo.value if veh and hasattr(veh.tipo, "value") else "",
            "hora_inicio": s.hora_inicio.isoformat() if s.hora_inicio else None,
            "hora_fin": s.hora_fin.isoformat() if s.hora_fin else None,
            "metodo_ingreso": s.metodo_ingreso.value if s.metodo_ingreso else "",
            "metodo_pago": s.metodo_pago.value if s.metodo_pago else "",
            "estado": s.estado.value,
            "pagado": s.pagado,
            "costo_total": s.costo_total,
            "exencion": s.exencion.value if s.exencion else "",
        })
    return data


@app.get("/api/admin/reportes")
async def admin_reportes(current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    r1 = await db.execute(select(func.count(SesionEstacionamiento.id)))
    total_sesiones = r1.scalar() or 0
    r2 = await db.execute(select(func.coalesce(func.sum(SesionEstacionamiento.costo_total), 0)))
    total_recaudado = float(r2.scalar() or 0)
    r3 = await db.execute(select(func.count(SesionEstacionamiento.id)).where(SesionEstacionamiento.estado == EstadoSesion.activa))
    activas = r3.scalar() or 0
    r4 = await db.execute(select(func.count(Conductor.id)))
    total_conductores = r4.scalar() or 0
    r5 = await db.execute(select(func.count(Permisionario.id)))
    total_permisionarios = r5.scalar() or 0
    r6 = await db.execute(select(func.coalesce(func.sum(Deuda.monto), 0)).where(Deuda.pagada == False))
    deuda_total = float(r6.scalar() or 0)
    r7 = await db.execute(select(func.count(Vehiculo.id)))
    total_vehiculos = r7.scalar() or 0

    r8 = await db.execute(select(func.coalesce(func.sum(Pago.comision_municipio), 0)).where(Pago.confirmado == True))
    comision_municipio = float(r8.scalar() or 0)
    r9 = await db.execute(select(func.coalesce(func.sum(Pago.comision_permisionario), 0)).where(Pago.confirmado == True))
    comision_permisionario = float(r9.scalar() or 0)
    r10 = await db.execute(select(func.coalesce(func.sum(Pago.monto_original), 0)).where(Pago.confirmado == True))
    total_bruto = float(r10.scalar() or 0)

    return {
        "total_sesiones": total_sesiones, "total_recaudado": total_recaudado,
        "sesiones_activas": activas, "total_conductores": total_conductores,
        "total_permisionarios": total_permisionarios, "total_vehiculos": total_vehiculos,
        "deuda_total": deuda_total,
        "finanzas": {
            "total_bruto": total_bruto,
            "total_neto": total_recaudado,
            "comision_municipio": comision_municipio,
            "comision_permisionario": comision_permisionario,
        },
    }


@app.get("/api/admin/finanzas")
async def admin_finanzas(current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Permisionario))
    permisionarios = result.scalars().all()
    data = []
    for p in permisionarios:
        r1 = await db.execute(
            select(func.coalesce(func.sum(Pago.monto_original), 0))
            .where(Pago.confirmado == True)
            .where(Pago.sesion_id == SesionEstacionamiento.id)
            .where(SesionEstacionamiento.permisionario_id == p.id)
        )
        total_bruto = float(r1.scalar() or 0)
        r2 = await db.execute(
            select(func.coalesce(func.sum(Pago.monto), 0))
            .where(Pago.confirmado == True)
            .where(Pago.sesion_id == SesionEstacionamiento.id)
            .where(SesionEstacionamiento.permisionario_id == p.id)
        )
        total_neto = float(r2.scalar() or 0)
        r3 = await db.execute(
            select(func.coalesce(func.sum(Pago.comision_municipio), 0))
            .where(Pago.confirmado == True)
            .where(Pago.sesion_id == SesionEstacionamiento.id)
            .where(SesionEstacionamiento.permisionario_id == p.id)
        )
        comision_municipio = float(r3.scalar() or 0)
        r4 = await db.execute(
            select(func.coalesce(func.sum(Pago.comision_permisionario), 0))
            .where(Pago.confirmado == True)
            .where(Pago.sesion_id == SesionEstacionamiento.id)
            .where(SesionEstacionamiento.permisionario_id == p.id)
        )
        comision_permisionario = float(r4.scalar() or 0)
        r5 = await db.execute(
            select(func.count(Pago.id))
            .where(Pago.confirmado == True)
            .where(Pago.sesion_id == SesionEstacionamiento.id)
            .where(SesionEstacionamiento.permisionario_id == p.id)
        )
        total_pagos = r5.scalar() or 0
        data.append({
            "permisionario_id": p.id,
            "nombre": f"{p.nombre} {p.apellido}",
            "codigo": p.codigo,
            "total_pagos": total_pagos,
            "total_bruto": total_bruto,
            "total_neto": total_neto,
            "comision_municipio": comision_municipio,
            "comision_permisionario": comision_permisionario,
            "cuota_pendiente": round(comision_municipio, 2),
            "cvu": p.cvu,
        })
    return data


@app.get("/api/permisionario/finanzas")
async def permisionario_finanzas(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user["role"] != "permisionario":
        raise HTTPException(403, "Solo permisionarios")
    pid = current_user["id"]
    r1 = await db.execute(
        select(func.coalesce(func.sum(Pago.monto_original), 0))
        .where(Pago.confirmado == True)
        .where(Pago.sesion_id == SesionEstacionamiento.id)
        .where(SesionEstacionamiento.permisionario_id == pid)
    )
    total_bruto = float(r1.scalar() or 0)
    r2 = await db.execute(
        select(func.coalesce(func.sum(Pago.monto), 0))
        .where(Pago.confirmado == True)
        .where(Pago.sesion_id == SesionEstacionamiento.id)
        .where(SesionEstacionamiento.permisionario_id == pid)
    )
    total_neto = float(r2.scalar() or 0)
    r3 = await db.execute(
        select(func.count(Pago.id))
        .where(Pago.confirmado == True)
        .where(Pago.sesion_id == SesionEstacionamiento.id)
        .where(SesionEstacionamiento.permisionario_id == pid)
    )
    total_pagos = r3.scalar() or 0
    return {
        "total_pagos": total_pagos,
        "total_recaudado_bruto": total_bruto,
        "total_recaudado_neto": total_neto,
        "comision_municipio_estimada": round(total_bruto * 0.2, 2),
        "ingreso_permisionario": round(total_bruto * 0.8, 2),
    }


@app.get("/api/admin/deudas")
async def admin_deudas(current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Deuda).order_by(Deuda.created_at.desc()).limit(200))
    deudas = result.scalars().all()
    data = []
    for d in deudas:
        cond = await db.get(Conductor, d.conductor_id)
        data.append({
            "id": d.id, "conductor_id": d.conductor_id,
            "conductor_nombre": f"{cond.nombre} {cond.apellido}" if cond else "",
            "conductor_dni": cond.dni if cond else "",
            "sesion_id": d.sesion_id, "monto": d.monto,
            "pagada": d.pagada, "motivo": d.motivo,
            "created_at": d.created_at.isoformat(),
        })
    return data


@app.get("/api/admin/config")
async def admin_get_config(current_user=Depends(require_role("admin"))):
    return {
        "PRECIO_AUTO": PRECIO_AUTO, "PRECIO_MOTO": PRECIO_MOTO,
        "HORARIO_CIERRE": HORARIO_CIERRE, "HORARIO_CIERRE_SAB": HORARIO_CIERRE_SAB,
        "DEUDA_MAXIMA": DEUDA_MAXIMA, "MP_DESCUENTO": MP_DESCUENTO,
        "ZONAS_NOCTURNAS": ZONAS_NOCTURNAS,
    }


@app.post("/api/admin/conductores/{conductor_id}/desbloquear")
async def admin_desbloquear_conductor(conductor_id: int, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    cond.bloqueado = False
    cond.saldo_deudor = 0
    await db.commit()
    return {"ok": True, "mensaje": f"{cond.nombre} desbloqueado"}


@app.post("/api/admin/conductores/{conductor_id}/suspender")
async def admin_suspender_conductor(conductor_id: int, dias: int = 0, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
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
    return {
        "ok": True, "bloqueado": cond.bloqueado,
        "bloqueado_hasta": cond.bloqueado_hasta.isoformat() if cond.bloqueado_hasta else None,
    }


@app.get("/api/admin/conductores/{conductor_id}/detalle")
async def admin_conductor_detalle(conductor_id: int, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    sr = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.conductor_id == conductor_id)
        .order_by(SesionEstacionamiento.hora_inicio.desc()).limit(50)
    )
    sesiones = []
    for s in sr.scalars().all():
        esp = await db.get(Espacio, s.espacio_id)
        veh = await db.get(Vehiculo, s.vehiculo_id) if s.vehiculo_id else None
        sesiones.append({
            "id": s.id, "espacio_id": s.espacio_id,
            "ubicacion": esp.ubicacion if esp else "",
            "vehiculo_patente": veh.patente if veh else "",
            "hora_inicio": s.hora_inicio.isoformat(),
            "hora_fin": s.hora_fin.isoformat() if s.hora_fin else None,
            "costo_total": s.costo_total or 0,
            "metodo_pago": s.metodo_pago.value if s.metodo_pago else None,
            "estado": s.estado.value, "pagado": s.pagado,
        })
    dr = await db.execute(select(Deuda).where(Deuda.conductor_id == conductor_id).order_by(Deuda.created_at.desc()).limit(50))
    deudas = [
        {"id": d.id, "monto": d.monto, "motivo": d.motivo,
         "pagada": d.pagada, "created_at": d.created_at.isoformat()}
        for d in dr.scalars().all()
    ]
    vr = await db.execute(select(Vehiculo).where(Vehiculo.conductor_id == conductor_id))
    vehiculos = [
        {"id": v.id, "patente": v.patente, "tipo": v.tipo.value if hasattr(v.tipo, 'value') else v.tipo,
         "marca": v.marca, "modelo": v.modelo, "predeterminado": v.predeterminado}
        for v in vr.scalars().all()
    ]
    return {
        "conductor": {
            "id": cond.id, "dni": cond.dni, "nombre": cond.nombre, "apellido": cond.apellido,
            "email": cond.email, "telefono": cond.telefono,
            "bloqueado": cond.bloqueado, "saldo_deudor": cond.saldo_deudor or 0,
            "email_verified": cond.email_verified,
        },
        "vehiculos": vehiculos, "sesiones": sesiones, "deudas": deudas,
    }


@app.get("/api/admin/conductores/buscar")
async def admin_buscar_conductores(q: str = "", current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    if not q:
        result = await db.execute(select(Conductor).order_by(Conductor.id.desc()).limit(100))
    else:
        result = await db.execute(
            select(Conductor).where(
                (Conductor.nombre.ilike(f"%{q}%")) |
                (Conductor.apellido.ilike(f"%{q}%")) |
                (Conductor.dni.ilike(f"%{q}%")) |
                (Conductor.email.ilike(f"%{q}%"))
            ).order_by(Conductor.id.desc()).limit(100)
        )
    return result.scalars().all()


@app.get("/api/admin/conductores/{conductor_id}/exportar-csv")
async def admin_exportar_conductor_csv(conductor_id: int, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404)
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.conductor_id == conductor_id)
        .order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    sesiones = result.scalars().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Espacio", "Inicio", "Fin", "Costo", "Pagado", "Metodo", "Estado"])
    for s in sesiones:
        esp = await db.get(Espacio, s.espacio_id)
        writer.writerow([
            s.id, esp.ubicacion if esp else "",
            s.hora_inicio.strftime("%Y-%m-%d %H:%M"),
            s.hora_fin.strftime("%Y-%m-%d %H:%M") if s.hora_fin else "",
            s.costo_total or 0, "Si" if s.pagado else "No",
            s.metodo_pago.value if s.metodo_pago else "",
            s.estado.value if s.estado else "",
        ])
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=conductor_{conductor_id}_historial.csv"},
    )


# ═══════════════════════════════════════════════════════
# API: ESPACIOS (SHARED)
# ═══════════════════════════════════════════════════════

@app.get("/api/espacios")
async def listar_espacios(
    calle: str = None,
    disponible: bool = None,
    permisionario_id: int = None,
    lat: float = None,
    lng: float = None,
    radio: float = 500,
    db: AsyncSession = Depends(get_db),
):
    query = select(Espacio)
    if disponible is not None:
        query = query.where(Espacio.disponible == disponible)
    if permisionario_id:
        query = query.where(Espacio.permisionario_id == permisionario_id)
    result = await db.execute(query)
    espacios = result.scalars().all()
    data = []
    for e in espacios:
        if calle and calle.lower() not in (e.ubicacion or "").lower():
            continue
        item = {
            "id": e.id, "ubicacion": e.ubicacion,
            "precio_por_hora": e.precio_por_hora, "disponible": e.disponible,
            "lat": e.lat, "lng": e.lng, "tipo": e.tipo,
            "permisionario_id": e.permisionario_id, "mano_id": e.mano_id,
        }
        if lat is not None and lng is not None and e.lat and e.lng:
            dist = ((e.lat - lat) ** 2 + (e.lng - lng) ** 2) ** 0.5 * 111320
            if dist <= radio:
                item["distancia"] = round(dist, 1)
            else:
                continue
        data.append(item)
    return data


@app.get("/api/espacios/disponibles")
async def espacios_disponibles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio).where(Espacio.disponible == True))
    return result.scalars().all()


@app.get("/api/espacios/con-estado")
async def espacios_con_estado(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio.disponible, func.count(Espacio.id)).group_by(Espacio.disponible))
    conteo = {"libres": 0, "ocupados": 0}
    for disp, cnt in result:
        if disp:
            conteo["libres"] = cnt
        else:
            conteo["ocupados"] = cnt
    return conteo


@app.get("/api/espacios/{espacio_id}")
async def get_espacio(espacio_id: int, db: AsyncSession = Depends(get_db)):
    espacio = await db.get(Espacio, espacio_id)
    if not espacio:
        raise HTTPException(404, "Espacio no encontrado")
    return {
        "id": espacio.id, "ubicacion": espacio.ubicacion,
        "precio_por_hora": espacio.precio_por_hora, "disponible": espacio.disponible,
        "lat": espacio.lat, "lng": espacio.lng, "tipo": espacio.tipo,
        "permisionario_id": espacio.permisionario_id, "mano_id": espacio.mano_id,
    }


@app.get("/api/mapa-data")
async def mapa_data(db: AsyncSession = Depends(get_db)):
    from app.idemsa_data import get_all_calles_cached
    return {
        "calles": get_all_calles_cached(),
        "centro": CENTRO_SALTA,
        "espacios_idemsa": _get_espacios(),
    }


@app.post("/api/buscar-estacionamiento")
async def buscar_estacionamiento(
    data: BuscarEstacionamientoRequest,
    db: AsyncSession = Depends(get_db),
):
    q, lat, lng, radio = data.q, data.lat, data.lng, data.radio
    if not q and (lat is None or lng is None):
        return {"error": "Direccion o coordenadas requeridas"}

    coords = None
    if lat is not None and lng is not None:
        coords = (lat, lng)
    else:
        coords = await geocodificar(q)

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
        return {"error": "No se pudo encontrar la direccion"}

    lat, lng = coords
    cercanos = []
    for e in _get_espacios():
        if e.get("tipo") != "estacionamiento_medido":
            continue
        dist = ((e["lat"] - lat) ** 2 + (e["lng"] - lng) ** 2) ** 0.5 * 111320
        if dist <= radio:
            cercanos.append({**e, "distancia": round(dist, 1)})
    cercanos.sort(key=lambda x: x["distancia"])
    top = cercanos[:10]

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
            "lat": s["lat"], "lng": s["lng"], "distancia": s["distancia"],
            "disponible": e.disponible if e else True,
            "espacio_id": e.id if e else None,
            "precio_por_hora": e.precio_por_hora if e else PRECIO_AUTO,
            "altura": s.get("altura", ""),
        })

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
        "consulta": q or "Mi ubicacion",
        "destino": {"lat": lat, "lng": lng},
        "resultados": result,
        "bloques": list(bloques.values()),
        "radio": radio,
    }


# ═══════════════════════════════════════════════════════
# API: ESPACIOS ADMIN CRUD
# ═══════════════════════════════════════════════════════

@app.post("/api/espacios", response_model=EspacioOut)
async def crear_espacio(data: EspacioCreate, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    esp = Espacio(**data.model_dump())
    db.add(esp)
    await db.commit()
    await db.refresh(esp)
    return esp


@app.put("/api/admin/espacios/{espacio_id}", response_model=EspacioOut)
async def admin_editar_espacio(espacio_id: int, data: EspacioUpdate, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    esp = await db.get(Espacio, espacio_id)
    if not esp:
        raise HTTPException(404)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(esp, field, value)
    await db.commit()
    await db.refresh(esp)
    return esp


@app.delete("/api/admin/espacios/{espacio_id}")
async def admin_eliminar_espacio(espacio_id: int, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    esp = await db.get(Espacio, espacio_id)
    if not esp:
        raise HTTPException(404)
    await db.delete(esp)
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# MERCADO PAGO WEBHOOK
# ═══════════════════════════════════════════════════════

@app.post("/api/mp/webhook")
async def mercadopago_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    from app.mercado_pago import procesar_pago_webhook, verificar_firma_webhook
    signature = request.headers.get("x-signature", "")
    request_id = request.headers.get("x-request-id", "")
    try:
        body = await request.json()
    except Exception:
        body = {}

    if not verificar_firma_webhook(request_id, str(body), signature):
        raise HTTPException(403, "Invalid webhook signature")

    payment_id = body.get("data", {}).get("id")
    if not payment_id:
        payment_id = request.query_params.get("id")
    if not payment_id:
        return {"ok": False, "error": "no payment_id"}

    payment = await procesar_pago_webhook(str(payment_id))
    status = payment.get("status", "")

    if status == "approved":
        ext_ref = payment.get("external_reference", "")
        sesion = None
        if ext_ref:
            sesion = await db.get(SesionEstacionamiento, int(ext_ref))
        if not sesion:
            pref_id = payment.get("preference_id", "")
            if pref_id:
                result = await db.execute(
                    select(SesionEstacionamiento).where(SesionEstacionamiento.pago_id == pref_id)
                )
                sesion = result.scalar_one_or_none()

        if sesion and sesion.estado == EstadoSesion.activa and not sesion.pagado:
            ahora = now_naive()
            sesion.costo_total, _, _, _ = await calcular_costo_con_pendientes(
                sesion, sesion.conductor_id, ahora, db, actualizar_pendientes=True
            )
            sesion.costo_total = round(sesion.costo_total * (1 - MP_DESCUENTO), 2)
            sesion.pagado = True
            sesion.estado = EstadoSesion.finalizada
            sesion.hora_fin = ahora
            conductor = await db.get(Conductor, sesion.conductor_id)
            if conductor:
                conductor.saldo_deudor = max((conductor.saldo_deudor or 0) - (sesion.costo_total or 0), 0)
            pago_result = await db.execute(select(Pago).where(Pago.sesion_id == sesion.id))
            pago = pago_result.scalar_one_or_none()
            if pago:
                pago.confirmado = True
                pago.mp_status = "approved"
            espacio = await db.get(Espacio, sesion.espacio_id)
            if espacio:
                espacio.disponible = True
            await db.commit()

    return {"ok": True}


@app.get("/pago/success", response_class=HTMLResponse)
async def pago_success(request: Request):
    return templates.TemplateResponse(request, "conductor/pago_resultado.html", {
        "titulo": "Pago aprobado",
        "mensaje": "Tu estacionamiento fue pagado con exito.",
        "icono": "check",
    })


@app.get("/pago/failure", response_class=HTMLResponse)
async def pago_failure(request: Request):
    return templates.TemplateResponse(request, "conductor/pago_resultado.html", {
        "titulo": "Pago rechazado",
        "mensaje": "El pago no pudo completarse. El monto se acumulo a tu deuda.",
        "icono": "error",
    })


@app.get("/pago/pending", response_class=HTMLResponse)
async def pago_pending(request: Request):
    return templates.TemplateResponse(request, "conductor/pago_resultado.html", {
        "titulo": "Pago pendiente",
        "mensaje": "Tu pago esta siendo procesado.",
        "icono": "pending",
    })


# ═══════════════════════════════════════════════════════
# API: SESSIONS (SHARED)
# ═══════════════════════════════════════════════════════

@app.get("/api/sesiones")
async def listar_sesiones(current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).order_by(SesionEstacionamiento.hora_inicio.desc())
    )
    data = []
    for s in result.scalars().all():
        esp = await db.get(Espacio, s.espacio_id)
        veh = await db.get(Vehiculo, s.vehiculo_id) if s.vehiculo_id else None
        data.append({
            "id": s.id, "espacio_id": s.espacio_id, "conductor_id": s.conductor_id,
            "vehiculo_id": s.vehiculo_id, "permisionario_id": s.permisionario_id,
            "ubicacion": esp.ubicacion if esp else "",
            "patente": veh.patente if veh else "",
            "tipo_vehiculo": veh.tipo.value if veh and hasattr(veh.tipo, 'value') else "",
            "hora_inicio": s.hora_inicio.isoformat(),
            "hora_fin": s.hora_fin.isoformat() if s.hora_fin else None,
            "costo_total": s.costo_total, "pagado": s.pagado,
            "metodo_pago": s.metodo_pago.value if s.metodo_pago else None,
            "metodo_ingreso": s.metodo_ingreso.value if s.metodo_ingreso else None,
            "estado": s.estado.value if s.estado else None,
        })
    return data


@app.get("/api/sesiones/activas")
async def sesiones_activas(current_user=Depends(require_role("admin", "permisionario")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.estado == EstadoSesion.activa)
    )
    data = []
    for s in result.scalars().all():
        esp = await db.get(Espacio, s.espacio_id)
        veh = await db.get(Vehiculo, s.vehiculo_id) if s.vehiculo_id else None
        data.append({
            "id": s.id, "espacio_id": s.espacio_id, "conductor_id": s.conductor_id,
            "vehiculo_id": s.vehiculo_id, "ubicacion": esp.ubicacion if esp else "",
            "patente": veh.patente if veh else "",
            "hora_inicio": s.hora_inicio.isoformat(),
            "metodo_ingreso": s.metodo_ingreso.value if s.metodo_ingreso else None,
            "estado": s.estado.value,
        })
    return data


# ═══════════════════════════════════════════════════════
# OLD COMPAT ENDPOINTS
# ═══════════════════════════════════════════════════════

@app.get("/api/permisionarios", response_model=list[PermisionarioOut])
async def listar_permisionarios(current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Permisionario))
    return result.scalars().all()


@app.post("/api/permisionarios", response_model=PermisionarioOut)
async def crear_permisionario(data: PermisionarioCreate, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Permisionario).where(Permisionario.dni == data.dni))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Ya existe un permisionario con ese DNI")
    codigo = f"PER{data.dni}"
    perm = Permisionario(
        codigo=codigo, nombre=data.nombre, apellido=data.apellido,
        dni=data.dni, email=data.email, telefono=data.telefono, cvu=data.cvu,
        password_hash=hash_password(secrets.token_hex(4)), activo=True,
    )
    db.add(perm)
    await db.flush()
    for i, calle in enumerate(data.calles):
        lado = data.lados[i] if i < len(data.lados) else "par"
        try:
            lado_enum = LadoMano(lado)
        except ValueError:
            lado_enum = LadoMano.par
        mano = Mano(permisionario_id=perm.id, calle=calle, lado=lado_enum)
        db.add(mano)
    await db.commit()
    await db.refresh(perm)
    return perm


@app.get("/api/permisionarios/{perm_id}", response_model=PermisionarioOut)
async def obtener_permisionario(perm_id: int, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    return perm


@app.put("/api/permisionarios/{perm_id}", response_model=PermisionarioOut)
async def actualizar_permisionario(perm_id: int, data: PermisionarioUpdate, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    perm = await db.get(Permisionario, perm_id)
    if not perm:
        raise HTTPException(404)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(perm, field, value)
    await db.commit()
    await db.refresh(perm)
    return perm


@app.get("/api/conductores", response_model=list[ConductorOut])
async def listar_conductores(current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conductor))
    return result.scalars().all()


@app.get("/api/conductores/{conductor_id}", response_model=ConductorOut)
async def obtener_conductor(conductor_id: int, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    cond = await db.get(Conductor, conductor_id)
    if not cond:
        raise HTTPException(404, "Conductor no encontrado")
    return cond


@app.post("/api/auth/cambiar-password")
async def cambiar_password(body: PasswordChangeRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    models_map = {"conductor": Conductor, "permisionario": Permisionario, "admin": Admin, }
    model = models_map.get(current_user["role"])
    if not model:
        raise HTTPException(400, "Rol no soportado")
    user = await db.get(model, current_user["id"])
    if not user or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Contrasena actual incorrecta")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True, "mensaje": "Contrasena actualizada"}


@app.get("/api/espacio/by-location")
async def espacio_by_location(lat: float, lng: float, db: AsyncSession = Depends(get_db)):
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
        raise HTTPException(404, "No se encontro espacio cercano")
    return {
        "id": row[0], "ubicacion": row[1],
        "precio_por_hora": row[2], "disponible": row[3],
        "lat": row[4], "lng": row[5],
    }


@app.get("/api/mapa/cercanos")
async def mapa_cercanos(lat: float, lng: float, radio: float = 300):
    cercanos = []
    for e in _get_espacios():
        if e.get("tipo") != "estacionamiento_medido":
            continue
        dist = ((e["lat"] - lat) ** 2 + (e["lng"] - lng) ** 2) ** 0.5 * 111320
        if dist <= radio:
            cercanos.append({**e, "distancia": round(dist, 1)})
    cercanos.sort(key=lambda x: x["distancia"])
    return cercanos[:20]


@app.get("/api/mapa/idemsa-calles")
async def idemsa_calles():
    return get_all_calles_cached()


@app.get("/manifest.json")
async def manifest():
    return RedirectResponse(url="/static/manifest.json")


@app.get("/sw.js")
async def service_worker():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(static_dir, "service-worker.js"), media_type="application/javascript")