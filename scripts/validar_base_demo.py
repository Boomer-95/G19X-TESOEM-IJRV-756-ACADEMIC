"""Valida exclusivamente la base restaurada de entrega en el socket temporal."""
import json
from datetime import date, timedelta
import os
from pathlib import Path
import re
import socket
import sys


def comprobar_inferencia_demo(db, cliente_http):
    """Contrasta SQL restaurado, inferencia real y respuestas del backend."""
    from app import main, models
    from app.ml.features import FEATURE_COLUMNS, extraer_features_cliente
    from app.services.analitica import cartera_actual

    assert main._modelo_riesgo is not None
    assert main._columnas_modelo == FEATURE_COLUMNS
    clientes = db.query(models.Cliente).order_by(models.Cliente.id).all()
    assert len(clientes) == 15
    respuesta = cliente_http.get('/api/clientes')
    assert respuesta.status_code == 200
    listado = {c['cliente_id']: c for c in respuesta.json()}
    filas = []
    for c in clientes:
        saldo = sum(d.saldo_pendiente for d in c.deudas if d.saldo_pendiente > 0)
        if c.id in (13, 14):
            probabilidad = score = None
            segmento = 'No definido'
        elif saldo == 0:
            probabilidad = score = None
            segmento = 'Sin deuda'
        else:
            features = extraer_features_cliente(db, c)
            frame = main.pd.DataFrame([features])[FEATURE_COLUMNS]
            p = float(main._modelo_riesgo.predict_proba(frame)[0][1])
            probabilidad, score = round(p, 3), round(1 - p, 3)
            segmento = ('Bajo riesgo' if score < .33 else
                        'Riesgo medio' if score < .66 else 'Alto riesgo')
        assert (c.probabilidad_pago_a_tiempo, c.score_riesgo, c.segmento) == (probabilidad, score, segmento), c.id
        for d in c.deudas:
            assert d.probabilidad_pago == (probabilidad if d.saldo_pendiente > 0 else None), d.id
        prioridad = round((score or 0) * saldo, 2)
        detalle = cliente_http.get(f'/api/clientes/{c.id}')
        assert detalle.status_code == 200
        for dato in (listado[c.id], detalle.json()):
            assert dato['folio'] == f'CL-{c.id:06d}'
            assert (dato['probabilidad_pago_a_tiempo'], dato['score_riesgo'], dato['segmento']) == (probabilidad, score, segmento)
            assert dato['saldo_pendiente'] == saldo
            assert dato['prioridad'] == prioridad
        filas.append(dict(id=c.id, folio=f'CL-{c.id:06d}', probabilidad=probabilidad,
                          score=score, segmento=segmento, saldo=saldo, prioridad=prioridad))
    cartera = cliente_http.get('/api/cartera-priorizada')
    assert cartera.status_code == 200
    cartera = cartera.json()
    activas = [f for f in filas if f['saldo'] > 0]
    assert {c['cliente_id'] for c in cartera} == {f['id'] for f in activas}
    assert [c['prioridad'] for c in cartera] == sorted((f['prioridad'] for f in activas), reverse=True)
    for c in cartera:
        assert c['prioridad'] == next(f['prioridad'] for f in filas if f['id'] == c['cliente_id'])
    assert {c['cliente_id'] for c in cartera[-2:]} == {13, 14}
    sin_evaluar = cliente_http.get('/api/clientes?analizado=false')
    assert sin_evaluar.status_code == 200
    assert {c['cliente_id'] for c in sin_evaluar.json()} == {13, 14}
    bajos = cliente_http.get('/api/clientes?segmento=Bajo%20riesgo')
    assert bajos.status_code == 200
    assert not {13, 14, 15} & {c['cliente_id'] for c in bajos.json()}
    # Cobertura explícita de los cinco casos de aceptación.
    assert filas[0]['segmento'] == 'Bajo riesgo'
    assert filas[4]['segmento'] == 'Riesgo medio'
    assert filas[2]['segmento'] == 'Alto riesgo'
    assert filas[12]['score'] is None and filas[12]['segmento'] == 'No definido'
    assert filas[14]['saldo'] == 0 and filas[14]['segmento'] == 'Sin deuda'
    actual = cartera_actual(db)
    snapshot = db.query(models.MetricaSnapshot).order_by(models.MetricaSnapshot.fecha.desc()).first()
    assert snapshot.clientes_alto_riesgo == actual['clientes_alto_riesgo']
    assert snapshot.deudores_activos == actual['deudores_activos']
    resumen = cliente_http.get('/api/analitica/resumen?dias=30')
    assert resumen.status_code == 200
    assert resumen.json()['clientes_alto_riesgo'] == actual['clientes_alto_riesgo']
    return filas


