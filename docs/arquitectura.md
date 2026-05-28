# Arquitectura del sistema

## Diagrama de componentes

```mermaid
graph TB
    subgraph Cliente
        EXP[App Expo<br/>WebView + QR nativo]
        NAV[Browser<br/>Jinja2 templates]
    end

    subgraph "Cloudflare Tunnel"
        CF[URL pública gratuita]
    end

    subgraph "FastAPI Backend"
        AUTH[auth_routes.py<br/>JWT login]
        API[main.py<br/>55+ endpoints]
        QR[qr_utils.py<br/>Generación QR]
        MP[mercado_pago.py<br/>MP integration]
        IDEMSA[idemsa_data.py<br/>Sync GIS]
    end

    subgraph "Base de datos"
        DB[(SQLite<br/>estacionamiento.db)]
    end

    subgraph "Externo"
        MPAPI[Mercado Pago<br/>Sandbox API]
        IDEMSA_API[IDEMSA<br/>Visor GIS]
    end

    EXP --> CF
    NAV --> CF
    CF --> API
    NAV --> API
    API --> AUTH
    API --> QR
    API --> MP
    API --> IDEMSA
    API --> DB
    MP --> MPAPI
    IDEMSA --> IDEMSA_API
```

## Modelo de datos (ERD)

```mermaid
erDiagram
    CONDUCTOR ||--o{ SESION : realiza
    CONDUCTOR ||--o{ RESERVA : solicita
    CONDUCTOR ||--o{ PENALIZACION : recibe
    ESPACIO ||--o{ SESION : registra
    ESPACIO ||--o{ RESERVA : reserva

    CONDUCTOR {
        int id PK
        string nombre
        string email
        string username UK
        string password_hash
        string patente
        bool bloqueado
        float saldo_deudor
    }

    PERMISIONARIO {
        int id PK
        string nombre
        string email
        string username UK
        string password_hash
        string calle
    }

    ADMIN {
        int id PK
        string nombre
        string username UK
        string password_hash
    }

    ESPACIO {
        int id PK
        string ubicacion
        float precio_por_hora
        bool disponible
        float lat
        float lng
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
        string metodo_pago
        bool lista_para_salir
    }

    RESERVA {
        int id PK
        int espacio_id FK
        int conductor_id FK
        datetime hora_inicio
        datetime hora_fin
        enum estado
        datetime creada_en
        datetime checkin_time
        bool usada
    }

    PENALIZACION {
        int id PK
        int conductor_id FK
        int reserva_id FK
        float monto
        string motivo
        datetime fecha
        bool pagada
    }
```

## Relaciones clave

- **Permisionario ↔ Espacios**: el permisionario NO tiene espacios asignados directamente. Es dueño de una **calle entera**. Los espacios se matchean por `ubicacion.startswith(perm.calle)`.
- **Espacios IDEMSA**: 6,974 espacios generados a partir de 604 segmentos viales oficiales. Grid de ~7m entre puntos.
- **Sesión**: una sesión pertenece a un conductor y un espacio. El costo se calcula al finalizar según `calcular_costo_estacionamiento(inicio, fin)`.

## Flujo de check-in / check-out

```mermaid
sequenceDiagram
    participant C as Conductor
    participant S as Sistema
    participant MP as Mercado Pago
    participant P as Permisionario

    Note over C: ESCENARIO 1: QR de permisionario
    C->>S: Escanea QR /conductor/checkin/perm/{id}
    S->>S: Busca espacio en esa calle
    S->>S: Crea sesion (hora_inicio=now)
    S-->>C: Redirige a /conductor/checkout/{id}
    
    C->>S: Elige metodo_pago + patente
    S->>S: Guarda metodo_pago

    alt Efectivo
        P->>S: Presiona "Cobrar efectivo"
        S->>S: Calcula costo (calcular_costo_estacionamiento)
        S->>S: costo_total, pagado=True, lista_para_salir=True
        S-->>P: QR de salida
        C->>S: Escanea QR de salida
        S->>S: Finaliza sesion
    else Mercado Pago
        S->>MP: Crea preferencia de pago
        MP-->>C: Link de pago
        C->>MP: Paga con tarjeta de prueba
        MP->>S: Webhook POST /api/mercadopago/webhook
        S->>S: costo_total, lista_para_salir=True
        C->>S: Escanea QR de salida
        S->>S: Finaliza sesion
    end
```

