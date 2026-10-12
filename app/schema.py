"""Comprobación de solo lectura; los cambios pertenecen a app.migrate."""
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from .database import Base
from . import models  # noqa: F401 — registra todas las tablas requeridas

SCHEMA_ERROR = (
    "Esquema de base de datos desactualizado o incompleto. "
    "Ejecute: python -m app.migrate"
)
DATABASE_ERROR = 'No se pudo verificar la base de datos. Compruebe PostgreSQL.'


def validar_esquema(bind):
    """Exige las tablas y columnas ORM actuales, también en tests SQLite."""
    try:
        with bind.connect() as conn:
            inspector = inspect(conn)
            # PostgreSQL no debe validar accidentalmente otro search_path.
            schema = 'public' if conn.dialect.name == 'postgresql' else None
            existentes = set(inspector.get_table_names(schema=schema))
            for tabla in Base.metadata.sorted_tables:
                if tabla.name not in existentes:
                    raise RuntimeError(SCHEMA_ERROR)
                columnas = {c['name'] for c in inspector.get_columns(tabla.name, schema=schema)}
                if not set(tabla.columns.keys()).issubset(columnas):
                    raise RuntimeError(SCHEMA_ERROR)
    except SQLAlchemyError:
        # Los errores de conexión/introspección pueden contener credenciales.
        raise RuntimeError(DATABASE_ERROR) from None
