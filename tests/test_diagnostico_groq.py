import json
import logging
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import AsyncOpenAI

from app import models
from app.services import comunicaciones, groq
from app.services.diagnostico_groq import estructura_respuesta


@pytest.mark.parametrize('contenido,motivo,sin_choices,exito', [
    (None, 'stop', False, False),
    ('', 'stop', False, False),
    (' \n\t ', 'length', False, False),
    ('Revisa tu saldo pendiente con PluriOne.', 'stop', False, True),
    ('Revisa tu saldo pendiente con PluriOne.', 'length', False, True),
    (None, 'stop', True, False),
    ([{'type': 'text', 'text': 'CONTENIDO-SENTINELA'}], 'stop', False, False),
])
def test_sdk_real_con_transporte_mock_y_diagnostico(client, db, headers, monkeypatch,
                                                  caplog, contenido, motivo,
                                                  sin_choices, exito):
    # JSON sintético pasa por la deserialización del SDK instalado; no usa red.
    cliente = models.Cliente(nombre='Fixture')
    db.add(cliente)
    db.flush()
    db.add(models.Deuda(cliente_id=cliente.id, monto_total=100, saldo_pendiente=100))
    db.commit()
    modelo = 'qwen/qwen3.8-27b'
    monkeypatch.setenv('GROQ_MODEL', 'openai/gpt-oss-20b')
    monkeypatch.setenv('GROQ_SMS_MODEL', modelo)
    payload = {
        'id': 'fixture', 'object': 'chat.completion', 'created': 0, 'model': modelo,
        'choices': [] if sin_choices else [{
            'index': 0, 'finish_reason': motivo,
            'message': {'role': 'assistant', 'content': contenido,
                        'reasoning': 'RAZONAMIENTO-SENTINELA',
                        'refusal': 'REFUSAL-SENTINELA' if not exito else None},
        }],
        'usage': {'prompt_tokens': 90, 'completion_tokens': 256, 'total_tokens': 346,
                  'completion_tokens_details': {'reasoning_tokens': 256}},
    }
    solicitudes = []

    def responder(request):
        solicitudes.append(request)
        return httpx.Response(200, json=payload)

    sdk = AsyncOpenAI(api_key='CLAVE-FICTICIA-SENTINELA',
                      base_url='https://example.invalid/openai/v1', max_retries=0,
                      http_client=httpx.AsyncClient(transport=httpx.MockTransport(responder)))
    monkeypatch.setattr(groq, 'client', sdk)
    registro = SimpleNamespace(id=7, cliente_id=cliente.id, canal='SMS', fecha_envio=date.today(),
        mensaje=contenido, exitoso=False, modo='simulado', estado='Simulado', provider=None)
    registrar = Mock(return_value=registro)
    monkeypatch.setattr(comunicaciones, 'registrar', registrar)
    caplog.set_level(logging.INFO, logger='app.routers.comunicaciones')
    res = client.post('/api/comunicaciones', headers=headers, json={
        'cliente_id': cliente.id, 'canal': 'SMS', 'mensaje': 'PROMPT-SENTINELA'})
    assert len(solicitudes) == 1
    assert solicitudes[0].url.path == '/openai/v1/chat/completions'
    assert json.loads(solicitudes[0].content)['model'] == modelo
    assert json.loads(solicitudes[0].content)['reasoning_effort'] == 'none'
    assert json.loads(solicitudes[0].content)['max_tokens'] == 256
    verificar_fidelidad_prompt(json.loads(solicitudes[0].content)['messages'][0]['content'])
    assert res.status_code == (201 if exito else 502)
    if exito:
        registrar.assert_called_once_with(db, cliente, 'SMS', contenido)
        assert res.json()['mensaje'] == contenido
    else:
        registrar.assert_not_called()  # No llega al servicio que contacta Twilio.
        assert ('MalformedResponse' if sin_choices else 'EmptyContent') in caplog.text
    assert db.query(models.Comunicacion).count() == 0
    evento = next(r.getMessage() for r in caplog.records
                  if r.getMessage().startswith('GroqAdaptationResponse'))
    estructura = json.loads(evento.split('structure=', 1)[1])
    assert estructura['requested_model'] == modelo
    assert estructura['returned_model'] == modelo
    assert estructura['model_matches'] is True
    assert estructura['choices_count'] == (0 if sin_choices else 1)
    assert estructura['reasoning_tokens'] == 256
    if not sin_choices:
        item = estructura['choices'][0]
        assert item['content_received'] is True
        assert item['content_is_none'] is (contenido is None)
        assert item['reasoning_present'] is True  # Extra conservado por el SDK.
        assert item['reasoning_length'] == len('RAZONAMIENTO-SENTINELA')
        assert item['finish_reason'] == motivo
        assert item['content_length'] == (len(contenido) if isinstance(contenido, str) else None)
    for secreto in ('CLAVE-FICTICIA-SENTINELA', 'PROMPT-SENTINELA',
                    'CONTENIDO-SENTINELA', 'RAZONAMIENTO-SENTINELA', 'REFUSAL-SENTINELA',
                    'Revisa tu saldo pendiente con PluriOne.'):
        assert secreto not in caplog.text


