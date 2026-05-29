import asyncio
from app.database import init_db, async_session, engine
from app.models import Conductor, Permisionario, Admin, Gestor, Mano, Vehiculo, ExencionTipo, TipoVehiculo
from app.auth import hash_password
from sqlalchemy import select, text


async def seed():
    async with engine.begin() as conn:
        from app.models import Base
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))

    async with async_session() as db:
        existing = await db.execute(select(Admin))
        if existing.scalars().first():
            print("Datos ya existen, omitiendo seed.")
            return

        admin = Admin(nombre="Administrador", username="admin", password_hash=hash_password("admin123"))
        db.add(admin)

        gestor = Gestor(
            nombre="Carlos", apellido="Méndez",
            dni="12345678", email="gestor@municipalidad.gob.ar",
            username="gestor1", password_hash=hash_password("gestor123"),
            permisos="permisionarios,conductores,sesiones,reportes,deudas",
        )
        db.add(gestor)
        await db.flush()

        juan = Permisionario(
            codigo="PER30456789", nombre="Juan", apellido="Pérez",
            dni="30456789", email="juan@ejemplo.com", telefono="3874123456",
            password_hash=hash_password("1234"),
        )
        maria = Permisionario(
            codigo="PER28345678", nombre="María", apellido="García",
            dni="28345678", email="maria@ejemplo.com", telefono="3874234567",
            password_hash=hash_password("1234"),
        )
        db.add_all([juan, maria])
        await db.flush()

        mano1 = Mano(permisionario_id=juan.id, calle="GENERAL GUEMES", altura_desde=100, altura_hasta=200, lado="par", lat=-24.7869, lng=-65.4054)
        mano2 = Mano(permisionario_id=juan.id, calle="GENERAL GUEMES", altura_desde=100, altura_hasta=200, lado="impar", lat=-24.7869, lng=-65.4054)
        mano3 = Mano(permisionario_id=maria.id, calle="CASEROS", altura_desde=1100, altura_hasta=1200, lado="par", lat=-24.7892, lng=-65.4204)
        db.add_all([mano1, mano2, mano3])
        await db.flush()

        # Conductor normal con auto y moto
        pedro = Conductor(
            dni="35123456", nombre="Pedro", apellido="López",
            email="pedro@ejemplo.com", telefono="3874345678",
            password_hash=hash_password("1234"), email_verified=True,
            exencion=ExencionTipo.ninguna,
        )
        # Conductora con camioneta
        ana = Conductor(
            dni="36234567", nombre="Ana", apellido="Martínez",
            email="ana@ejemplo.com", telefono="3874456789",
            password_hash=hash_password("1234"), email_verified=True,
            exencion=ExencionTipo.ninguna,
        )
        # Conductor con oblea de discapacidad
        carlos = Conductor(
            dni="30111222", nombre="Carlos", apellido="Ruiz",
            email="carlos.disc@ejemplo.com", telefono="3874567890",
            password_hash=hash_password("1234"), email_verified=True,
            exencion=ExencionTipo.discapacidad,
        )
        # Conductora frentista
        lucia = Conductor(
            dni="29444555", nombre="Lucía", apellido="Fernández",
            email="lucia.frentista@ejemplo.com", telefono="3874678901",
            password_hash=hash_password("1234"), email_verified=True,
            exencion=ExencionTipo.frentista,
        )
        # Conductor veterano de Malvinas
        roberto = Conductor(
            dni="20999888", nombre="Roberto", apellido="Gómez",
            email="roberto.veterano@ejemplo.com", telefono="3874789012",
            password_hash=hash_password("1234"), email_verified=True,
            exencion=ExencionTipo.veterano_malvinas,
        )
        # Conductora con bicicleta
        eva = Conductor(
            dni="37555666", nombre="Eva", apellido="Torres",
            email="eva.bici@ejemplo.com", telefono="3874890123",
            password_hash=hash_password("1234"), email_verified=True,
            exencion=ExencionTipo.ninguna,
        )
        db.add_all([pedro, ana, carlos, lucia, roberto, eva])
        await db.flush()

        vehiculos = [
            Vehiculo(conductor_id=pedro.id, patente="AB123CD", tipo=TipoVehiculo.auto, marca="Toyota", modelo="Corolla", predeterminado=True),
            Vehiculo(conductor_id=pedro.id, patente="AB456EF", tipo=TipoVehiculo.moto, marca="Honda", modelo="CG 150"),
            Vehiculo(conductor_id=ana.id, patente="BC789GH", tipo=TipoVehiculo.camioneta, marca="Ford", modelo="Ranger", predeterminado=True),
            Vehiculo(conductor_id=carlos.id, patente="CD111AA", tipo=TipoVehiculo.auto, marca="Chevrolet", modelo="Corsa", predeterminado=True),
            Vehiculo(conductor_id=lucia.id, patente="EF222BB", tipo=TipoVehiculo.auto, marca="Volkswagen", modelo="Gol", predeterminado=True),
            Vehiculo(conductor_id=roberto.id, patente="GH333CC", tipo=TipoVehiculo.auto, marca="Fiat", modelo="Cronos", predeterminado=True),
            Vehiculo(conductor_id=eva.id, patente="BI001BICI", tipo=TipoVehiculo.bicicleta, marca="Venzo", modelo="Urban", predeterminado=True),
        ]
        db.add_all(vehiculos)

        await db.commit()

        print("========================================")
        print("  USUARIOS DE PRUEBA — v2.0")
        print("========================================")
        print()
        print("CONDUCTORES:")
        print("  35123456 / 1234 — Pedro López (auto+_controller, sin exención)")
        print("  36234567 / 1234 — Ana Martínez (camioneta, sin exención)")
        print("  30111222 / 1234 — Carlos Ruiz (auto, OBLEA DISCAPACIDAD)")
        print("  29444555 / 1234 — Lucía Fernández (auto, FRENTISTA)")
        print("  20999888 / 1234 — Roberto Gómez (auto, VETERANO MALVINAS)")
        print("  37555666 / 1234 — Eva Torres (BICICLETA, sin exención)")
        print()
        print("PRECIOS:")
        print("  Auto/Camioneta: $600/h")
        print("  Moto: $100/h")
        print("  Bicicleta: GRATUITO")
        print("  Oblea discapacidad: GRATUITO (3hs)")
        print("  Frentista: GRATUITO (2hs mañana + 2hs tarde)")
        print("  Veterano Malvinas: GRATUITO")
        print()
        print("HORARIOS:")
        print("  Lun-Vie: 7-21hs ($600/h autos, $100/h motos)")
        print("  Sábados: 7-14hs ($600/h autos, $100/h motos)")
        print("  Nocturno: 22-5hs ($600/h autos, $100/h motos)")
        print("  Domingos: GRATUITO")
        print()
        print("PERMISIONARIOS:")
        print("  PER30456789 / 1234 — Juan Pérez (Gral. Güemes par+impar)")
        print("  PER28345678 / 1234 — María García (Caseros 1100-1200 par)")
        print()
        print("GESTOR: gestor1 / gestor123 — Carlos Méndez")
        print("ADMIN: admin / admin123")
        print("========================================")


if __name__ == "__main__":
    asyncio.run(seed())