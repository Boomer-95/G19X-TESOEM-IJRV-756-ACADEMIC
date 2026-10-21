"""Sugerencia observacional MVP. Función de lectura sin BD ni proveedores."""
import os
from datetime import date
from decimal import Decimal
from fractions import Fraction
from math import isfinite

CANALES = ('Email', 'SMS', 'WhatsApp')  # Último desempate, no preferencia comercial.
FALLOS = {'failed', 'undelivered', 'bounced', 'dropped'}


def ventana_configurada():
    valor = int(os.getenv('CANAL_SUGERIDO_VENTANA_PAGO_DIAS', '7'))
    if not 1 <= valor <= 365:
        raise ValueError('CANAL_SUGERIDO_VENTANA_PAGO_DIAS debe estar entre 1 y 365')
    return valor


def fuente(registros):
    modos = {c.modo for c in registros if c.modo in ('real', 'simulado')}
    return ('mixta' if len(modos) == 2 else 'real' if modos == {'real'}
            else 'simulada' if modos else 'no_verificada' if registros else 'sin_datos')


def sugerir_canal(cliente, *, ventana_pago_dias=None, hoy=None):
    """Primera asociación por pago: última fecha, luego mayor ID, sin duplicar.

    El día cero es inclusivo: la BD no guarda hora y no permite probar el orden
    intradía. Fallos e intenciones también pueden coincidir temporalmente con
    pagos; esto no confirma contacto ni causalidad. Ver docs/CANAL_SUGERIDO.md.
    """
    ventana = ventana_configurada() if ventana_pago_dias is None else ventana_pago_dias
    if isinstance(ventana, bool) or not isinstance(ventana, int) or not 1 <= ventana <= 365:
        raise ValueError('La ventana debe ser un entero entre 1 y 365 días')
    hoy = hoy or date.today()
    contactos = [c for c in cliente.comunicaciones
                 if c.cliente_id == cliente.id and c.canal in CANALES
                 and (c.fecha_envio is None or c.fecha_envio <= hoy)]
    fechados = [c for c in contactos if c.fecha_envio is not None]
    conocidos = [c for c in fechados if c.modo in ('real', 'simulado')]
    estadisticas = {}
    for canal in CANALES:
        todos = [c for c in contactos if c.canal == canal]
        registros = [c for c in conocidos if c.canal == canal]
        # Una simulación no prueba entrega/lectura, aunque tenga flags heredados.
        fallidas = [c for c in registros if c.modo == 'real' and
                    (c.estado in ('Fallido', 'No entregado') or c.provider_status in FALLOS)]
        entregadas = [c for c in registros if c.modo == 'real' and c not in fallidas
                      and (c.provider_status in ('delivered', 'read')
                           or c.estado in ('Entregado', 'Leído'))]
        leidas = [c for c in entregadas if c.provider_status == 'read' or c.estado == 'Leído']
        estadisticas[canal] = dict(
            comunicaciones_totales=len(todos), comunicaciones_evaluables=len(registros),
            entregadas_o_leidas=len(entregadas), leidas=len(leidas),
            fallidas_o_no_entregadas=len(fallidas), pagos_asociados_temporalmente=0,
            monto_asociado_temporalmente=Decimal(0),
            ultima_comunicacion=max((c.fecha_envio for c in todos if c.fecha_envio), default=None),
            fuente_evidencia=fuente(todos),
            comunicaciones_reales=sum(c.modo == 'real' for c in registros),
            comunicaciones_simuladas=sum(c.modo == 'simulado' for c in registros),
            comunicaciones_no_evaluables=len(todos) - len(registros))
    for pago in cliente.pagos:
        if (pago.cliente_id != cliente.id or pago.fecha_pago is None
                or pago.fecha_pago > hoy or not pago.se_recuperó
                or not isfinite(pago.monto) or pago.monto <= 0):
            continue
        candidatos = [c for c in fechados if 0 <= (pago.fecha_pago - c.fecha_envio).days <= ventana]
        if not candidatos:
            continue
        contacto = max(candidatos, key=lambda c: (c.fecha_envio, c.id))
        # Origen desconocido: no se reasigna a un contacto anterior conocido.
        if contacto.modo not in ('real', 'simulado'):
            continue
        datos = estadisticas[contacto.canal]
        datos['pagos_asociados_temporalmente'] += 1
        datos['monto_asociado_temporalmente'] += Decimal(str(pago.monto))
    for datos in estadisticas.values():
        datos['monto_asociado_temporalmente'] = float(datos['monto_asociado_temporalmente'].quantize(Decimal('.01')))
        datos['score_interno'] = (5 * datos['pagos_asociados_temporalmente'] + 3 * datos['leidas']
                                 + 2 * (datos['entregadas_o_leidas'] - datos['leidas'])
                                 - 2 * datos['fallidas_o_no_entregadas'])
    elegibles = [canal for canal, d in estadisticas.items()
                 if d['comunicaciones_evaluables'] >= 2 and d['score_interno'] > 0]
    base = dict(ventana_pago_dias=ventana, estadisticas=estadisticas,
                fuente_evidencia=fuente(contactos))
    if not elegibles:
        return dict(canal=None, estado='Sin evidencia suficiente', confianza='insuficiente',
                    motivo='Se requieren al menos dos comunicaciones fechadas de origen conocido en un canal y un score positivo de evidencia.', **base)
    def orden(canal):
        d = estadisticas[canal]
        return (d['score_interno'], d['pagos_asociados_temporalmente'],
                Fraction(d['entregadas_o_leidas'], d['comunicaciones_evaluables']),
                d['comunicaciones_evaluables'], -CANALES.index(canal))
    canal = max(elegibles, key=orden)
    d = estadisticas[canal]
    confianza = 'baja'
    if d['fuente_evidencia'] == 'real':
        if (d['comunicaciones_evaluables'] >= 10 and d['pagos_asociados_temporalmente'] >= 3
                and Fraction(d['entregadas_o_leidas'], d['comunicaciones_evaluables']) >= Fraction(4, 5)):
            confianza = 'alta'
        elif d['comunicaciones_evaluables'] >= 5 and d['entregadas_o_leidas'] >= 2:
            confianza = 'media'
    motivo = (f"{d['entregadas_o_leidas']} de {d['comunicaciones_evaluables']} contactos evaluables fueron entregados/leídos; "
              f"{d['fallidas_o_no_entregadas']} fallaron y hay {d['pagos_asociados_temporalmente']} pagos asociados temporalmente "
              f"dentro de los siguientes {ventana} días. Mayor score interno, con desempates documentados; no es probabilidad.")
    return dict(canal=canal, estado='Canal sugerido', confianza=confianza, motivo=motivo, **base)
