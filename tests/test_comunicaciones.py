from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
from twilio.base.exceptions import TwilioRestException
import pytest
from sqlalchemy import create_engine, text
from app import models
from app.migrate import migrar
from app.services import comunicaciones, groq, mensajes, twilio_service, sendgrid_service
from app.services.mensajes import preparar_sms, validar_sms


@pytest.fixture(autouse=True)
def groq_adaptacion(client, monkeypatch):
    create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content='Mensaje de prueba'), finish_reason='stop')]))
    monkeypatch.setattr(groq, 'client', SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create)), close=AsyncMock()))
    return create


@pytest.fixture
def configurado(monkeypatch):
    valores = {
        'COMMUNICATIONS_REAL_ENABLED': 'true',
        'TWILIO_ACCOUNT_SID': 'sid-ficticio-prueba', 'TWILIO_AUTH_TOKEN': 'token-ficticio-prueba',
        'TWILIO_PHONE_NUMBER': '+12025550101', 'TWILIO_WHATSAPP_NUMBER': 'whatsapp:+12025550102',
        'SENDGRID_API_KEY': 'clave-ficticia-prueba', 'SENDGRID_FROM_EMAIL': 'demo@example.com',
    }
    for nombre, valor in valores.items():
        monkeypatch.setenv(nombre, valor)
    twilio = Mock()
    twilio.return_value.messages.create.return_value = SimpleNamespace(sid='mock-message-id', status='queued')
    sendgrid = Mock()
    sendgrid.return_value.client.mail.send.post.return_value = SimpleNamespace(status_code=202, headers={'X-Message-Id': 'mock-email-id'})
    monkeypatch.setattr(twilio_service, 'Client', twilio)
    monkeypatch.setattr(sendgrid_service, 'SendGridAPIClient', sendgrid)
    return twilio, sendgrid


@pytest.fixture
def contacto(db):
    c = models.Cliente(nombre='Prueba', email='cliente@example.com', telefono='+12025550103')
    db.add(c)
    db.flush()
    db.add(models.Deuda(cliente_id=c.id, monto_total=100, saldo_pendiente=100))
    db.commit()
    return c


def enviar(client, headers, contacto, canal):
    return client.post('/api/comunicaciones', headers=headers,
                       json={'cliente_id': contacto.id, 'canal': canal, 'mensaje': 'Mensaje de prueba'})


@pytest.mark.parametrize('numero,esperado', [
    ('+525500000000', '+5215500000000'),
    ('+5215500000000', '+5215500000000'),
    ('+12025550103', '+12025550103'),
    ('+34600000000', '+34600000000'),
])
def test_normalizar_destino_whatsapp(numero, esperado):
    assert twilio_service.normalizar_destino_whatsapp(numero) == esperado
    assert twilio_service.normalizar_destino_whatsapp(esperado) == esperado


@pytest.mark.parametrize('numero', [None, '525500000000', '+52 5500000000',
                                  'whatsapp:+525500000000'])
def test_normalizar_whatsapp_rechaza_formato_invalido(numero):
    with pytest.raises(ValueError, match='E.164'):
        twilio_service.normalizar_destino_whatsapp(numero)


@pytest.mark.parametrize('numero,alias', [
    ('+525500000000', '+5215500000000'),
    ('+5215500000000', '+5215500000000'),
    ('+12025550103', '+12025550103'),
])
@pytest.mark.parametrize('canal', ['SMS', 'WhatsApp'])
def test_destino_por_canal_sin_modificar_cliente(client, db, headers, contacto,
                                              configurado, groq_adaptacion,
                                              monkeypatch, numero, alias, canal):
    contacto.telefono = numero
    db.commit()
    original = 'Mensaje original largo sin modificar.\n' * 10
    breve = groq_adaptacion.return_value.choices[0].message.content
    if canal == 'SMS':
        def prohibir_normalizacion(_):
            raise AssertionError('SMS no debe normalizar el destino para WhatsApp')
        monkeypatch.setattr(twilio_service, 'normalizar_destino_whatsapp', prohibir_normalizacion)
    res = client.post('/api/comunicaciones', headers=headers, json={
        'cliente_id': contacto.id, 'canal': canal, 'mensaje': original})
    assert res.status_code == 201
    destino = 'whatsapp:' + alias if canal == 'WhatsApp' else numero
    origen = 'whatsapp:+12025550102' if canal == 'WhatsApp' else '+12025550101'
    cuerpo = original if canal == 'WhatsApp' else breve
    configurado[0].return_value.messages.create.assert_called_once_with(
        to=destino, from_=origen, body=cuerpo)
    configurado[1].assert_not_called()
    if canal == 'WhatsApp':
        groq_adaptacion.assert_not_awaited()
    assert res.json()['mensaje'] == cuerpo
    assert db.get(models.Comunicacion, res.json()['id']).mensaje == cuerpo
    db.expire_all()
    assert db.get(models.Cliente, contacto.id).telefono == numero


