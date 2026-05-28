import asyncio
from app.database import init_db, async_session
from app.models import Permisionario, Conductor, Espacio, Admin
from app.auth import hash_password
from sqlalchemy import select


async def seed():
    await init_db()
    async with async_session() as db:
        existing = await db.execute(select(Permisionario))
        if existing.scalars().first():
            print("Datos ya existen, omitiendo seed.")
            return

        # Admin
        admin = Admin(nombre="Admin", username="admin", password_hash=hash_password("admin123"))
        db.add(admin)

        # Permisionarios
        juan = Permisionario(
            nombre="Juan Pérez", email="juan@ejemplo.com", telefono="1155550101",
            username="juan", password_hash=hash_password("1234"),
            calle="Gral. Güemes",
        )
        maria = Permisionario(
            nombre="María García", email="maria@ejemplo.com", telefono="1155550102",
            username="maria", password_hash=hash_password("1234"),
            calle="Caseros",
        )
        db.add_all([juan, maria])
        await db.flush()

        # Conductores
        pedro = Conductor(
            nombre="Pedro López", email="pedro@ejemplo.com", telefono="1166660101",
            username="pedro", password_hash=hash_password("1234"), patente="AB123CD",
        )
        ana = Conductor(
            nombre="Ana Martínez", email="ana@ejemplo.com", telefono="1166660102",
            username="ana", password_hash=hash_password("1234"), patente="BC456EF",
        )
        db.add_all([pedro, ana])
        await db.flush()

        # Espacios (sin permisionario_id — la pertenencia se determina por calle)
        espacios = [
            Espacio(ubicacion="Gral. Güemes 150", precio_por_hora=600.0, lat=-24.7885, lng=-65.4100),
            Espacio(ubicacion="Caseros 200", precio_por_hora=600.0, lat=-24.7892, lng=-65.4090),
            Espacio(ubicacion="Mitre 350", precio_por_hora=600.0, lat=-24.7878, lng=-65.4115),
            Espacio(ubicacion="España 180", precio_por_hora=600.0, lat=-24.7880, lng=-65.4085),
            Espacio(ubicacion="Alberdi 220", precio_por_hora=600.0, lat=-24.7895, lng=-65.4120),
            Espacio(ubicacion="Buenos Aires 300", precio_por_hora=600.0, lat=-24.7870, lng=-65.4105),
        ]
        db.add_all(espacios)
        await db.commit()

        print("✅ Datos de prueba creados:")
        print(f"   Admin: admin / admin123")
        print(f"   Permisionarios: juan / 1234 (ID {juan.id}), maria / 1234 (ID {maria.id})")
        print(f"   Conductores: pedro / 1234 (ID {pedro.id}), ana / 1234 (ID {ana.id})")
        for e in espacios:
            print(f"   Espacio #{e.id}: {e.ubicacion} - ${e.precio_por_hora}/h [{e.lat}, {e.lng}]")


if __name__ == "__main__":
    asyncio.run(seed())
