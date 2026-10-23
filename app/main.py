import os
import logging
import math
from contextlib import asynccontextmanager
from datetime import date
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from . import models, auth
from .services import comunicaciones
from .services.analitica import router as analitica_router
from .services.mensajes import adaptar_sms, extraer_adaptacion, AdaptacionInvalida, SMS_INSTRUCCION
from .services.configuracion import estado_proveedores
from .services.diagnostico_groq import estructura_respuesta
from .twilio_webhook import router as twilio_router
from .database import get_db, engine, Base
from .schema import validar_esquema
from openai import AsyncOpenAI
import joblib
import pandas as pd

from .ml.features import extraer_features_cliente, FEATURE_COLUMNS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    validar_esquema(engine)
    yield
    if client is not None:
        await client.close()


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

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = (
    AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1",
                timeout=20.0, max_retries=0)
    if GROQ_API_KEY and GROQ_API_KEY.strip() else None
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml", "risk_model.joblib")
_modelo_riesgo = None
_columnas_modelo = FEATURE_COLUMNS

if os.path.exists(MODEL_PATH):
    _bundle = joblib.load(MODEL_PATH)
    _modelo_riesgo = _bundle["modelo"]
    _columnas_modelo = _bundle["columnas"]
    print("✅ Modelo de riesgo cargado correctamente.")
else:
    print("⚠️  No se encontró app/ml/risk_model.joblib. Corre 'python -m app.ml.train_model'.")


# ============ AUTENTICACIÓN ============

@app.get("/auth/me")
def whoami(user: dict = Depends(auth.get_entra_user)):
    return user


# ============ ENDPOINTS PROTEGIDOS (requieren sesión) ============

def recalcular_riesgo(db, cliente):
    features = extraer_features_cliente(db, cliente)
    if features["monto_pendiente_actual"] <= 0:
        cliente.score_riesgo = None
        cliente.probabilidad_pago_a_tiempo = None
        cliente.segmento = "Sin deuda"
        return {"features_usadas": features, "saldo_pendiente": 0,
                "sin_deuda_activa": True, "probabilidad_pago_a_tiempo": None,
                "score_riesgo": None, "segmento": "Sin deuda"}
    if _modelo_riesgo is None:
        raise HTTPException(503, "El modelo de riesgo no está entrenado. Corre 'python -m app.ml.train_model'.")
    frame = pd.DataFrame([features])[_columnas_modelo]
    probabilidad = float(_modelo_riesgo.predict_proba(frame)[0][1])
    cliente.probabilidad_pago_a_tiempo = round(probabilidad, 3)
    cliente.score_riesgo = round(1 - probabilidad, 3)
    cliente.segmento = ("Alto riesgo" if cliente.score_riesgo >= .66 else
                        "Riesgo medio" if cliente.score_riesgo >= .33 else "Bajo riesgo")
    return {"features_usadas": features, "sin_deuda_activa": False,
            "saldo_pendiente": features["monto_pendiente_actual"],
            "probabilidad_pago_a_tiempo": cliente.probabilidad_pago_a_tiempo,
            "score_riesgo": cliente.score_riesgo, "segmento": cliente.segmento}


def estado_deuda(deuda):
    if deuda.saldo_pendiente <= 0:
        return "Pagada"
    if deuda.fecha_vencimiento and deuda.fecha_vencimiento < date.today():
        return "En Mora"
    return "Pendiente"


def deuda_dict(d):
    dias = (d.fecha_vencimiento - date.today()).days if d.fecha_vencimiento else None
    return {"id": d.id, "monto_original": d.monto_total,
            "saldo_pendiente": d.saldo_pendiente, "fecha_vencimiento": d.fecha_vencimiento,
            "estatus": estado_deuda(d), "dias_restantes": dias,
            "dias_atraso": max(0, -dias) if dias is not None and d.saldo_pendiente > 0 else 0}


def pago_dict(p):
    return {"id": p.id, "deuda_id": p.deuda_id, "fecha_pago": p.fecha_pago,
            "monto": p.monto, "dias_atraso": p.dias_atraso}


def resumen_cliente(c):
    activas = [d for d in c.deudas if d.saldo_pendiente > 0]
    saldo = sum(d.saldo_pendiente for d in activas)
    fecha = min((d.fecha_vencimiento for d in activas if d.fecha_vencimiento), default=None)
    return {"cliente_id": c.id, "folio": f"CL-{c.id:06d}", "cliente_nombre": c.nombre,
            "monto_pendiente": saldo, "saldo_pendiente": saldo, "sin_deuda_activa": saldo <= 0,
            "estado_deuda": "Sin deuda activa" if saldo <= 0 else "En Mora" if any(estado_deuda(d) == "En Mora" for d in activas) else "Pendiente",
            "score_riesgo": c.score_riesgo if saldo > 0 else None,
            "segmento": c.segmento if saldo > 0 else "Sin deuda",
            "probabilidad_pago_a_tiempo": c.probabilidad_pago_a_tiempo if saldo > 0 else None,
            "prioridad": round((c.score_riesgo or 0) * saldo, 2),
            "fecha_vencimiento": fecha,
            "dias_restantes": (fecha - date.today()).days if fecha else None}


def evaluacion_riesgo_completa(cliente):
    """Vigencia disponible sin timestamps/versionado: campos completos y válidos."""
    p, score = cliente.probabilidad_pago_a_tiempo, cliente.score_riesgo
    return (p is not None and score is not None
            and math.isfinite(p) and math.isfinite(score)
            and 0 <= p <= 1 and 0 <= score <= 1
            and abs(p + score - 1) <= .001
            and cliente.segmento in ("Bajo riesgo", "Riesgo medio", "Alto riesgo"))


from .routers import clientes, pagos, comunicaciones as comunicaciones_router, ia  # noqa: E402
app.include_router(clientes.router)
app.include_router(pagos.router)
app.include_router(comunicaciones_router.router)
app.include_router(ia.router)