@pytest.mark.parametrize('canal', ['Email', 'SMS', 'WhatsApp', 'Llamada'])
@pytest.mark.parametrize('interruptor', [None, 'false', '1', 'yes'])
def test_interruptor_fuerza_simulacion(client, headers, contacto, configurado, monkeypatch, canal, interruptor):
    if interruptor is None:
        monkeypatch.delenv('COMMUNICATIONS_REAL_ENABLED')
    else:
        monkeypatch.setenv('COMMUNICATIONS_REAL_ENABLED', interruptor)
    res = enviar(client, headers, contacto, canal)
    assert res.status_code == 201
    assert res.json()['modo'] == 'simulado'
    assert res.json()['estado'] == 'Simulado'
    assert res.json()['exitoso'] is False
    for mock in configurado:
        mock.assert_not_called()
    assert not any(client.get('/api/integraciones/estado', headers=headers).json().values())


@pytest.mark.parametrize('canal,variable', [('Email', 'SENDGRID_API_KEY'), ('Email', 'SENDGRID_FROM_EMAIL'),
    ('SMS', 'TWILIO_AUTH_TOKEN'), ('SMS', 'TWILIO_PHONE_NUMBER'), ('SMS', 'TWILIO_ACCOUNT_SID'),
    ('WhatsApp', 'TWILIO_WHATSAPP_NUMBER')])
def test_configuracion_incompleta(client, headers, contacto, configurado, monkeypatch, canal, variable):
    monkeypatch.delenv(variable)
    assert enviar(client, headers, contacto, canal).json()['estado'] == 'Simulado'
    for mock in configurado:
        mock.assert_not_called()


@pytest.mark.parametrize('canal', ['Email', 'SMS', 'WhatsApp'])
def test_envio_real_mock(client, db, headers, contacto, configurado, canal):
    twilio, sendgrid = configurado
    res = enviar(client, headers, contacto, canal)
    assert res.status_code == 201
    data = res.json()
    assert (data['modo'], data['estado'], data['exitoso'], data['simulada']) == ('real', 'Enviado', True, False)
    registro = db.get(models.Comunicacion, data['id'])
    assert registro.external_id == ('mock-email-id' if canal == 'Email' else 'mock-message-id')
    if canal == 'Email':
        call = sendgrid.return_value.client.mail.send.post
        call.assert_called_once()
        assert call.call_args.kwargs['request_body']['personalizations'][0]['to'][0]['email'] == contacto.email
        assert call.call_args.kwargs['timeout'] == 15
        twilio.assert_not_called()
    else:
        prefijo = 'whatsapp:' if canal == 'WhatsApp' else ''
        twilio.return_value.messages.create.assert_called_once_with(to=prefijo + contacto.telefono,
            from_=prefijo + ('+12025550102' if prefijo else '+12025550101'), body='Mensaje de prueba')
        sendgrid.assert_not_called()
    historial = client.get(f'/api/clientes/{contacto.id}', headers=headers).json()['comunicaciones'][0]
    assert historial['modo'] == 'real' and historial['estado'] == 'Enviado'


@pytest.mark.parametrize('canal', ['Email', 'SMS', 'WhatsApp'])
def test_error_seguro(client, db, headers, contacto, configurado, canal, caplog):
    twilio, sendgrid = configurado
    mock = sendgrid.return_value.client.mail.send.post if canal == 'Email' else twilio.return_value.messages.create
    mock.side_effect = RuntimeError('SECRETO-SENTINELA Authorization: clave-ficticia-prueba')
    data = enviar(client, headers, contacto, canal).json()
    assert data['estado'] == 'Fallido' and data['modo'] == 'real' and data['exitoso'] is False
    registro = db.get(models.Comunicacion, data['id'])
    assert registro.error_tecnico == 'ProviderRequestFailed'
    assert registro.external_id is None and registro.provider_status is None
    assert 'SECRETO-SENTINELA' not in str(data) + caplog.text + registro.error_tecnico
    assert not any(r.exc_info or r.stack_info for r in caplog.records)
    mock.assert_called_once()


