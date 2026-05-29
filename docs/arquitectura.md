# Arquitectura del sistema

## Diagrama de componentes

```mermaid
graph TB
    subgraph Cliente
        EXP[App Expo<br/>WebView + QR nativo]
        NAV[Browser<br/>Jinja2 templates]
        PWA[Service Worker<br/>offline cache]
    end

    subgraph "Cloudflare Tunnel"
        CF[URL pública gratuita]
    end

    subgraph "FastAPI Backend"
        AUTH[auth_routes.py<br/>JWT login + register + verify]
        API[main.py<br/>2368 líneas — 80+ endpoints]
        QR[qr_utils.py<br/>Generación QR]
        MP[mercado_pago.py<br/>MP integration / simulado]
        IDEMSA[idemsa_data.py<br/>Sync GIS]
    end

    subgraph "Base de datos"
        DB[(SQLite<br/>estacionamiento.db<br/>12 tablas)]
    end

    subgraph "Externo"
        MPAPI[Mercado Pago<br/>Sandbox API]
        IDEMSA_MAP[IDEMSA<br/>Visor GIS iframe]
    end

    EXP --> CF
    NAV --> CF
    CF --> API
    NAV --> API
    PWA --> CF
    API --> AUTH
    API --> QR
    API --> MP
    API --> IDEMSA
    API --> DB
    MP --> MPAPI
    NAV --> IDEMSA_MAP
```

## Modelo de datos (ERD)

```mermaid
erDiagram
    CONDUCTOR ||--o{ SESION : realiza
    CONDUCTOR ||--o{ VEHICULO : tiene
    CONDUCTOR ||--o{ DEUDA : acumula
    VEHICULO ||--o{ SESION : usa
    PERMISIONARIO ||--o{ MANO : tiene
    MANO ||--o{ ESPACIO : agrupa
    ESPACIO ||--o{ SESION : registra
    SESION ||--o| PAGO : genera
    CONDUCTOR {
        int id PK
        string dni UK
        string nombre
        string apellido
        string email UK
        string telefono
        string password_hash
        bool email_verified
        bool bloqueado
        datetime bloqueado_hasta
        float saldo_deudor
        enum exencion
    }
    VEHICULO {
        int id PK
        int conductor_id FK
        string patente
        enum tipo
        string marca
        string modelo
        int anio
        bool predeterminado
    }
    PERMISIONARIO {
        int id PK
        string codigo UK
        string nombre
        string apellido
        string dni UK
        string email UK
        string telefono
        string password_hash
        bool activo
    }
    MANO {
        int id PK
        int permisionario_id FK
        string calle
        int altura_desde
        int altura_hasta
        enum lado
        float lat
        float lng
    }
    ESPACIO {
        int id PK
        int mano_id FK
        int numero
        string ubicacion
        float precio_por_hora
        bool disponible
        float lat
        float lng
        string tipo
        int permisionario_id FK
    }
    SESION {
        int id PK
        int espacio_id FK
        int conductor_id FK
        int vehiculo_id FK
        int permisionario_id FK
        datetime hora_inicio
        datetime hora_fin
        float costo_total
        bool pagado
        enum metodo_pago
        enum metodo_ingreso
        enum exencion
        enum estado
        string pago_id
    }
    PAGO {
        int id PK
        int sesion_id FK
        float monto
        enum metodo
        string mp_preference_id
        string mp_status
        bool confirmado
    }
    DEUDA {
        int id PK
        int conductor_id FK
        int sesion_id FK
        float monto
        bool pagada
        int reported_by FK
        string motivo
    }
    GESTOR {
        int id PK
        string nombre
        string apellido
        string dni UK
        string email UK
        string username UK
        string password_hash
        string permisos
        bool activo
    }
    ADMIN {
        int id PK
        string nombre
        string username UK
        string password_hash
    }
    EMAIL_VERIFICATION {
        int id PK
        string email
        string code
        bool verified
        datetime expires_at
    }
```

## Relaciones clave

- **Permisionario ↔ Espacios**: a través de `Mano`. El permisionario tiene una o más manos (calle + rango de altura + lado). Los espacios se filtran por `ubicacion.startswith(mano.calle)` y rango de `numero`.
- **Espacios IDEMSA**: ~6,974 espacios sincronizados desde el visor GIS oficial de IDEMSA. Grid de ~7m entre puntos. Sin distinción par/impar (IDEMSA usa block-level).
- **Sesión**: el costo se calcula en tiempo real según `calcular_costo_estacionamiento(inicio, ahora, tipo, exencion)`.
- **Vehículos compartidos**: no hay validación de dueño — cualquier conductor puede usar cualquier vehículo.

