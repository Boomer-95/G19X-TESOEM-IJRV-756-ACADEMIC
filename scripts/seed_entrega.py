"""Seed académico inventado. SOLO un clúster temporal /tmp/motor-entrega-* vacío.

No lee .env, no usa servicios externos, no borra datos ni admite producción.
Ejecutar desde la raíz con el Python del proyecto; requiere URL explícita.
"""
import argparse
from datetime import date, datetime, time, timedelta, timezone
import os
from pathlib import Path
import sys


def preparar_entorno(url):
    from sqlalchemy.engine import make_url
    destino = make_url(url)
    host = destino.query.get('host', destino.host or '')
    ruta = Path(host)
    if (destino.drivername != 'postgresql+psycopg2'
            or destino.database != 'motor_cobranza_entrega_tmp'
            or destino.username != 'demo_entrega' or destino.password
            or destino.host or destino.query.keys() - {'host', 'port'}
            or not str(ruta).startswith('/tmp/motor-entrega-')
            or ruta.resolve() != ruta or not ruta.is_dir()):
        raise ValueError('Destino rechazado: solo socket temporal y base entrega vacía.')
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ.pop('DB_HOST', None)
    os.environ['DATABASE_URL'] = url
    os.environ['COMMUNICATIONS_REAL_ENABLED'] = 'false'


def evaluar_clientes_demo(db, clientes):
    """Inferencia de producción después de persistir TODO el historial ficticio."""
    from app.services.riesgo import recalcular_riesgo
    db.flush()  # SessionLocal tiene autoflush=False; no evaluar datos incompletos.
    for posicion, cliente in enumerate(clientes, 1):
        if posicion in (13, 14):
            # Casos deliberadamente pendientes de evaluación, nunca riesgo bajo.
            cliente.score_riesgo = cliente.probabilidad_pago_a_tiempo = None
            cliente.segmento = 'No definido'
        else:
            # Incluye el liquidado: el pipeline devuelve NULL y "Sin deuda".
            recalcular_riesgo(db, cliente)
        for deuda in cliente.deudas:
            deuda.probabilidad_pago = (cliente.probabilidad_pago_a_tiempo
                                      if deuda.saldo_pendiente > 0 else None)
    db.flush()