@pytest.mark.parametrize('canal', ['SMS', 'WhatsApp'])
@pytest.mark.parametrize('status,code', [(400, 21604), (401, 20003), (429, 20429),
                                       (500, None), ('HTTP-SECRETO', 'CODIGO-SECRETO')])
def test_twilio_rest_exception_metadatos_seguros(client, db, headers, contacto,
        configurado, monkeypatch, caplog, canal, status, code):
    callback = 'https://callback-secreto.example.invalid/api/webhooks/twilio/status'
    monkeypatch.setenv('TWILIO_STATUS_CALLBACK_URL', callback)
    sensibles = [contacto.telefono, '+12025550101', '+12025550102',
                 'sid-ficticio-prueba', 'token-ficticio-prueba', 'Mensaje de prueba',
                 callback, 'Authorization: HEADER-SECRETO', 'HTTP-SECRETO', 'CODIGO-SECRETO']
    uri = 'https://api.twilio.com/Accounts/sid-ficticio-prueba/Messages.json'
    create = configurado[0].return_value.messages.create
    create.side_effect = TwilioRestException(status, uri, msg=' '.join(sensibles),
                                            code=code, method='POST')
    res = enviar(client, headers, contacto, canal)
    assert res.status_code == 201
    registro = db.get(models.Comunicacion, res.json()['id'])
    assert registro.estado == 'Fallido' and registro.exitoso is False
    assert registro.error_tecnico == 'ProviderRequestFailed'
    assert registro.external_id is None and registro.provider_status is None
    logs = [r for r in caplog.records if r.name == twilio_service.__name__]
    assert len(logs) == 1
    assert logs[0].getMessage() == (
        f'TwilioRequestFailed channel={canal} '
        f'http_status={status if type(status) is int else None} '
        f'code={code if type(code) is int else None}')
    assert not any(r.exc_info or r.stack_info for r in caplog.records)
    assert all(secreto not in caplog.text for secreto in sensibles + [uri])
    assert 'http_status' not in res.text and 'code' not in res.json()
    create.assert_called_once()
    assert create.call_args.kwargs['status_callback'] == (
        callback + f'?comunicacion_id={registro.id}')


def test_twilio_rest_exception_servicio_no_expone_contexto(configurado, caplog):
    create = configurado[0].return_value.messages.create
    create.side_effect = TwilioRestException(400, 'https://url-secreta.invalid',
                                            msg='SECRETO-SENTINELA', code=21604)
    with pytest.raises(RuntimeError, match='^ProviderRequestFailed$') as error:
        twilio_service.enviar_mensaje('+12025550103', 'Mensaje de prueba')
    assert error.value.__suppress_context__
    assert error.value.__cause__ is None
    assert 'SECRETO-SENTINELA' not in caplog.text
    create.assert_called_once()


@pytest.mark.parametrize('canal,campo,valor', [('Email', 'email', None), ('Email', 'email', 'invalido'),
    ('SMS', 'telefono', None), ('SMS', 'telefono', '123'), ('WhatsApp', 'telefono', None),
    ('WhatsApp', 'telefono', 'no-es-numero')])
def test_destinatario_invalido(client, db, headers, contacto, configurado, canal, campo, valor):
    setattr(contacto, campo, valor)
    db.commit()
    assert enviar(client, headers, contacto, canal).status_code == 422
    assert db.query(models.Comunicacion).count() == 0
    for mock in configurado:
        mock.assert_not_called()


def test_estado_protegido_y_voice(client, headers, contacto, configurado):
    assert client.get('/api/integraciones/estado').status_code == 401
    assert client.get('/api/integraciones/estado', headers=headers).json() == {
        'sendgrid': True, 'twilio_sms': True, 'twilio_whatsapp': True, 'twilio_voice': False}
    assert enviar(client, headers, contacto, 'Llamada').json()['estado'] == 'Simulado'
    for mock in configurado:
        mock.assert_not_called()


def test_servicios_respetan_interruptor(configurado, monkeypatch):
    monkeypatch.setenv('COMMUNICATIONS_REAL_ENABLED', 'false')
    with pytest.raises(ValueError):
        sendgrid_service.enviar_email('demo@example.com', 'Asunto', 'Mensaje')
    with pytest.raises(ValueError):
        twilio_service.enviar_mensaje('+12025550103', 'Mensaje')
    for mock in configurado:
        mock.assert_not_called()


