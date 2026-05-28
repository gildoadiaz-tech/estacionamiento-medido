# Datos geoespaciales del centro y macro centro de Salta
# Coordenadas aproximadas en formato [lat, lng]
# Centro de Salta: -24.7883, -65.4106

from enum import Enum


class TipoVia(str, Enum):
    estacionamiento_medido = "estacionamiento_medido"
    prohibido_estacionar = "prohibido_estacionar"
    carga_descarga = "carga_descarga"
    bicisenda = "bicisenda"
    peatonal = "peatonal"


class TipoEspacio(str, Enum):
    libre = "libre"
    ocupado = "ocupado"
    reservado = "reservado"


CENTRO_SALTA = [-24.7883, -65.4106]

# Calles del centro con información de estacionamiento
# Cada calle es una lista de puntos [lat, lng] que forman la polilínea
CALLES = [
    # ─── Calles con estacionamiento medido (Norte-Sur) ───
    {
        "nombre": "Caseros",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7810, -65.4055], [-24.7825, -65.4055], [-24.7840, -65.4055],
            [-24.7855, -65.4055], [-24.7870, -65.4055], [-24.7885, -65.4055],
            [-24.7900, -65.4055], [-24.7915, -65.4055], [-24.7930, -65.4055],
        ],
        "cuadras": 8,
        "tarifa": 60,
    },
    {
        "nombre": "Mitre",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7810, -65.4075], [-24.7825, -65.4075], [-24.7840, -65.4075],
            [-24.7855, -65.4075], [-24.7870, -65.4075], [-24.7885, -65.4075],
            [-24.7900, -65.4075], [-24.7915, -65.4075], [-24.7930, -65.4075],
        ],
        "cuadras": 8,
        "tarifa": 60,
    },
    {
        "nombre": "España",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7815, -65.4095], [-24.7830, -65.4095], [-24.7845, -65.4095],
            [-24.7860, -65.4095], [-24.7875, -65.4095], [-24.7890, -65.4095],
            [-24.7905, -65.4095], [-24.7920, -65.4095],
        ],
        "cuadras": 7,
        "tarifa": 60,
    },
    {
        "nombre": "Alberdi",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7815, -65.4115], [-24.7830, -65.4115], [-24.7845, -65.4115],
            [-24.7860, -65.4115], [-24.7875, -65.4115], [-24.7890, -65.4115],
            [-24.7905, -65.4115], [-24.7920, -65.4115],
        ],
        "cuadras": 7,
        "tarifa": 50,
    },
    {
        "nombre": "Buenos Aires",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7815, -65.4135], [-24.7830, -65.4135], [-24.7845, -65.4135],
            [-24.7860, -65.4135], [-24.7875, -65.4135], [-24.7890, -65.4135],
            [-24.7905, -65.4135], [-24.7920, -65.4135],
        ],
        "cuadras": 7,
        "tarifa": 50,
    },
    {
        "nombre": "Balcarce",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7815, -65.4155], [-24.7830, -65.4155], [-24.7845, -65.4155],
            [-24.7860, -65.4155], [-24.7875, -65.4155], [-24.7890, -65.4155],
            [-24.7905, -65.4155],
        ],
        "cuadras": 6,
        "tarifa": 50,
    },
    {
        "nombre": "Zuviría",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7815, -65.4175], [-24.7830, -65.4175], [-24.7845, -65.4175],
            [-24.7860, -65.4175], [-24.7875, -65.4175], [-24.7890, -65.4175],
            [-24.7905, -65.4175],
        ],
        "cuadras": 6,
        "tarifa": 50,
    },
    {
        "nombre": "Urquiza",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7815, -65.4195], [-24.7830, -65.4195], [-24.7845, -65.4195],
            [-24.7860, -65.4195], [-24.7875, -65.4195], [-24.7890, -65.4195],
            [-24.7905, -65.4195],
        ],
        "cuadras": 6,
        "tarifa": 50,
    },

    # ─── Calles con estacionamiento medido (Este-Oeste) ───
    {
        "nombre": "Córdoba",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7855, -65.4190], [-24.7855, -65.4170], [-24.7855, -65.4150],
            [-24.7855, -65.4130], [-24.7855, -65.4110], [-24.7855, -65.4090],
            [-24.7855, -65.4070], [-24.7855, -65.4050],
        ],
        "cuadras": 7,
        "tarifa": 60,
    },
    {
        "nombre": "La Rioja",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7875, -65.4190], [-24.7875, -65.4170], [-24.7875, -65.4150],
            [-24.7875, -65.4130], [-24.7875, -65.4110], [-24.7875, -65.4090],
            [-24.7875, -65.4070], [-24.7875, -65.4050],
        ],
        "cuadras": 7,
        "tarifa": 60,
    },
    {
        "nombre": "Santiago del Estero",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7895, -65.4190], [-24.7895, -65.4170], [-24.7895, -65.4150],
            [-24.7895, -65.4130], [-24.7895, -65.4110], [-24.7895, -65.4090],
            [-24.7895, -65.4070], [-24.7895, -65.4050],
        ],
        "cuadras": 7,
        "tarifa": 50,
    },
    {
        "nombre": "Santa Fe",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7915, -65.4190], [-24.7915, -65.4170], [-24.7915, -65.4150],
            [-24.7915, -65.4130], [-24.7915, -65.4110], [-24.7915, -65.4090],
            [-24.7915, -65.4070], [-24.7915, -65.4050],
        ],
        "cuadras": 7,
        "tarifa": 50,
    },
    {
        "nombre": "Jujuy",
        "tipo": TipoVia.estacionamiento_medido,
        "puntos": [
            [-24.7935, -65.4170], [-24.7935, -65.4150], [-24.7935, -65.4130],
            [-24.7935, -65.4110], [-24.7935, -65.4090], [-24.7935, -65.4070],
            [-24.7935, -65.4050],
        ],
        "cuadras": 6,
        "tarifa": 50,
    },

    # ─── Avenidas sin estacionamiento / prohibido ───
    {
        "nombre": "Av. San Martín",
        "tipo": TipoVia.prohibido_estacionar,
        "puntos": [
            [-24.7780, -65.4035], [-24.7800, -65.4035], [-24.7820, -65.4035],
            [-24.7840, -65.4035], [-24.7860, -65.4035], [-24.7880, -65.4035],
            [-24.7900, -65.4035], [-24.7920, -65.4035], [-24.7940, -65.4035],
            [-24.7960, -65.4035],
        ],
        "cuadras": 10,
        "tarifa": 0,
    },
    {
        "nombre": "Av. Sarmiento",
        "tipo": TipoVia.prohibido_estacionar,
        "puntos": [
            [-24.7800, -65.4210], [-24.7800, -65.4190], [-24.7800, -65.4170],
            [-24.7800, -65.4150], [-24.7800, -65.4130], [-24.7800, -65.4110],
            [-24.7800, -65.4090], [-24.7800, -65.4070], [-24.7800, -65.4050],
        ],
        "cuadras": 8,
        "tarifa": 0,
    },
    {
        "nombre": "Av. Belgrano",
        "tipo": TipoVia.prohibido_estacionar,
        "puntos": [
            [-24.7950, -65.4210], [-24.7950, -65.4190], [-24.7950, -65.4170],
            [-24.7950, -65.4150], [-24.7950, -65.4130], [-24.7950, -65.4110],
            [-24.7950, -65.4090], [-24.7950, -65.4070], [-24.7950, -65.4050],
        ],
        "cuadras": 8,
        "tarifa": 0,
    },
    {
        "nombre": "Av. Virrey Toledo",
        "tipo": TipoVia.prohibido_estacionar,
        "puntos": [
            [-24.7820, -65.4220], [-24.7840, -65.4220], [-24.7860, -65.4220],
            [-24.7880, -65.4220], [-24.7900, -65.4220], [-24.7920, -65.4220],
            [-24.7940, -65.4220],
        ],
        "cuadras": 6,
        "tarifa": 0,
    },
    {
        "nombre": "Av. Chile / Av. Bolivia",
        "tipo": TipoVia.prohibido_estacionar,
        "puntos": [
            [-24.7820, -65.4030], [-24.7840, -65.4030], [-24.7860, -65.4030],
            [-24.7880, -65.4030], [-24.7900, -65.4030], [-24.7920, -65.4030],
            [-24.7940, -65.4030],
        ],
        "cuadras": 6,
        "tarifa": 0,
    },

    # ─── Zona peatonal ───
    {
        "nombre": "Mitre (peatonal centro)",
        "tipo": TipoVia.peatonal,
        "puntos": [
            [-24.7885, -65.4105], [-24.7885, -65.4095], [-24.7885, -65.4085],
            [-24.7885, -65.4075],
        ],
        "cuadras": 3,
        "tarifa": 0,
    },
]


def generar_espacios_para_calle(calle):
    espacios = []
    pts = calle["puntos"]
    for i in range(len(pts) - 1):
        lat1, lng1 = pts[i]
        lat2, lng2 = pts[i + 1]
        for j in range(5):
            t = (j + 0.5) / 5
            lat = round(lat1 + (lat2 - lat1) * t, 6)
            lng = round(lng1 + (lng2 - lng1) * t, 6)
            espacios.append({
                "lat": lat, "lng": lng,
                "calle": calle["nombre"],
                "tarifa": calle["tarifa"],
                "tipo": calle["tipo"].value,
            })
    return espacios


ESPACIOS_VIRTUALES = []
for c in CALLES:
    if c["tipo"] == TipoVia.estacionamiento_medido:
        ESPACIOS_VIRTUALES.extend(generar_espacios_para_calle(c))
