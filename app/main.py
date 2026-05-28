from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update
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


# ─── HTML ROUTES ───────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/permisionario/{perm_id}/panel", response_class=HTMLResponse)
async def panel_permisionario(request: Request, perm_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Permisionario).where(Permisionario.id == perm_id)
    )
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(404, "Permisionario no encontrado")

    result = await db.execute(
        select(Espacio).where(Espacio.permisionario_id == perm_id)
    )
    espacios = result.scalars().all()

    result = await db.execute(
        select(Reserva).where(Reserva.espacio_id.in_([e.id for e in espacios]))
    )
    reservas = result.scalars().all()

    return templates.TemplateResponse("panel.html", {
        "request": request,
        "permisionario": perm,
        "espacios": espacios,
        "reservas": reservas,
    })


@app.get("/checkin/{espacio_id}", response_class=HTMLResponse)
async def checkin_page(request: Request, espacio_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio).where(Espacio.id == espacio_id))
    espacio = result.scalar_one_or_none()
    if not espacio:
        raise HTTPException(404, "Espacio no encontrado")
    return templates.TemplateResponse("checkin.html", {
        "request": request,
        "espacio": espacio,
    })


@app.get("/checkout/{sesion_id}", response_class=HTMLResponse)
async def checkout_page(request: Request, sesion_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SesionEstacionamiento).where(SesionEstacionamiento.id == sesion_id)
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(404, "Sesión no encontrada")

    result = await db.execute(select(Espacio).where(Espacio.id == sesion.espacio_id))
    espacio = result.scalar_one()

    return templates.TemplateResponse("checkout.html", {
        "request": request,
        "sesion": sesion,
        "espacio": espacio,
    })


@app.get("/reservar/{espacio_id}", response_class=HTMLResponse)
async def reservar_page(request: Request, espacio_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio).where(Espacio.id == espacio_id))
    espacio = result.scalar_one_or_none()
    if not espacio:
        raise HTTPException(404, "Espacio no encontrado")
    return templates.TemplateResponse("reservar.html", {
        "request": request,
        "espacio": espacio,
    })


# ─── API ROUTES ────────────────────────────────────

@app.post("/api/permisionarios", response_model=PermisionarioOut)
async def crear_permisionario(data: PermisionarioCreate, db: AsyncSession = Depends(get_db)):
    perm = Permisionario(**data.model_dump())
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return perm


@app.post("/api/conductores", response_model=ConductorOut)
async def crear_conductor(data: ConductorCreate, db: AsyncSession = Depends(get_db)):
    cond = Conductor(**data.model_dump())
    db.add(cond)
    await db.commit()
    await db.refresh(cond)
    return cond


@app.post("/api/espacios", response_model=EspacioOut)
async def crear_espacio(data: EspacioCreate, db: AsyncSession = Depends(get_db)):
    esp = Espacio(**data.model_dump())
    db.add(esp)
    await db.commit()
    await db.refresh(esp)
    return esp


@app.get("/api/espacios", response_model=list[EspacioOut])
async def listar_espacios(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Espacio))
    return result.scalars().all()


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
        hora_inicio=datetime.now(timezone.utc),
    )
    db.add(sesion)
    espacio.disponible = False
    await db.commit()
    await db.refresh(sesion)

    qr_data = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/checkout/{sesion.id}"
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

    ahora = datetime.now(timezone.utc)
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


@app.get("/api/reservas/pendientes/{permisionario_id}", response_model=list[ReservaOut])
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
    return result.scalars().all()


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


@app.post("/api/checkin/{sesion_id}")
async def checkin_form(sesion_id: int, conductor_id: int = Form(...), db: AsyncSession = Depends(get_db)):
    data = CheckInRequest(espacio_id=sesion_id, conductor_id=conductor_id)
    return await checkin(data, db)