def test_migracion_conserva_historico():
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE comunicaciones (id INTEGER PRIMARY KEY, cliente_id INTEGER, canal VARCHAR, fecha_envio DATE, mensaje VARCHAR, exitoso BOOLEAN)'))
        conn.execute(text("INSERT INTO comunicaciones VALUES (1, NULL, 'SMS', '2026-01-01', 'Histórico', 1)"))
    migrar(engine)
    migrar(engine)
    with engine.connect() as conn:
        fila = conn.execute(text('SELECT * FROM comunicaciones')).mappings().one()
        assert fila['mensaje'] == 'Histórico' and fila['exitoso'] == 1
        assert fila['modo'] is None and fila['estado'] is None
        assert fila['external_id'] is None
        assert fila['provider_status'] is None
    engine.dispose()


@pytest.mark.parametrize('canal', ['Email', 'SMS', 'WhatsApp'])
def test_rechazo_del_proveedor(client, headers, contacto, configurado, canal):
    twilio, sendgrid = configurado
    if canal == 'Email':
        sendgrid.return_value.client.mail.send.post.return_value.status_code = 400
    else:
        twilio.return_value.messages.create.return_value.status = 'failed'
    data = enviar(client, headers, contacto, canal).json()
    assert data['estado'] == 'Fallido' and data['exitoso'] is False


def test_red_bloqueada():
    import socket
    with socket.socket() as sock, pytest.raises(AssertionError, match='Red externa prohibida'):
        sock.connect(('127.0.0.1', 9))


def test_loggers_sdk_no_exponen_cabeceras():
    import logging
    assert logging.getLogger('python_http_client.client').disabled
    assert logging.getLogger('twilio.http_client').disabled


@pytest.mark.parametrize('canal', ['Email', 'WhatsApp', 'SMS', 'Llamada'])
def test_adaptacion_por_canal(client, db, headers, contacto, configurado, groq_adaptacion, canal):
    original = '  Estimado cliente, recuerde su saldo pendiente y contacte a PluriOne.\n' * 8
    breve = ('Hola, le hablamos de PluriOne para recordarle su saldo pendiente. '
             'Podemos conversar sobre su pago cuando tenga un momento disponible. Gracias por su atencion.')
    groq_adaptacion.return_value.choices[0].message.content = breve
    estrategia = models.HistorialMensaje(cliente_id=contacto.id, monto_al_momento=100,
                                        mensaje_generado=original, contexto_hash='a' * 64)
    db.add(estrategia)
    db.commit()
    res = client.post('/api/comunicaciones', headers=headers, json={
        'cliente_id': contacto.id, 'canal': canal, 'mensaje': original})
    assert res.status_code == 201
    esperado = preparar_sms(breve) if canal == 'SMS' else breve if canal == 'Llamada' else original
    data = res.json()
    assert data['mensaje'] == esperado
    assert db.get(models.Comunicacion, data['id']).mensaje == esperado
    db.refresh(estrategia)
    assert estrategia.mensaje_generado == original
    twilio, sendgrid = configurado
    if canal in ('Email', 'WhatsApp'):
        groq_adaptacion.assert_not_awaited()
    else:
        groq_adaptacion.assert_awaited_once()
        args = groq_adaptacion.call_args.kwargs
        assert original in args['messages'][1]['content'] if canal == 'SMS' else args['messages'][1]['content'] == original
        assert '130' in args['messages'][0]['content'] if canal == 'SMS' else 'natural' in args['messages'][0]['content']
    if canal == 'Email':
        sendgrid.return_value.client.mail.send.post.assert_called_once()
        assert sendgrid.return_value.client.mail.send.post.call_args.kwargs['request_body']['content'][0]['value'] == original
    elif canal == 'Llamada':
        assert len(esperado) > 150 and data['modo'] == 'simulado'
        twilio.assert_not_called()
        sendgrid.assert_not_called()
    else:
        twilio.return_value.messages.create.assert_called_once()
        assert twilio.return_value.messages.create.call_args.kwargs['body'] == esperado
        assert data['estado'] == 'Enviado'  # SID no confirma entrega.
        if canal == 'SMS':
            assert len(esperado) <= 150


