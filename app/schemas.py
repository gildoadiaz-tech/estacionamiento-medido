from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class PermisionarioCreate(BaseModel):
    nombre: str
    email: str
    telefono: Optional[str] = None


class PermisionarioOut(BaseModel):
    id: int
    nombre: str
    email: str
    telefono: Optional[str] = None

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

    model_config = {"from_attributes": True}


class EspacioCreate(BaseModel):
    ubicacion: str
    permisionario_id: int
    precio_por_hora: float = 50.0


class EspacioOut(BaseModel):
    id: int
    ubicacion: str
    permisionario_id: int
    precio_por_hora: float
    disponible: bool

    model_config = {"from_attributes": True}


class CheckInRequest(BaseModel):
    espacio_id: int
    conductor_id: int


class CheckInResponse(BaseModel):
    sesion_id: int
    hora_inicio: datetime
    qr_salida: str


class CheckOutRequest(BaseModel):
    sesion_id: int


class CheckOutResponse(BaseModel):
    sesion_id: int
    horas: float
    costo_total: float
    link_pago: str


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