def test_observabilidad_no_imprime_valores_o_claves_arbitrarios():
    secreto = 'SECRETO-SENTINELA'
    respuesta = {
        'model': secreto, 'choices': [{
            'finish_reason': secreto,
            'message': {'content': {'text': secreto}, 'tool_calls': [{'arguments': secreto}],
                        'reasoning_content': secreto, 'audio': {'data': secreto},
                        secreto: secreto},
        }],
        'usage': {'prompt_tokens': secreto, 'completion_tokens': True},
    }
    datos = estructura_respuesta(respuesta, secreto, 256)
    assert secreto not in json.dumps(datos)
    assert datos['requested_model'] == datos['returned_model'] == 'other'
    assert datos['prompt_tokens'] is None
    assert datos['completion_tokens'] is None
    item = datos['choices'][0]
    assert item['content_type'] == 'dict'
    assert item['tool_calls_count'] == 1
    assert item['audio_present'] is True
    assert item['reasoning_content_present'] is True


@pytest.mark.parametrize('respuesta', [None, SimpleNamespace(choices=None),
                                     SimpleNamespace(choices=[]),
                                     SimpleNamespace(choices=[None])])
def test_diagnostico_tolera_estructura_ausente(respuesta):
    json.dumps(estructura_respuesta(respuesta, 'llama-3.1-8b-instant', 256))


def test_sdk_distingue_content_ausente_de_null():
    from openai.types.chat import ChatCompletion
    respuesta = ChatCompletion.model_validate({
        'id': 'fixture', 'created': 0, 'model': 'openai/gpt-oss-20b',
        'object': 'chat.completion',
        'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant'}}],
    })
    datos = estructura_respuesta(respuesta, respuesta.model, 256)
    assert datos['choices'][0]['content_received'] is False
    assert datos['choices'][0]['content_is_none'] is True


@pytest.mark.parametrize('modelo', ['openai/gpt-oss-20b', 'openai/gpt-oss-120b',
                                  'llama-3.1-8b-instant', 'qwen/qwen3.8-27b'])
@pytest.mark.parametrize('canal', ['SMS', 'Llamada', 'Email', 'WhatsApp'])
def test_modelo_sms_separado_y_reasoning_por_modelo(client, db, headers, monkeypatch, modelo, canal):
    from unittest.mock import AsyncMock
    cliente = models.Cliente(nombre='Fixture')
    db.add(cliente)
    db.flush()
    db.add(models.Deuda(cliente_id=cliente.id, monto_total=100, saldo_pendiente=100))
    db.commit()
    monkeypatch.setenv('GROQ_MODEL', 'openai/gpt-oss-20b')
    monkeypatch.setenv('GROQ_SMS_MODEL', modelo)
    crear = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(
        finish_reason='stop', message=SimpleNamespace(content='Revisa tu saldo.'))]))
    monkeypatch.setattr(groq, 'client', SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=crear)), close=AsyncMock()))
    registro = SimpleNamespace(id=1, cliente_id=cliente.id, canal=canal,
        fecha_envio=date.today(), mensaje='Revisa tu saldo.', exitoso=False,
        modo='simulado', estado='Simulado', provider=None)
    monkeypatch.setattr(comunicaciones, 'registrar', Mock(return_value=registro))
    res = client.post('/api/comunicaciones', headers=headers, json={
        'cliente_id': cliente.id, 'canal': canal, 'mensaje': 'Texto ficticio original.'})
    assert res.status_code == 201
    if canal in ('Email', 'WhatsApp'):
        crear.assert_not_awaited()
        comunicaciones.registrar.assert_called_once_with(
            db, cliente, canal, 'Texto ficticio original.')
        return
    crear.assert_awaited_once()
    kwargs = crear.call_args.kwargs
    assert kwargs['model'] == (modelo if canal == 'SMS' else 'openai/gpt-oss-20b')
    if canal == 'SMS' and modelo.startswith('openai/gpt-oss-'):
        assert kwargs['reasoning_effort'] == 'low'
    elif canal == 'SMS' and modelo == 'qwen/qwen3.8-27b':
        assert kwargs['reasoning_effort'] == 'none'
    else:
        assert 'reasoning_effort' not in kwargs
    assert 'reasoning_format' not in kwargs
    assert 'include_reasoning' not in kwargs
    assert kwargs['max_tokens'] == (256 if canal == 'SMS' else 150)


@pytest.mark.parametrize('modelo', ['openai/gpt-oss-20b', 'openai/gpt-oss-120b',
                                  'llama-3.1-8b-instant', 'qwen/qwen3.8-27b'])
