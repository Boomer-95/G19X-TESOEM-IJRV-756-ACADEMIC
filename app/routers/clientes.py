from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from .. import auth, models
from ..database import get_db
from ..services import riesgo
from ..services.analitica import cartera_actual
from ..services.canal_sugerido import sugerir_canal
from ..services.recomendacion import recomendar_cliente

router = APIRouter(tags=["clientes"])


@router.get("/api/clientes")
def buscar_clientes(query: str = "", segmento: Literal["Alto riesgo", "Riesgo medio", "Bajo riesgo", "No definido", "Sin calcular"] | None = None,
    solo_con_deuda: bool = False, analizado: bool | None = None, estatus_deuda: Literal["Pendiente", "En Mora", "En mora", "Pagada"] | None = None,
    orden: Literal["prioridad", "saldo", "atraso", "vencimiento", "nombre"] = "prioridad",
    db: Session = Depends(get_db), user: dict = Depends(auth.get_entra_user)):
    consulta = db.query(models.Cliente).options(selectinload(models.Cliente.deudas))
    if solo_con_deuda:
        consulta = consulta.filter(models.Cliente.deudas.any(models.Deuda.saldo_pendiente > 0))
    texto = query.strip()
    if texto:
        identificador = texto[3:] if texto.upper().startswith("CL-") else texto
        if identificador.isdigit():
            consulta = consulta.filter(models.Cliente.id == int(identificador))
        else:
            consulta = consulta.filter(models.Cliente.nombre.ilike("%" + texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"))
    if segmento:
        consulta = consulta.filter(
            or_(models.Cliente.segmento == "No definido", models.Cliente.segmento.is_(None))
            if segmento in ("No definido", "Sin calcular") else models.Cliente.segmento == segmento)
    if analizado is not None:
        condicion = or_(models.Cliente.segmento == "No definido", models.Cliente.segmento.is_(None))
        consulta = consulta.filter(~condicion if analizado else condicion)
    clientes = consulta.all()
    if estatus_deuda:
        clientes = [c for c in clientes if any(riesgo.estado_deuda(d).lower() == estatus_deuda.lower() for d in c.deudas)]
    filas = [riesgo.resumen_cliente(c) for c in clientes]
    claves = {"prioridad": lambda c: -c["prioridad"], "saldo": lambda c: -c["monto_pendiente"],
              "atraso": lambda c: min(c["dias_restantes"] or 0, 0),
              "vencimiento": lambda c: c["fecha_vencimiento"] or date.max,
              "nombre": lambda c: (c["cliente_nombre"] or "").casefold()}
    return sorted(filas, key=lambda c: (claves[orden](c), c["cliente_id"]))


@router.get("/api/clientes/{cliente_id}")
def detalle_cliente(cliente_id: int, db: Session = Depends(get_db),
                    user: dict = Depends(auth.get_entra_user)):
    c = db.get(models.Cliente, cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    ultimo = db.query(models.HistorialMensaje).filter_by(cliente_id=c.id).order_by(models.HistorialMensaje.fecha_creacion.desc().nulls_last(), models.HistorialMensaje.id.desc()).first()
    return {**riesgo.resumen_cliente(c), "email": c.email, "telefono": c.telefono,
            "recomendacion_recuperacion": recomendar_cliente(c),
            "canal_sugerido": sugerir_canal(c),
            "tiene_estrategia": ultimo is not None,
            "fecha_ultima_estrategia": ultimo.fecha_creacion if ultimo else None,
            "monto_original_total": sum(d.monto_total for d in c.deudas),
            "numero_deudas": len(c.deudas),
            "numero_deudas_vencidas": sum(riesgo.estado_deuda(d) == "En Mora" for d in c.deudas),
            "deudas": [riesgo.deuda_dict(d) for d in sorted(c.deudas, key=lambda d: d.id)],
            "pagos": [riesgo.pago_dict(p) for p in sorted(c.pagos, key=lambda p: (p.fecha_pago or date.min, p.id), reverse=True)],
            "comunicaciones": [
                {"id": registro.id, "canal": registro.canal, "fecha": registro.fecha_envio,
                 "mensaje": registro.mensaje, "exitoso": registro.exitoso,
                 "simulada": registro.modo == "simulado" or (registro.modo is None and registro.exitoso is False),
                 "modo": registro.modo, "estado": registro.estado, "provider": registro.provider,
                 "provider_status": registro.provider_status}
                for registro in sorted(c.comunicaciones,
                    key=lambda registro: (registro.fecha_envio or date.min, registro.id), reverse=True)
            ],
            "ultima_estrategia": {"id": ultimo.id, "mensaje": ultimo.mensaje_generado, "fecha": ultimo.fecha_creacion,
                                   "origen_verificado": bool(ultimo.contexto_hash)} if ultimo else None}


@router.get("/api/cartera-priorizada")
def cartera_priorizada(
    db: Session = Depends(get_db),
    user: dict = Depends(auth.get_entra_user),
):
    clientes = db.query(models.Cliente).options(selectinload(models.Cliente.deudas)).all()
    return sorted([riesgo.resumen_cliente(c) for c in clientes if any(d.saldo_pendiente > 0 for d in c.deudas)],
                  key=lambda c: c["prioridad"], reverse=True)


@router.get("/api/metricas")
def obtener_metricas_globales(
    db: Session = Depends(get_db),
    user: dict = Depends(auth.get_entra_user),
):
    total_clientes = db.query(models.Cliente).count()
    cartera = cartera_actual(db)
    saldo_total = cartera['saldo_pendiente']
    cartera_vencida = cartera['cartera_vencida']
    total_estrategias = db.query(func.count(func.distinct(models.HistorialMensaje.cliente_id))).scalar()

    monto_original = db.query(func.sum(models.Deuda.monto_total)).scalar() or 0.0
    if monto_original > 0:
        monto_pagado = monto_original - saldo_total
        porcentaje_recuperacion = (monto_pagado / monto_original) * 100
    else:
        porcentaje_recuperacion = 0.0

    return {
        "total_clientes": total_clientes,
        "deudores_activos": cartera["deudores_activos"],
        "clientes_sin_evaluar": db.query(models.Cliente).filter(or_(models.Cliente.segmento == "No definido", models.Cliente.segmento.is_(None))).count(),
        "saldo_pendiente": saldo_total,
        "cartera_vencida": cartera_vencida,
        "estrategias_ia": total_estrategias,
        "porcentaje_recuperacion": round(porcentaje_recuperacion, 1),
    }
