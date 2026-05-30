# Comparativa: Sistema Municipal vs Estacionamiento Medido v2.0

## Flujo de estacionamiento

| Paso | Municipal | Nuestro sistema |
|---|---|---|
| 1 | Escanea QR del permisionario | Escanea QR del permisionario |
| 2 | Ingresa **patente, horas, email, pago** | CHECK-IN automático (1 tap) |
| 3 | **Paga por adelantado** (prepago) | El tiempo corre, paga al final |
| 4 | Recibe comprobante por email | Ve el timer en vivo en la app |
| 5 | Inspector recorre con móvil verificando patentes | Permisionario procesa la salida |
| 6 | Si se pasa del tiempo comprado → multa | Paga lo que realmente usó |
| 7 | — | Si no paga → deuda → bloqueo automático |

## Problemas del sistema municipal

- Carga constante de datos (patente, horas, email, pago) **cada vez que estacionás**
- Tenés que **adivinar** cuánto tiempo vas a estar
- Si te pasás del tiempo comprado, te multan aunque hayas pagado
- El comprobante por email es fácil de perder
- El inspector tiene que verificar **cada patente** recorriendo la calle
- No hay registro de usuarios ni historial
- No hay mapa interactivo ni búsqueda de espacios libres

## Ventajas de nuestro sistema

- **Un solo registro** y después escaneás y listo — sin formularios por cada estacionada
- **Pago post-pago**: solo pagás el tiempo real que usaste
- **Sin formularios repetitivos** — registro único con DNI
- Control municipal en tiempo real desde el dashboard
- Deuda acumulativa con bloqueo progresivo, no multa directa
- Exenciones automáticas: discapacidad, frentista, veterano de Malvinas, bicicleta
- App mobile con escáner QR nativo (React Native / Expo)

## Funcionalidad estrella: Búsqueda en vivo de estacionamiento

| Característica | Municipal | Nuestro sistema |
|---|---|---|
| **Búsqueda por GPS** | No tiene | Usa geolocalización del navegador + Nominatim + datos IDEMSA |
| **Búsqueda por destino** | No tiene | Ingresás "Gral. Güemes 150" y te muestra resultados |
| **Datos en tiempo real** | No tiene | Muestra espacios disponibles/ocupados al instante |
| **Integración con mapas** | Imagen estática | Leaflet interactivo + link a Google Maps para navegar |
| **Filtro por distancia** | No tiene | 500 m radio en búsqueda textual, 400 m en GPS |
| **Resultados agrupados** | No tiene | Por cuadra con cantidad de espacios libres y distancia mínima |
| **Geocodificación inversa** | No tiene | Convertís dirección → coordenadas → espacios cercanos |
| **Mapa interactivo** | No tiene | Zoom, marcadores, calles coloreadas por tipo de estacionamiento |

## Ideas principales del proyecto

1. **Automatización total** — el conductor no tiene que hacer nada más que escanear un QR. El sistema detecta el espacio, asigna el vehículo y empieza a contar el tiempo automáticamente.

2. **Pago justo** — pagás el tiempo real de uso, no un bloque comprado por adelantado. Si estacionás 23 minutos, pagás 23 minutos.

3. **Control municipal sin recorrer la calle** — gestores y administradores ven todas las sesiones activas en un mapa en tiempo real desde el escritorio.

4. **Inclusión** — las exenciones (discapacidad, frentista, veterano de Malvinas, bicicleta) se aplican automáticamente según el perfil del conductor. Sin trámites presenciales ni papeles.

5. **Deuda progresiva** — si un conductor se va sin pagar, la deuda se acumula. Al llegar a $10 000 se bloquea automáticamente hasta que regularice. Sin multas sorpresa.

6. **Búsqueda inteligente** — el conductor encuentra estacionamiento disponible cerca de donde va, ya sea por GPS o escribiendo la dirección, y puede navegar hasta ahí con Google Maps.

## Roles del sistema

| Rol | Función |
|---|---|
| **Conductor** | Se registra con DNI, agrega vehículos, busca estacionamiento, estaciona vía QR, paga al retirarse, ve historial |
| **Permisionario** | Asignado a una cuadra, procesa ingresos y salidas, cobra en efectivo o Mercado Pago, reporta deudas |
| **Gestor** | Supervisa permisionarios y conductores, ve sesiones activas y reportes |
| **Admin** | Control total: CRUD de todos los roles, espacios, sesiones, deudas, reportes, exportación CSV |

## Stack técnico

- **Backend**: Python 3.12 + FastAPI (async) + SQLAlchemy (async)
- **Base de datos**: SQLite (desarrollo) / PostgreSQL (producción)
- **Autenticación**: JWT + bcrypt, 4 modelos de usuario
- **Pagos**: Mercado Pago (sandbox) + efectivo
- **Mapas**: Leaflet + OpenStreetMap + Nominatim + IDEMSA (GIS municipal)
- **QR**: Generación dinámica por permisionario y por sesión
- **Mobile**: React Native / Expo con WebView y escáner QR nativo
- **PWA**: Service worker con manifest.json para instalación en el celular
