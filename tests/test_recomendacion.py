from datetime import date, timedelta
from types import SimpleNamespace as Dato
from unittest.mock import Mock

import pytest
from app import main, models
from app.services.recomendacion import (
    _configuracion_segura,
    _generar_propuestas,
    recomendar_cliente,
    recomendar_recuperacion,
)


MOTIVO_PLAN_PAGOS = (
    "Atraso de 30 a 89 días y saldo mayor a $1,000 MXN. "
    "Las opciones calculadas son propuestas informativas sujetas a revisión y "
    "autorización humana; no modifican la deuda ni constituyen un acuerdo aprobado."
)
ADVERTENCIA_PROPUESTA = "Propuesta sujeta a revisión y autorización humana. No modifica la deuda."


def recomendar(**cambios):
    entrada = dict(score_riesgo=.2, segmento='Bajo riesgo', dias_atraso=5,
                   saldo_pendiente=2000, pagos_puntuales=0)
    entrada.update(cambios)
    return recomendar_recuperacion(**entrada)


@pytest.mark.parametrize('cambios,tipo,humana', [
    ({'pagos_puntuales': 3}, 'Recordatorio de pago', False),
    ({'dias_atraso': 30}, 'Propuesta de plan de pagos', True),
    ({'score_riesgo': .66}, 'Seguimiento prioritario', False),
    ({'segmento': 'Alto riesgo'}, 'Seguimiento prioritario', False),
    ({'saldo_pendiente': 1000, 'dias_atraso': 60}, 'Recordatorio de pago', False),
    ({'saldo_pendiente': 50000}, 'Recordatorio de pago', False),
    ({'saldo_pendiente': 0, 'score_riesgo': None}, 'Sin gestión de recuperación', False),
    ({'dias_atraso': 0}, 'Recordatorio preventivo', False),
    ({'dias_atraso': -1}, 'Recordatorio preventivo', False),
    ({'dias_atraso': 29}, 'Recordatorio de pago', False),
    ({'dias_atraso': 89}, 'Propuesta de plan de pagos', True),
    ({'dias_atraso': 90}, 'Revisión manual para negociación', True),
    ({'saldo_pendiente': 1000.01, 'dias_atraso': 30}, 'Propuesta de plan de pagos', True),
    ({'saldo_pendiente': 49999.99}, 'Recordatorio de pago', False),
    ({'saldo_pendiente': 50000, 'dias_atraso': 1}, 'Recordatorio de pago', False),
    ({'saldo_pendiente': 50000, 'dias_atraso': 29}, 'Recordatorio de pago', False),
    ({'saldo_pendiente': 50000, 'dias_atraso': 30}, 'Revisión manual para negociación', True),
    ({'saldo_pendiente': 49999.99, 'dias_atraso': 30}, 'Propuesta de plan de pagos', True),
    ({'saldo_pendiente': 50000, 'dias_atraso': 1, 'score_riesgo': .8}, 'Seguimiento prioritario', False),
    ({'saldo_pendiente': 50000, 'dias_atraso': 30, 'score_riesgo': .8}, 'Revisión manual para negociación', True),
    ({'saldo_pendiente': 50000, 'dias_atraso': 90, 'score_riesgo': None}, 'Revisión manual', True),
    ({'saldo_pendiente': 50000, 'dias_atraso': 0}, 'Recordatorio preventivo', False),
    ({'score_riesgo': .659}, 'Recordatorio de pago', False),
    ({'score_riesgo': 1}, 'Seguimiento prioritario', False),
    ({'score_riesgo': 0}, 'Recordatorio de pago', False),
    ({'score_riesgo': None}, 'Revisión manual', True),
    ({'score_riesgo': float('nan')}, 'Revisión manual', True),
    ({'score_riesgo': 1.01}, 'Revisión manual', True),
    ({'segmento': 'No definido'}, 'Revisión manual', True),
    ({'dias_atraso': None}, 'Revisión manual', True),
    ({'saldo_pendiente': -1}, 'Revisión manual', True),
    ({'saldo_pendiente': float('inf')}, 'Revisión manual', True),
])
def test_reglas_y_limites(cambios, tipo, humana):
    salida = recomendar(**cambios)
    assert salida == recomendar(**cambios)
    assert salida['tipo'] == tipo
    assert salida['requiere_revision_humana'] is humana
    assert salida['motivo']
    assert salida['nivel_atencion'] in ('normal', 'alta', 'sin atención')
    claves_base = {'tipo', 'motivo', 'nivel_atencion', 'requiere_revision_humana'}
    if tipo == 'Propuesta de plan de pagos':
        assert set(salida) == claves_base | {'propuesta_pronto_pago', 'propuesta_plan_pagos'}
        assert salida['motivo'] == MOTIVO_PLAN_PAGOS
    else:
        assert set(salida) == claves_base