## Flujo de búsqueda de estacionamiento

```mermaid
flowchart TD
    A[Conductor en /buscar] --> B{Como busca?}
    B -->|Texto| C[Ingresa calle + altura<br/>ej: GENERAL GUEMES 150]
    B -->|GPS| D[Presiona Buscar ahora]
    D --> E[Navegador pide ubicacion]
    E --> F[Obtiene lat + lng]
    C --> G[Nominatim geocodifica]
    G --> H[Coordenadas]
    F --> H
    H --> I{Esta en el centro<br/>(<5km del microcentro)?}
    I -->|No| J[Buscador IDEMSA por nombre de calle]
    I -->|Si| K[Busca espacios IDEMSA en radio]
    K --> L[Filtra solo estacionamiento_medido]
    L --> M[Calcula distancia a cada espacio]
    M --> N[Ordena por distancia + top 10]
    N --> O[Agrupa por bloques<br/>calle + altura]
    O --> P[Devuelve bloques con<br/>disponibles y distancia]
    J --> K
```

## Flujo de registro y login

```mermaid
sequenceDiagram
    participant C as Conductor
    participant S as Sistema
    C->>S: POST /api/auth/register/conductor
    S->>S: Crea Conductor + Vehiculo (email_verified=False)
    S->>S: Genera UUID token, guarda EmailVerification
    S-->>C: "Revisá tu email" + link impreso en terminal
    C->>S: GET /api/auth/verify-email?token=<uuid>
    S->>S: Marca email_verified=True
    S-->>C: Página HTML "Email verificado correctamente"
    C->>S: POST /api/auth/login (dni + password)
    S->>S: Verifica email_verified, genera JWT
    S-->>C: Token + role + user_id
```

## Flujo del permisionario

```mermaid
flowchart TD
    A[Login PER30456789 / 1234] --> B[Panel principal]
    B --> C{Opcion}
    C -->|Sesiones activas| D[Ver tarjetas con timer+costo]
    D --> E[Tarjeta muestra: patente, tipo, exencion, tarifa, costo estimado]
    E --> F[Ir a Salida]
    F --> G[Seleccionar sesion + metodo pago]
    G --> H{Efectivo o MP?}
    H -->|Efectivo| I[Finaliza sesion inmediato]
    H -->|MP| J[Sesion queda activa con hora_fin + costo bloqueado]
    J --> K[Conductor confirma pago MP]
    K --> L[Finaliza sesion]
    I --> M[Espacio liberado]
    L --> M
    C -->|Ingreso manual| N[Ingresar patente]
    N --> O{Busca vehiculo en DB?}
    O -->|Existe| P[Crea sesion con conductor existente]
    O -->|No existe| Q[Crea conductor guest + vehiculo]
    Q --> P
    C -->|QR| R[Muestra QR de la cuadra]
    R --> S[QR apunta a /estacionar?perm={id}]
    C -->|Cuadra| T[Muestra calles asignadas]
    T --> U[Calle + altura_desde + altura_hasta + lado]
    C -->|Espacios| V[Mapa con espacios coloreados]
    V --> W[Verde = libre, Rojo = ocupado]
```

## Flujo de sincronización IDEMSA

```mermaid
flowchart LR
    A[Inicio servidor] --> B[sync_espacios_db]
    B --> C[Lee archivo JS estacionamiento_mar25.js]
    C --> D[Parsea segmentos viales]
    D --> E[Genera grid de ~7m por segmento]
    E --> F[Calcula altura aprox por interpolacion]
    F --> G[Guarda en DB: ubicacion, lat, lng, tipo, numero]
    G --> H[~6974 espacios en tabla espacios]
    H --> I[Permisionarios filtran por calle + rango altura]
```

## Flujo de check-in / check-out

