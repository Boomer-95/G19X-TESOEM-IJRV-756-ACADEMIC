"""Reglas de negocio MVP v1; no predicen ni autorizan condiciones financieras.

Primera coincidencia gana. Umbrales en MXN y días naturales, documentados en
 docs/RECOMENDACION_RECUPERACION.md. No hay escrituras ni acceso a proveedores.
"""
import os
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite


def _configuracion_segura():
    pct = Decimal("10.0")
    try:
        val_pct = Decimal(os.getenv("RECOMENDACION_DESCUENTO_PCT", "10.0"))
        if val_pct.is_finite() and Decimal("0") < val_pct <= Decimal("10.0"):
            pct = val_pct
    except (InvalidOperation, ValueError, TypeError):
        pct = Decimal("10.0")

    dias = 5
    try:
        val_dias = int(os.getenv("RECOMENDACION_DESCUENTO_DIAS", "5"))
        if val_dias > 0:
            dias = val_dias
    except (InvalidOperation, ValueError, TypeError):
        dias = 5

    umbral1 = Decimal("5000.0")
    try:
        val_u1 = Decimal(os.getenv("RECOMENDACION_UMBRAL_PLAZO_1", "5000.0"))
        if val_u1.is_finite() and val_u1 > Decimal("0"):
            umbral1 = val_u1
    except (InvalidOperation, ValueError, TypeError):
        umbral1 = Decimal("5000.0")

    umbral2 = Decimal("15000.0")
    try:
        val_u2 = Decimal(os.getenv("RECOMENDACION_UMBRAL_PLAZO_2", "15000.0"))
        if val_u2.is_finite() and val_u2 > Decimal("0"):
            umbral2 = val_u2
    except (InvalidOperation, ValueError, TypeError):
        umbral2 = Decimal("15000.0")

    if not (umbral1 < umbral2):
        umbral1 = Decimal("5000.0")
        umbral2 = Decimal("15000.0")

    return float(pct), int(dias), float(umbral1), float(umbral2)


def _generar_propuestas(saldo_float):
    pct, dias, umbral_1, umbral_2 = _configuracion_segura()
    centavos = Decimal("0.01")
    try:
        saldo = Decimal(str(saldo_float)).quantize(centavos, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        saldo = Decimal("0.00")
    pct_dec = Decimal(str(pct))
    descuento = (saldo * pct_dec / Decimal("100")).quantize(centavos, rounding=ROUND_HALF_UP)
    saldo_propuesto = (saldo - descuento).quantize(centavos, rounding=ROUND_HALF_UP)
    advertencia = "Propuesta sujeta a revisión y autorización humana. No modifica la deuda."

    plazos = [3]
    if saldo >= Decimal(str(umbral_1)):
        plazos.append(6)
    if saldo >= Decimal(str(umbral_2)):
        plazos.append(12)

    opciones = [
        {
            "meses": int(m),
            "cuota_mensual": float((saldo / Decimal(m)).quantize(centavos, rounding=ROUND_HALF_UP)),
        }
        for m in plazos
    ]

    return {
        "propuesta_pronto_pago": {
            "porcentaje_descuento": float(pct),
            "descuento": float(descuento),
            "saldo_propuesto": float(saldo_propuesto),
            "vigencia_dias": int(dias),
            "advertencia": advertencia,
        },
        "propuesta_plan_pagos": {
            "saldo_base": float(saldo),
            "opciones": opciones,
            "advertencia": advertencia,
        },
    }


def recomendar_recuperacion(*, score_riesgo, segmento, dias_atraso,
                            saldo_pendiente, pagos_puntuales=0):
    """Función pura. Un atraso None indica vencimiento desconocido.

    pagos_puntuales cuenta únicamente pagos realizados con atraso conocido <= 0.
    No tener historial no se interpreta como incumplimiento.
    """
    def resultado(tipo, motivo, nivel="normal", humana=False):
        return {"tipo": tipo, "motivo": motivo, "nivel_atencion": nivel,
                "requiere_revision_humana": humana}

    if not isfinite(saldo_pendiente) or saldo_pendiente < 0:
        return resultado("Revisión manual", "Faltan datos válidos de riesgo o vencimiento; verificar la información antes de definir una estrategia.", "alta", True)
    if saldo_pendiente == 0:
        return resultado("Sin gestión de recuperación", "No hay saldo pendiente.", "sin atención")
    if (dias_atraso is None or score_riesgo is None or not isfinite(score_riesgo)
            or not 0 <= score_riesgo <= 1
            or segmento not in ("Bajo riesgo", "Riesgo medio", "Alto riesgo")):
        return resultado("Revisión manual", "Faltan datos válidos de riesgo o vencimiento; verificar la información antes de definir una estrategia.", "alta", True)
    dias_atraso = max(0, dias_atraso)
    if dias_atraso >= 90 or (saldo_pendiente >= 50000 and dias_atraso >= 30):
        return resultado("Revisión manual para negociación",
                         "Atraso de al menos 90 días o saldo de al menos $50,000 MXN con al menos 30 días de atraso. Cualquier negociación requiere revisión/autorización humana.", "alta", True)
    if score_riesgo >= .66 or segmento == "Alto riesgo":
        return resultado("Seguimiento prioritario", "Score de riesgo >= 0.66 o segmento Alto riesgo; priorizar seguimiento sin ofrecer condiciones financieras.", "alta")
    if dias_atraso == 0:
        return resultado("Recordatorio preventivo", "Saldo activo sin atraso; recordar el vencimiento sin comprometer condiciones.", "normal")
    if dias_atraso >= 30 and saldo_pendiente > 1000:
        base = resultado(
            "Propuesta de plan de pagos",
            "Atraso de 30 a 89 días y saldo mayor a $1,000 MXN. Las opciones calculadas son propuestas informativas sujetas a revisión y autorización humana; no modifican la deuda ni constituyen un acuerdo aprobado.",
            "alta",
            True,
        )
        base.update(_generar_propuestas(saldo_pendiente))
        return base
    motivo = "Saldo de hasta $1,000 MXN o atraso menor a 30 días; recordar el pago del saldo vigente."
    if pagos_puntuales >= 3 and score_riesgo < .33 and segmento == "Bajo riesgo":
        motivo += " Hay al menos tres pagos puntuales observados; favorecer un contacto cordial."
    return resultado("Recordatorio de pago", motivo)


def recomendar_cliente(cliente, *, hoy=None):
    """Adapta datos existentes sin recalcular score ni modificar deuda/cliente.

    Suma saldos positivos y usa el mayor atraso de las deudas activas.
    Cualquier deuda activa sin fecha obliga a verificar datos.
    """
    hoy = hoy or date.today()
    activas = [d for d in cliente.deudas if d.saldo_pendiente > 0]
    fechas = [d.fecha_vencimiento for d in activas]
    atraso = (max([0] + [(hoy - f).days for f in fechas])
              if all(f is not None for f in fechas) else None)
    puntuales = sum(p.fecha_pago is not None and p.dias_atraso is not None
                    and p.dias_atraso <= 0 for p in cliente.pagos)
    return recomendar_recuperacion(score_riesgo=cliente.score_riesgo,
                                  segmento=cliente.segmento, dias_atraso=atraso,
                                  saldo_pendiente=sum(d.saldo_pendiente for d in activas),
                                  pagos_puntuales=puntuales)
