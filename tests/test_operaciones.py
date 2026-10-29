from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import create_engine, text, inspect
from app import main, models, seed
from app.ml import seed_historial
from app.migrate import migrar
from app.services import comunicaciones, groq as groq_service, riesgo


@pytest.fixture
def cartera(db):
    c = models.Cliente(nombre='Ana Ficticia', email='ana@example.invalid')
    otro = models.Cliente(nombre='Ana Ficticia', email='otra@example.invalid', segmento='Alto riesgo', score_riesgo=.8)
    db.add_all([c, otro]); db.flush()
    for persona, dias in [(c, -10), (c, 20), (otro, 0)]:
        db.add(models.Deuda(cliente_id=persona.id, monto_total=1000, saldo_pendiente=1000,
                            fecha_vencimiento=date.today() + timedelta(days=dias), estatus='Pendiente'))
    db.commit()
    return c, otro


def groq(monkeypatch, contenido='Estrategia de prueba — Cobranza Inteligente PluriOne', error=None):
    create = AsyncMock(side_effect=error, return_value=SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=contenido), finish_reason='stop')]))
    monkeypatch.setattr(groq_service, 'client', SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock()))
    return create


@pytest.mark.parametrize('contenido,error', [('', None), ('   ', None), (None, None), ('x', RuntimeError('privado'))])
def test_groq_error_sin_historial(client, db, headers, cartera, monkeypatch, contenido, error):
    groq(monkeypatch, contenido, error)
    res = client.post(f'/ia/analizar-riesgo/{cartera[0].id}', headers=headers)
    assert res.status_code == 502
    assert 'privado' not in res.text
    assert db.query(models.HistorialMensaje).count() == 0
    assert db.get(models.Cliente, cartera[0].id).segmento == 'No definido'


def test_contexto_reutilizacion_y_distinct(client, db, headers, cartera, monkeypatch):
    create = groq(monkeypatch)
    c, otro = cartera
    url = f'/ia/analizar-riesgo/{c.id}'
    assert client.post(url, headers=headers).status_code == 200
    assert client.post(url, headers=headers).json()['reutilizada'] is True
    assert create.await_count == 1
    contexto = create.call_args.kwargs['messages'][1]['content']
    for campo in ['features_usadas', 'score_riesgo', 'segmento', 'fecha_vencimiento', 'dias_atraso', 'pagos_recientes', 'probabilidad_pago_a_tiempo']:
        assert campo in contexto
    for secreto in ['hashed_password', 'email', 'telefono', 'Authorization', 'JWT']:
        assert secreto not in contexto
    assert client.post(url + '?regenerar=true', headers=headers).json()['reutilizada'] is False
    assert db.query(models.HistorialMensaje).count() == 2
    assert client.get('/api/metricas', headers=headers).json()['estrategias_ia'] == 1
    assert client.post(f'/ia/analizar-riesgo/{otro.id}', headers=headers).status_code == 200
    assert client.get('/api/metricas', headers=headers).json()['estrategias_ia'] == 2
    assert client.post(f'/api/deudas/{c.deudas[0].id}/pagos', headers=headers, json={'monto': 10}).status_code == 201
    assert client.post(url, headers=headers).json()['reutilizada'] is True
    assert client.post(url + '?regenerar=true', headers=headers).json()['reutilizada'] is False


def test_estrategia_heredada_conservada_sin_llamada(client, db, headers, cartera, monkeypatch):
    c = cartera[0]
    db.add(models.HistorialMensaje(cliente_id=c.id, monto_al_momento=2000, mensaje_generado='Registro antiguo'))
    db.commit()
    create = groq(monkeypatch)
    res = client.post(f'/ia/analizar-riesgo/{c.id}', headers=headers)
    assert res.status_code == 200
    assert res.json()['reutilizada'] is True
    assert res.json()['modo_generacion'] == 'historico'
    create.assert_not_awaited()


