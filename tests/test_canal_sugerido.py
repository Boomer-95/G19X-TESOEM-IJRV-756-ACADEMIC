from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace as Dato
from unittest.mock import Mock

import pytest
from sqlalchemy import event
from app import main, models
from app.services.canal_sugerido import sugerir_canal

HOY = date(2026, 10, 21)


def contacto(id, canal='SMS', dias=3, modo='real', estado='Entregado', status='delivered', cliente_id=1):
    return Dato(id=id, cliente_id=cliente_id, canal=canal, fecha_envio=HOY-timedelta(days=dias),
                modo=modo, estado=estado, provider_status=status)


def pago(id=1, dias=0, monto=100, cliente_id=1, recuperado=True):
    return Dato(id=id, cliente_id=cliente_id, fecha_pago=HOY-timedelta(days=dias), monto=monto,
                se_recuperó=recuperado)


def calcular(contactos=(), pagos=(), **kwargs):
    return sugerir_canal(Dato(id=1, comunicaciones=list(contactos), pagos=list(pagos)), hoy=HOY, **kwargs)


def test_sin_comunicaciones():
    r = calcular()
    assert r['canal'] is None
    assert r['estado'] == 'Sin evidencia suficiente'
    assert r['confianza'] == 'insuficiente'
    assert r['ventana_pago_dias'] == 7
    assert all(d['comunicaciones_totales'] == 0 for d in r['estadisticas'].values())


def test_un_contacto_no_suficiente_aun_con_pago():
    assert calcular([contacto(1)], [pago()])['canal'] is None


def test_sms_entregado_email_fallido_sin_pagos():
    r = calcular([contacto(1), contacto(2),
                  contacto(3, 'Email', estado='Fallido', status='failed'),
                  contacto(4, 'Email', estado='No entregado', status='undelivered')])
    assert r['canal'] == 'SMS'
    assert r['estadisticas']['SMS']['score_interno'] == 4
    assert r['estadisticas']['Email']['score_interno'] == -4
    assert r['estadisticas']['SMS']['pagos_asociados_temporalmente'] == 0


def test_whatsapp_leido_no_duplica_peso_entrega():
    r = calcular([contacto(1), contacto(2), contacto(3, 'WhatsApp', estado='Leído', status='read'),
                  contacto(4, 'WhatsApp', estado='Leído', status='read')])
    assert r['canal'] == 'WhatsApp'
    d = r['estadisticas']['WhatsApp']
    assert (d['entregadas_o_leidas'], d['leidas'], d['score_interno']) == (2, 2, 6)


@pytest.mark.parametrize('dias,cuenta', [(0, 1), (7, 1), (8, 0)])
def test_ventana_inclusiva(dias, cuenta):
    r = calcular([contacto(1, dias=20), contacto(2, dias=dias)], [pago()])
    d = r['estadisticas']['SMS']
    assert d['pagos_asociados_temporalmente'] == cuenta
    assert d['monto_asociado_temporalmente'] == 100 * cuenta
    assert d['score_interno'] == 4 + 5 * cuenta


def test_pago_solo_ultimo_contacto_y_desempate_fecha_por_id():
    contactos = [contacto(1, 'Email', dias=6), contacto(2, 'Email', dias=6),
                 contacto(3, 'SMS', dias=2), contacto(4, 'WhatsApp', dias=2),
                 contacto(5, 'Llamada', dias=0), contacto(6, cliente_id=2, dias=0)]
    r = calcular(contactos, [pago(monto=100.10), pago(2, monto=20.20)])
    assert sum(d['pagos_asociados_temporalmente'] for d in r['estadisticas'].values()) == 2
    assert r['estadisticas']['WhatsApp']['monto_asociado_temporalmente'] == 120.30
    assert r == calcular(reversed(contactos), [pago(2, monto=20.20), pago(monto=100.10)])


