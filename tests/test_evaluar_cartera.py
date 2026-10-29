"""Evaluación local por lote: solo campos de riesgo del cliente, sin servicios."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import event

from app import models
from app.services import comunicaciones, groq, riesgo, twilio_service, sendgrid_service

URL = '/api/cartera/evaluar'


@pytest.fixture(autouse=True)
def proveedores_prohibidos(monkeypatch):
    groq_mock = AsyncMock(side_effect=AssertionError('Groq prohibido'))
    monkeypatch.setattr(groq, 'client', SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=groq_mock)), close=AsyncMock()))
    llamadas = []
    for modulo, nombre in [(comunicaciones, 'registrar'), (twilio_service, 'enviar_mensaje'),
                           (twilio_service, 'enviar_llamada'), (sendgrid_service, 'enviar_email')]:
        funcion = Mock(side_effect=AssertionError('Proveedor prohibido'))
        monkeypatch.setattr(modulo, nombre, funcion)
        llamadas.append(funcion)
    yield
    groq_mock.assert_not_awaited()
    for funcion in llamadas:
        funcion.assert_not_called()


def cliente(db, *, saldo=10000, evaluado=False):
    c = models.Cliente(nombre='Perfil prueba', score_riesgo=.4 if evaluado else None,
                       probabilidad_pago_a_tiempo=.6 if evaluado else None,
                       segmento='Riesgo medio' if evaluado else 'No definido')
    db.add(c); db.flush()
    if not evaluado:
        c.score_riesgo = None
    db.add(models.Deuda(cliente_id=c.id, monto_total=10000, saldo_pendiente=saldo,
                        fecha_vencimiento=date.today(), estatus='Pendiente' if saldo else 'Pagada',
                        probabilidad_pago=.77))
    db.add(models.Pago(cliente_id=c.id, monto=200, fecha_vencimiento=date.today(),
                       fecha_pago=date.today(), dias_atraso=0))
    db.commit()
    return c


def snapshot(db, clase):
    return [tuple(getattr(f, c.name) for c in clase.__table__.columns)
            for f in db.query(clase).order_by(clase.id)]


def test_autenticacion(client):
    assert client.post(URL).status_code == 401


@pytest.mark.parametrize('envio_real', ['true', 'false'])
def test_evaluacion_solo_riesgo_y_repeticion(client, db, headers, monkeypatch, envio_real):
    monkeypatch.setenv('COMMUNICATIONS_REAL_ENABLED', envio_real)
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    pendiente = cliente(db)
    existente = cliente(db, evaluado=True)
    liquidado = cliente(db, saldo=0)
    # Ningún campo de deuda/pago/historial/comunicación debe cambiar.
    clases = [models.Deuda, models.Pago, models.HistorialMensaje, models.Comunicacion]
    antes = {clase: snapshot(db, clase) for clase in clases}
    original = riesgo.recalcular_riesgo
    esperado = original(db, pendiente)
    db.rollback()  # Revertir el cálculo de referencia antes del POST.
    ids = [pendiente.id, existente.id, liquidado.id]
    inferencia = Mock(wraps=original)
    monkeypatch.setattr(riesgo, 'recalcular_riesgo', inferencia)
    respuesta = client.post(URL, headers=headers)
    assert respuesta.status_code == 200
    assert respuesta.json() == dict(clientes_activos_encontrados=2, clientes_evaluados=1,
        clientes_ya_evaluados_omitidos=1, clientes_fallidos=0, clientes_sin_deuda_omitidos=0, errores=[])
    assert inferencia.call_count == 1
    assert inferencia.call_args.args[1].id == ids[0]
    db.expire_all()
    c = db.get(models.Cliente, ids[0])
    assert (c.probabilidad_pago_a_tiempo, c.score_riesgo, c.segmento) == tuple(
        esperado[k] for k in ('probabilidad_pago_a_tiempo', 'score_riesgo', 'segmento'))
    assert db.get(models.Cliente, ids[1]).score_riesgo == .4
    assert db.get(models.Cliente, ids[2]).score_riesgo is None
    assert {clase: snapshot(db, clase) for clase in clases} == antes
    segundo = client.post(URL, headers=headers).json()
    assert segundo['clientes_evaluados'] == 0 and segundo['clientes_ya_evaluados_omitidos'] == 2
    assert inferencia.call_count == 1


def test_rollback_individual_y_continuacion(client, db, headers, monkeypatch):
    malo = cliente(db); bueno = cliente(db)
    ids = [malo.id, bueno.id]
    original = riesgo.recalcular_riesgo
    def evaluar(db, c):
        if c.id == ids[0]:
            c.score_riesgo = .99
            c.segmento = 'Alto riesgo'
            db.flush()  # Incluso escrituras parciales deben revertirse.
            raise RuntimeError('SECRETO-SENTINELA')
        return original(db, c)
    monkeypatch.setattr(riesgo, 'recalcular_riesgo', evaluar)
    respuesta = client.post(URL, headers=headers)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos['clientes_evaluados'] == 1 and datos['clientes_fallidos'] == 1
    assert datos['errores'][0]['cliente_id'] == ids[0]
    assert 'SECRETO-SENTINELA' not in respuesta.text
    db.expire_all()
    assert db.get(models.Cliente, ids[0]).score_riesgo is None
    assert db.get(models.Cliente, ids[0]).segmento == 'No definido'
    assert riesgo.evaluacion_riesgo_completa(db.get(models.Cliente, ids[1]))


def test_fallo_al_guardar_no_cuenta_como_exito(client, db, headers):
    primero = cliente(db); segundo = cliente(db)
    ids = [primero.id, segundo.id]
    def fallar(session, contexto, instancias):
        if any(isinstance(c, models.Cliente) and c.id == ids[0] for c in session.dirty):
            raise RuntimeError('Fallo de persistencia')
    event.listen(db, 'before_flush', fallar)
    try:
        datos = client.post(URL, headers=headers).json()
    finally:
        event.remove(db, 'before_flush', fallar)
    assert datos['clientes_evaluados'] == 1 and datos['clientes_fallidos'] == 1
    db.expire_all()
    assert db.get(models.Cliente, ids[0]).score_riesgo is None
    assert db.get(models.Cliente, ids[1]).score_riesgo is not None


@pytest.mark.parametrize('probabilidad', [float('nan'), float('inf'), -1, 2])
def test_salida_invalida_se_revierte(client, db, headers, monkeypatch, probabilidad):
    c = cliente(db); id_ = c.id
    modelo = Mock()
    modelo.predict_proba.return_value = [[1 - probabilidad, probabilidad]]
    monkeypatch.setattr(riesgo, '_modelo_riesgo', modelo)
    datos = client.post(URL, headers=headers).json()
    assert datos['clientes_fallidos'] == 1 and datos['clientes_evaluados'] == 0
    db.expire_all()
    assert db.get(models.Cliente, id_).score_riesgo is None


@pytest.mark.parametrize('campo,valor', [('score_riesgo', None), ('probabilidad_pago_a_tiempo', None), ('segmento', 'No definido')])
def test_evaluacion_incompleta_se_procesa(client, db, headers, campo, valor):
    c = cliente(db, evaluado=True); setattr(c, campo, valor); db.commit()
    datos = client.post(URL, headers=headers).json()
    assert datos['clientes_evaluados'] == 1


def test_modelo_ausente_no_escribe(client, db, headers, monkeypatch):
    c = cliente(db); id_ = c.id
    monkeypatch.setattr(riesgo, '_modelo_riesgo', None)
    assert client.post(URL, headers=headers).status_code == 503
    assert db.get(models.Cliente, id_).score_riesgo is None


def test_cartera_vacia(client, headers):
    datos = client.post(URL, headers=headers).json()
    assert datos['clientes_activos_encontrados'] == datos['clientes_evaluados'] == datos['clientes_fallidos'] == 0
