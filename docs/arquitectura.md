# Arquitectura del sistema

## Diagrama de componentes

```
┌─────────────────────────────────────────────────────────┐
│                      Cliente                             │
│  ┌─────────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Expo (app)  │  │ Browser  │  │ Escáner QR       │   │
│  └──────┬──────┘  └────┬─────┘  └────────┬─────────┘   │
└─────────┼──────────────┼─────────────────┼──────────────┘
          │              │                 │
    ┌─────▼──────────────▼─────────────────▼──────┐
    │           Cloudflare Tunnel                  │
    │         (exposición sin hosting)             │
    └────────────────────┬────────────────────────┘
                         │
    ┌────────────────────▼────────────────────────┐
    │              FastAPI (Backend)               │
    │  ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
    │  │   API    │ │  QR Gen  │ │  MP Client  │  │
    │  └────┬─────┘ └──────────┘ └──────┬──────┘  │
    └───────┼───────────────────────────┼──────────┘
            │                           │
    ┌───────▼───────┐           ┌───────▼───────┐
    │    SQLite     │           │ Mercado Pago  │
    │  (base local) │           │ (sandbox API) │
    └───────────────┘           └───────────────┘
```

## Modelo de datos

```mermaid
erDiagram
    PERMISIONARIO ||--o{ ESPACIO : tiene
    ESPACIO ||--o{ SESION : registra
    ESPACIO ||--o{ RESERVA : reserva
    CONDUCTOR ||--o{ SESION : realiza
    CONDUCTOR ||--o{ RESERVA : solicita
    SESION ||--|| PAGO : genera

    PERMISIONARIO {
        int id PK
        string nombre
        string email
        string telefono
    }
    CONDUCTOR {
        int id PK
        string nombre
        string email
        string telefono
    }
    ESPACIO {
        int id PK
        string ubicacion
        int permisionario_id FK
        float precio_por_hora
        bool disponible
    }
    SESION {
        int id PK
        int espacio_id FK
        int conductor_id FK
        datetime hora_inicio
        datetime hora_fin
        float costo_total
        bool pagado
        string pago_id
    }
    RESERVA {
        int id PK
        int espacio_id FK
        int conductor_id FK
        datetime hora_inicio
        datetime hora_fin
        enum estado
        datetime creada_en
    }
```

## Flujo de check-in / check-out

```mermaid
sequenceDiagram
    participant C as Conductor
    participant S as Sistema
    participant MP as Mercado Pago
    participant P as Permisionario

    C->>S: Escanea QR entrada
    S->>S: Registra hora inicio
    S-->>C: Muestra QR salida
    Note over C: Estaciona
    C->>S: Escanea QR salida
    S->>S: Calcula tiempo y costo
    S->>MP: Crea preferencia de pago
    MP-->>S: Link de pago
    S-->>C: Link de pago
    C->>MP: Paga
    MP-->>S: Notifica pago
    S->>S: Marca como pagado
    S-->>P: Notifica fin
```

## Stack tecnológico

| Componente   | Tecnología     | Justificación                          |
|-------------|----------------|----------------------------------------|
| Backend     | FastAPI        | Async, tipado, documentación automática|
| Base datos  | SQLite         | Sin servidor, cero config, archivo     |
| QR          | qrcode + PIL   | Generación server-side sin API externa |
| Pagos       | Mercado Pago   | #1 en Argentina, sandbox gratuito      |
| Frontend    | Tailwind + Jinja2 | Sin build step, CDN, responsive     |
| Exposición  | Cloudflare     | Tunnel gratuito, sin dominio propio    |
