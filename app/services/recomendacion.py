"""Reglas de negocio MVP v1; no predicen ni autorizan condiciones financieras.

Primera coincidencia gana. Umbrales en MXN y días naturales, documentados en
 docs/RECOMENDACION_RECUPERACION.md. No hay escrituras ni acceso a proveedores.
"""
from datetime import date
from math import isfinite


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
        return resultado("Propuesta de plan de pagos", "Atraso de 30 a 89 días y saldo mayor a $1,000 MXN. Evaluar viabilidad; cualquier plan requiere revisión/autorización humana, sin cuotas ni plazos preaprobados.", "alta", True)
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
