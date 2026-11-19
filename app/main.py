"""Punto de entrada: una sola app en Railway que sirve
  - la landing de temporada  ->  /
  - la API del formulario    ->  /api/...
  - el servidor MCP          ->  MCP_PATH (por defecto /mcp)
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import landing
from .db import init_db
from .mcp_server import mcp

BASE = Path(__file__).resolve().parent.parent

# Ruta del MCP configurable por variable de entorno (permite una ruta difícil de adivinar).
MCP_PATH = "/" + os.getenv("MCP_PATH", "mcp").strip("/")

mcp_app = mcp.http_app(path=MCP_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    async with mcp_app.lifespan(app):  # FastMCP necesita su propio ciclo de vida
        yield


app = FastAPI(title="El Fogón de Doña Tere", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(landing.router)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
# Al final: todo lo que no coincidió arriba lo atiende la app MCP (solo responde en MCP_PATH)
app.mount("/", mcp_app)