@pytest.mark.parametrize('texto,esperado', [
    ('  José\n  paga\t$100 “hoy” 😊 ', 'Jose paga $100 "hoy"'),
    ('a' * 150, 'a' * 150),
    ('hola ' + 'a' * 145, 'hola ' + 'a' * 145),
    ('hola ' + 'a' * 146, 'hola'),
    ('saldo ' * 40, ' '.join(['saldo'] * 25)),
    ('{}[]^~|\\` €', 'EUR'),
])
def test_sms_seguro(texto, esperado):
    assert preparar_sms(texto) == esperado
    validar_sms(esperado)
    assert len(esperado) <= 150


@pytest.mark.parametrize('canal,fallo', [
    (canal, fallo) for canal in ('SMS', 'Llamada')
    for fallo in ('excepcion', 'vacio', 'sin_configuracion')
] + [('Llamada', 'truncado'), ('SMS', 'sin_palabras'), ('SMS', 'solo_emojis')])
def test_groq_falla_sin_envio(client, db, headers, contacto, configurado, groq_adaptacion,
                            monkeypatch, canal, fallo, caplog):
    if fallo == 'excepcion':
        groq_adaptacion.side_effect = RuntimeError('SECRETO-SENTINELA')
    elif fallo == 'sin_configuracion':
        monkeypatch.setattr(groq, 'client', None)
    elif fallo == 'truncado':
        groq_adaptacion.return_value.choices[0].finish_reason = 'length'
    elif fallo == 'vacio':
        groq_adaptacion.return_value.choices[0].message.content = '  '
    else:
        groq_adaptacion.return_value.choices[0].message.content = (
            '😊' if fallo == 'solo_emojis' else 'x' * 151)
    res = enviar(client, headers, contacto, canal)
    assert res.status_code == (503 if fallo == 'sin_configuracion' else 502)
    assert db.query(models.Comunicacion).count() == 0
    assert 'SECRETO-SENTINELA' not in res.text + caplog.text
    for mock in configurado:
        mock.assert_not_called()


@pytest.mark.parametrize('texto', ['x' * 151, '😊', '  hola ', 'á', '^' * 100])
def test_guardia_twilio_no_envia_sms_invalido(configurado, texto):
    with pytest.raises(ValueError):
        twilio_service.enviar_mensaje('+12025550103', texto)
    configurado[0].assert_not_called()


def test_twilio_sin_reintentos(client, headers, contacto, configurado):
    assert enviar(client, headers, contacto, 'SMS').status_code == 201
    http = configurado[0].call_args.kwargs['http_client']
    assert http.timeout == 15
    assert http.session.adapters['https://'].max_retries.total == 0


@pytest.mark.parametrize('motivo,contenido,categoria', [
    ('length', '', 'EmptyContent'),
    ('length', '😊', 'NoUsableSmsWords'),
    ('content_filter', None, 'UnexpectedFinishReason'),
    (None, 'Texto', 'UnexpectedFinishReason'),
    ('tool_calls', None, 'UnexpectedFinishReason'),
    ('stop', None, 'EmptyContent'),
    ('stop', ' \n ', 'EmptyContent'),
    ('stop', 123, 'EmptyContent'),
    ('stop', '😊\u200d😊', 'NoUsableSmsWords'),
    ('stop', 'x' * 151, 'NoUsableSmsWords'),
])
def test_502_adaptacion_con_categoria(client, db, headers, contacto, configurado,
                                    groq_adaptacion, caplog, motivo, contenido, categoria):
    anterior = models.Comunicacion(id=6, cliente_id=contacto.id, canal='SMS',
                                  mensaje='SMS anterior', exitoso=True)
    db.add(anterior)
    db.commit()
    opcion = groq_adaptacion.return_value.choices[0]
    opcion.finish_reason, opcion.message.content = motivo, contenido
    res = enviar(client, headers, contacto, 'SMS')
    assert res.status_code == 502
    assert f'SmsAdaptationFailed reason={categoria}' in caplog.text
    assert db.query(models.Comunicacion).count() == 1
    assert db.get(models.Comunicacion, 6).mensaje == 'SMS anterior'
    for proveedor in configurado:
        proveedor.assert_not_called()


@pytest.mark.parametrize('respuesta', [None, SimpleNamespace(choices=[]),
    SimpleNamespace(choices=None), SimpleNamespace(choices=[None])])
