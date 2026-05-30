# Casos de Uso para Pruebas — Estacionamiento Medido v2.0

**URL**: https://poor-aids-budget-cube.trycloudflare.com  
**Contexto**: app funcional con datos demo cargados (sesiones activas, historial, deudas)

---

## 1. Auth

### 1.1 Login — todos los roles
| # | Caso | Rol | Usuario | Resultado esperado |
|---|---|---|---|---|
| 1.1.1 | Login conductor exitoso | Conductor | `35123456` / `1234` | Redirige a `/conductor`, muestra home con timer |
| 1.1.2 | Login permisionario exitoso | Permisionario | `PER30456789` / `1234` | Redirige a `/permisionario/panel`, muestra sidebar |
| 1.1.3 | Login gestor exitoso | Gestor | `gestor1` / `gestor123` | Redirige a `/gestor`, sidebar con permisos |
| 1.1.4 | Login admin exitoso | Admin | `admin` / `admin123` | Redirige a `/admin`, sidebar completo |
| 1.1.5 | Credenciales incorrectas | Cualquiera | `35123456` / `wrong` | Muestra error "Credenciales inválidas" |
| 1.1.6 | Usuario inexistente | Cualquiera | `99999999` / `1234` | Muestra error "Credenciales inválidas" |
| 1.1.7 | DNI con formato incorrecto | Conductor | `ABCD` / `1234` | Muestra error de validación |

### 1.2 Registro
| # | Caso | Resultado esperado |
|---|---|---|
| 1.2.1 | Registro exitoso | Crea conductor, muestra mensaje "verifica tu email", imprime link en terminal del server |
| 1.2.2 | DNI ya registrado | Muestra error "DNI ya registrado" |
| 1.2.3 | Email ya registrado | Muestra error "Email ya registrado" |
| 1.2.4 | Campos obligatorios vacios | Muestra errores de validacion del lado cliente |
| 1.2.5 | Contraseña muy corta | Muestra error de validacion (>4 caracteres) |
| 1.2.6 | Verificar email con token valido | Abrir `/api/auth/verify-email?token=<uuid>` → pagina exito |
| 1.2.7 | Verificar email con token invalido | Abrir `/api/auth/verify-email?token=xxx` → pagina error |
| 1.2.8 | Login sin verificar email | Intentar login con conductor no verificado → error "verifica tu email" |

---

## 2. Conductor

### 2.1 Home (sesion activa)
| # | Caso | Usuario | Resultado esperado |
|---|---|---|---|
| 2.1.1 | Ver timer en vivo | `35123456` | Muestra tarjeta "Sesión activa" con timer actualizandose, costo estimado |
| 2.1.2 | Ver tarifa aplicada | `35123456` | Muestra $600/h (auto, sin exencion) |
| 2.1.3 | Conductor sin sesion activa | `36234567` | No mostrar tarjeta de sesion activa, mostrar boton "Estacionar" |
| 2.1.4 | Conductor exento (discapacidad) | `30111222` | Si tiene sesion activa, mostrar costo $0 |
| 2.1.5 | Conductor bloqueado por deuda | `20999888` (debe $2400) | Mostrar alerta de deuda pendiente, boton estacionar bloqueado |
| 2.1.6 | Conductor con bicicleta | `37555666` | Costo $0 por bicicleta |

### 2.2 Buscar estacionamiento
| # | Caso | Resultado esperado |
|---|---|---|
| 2.2.1 | Mapa IDEMSA cargado | El iframe del mapa municipal se ve correctamente |
| 2.2.2 | Busqueda por calle y altura | Escribir "Caseros 1150" → muestra espacios disponibles (cards) |
| 2.2.3 | Busqueda por solo calle | Escribir "Güemes" → muestra resultados filtrados |
| 2.2.4 | Busqueda sin resultados | Escribir "CalleFalsa 9999" → mensaje "No se encontraron espacios" |
| 2.2.5 | GPS "Buscar ahora" | Click boton → busca dentro de 400m, muestra resultados |
| 2.2.6 | Resultados muestran precio | Cada card muestra $600/h o $100/h o Gratis |
| 2.2.7 | Resultados con permisionario asignado | Muestra nombre del permisionario si tiene asignacion |

