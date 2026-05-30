from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.database import Base


class TipoVehiculo(str, enum.Enum):
    auto = "auto"
    camioneta = "camioneta"
    moto = "moto"
    bicicleta = "bicicleta"


class ExencionTipo(str, enum.Enum):
    ninguna = "ninguna"
    discapacidad = "discapacidad"
    frentista = "frentista"
    veterano_malvinas = "veterano_malvinas"


class MetodoPago(str, enum.Enum):
    efectivo = "efectivo"
    mercadopago = "mercadopago"


class MetodoIngreso(str, enum.Enum):
    qr = "qr"
    aqui = "aqui"
    manual = "manual"


class EstadoSesion(str, enum.Enum):
    activa = "activa"
    finalizada = "finalizada"
    deuda = "deuda"


class LadoMano(str, enum.Enum):
    par = "par"
    impar = "impar"


class Conductor(Base):
    __tablename__ = "conductores"

    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String, unique=True, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    telefono = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)
    bloqueado = Column(Boolean, default=False)
    bloqueado_hasta = Column(DateTime, nullable=True)
    saldo_deudor = Column(Float, default=0.0)
    horas_pendientes = Column(Float, default=0.0, comment="Horas no diurnas acumuladas para cobrar en la proxima sesion")
    exencion = Column(Enum(ExencionTipo), default=ExencionTipo.ninguna)
    frentista_calle = Column(String, nullable=True, comment="Calle registrada del frentista para validar gratuidad")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    vehiculos = relationship("Vehiculo", back_populates="conductor", cascade="all, delete-orphan")
    sesiones = relationship("SesionEstacionamiento", back_populates="conductor")
    deudas = relationship("Deuda", back_populates="conductor")


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    patente = Column(String, nullable=False, index=True)
    tipo = Column(Enum(TipoVehiculo), default=TipoVehiculo.auto)
    marca = Column(String, nullable=True)
    modelo = Column(String, nullable=True)
    anio = Column(Integer, nullable=True)
    predeterminado = Column(Boolean, default=False)

    conductor = relationship("Conductor", back_populates="vehiculos")
    sesiones = relationship("SesionEstacionamiento", back_populates="vehiculo")


class Permisionario(Base):
    __tablename__ = "permisionarios"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    dni = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    telefono = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    manos = relationship("Mano", back_populates="permisionario", cascade="all, delete-orphan")


class Mano(Base):
    __tablename__ = "manos"

    id = Column(Integer, primary_key=True, index=True)
    permisionario_id = Column(Integer, ForeignKey("permisionarios.id"), nullable=False, index=True)
    calle = Column(String, nullable=False, index=True)
    altura_desde = Column(Integer, nullable=True)
    altura_hasta = Column(Integer, nullable=True)
    lado = Column(Enum(LadoMano), default=LadoMano.par)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    permisionario = relationship("Permisionario", back_populates="manos")
    espacios = relationship("Espacio", back_populates="mano")


class Espacio(Base):
    __tablename__ = "espacios"

    id = Column(Integer, primary_key=True, index=True)
    mano_id = Column(Integer, ForeignKey("manos.id"), nullable=True, index=True)
    numero = Column(Integer, nullable=True)
    ubicacion = Column(String, nullable=False, index=True)
    precio_por_hora = Column(Float, default=600.0)
    disponible = Column(Boolean, default=True, index=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    tipo = Column(String, nullable=True, index=True)
    permisionario_id = Column(Integer, ForeignKey("permisionarios.id"), nullable=True, index=True)

    mano = relationship("Mano", back_populates="espacios")
    permisionario = relationship("Permisionario")
    sesiones = relationship("SesionEstacionamiento", back_populates="espacio")


class SesionEstacionamiento(Base):
    __tablename__ = "sesiones"

    id = Column(Integer, primary_key=True, index=True)
    espacio_id = Column(Integer, ForeignKey("espacios.id"), nullable=False, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=True, index=True)
    permisionario_id = Column(Integer, ForeignKey("permisionarios.id"), nullable=True, index=True)
    hora_inicio = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    hora_fin = Column(DateTime, nullable=True, index=True)
    costo_total = Column(Float, nullable=True)
    pagado = Column(Boolean, default=False)
    metodo_pago = Column(Enum(MetodoPago), nullable=True)
    metodo_ingreso = Column(Enum(MetodoIngreso), default=MetodoIngreso.qr)
    exencion = Column(Enum(ExencionTipo), default=ExencionTipo.ninguna)
    estado = Column(Enum(EstadoSesion), default=EstadoSesion.activa, index=True)
    pago_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    espacio = relationship("Espacio", back_populates="sesiones")
    conductor = relationship("Conductor", back_populates="sesiones")
    vehiculo = relationship("Vehiculo", back_populates="sesiones")
    permisionario = relationship("Permisionario")
    pago = relationship("Pago", back_populates="sesion", uselist=False)


class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    sesion_id = Column(Integer, ForeignKey("sesiones.id"), nullable=False, index=True)
    monto = Column(Float, nullable=False, comment="Lo que realmente pagó el conductor")
    monto_original = Column(Float, nullable=True, comment="Precio sin descuento MP")
    metodo = Column(Enum(MetodoPago), nullable=False)
    comision_municipio = Column(Float, default=0.0, comment="Lo que recibe el municipio (20% de monto_original, 0 si MP)")
    comision_permisionario = Column(Float, default=0.0, comment="Lo que recibe el permisionario (80% de monto_original)")
    cuota_liquidada = Column(Boolean, default=False, comment="Si ya se liquidó la cuota al municipio")
    mp_preference_id = Column(String, nullable=True)
    mp_status = Column(String, nullable=True)
    confirmado = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sesion = relationship("SesionEstacionamiento", back_populates="pago")


class CuotaPermisionario(Base):
    __tablename__ = "cuotas_permisionario"

    id = Column(Integer, primary_key=True, index=True)
    permisionario_id = Column(Integer, ForeignKey("permisionarios.id"), nullable=False, index=True)
    periodo_inicio = Column(DateTime, nullable=False)
    periodo_fin = Column(DateTime, nullable=False)
    total_recaudado = Column(Float, default=0.0, comment="Suma de monto_original de todos los pagos")
    total_efectivo = Column(Float, default=0.0)
    total_mp = Column(Float, default=0.0)
    monto_cuota = Column(Float, default=0.0, comment="20% de total_recaudado, pero sin contar lo subsidiado en MP")
    pagada = Column(Boolean, default=False)
    fecha_vencimiento = Column(DateTime, nullable=True)
    fecha_pago = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Deuda(Base):
    __tablename__ = "deudas"

    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    sesion_id = Column(Integer, ForeignKey("sesiones.id"), nullable=True)
    monto = Column(Float, nullable=False)
    pagada = Column(Boolean, default=False, index=True)
    reported_by = Column(Integer, ForeignKey("permisionarios.id"), nullable=True)
    motivo = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conductor = relationship("Conductor", back_populates="deudas")


class Penalizacion(Base):
    __tablename__ = "penalizaciones"

    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    monto = Column(Float, nullable=False)
    motivo = Column(String, nullable=False)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    pagada = Column(Boolean, default=False)
    resuelta_por = Column(Integer, nullable=True)
    resuelta_en = Column(DateTime, nullable=True)


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False)
    verified = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Gestor(Base):
    __tablename__ = "gestores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=True)
    dni = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    permisos = Column(String, default="permisionarios,conductores,sesiones,reportes")
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)