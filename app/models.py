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

    espacios = relationship("Espacio", back_populates="permisionario")


class Conductor(Base):
    __tablename__ = "conductores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    telefono = Column(String)

    sesiones = relationship("SesionEstacionamiento", back_populates="conductor")
    reservas = relationship("Reserva", back_populates="conductor")


class Espacio(Base):
    __tablename__ = "espacios"

    id = Column(Integer, primary_key=True, index=True)
    ubicacion = Column(String, nullable=False)  # ej: "Av. Siempre Viva 123"
    permisionario_id = Column(Integer, ForeignKey("permisionarios.id"), nullable=False)
    precio_por_hora = Column(Float, default=50.0)  # pesos argentinos
    disponible = Column(Boolean, default=True)

    permisionario = relationship("Permisionario", back_populates="espacios")
    sesiones = relationship("SesionEstacionamiento", back_populates="espacio")
    reservas = relationship("Reserva", back_populates="espacio")


class SesionEstacionamiento(Base):
    __tablename__ = "sesiones"

    id = Column(Integer, primary_key=True, index=True)
    espacio_id = Column(Integer, ForeignKey("espacios.id"), nullable=False)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False)
    hora_inicio = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    hora_fin = Column(DateTime, nullable=True)
    costo_total = Column(Float, nullable=True)
    pagado = Column(Boolean, default=False)
    pago_id = Column(String, nullable=True)  # ID de Mercado Pago

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
    creada_en = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    espacio = relationship("Espacio", back_populates="reservas")
    conductor = relationship("Conductor", back_populates="reservas")