@pytest.mark.parametrize('revision_ficticia', [False, True])
def test_script_aislado_misma_peticion_y_solo_metadatos(monkeypatch, capsys, tmp_path,
                                                     modelo, revision_ficticia):
    import asyncio
    from unittest.mock import AsyncMock
    from scripts import diagnostico_groq_sms as script
    monkeypatch.delenv('GROQ_MODEL', raising=False)
    monkeypatch.delenv('GROQ_SMS_MODEL', raising=False)
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.setattr(script, 'dotenv_values', lambda *args, **kwargs: {
        'GROQ_MODEL': 'openai/gpt-oss-20b', 'GROQ_SMS_MODEL': modelo,
        'GROQ_API_KEY': 'CLAVE-FICTICIA-SENTINELA'})
    monkeypatch.setattr(script.logging, 'disable', Mock())
    monkeypatch.setattr(script.warnings, 'filterwarnings', Mock())
    monkeypatch.setattr(script, 'SoloGroq', Mock())
    monkeypatch.setattr(script.httpx, 'AsyncClient', Mock())
    contenido = 'CONTENIDO-SENTINELA'
    reasoning = 'RAZONAMIENTO-SENTINELA'
    crear = AsyncMock(return_value=SimpleNamespace(model=modelo, choices=[SimpleNamespace(
        finish_reason='stop', message=SimpleNamespace(content=contenido, reasoning=reasoning))],
        usage=SimpleNamespace(total_tokens=100, completion_tokens=60,
                              completion_tokens_details=SimpleNamespace(reasoning_tokens=20))))
    sdk = Mock()
    sdk.__aenter__ = AsyncMock(return_value=SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=crear))))
    sdk.__aexit__ = AsyncMock(return_value=False)
    constructor = Mock(return_value=sdk)
    monkeypatch.setattr(script, 'AsyncOpenAI', constructor)
    ruta_revision = tmp_path / 'revision.txt'
    def crear_archivo(**kwargs):
        descriptor = script.os.open(ruta_revision, script.os.O_WRONLY | script.os.O_CREAT, 0o600)
        return descriptor, str(ruta_revision)
    monkeypatch.setattr(script.tempfile, 'mkstemp', crear_archivo)
    assert asyncio.run(script.main(revision_ficticia=revision_ficticia)) == 0
    crear.assert_awaited_once()
    kwargs = crear.call_args.kwargs
    assert kwargs['model'] == modelo
    assert kwargs['max_tokens'] == 256
    assert kwargs['temperature'] == 0.2
    verificar_fidelidad_prompt(kwargs['messages'][0]['content'])
    if modelo.startswith('openai/gpt-oss-'):
        assert kwargs['reasoning_effort'] == 'low'
    elif modelo == 'qwen/qwen3.8-27b':
        assert kwargs['reasoning_effort'] == 'none'
    else:
        assert 'reasoning_effort' not in kwargs
    assert constructor.call_args.kwargs['max_retries'] == 0
    assert constructor.call_args.kwargs['base_url'] == 'https://api.groq.com/openai/v1'
    salida = capsys.readouterr().out
    assert contenido not in salida and reasoning not in salida
    assert 'CLAVE-FICTICIA-SENTINELA' not in salida
    lineas = salida.splitlines()
    assert set(json.loads(lineas[0])) == {
        'requested_model', 'returned_model', 'finish_reason', 'content_length', 'reasoning_length',
        'completion_tokens', 'reasoning_tokens'}
    if revision_ficticia:
        assert json.loads(lineas[1]) == {'revision_ficticia_archivo': str(ruta_revision)}
        assert ruta_revision.read_text() == contenido
        assert ruta_revision.stat().st_mode & 0o777 == 0o600
    else:
        assert len(lineas) == 1
        assert not ruta_revision.exists()


def verificar_fidelidad_prompt(prompt):
    from app.services.mensajes import SMS_INSTRUCCION
    assert prompt == SMS_INSTRUCCION
    for restriccion in (
        'Usa exclusivamente hechos presentes en el mensaje original.',
        'No deduzcas ni agregues consecuencias financieras.',
        'Si un dato o consecuencia no aparece expresamente en el original, omítelo.',
        'recargos', 'intereses', 'penalizaciones', 'descuentos', 'convenios',
        'reestructuraciones', 'consecuencias', 'condiciones financieras', 'fechas',
        'importes', 'datos de contacto', 'La fidelidad al original tiene prioridad',
    ):
        assert restriccion in prompt


def test_transporte_script_solo_groq_una_peticion():
    import asyncio
    from unittest.mock import AsyncMock
    from scripts.diagnostico_groq_sms import SoloGroq

    async def verificar():
        transporte = SoloGroq()
        await transporte.transporte.aclose()
        mock = AsyncMock()
        transporte.transporte = mock
        for url in ('https://example.invalid/openai/v1/chat/completions',
                    'https://api.groq.com/api/comunicaciones',
                    'http://api.groq.com/openai/v1/chat/completions'):
            with pytest.raises(RuntimeError):
                await transporte.handle_async_request(httpx.Request('POST', url))
        mock.handle_async_request.assert_not_awaited()
        request = httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')
        await transporte.handle_async_request(request)
        with pytest.raises(RuntimeError):
            await transporte.handle_async_request(request)
        mock.handle_async_request.assert_awaited_once_with(request)
        await transporte.aclose()

    asyncio.run(verificar())
