import uuid, logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models import Conductor, Permisionario, Admin, Gestor, EmailVerification, Vehiculo
from app.auth import verify_password, create_token, decode_token, hash_password

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory="app/templates")


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterConductorRequest(BaseModel):
    dni: str
    nombre: str
    apellido: str
    email: str
    telefono: str = ""
    password: str
    patente: str
    tipo_vehiculo: str = "auto"
    marca: str = ""
    modelo: str = ""


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    login_map = [
        (Conductor, "conductor", Conductor.dni),
        (Permisionario, "permisionario", Permisionario.codigo),
        (Gestor, "gestor", Gestor.username),
        (Admin, "admin", Admin.username),
    ]
    for model, role, id_field in login_map:
        result = await db.execute(select(model).where(id_field == data.username))
        user = result.scalar_one_or_none()
        if user and verify_password(data.password, user.password_hash):
            if hasattr(user, "email_verified") and not user.email_verified:
                raise HTTPException(403, "Email no verificado. Verificá tu correo primero.")
            if hasattr(user, "activo") and not user.activo:
                raise HTTPException(403, "Cuenta desactivada.")
            token = create_token({
                "user_id": user.id,
                "role": role,
                "username": data.username,
            })
            nombre = getattr(user, "nombre", "")
            apellido = getattr(user, "apellido", "")
            return {
                "token": token,
                "role": role,
                "user_id": user.id,
                "nombre": f"{nombre} {apellido}".strip(),
                "username": data.username,
            }
    raise HTTPException(401, "Usuario o contraseña incorrectos")


@router.post("/register/conductor")
async def register_conductor(data: RegisterConductorRequest, db: AsyncSession = Depends(get_db)):
    if not data.dni or len(data.dni) < 7:
        raise HTTPException(400, "DNI inválido.")
    existing_dni = await db.execute(select(Conductor).where(Conductor.dni == data.dni))
    if existing_dni.scalar_one_or_none():
        raise HTTPException(400, "Ya existe un conductor con ese DNI.")
    existing_email = await db.execute(select(Conductor).where(Conductor.email == data.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(400, "Ya existe un conductor con ese email.")
    existing_plate = await db.execute(select(Vehiculo).where(Vehiculo.patente == data.patente))
    if existing_plate.scalar_one_or_none():
        raise HTTPException(400, "Ya existe un vehículo con esa patente.")

    conductor = Conductor(
        dni=data.dni,
        nombre=data.nombre,
        apellido=data.apellido,
        email=data.email,
        telefono=data.telefono or None,
        password_hash=hash_password(data.password),
        email_verified=False,
    )
    db.add(conductor)
    await db.flush()
    vehiculo = Vehiculo(
        conductor_id=conductor.id,
        patente=data.patente.upper(),
        tipo=data.tipo_vehiculo,
        marca=data.marca or None,
        modelo=data.modelo or None,
        predeterminado=True,
    )
    db.add(vehiculo)

    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=24)
    verification = EmailVerification(email=data.email, code=token, verified=False, expires_at=expires)
    db.add(verification)
    await db.commit()

    base = "http://localhost:8000"
    link = f"{base}/api/auth/verify-email?token={token}"
    logging.info(f"Verification link for {data.email}: {link}")
    return {"message": "Cuenta creada. Revisá tu email para verificar tu dirección de correo.", "email": data.email}


@router.get("/verify-email")
async def verify_email(request: Request, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EmailVerification)
        .where(EmailVerification.code == token)
        .where(EmailVerification.verified == False)
        .order_by(EmailVerification.created_at.desc())
    )
    verification = result.scalar_one_or_none()
    if not verification:
        return templates.TemplateResponse(request, "auth/verify_result.html", {"success": False, "message": "Enlace inválido o ya fue usado."})
    if verification.expires_at < datetime.utcnow():
        return templates.TemplateResponse(request, "auth/verify_result.html", {"success": False, "message": "Enlace expirado."})
    verification.verified = True
    conductor = await db.execute(select(Conductor).where(Conductor.email == verification.email))
    c = conductor.scalar_one_or_none()
    if c:
        c.email_verified = True
    await db.commit()
    return templates.TemplateResponse(request, "auth/verify_result.html", {"success": True, "message": "Email verificado correctamente. Ya podés iniciar sesión."})


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    auth = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = decode_token(auth)
    if not payload:
        raise HTTPException(401, "Token inválido")
    return payload