@pytest.mark.parametrize('query,cantidad', [('aNa', 2), ('1', 1), ('cl-000001', 1), ('No existe', 0), ('%', 0)])
def test_busqueda(client, headers, cartera, query, cantidad):
    res = client.get('/api/clientes', params={'query': query}, headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == cantidad


@pytest.mark.parametrize('params,ids', [({'analizado': 'false'}, [1]), ({'analizado': 'true'}, [2]),
    ({'segmento': 'Alto riesgo'}, [2]), ({'segmento': 'Sin calcular'}, [1]),
    ({'estatus_deuda': 'En Mora'}, [1]), ({'estatus_deuda': 'Pagada'}, [])])
def test_filtros(client, headers, cartera, params, ids):
    assert [c['cliente_id'] for c in client.get('/api/clientes', params=params, headers=headers).json()] == ids
    assert client.get('/api/metricas', headers=headers).json()['clientes_sin_evaluar'] == 1


def test_detalle_fechas(client, headers, cartera):
    data = client.get(f'/api/clientes/{cartera[0].id}', headers=headers).json()
    assert data['folio'] == 'CL-000001'
    assert data['monto_original_total'] == 2000
    assert data['numero_deudas_vencidas'] == 1
    assert data['dias_restantes'] == -10
    assert [d['dias_restantes'] for d in data['deudas']] == [-10, 20]
    assert [d['estatus'] for d in data['deudas']] == ['En Mora', 'Pendiente']
    assert client.get('/api/clientes/9999', headers=headers).status_code == 404


@pytest.mark.parametrize('indice,monto,estado,saldo,atraso', [(0,300,'En Mora',700,10), (0,1000,'Pagada',0,10), (1,300,'Pendiente',700,-20)])
def test_pago_y_modelo(client, db, headers, cartera, monkeypatch, indice, monto, estado, saldo, atraso):
    c = cartera[0]; deuda = c.deudas[indice]
    class Modelo:
        def predict_proba(self, frame):
            assert frame.iloc[0]['num_pagos_historicos'] == 1
            assert frame.iloc[0]['monto_pendiente_actual'] == saldo + 1000
            assert frame.iloc[0]['num_deudas_activas'] == (1 if saldo == 0 else 2)
            return [[.25,.75]]
    monkeypatch.setattr(riesgo, '_modelo_riesgo', Modelo())
    data = client.post(f'/api/deudas/{deuda.id}/pagos', json={'monto': monto}, headers=headers)
    assert data.status_code == 201, data.text
    data = data.json()
    assert data['nuevo_saldo'] == saldo
    assert data['estatus'] == estado
    assert data['score_riesgo'] == .25
    assert data['segmento'] == 'Bajo riesgo'
    assert data['probabilidad_pago_a_tiempo'] == .75
    assert data['pago']['dias_atraso'] == atraso
    db.refresh(deuda); db.refresh(c)
    assert deuda.saldo_pendiente == saldo
    assert deuda.estatus == estado
    assert c.score_riesgo == .25
    pago = db.query(models.Pago).one()
    assert pago.deuda_id == deuda.id and pago.cliente_id == c.id
    assert len(client.get(f'/api/clientes/{c.id}', headers=headers).json()['pagos']) == 1
    if saldo == 0:
        assert client.post(f'/api/deudas/{deuda.id}/pagos', json={'monto': 1}, headers=headers).status_code == 409


@pytest.mark.parametrize('monto', [0, -1, 1001, 'NaN', 'Infinity', '0.001'])
def test_pago_invalido(client, db, headers, cartera, monto):
    d = cartera[0].deudas[0]
    assert client.post(f'/api/deudas/{d.id}/pagos', json={'monto': monto}, headers=headers).status_code == 422
    assert db.query(models.Pago).count() == 0
    assert d.saldo_pendiente == 1000


def test_pago_inexistente_y_rollback(client, db, headers, cartera, monkeypatch):
    assert client.post('/api/deudas/999/pagos', json={'monto': 1}, headers=headers).status_code == 404
    monkeypatch.setattr(riesgo, '_modelo_riesgo', None)
    d = cartera[0].deudas[0]
    assert client.post(f'/api/deudas/{d.id}/pagos', json={'monto': 100}, headers=headers).status_code == 503
    db.refresh(d)
    assert d.saldo_pendiente == 1000
    assert db.query(models.Pago).count() == 0


def test_migracion_aditiva():
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre VARCHAR)'))
        conn.execute(text('CREATE TABLE pagos (id INTEGER PRIMARY KEY, cliente_id INTEGER)'))
        conn.execute(text('CREATE TABLE historial_mensajes (id INTEGER PRIMARY KEY)'))
        conn.execute(text("INSERT INTO clientes (id,nombre) VALUES (1,'Existente')"))
    migrar(engine); migrar(engine)
    assert 'deuda_id' in {c['name'] for c in inspect(engine).get_columns('pagos')}
    with engine.connect() as conn:
        assert conn.execute(text('SELECT nombre FROM clientes')).scalar() == 'Existente'
    assert inspect(engine).get_foreign_keys('pagos')[0]['referred_table'] == 'deudas'
    engine.dispose()


