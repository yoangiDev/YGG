import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.db.models  # noqa: F401  (registra todos los modelos ORM)
from app.auth.router import router as auth_router
from app.core.config import settings
from app.routers.admin import router as admin_router
from app.routers.ddragon import router as ddragon_router
from app.routers.league import router as league_router
from app.routers.matches import router as matches_router
from app.routers.players import router as players_router
from app.routers.snapshots import router as snapshots_router

# El esquema lo gestiona exclusivamente Alembic (`alembic upgrade head`).
app = FastAPI(
    title="YGG API",
    description="API para análisis de partidas de League of Legends",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(players_router)
app.include_router(matches_router)
app.include_router(snapshots_router)
app.include_router(ddragon_router)
app.include_router(admin_router)
app.include_router(league_router)

# Asegurar que el directorio de datos estáticos existe antes de montarlo
os.makedirs("./data/ddragon", exist_ok=True)
app.mount("/static/ddragon", StaticFiles(directory="./data/ddragon"), name="ddragon_static")


@app.get("/")
def root():
    return {"message": "YGG API", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
