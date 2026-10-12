import traceback

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app import main
from app.schema import DATABASE_ERROR, SCHEMA_ERROR, validar_esquema


def test_esquema_correcto_permite_arranque(db, monkeypatch):
    monkeypatch.setattr(main, 'engine', db.get_bind())
    monkeypatch.setattr(main, 'client', None)
    with TestClient(main.app):
        pass


@pytest.mark.parametrize('sql', [
    'DROP TABLE metricas_snapshots',
    'ALTER TABLE comunicaciones DROP COLUMN estrategia_id',
    'ALTER TABLE clientes DROP COLUMN probabilidad_pago_a_tiempo',
    'ALTER TABLE historial_mensajes DROP COLUMN contexto_hash',
])
def test_esquema_incompleto_aborta_sin_reparar(db, monkeypatch, sql):
    bind = db.get_bind()
    with bind.begin() as conn:
        if sql == 'ALTER TABLE comunicaciones DROP COLUMN estrategia_id':
            # SQLite no permite DROP de una columna referenciada por una FK.
            # Recrear solo la tabla de este fixture como un esquema legacy.
            columnas = ', '.join(c.name for c in main.Base.metadata.tables['comunicaciones'].columns
                                 if c.name != 'estrategia_id')
            conn.execute(text(f'CREATE TABLE comunicaciones_legacy AS SELECT {columnas} FROM comunicaciones'))
            conn.execute(text('DROP TABLE comunicaciones'))
            conn.execute(text('ALTER TABLE comunicaciones_legacy RENAME TO comunicaciones'))
        else:
            conn.execute(text(sql))
    antes = {t: [c['name'] for c in inspect(bind).get_columns(t)]
             for t in inspect(bind).get_table_names()}
    monkeypatch.setattr(main, 'engine', bind)
    monkeypatch.setattr(main, 'client', None)
    with pytest.raises(RuntimeError, match='Ejecute: python -m app.migrate') as exc:
        with TestClient(main.app):
            pytest.fail('El backend no debe aceptar tráfico con esquema incompatible')
    assert str(exc.value) == SCHEMA_ERROR
    despues = {t: [c['name'] for c in inspect(bind).get_columns(t)]
               for t in inspect(bind).get_table_names()}
    assert antes == despues


def test_error_conexion_no_expone_credenciales(monkeypatch):
    secreto = 'postgresql://ficticio:password_sentinela@example.invalid/demo'

    class Bind:
        def connect(self):
            raise OperationalError(secreto, {}, Exception(secreto))

    from app import schema
    from contextlib import nullcontext
    from types import SimpleNamespace

    def inspeccion_fallida(conn):
        raise OperationalError(secreto, {}, Exception(secreto))

    monkeypatch.setattr(schema, 'inspect', inspeccion_fallida)
    # Tanto conectar como introspectar deben dar el error de disponibilidad.
    for bind in (Bind(), SimpleNamespace(connect=lambda: nullcontext(object()))):
        with pytest.raises(RuntimeError) as exc:
            validar_esquema(bind)
        mensaje = ''.join(traceback.format_exception(exc.value))
        assert str(exc.value) == DATABASE_ERROR
        assert str(exc.value) != SCHEMA_ERROR
        assert secreto not in mensaje
        assert 'password_sentinela' not in mensaje


def test_postgresql_inspecciona_public(monkeypatch):
    from types import SimpleNamespace
    from app import schema

    class Conn:
        dialect = SimpleNamespace(name='postgresql')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Inspector:
        def get_table_names(self, *, schema):
            assert schema == 'public'
            return list(main.Base.metadata.tables)

        def get_columns(self, name, *, schema):
            assert schema == 'public'
            return [{'name': c.name} for c in main.Base.metadata.tables[name].columns]

    monkeypatch.setattr(schema, 'inspect', lambda conn: Inspector())
    validar_esquema(SimpleNamespace(connect=Conn))