def test_seed_idempotente(db, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    for modulo in [seed, seed_historial]:
        monkeypatch.setattr(modulo, 'migrar', lambda: None)
        monkeypatch.setattr(modulo, 'SessionLocal', sessionmaker(bind=db.get_bind()))
    db.add(models.Cliente(nombre='Ana original', email='ana@ejemplo.com'))
    db.commit()
    seed.poblar_db(); seed_historial.poblar_historial()
    conteos = [db.query(m).count() for m in [models.Cliente, models.Deuda, models.Pago]]
    seed.poblar_db(); seed_historial.poblar_historial()
    assert conteos == [db.query(m).count() for m in [models.Cliente, models.Deuda, models.Pago]]
    assert conteos[0] == 15
    assert db.get(models.Cliente, 1).nombre == 'Ana original'


@pytest.mark.parametrize('metodo,ruta', [('get','/api/clientes'), ('get','/api/clientes/1'), ('post','/api/deudas/1/pagos')])
def test_nuevas_rutas_protegidas(client, metodo, ruta):
    assert getattr(client, metodo)(ruta).status_code == 401


@pytest.mark.parametrize('orden', ['prioridad', 'saldo', 'atraso', 'vencimiento', 'nombre'])
def test_ordenes(client, headers, cartera, orden):
    filas = client.get('/api/clientes', params={'orden': orden}, headers=headers).json()
    assert len(filas) == 2
    assert filas[0]['cliente_id'] == (2 if orden == 'prioridad' else 1)


def test_pago_hoy_con_modelo_real(client, db, headers, cartera):
    c = cartera[1]
    res = client.post(f'/api/deudas/{c.deudas[0].id}/pagos', json={'monto': '0.01'}, headers=headers)
    assert res.status_code == 201
    assert res.json()['nuevo_saldo'] == 999.99
    assert res.json()['pago']['dias_atraso'] == 0
    assert res.json()['estatus'] == 'Pendiente'
    features = riesgo.extraer_features_cliente(db, c)
    expected = riesgo._modelo_riesgo.predict_proba(riesgo.pd.DataFrame([features])[riesgo._columnas_modelo])[0][1]
    assert res.json()['probabilidad_pago_a_tiempo'] == round(float(expected), 3)


def test_groq_truncado(client, db, headers, cartera, monkeypatch):
    create = groq(monkeypatch)
    create.return_value.choices[0].finish_reason = 'length'
    assert client.post(f'/ia/analizar-riesgo/{cartera[0].id}', headers=headers).status_code == 502
    assert db.query(models.HistorialMensaje).count() == 0


def test_migracion_base_nueva():
    engine = create_engine('sqlite://')
    migrar(engine); migrar(engine)
    assert set(main.Base.metadata.tables).issubset(inspect(engine).get_table_names())
    engine.dispose()


def test_ficha_comunicaciones_del_cliente(client, db, headers, cartera):
    c, otro = cartera
    db.add(models.Comunicacion(cliente_id=c.id, canal='SMS', fecha_envio=date.today() - timedelta(days=1),
                              mensaje='Registro histórico', exitoso=True))
    db.add(models.Comunicacion(cliente_id=otro.id, canal='Email', fecha_envio=date.today(),
                              mensaje='Pertenece a otro cliente', exitoso=False))
    db.commit()
    for canal in ['Email', 'WhatsApp']:
        assert client.post('/api/comunicaciones', headers=headers, json={
            'cliente_id': c.id, 'canal': canal, 'mensaje': f'Registro ficticio {canal}',
        }).status_code == 201
    registros = client.get(f'/api/clientes/{c.id}', headers=headers).json()['comunicaciones']
    assert [r['canal'] for r in registros] == ['WhatsApp', 'Email', 'SMS']
    assert registros[0]['simulada'] is True
    assert registros[0]['exitoso'] is False
    assert registros[0]['fecha'] == date.today().isoformat()
    assert registros[0]['mensaje'] == 'Registro ficticio WhatsApp'
    assert registros[2]['simulada'] is False
    assert db.query(models.Comunicacion).count() == 4


def test_ficha_sin_comunicaciones(client, headers, cartera):
    assert client.get(f'/api/clientes/{cartera[0].id}', headers=headers).json()['comunicaciones'] == []


def test_busqueda_apellido_parcial_y_folios_unicos(client, headers, cartera):
    filas = client.get('/api/clientes', params={'query': 'FiCt'}, headers=headers).json()
    assert len(filas) == 2
    assert filas[0]['cliente_nombre'] == filas[1]['cliente_nombre']
    assert {f['folio'] for f in filas} == {'CL-000001', 'CL-000002'}


@pytest.mark.parametrize('con_estrategia', [False, True])
def test_seleccion_solo_consulta(client, db, headers, cartera, monkeypatch, con_estrategia):
    from unittest.mock import Mock
    c = cartera[0]
    create = groq(monkeypatch)
    modelo = Mock()
    monkeypatch.setattr(riesgo, '_modelo_riesgo', modelo)
    if con_estrategia:
        for mensaje in ['Anterior', 'Última almacenada']:
            db.add(models.HistorialMensaje(cliente_id=c.id, monto_al_momento=2000,
                mensaje_generado=mensaje, contexto_hash='a' * 64))
        db.commit()
    cantidad = db.query(models.HistorialMensaje).count()
    for _ in range(2):
        data = client.get(f'/api/clientes/{c.id}', headers=headers).json()
        assert data['tiene_estrategia'] is con_estrategia
        assert data['sin_deuda_activa'] is False
        if con_estrategia:
            assert data['ultima_estrategia']['mensaje'] == 'Última almacenada'
            assert data['fecha_ultima_estrategia']
        else:
            assert data['ultima_estrategia'] is None
            assert data['segmento'] == 'No definido'
    create.assert_not_awaited()
    modelo.predict_proba.assert_not_called()
    assert db.query(models.HistorialMensaje).count() == cantidad


@pytest.mark.parametrize('ruta', ['/api/clientes/{id}', '/ia/calcular-riesgo/{id}', '/ia/analizar-riesgo/{id}', '/ia/analizar-riesgo/{id}?regenerar=true'])
@pytest.mark.parametrize('configurado', [False, True])
def test_sin_deuda_no_modelo_ni_groq(client, db, headers, monkeypatch, ruta, configurado):
    from unittest.mock import Mock
    c = models.Cliente(nombre='Liquidado', score_riesgo=.292, segmento='Bajo riesgo', probabilidad_pago_a_tiempo=.708)
    db.add(c); db.flush()
    db.add(models.Deuda(cliente_id=c.id, monto_total=100, saldo_pendiente=0, fecha_vencimiento=date.today(), estatus='Pagada'))
    db.commit()
    create = groq(monkeypatch) if configurado else None
    modelo = Mock() if configurado else None
    monkeypatch.setattr(riesgo, '_modelo_riesgo', modelo)
    metodo = client.get if ruta.startswith('/api') else client.post
    res = metodo(ruta.format(id=c.id), headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data['sin_deuda_activa'] is True
    assert data['saldo_pendiente'] == 0
    assert data['probabilidad_pago_a_tiempo'] is None
    assert data['score_riesgo'] is None
    assert data['segmento'] == 'Sin deuda'
    if configurado:
        create.assert_not_awaited(); modelo.predict_proba.assert_not_called()
    assert db.query(models.HistorialMensaje).count() == 0
    if metodo == client.post:
        db.refresh(c)
        assert c.score_riesgo is None and c.segmento == 'Sin deuda'
    else:
        # GET no modifica datos históricos aunque oculte una predicción obsoleta.
        assert c.score_riesgo == .292
    assert client.get('/api/cartera-priorizada', headers=headers).json() == []
    assert client.get('/api/clientes?solo_con_deuda=true', headers=headers).json() == []
    assert len(client.get('/api/clientes', headers=headers).json()) == 1
    assert client.get('/api/metricas', headers=headers).json()['deudores_activos'] == 0


def test_liquidar_ultima_deuda_sin_modelo(client, db, headers, cartera, monkeypatch):
    c = cartera[1]
    monkeypatch.setattr(riesgo, '_modelo_riesgo', None)
    create = groq(monkeypatch)
    assert client.get('/api/metricas', headers=headers).json()['deudores_activos'] == 2
    res = client.post(f'/api/deudas/{c.deudas[0].id}/pagos', json={'monto': 1000}, headers=headers)
    assert res.status_code == 201
    assert res.json()['sin_deuda_activa'] is True
    assert res.json()['estatus'] == 'Pagada'
    assert res.json()['score_riesgo'] is None
    db.refresh(c)
    assert c.score_riesgo is None
    assert c.probabilidad_pago_a_tiempo is None
    assert c.segmento == 'Sin deuda'
    assert db.query(models.Pago).count() == 1
    assert client.get('/api/metricas', headers=headers).json()['deudores_activos'] == 1
    assert [r['cliente_id'] for r in client.get('/api/cartera-priorizada', headers=headers).json()] == [cartera[0].id]
    assert client.get(f'/api/clientes/{c.id}', headers=headers).json()['sin_deuda_activa'] is True
    create.assert_not_awaited()


@pytest.mark.parametrize('segmento', ['No definido', 'Sin calcular'])
def test_filtro_sin_calcular_incluye_segmento_nulo(client, db, headers, cartera, segmento):
    c, otro = cartera
    db.query(models.Cliente).filter_by(id=otro.id).update({'segmento': None})
    db.commit()
    resultado = client.get('/api/clientes', params={'segmento': segmento}, headers=headers)
    assert resultado.status_code == 200
    assert {fila['cliente_id'] for fila in resultado.json()} == {c.id, otro.id}
    assert client.get('/api/metricas', headers=headers).json()['clientes_sin_evaluar'] == 2


def test_historial_fecha_nula_no_desplaza_estrategia_fechada(client, db, headers, cartera, monkeypatch):
    from datetime import datetime
    c = cartera[0]
    fechado = models.HistorialMensaje(cliente_id=c.id, monto_al_momento=2000,
        mensaje_generado='Estrategia fechada', fecha_creacion=datetime(2026, 10, 2, 12))
    sin_fecha = models.HistorialMensaje(cliente_id=c.id, monto_al_momento=2000,
        mensaje_generado='Histórico sin fecha')
    db.add_all([fechado, sin_fecha])
    db.flush()
    db.query(models.HistorialMensaje).filter_by(id=sin_fecha.id).update({'fecha_creacion': None})
    db.commit()
    create = groq(monkeypatch)
    historial = client.get(f'/ia/historial/{c.id}', headers=headers).json()
    assert [fila['id'] for fila in historial] == [fechado.id, sin_fecha.id]
    assert historial[1]['fecha_creacion'] is None
    detalle = client.get(f'/api/clientes/{c.id}', headers=headers).json()
    assert detalle['ultima_estrategia']['mensaje'] == 'Estrategia fechada'
    estrategia = client.post(f'/ia/analizar-riesgo/{c.id}', headers=headers).json()
    assert estrategia['historial_id'] == fechado.id
    create.assert_not_awaited()


@pytest.mark.parametrize('canal', ['Email', 'SMS', 'WhatsApp', 'Llamada'])
def test_sin_deuda_no_comunicacion_de_cobranza(client, db, headers, monkeypatch, canal):
    from unittest.mock import Mock
    c = models.Cliente(nombre='Liquidado')
    db.add(c)
    db.flush()
    db.add(models.Deuda(cliente_id=c.id, monto_total=100, saldo_pendiente=0,
        fecha_vencimiento=date.today(), estatus='Pagada'))
    db.commit()
    create = groq(monkeypatch)
    registrar = Mock(side_effect=AssertionError('No contactar cliente liquidado'))
    monkeypatch.setattr(comunicaciones, 'registrar', registrar)
    resultado = client.post('/api/comunicaciones', headers=headers,
        json={'cliente_id': c.id, 'canal': canal, 'mensaje': 'Mensaje de cobranza'})
    assert resultado.status_code == 409
    create.assert_not_awaited()
    registrar.assert_not_called()
    assert db.query(models.Comunicacion).count() == 0


def test_groq_recibe_recomendacion_sin_propuesta_financiera_y_prompt_restringido(client, db, headers, cartera, monkeypatch):
    import json
    from app.services.recomendacion import recomendar_cliente
    create = groq(monkeypatch)
    c = cartera[0]  # atraso 10 días -> Recordatorio de pago (sin propuestas financieras)
    res = client.post(f'/ia/analizar-riesgo/{c.id}', headers=headers)
    assert res.status_code == 200
    create.assert_awaited_once()
    mensajes = create.call_args.kwargs['messages']
    system_prompt = mensajes[0]['content']
    payload = json.loads(mensajes[1]['content'])

    db.refresh(c)
    esperada = recomendar_cliente(c)
    assert esperada['tipo'] != 'Propuesta de plan de pagos'
    assert 'recomendacion_recuperacion' in payload
    assert payload['recomendacion_recuperacion'] == esperada
    assert 'propuesta_pronto_pago' not in payload['recomendacion_recuperacion']
    assert 'propuesta_plan_pagos' not in payload['recomendacion_recuperacion']

    assert 'solo redacta' in system_prompt.lower()
    assert 'no decides condiciones financieras' in system_prompt.lower()
    assert 'no inventes descuentos' in system_prompt.lower()
    assert 'no inventes plazos' in system_prompt.lower()
    assert 'no inventes cuotas' in system_prompt.lower()
    assert 'respetar exactamente los valores proporcionados' in system_prompt.lower()


def test_groq_recibe_propuestas_exactas_en_plan_de_pagos(client, db, headers, monkeypatch):
    import json
    from app.services.recomendacion import recomendar_cliente
    class ModeloBajoRiesgo:
        def predict_proba(self, _frame):
            return [[0.2, 0.8]]
    monkeypatch.setattr(riesgo, '_modelo_riesgo', ModeloBajoRiesgo())
    c = models.Cliente(nombre='Cliente Plan Pagos', email='plan@example.invalid')
    db.add(c)
    db.flush()
    db.add(models.Deuda(cliente_id=c.id, monto_total=6000, saldo_pendiente=6000,
                        fecha_vencimiento=date.today() - timedelta(days=45), estatus='En Mora'))
    db.commit()

    create = groq(monkeypatch)
    res = client.post(f'/ia/analizar-riesgo/{c.id}', headers=headers)
    assert res.status_code == 200
    create.assert_awaited_once()
    payload = json.loads(create.call_args.kwargs['messages'][1]['content'])

    db.refresh(c)
    esperada = recomendar_cliente(c)
    assert esperada['tipo'] == 'Propuesta de plan de pagos'
    rec = payload['recomendacion_recuperacion']
    assert rec == esperada

    assert 'propuesta_pronto_pago' in rec
    for clave in ('porcentaje_descuento', 'descuento', 'saldo_propuesto', 'vigencia_dias'):
        assert clave in rec['propuesta_pronto_pago']
    assert 'propuesta_plan_pagos' in rec
    assert 'opciones' in rec['propuesta_plan_pagos']
    assert len(rec['propuesta_plan_pagos']['opciones']) > 0
    for opcion in rec['propuesta_plan_pagos']['opciones']:
        assert 'meses' in opcion
        assert 'cuota_mensual' in opcion
