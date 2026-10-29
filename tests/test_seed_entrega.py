"""Seed demo con SQLAlchemy aislado y el bundle aprobado, sin base operativa."""
from datetime import date
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import auth, database, main, models
from scripts import seed_entrega
from scripts.validar_base_demo import comprobar_inferencia_demo, comprobar_canales_demo


@pytest.fixture
def demo(tmp_path, monkeypatch):
    # Archivo local nuevo para conservar datos tras engine.dispose() del seed.
    engine = create_engine(f'sqlite:///{tmp_path / "demo.sqlite"}')
    sesiones = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(database, 'engine', engine)
    monkeypatch.setattr(database, 'SessionLocal', sesiones)
    monkeypatch.setattr(main, 'engine', engine)
    for nombre in ('PYTHON_DOTENV_DISABLED', 'DATABASE_URL', 'COMMUNICATIONS_REAL_ENABLED'):
        monkeypatch.setenv(nombre, os.environ.get(nombre, ''))
    # Se ejecuta también la protección real de URL; solo el motor se sustituye
    # por SQLite en estos tests. La restauración PostgreSQL se prueba aparte.
    with tempfile.TemporaryDirectory(prefix='motor-entrega-') as carpeta:
        url = f'postgresql+psycopg2://demo_entrega@/motor_cobranza_entrega_tmp?host={carpeta}&port=55439'
        seed_entrega.poblar(url, date(2026, 10, 6))
        def get_db():
            with sesiones() as db:
                yield db
        main.app.dependency_overrides[main.get_db] = get_db
        main.app.dependency_overrides[auth.get_entra_user] = lambda: {'oid': 'demo-test'}
        with sesiones() as db, TestClient(main.app) as cliente:
            yield db, cliente, url
        main.app.dependency_overrides.clear()
    engine.dispose()


def test_seed_modelo_conteos_backend_y_prioridad(demo):
    db, cliente, _ = demo
    filas = comprobar_inferencia_demo(db, cliente)
    esperados = [(models.Cliente, 15), (models.Deuda, 23), (models.Pago, 40),
                 (models.HistorialMensaje, 24), (models.Comunicacion, 24),
                 (models.MetricaSnapshot, 15), (models.Administrador, 0)]
    assert all(db.query(tabla).count() == cantidad for tabla, cantidad in esperados)
    assert {f['segmento'] for f in filas} == {'Bajo riesgo', 'Riesgo medio', 'Alto riesgo', 'No definido', 'Sin deuda'}
    for c in db.query(models.Cliente):
        assert c.email == f'cliente{c.id:02d}@example.invalid'
        assert c.telefono is None
    for c in db.query(models.Comunicacion):
        assert c.modo == 'simulado' and c.exitoso is False
        assert all(getattr(c, nombre) is None for nombre in ('provider', 'external_id', 'error_tecnico', 'provider_status'))
    for d in db.query(models.Deuda):
        pagos = db.query(models.Pago).filter_by(deuda_id=d.id).all()
        assert d.monto_total == pytest.approx(d.saldo_pendiente + sum(p.monto for p in pagos))
        assert all(p.cliente_id == d.cliente_id and p.dias_atraso == (p.fecha_pago - p.fecha_vencimiento).days for p in pagos)


@pytest.mark.parametrize('campo,valor', [('score_riesgo', .15), ('probabilidad_pago_a_tiempo', .85), ('segmento', 'Alto riesgo')])
def test_validador_rechaza_scores_manuales(demo, campo, valor):
    db, cliente, _ = demo
    setattr(db.get(models.Cliente, 1), campo, valor)
    db.commit()
    with pytest.raises(AssertionError):
        comprobar_inferencia_demo(db, cliente)


def test_validador_rechaza_probabilidad_deuda_incoherente(demo):
    db, cliente, _ = demo
    db.get(models.Deuda, 1).probabilidad_pago = .85
    db.commit()
    with pytest.raises(AssertionError):
        comprobar_inferencia_demo(db, cliente)


def test_seed_rechaza_destino_no_vacio(demo):
    db, _, url = demo
    with pytest.raises(ValueError, match='completamente vacía'):
        seed_entrega.poblar(url, date(2026, 10, 6))
    assert db.query(models.Cliente).count() == 15