def test_no_contacto_posterior_al_pago():
    r = calcular([contacto(1, dias=0), contacto(2, dias=0)], [pago(dias=1)])
    assert r['estadisticas']['SMS']['pagos_asociados_temporalmente'] == 0


@pytest.mark.parametrize('status', ['failed', 'undelivered', 'bounced', 'dropped'])
def test_fallos_no_son_entregas(status):
    r = calcular([contacto(1, status=status), contacto(2, status=status)])
    d = r['estadisticas']['SMS']
    assert d['fallidas_o_no_entregadas'] == 2
    assert d['entregadas_o_leidas'] == 0
    assert r['canal'] is None


def test_enviado_no_es_entrega_y_pago_no_confirma_contacto():
    contactos = [contacto(1, estado='Enviado', status='sent'), contacto(2, estado='Enviado', status='accepted')]
    assert calcular(contactos)['canal'] is None
    r = calcular(contactos, [pago()])
    assert r['canal'] == 'SMS'
    assert r['estadisticas']['SMS']['entregadas_o_leidas'] == 0
    assert r['estadisticas']['SMS']['score_interno'] == 5


@pytest.mark.parametrize('modo,fuente', [('real', 'real'), ('simulado', 'simulada')])
def test_fuentes_reales_y_demo(modo, fuente):
    contactos = [contacto(1, modo=modo), contacto(2, modo=modo)]
    r = calcular(contactos, [pago()])
    assert r['canal'] == 'SMS'
    assert r['fuente_evidencia'] == fuente
    assert r['confianza'] == 'baja'
    assert r['estadisticas']['SMS']['entregadas_o_leidas'] == (2 if modo == 'real' else 0)


def test_simulados_sin_pago_no_inventa_entregas():
    assert calcular([contacto(1, modo='simulado'), contacto(2, modo='simulado')])['canal'] is None


def test_fuente_mixta_y_confianza_baja():
    r = calcular([contacto(1), contacto(2, modo='simulado')], [pago()])
    assert r['fuente_evidencia'] == 'mixta'
    assert r['estadisticas']['SMS']['fuente_evidencia'] == 'mixta'
    assert r['confianza'] == 'baja'


def test_origen_desconocido_no_es_real_ni_reasigna_pago():
    r = calcular([contacto(1, dias=5), contacto(2, dias=5), contacto(3, dias=1, modo=None)], [pago()])
    assert r['estadisticas']['SMS']['comunicaciones_no_evaluables'] == 1
    assert r['estadisticas']['SMS']['pagos_asociados_temporalmente'] == 0
    assert calcular([contacto(1, modo=None), contacto(2, modo=None)], [pago()])['canal'] is None


def test_desempate_orden_fijo():
    r = calcular([contacto(1), contacto(2), contacto(3, 'Email'), contacto(4, 'Email')])
    assert r['canal'] == 'Email'


def test_desempate_mas_pagos_antes_de_tasa():
    contactos = [contacto(1, 'SMS', dias=5, estado='Enviado', status='sent'),
                 contacto(2, 'SMS', dias=5, estado='Enviado', status='sent'),
                 contacto(3, 'SMS', dias=10, estado='Fallido', status='failed'),
                 contacto(4, 'Email', dias=20, estado='Leído', status='read'),
                 contacto(5, 'Email', dias=20, estado='Enviado', status='sent')]
    r = calcular(contactos, [pago()])
    assert r['estadisticas']['SMS']['score_interno'] == r['estadisticas']['Email']['score_interno'] == 3
    assert r['canal'] == 'SMS'


def test_desempate_tasa_antes_de_cantidad():
    contactos = [contacto(1), contacto(2)] + [contacto(i, 'Email', estado='Enviado', status='sent') for i in (3, 4)] + [contacto(5, 'Email'), contacto(6, 'Email')]
    assert calcular(contactos)['canal'] == 'SMS'


