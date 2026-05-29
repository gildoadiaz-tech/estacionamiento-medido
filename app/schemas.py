from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ConductorRegistro(BaseModel):
    dni: str
    nombre: str
    apellido: str
    email: str
    telefono: Optional[str] = None
    password: str
    patente: str
    tipo_vehiculo: str = "auto"
    marca: Optional[str] = None
    modelo: Optional[str] = None


class EmailVerifyRequest(BaseModel):
    email: str
    code: str


class VehiculoCreate(BaseModel):
    patente: str
    tipo: str = "auto"
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    predeterminado: bool = False


class VehiculoOut(BaseModel):
    id: int
    patente: str
    tipo: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    predeterminado: bool

    model_config = {"from_attributes": True}


class ConductorOut(BaseModel):
    id: int
    dni: str
    nombre: str
    apellido: str
    email: str
    telefono: Optional[str] = None
    email_verified: bool = False
    bloqueado: bool = False
    saldo_deudor: float = 0.0
    exencion: str = "ninguna"

    model_config = {"from_attributes": True}


class ConductorUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PermisionarioCreate(BaseModel):
    dni: str
    nombre: str
    apellido: str
    email: str
    telefono: Optional[str] = None
    calles: list[str] = []
    lados: list[str] = []


class PermisionarioOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    apellido: str
    dni: str
    email: str
    telefono: Optional[str] = None
    activo: bool = True

    model_config = {"from_attributes": True}


class PermisionarioUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    activo: Optional[bool] = None


class ManoOut(BaseModel):
    id: int
    calle: str
    altura_desde: Optional[int] = None
    altura_hasta: Optional[int] = None
    lado: str
    permisionario_id: int
    espacios_count: int = 0

    model_config = {"from_attributes": True}


class EspacioOut(BaseModel):
    id: int
    ubicacion: str
    precio_por_hora: float
    disponible: bool
    lat: Optional[float] = None
    lng: Optional[float] = None
    tipo: Optional[str] = None
    permisionario_id: Optional[int] = None

    model_config = {"from_attributes": True}


class EspacioCreate(BaseModel):
    ubicacion: str
    precio_por_hora: float = 600.0
    permisionario_id: Optional[int] = None
    mano_id: Optional[int] = None


class EspacioUpdate(BaseModel):
    ubicacion: Optional[str] = None
    precio_por_hora: Optional[float] = None
    disponible: Optional[bool] = None
    permisionario_id: Optional[int] = None


class CheckInRequest(BaseModel):
    espacio_id: Optional[int] = None
    vehiculo_id: Optional[int] = None
    permisionario_id: Optional[int] = None
    metodo_ingreso: str = "qr"


class RegistroManualRequest(BaseModel):
    permisionario_id: int
    patente: str
    espacio_id: Optional[int] = None


class SalidaRequest(BaseModel):
    sesion_id: int
    metodo_pago: str = "efectivo"


class ElegirPagoRequest(BaseModel):
    metodo: str
    patente: Optional[str] = None


class GestorCreate(BaseModel):
    nombre: str
    apellido: Optional[str] = None
    dni: Optional[str] = None
    email: str
    password: str
    permisos: str = "permisionarios,conductores,sesiones,reportes"


class GestorOut(BaseModel):
    id: int
    nombre: str
    apellido: Optional[str] = None
    dni: Optional[str] = None
    email: str
    username: str
    permisos: str
    activo: bool = True

    model_config = {"from_attributes": True}


class SesionOut(BaseModel):
    id: int
    espacio_id: int
    conductor_id: int
    vehiculo_id: Optional[int] = None
    permisionario_id: Optional[int] = None
    hora_inicio: datetime
    hora_fin: Optional[datetime] = None
    costo_total: Optional[float] = None
    pagado: bool = False
    metodo_pago: Optional[str] = None
    metodo_ingreso: Optional[str] = None
    estado: str = "activa"
    ubicacion: Optional[str] = None
    patente: Optional[str] = None
    vehiculo: Optional[dict] = None
    exencion: str = "ninguna"

    model_config = {"from_attributes": True}


class DeudaOut(BaseModel):
    id: int
    conductor_id: int
    sesion_id: Optional[int] = None
    monto: float
    pagada: bool = False
    motivo: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PenalizacionOut(BaseModel):
    id: int
    conductor_id: int
    monto: float
    motivo: str
    fecha: datetime
    pagada: bool = False

    model_config = {"from_attributes": True}


class ReporteDeudaRequest(BaseModel):
    sesion_id: int


class BuscarEstacionamientoRequest(BaseModel):
    q: str = ""
    lat: float = None
    lng: float = None
    radio: int = 500