def test_respuesta_malformada(client, db, headers, contacto, configurado,
                             groq_adaptacion, caplog, respuesta):
    groq_adaptacion.return_value = respuesta
    assert enviar(client, headers, contacto, 'SMS').status_code == 502
    assert 'SmsAdaptationFailed reason=MalformedResponse' in caplog.text
    assert db.query(models.Comunicacion).count() == 0
    for proveedor in configurado:
        proveedor.assert_not_called()


@pytest.mark.parametrize('fallo,categoria', [
    ('timeout', 'Timeout'), ('conexion', 'ConnectionError'),
    (400, 'BadRequest'), (401, 'AuthenticationFailed'), (403, 'PermissionDenied'),
    (404, 'ModelNotFound'), (429, 'RateLimited'), (500, 'ProviderHttpError'),
    ('inesperado', 'UnexpectedClientError'),
])
def test_groq_error_categorias_seguras(client, db, headers, contacto, configurado,
                                     groq_adaptacion, caplog, fallo, categoria):
    import httpx
    from openai import APITimeoutError, APIConnectionError, APIStatusError
    secreto = 'SECRETO-SENTINELA telefono email contenido Authorization'
    request = httpx.Request('POST', 'https://example.invalid', headers={'Authorization': secreto})
    if fallo == 'timeout':
        error = APITimeoutError(request=request)
    elif fallo == 'conexion':
        error = APIConnectionError(message=secreto, request=request)
    elif isinstance(fallo, int):
        error = APIStatusError(secreto, response=httpx.Response(fallo, request=request),
                               body={'error': secreto})
    else:
        error = RuntimeError(secreto)
    groq_adaptacion.side_effect = error
    res = enviar(client, headers, contacto, 'SMS')
    assert res.status_code == 502
    assert f'GroqGenerationFailed canal=SMS reason={categoria}' in caplog.text
    assert secreto not in res.text + caplog.text
    assert not any(r.exc_info for r in caplog.records)
    assert db.query(models.Comunicacion).count() == 0
    for proveedor in configurado:
        proveedor.assert_not_called()


def test_presupuesto_tokens_y_fallback_de_respuesta_completa(client, db, headers, contacto,
                                                           configurado, groq_adaptacion):
    # Reproduce una generación que consume más del presupuesto antiguo (100).
    # Para SMS length con contenido utilizable debe pasar por el mismo respaldo.
    completo = 'José,\n recuerde su saldo pendiente. ' * 10
    async def generar(**kwargs):
        assert kwargs['model'] == 'qwen/qwen3.8-27b'
        assert kwargs['reasoning_effort'] == 'none'
        assert kwargs['max_tokens'] == 256
        assert kwargs['temperature'] == 0.2
        motivo = 'length'
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason=motivo, message=SimpleNamespace(content=completo))])
    groq_adaptacion.side_effect = generar
    res = enviar(client, headers, contacto, 'SMS')
    assert res.status_code == 201
    esperado = preparar_sms(completo)
    assert 0 < len(esperado) <= 150
    assert res.json()['mensaje'] == esperado
    validar_sms(esperado)
    twilio, sendgrid = configurado
    twilio.return_value.messages.create.assert_called_once_with(
        to=contacto.telefono, from_='+12025550101', body=esperado)
    sendgrid.assert_not_called()
    assert db.query(models.Comunicacion).count() == 1
    groq_adaptacion.assert_awaited_once()


def test_error_programacion_local_no_se_disfraza_de_502(client, headers, contacto,
                                                     configurado, monkeypatch):
    def roto(_):
        raise RuntimeError('Error de programación local')
    monkeypatch.setattr(mensajes, 'adaptar_sms', roto)
    with pytest.raises(RuntimeError, match='Error de programación local'):
        enviar(client, headers, contacto, 'SMS')
    for proveedor in configurado:
        proveedor.assert_not_called()


