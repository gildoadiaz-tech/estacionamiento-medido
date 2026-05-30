# Desafío SEM — Propuesta

---

## 1. Flujo completo de pago para el conductor

1. **Estacionar** — El conductor busca un espacio libre en el mapa o por dirección, selecciona uno y se registra el inicio de la sesión.

2. **Mientras está estacionado** — Ve en su pantalla un contador en tiempo real con el tiempo transcurrido y el costo estimado, actualizándose automáticamente.

3. **El permisionario finaliza la sesión** — Cuando el conductor se va, el permisionario procesa la salida desde su celular eligiendo el método de pago.

4. **Si paga en efectivo** — El conductor ve en su pantalla "Estacionamiento finalizado" con el monto a pagar al permisionario. Listo.

5. **Si paga con Mercado Pago** — El conductor ve "Pago pendiente" y un botón que lo lleva a Mercado Pago. Una vez que paga, la sesión se cierra sola.

6. **Si está exento** (discapacidad, frentista, veterano de Malvinas, bicicleta) — No paga nada, la sesión se cierra y listo.

---

## 2. Rol del permisionario en el nuevo sistema

- **Registra el ingreso** cuando el conductor estaciona, escaneando su código o ingresando la patente.
- **Monitorea en vivo** todas las sesiones activas en su cuadra, con timer y costo en tiempo real.
- **Procesa la salida** eligiendo si el conductor paga en efectivo o con Mercado Pago.
- **Genera QR de salida** desde su panel para mostrar al conductor o imprimir.
- **Para permisionarios sin celular** — Puede imprimir su código QR y operar desde cualquier computadora o tablet del comercio.
- **Garantía de cobro** — Siempre cobra el 80%. En efectivo lo recibe directamente; con Mercado Pago el dinero llega a su cuenta automáticamente.
- **Accede a reportes** diarios de lo cobrado con desglose de su comisión.

---

## 3. Mecanismo de registro digital del pago en efectivo

Cuando el permisionario cobra en efectivo, el sistema registra automáticamente:

- Monto exacto cobrado, con tarifa, fraccionamiento y exenciones aplicadas.
- Fecha, hora y permisionario que cobró.
- Sesión y espacio asociados.

Queda un registro digital por cada pago en efectivo, sin talonario de papel ni manual alguno. El administrador puede ver y filtrar todos los cobros desde su panel.

Si un conductor se va sin pagar, esa deuda se acumula automáticamente y se descuenta en su próxima sesión.

---

## 4. Cumplimiento de la Ordenanza 12.170

| Regla | Cómo la cumplimos |
|---|---|
| **Tarifas** | $700 la hora para autos y camionetas, $300 para motos, bicicletas gratis |
| **Fraccionamiento** | Desde la segunda hora se cobra cada 15 minutos, no por hora completa |
| **Tolerancia** | Los primeros 5 minutos son gratuitos — si te vas antes, no pagás nada |
| **Descuento 20% digital** | Pagando con Mercado Pago tenés 20% de descuento, que lo absorbe el municipio |
| **Exenciones** | Discapacidad con oblea, frentista (validado por calle), veterano de Malvinas — todos gratuitos |
| **Feriados** | Estacionamiento diurno gratis en feriados nacionales y provinciales de Salta. Zonas nocturnas habilitadas de 22 a 5 |
| **Horarios** | Lunes a viernes 7 a 21, sábados 7 a 14, domingos gratis. Zonas nocturnas (Balcarce, Güemes, Alvarado) 22 a 5 |
| **Distribución** | 80% para el permisionario, 20% para el municipio, en todos los cobros |

---

## 5. Integración con Mercado Pago

- El conductor elige Mercado Pago como método de pago y se abre la plataforma de MP directamente.
- Acepta tarjeta de crédito, débito, transferencia bancaria y saldo en cuenta.
- El cobro se divide automáticamente: el permisionario recibe el 80% en su cuenta de MP y el municipio el 20%.
- MP notifica al sistema cuando el pago se confirma, y la sesión se cierra sin intervención manual.
- Para la demo funciona en modo simulación. En producción se configuran las credenciales reales del permisionario.

---

## 6. Velocidad de transacción

El sistema actual de Salta (2024-25) fracasó porque cada transacción demoraba hasta 2 minutos, generando malestar y abandono.

Nuestro sistema resuelve esto:

- **Check-in**: menos de 1 segundo. El conductor escanea el QR y ya está registrado.
- **Cálculo de costo**: instantáneo, se hace en el servidor sin demora.
- **Salida en efectivo**: menos de 1 segundo. El permisionario confirma y listo.
- **Salida con Mercado Pago**: el link de pago se genera en 1 segundo. El conductor paga en paralelo sin bloquear nada.
- **Sin llamadas, sin tickets impresos, sin espera manual**. Todo es digital e inmediato.

---

## 7. Accesibilidad

- **Celular básico** — La app es una página web ligera (menos de 2MB) que funciona en cualquier Android con Chrome. No hay que descargar nada de la tienda.
- **Conductor sin celular** — El permisionario puede imprimir un código QR en tarjeta para que el conductor escanee al volver. Registra el ingreso y la salida manualmente desde su dispositivo.
- **Permisionario sin celular propio** — Opera desde cualquier computadora o tablet del comercio. También puede imprimir su código QR para ofrecer a los conductores.
- **Sin GPS** — Si el conductor no tiene ubicación, puede buscar por calle y número manualmente.
- **Sin cámara** — Si no puede escanear el QR, ingresa el código de 4 dígitos a mano.
- **Poca señal** — La app funciona offline para ver la sesión activa. Solo necesita conexión para iniciar o finalizar.
- **Legibilidad** — Letras grandes, botones amplios para tocar, colores con buen contraste, estados claros (verde = todo bien, amarillo = esperando, rojo = error).