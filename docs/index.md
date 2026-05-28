# Documentación del Sistema de Estacionamiento Medido

## Visión general

Sistema digital para la gestión de estacionamiento medido en la vía pública.
Cada cuadra tiene un permisionario responsable que gestiona los espacios mediante
códigos QR. Los conductores escanean al llegar y al retirarse, pagando
exclusivamente por el tiempo usado.

## Actores

| Actor           | Descripción                                           |
|-----------------|-------------------------------------------------------|
| **Conductor**   | Usuario que estaciona. Escanea QR de entrada y salida |
| **Permisionario**| Encargado de la cuadra. Aprueba reservas. Genera QR  |
| **Sistema**     | Backend que registra sesiones, calcula costos y cobra |

## Funcionalidades

- **Check-in / Check-out** mediante QR
- **Cálculo dinámico de tarifa** por tiempo real de uso
- **Pago integrado** con Mercado Pago
- **Reservas** con aprobación del permisionario
- **Panel** del permisionario para gestionar espacios y reservas