## Flujo de reservas y penalizaciones

```mermaid
sequenceDiagram
    participant C as Conductor
    participant S as Sistema
    participant P as Permisionario
    
    C->>S: Solicita reserva (espacio, hora_inicio, hora_fin)
    S->>P: Reserva pendiente
    alt Aprueba
        P->>S: POST /api/reservas/aprobar
        S->>S: estado=aprobada
        Note over C: Llega la hora de la reserva
        alt Hace check-in (>5 min tarde)
            C->>S: Check-in en espacio reservado
            S->>S: Compara diff con hora_inicio
            S->>S: Penaliza: 10% de $600 = $60
            S->>C: Check-in exitoso + penalizacion
        else Hace check-in (a tiempo)
            C->>S: Check-in en espacio reservado
            S->>S: Todo ok
        else No se presenta
            S->>S: Tarea no_show (cada 60s) detecta
            S->>S: Penaliza: $60
            S->>S: reserva.usada=True, estado=rechazada
        end
    else Rechaza
        P->>S: POST /api/reservas/aprobar(aprobar=false)
        S->>S: estado=rechazada
    end
```

## Flujo de bloqueo

```mermaid
flowchart TD
    A[Conductor activo] --> B{Penalizaciones<br/>del mes >= 5?}
    B -->|Sí| C[Bloqueado]
    B -->|No| D{Deuda >= $10,000?}
    D -->|Sí| C
    D -->|No| E{Sesión activa<br/>verifica en cada<br/>operación?}
    E -->|ok| F[Sin cambios]
    C --> G[Admin desbloquea<br/>o conductor paga $5,000]
    G --> A
```

## Tarifas y horarios

```mermaid
flowchart LR
    A[Calcular costo] --> B{Es domingo?}
    B -->|Sí| C[Gratis]
    B -->|No| D{Es sábado?}
    D -->|Sí, antes 14hs| E[Cobrar $600/h]
    D -->|Sí, después 14hs| F[Gratis hasta el lunes]
    D -->|No, lun-vie| G{Está entre 7 y 21hs?}
    G -->|Sí| E
    G -->|No| H[Gratis hasta las 7am]
    
    E --> I[Acumular al total]
```

## Stack detallado

| Componente | Tecnología | Versión | Rol |
|------------|-----------|---------|-----|
| Backend | FastAPI | 0.115+ | Servidor ASGI con tipado fuerte |
| ORM | SQLAlchemy | 2.0+ | Async, sesiones por request |
| DB | SQLite | 3.x | Archivo único, sin servidor |
| Auth | python-jose + bcrypt | — | JWT HS256, 24hs expiración |
| QR | qrcode (PIL) | — | Generación server-side |
| Pagos | mercadopago | SDK | Sandbox con webhook |
| Frontend | Jinja2 + CSS | — | Server-rendered, forced dark |
| Mapas | Leaflet | 1.9 | OSM tiles + MarkerCluster |
| Mobile | Expo + WebView | 52 | Web wrapper + QR nativo |
| Tunnel | cloudflared | — | Exposición gratuita |

## Archivos clave

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `app/main.py` | 1297 | Rutas API + HTML + lógica de negocio |
| `app/models.py` | 114 | 7 modelos SQLAlchemy |
| `app/schemas.py` | 133 | Schemas Pydantic de entrada/salida |
| `app/idemsa_data.py` | 221 | Sincronización GIS IDEMSA |
| `app/mapa_data.py` | 268 | Calles del centro (mapa offline) |
| `app/auth.py` | 34 | JWT + bcrypt helpers |
| `seed.py` | 67 | Datos de prueba |