```mermaid
sequenceDiagram
    participant C as Conductor
    participant S as Sistema
    participant MP as Mercado Pago
    participant P as Permisionario

    Note over C: Busca estacionamiento
    C->>S: POST /api/buscar-estacionamiento (texto o GPS)
    S-->>C: Bloques disponibles con distancias

    Note over C: Check-in por QR de permisionario
    C->>S: POST /api/conductor/checkin (permisionario_id)
    S->>S: Busca espacio, crea sesion activa
    S-->>C: sesion_id + qr_salida

    Note over C: Timer activo con costo estimado
    C->>S: GET /api/conductor/sesion-activa
    S-->>C: hora_inicio, costo_estimado, tarifa_por_hora, es_gratuito

    Note over C: Elige metodo de pago
    C->>S: POST /api/conductor/elegir-pago/{id}
    S-->>C: costo_total, init_point (si MP)

    alt Efectivo
        P->>S: POST /api/permisionario/salida (metodo_pago=efectivo)
        S->>S: Calcula costo, finaliza sesion, libera espacio
        S-->>P: ok
    else Mercado Pago
        P->>S: POST /api/permisionario/salida (metodo_pago=mercadopago)
        S->>S: Bloquea costo, NO finaliza sesion
        S-->>P: costo_total, init_point
        C->>S: GET /conductor/pago-mercadopago/{id}
        S-->>C: Pagina MP simulada
        C->>S: POST /api/conductor/pago-mercadopago/{id}/confirmar
        S->>S: Finaliza sesion, libera espacio
        S-->>C: ok, costo
    end
```

## Flujo de salida (conductor no finaliza)

```mermaid
flowchart TD
    A[Conductor en checkout] --> B{Metodo de pago?}
    B -->|Efectivo| C[Permisionario procesa salida]
    B -->|Mercado Pago| D[Permisionario procesa salida con MP]
    C --> E[Sesion finalizada<br/>espacio liberado]
    D --> F[Sesion sigue activa<br/>hora_fin y costo bloqueados]
    F --> G[Conductor paga en MP simulado]
    G --> H[POST /api/conductor/pago-mercadopago/{id}/confirmar]
    H --> E
```

## Flujo de bloqueo

```mermaid
flowchart TD
    A[Conductor activo] --> B{Saldo deudor<br/>>= $10,000?}
    B -->|Sí| C[Bloqueado automático]
    B -->|No| D[Sin cambios]
    C --> E{Pagar deuda<br/>o admin desbloquea}
    E -->|Paga| F[Saldo_deudor = 0<br/>bloqueado = False]
    E -->|Admin| F
```

## Tarifas y horarios

```mermaid
flowchart LR
    A[Calcular costo] --> B{Tipo vehiculo?}
    B -->|Bicicleta| C[Gratis]
    B -->|Auto/Camioneta/Moto| D{Exencion activa?}
    D -->|Discapacidad, Frentista, Veterano| C
    D -->|Ninguna| E{Es domingo?}
    E -->|Sí| C
    E -->|No| F{Es sabado?}
    F -->|Sí, antes 14hs| G[Cobrar segun tipo]
    F -->|Sí, despues 14hs| H[Gratis hasta el lunes]
    F -->|No, lun-vie| I{Entre 7 y 21hs?}
    I -->|Sí| G
    I -->|No| J{Entre 22 y 5hs?}
    J -->|Sí| G
    J -->|No| K[Gratis hasta prox inicio]

    G --> L[Auto/Camioneta: $600/h<br/>Moto: $100/h]
```

## Stack detallado

| Componente | Tecnología | Versión | Rol |
|------------|-----------|---------|-----|
| Backend | FastAPI | 0.115+ | Servidor ASGI con tipado fuerte |
| ORM | SQLAlchemy | 2.0+ | Async, sesiones por request |
| DB | SQLite | 3.x | Archivo único, sin servidor |
| Auth | python-jose + bcrypt | — | JWT HS256, 24hs expiración |
| QR | qrcode (PIL) | — | Generación server-side |
| Pagos | mercadopago SDK | — | Sandbox con fallback simulado |
| Frontend | Jinja2 + CSS | — | Server-rendered, mobile-first |
| Mapas | IDEMSA iframe + Leaflet | — | Embed GIS + capas offline |
| PWA | Service Worker | — | Cache-first static, network-first API |
| Mobile | Expo + WebView | 52 | Web wrapper + QR nativo |
| Tunnel | cloudflared | — | Exposición gratuita |

## Archivos clave

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `app/main.py` | 2368 | Rutas API + HTML + lógica de negocio |
| `app/models.py` | 238 | 10 modelos SQLAlchemy |
| `app/schemas.py` | — | Schemas Pydantic de entrada/salida |
| `app/idemsa_data.py` | — | Sincronización GIS IDEMSA |
| `app/auth_routes.py` | 144 | Login + registro + verificación email |
| `auth.py` | 34 | JWT + bcrypt helpers |
| `seed.py` | 147 | Datos de prueba |
