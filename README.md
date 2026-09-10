# YGG - Análisis de partidas de League of Legends

## ¿Qué es YGG?

YGG es una plataforma de scouting competitivo para League of Legends. Permite registrar jugadores, generar análisis históricos de partidas mediante snapshots y consultar métricas avanzadas para mejorar la evaluación de rendimiento.

El proyecto combina un backend en **FastAPI** y un frontend en **Flutter** para ofrecer una experiencia multiplataforma.

## Componentes principales

### Backend
- Autenticación con roles (`user` / `admin`).
- CRUD de jugadores y jugadores asociados a cada usuario.
- Creación de snapshots de partidas en segundo plano.
- Integración con la **Riot Games API** y **Data Dragon**.
- Persistencia en PostgreSQL.

### Frontend
- Interfaz multiplataforma (web, desktop y móvil).
- Gestión de estado con **Riverpod**.
- Cliente HTTP con **Dio** e interceptores JWT.
- Visualización de historial, campeones más jugados y métricas por snapshot.

## Arquitectura

El proyecto se divide en dos capas principales:

- **Frontend:** cliente Flutter que consume la API.
- **Backend:** servidor FastAPI que procesa datos y almacena resultados.

Para una vista completa de la arquitectura, revisa `architecture.md`.

## Instalación

### Backend

#### Requisitos
- Python 3.12+
- PostgreSQL
- Opcional: Poetry

#### Pasos

```bash
cd backend
```

Con Poetry:

```bash
poetry install
poetry shell
```

Con pip:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Configura `.env` en `backend/` con:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ygg
RIOT_API_KEY=tu_clave_de_riot
SECRET_KEY=una_clave_segura
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Ejecuta las migraciones:

```bash
alembic upgrade head
```

Inicia el servidor:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

#### Requisitos
- Flutter SDK
- Editor compatible con Flutter

#### Pasos

```bash
cd frontend
flutter pub get
flutter run -d chrome
```

## Endpoints clave

- `POST /auth/register` — registrar usuario
- `POST /auth/login` — iniciar sesión
- `GET /auth/me` — perfil autenticado
- `GET /players/` — listar jugadores
- `POST /players/` — crear jugador
- `GET /players/{id}` — ver jugador
- `PUT /players/{id}` — actualizar jugador
- `POST /players/{id}/refresh` — refrescar datos
- `GET /matches/player/{id}` — partidas de jugador
- `POST /snapshots/` — crear snapshot
- `GET /snapshots/player/{id}` — listar snapshots
- `GET /snapshots/jobs/{job_id}` — progreso de job
- `GET /ddragon/version` — versión de Data Dragon
- `GET /ddragon/spells` — hechizos de invocador

### Administración

- `GET /admin/users/` — listar usuarios
- `PATCH /admin/users/{id}/role` — cambiar rol
- `PATCH /admin/users/{id}/active` — activar/desactivar usuario
- `POST /admin/users/` — crear usuario admin
- `GET /admin/stats/` — estadísticas globales

## Uso rápido con curl

Registrar:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"usuario","password":"password123"}'
```

Iniciar sesión:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

Usar token:

```bash
curl -X GET http://localhost:8000/players/ \
  -H "Authorization: Bearer TU_TOKEN"
```

## Notas de arquitectura

- Los snapshots se ejecutan en background con `asyncio.create_task`.
- El backend usa la tabla `jobs` para seguir el progreso.
- El frontend realiza polling hasta que el análisis se completa.

## Futuras mejoras

- Cola de tareas con **Redis + Celery/RQ**.
- Notificaciones en tiempo real con **WebSockets**.
- Caché distribuida para reducir llamadas a Riot.
- Rate limiting para proteger endpoints.
- Monitorización de rendimiento.

## Licencia

MIT.