@pytest.mark.parametrize('url', [
    'postgresql+psycopg2://demo_entrega@localhost/motor_cobranza_entrega_tmp',
    'postgresql+psycopg2://demo_entrega@/operativa?host=/tmp/motor-entrega-prueba',
    'postgresql+psycopg2://demo_entrega:secreto@/motor_cobranza_entrega_tmp?host=/tmp/motor-entrega-prueba',
    'sqlite://',
])
def test_proteccion_url_rechaza_destinos_ajenos(url):
    with pytest.raises(ValueError, match='Destino rechazado'):
        seed_entrega.preparar_entorno(url)


def test_evaluar_cartera_demo_13_14(demo, monkeypatch):
    from unittest.mock import AsyncMock, Mock
    from types import SimpleNamespace
    from app.services import comunicaciones, groq as groq_service, riesgo, twilio_service, sendgrid_service
    db, cliente, _ = demo
    groq = AsyncMock()
    monkeypatch.setattr(groq_service, 'client', SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=groq)), close=AsyncMock()))
    externos = []
    for modulo, nombre in [(comunicaciones, 'registrar'), (twilio_service, 'enviar_mensaje'),
                           (twilio_service, 'enviar_llamada'), (sendgrid_service, 'enviar_email')]:
        funcion = Mock(side_effect=AssertionError('Llamada externa prohibida'))
        monkeypatch.setattr(modulo, nombre, funcion)
        externos.append(funcion)
    clases = [models.Deuda, models.Pago, models.HistorialMensaje, models.Comunicacion]
    def snapshot(clase):
        return [tuple(getattr(f, c.name) for c in clase.__table__.columns) for f in db.query(clase).order_by(clase.id)]
    antes = {clase: snapshot(clase) for clase in clases}
    cartera_antes = cliente.get('/api/cartera-priorizada').json()
    assert {c['cliente_id'] for c in cartera_antes[-2:]} == {13, 14}
    esperados = {}
    for id_ in (13, 14):
        c = db.get(models.Cliente, id_)
        assert c.score_riesgo is None
        esperados[id_] = riesgo.recalcular_riesgo(db, c)
    db.rollback()
    datos = cliente.post('/api/cartera/evaluar').json()
    assert datos['clientes_activos_encontrados'] == 14
    assert datos['clientes_evaluados'] == 2
    assert datos['clientes_ya_evaluados_omitidos'] == 12
    assert datos['clientes_fallidos'] == 0
    db.expire_all()
    cartera_despues = cliente.get('/api/cartera-priorizada').json()
    for id_ in (13, 14):
        c = next(c for c in cartera_despues if c['cliente_id'] == id_)
        for campo in ('score_riesgo', 'probabilidad_pago_a_tiempo', 'segmento'):
            assert c[campo] == esperados[id_][campo]
        assert c['prioridad'] == round(c['score_riesgo'] * c['saldo_pendiente'], 2)
        assert c['prioridad'] > 0
    assert [c['prioridad'] for c in cartera_despues] == sorted((c['prioridad'] for c in cartera_despues), reverse=True)
    assert [c['cliente_id'] for c in cartera_antes] != [c['cliente_id'] for c in cartera_despues]
    assert {clase: snapshot(clase) for clase in clases} == antes
    assert db.get(models.Cliente, 15).score_riesgo is None
    assert cliente.post('/api/cartera/evaluar').json()['clientes_evaluados'] == 0
    groq.assert_not_awaited()
    for funcion in externos:
        funcion.assert_not_called()


def test_canales_demo_reproducibles_sin_duplicar_pago(demo):
    db, cliente, _ = demo
    filas = comprobar_canales_demo(db, cliente, hoy=date(2026, 10, 6))
    assert [f['canal'] for f in filas[:3]] == ['SMS', 'WhatsApp', 'Email']
    assert all(f['score_ganador'] == 5 and f['pagos_asociados'] == 1 for f in filas[:3])
    assert all(f['canal'] is None for f in filas[3:])
    # El contacto y su estrategia ficticia conservan fecha y cliente coherentes.
    for c in db.query(models.Comunicacion):
        assert c.estrategia.cliente_id == c.cliente_id
        assert c.estrategia.fecha_creacion.date() == c.fecha_envio


def test_validador_rechaza_escenario_canal_roto(demo):
    db, cliente, _ = demo
    contacto = db.query(models.Comunicacion).filter_by(cliente_id=1).first()
    contacto.canal = 'Email'
    db.commit()
    with pytest.raises(AssertionError):
        comprobar_canales_demo(db, cliente, hoy=date(2026, 10, 6))
