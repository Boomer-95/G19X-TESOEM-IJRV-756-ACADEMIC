import json
import logging
import os
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from .. import main, models, auth
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["comunicaciones"])


class ComunicacionNueva(BaseModel):
    cliente_id: int = Field(gt=0)
    estrategia_id: int | None = Field(default=None, gt=0)
    canal: Literal["Email", "SMS", "WhatsApp", "Llamada"]
    mensaje: str = Field(min_length=1, max_length=10000)

    @field_validator("mensaje")
    @classmethod
    def mensaje_no_vacio(cls, value):
        if not value.strip():
            raise ValueError("El mensaje no puede estar vacío")
        return value


@router.post("/api/comunicaciones", status_code=201)
async def registrar_comunicacion(
    datos: ComunicacionNueva,
    db: Session = Depends(get_db),
    user: dict = Depends(auth.get_entra_user),
):
    cliente = db.get(models.Cliente, datos.cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    if datos.estrategia_id is not None:
        estrategia = db.get(models.HistorialMensaje, datos.estrategia_id)
        if estrategia is None or estrategia.cliente_id != cliente.id:
            raise HTTPException(422, "La estrategia debe pertenecer al cliente de la comunicación.")
    mensaje_envio = datos.mensaje

    # La protección de cobranza también se aplica a llamadas directas a la API.
    if main.resumen_cliente(cliente)["sin_deuda_activa"]:
        raise HTTPException(409, "El cliente no tiene deuda activa; no se requiere comunicación de cobranza.")

    # Solo SMS y Llamada requieren una versión corta.
    # Email y WhatsApp conservan exactamente el mensaje original.
    if datos.canal in ("SMS", "Llamada"):
        if main.client is None:
            raise HTTPException(503, "Servicio de IA no configurado.")

        if datos.canal == "SMS":
            instruccion = main.SMS_INSTRUCCION
            # Tokens no equivalen a caracteres: dejar margen de generación y
            # aplicar el límite SMS sobre el texto utilizable normalizado, aun
            # cuando el proveedor termine por length. Sin aumentar el presupuesto.
            max_tokens = 256
            mensaje_usuario = (
                "Devuelve solo la linea SMS derivada de este texto:\n"
                "<mensaje_original>\n" + datos.mensaje + "\n</mensaje_original>"
            )
        else:
            instruccion = (
                "Convierte el siguiente mensaje de cobranza en un mensaje breve "
                "y natural para ser leído durante una llamada telefónica. "
                "Conserva únicamente la información esencial. "
                "Debe ser profesional, respetuoso y no amenazante. "
                "No inventes información. "
                "No agregues explicaciones ni comillas. "
                "Devuelve exclusivamente el mensaje."
            )
            max_tokens = 150
            mensaje_usuario = datos.mensaje

        modelo_adaptacion = (
            os.getenv("GROQ_SMS_MODEL", "qwen/qwen3.8-27b") if datos.canal == "SMS"
            else os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        )
        # Qwen 3.8 admite none (instruct). GPT-OSS solo admite low/medium/high.
        # La política SMS no altera estrategias ni adaptación de voz.
        opciones_razonamiento = (
            {"reasoning_effort": "none"}
            if datos.canal == "SMS" and modelo_adaptacion == "qwen/qwen3.8-27b"
            else {"reasoning_effort": "low"}
            if datos.canal == "SMS" and modelo_adaptacion in
            {"openai/gpt-oss-20b", "openai/gpt-oss-120b"} else {}
        )
        try:
            respuesta = await main.client.chat.completions.create(
                model=modelo_adaptacion,
                messages=[
                    {"role": "system", "content": instruccion},
                    {"role": "user", "content": mensaje_usuario},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
                **opciones_razonamiento,
            )

        except APIError as exc:
            if isinstance(exc, APITimeoutError):
                categoria = 'Timeout'
            elif isinstance(exc, APIConnectionError):
                categoria = 'ConnectionError'
            elif isinstance(exc, APIStatusError):
                categoria = {400: 'BadRequest', 401: 'AuthenticationFailed',
                             403: 'PermissionDenied', 404: 'ModelNotFound',
                             429: 'RateLimited'}.get(exc.status_code, 'ProviderHttpError')
            else:
                categoria = 'ProviderError'
            main.logger.warning('GroqGenerationFailed canal=%s reason=%s', datos.canal, categoria)
            raise HTTPException(502, f"No se pudo generar el mensaje corto para {datos.canal}.") from None
        except Exception:
            # Frontera del cliente externo; no confundir errores de red/SDK
            # con validación local ni registrar excepciones que puedan tener secretos.
            main.logger.error('GroqGenerationFailed canal=%s reason=UnexpectedClientError', datos.canal)
            raise HTTPException(502, f"No se pudo generar el mensaje corto para {datos.canal}.") from None

        try:
            if datos.canal == "SMS":
                mensaje_envio = main.adaptar_sms(respuesta)
            else:
                mensaje_envio = main.extraer_adaptacion(respuesta)
        except main.AdaptacionInvalida as exc:
            categoria = 'SmsAdaptationFailed' if datos.canal == 'SMS' else 'VoiceAdaptationFailed'
            main.logger.warning('%s reason=%s', categoria, exc.codigo)
            main.logger.warning('GroqAdaptationResponse canal=%s reason=%s structure=%s', datos.canal, exc.codigo,
                           json.dumps(main.estructura_respuesta(respuesta, modelo_adaptacion, max_tokens)))
            raise HTTPException(
                502,
                f"No se pudo generar el mensaje corto para {datos.canal}."
            ) from None

        main.logger.info('GroqAdaptationResponse canal=%s structure=%s', datos.canal,
                    json.dumps(main.estructura_respuesta(respuesta, modelo_adaptacion, max_tokens)))

    return main.comunicaciones.respuesta(
        main.comunicaciones.registrar(
            db,
            cliente,
            datos.canal,
            mensaje_envio,
            **({"estrategia_id": datos.estrategia_id} if datos.estrategia_id is not None else {})
        )
    )


@router.get("/api/integraciones/estado")
def integraciones_estado(user: dict = Depends(auth.get_entra_user)):
    return main.estado_proveedores()