@pytest.mark.parametrize('motivo', ['stop', 'length'])
def test_sms_length_util_se_entrega_a_comunicaciones_mock(client, db, headers, contacto,
                                                        groq_adaptacion, monkeypatch, motivo):
    from datetime import date
    contenido = '"**Jose, recuerda tu saldo pendiente. Contacta a PluriOne para revisar tu pago.**" ' * 4
    groq_adaptacion.return_value.choices[0].finish_reason = motivo
    groq_adaptacion.return_value.choices[0].message.content = contenido
    esperado = preparar_sms(contenido)
    registro = SimpleNamespace(id=7, cliente_id=contacto.id, canal='SMS', fecha_envio=date.today(),
        mensaje=esperado, exitoso=False, modo='simulado', estado='Simulado', provider=None)
    registrar = Mock(return_value=registro)
    monkeypatch.setattr(comunicaciones, 'registrar', registrar)
    res = enviar(client, headers, contacto, 'SMS')
    assert res.status_code == 201
    registrar.assert_called_once_with(db, contacto, 'SMS', esperado)
    assert res.json()['mensaje'] == esperado
    assert len(esperado) <= 150
    validar_sms(esperado)
    assert db.query(models.Comunicacion).count() == 0
    groq_adaptacion.assert_awaited_once()


@pytest.mark.parametrize('contenido', [None, '', ' \n\t ', '😊', '```\n***\n```',
    '<think>Debo pensar en como redactarlo', 'x' * 151])
def test_sms_length_inutil_no_registra(client, db, headers, contacto, groq_adaptacion,
                                     monkeypatch, contenido):
    opcion = groq_adaptacion.return_value.choices[0]
    opcion.finish_reason, opcion.message.content = 'length', contenido
    registrar = Mock()
    monkeypatch.setattr(comunicaciones, 'registrar', registrar)
    assert enviar(client, headers, contacto, 'SMS').status_code == 502
    registrar.assert_not_called()
    assert db.query(models.Comunicacion).count() == 0


@pytest.mark.parametrize('formato,esperado', [
    ('SMS: "**Jose, revisa tu saldo.**"', 'Jose, revisa tu saldo.'),
    ('```text\nJose, revisa tu saldo.\n```', 'Jose, revisa tu saldo.'),
    ('- **Jose**,\n revisa tu saldo. 😊', 'Jose, revisa tu saldo.'),
    ('<think>RAZONAMIENTO-SENTINELA</think>\nSMS: Jose, revisa tu saldo.', 'Jose, revisa tu saldo.'),
    ('Jose, revisa tu saldo.<think>Razonamiento incompleto', 'Jose, revisa tu saldo.'),
])
def test_formato_y_razonamiento_no_se_envian(formato, esperado):
    assert preparar_sms(formato) == esperado
    validar_sms(esperado)


def test_razonamiento_separado_no_sustituye_contenido(client, headers, contacto,
                                                    groq_adaptacion, monkeypatch, caplog):
    opcion = groq_adaptacion.return_value.choices[0]
    opcion.finish_reason = 'length'
    opcion.message.content = None
    opcion.message.reasoning = 'RAZONAMIENTO-SENTINELA'
    registrar = Mock()
    monkeypatch.setattr(comunicaciones, 'registrar', registrar)
    res = enviar(client, headers, contacto, 'SMS')
    assert res.status_code == 502
    registrar.assert_not_called()
    assert 'RAZONAMIENTO-SENTINELA' not in res.text + caplog.text


@pytest.mark.parametrize('motivo', ['stop', 'length'])
def test_sms_corto_util_no_se_reemplaza(client, headers, contacto, configurado,
                                      groq_adaptacion, motivo):
    texto = ('Recuerda tu saldo pendiente con PluriOne. Contactanos para revisar '
             'las opciones de pago y resolver dudas sobre tu cuenta.')
    assert 120 <= len(texto) <= 130
    opcion = groq_adaptacion.return_value.choices[0]
    opcion.finish_reason, opcion.message.content = motivo, texto
    res = enviar(client, headers, contacto, 'SMS')
    assert res.status_code == 201
    assert res.json()['mensaje'] == texto
    configurado[0].return_value.messages.create.assert_called_once_with(
        to=contacto.telefono, from_='+12025550101', body=texto)


@pytest.mark.parametrize('longitud', range(140, 162))
def test_limite_sms_respeta_palabras_en_la_frontera(longitud):
    prefijo = 'saldo ' * 23
    palabra = 'p' * (longitud - len(prefijo))
    texto = prefijo + palabra
    resultado = preparar_sms(texto)
    assert len(resultado) <= 150
    assert resultado == (texto if longitud <= 150 else prefijo.rstrip())


@pytest.mark.parametrize('numero', ['+52' + '５' * 10, '+52' + '٥' * 10])
def test_e164_rechaza_digitos_unicode(numero):
    from app.services.configuracion import telefono_valido
    assert not telefono_valido(numero)
