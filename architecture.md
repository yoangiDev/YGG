# Arquitectura de YGG

## Visión general

YGG se organiza en dos capas principales:

- **Frontend Flutter:** cliente multiplataforma que consume la API.
- **Backend FastAPI:** servidor que procesa datos, orquesta análisis y persiste resultados.

La comunicación entre ambas capas es por **HTTP/REST**. El backend también integra servicios externos como Riot API y Data Dragon, además de PostgreSQL como base de datos principal.

## Diagrama de alto nivel

```text
Flutter App
  +- Pantallas / Screens
  +- Providers (Riverpod)
  +- Cliente Dio
        ¦
        ?
FastAPI Backend
  +- Routers / Endpoints
  +- Auth / JWT
  +- Servicios Externos
  ¦   +- Riot Client
  ¦   +- Data Dragon
  ¦   +- Stats Runner
  +- CRUD / Repositorios
  +- Sesiones SQLAlchemy
        ¦
        ?
    PostgreSQL
```

## Backend: capas y responsabilidades

### 1. Rutas y entrada de datos

`app/routers/` define los endpoints de la aplicación:

- `auth/` — autenticación y registro.
- `players/` — gestión de jugadores.
- `matches/` — histórico de partidas.
- `snapshots/` — creación y consulta de snapshots.
- `ddragon/` — recursos de Data Dragon.
- `admin/` — administración y estadísticas globales.

Estas rutas reciben peticiones, validan datos con **Pydantic** y llaman a la lógica de negocio correspondiente.

### 2. Autenticación y autorización

`app/auth/` se encarga de:

- la generación y verificación de JWT.
- la validación de usuarios activos.
- el control de acceso por roles.

El flujo de seguridad es:

1. El usuario inicia sesión con email/contraseña.
2. El backend valida el hash con `bcrypt`.
3. Se emite un token JWT firmado.
4. El cliente lo guarda y lo envía en `Authorization`.
5. El backend valida el token y el rol en cada petición.

### 3. Servicios externos

`app/service/` contiene la integración con APIs externas y la lógica de análisis:

- `riot_client.py`: descarga de partidas, timelines, datos de liga y summoner.
- `ddragon_client.py`: consulta y cache local de datos estáticos.
- `http_client.py`: configuración de sesiones HTTP asíncronas.
- `stats_runner.py`: orquestación de la creación de snapshots.

#### RiotAPIClient

- controla la concurrencia para no exceder límites de Riot.
- maneja reintentos en `429` respetando `Retry-After`.
- normaliza campeones, runas, roles y regiones.
- obtiene timelines para métricas avanzadas.

#### Data Dragon

- almacena localmente los JSON de Riot.
- permite mapear IDs de objetos, runas y hechizos.
- reduce llamadas repetidas a Riot.

### 4. Capa de datos

Los modelos SQLAlchemy están en `app/db/models/` y las migraciones se administran con Alembic.

Estructura principal:

- `user.py` — usuarios.
- `player.py` — jugadores.
- `snapshot.py` — snapshots.
- `match.py` — datos de partidas.
- `job.py` — estados de procesos.

#### Relaciones clave

- Un `User` puede tener muchos `Player`.
- Un `Player` puede tener muchos `Snapshot`.
- Un `Snapshot` puede estar vinculado a muchas `Match`.

## Métricas y datos calculados

YGG calcula métricas derivadas de la partida y del timeline para enriquecer cada match.

- **Daño y combate:** KDA, participación de equipo, daño a estructuras.
- **Diferenciales de línea:** CS, oro y experiencia en minutos clave.
- **Métricas tácticas:** kills en solitario, wards, control de visión y objetivos.
- **Eventos espaciales:** muertes y guardianes con coordenadas para mapas de calor.

## Frontend: arquitectura por características

La carpeta `frontend/lib/` está estructurada en:

- `core/` — configuración global y utilidades.
- `features/` — módulos independientes por dominio.
- `screens/` — pantallas completas.

Esto permite separar la lógica de negocio, los providers y los widgets según la funcionalidad.

### Componentes principales

- `core/api/`: cliente Dio e interceptores JWT.
- `core/auth/`: estado de autenticación y sesión.
- `core/theme/`: estilos y colores.
- `features/admin/`: panel de administración.
- `features/players/`: gestión de jugadores, matches y snapshots.

## Flujo de creación de snapshots

El proceso de snapshot está diseñado como job asíncrono para no bloquear la API:

1. El frontend llama a `POST /snapshots/`.
2. El backend crea un registro en `jobs` con `processing`.
3. Se ejecuta `asyncio.create_task(...)` para procesar el snapshot en segundo plano.
4. Se descargan partidas y timelines desde Riot.
5. Se calculan métricas y se almacenan en PostgreSQL.
6. El frontend consulta `GET /snapshots/jobs/{job_id}`.
7. Cuando el job termina, el snapshot se muestra al usuario.

## Seguridad y limitaciones

### Seguridad

- Contraseñas cifradas con `bcrypt`.
- JWT firmado con `HS256`.
- Control de acceso por roles y estado del usuario.

### Limitaciones actuales

- Los trabajos de snapshot se ejecutan en el proceso de FastAPI.
- Si el servidor se reinicia, los jobs en curso pueden perderse.
- No hay rate limiting global.

### Mejoras recomendadas

- Migrar a cola de tareas con **Redis + Celery/RQ**.
- Sustituir polling por **WebSockets**.
- Añadir caché distribuida para la Riot API.
- Incorporar monitorización de rendimiento.