### 2.3 Estacionar (check-in)
| # | Caso | Resultado esperado |
|---|---|---|
| 2.3.1 | Pagina de escaneo QR | Se muestra camara/scanner + input manual |
| 2.3.2 | Check-in exitoso via QR | Escanear QR del permisionario → sesion creada, redirige a home con timer |
| 2.3.3 | Check-in con vehiculo seleccionado | Elegir vehiculo en la UI antes de escanear |
| 2.3.4 | Check-in bloqueado por deuda | `20999888` → error "Tenes una deuda pendiente" |
| 2.3.5 | Check-in en horario nocturno | Aplica tarifa nocturna correspondiente |

### 2.4 Checkout (sesion propia)
| # | Caso | Resultado esperado |
|---|---|---|
| 2.4.1 | Ver pantalla checkout | Boton "Ver detalle" desde home → muestra timer, costo, botones |
| 2.4.2 | Conductor ve waiting badge | Muestra "Esperando que el permisionario procese la salida" |
| 2.4.3 | Boton MP (si permisionario proceso con MP) | Muestra "Pagar con Mercado Pago" → lleva a simulacion |
| 2.4.4 | Pago MP simulado | Click "Pagar" en simulacion → muestra confirmacion |
| 2.4.5 | Sin acciones disponibles | Conductor NO puede finalizar su propia sesion (solo permisionario) |

### 2.5 Perfil
| # | Caso | Resultado esperado |
|---|---|---|
| 2.5.1 | Ver datos personales | Muestra DNI, nombre, email, telefono |
| 2.5.2 | Ver exencion aplicada | Discapacidad: muestra "Oblea Discapacidad (Gratuito)" |
| 2.5.3 | Ver saldo deudor | `20999888` muestra $2400 de deuda |
| 2.5.4 | Sin deuda | `35123456` muestra "Sin deudas" |

### 2.6 Vehiculos
| # | Caso | Resultado esperado |
|---|---|---|
| 2.6.1 | Listar vehiculos | Pedro: muestra Toyota Corolla (predet.) + Honda CG 150 |
| 2.6.2 | Vehiculo predeterminado | Marca visual de cual es el default |
| 2.6.3 | Bicicleta | Eva: muestra "Venzo Urban (Bicicleta)" |
| 2.6.4 | Agregar vehiculo | Formulario: patente, tipo, marca, modelo |
| 2.6.5 | Eliminar vehiculo | Confirmacion y eliminacion |

### 2.7 Historial
| # | Caso | Resultado esperado |
|---|---|---|
| 2.7.1 | Ver sesiones pasadas | Pedro: muestra 2 sesiones finalizadas con costos $1350 y $900 |
| 2.7.2 | Ver metodo de pago | Columna con MP o Efectivo |
| 2.7.3 | Sesion gratuita | Carlos/Lucia/Roberto/Eva: costo $0 con exencion indicada |
| 2.7.4 | Sesion sin costo con exencion | Muestra "Exento (Discapacidad)" en lugar del monto |
| 2.7.5 | Historial vacio | Conductor nuevo: mensaje "Sin sesiones registradas" |

---

## 3. Permisionario

### 3.1 Panel
| # | Caso | Resultado esperado |
|---|---|---|
| 3.1.1 | Ver dashboard | Tarjetas: sesiones activas, ingresos del dia, espacios libres |
| 3.1.2 | Ver sesiones activas con timer | Lista de conductores estacionados, timer en vivo, costo corriendo |
| 3.1.3 | Sin sesiones | Maria (si no tiene activas): muestra "Sin sesiones activas" |
| 3.1.4 | Costos acumulados del dia | Suma total de costos de sesiones finalizadas hoy |

### 3.2 Espacios
| # | Caso | Resultado esperado |
|---|---|---|
| 3.2.1 | Mapa de espacios | Visualizacion de espacios asignados con color libre/ocupado |
| 3.2.2 | Espacio ocupado | Muestra patente del conductor, tiempo transcurrido |

