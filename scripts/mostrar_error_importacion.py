"""Últimos diagnósticos técnicos de psql, sin reproducir datos del stderr."""
from pathlib import Path
import re
import sys


# Mostrar categorías conocidas, nunca identificadores, SQL, URLs ni texto libre.
# Incluso los DETAIL/HINT de PostgreSQL pueden contener valores privados.
CAUSAS = (
    (r'relation .* already exists', 'La relación ya existe.'),
    (r'duplicate key', 'Clave duplicada; conflicto con una restricción única.'),
    (r'foreign key constraint', 'Violación de clave foránea.'),
    (r'not-null constraint', 'Violación de restricción NOT NULL.'),
    (r'check constraint', 'Violación de restricción CHECK.'),
    (r'permission denied', 'Permisos insuficientes.'),
    (r'(?:relation|column|function|schema|role|database) .* does not exist', 'Objeto requerido inexistente.'),
    (r'syntax error', 'Error de sintaxis SQL.'),
    (r'invalid input syntax', 'Formato de dato incompatible con el tipo requerido.'),
    (r'(?:extra data after last expected column|missing data for column|COPY.*failed)', 'Formato COPY incompatible.'),
    (r'password authentication failed|authentication failed', 'Autenticación PostgreSQL fallida.'),
    (r'could not translate host name', 'No se pudo resolver el host de PostgreSQL.'),
    (r'connection refused|could not connect|connection .* failed', 'No se pudo conectar a PostgreSQL.'),
    (r'server closed the connection|terminating connection', 'PostgreSQL cerró la conexión.'),
    (r'no space left', 'Espacio de almacenamiento insuficiente.'),
    (r'out of memory', 'Memoria insuficiente.'),
)


def diagnosticos(texto):
    lineas = []
    for linea in texto.splitlines():
        match = re.search(r'\b(ERROR|FATAL|WARNING|DETAIL|HINT|CONTEXT):\s*(.*)$', linea)
        if match:
            nivel, detalle = match.groups()
        elif linea.startswith('psql: error:'):
            nivel, detalle = 'ERROR', linea
        else:
            continue
        causa = 'Detalle omitido por seguridad.'
        if nivel in ('ERROR', 'FATAL', 'WARNING'):
            causa = next((mensaje for patron, mensaje in CAUSAS if re.search(patron, detalle, re.I)), causa)
        lineas.append(f'{nivel}: {causa}')
    return lineas[-10:] or ['No se recibió un diagnóstico PostgreSQL reconocible; detalle omitido por seguridad.']


if __name__ == '__main__':
    print('\n'.join(diagnosticos(Path(sys.argv[1]).read_text(errors='replace'))), file=sys.stderr)