@pytest.mark.parametrize('cambios', [
    {'score_riesgo': None}, {'score_riesgo': float('nan')},
    {'score_riesgo': 1.01}, {'segmento': 'No definido'}, {'dias_atraso': None},
    {'saldo_pendiente': -1}, {'saldo_pendiente': float('inf')},
])
def test_datos_incompletos_motivo_exacto(cambios):
    assert recomendar(**cambios) == {
        'tipo': 'Revisión manual',
        'motivo': 'Faltan datos válidos de riesgo o vencimiento; verificar la información antes de definir una estrategia.',
        'nivel_atencion': 'alta',
        'requiere_revision_humana': True,
    }


def test_historial_observado_y_limite():
    assert 'puntuales' not in recomendar(pagos_puntuales=2)['motivo']
    assert 'puntuales' in recomendar(pagos_puntuales=3)['motivo']
    assert 'puntuales' not in recomendar(pagos_puntuales=3, score_riesgo=.33)['motivo']


def test_adaptador_solo_deudas_activas_y_pagos_realizados():
    hoy = date(2026, 10, 21)
    c = Dato(score_riesgo=.2, segmento='Bajo riesgo',
             deudas=[Dato(saldo_pendiente=600, fecha_vencimiento=hoy-timedelta(days=30)),
                     Dato(saldo_pendiente=401, fecha_vencimiento=hoy+timedelta(days=10)),
                     Dato(saldo_pendiente=0, fecha_vencimiento=hoy-timedelta(days=100))],
             pagos=[Dato(fecha_pago=hoy, dias_atraso=0)] * 3)
    assert recomendar_cliente(c, hoy=hoy)['tipo'] == 'Propuesta de plan de pagos'
    c.deudas[1].saldo_pendiente = 400
    assert 'puntuales' in recomendar_cliente(c, hoy=hoy)['motivo']
    c.pagos[0] = Dato(fecha_pago=None, dias_atraso=0)
    assert 'puntuales' not in recomendar_cliente(c, hoy=hoy)['motivo']
    c.deudas[1].fecha_vencimiento = None
    assert recomendar_cliente(c, hoy=hoy)['requiere_revision_humana'] is True


def test_ficha_solo_lectura_y_actualizacion_datos(client, db, headers, monkeypatch):
    c = models.Cliente(nombre='Prueba', score_riesgo=.2, segmento='Bajo riesgo')
    c.deudas = [models.Deuda(monto_total=2000, saldo_pendiente=2000,
                             fecha_vencimiento=date.today()-timedelta(days=30))]
    db.add(c); db.commit()
    proveedor = Mock(side_effect=AssertionError('No llamar proveedor'))
    modelo = Mock(side_effect=AssertionError('No ejecutar ML'))
    monkeypatch.setattr(main, 'client', proveedor)
    monkeypatch.setattr(main, '_modelo_riesgo', modelo)
    url = f'/api/clientes/{c.id}'
    for _ in range(2):
        res = client.get(url, headers=headers)
        assert res.status_code == 200
        assert res.json()['recomendacion_recuperacion']['tipo'] == 'Propuesta de plan de pagos'
    assert c.deudas[0].saldo_pendiente == 2000
    assert c.score_riesgo == .2
    c.deudas[0].saldo_pendiente = 0
    db.commit()
    assert client.get(url, headers=headers).json()['recomendacion_recuperacion']['tipo'] == 'Sin gestión de recuperación'
    assert db.query(models.HistorialMensaje).count() == 0
    assert db.query(models.Comunicacion).count() == 0
    assert db.query(models.Pago).count() == 0
    assert not proveedor.mock_calls
    assert not modelo.mock_calls
    # Evita que lifespan intente cerrar el objeto de prueba síncrono.
    monkeypatch.setattr(main, 'client', None)


def test_propuestas_descuento_plazos_y_disclaimer():
    # Deuda baja (< umbral_1 = 5000): solo 3 meses
    baja = recomendar(dias_atraso=30, saldo_pendiente=2000)
    assert baja['propuesta_pronto_pago'] == {
        'porcentaje_descuento': 10.0,
        'descuento': 200.0,
        'saldo_propuesto': 1800.0,
        'vigencia_dias': 5,
        'advertencia': ADVERTENCIA_PROPUESTA,
    }
    assert baja['propuesta_plan_pagos'] == {
        'saldo_base': 2000.0,
        'opciones': [{'meses': 3, 'cuota_mensual': 666.67}],
        'advertencia': ADVERTENCIA_PROPUESTA,
    }

    # Deuda media (>= 5000 y < 15000): 3 y 6 meses
    media = recomendar(dias_atraso=45, saldo_pendiente=6000)
    assert [o['meses'] for o in media['propuesta_plan_pagos']['opciones']] == [3, 6]
    assert media['propuesta_plan_pagos']['opciones'] == [
        {'meses': 3, 'cuota_mensual': 2000.0},
        {'meses': 6, 'cuota_mensual': 1000.0},
    ]

    # Deuda alta (>= 15000 y < 50000): 3, 6 y 12 meses
    alta = recomendar(dias_atraso=60, saldo_pendiente=15000)
    assert [o['meses'] for o in alta['propuesta_plan_pagos']['opciones']] == [3, 6, 12]
    assert alta['propuesta_plan_pagos']['opciones'] == [
        {'meses': 3, 'cuota_mensual': 5000.0},
        {'meses': 6, 'cuota_mensual': 2500.0},
        {'meses': 12, 'cuota_mensual': 1250.0},
    ]


