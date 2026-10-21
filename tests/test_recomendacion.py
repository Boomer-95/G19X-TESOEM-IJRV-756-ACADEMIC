from datetime import date, timedelta
from types import SimpleNamespace as Dato
from unittest.mock import Mock

import pytest
from app import main, models
from app.services.recomendacion import recomendar_recuperacion, recomendar_cliente


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
    assert set(salida) == {'tipo', 'motivo', 'nivel_atencion', 'requiere_revision_humana'}


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
