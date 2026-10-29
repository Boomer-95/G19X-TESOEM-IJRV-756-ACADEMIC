import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from . import models, auth  # noqa: F401
from .database import get_db, engine, Base  # noqa: F401
from .routers import clientes, pagos, comunicaciones as comunicaciones_router, ia
from .schema import validar_esquema
from .services.analitica import router as analitica_router
from .services.groq import close_client
from .twilio_webhook import router as twilio_router


@asynccontextmanager
async def lifespan(app):
    validar_esquema(engine)
    yield
    await close_client()


app = FastAPI(title="Motor Inteligente de Cobranza PluriOne API", lifespan=lifespan)
app.include_router(twilio_router)
app.include_router(analitica_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
    ).split(",") if origin.strip() and origin.strip() != "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ AUTENTICACIÓN ============

@app.get("/auth/me")
def whoami(user: dict = Depends(auth.get_entra_user)):
    return user


# ============ ENDPOINTS PROTEGIDOS (requieren sesión) ============

app.include_router(clientes.router)
app.include_router(pagos.router)
app.include_router(comunicaciones_router.router)
app.include_router(ia.router)
