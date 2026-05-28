import asyncio
from app.database import init_db, async_session
from app.models import Permisionario, Conductor, Espacio
from sqlalchemy import select


async def seed():
    await init_db()
    async with async_session() as db:
        existing = await db.execute(select(Permisionario))
        if existing.scalars().first():
            print("Datos ya existen, omitiendo seed.")
            return

        juan = Permisionario(nombre="Juan Pérez", email="juan@ejemplo.com", telefono="1155550101")
        maria = Permisionario(nombre="María García", email="maria@ejemplo.com", telefono="1155550102")
        db.add_all([juan, maria])
        await db.flush()

        pedro = Conductor(nombre="Pedro López", email="pedro@ejemplo.com", telefono="1166660101")
        ana = Conductor(nombre="Ana Martínez", email="ana@ejemplo.com", telefono="1166660102")
        db.add_all([pedro, ana])
        await db.flush()

        espacios = [
            Espacio(ubicacion="Av. Corrientes 1000", permisionario_id=juan.id, precio_por_hora=60.0),
            Espacio(ubicacion="Av. Corrientes 1100", permisionario_id=juan.id, precio_por_hora=60.0),
            Espacio(ubicacion="Av. Santa Fe 2000", permisionario_id=maria.id, precio_por_hora=50.0),
            Espacio(ubicacion="Av. Santa Fe 2100", permisionario_id=maria.id, precio_por_hora=50.0),
        ]
        db.add_all(espacios)
        await db.commit()

        print("✅ Datos de prueba creados:")
        print(f"   Permisionarios: {juan.id} (Juan), {maria.id} (María)")
        print(f"   Conductores: {pedro.id} (Pedro), {ana.id} (Ana)")
        for e in espacios:
            print(f"   Espacio #{e.id}: {e.ubicacion} - ${e.precio_por_hora}/h")


if __name__ == "__main__":
    asyncio.run(seed())