### 3.3 Cuadra
| # | Caso | Resultado esperado |
|---|---|---|
| 3.3.1 | Ver cuadra asignada | Juan: muestra "Gral. Güemes 100-200 (Par + Impar)" |
| 3.3.2 | Vista en mapa | Mapa con la cuadra resaltada |

### 3.4 QR
| # | Caso | Resultado esperado |
|---|---|---|
| 3.4.1 | Ver QR de la cuadra | Codigo QR generado dinamicamente para que conductores escaneen |
| 3.4.2 | QR contiene datos de cuadra | Al escanear, identifica al permisionario y cuadra |

### 3.5 Ingreso Manual
| # | Caso | Resultado esperado |
|---|---|---|
| 3.5.1 | Ingreso por patente existente | Escribir patente de Pedro (`AB123CD`) → asigna al conductor automaticamente |
| 3.5.2 | Ingreso con patente nueva | Escribir patente no registrada → crea conductor temporal |
| 3.5.3 | Confirmar ingreso | Sesion se crea y aparece en panel de activas |
| 3.5.4 | Patente vacia | Error "Ingrese una patente" |

### 3.6 Salida
| # | Caso | Resultado esperado |
|---|---|---|
| 3.6.1 | Procesar salida efectivo | Seleccionar sesion activa → "Cobrar en Efectivo" → sesion finaliza inmediato |
| 3.6.2 | Procesar salida MP | "Mercado Pago" → costo se bloquea, espera pago del conductor |
| 3.6.3 | Reportar deuda | Marcar como deuda si conductor no paga → aparece en admin deudas |
| 3.6.4 | Ver resumen antes de finalizar | Muestra: patente, tiempo, costo total, metodo |

### 3.7 Historial permisionario
| # | Caso | Resultado esperado |
|---|---|---|
| 3.7.1 | Sesiones del dia | Lista resumida de todas las sesiones procesadas hoy |
| 3.7.2 | Totales del dia | Suma de ingresos, cantidad de sesiones |

---

## 4. Gestor

### 4.1 Dashboard
| # | Caso | Resultado esperado |
|---|---|---|
| 4.1.1 | Ver dashboard gestor | Estadisticas generales: sesiones activas, conductores, ingresos |
| 4.1.2 | Navegacion sidebar | Links a: Dashboard, Conductores, Permisionarios, Sesiones, Reportes |

---

## 5. Admin

### 5.1 Dashboard
| # | Caso | Resultado esperado |
|---|---|---|
| 5.1.1 | Ver dashboard admin | Panel completo con todas las metricas del sistema |
| 5.1.2 | Sidebar con todas las secciones | Conductores, Permisionarios, Gestores, Sesiones, Espacios, Reportes, Deudas |

### 5.2 CRUD Conductores
| # | Caso | Resultado esperado |
|---|---|---|
| 5.2.1 | Listar conductores | Tabla con los 6 conductores: DNI, nombre, email, exencion |
| 5.2.2 | Buscar conductor | Filtro por DNI o nombre |
| 5.2.3 | Ver detalle conductor | Click → datos personales, vehiculos, historial, deudas |
| 5.2.4 | Bloquear conductor | Boton bloquear → no puede estacionar |
| 5.2.5 | Exportar CSV | Descarga de lista de conductores |

### 5.3 CRUD Permisionarios
| # | Caso | Resultado esperado |
|---|---|---|
| 5.3.1 | Listar permisionarios | Tabla: codigo, nombre, email, calles asignadas |
| 5.3.2 | Asignar cuadra | Formulario: calle, altura desde/hasta, lado |
| 5.3.3 | Ver detalle permisionario | Muestra datos + calles asignadas + sesiones |

### 5.4 CRUD Gestores
| # | Caso | Resultado esperado |
|---|---|---|
| 5.4.1 | Listar gestores | Muestra Carlos Mendez con permisos |
| 5.4.2 | Editar permisos | Checkboxes de modulos habilitados |

### 5.5 Sesiones en Vivo
| # | Caso | Resultado esperado |
|---|---|---|
| 5.5.1 | Mapa interactivo | Mapa con marcadores de sesiones activas |
| 5.5.2 | Lista de sesiones activas | Tabla con conductor, espacio, timer, costo |

