import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db.base import Base
from app.db.session import engine
from app.db.models.user import User
from app.db.models.player import Player
from app.db.models.match import Match
from app.db.models.snapshot import Snapshot
from app.db.models.job import Job
from app.db.models.rank_cutoff import RankCutoff

from app.auth.router import router as auth_router
from app.routers.players import router as players_router
from app.routers.matches import router as matches_router
from app.routers.snapshots import router as snapshots_router
from app.routers.ddragon import router as ddragon_router
from app.routers.admin import router as admin_router
from app.routers.league import router as league_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="YGG API",
    description="API para análisis de partidas de League of Legends",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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