def poblar(url, hoy):
    preparar_entorno(url)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sqlalchemy import inspect
    from app.database import engine, Base, SessionLocal
    from app import models as m
    from app.migrate import migrar
    # Rechazar cualquier tabla antes de create_all/migraciones: jamás completar una BD existente.
    with engine.connect() as conn:
        if inspect(conn).get_table_names():
            raise ValueError('Destino rechazado: la base debe estar completamente vacía.')
    Base.metadata.create_all(engine)
    migrar(engine)
    with SessionLocal.begin() as db:
        clientes, deudas, pagos, estrategias = [], [], [], []
        for i in range(1, 16):
            c = m.Cliente(nombre=f'Cliente Ficticio Demo {i:02d}',
                          email=f'cliente{i:02d}@example.invalid', telefono=None,
                          score_riesgo=None, probabilidad_pago_a_tiempo=None,
                          segmento='Sin deuda' if i == 15 else 'No definido')
            db.add(c)
            db.flush()
            # El default ORM 0.0 sustituye None durante INSERT; restaurar NULL tras flush.
            c.score_riesgo = c.probabilidad_pago_a_tiempo = None
            clientes.append(c)
            total = float(3000 + i * 1200)
            abonado = total if i == 15 else total / 4 if i % 2 == 0 else 0
            offset = -20 - i if i % 3 == 0 or i % 3 == 1 else 180 + i
            vencimiento = hoy + timedelta(days=offset)
            d = m.Deuda(cliente_id=c.id, monto_total=total, saldo_pendiente=total - abonado,
                        fecha_vencimiento=vencimiento,
                        estatus='Pagada' if i == 15 else 'En Mora' if offset < 0 else 'Pendiente',
                        probabilidad_pago=None)
            db.add(d)
            db.flush()
            deudas.append(d)
            if abonado:
                fecha_pago = hoy - timedelta(days=2 + i)
                p = m.Pago(cliente_id=c.id, deuda_id=d.id, monto=abonado,
                           fecha_vencimiento=vencimiento, fecha_pago=fecha_pago,
                           dias_atraso=(fecha_pago - vencimiento).days, canal_contacto='Demo sintética', se_recuperó=True)
                db.add(p)
                pagos.append(p)
        # Ocho obligaciones históricas liquidadas; cuatro pagos por deuda, sin inflar recuperación.
        for i, c in enumerate(clientes[:8], 1):
            total = float(4000 + i * 800)
            vencimiento = hoy - timedelta(days=60 + i)
            d = m.Deuda(cliente_id=c.id, monto_total=total, saldo_pendiente=0,
                        fecha_vencimiento=vencimiento, estatus='Pagada', probabilidad_pago=None)
            db.add(d)
            db.flush()
            deudas.append(d)
            atraso = [-3, 5, 18][(i - 1) % 3]
            for n in range(4):
                fecha_pago = vencimiento + timedelta(days=atraso - 9 + n * 3)
                p = m.Pago(cliente_id=c.id, deuda_id=d.id, monto=total / 4,
                           fecha_vencimiento=vencimiento, fecha_pago=fecha_pago,
                           dias_atraso=(fecha_pago - vencimiento).days, canal_contacto='Demo sintética', se_recuperó=True)
                db.add(p)
                pagos.append(p)
        evaluar_clientes_demo(db, clientes)
        # Reutilizar seis contactos (sin añadir pagos): dos del mismo canal,
        # antes del último abono histórico y después del penúltimo. Así solo
        # el último pago queda asociado y siempre al contacto más reciente.
        canales_demo = {1: 'SMS', 2: 'WhatsApp', 3: 'Email'}
        ultimos_pagos = {i: max(p.fecha_pago for p in pagos
                               if p.cliente_id == i and p.deuda_id != deudas[i - 1].id)
                        for i in canales_demo}
        # Plantillas ficticias almacenadas: NO generadas llamando a Groq.
        for i, c in enumerate(clientes[:12], 1):
            for n in range(2):
                hace = 24 - i + n * 2
                fecha_contacto = (ultimos_pagos[i] - timedelta(days=2 - n)
                                  if i in canales_demo else hoy - timedelta(days=hace))
                h = m.HistorialMensaje(cliente_id=c.id, contexto_hash=None,
                    monto_al_momento=deudas[i - 1].monto_total,
                    mensaje_generado=f'[DEMO FICTICIA] Estrategia {n + 1} para {c.nombre}: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.',
                    fecha_creacion=datetime.combine(fecha_contacto, time(12), tzinfo=timezone.utc))
                db.add(h)
                db.flush()
                estrategias.append(h)
                db.add(m.Comunicacion(cliente_id=c.id, estrategia_id=h.id,
                    canal=canales_demo.get(i, ['Email', 'SMS', 'WhatsApp'][((i - 1) + n) % 3]),
                    fecha_envio=h.fecha_creacion.date(), mensaje='[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.',
                    exitoso=False, modo='simulado', estado='Simulado', provider=None,
                    external_id=None, error_tecnico=None, provider_status=None))
        # Historial académico explícitamente inventado; último punto coincide con cartera y pagos.
        saldo = sum(d.saldo_pendiente for d in deudas)
        vencida = sum(d.saldo_pendiente for d in deudas if d.fecha_vencimiento < hoy)
        from app.services.analitica import cartera_actual
        cartera = cartera_actual(db)
        for hace in range(28, -1, -2):
            corte = hoy - timedelta(days=hace)
            db.add(m.MetricaSnapshot(fecha=corte, saldo_pendiente=saldo + hace * 700,
                cartera_vencida=vencida + hace * 400, deudores_activos=cartera['deudores_activos'],
                clientes_alto_riesgo=cartera['clientes_alto_riesgo'], monto_recuperado=sum(p.monto for p in pagos if p.fecha_pago <= corte),
                clientes_con_estrategia_ia=len({h.cliente_id for h in estrategias if h.fecha_creacion.date() <= corte})))
    engine.dispose()
    print('Demo ficticia creada: 15 clientes, 23 deudas, 40 pagos, 24 estrategias, 24 comunicaciones, 15 snapshots; administradores vacíos.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--fecha-base', type=date.fromisoformat, default=date(2026, 10, 6))
    args = parser.parse_args()
    poblar(args.database_url, args.fecha_base)
