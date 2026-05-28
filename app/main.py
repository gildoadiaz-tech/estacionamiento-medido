from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import os

from app.database import init_db, get_db
from app.models import (
    Permisionario, Conductor, Espacio,
    SesionEstacionamiento, Reserva, EstadoReserva,
)
from app.schemas import (
    CheckInRequest, CheckInResponse, CheckOutRequest, CheckOutResponse,
    ReservaCreate, ReservaOut, ReservaAprobar,
    PermisionarioCreate, PermisionarioOut,
    ConductorCreate, ConductorOut,
    EspacioCreate, EspacioOut,
)
from app.qr_utils import generar_qr_base64
from app.mercado_pago import crear_preferencia_pago


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Estacionamiento Medido", lifespan=lifespan)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


# ─── HELPERS ────────────────────────────────────────

def now_naive():
    return datetime.utcnow()


def sesion_to_dict(s):
    return {
        "id": s.id, "espacio_id": s.espacio_id, "conductor_id": s.conductor_id,
        "hora_inicio": s.hora_inicio.isoformat() if s.hora_inicio else None,
        "hora_fin": s.hora_fin.isoformat() if s.hora_fin else None,
        "costo_total": s.costo_total, "pagado": s.pagado, "pago_id": s.pago_id,
    }


def reserva_to_dict(r):
    return {
        "id": r.id, "espacio_id": r.espacio_id, "conductor_id": r.conductor_id,
        "hora_inicio": r.hora_inicio.isoformat() if r.hora_inicio else None,
        "hora_fin": r.hora_fin.isoformat() if r.hora_fin else None,
        "estado": r.estado.value if r.estado else None,
        "creada_en": r.creada_en.isoformat() if r.creada_en else None,
    }


# ─── LANDING ────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


# ═══════════════════════════════════════════════════════
# PANEL 1: CONDUCTOR APP (mobile-first)
# ═══════════════════════════════════════════════════════

@app.get("/conductor", response_class=HTMLResponse)
async def conductor_home(request: Request):
    return templates.TemplateResponse(request, "conductor/index.html", {})


@app.get("/conductor/checkin", response_class=HTMLResponse)
async def conductor_checkin(request: Request):
    return templates.TemplateResponse(request, "conductor/checkin.html", {"conductor_id": 1})


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
    return templates.TemplateResponse(request, "conductor/checkout.html", {
        "sesion": sesion, "espacio": espacio,
    })


@app.get("/conductor/reservar", response_class=HTMLResponse)
async def conductor_reservar(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio))
    espacios = result.scalars().all()
    return templates.TemplateResponse(request, "conductor/reservar.html", {"espacios": espacios})


@app.get("/conductor/mis-reservas", response_class=HTMLResponse)
async def conductor_mis_reservas(request: Request):
    return templates.TemplateResponse(request, "conductor/mis_reservas.html", {})


@app.get("/conductor/historial", response_class=HTMLResponse)
async def conductor_historial(request: Request):
    return templates.TemplateResponse(request, "conductor/historial.html", {})


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

    result = await db.execute(select(Espacio).where(Espacio.permisionario_id == perm_id))
    espacios = result.scalars().all()

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    qrs = {}
    for e in espacios:
        qr_data = f"{base_url}/conductor/checkin"
        qrs[e.id] = generar_qr_base64(qr_data)

    return templates.TemplateResponse(request, "permisionario/qr.html", {
        "permisionario": perm, "espacios": espacios, "qrs": qrs,
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

@app.post("/api/checkin", response_model=CheckInResponse)
async def checkin(data: CheckInRequest, db: AsyncSession = Depends(get_db)):
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


@app.post("/api/checkout", response_model=CheckOutResponse)
async def checkout(data: CheckOutRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.id == data.sesion_id)
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(404, "Sesión no encontrada")
    if sesion.hora_fin:
        raise HTTPException(400, "Sesión ya finalizada")

    result = await db.execute(select(Espacio).where(Espacio.id == sesion.espacio_id))
    espacio = result.scalar_one()

    result = await db.execute(select(Conductor).where(Conductor.id == sesion.conductor_id))
    conductor = result.scalar_one()

    ahora = now_naive()
    sesion.hora_fin = ahora

    horas = max((ahora - sesion.hora_inicio).total_seconds() / 3600, 0.25)
    sesion.costo_total = round(horas * espacio.precio_por_hora, 2)

    espacio.disponible = True

    link_pago = await crear_preferencia_pago(
        monto=sesion.costo_total,
        concepto=f"Estacionamiento - {espacio.ubicacion}",
        conductor_email=conductor.email,
    )
    sesion.pago_id = link_pago

    await db.commit()

    return CheckOutResponse(
        sesion_id=sesion.id,
        horas=round(horas, 2),
        costo_total=sesion.costo_total,
        link_pago=link_pago,
    )


# ═══════════════════════════════════════════════════════
# API: SESIONES
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
    result = await db.execute(
        select(Espacio.id).where(Espacio.permisionario_id == permisionario_id)
    )
    espacio_ids = result.scalars().all()
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
    result = await db.execute(
        select(Espacio.id).where(Espacio.permisionario_id == permisionario_id)
    )
    espacio_ids = result.scalars().all()
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
