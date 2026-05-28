from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.database import Base


class EstadoReserva(str, enum.Enum):
    pendiente = "pendiente"
    aprobada = "aprobada"
    rechazada = "rechazada"


class Permisionario(Base):
    __tablename__ = "permisionarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    telefono = Column(String)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    calle = Column(String, nullable=False)


class Conductor(Base):
    __tablename__ = "conductores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    telefono = Column(String)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    patente = Column(String, nullable=True)
    bloqueado = Column(Boolean, default=False)
    saldo_deudor = Column(Float, default=0.0)

    sesiones = relationship("SesionEstacionamiento", back_populates="conductor")
    reservas = relationship("Reserva", back_populates="conductor")
    penalizaciones = relationship("Penalizacion", back_populates="conductor")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)


class Espacio(Base):
    __tablename__ = "espacios"

    id = Column(Integer, primary_key=True, index=True)
    ubicacion = Column(String, nullable=False)
    precio_por_hora = Column(Float, default=50.0)
    disponible = Column(Boolean, default=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    sesiones = relationship("SesionEstacionamiento", back_populates="espacio")
    reservas = relationship("Reserva", back_populates="espacio")


class SesionEstacionamiento(Base):
    __tablename__ = "sesiones"

    id = Column(Integer, primary_key=True, index=True)
    espacio_id = Column(Integer, ForeignKey("espacios.id"), nullable=False)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False)
    hora_inicio = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    hora_fin = Column(DateTime, nullable=True)
    costo_total = Column(Float, nullable=True)
    pagado = Column(Boolean, default=False)
    pago_id = Column(String, nullable=True)
    metodo_pago = Column(String, nullable=True)
    lista_para_salir = Column(Boolean, default=False)

    espacio = relationship("Espacio", back_populates="sesiones")
    conductor = relationship("Conductor", back_populates="sesiones")


class Reserva(Base):
    __tablename__ = "reservas"

    id = Column(Integer, primary_key=True, index=True)
    espacio_id = Column(Integer, ForeignKey("espacios.id"), nullable=False)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False)
    hora_inicio = Column(DateTime, nullable=False)
    hora_fin = Column(DateTime, nullable=False)
    estado = Column(Enum(EstadoReserva), default=EstadoReserva.pendiente)
    creada_en = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    checkin_time = Column(DateTime, nullable=True)
    usada = Column(Boolean, default=False)

    espacio = relationship("Espacio", back_populates="reservas")
    conductor = relationship("Conductor", back_populates="reservas")


class Penalizacion(Base):
    __tablename__ = "penalizaciones"

    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False)
    reserva_id = Column(Integer, ForeignKey("reservas.id"), nullable=True)
    monto = Column(Float, nullable=False)
    motivo = Column(String, nullable=False)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    pagada = Column(Boolean, default=False)

    conductor = relationship("Conductor", back_populates="penalizaciones")