def test_redondeo_decimal_evita_errores_coma_flotante():
    propuestas = _generar_propuestas(1000.33)
    assert propuestas['propuesta_pronto_pago'] == {
        'porcentaje_descuento': 10.0,
        'descuento': 100.03,
        'saldo_propuesto': 900.30,
        'vigencia_dias': 5,
        'advertencia': ADVERTENCIA_PROPUESTA,
    }
    assert propuestas['propuesta_plan_pagos'] == {
        'saldo_base': 1000.33,
        'opciones': [{'meses': 3, 'cuota_mensual': 333.44}],
        'advertencia': ADVERTENCIA_PROPUESTA,
    }


@pytest.mark.parametrize('env_vars,esperado', [
    ({}, (10.0, 5, 5000.0, 15000.0)),
    ({'RECOMENDACION_DESCUENTO_PCT': '7.5', 'RECOMENDACION_DESCUENTO_DIAS': '10',
      'RECOMENDACION_UMBRAL_PLAZO_1': '3000', 'RECOMENDACION_UMBRAL_PLAZO_2': '12000'},
     (7.5, 10, 3000.0, 12000.0)),
    # Descuento > 10% revierte solo el porcentaje a 10.0
    ({'RECOMENDACION_DESCUENTO_PCT': '15.0', 'RECOMENDACION_DESCUENTO_DIAS': '8'},
     (10.0, 8, 5000.0, 15000.0)),
    # Descuento 0 o negativo o texto inválido
    ({'RECOMENDACION_DESCUENTO_PCT': '0', 'RECOMENDACION_DESCUENTO_DIAS': '7'},
     (10.0, 7, 5000.0, 15000.0)),
    ({'RECOMENDACION_DESCUENTO_PCT': '-5', 'RECOMENDACION_DESCUENTO_DIAS': '7'},
     (10.0, 7, 5000.0, 15000.0)),
    ({'RECOMENDACION_DESCUENTO_PCT': 'invalido', 'RECOMENDACION_DESCUENTO_DIAS': '7'},
     (10.0, 7, 5000.0, 15000.0)),
    # Días inválidos, negativos o cero no afectan otras variables válidas
    ({'RECOMENDACION_DESCUENTO_PCT': '5.0', 'RECOMENDACION_DESCUENTO_DIAS': '0'},
     (5.0, 5, 5000.0, 15000.0)),
    ({'RECOMENDACION_DESCUENTO_PCT': '5.0', 'RECOMENDACION_DESCUENTO_DIAS': '-3'},
     (5.0, 5, 5000.0, 15000.0)),
    ({'RECOMENDACION_DESCUENTO_PCT': '5.0', 'RECOMENDACION_DESCUENTO_DIAS': 'abc'},
     (5.0, 5, 5000.0, 15000.0)),
    # Un umbral válido y otro inválido (independencia cuando umbral_1 < umbral_2 se mantiene)
    ({'RECOMENDACION_UMBRAL_PLAZO_1': '4000', 'RECOMENDACION_UMBRAL_PLAZO_2': 'invalido'},
     (10.0, 5, 4000.0, 15000.0)),
    ({'RECOMENDACION_UMBRAL_PLAZO_1': '-100', 'RECOMENDACION_UMBRAL_PLAZO_2': '20000'},
     (10.0, 5, 5000.0, 20000.0)),
    ({'RECOMENDACION_UMBRAL_PLAZO_1': '0', 'RECOMENDACION_UMBRAL_PLAZO_2': '18000'},
     (10.0, 5, 5000.0, 18000.0)),
    # UMBRAL_1 >= UMBRAL_2 revierte AMBOS umbrales a 5000.0 y 15000.0
    ({'RECOMENDACION_UMBRAL_PLAZO_1': '20000', 'RECOMENDACION_UMBRAL_PLAZO_2': '10000',
      'RECOMENDACION_DESCUENTO_PCT': '8.0'},
     (8.0, 5, 5000.0, 15000.0)),
    ({'RECOMENDACION_UMBRAL_PLAZO_1': '10000', 'RECOMENDACION_UMBRAL_PLAZO_2': '10000'},
     (10.0, 5, 5000.0, 15000.0)),
    # Un umbral válido alto que al revertir el otro inválido rompe umbral_1 < umbral_2
    ({'RECOMENDACION_UMBRAL_PLAZO_1': '16000', 'RECOMENDACION_UMBRAL_PLAZO_2': 'texto'},
     (10.0, 5, 5000.0, 15000.0)),
])
def test_configuracion_segura_failsafe_independiente(monkeypatch, env_vars, esperado):
    for var in (
        'RECOMENDACION_DESCUENTO_PCT',
        'RECOMENDACION_DESCUENTO_DIAS',
        'RECOMENDACION_UMBRAL_PLAZO_1',
        'RECOMENDACION_UMBRAL_PLAZO_2',
    ):
        monkeypatch.delenv(var, raising=False)
    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)
    assert _configuracion_segura() == esperado