def comprobar_canales_demo(db, cliente_http, *, hoy=None):
    """Escenarios sintéticos: regla aprobada intacta, sin escrituras ni envíos."""
    from app import models
    from app.services.canal_sugerido import sugerir_canal

    filas = []
    for c in db.query(models.Cliente).order_by(models.Cliente.id):
        r = sugerir_canal(c, hoy=hoy)
        assert r['ventana_pago_dias'] == 7
        respuesta = cliente_http.get(f'/api/clientes/{c.id}')
        assert respuesta.status_code == 200
        # Comparar todos los campos tras serializar las fechas para JSON.
        assert respuesta.json()['canal_sugerido'] == json.loads(json.dumps(r, default=str))
        canal = r['canal']
        datos = r['estadisticas'].get(canal, {})
        if c.id in (1, 2, 3):
            esperado = {1: 'SMS', 2: 'WhatsApp', 3: 'Email'}[c.id]
            assert canal == esperado, c.id
            assert r['fuente_evidencia'] == 'simulada' and r['confianza'] == 'baja'
            assert datos['comunicaciones_evaluables'] == 2
            assert datos['score_interno'] == 5
            assert datos['pagos_asociados_temporalmente'] == 1
            contactos = sorted(c.comunicaciones, key=lambda x: (x.fecha_envio, x.id))
            assert len(contactos) == 2 and all(x.canal == esperado for x in contactos)
            asociados = [p for p in c.pagos if p.fecha_pago is not None
                         and 0 <= (p.fecha_pago - contactos[-1].fecha_envio).days <= 7]
            assert len(asociados) == 1
            assert contactos[0].fecha_envio < contactos[1].fecha_envio < asociados[0].fecha_pago
            assert sum(d['pagos_asociados_temporalmente'] for d in r['estadisticas'].values()) == 1
        else:
            assert canal is None and r['estado'] == 'Sin evidencia suficiente', c.id
            assert r['confianza'] == 'insuficiente'
            assert r['fuente_evidencia'] == ('simulada' if c.id <= 12 else 'sin_datos')
        for contacto in c.comunicaciones:
            assert contacto.modo == 'simulado' and contacto.estado == 'Simulado'
            assert contacto.exitoso is False
            assert contacto.provider_status is None and contacto.provider is None
        assert all(d['entregadas_o_leidas'] == d['leidas'] == d['fallidas_o_no_entregadas'] == 0
                   for d in r['estadisticas'].values())
        filas.append(dict(id=c.id, canal=canal, confianza=r['confianza'],
                          fuente=r['fuente_evidencia'], score_ganador=datos.get('score_interno'),
                          pagos_asociados=sum(d['pagos_asociados_temporalmente'] for d in r['estadisticas'].values())))
    assert len(filas) == 15
    return filas


