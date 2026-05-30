"""
Seed con datos ficticios para demo.
Crea espacios, sesiones, pagos, deudas y cuotas.
Correr DESPUÉS de seed.py.
Uso: python3 seed_datos.py
"""
import asyncio
import math
import random
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from app.database import async_session, engine
from app.models import (
    Base, Conductor, Permisionario, Mano, Espacio, Vehiculo,
    SesionEstacionamiento, Pago, Deuda, CuotaPermisionario,
    EstadoSesion, MetodoPago, MetodoIngreso, ExencionTipo, TipoVehiculo, LadoMano,
)


async def seed_datos():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from sqlalchemy import text
        if "sqlite" in str(conn.engine.url):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=5000"))

    async with async_session() as db:
        result = await db.execute(select(Permisionario))
        permisionarios = result.scalars().all()
        if not permisionarios:
            print("No hay permisionarios. Corre seed.py primero.")
            return

        result = await db.execute(select(Conductor))
        conductores = result.scalars().all()
        if not conductores:
            print("No hay conductores. Corre seed.py primero.")
            return

        result = await db.execute(select(Vehiculo))
        vehiculos = result.scalars().all()

        result = await db.execute(select(Mano))
        manos = result.scalars().all()

        result = await db.execute(select(Espacio))
        espacios_existing = result.scalars().all()

        print(f"Conductores: {len(conductores)}, Permisionarios: {len(permisionarios)}, Manos: {len(manos)}, Vehiculos: {len(vehiculos)}")

        now = datetime.now()

        # === CREAR ESPACIOS ===
        if not espacios_existing and manos:
            for mano in manos:
                alt_desde = mano.altura_desde or 100
                alt_hasta = mano.altura_hasta or 200
                for i in range(alt_desde, alt_hasta + 1, 10):
                    ubicacion = f"{mano.calle} {i} ({mano.lado.value})"
                    lat_offset = (i - alt_desde) * 0.00003
                    lng_offset = (i - alt_desde) * 0.00003
                    espacio = Espacio(
                        mano_id=mano.id,
                        numero=i,
                        ubicacion=ubicacion,
                        precio_por_hora=700.0,
                        disponible=True,
                        lat=mano.lat + lat_offset if mano.lat else None,
                        lng=mano.lng + lng_offset if mano.lng else None,
                        tipo="auto",
                        permisionario_id=mano.permisionario_id,
                    )
                    db.add(espacio)
            await db.flush()
            result = await db.execute(select(Espacio))
            espacios = result.scalars().all()
            print(f"Creados {len(espacios)} espacios")
        else:
            espacios = espacios_existing

        if not espacios:
            print("No hay espacios disponibles. Abortando.")
            await db.close()
            return

        # Mapear conductores por id para acceso rápido
        cond_by_id = {c.id: c for c in conductores}
        perm_by_id = {p.id: p for p in permisionarios}
        veh_by_cond = {}
        for v in vehiculos:
            veh_by_cond.setdefault(v.conductor_id, []).append(v)

        sesiones_count = 0
        pagos_count = 0
        deudas_count = 0

        def calcular_costo(tipo, horas, exencion, metodo_pago):
            if exencion != ExencionTipo.ninguna:
                return 0.0, 700.0 * horas if tipo in (TipoVehiculo.auto, TipoVehiculo.camioneta) else 300.0 * horas
            if tipo == TipoVehiculo.bicicleta:
                return 0.0, 0.0
            precio = 700.0 if tipo in (TipoVehiculo.auto, TipoVehiculo.camioneta) else 300.0
            monto_original = precio * horas
            costo = precio  # primera hora completa
            if horas > 1:
                fraccion_15min = math.ceil((horas - 1) * 4)
                costo = precio + (fraccion_15min / 4) * precio
                costo = round(costo, 2)
                monto_original = round(monto_original, 2)
            if metodo_pago == MetodoPago.mercadopago:
                costo = round(costo * 0.8, 2)
            return costo, round(monto_original, 2)

        def get_perm_for_espacio(esp):
            return perm_by_id.get(esp.permisionario_id, permisionarios[0])

        # === SESIONES FINALIZADAS PAGADAS (efectivo) ===
        escenarios_efectivo = [
            # (conductor_idx, veh_idx, horas, dias_atras)
            (0, 0, 1.0, 1),
            (0, 0, 2.5, 2),
            (0, 1, 0.5, 4),
            (1, 0, 1.5, 1),
            (1, 0, 3.0, 3),
            (3, 0, 1.0, 2),
            (4, 0, 1.0, 1),
            (0, 0, 4.0, 7),
            (1, 0, 0.08, 5),
            (3, 0, 2.0, 6),
            (0, 0, 1.0, 10),
            (1, 0, 1.0, 12),
            (4, 0, 0.5, 8),
            (0, 1, 1.0, 3),
            (1, 0, 2.0, 14),
        ]

        for cond_idx, veh_idx, horas, dias_atras in escenarios_efectivo:
            conductor = conductores[cond_idx] if cond_idx < len(conductores) else conductores[0]
            vehs = veh_by_cond.get(conductor.id, [])
            vehiculo = vehs[min(veh_idx, len(vehs) - 1)] if vehs else None
            tipo = vehiculo.tipo if vehiculo else TipoVehiculo.auto

            espacio = random.choice(espacios)
            perm = get_perm_for_espacio(espacio)

            hora_inicio = now - timedelta(days=dias_atras, hours=random.randint(8, 18))
            hora_fin = hora_inicio + timedelta(hours=horas)

            costo, monto_original = calcular_costo(tipo, horas, conductor.exencion, MetodoPago.efectivo)
            if horas <= 5 / 60:
                costo = 0.0
                monto_original = 0.0

            comision_municipio = round(monto_original * 0.2, 2) if monto_original > 0 else 0.0
            comision_permisionario = round(monto_original * 0.8, 2) if monto_original > 0 else 0.0

            sesion = SesionEstacionamiento(
                espacio_id=espacio.id,
                conductor_id=conductor.id,
                vehiculo_id=vehiculo.id if vehiculo else None,
                permisionario_id=perm.id,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                costo_total=costo,
                pagado=True,
                metodo_pago=MetodoPago.efectivo,
                metodo_ingreso=MetodoIngreso.qr,
                exencion=conductor.exencion,
                codigo_salida=str(secrets.randbelow(9000) + 1000),
                estado=EstadoSesion.finalizada,
            )
            db.add(sesion)
            await db.flush()
            sesiones_count += 1

            db.add(Pago(
                sesion_id=sesion.id,
                monto=costo,
                monto_original=monto_original,
                metodo=MetodoPago.efectivo,
                comision_municipio=comision_municipio,
                comision_permisionario=comision_permisionario,
                confirmado=True,
            ))
            pagos_count += 1

        # === SESIONES FINALIZADAS PAGADAS (Mercado Pago) ===
        escenarios_mp = [
            (0, 0, 1.0, 1),
            (1, 0, 2.0, 2),
            (0, 0, 1.5, 5),
            (3, 0, 1.0, 3),
            (0, 1, 0.5, 8),
            (1, 0, 3.5, 4),
        ]

        for cond_idx, veh_idx, horas, dias_atras in escenarios_mp:
            conductor = conductores[cond_idx] if cond_idx < len(conductores) else conductores[0]
            vehs = veh_by_cond.get(conductor.id, [])
            vehiculo = vehs[min(veh_idx, len(vehs) - 1)] if vehs else None
            tipo = vehiculo.tipo if vehiculo else TipoVehiculo.auto

            espacio = random.choice(espacios)
            perm = get_perm_for_espacio(espacio)

            hora_inicio = now - timedelta(days=dias_atras, hours=random.randint(8, 18))
            hora_fin = hora_inicio + timedelta(hours=horas)

            costo, monto_original = calcular_costo(tipo, horas, conductor.exencion, MetodoPago.mercadopago)

            comision_municipio = 0.0
            comision_permisionario = round(monto_original * 0.8, 2) if monto_original > 0 else 0.0

            sesion = SesionEstacionamiento(
                espacio_id=espacio.id,
                conductor_id=conductor.id,
                vehiculo_id=vehiculo.id if vehiculo else None,
                permisionario_id=perm.id,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                costo_total=costo,
                pagado=True,
                metodo_pago=MetodoPago.mercadopago,
                metodo_ingreso=MetodoIngreso.qr,
                exencion=conductor.exencion,
                codigo_salida=str(secrets.randbelow(9000) + 1000),
                estado=EstadoSesion.finalizada,
            )
            db.add(sesion)
            await db.flush()
            sesiones_count += 1

            db.add(Pago(
                sesion_id=sesion.id,
                monto=costo,
                monto_original=monto_original,
                metodo=MetodoPago.mercadopago,
                comision_municipio=comision_municipio,
                comision_permisionario=comision_permisionario,
                confirmado=True,
                mp_status="approved",
                mp_preference_id=f"DEMO-{sesion.id}-{secrets.randbelow(9000)+1000}",
            ))
            pagos_count += 1

        # === SESIONES EXENTAS ===
        escenarios_exentos = [
            (2, 0, 2.0, 1),
            (2, 0, 1.0, 3),
            (3, 0, 1.5, 2),
            (4, 0, 3.0, 1),
            (4, 0, 1.0, 5),
        ]

        for cond_idx, veh_idx, horas, dias_atras in escenarios_exentos:
            conductor = conductores[cond_idx] if cond_idx < len(conductores) else conductores[0]
            vehs = veh_by_cond.get(conductor.id, [])
            vehiculo = vehs[min(veh_idx, len(vehs) - 1)] if vehs else None
            tipo = vehiculo.tipo if vehiculo else TipoVehiculo.auto

            espacio = random.choice(espacios)
            perm = get_perm_for_espacio(espacio)

            hora_inicio = now - timedelta(days=dias_atras, hours=random.randint(7, 19))
            hora_fin = hora_inicio + timedelta(hours=horas)

            monto_original = (700.0 if tipo in (TipoVehiculo.auto, TipoVehiculo.camioneta) else 300.0) * horas

            sesion = SesionEstacionamiento(
                espacio_id=espacio.id,
                conductor_id=conductor.id,
                vehiculo_id=vehiculo.id if vehiculo else None,
                permisionario_id=perm.id,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                costo_total=0.0,
                pagado=True,
                metodo_pago=MetodoPago.efectivo,
                metodo_ingreso=MetodoIngreso.qr,
                exencion=conductor.exencion,
                codigo_salida=str(secrets.randbelow(9000) + 1000),
                estado=EstadoSesion.finalizada,
            )
            db.add(sesion)
            await db.flush()
            sesiones_count += 1

            db.add(Pago(
                sesion_id=sesion.id,
                monto=0.0,
                monto_original=round(monto_original, 2),
                metodo=MetodoPago.efectivo,
                comision_municipio=round(monto_original * 0.2, 2),
                comision_permisionario=round(monto_original * 0.8, 2),
                confirmado=True,
            ))
            pagos_count += 1

        # === SESIONES CON DEUDA ===
        escenarios_deuda = [
            (0, 0, 1.0, 0),
            (1, 0, 2.0, 0),
            (0, 0, 3.0, 1),
        ]

        for cond_idx, veh_idx, horas, dias_atras in escenarios_deuda:
            conductor = conductores[cond_idx] if cond_idx < len(conductores) else conductores[0]
            vehs = veh_by_cond.get(conductor.id, [])
            vehiculo = vehs[min(veh_idx, len(vehs) - 1)] if vehs else None
            tipo = vehiculo.tipo if vehiculo else TipoVehiculo.auto

            espacio = random.choice(espacios)
            perm = get_perm_for_espacio(espacio)

            hora_inicio = now - timedelta(days=dias_atras, hours=random.randint(7, 18))
            hora_fin = hora_inicio + timedelta(hours=horas)

            costo, monto_original = calcular_costo(tipo, horas, conductor.exencion, MetodoPago.efectivo)

            sesion = SesionEstacionamiento(
                espacio_id=espacio.id,
                conductor_id=conductor.id,
                vehiculo_id=vehiculo.id if vehiculo else None,
                permisionario_id=perm.id,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                costo_total=costo,
                pagado=False,
                metodo_pago=MetodoPago.efectivo,
                metodo_ingreso=MetodoIngreso.qr,
                exencion=ExencionTipo.ninguna,
                codigo_salida=str(secrets.randbelow(9000) + 1000),
                estado=EstadoSesion.deuda,
            )
            db.add(sesion)
            await db.flush()
            sesiones_count += 1

            db.add(Deuda(
                conductor_id=conductor.id,
                sesion_id=sesion.id,
                monto=costo,
                pagada=False,
                reported_by=perm.id,
                motivo=f"Estacionamiento impago - espacio {espacio.ubicacion}",
            ))
            deudas_count += 1

            conductor.saldo_deudor = (conductor.saldo_deudor or 0) + costo

        # === SESION ACTIVA (en curso) ===
        pedro = conductores[0]
        disponible_espacios = [e for e in espacios if e.disponible]
        if disponible_espacios:
            espacio_activo = disponible_espacios[0]
            perm_activo = get_perm_for_espacio(espacio_activo)
            vehs_pedro = veh_by_cond.get(pedro.id, [])

            sesion_activa = SesionEstacionamiento(
                espacio_id=espacio_activo.id,
                conductor_id=pedro.id,
                vehiculo_id=vehs_pedro[0].id if vehs_pedro else None,
                permisionario_id=perm_activo.id,
                hora_inicio=now - timedelta(minutes=47),
                hora_fin=None,
                costo_total=None,
                pagado=False,
                metodo_pago=None,
                metodo_ingreso=MetodoIngreso.qr,
                exencion=ExencionTipo.ninguna,
                codigo_salida="4829",
                estado=EstadoSesion.activa,
            )
            db.add(sesion_activa)
            await db.flush()
            sesiones_count += 1

            espacio_activo.disponible = False

        # === ACTUALIZAR ESPACIOS OCUPADOS ===
        for esp in random.sample(espacios, min(5, len(espacios))):
            if esp.disponible and esp.id != espacio_activo.id if disponible_espacios else True:
                esp.disponible = False

        # === CUOTAS DE PERMISIONARIO ===
        cuotas_count = 0
        for perm in permisionarios:
            for mes_atras in range(1, 4):
                periodo_inicio = now - timedelta(days=30 * mes_atras)
                periodo_fin = periodo_inicio + timedelta(days=30)

                total_efectivo = round(random.uniform(5000, 15000), 2)
                total_mp = round(random.uniform(3000, 10000), 2)
                total = total_efectivo + total_mp
                monto_cuota = round(total * 0.2, 2)

                cuota = CuotaPermisionario(
                    permisionario_id=perm.id,
                    periodo_inicio=periodo_inicio,
                    periodo_fin=periodo_fin,
                    total_recaudado=total,
                    total_efectivo=total_efectivo,
                    total_mp=total_mp,
                    monto_cuota=monto_cuota,
                    pagada=mes_atras > 1,
                    fecha_vencimiento=periodo_fin + timedelta(days=10),
                )
                db.add(cuota)
                cuotas_count += 1

        await db.commit()

        print("=== DATOS FICTICIOS CREADOS ===")
        print(f"  Espacios: {len(espacios)}")
        print(f"  Sesiones: {sesiones_count}")
        print(f"  Pagos: {pagos_count}")
        print(f"  Deudas: {deudas_count}")
        print(f"  Cuotas: {cuotas_count}")
        print(f"  (1 sesión activa: Pedro, 47 min en curso)")
        print()


if __name__ == "__main__":
    asyncio.run(seed_datos())