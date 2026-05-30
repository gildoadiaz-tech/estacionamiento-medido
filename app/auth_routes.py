import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conductor, Permisionario, Admin, Gestor, EmailVerification, Vehiculo, ExencionTipo, TipoVehiculo, Mano
from app.auth import verify_password, create_token, decode_token, hash_password

router = APIRouter()
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
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        from app.database import init_db, async_session as _as
        await init_db()
        async with _as() as _s:
            r = await _s.execute(select(Admin))
            if not r.scalars().first():
                _s.add(Admin(nombre="Administrador", username="admin", password_hash=hash_password("admin123")))
                _s.add(Gestor(nombre="Carlos", apellido="Méndez", dni="12345678", email="gestor@municipalidad.gob.ar", username="gestor1", password_hash=hash_password("gestor123"), permisos="permisionarios,conductores,sesiones,reportes,deudas"))
                await _s.flush()
                p1 = Permisionario(codigo="PER30456789", nombre="Juan", apellido="Pérez", dni="30456789", email="juan@ejemplo.com", telefono="3874123456", password_hash=hash_password("1234"))
                p2 = Permisionario(codigo="PER28345678", nombre="María", apellido="García", dni="28345678", email="maria@ejemplo.com", telefono="3874234567", password_hash=hash_password("1234"))
                _s.add_all([p1, p2])
                await _s.flush()
                _s.add_all([Mano(permisionario_id=p1.id, calle="GENERAL GUEMES", altura_desde=100, altura_hasta=200, lado="par", lat=-24.7869, lng=-65.4054), Mano(permisionario_id=p1.id, calle="GENERAL GUEMES", altura_desde=100, altura_hasta=200, lado="impar", lat=-24.7869, lng=-65.4054), Mano(permisionario_id=p2.id, calle="CASEROS", altura_desde=1100, altura_hasta=1200, lado="par", lat=-24.7892, lng=-65.4204)])
                cs = [Conductor(dni="35123456", nombre="Pedro", apellido="López", email="pedro@ejemplo.com", telefono="3874345678", password_hash=hash_password("1234"), email_verified=True, exencion=ExencionTipo.ninguna), Conductor(dni="36234567", nombre="Ana", apellido="Martínez", email="ana@ejemplo.com", telefono="3874456789", password_hash=hash_password("1234"), email_verified=True, exencion=ExencionTipo.ninguna), Conductor(dni="30111222", nombre="Carlos", apellido="Ruiz", email="carlos.disc@ejemplo.com", telefono="3874567890", password_hash=hash_password("1234"), email_verified=True, exencion=ExencionTipo.discapacidad), Conductor(dni="29444555", nombre="Lucía", apellido="Fernández", email="lucia.frentista@ejemplo.com", telefono="3874678901", password_hash=hash_password("1234"), email_verified=True, exencion=ExencionTipo.frentista), Conductor(dni="20999888", nombre="Roberto", apellido="Gómez", email="roberto.veterano@ejemplo.com", telefono="3874789012", password_hash=hash_password("1234"), email_verified=True, exencion=ExencionTipo.veterano_malvinas), Conductor(dni="37555666", nombre="Eva", apellido="Torres", email="eva.bici@ejemplo.com", telefono="3874890123", password_hash=hash_password("1234"), email_verified=True, exencion=ExencionTipo.ninguna)]
                _s.add_all(cs)
                await _s.flush()
                _s.add_all([Vehiculo(conductor_id=cs[0].id, patente="AB123CD", tipo=TipoVehiculo.auto, marca="Toyota", modelo="Corolla", predeterminado=True), Vehiculo(conductor_id=cs[0].id, patente="AB456EF", tipo=TipoVehiculo.moto, marca="Honda", modelo="CG 150"), Vehiculo(conductor_id=cs[1].id, patente="BC789GH", tipo=TipoVehiculo.camioneta, marca="Ford", modelo="Ranger", predeterminado=True), Vehiculo(conductor_id=cs[2].id, patente="CD111AA", tipo=TipoVehiculo.auto, marca="Chevrolet", modelo="Corsa", predeterminado=True), Vehiculo(conductor_id=cs[3].id, patente="EF222BB", tipo=TipoVehiculo.auto, marca="Volkswagen", modelo="Gol", predeterminado=True), Vehiculo(conductor_id=cs[4].id, patente="GH333CC", tipo=TipoVehiculo.auto, marca="Fiat", modelo="Cronos", predeterminado=True), Vehiculo(conductor_id=cs[5].id, patente="BI001BICI", tipo=TipoVehiculo.bicicleta, marca="Venzo", modelo="Urban", predeterminado=True)])
                await _s.commit()
    except Exception:
        pass
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
    print(f"\n{'='*60}\n[VERIFICATION] {data.email}\n{link}\n{'='*60}\n")
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