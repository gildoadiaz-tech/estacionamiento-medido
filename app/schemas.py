from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class PermisionarioCreate(BaseModel):
    nombre: str
    email: str
    telefono: Optional[str] = None
    calle: Optional[str] = None


class PermisionarioOut(BaseModel):
    id: int
    nombre: str
    email: str
    telefono: Optional[str] = None
    calle: Optional[str] = None

    model_config = {"from_attributes": True}


class ConductorCreate(BaseModel):
    nombre: str
    email: str
    telefono: Optional[str] = None


class ConductorOut(BaseModel):
    id: int
    nombre: str
    email: str
    telefono: Optional[str] = None
    patente: Optional[str] = None
    bloqueado: bool = False
    saldo_deudor: float = 0.0

    model_config = {"from_attributes": True}


class ConductorUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    patente: Optional[str] = None


class EspacioCreate(BaseModel):
    ubicacion: str
    precio_por_hora: float = 50.0


class EspacioOut(BaseModel):
    id: int
    ubicacion: str
    precio_por_hora: float
    disponible: bool

    model_config = {"from_attributes": True}


class CheckInRequest(BaseModel):
    espacio_id: int
    conductor_id: int


class CheckInPorPermRequest(BaseModel):
    permisionario_id: int
    conductor_id: int


class CheckInResponse(BaseModel):
    sesion_id: int
    hora_inicio: datetime
    qr_salida: str


class CheckOutRequest(BaseModel):
    sesion_id: int


class CheckOutResponse(BaseModel):
    sesion_id: int
    costo_total: float
    link_pago: str


class ElegirPagoRequest(BaseModel):
    metodo: str
    patente: Optional[str] = None


class ReservaCreate(BaseModel):
    espacio_id: int
    conductor_id: int
    hora_inicio: datetime
    hora_fin: datetime


class ReservaOut(BaseModel):
    id: int
    espacio_id: int
    conductor_id: int
    hora_inicio: datetime
    hora_fin: datetime
    estado: str
    creada_en: datetime

    model_config = {"from_attributes": True}


class ReservaAprobar(BaseModel):
    reserva_id: int
    aprobar: bool


class PenalizacionOut(BaseModel):
    id: int
    conductor_id: int
    reserva_id: Optional[int] = None
    monto: float
    motivo: str
    fecha: datetime
    pagada: bool

    model_config = {"from_attributes": True}


class ConductorStatus(BaseModel):
    bloqueado: bool
    saldo_deudor: float
    penalizaciones_mes: int
    motivo_bloqueo: Optional[str] = None