### 5.6 Reportes
| # | Caso | Resultado esperado |
|---|---|---|
| 5.6.1 | Reporte de ingresos | Totales por dia/semana/mes, por metodo de pago |
| 5.6.2 | Reporte de ocupacion | % de espacios ocupados vs libres |
| 5.6.3 | Exportar reporte | Descarga en CSV |

### 5.7 Espacios (Admin)
| # | Caso | Resultado esperado |
|---|---|---|
| 5.7.1 | Listar espacios | Tabla con ubicacion, precio, disponible, permisionario |
| 5.7.2 | Asignar espacio a permisionario | Selector de permisionario + guardar |
| 5.7.3 | Editar precio por hora | Cambiar tarifa de un espacio especifico |

### 5.8 Deudas
| # | Caso | Resultado esperado |
|---|---|---|
| 5.8.1 | Listar deudas | Muestra deuda activa de Roberto ($2400) + deudas pagadas |
| 5.8.2 | Marcar deuda como pagada | Click "Pagar" → deuda se cierra |
| 5.8.3 | Ver detalle de deuda | Muestra conductor, monto, motivo, quien reporto |

---

## 6. Logica de Negocio

### 6.1 Calculo de costos
| # | Caso | Vehiculo | Horas | Exencion | Costo esperado |
|---|---|---|---|---|---|
| 6.1.1 | Auto en horario normal | Auto | 2h | Ninguna | $1200 |
| 6.1.2 | Auto 1h23min (redondeo) | Auto | 1h23min | Ninguna | $600 (1h) o $1200 (2h, ver redondeo) |
| 6.1.3 | Moto en horario normal | Moto | 1.5h | Ninguna | $200 |
| 6.1.4 | Bicicleta | Bici | 3h | Ninguna | $0 |
| 6.1.5 | Discapacidad | Auto | 3h | Discapacidad | $0 |
| 6.1.6 | Frentista (mañana) | Auto | 2h | Frentista | $0 |
| 6.1.7 | Veterano Malvinas | Auto | cualquier | Veterano | $0 |

### 6.2 Horarios
| # | Caso | Resultado esperado |
|---|---|---|
| 6.2.1 | Domingo gratis | Cualquier vehiculo el domingo → $0 |
| 6.2.2 | Nocturno (22-5hs) | Aplica tarifa nocturna |
| 6.2.3 | Sabado 7-14hs | Tarifa normal en horario sabatino |
| 6.2.4 | Fuera de horario (ej. 23hs) | No permite iniciar sesion o aplica nocturno |

### 6.3 Bloqueos
| # | Caso | Resultado esperado |
|---|---|---|
| 6.3.1 | Conductor con deuda no puede estacionar | Boton estacionar deshabilitado, muestra alerta |
| 6.3.2 | Admin bloquea conductor | Conductor bloqueado no puede iniciar sesion |
| 6.3.3 | Bloqueo temporal (fecha expiracion) | Despues de la fecha, puede volver a estacionar |

### 6.4 Flujo MP
| # | Caso | Resultado esperado |
|---|---|---|
| 6.4.1 | Permisionario elige MP en salida | Costo se bloquea, sesion queda "activa" |
| 6.4.2 | Conductor ve boton "Pagar con MP" | Aparece en checkout |
| 6.4.3 | Pago MP simulado exitoso | Sesion se finaliza, pago registrado |
| 6.4.4 | Conductor no paga | Sesion queda en estado "deuda" |

---

## Cobertura resumen

| Area | Casos |
|---|---|
| Auth (login + registro + verify) | 14 |
| Conductor (home, buscar, estacionar, checkout, perfil, vehiculos, historial) | 27 |
| Permisionario (panel, espacios, cuadra, QR, ingreso, salida, historial) | 16 |
| Gestor (dashboard, navegacion) | 3 |
| Admin (dashboard, 7 CRUDs, reportes, deudas) | 22 |
| Logica de negocio (costos, horarios, bloqueos, MP) | 17 |
| **Total** | **~99 casos** |