def validar(url, archivo):
    from sqlalchemy.engine import make_url
    destino = make_url(url)
    if destino.database != 'motor_cobranza_validacion_tmp':
        raise ValueError('Solo se admite la base temporal de validación.')
    from seed_entrega import preparar_entorno
    preparar_entorno(destino.set(database='motor_cobranza_entrega_tmp').render_as_string(hide_password=False))
    os.environ['DATABASE_URL'] = url
    # Revisión del SQL sin imprimir coincidencias potencialmente sensibles.
    sql = Path(archivo).read_text()
    prohibidos = [r'Bearer\s+\S+', r'(?:TWILIO_AUTH_TOKEN|SENDGRID_API_KEY|GROQ_API_KEY|CLIENT_SECRET)',
                  r'\b(?:AC|SM|MM|SK)[a-fA-F0-9]{32}\b', r'\b(?:sk-|gsk_|SG\.)[A-Za-z0-9_-]+',
                  r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', r'\+[1-9][0-9]{7,14}',
                  r'OWNER TO', r'^(?:GRANT|REVOKE) ', r'postgres(?:ql)?://']
    if any(re.search(p, sql, re.I | re.M) for p in prohibidos):
        raise ValueError('Revisión de seguridad SQL fallida; contenido no mostrado.')
    correos = re.findall(r'[\w.+-]+@[\w.-]+', sql)
    if len(correos) != 15 or any(not re.fullmatch(r'cliente\d{2}@example\.invalid', c) for c in correos):
        raise ValueError('Correos del dump fuera de la lista ficticia permitida.')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sqlalchemy import inspect, text
    from app.database import engine, Base, get_db
    from app import models  # noqa: F401
    esperados = dict(clientes=15, deudas=23, pagos=40, historial_mensajes=24,
                     comunicaciones=24, metricas_snapshots=15, administradores=0)
    with engine.connect() as conn:
        inspector = inspect(conn)
        assert set(inspector.get_table_names()) == set(esperados)
        for nombre, tabla in Base.metadata.tables.items():
            assert {c['name'] for c in inspector.get_columns(nombre)} == set(tabla.columns.keys()), nombre
            fks = {(tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns'])) for f in inspector.get_foreign_keys(nombre)}
            for fk in tabla.foreign_keys:
                assert ((fk.parent.name,), fk.column.table.name, (fk.column.name,)) in fks
            indices = {i['name'] for i in inspector.get_indexes(nombre)}
            assert {i.name for i in tabla.indexes} <= indices
        conteos = {t: conn.scalar(text(f'SELECT count(*) FROM {t}')) for t in esperados}
        assert conteos == esperados, conteos
        comprobaciones = {
            'deuda_vencida': "SELECT count(*) FROM deudas WHERE saldo_pendiente > 0 AND fecha_vencimiento < CURRENT_DATE",
            'deuda_futura': "SELECT count(*) FROM deudas WHERE saldo_pendiente > 0 AND fecha_vencimiento > CURRENT_DATE",
            'sin_evaluar': "SELECT count(*) FROM clientes WHERE segmento = 'No definido' AND score_riesgo IS NULL",
            'estrategias': 'SELECT count(*) FROM historial_mensajes',
            'comunicaciones_con_estrategia': 'SELECT count(*) FROM comunicaciones c JOIN historial_mensajes h ON h.id=c.estrategia_id AND h.cliente_id=c.cliente_id',
            'fechas_snapshots': 'SELECT count(DISTINCT fecha) FROM metricas_snapshots',
        }
        resultados = {k: conn.scalar(text(v)) for k, v in comprobaciones.items()}
        assert all(v > 0 for v in resultados.values()), resultados
        assert resultados['fechas_snapshots'] == 15
        assert conn.scalar(text('SELECT count(*) FROM clientes WHERE telefono IS NOT NULL')) == 0
        assert conn.scalar(text("SELECT count(*) FROM comunicaciones WHERE modo IS DISTINCT FROM 'simulado' OR exitoso IS DISTINCT FROM false OR external_id IS NOT NULL OR provider IS NOT NULL OR provider_status IS NOT NULL OR error_tecnico IS NOT NULL")) == 0
        # Cada deuda cumple monto original = saldo + pagos; no pagos sueltos.
        assert conn.scalar(text('SELECT count(*) FROM pagos WHERE deuda_id IS NULL')) == 0
        assert conn.scalar(text('SELECT count(*) FROM deudas d WHERE abs(d.monto_total - d.saldo_pendiente - COALESCE((SELECT sum(p.monto) FROM pagos p WHERE p.deuda_id=d.id),0)) > 0.01')) == 0
        assert conn.scalar(text('SELECT count(*) FROM pagos p JOIN deudas d ON d.id=p.deuda_id WHERE p.cliente_id<>d.cliente_id OR p.dias_atraso<>p.fecha_pago-p.fecha_vencimiento')) == 0
        # Comprobar estado de secuencias restauradas sin consumir IDs ni insertar datos.
        for tabla in Base.metadata.tables:
            secuencia = conn.scalar(text("SELECT pg_get_serial_sequence(:tabla, 'id')"), {'tabla': tabla})
            assert secuencia
            estado = conn.execute(text(f'SELECT last_value, is_called FROM {secuencia}')).one()
            maximo = conn.scalar(text(f'SELECT COALESCE(max(id), 0) FROM {tabla}'))
            assert estado[0] >= maximo
    # Entra se sustituye SOLO en este TestClient local; jamás se cambian credenciales o código.
    conectar = socket.socket.connect
    def solo_socket_local(sock, address):
        if sock.family != socket.AF_UNIX:
            raise AssertionError('Conexiones externas prohibidas durante validación demo.')
        return conectar(sock, address)
    socket.socket.connect = solo_socket_local
    from fastapi.testclient import TestClient
    from app import main, auth
    main.app.dependency_overrides[auth.get_entra_user] = lambda: {'oid': 'demo-local', 'name': 'Evaluador ficticio'}
    rutas = ['/api/metricas', '/api/clientes', '/api/clientes/1', '/api/cartera-priorizada',
             '/ia/historial/1', '/api/analitica/resumen?dias=30',
             '/api/analitica/canales?dias=30', '/api/analitica/evolucion?dias=30', '/api/integraciones/estado']
    estados = {}
    # Los GET de evolución hacen upsert de snapshots: aislar también esos
    # efectos y deshacerlos al acabar, conservando los conteos del dump.
    from sqlalchemy.orm import sessionmaker
    conexion_backend = engine.connect()
    transaccion_backend = conexion_backend.begin()
    SesionValidacion = sessionmaker(bind=conexion_backend, join_transaction_mode='create_savepoint')
    def db_validacion():
        with SesionValidacion() as db:
            yield db
    main.app.dependency_overrides[get_db] = db_validacion
    try:
        # Sin lifespan: la validación no crea tablas; el SQL es la única fuente del esquema.
        cliente = TestClient(main.app)
        with SesionValidacion() as db:
            inferencias = comprobar_inferencia_demo(db, cliente)
            canales_demo = comprobar_canales_demo(db, cliente)
        for ruta in rutas:
            respuesta = cliente.get(ruta)
            assert respuesta.status_code == 200, (ruta, respuesta.status_code)
            estados[ruta] = respuesta.status_code
            if '/resumen?' in ruta:
                assert respuesta.json()['monto_recuperado_post_ia'] == 0
            if '/evolucion?' in ruta:
                with SesionValidacion() as db:
                    fechas = [s.fecha.isoformat() for s in db.query(models.MetricaSnapshot).filter(
                        models.MetricaSnapshot.fecha.between(date.today() - timedelta(days=29), date.today())
                    ).order_by(models.MetricaSnapshot.fecha)]
                assert [fila['fecha'] for fila in respuesta.json()] == fechas
                assert fechas
        cliente.close()
    finally:
        main.app.dependency_overrides.clear()
        transaccion_backend.rollback()
        conexion_backend.close()
        socket.socket.connect = conectar
        engine.dispose()
    with engine.connect() as conn:
        conteos_finales = {t: conn.scalar(text(f'SELECT count(*) FROM {t}')) for t in esperados}
        assert conteos_finales == esperados, conteos_finales
    engine.dispose()
    print(json.dumps({'conteos_importados': conteos, 'comprobaciones': resultados,
                      'conteos_tras_backend': conteos_finales, 'endpoints': estados, 'inferencia_y_prioridad': inferencias, 'canales_sugeridos_demo': canales_demo, 'seguridad_sql': 'OK'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    validar(sys.argv[1], sys.argv[2])
