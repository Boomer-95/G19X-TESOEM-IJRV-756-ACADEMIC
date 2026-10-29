from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app import models
from app.ml.features import extraer_features_cliente
from app.services import groq, riesgo


@pytest.mark.parametrize('method,path', [
    ('get', '/auth/me'), ('get', '/api/metricas'), ('get', '/api/cartera-priorizada'),
    ('get', '/ia/historial/1'), ('post', '/ia/analizar-riesgo/1'),
    ('post', '/ia/calcular-riesgo/1'), ('post', '/api/comunicaciones'),
])
def test_protegidos(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def crear_cliente(db):
    cliente = models.Cliente(nombre='Cliente demo', email='demo@example.invalid', score_riesgo=0.8)
    db.add(cliente)
    db.commit()
    return cliente


def agregar_deuda(db, c):
    db.add(models.Deuda(cliente_id=c.id, monto_total=100, saldo_pendiente=100,
                        fecha_vencimiento=date.today(), estatus='Pendiente'))
    db.commit()


def test_metricas_y_prioridad(client, db, headers):
    c = crear_cliente(db)
    otro = models.Cliente(nombre='Otro', score_riesgo=0.1)
    db.add(otro)
    db.flush()
    hoy = date.today()
    for cliente_id, saldo, fecha, estado in [
        (c.id, 100, hoy - timedelta(days=1), 'Pendiente'),
        (c.id, 200, hoy + timedelta(days=5), 'En Mora'),
        (c.id, 300, hoy + timedelta(days=5), 'Pendiente'),
        (c.id, 50, hoy, 'Pendiente'),
        (c.id, 0, hoy - timedelta(days=5), 'Pagada'),
        (otro.id, 100, hoy + timedelta(days=5), 'Pendiente'),
    ]:
        db.add(models.Deuda(cliente_id=cliente_id, monto_total=200, saldo_pendiente=saldo, fecha_vencimiento=fecha, estatus=estado))
    db.commit()
    data = client.get('/api/metricas', headers=headers).json()
    assert data['cartera_vencida'] == 300
    assert data['porcentaje_recuperacion'] == 37.5
    cartera = client.get('/api/cartera-priorizada', headers=headers).json()
    assert cartera[0]['cliente_id'] == c.id
    assert cartera[0]['prioridad'] == 520
    assert cartera[1]['prioridad'] == 10


@pytest.mark.parametrize('prob,segmento', [(0.1, 'Alto riesgo'), (0.5, 'Riesgo medio'), (0.9, 'Bajo riesgo')])
def test_riesgo(client, db, headers, monkeypatch, prob, segmento):
    c = crear_cliente(db)
    agregar_deuda(db, c)
    class Modelo:
        def predict_proba(self, frame):
            assert list(frame.columns) == riesgo.FEATURE_COLUMNS
            return [[1-prob, prob]]
    monkeypatch.setattr(riesgo, '_modelo_riesgo', Modelo())
    data = client.post(f'/ia/calcular-riesgo/{c.id}', headers=headers).json()
    assert data['score_riesgo'] == round(1-prob, 3)
    assert data['segmento'] == segmento
    assert db.get(models.Cliente, c.id).segmento == segmento
    assert extraer_features_cliente(db, c)['num_pagos_historicos'] == 0


def test_groq_sin_configurar(client, db, headers):
    c = crear_cliente(db)
    agregar_deuda(db, c)
    res = client.post(f'/ia/analizar-riesgo/{c.id}', headers=headers)
    assert res.status_code == 503
    assert res.json()['detail'] == 'Servicio de IA no configurado.'
    assert db.query(models.HistorialMensaje).count() == 0


def test_groq_mock(client, db, headers, monkeypatch):
    monkeypatch.setenv('GROQ_MODEL', 'openai/gpt-oss-20b')
    monkeypatch.setenv('GROQ_SMS_MODEL', 'qwen/qwen3.8-27b')
    c = crear_cliente(db)
    agregar_deuda(db, c)
    create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Mensaje PluriOne'), finish_reason='stop')]))
    monkeypatch.setattr(groq, 'client', SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock()))
    data = client.post(f'/ia/analizar-riesgo/{c.id}', headers=headers).json()
    assert data['mensaje_empatico'] == 'Mensaje PluriOne'
    assert data['modo_generacion'] == 'groq'
    create.assert_awaited_once()
    assert create.call_args.kwargs['model'] == 'openai/gpt-oss-20b'
    assert 'reasoning_effort' not in create.call_args.kwargs


@pytest.mark.parametrize('canal', ['Email', 'SMS', 'WhatsApp', 'Llamada'])
def test_comunicacion(client, db, headers, canal, monkeypatch):
    create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content='Mensaje demo'), finish_reason='stop')]))
    monkeypatch.setattr(groq, 'client', SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create)), close=AsyncMock()))
    c = crear_cliente(db)
    agregar_deuda(db, c)
    res = client.post('/api/comunicaciones', headers=headers, json={'cliente_id': c.id, 'canal': canal, 'mensaje': 'Mensaje demo'})
    assert res.status_code == 201
    assert res.json()['simulada'] is True
    assert res.json()['exitoso'] is False
    registro = db.get(models.Comunicacion, res.json()['id'])
    assert registro.canal == canal
    assert registro.fecha_envio == date.today()


def test_validaciones(client, headers, monkeypatch):
    assert client.post('/api/comunicaciones', headers=headers, json={'cliente_id': 1, 'canal': 'Fax', 'mensaje': 'x'}).status_code == 422
    assert client.post('/api/comunicaciones', headers=headers, json={'cliente_id': 1, 'canal': 'Email', 'mensaje': '  '}).status_code == 422
    assert client.post('/api/comunicaciones', headers=headers, json={'cliente_id': 999, 'canal': 'Email', 'mensaje': 'x'}).status_code == 404
    monkeypatch.setattr(riesgo, '_modelo_riesgo', None)
    assert client.post('/ia/calcular-riesgo/1', headers=headers).status_code == 404


def test_modelo_existente(client, db, headers):
    c = crear_cliente(db)
    agregar_deuda(db, c)
    assert riesgo._modelo_riesgo is not None
    res = client.post(f'/ia/calcular-riesgo/{c.id}', headers=headers)
    assert res.status_code == 200
    assert 0 <= res.json()['score_riesgo'] <= 1
