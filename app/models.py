from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Index
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
    calle = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    espacios = relationship("Espacio", back_populates="permisionario")


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
    bloqueado_hasta = Column(DateTime, nullable=True)
    saldo_deudor = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    sesiones = relationship("SesionEstacionamiento", back_populates="conductor")
    reservas = relationship("Reserva", back_populates="conductor")
    penalizaciones = relationship("Penalizacion", back_populates="conductor")
    patentes_secundarias = relationship("PatenteSecundaria", back_populates="conductor", cascade="all, delete-orphan")
    favoritos = relationship("Favorito", back_populates="conductor", cascade="all, delete-orphan")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)


class Espacio(Base):
    __tablename__ = "espacios"

    id = Column(Integer, primary_key=True, index=True)
    ubicacion = Column(String, nullable=False, index=True)
    precio_por_hora = Column(Float, default=600.0)
    disponible = Column(Boolean, default=True, index=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    permisionario_id = Column(Integer, ForeignKey("permisionarios.id"), nullable=True, index=True)
    tipo = Column(String, nullable=True, index=True)

    sesiones = relationship("SesionEstacionamiento", back_populates="espacio")
    reservas = relationship("Reserva", back_populates="espacio")
    permisionario = relationship("Permisionario", back_populates="espacios")


class SesionEstacionamiento(Base):
    __tablename__ = "sesiones"

    id = Column(Integer, primary_key=True, index=True)
    espacio_id = Column(Integer, ForeignKey("espacios.id"), nullable=False, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    hora_inicio = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    hora_fin = Column(DateTime, nullable=True, index=True)
    costo_total = Column(Float, nullable=True)
    pagado = Column(Boolean, default=False)
    pago_id = Column(String, nullable=True)
    metodo_pago = Column(String, nullable=True)
    lista_para_salir = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    espacio = relationship("Espacio", back_populates="sesiones")
    conductor = relationship("Conductor", back_populates="sesiones")


class Reserva(Base):
    __tablename__ = "reservas"

    id = Column(Integer, primary_key=True, index=True)
    espacio_id = Column(Integer, ForeignKey("espacios.id"), nullable=False, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    permisionario_id = Column(Integer, ForeignKey("permisionarios.id"), nullable=True, index=True)
    hora_inicio = Column(DateTime, nullable=False, index=True)
    hora_fin = Column(DateTime, nullable=False, index=True)
    estado = Column(Enum(EstadoReserva), default=EstadoReserva.pendiente, index=True)
    creada_en = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    checkin_time = Column(DateTime, nullable=True)
    usada = Column(Boolean, default=False)
    resuelta_por = Column(Integer, nullable=True)

    espacio = relationship("Espacio", back_populates="reservas")
    conductor = relationship("Conductor", back_populates="reservas")


class Penalizacion(Base):
    __tablename__ = "penalizaciones"

    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    reserva_id = Column(Integer, ForeignKey("reservas.id"), nullable=True)
    monto = Column(Float, nullable=False)
    motivo = Column(String, nullable=False)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    pagada = Column(Boolean, default=False)
    resuelta_por = Column(Integer, nullable=True)
    resuelta_en = Column(DateTime, nullable=True)

    conductor = relationship("Conductor", back_populates="penalizaciones")


class PatenteSecundaria(Base):
    __tablename__ = "patentes_secundarias"

    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    patente = Column(String, nullable=False)

    conductor = relationship("Conductor", back_populates="patentes_secundarias")


class Favorito(Base):
    __tablename__ = "favoritos_conductor"

    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    espacio_id = Column(Integer, ForeignKey("espacios.id"), nullable=False)
    nombre = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conductor = relationship("Conductor", back_populates="favoritos")
    espacio = relationship("Espacio")