def test_desempate_cantidad_antes_de_orden_fijo():
    contactos = [contacto(1, 'Email', estado='Enviado', status='sent'),
                 contacto(2, 'Email', estado='Enviado', status='sent')]
    contactos += [contacto(i, 'SMS', estado='Enviado', status='sent') for i in range(3, 6)]
    # Una asociación para cada canal en días distintos, igual score y tasa cero.
    contactos[0].fecha_envio = HOY-timedelta(days=15)
    contactos[1].fecha_envio = HOY-timedelta(days=15)
    assert calcular(contactos, [pago(1, dias=14), pago(2)])['canal'] == 'SMS'


@pytest.mark.parametrize('cantidad,pagos,confianza', [(4, 0, 'baja'), (5, 0, 'media'), (10, 2, 'media'), (10, 3, 'alta')])
def test_confianza_cantidad_calidad(cantidad, pagos, confianza):
    r = calcular([contacto(i) for i in range(cantidad)], [pago(i) for i in range(pagos)])
    assert r['confianza'] == confianza


def test_configuracion_y_fecha_faltante(monkeypatch):
    monkeypatch.setenv('CANAL_SUGERIDO_VENTANA_PAGO_DIAS', '3')
    contactos = [contacto(1, dias=4), contacto(2, dias=4)]
    r = calcular(contactos, [pago()])
    assert r['ventana_pago_dias'] == 3
    assert r['estadisticas']['SMS']['pagos_asociados_temporalmente'] == 0
    contactos[0].fecha_envio = None
    assert calcular(contactos)['canal'] is None
    for valor in (0, 366, True, 1.5):
        with pytest.raises(ValueError):
            calcular(ventana_pago_dias=valor)


def test_pagos_invalidos_otro_cliente_y_futuro():
    pagos = [pago(cliente_id=2), pago(monto=0), pago(recuperado=False), pago(dias=-1)]
    sin_fecha = pago(); sin_fecha.fecha_pago = None
    r = calcular([contacto(1), contacto(2)], pagos+[sin_fecha])
    assert r['estadisticas']['SMS']['pagos_asociados_temporalmente'] == 0


def test_funcion_no_muta_entradas():
    contactos, pagos = [contacto(1), contacto(2)], [pago()]
    copia = deepcopy((contactos, pagos))
    calcular(contactos, pagos)
    assert (contactos, pagos) == copia


def test_get_sin_escrituras_ml_ni_proveedores(client, db, headers, monkeypatch):
    c = models.Cliente(nombre='Canal de prueba')
    db.add(c); db.flush()
    for i in range(2):
        db.add(models.Comunicacion(cliente_id=c.id, canal='SMS', fecha_envio=date.today(),
                                  modo='real', estado='Entregado', provider_status='delivered'))
    db.commit()
    sentencias = []
    def observar(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(statement.strip().split()[0].upper())
    event.listen(db.get_bind(), 'before_cursor_execute', observar)
    proveedor = Mock(side_effect=AssertionError('Proveedor prohibido'))
    modelo = Mock(side_effect=AssertionError('ML prohibido'))
    monkeypatch.setattr(main, 'client', proveedor)
    monkeypatch.setattr(main, '_modelo_riesgo', modelo)
    monkeypatch.setattr(main.comunicaciones, 'registrar', proveedor)
    monkeypatch.setattr(main.comunicaciones.twilio_service, 'enviar_mensaje', proveedor)
    monkeypatch.setattr(main.comunicaciones.sendgrid_service, 'enviar_email', proveedor)
    try:
        for _ in range(2):
            res = client.get(f'/api/clientes/{c.id}', headers=headers)
            assert res.status_code == 200
            assert res.json()['canal_sugerido']['canal'] == 'SMS'
        assert sentencias and set(sentencias) == {'SELECT'}
        assert not db.new and not db.dirty and not db.deleted
        assert not proveedor.mock_calls and not modelo.mock_calls
    finally:
        event.remove(db.get_bind(), 'before_cursor_execute', observar)
        monkeypatch.setattr(main, 'client', None)
