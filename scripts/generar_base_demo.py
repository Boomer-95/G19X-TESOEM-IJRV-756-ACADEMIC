"""Regenera SQL y valida restauración en un clúster PostgreSQL 16 NUEVO en /tmp.

No usa Docker, .env ni la base operativa. Requiere binarios PostgreSQL 16 y
las dependencias Python del proyecto. Se debe ejecutar como usuario no root.
"""
import argparse
from datetime import date
import os
from pathlib import Path
import subprocess
import sys
import tempfile

RAIZ = Path(__file__).resolve().parents[1]


def generar(fecha, binarios):
    carpeta = Path(tempfile.mkdtemp(prefix='motor-entrega-'))
    socket = carpeta / 'socket'
    socket.mkdir(mode=0o700)
    data = carpeta / 'data'
    # Entorno limpio: no heredar configuraciones PG, credenciales ni proveedores.
    entorno = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
               'PYTHON_DOTENV_DISABLED': '1', 'COMMUNICATIONS_REAL_ENABLED': 'false'}
    def ejecutar(args, **kwargs):
        return subprocess.run([str(a) for a in args], cwd=RAIZ, env=entorno, check=True, **kwargs)
    def pg(nombre, *args, **kwargs):
        return ejecutar([binarios / nombre, *args], **kwargs)
    conexion = ['-h', socket, '-p', '55439', '-U', 'demo_entrega']
    iniciado = False
    try:
        pg('initdb', '-D', data, '-U', 'demo_entrega', '--auth=trust', '--no-locale', '-E', 'UTF8', stdout=subprocess.DEVNULL)
        pg('pg_ctl', '-D', data, '-l', carpeta / 'postgres.log', '-o',
           f"-k {socket} -p 55439 -c listen_addresses=''", '-w', 'start')
        iniciado = True
        pg('createdb', *conexion, 'motor_cobranza_entrega_tmp')
        url = f'postgresql+psycopg2://demo_entrega@/motor_cobranza_entrega_tmp?host={socket}&port=55439'
        ejecutar([sys.executable, 'scripts/seed_entrega.py', '--database-url', url, '--fecha-base', fecha.isoformat()])
        candidato = carpeta / 'base-de-datos.sql'
        pg('pg_dump', *conexion, '-d', 'motor_cobranza_entrega_tmp', '--format=plain',
           '--no-owner', '--no-privileges', '-f', candidato)
        # Normalizar el final antes de restaurar exactamente el SQL a publicar.
        candidato.write_bytes(candidato.read_bytes().rstrip(b'\n') + b'\n')
        pg('createdb', *conexion, 'motor_cobranza_validacion_tmp')
        pg('psql', *conexion, '-X', '-v', 'ON_ERROR_STOP=1', '--single-transaction',
           '-d', 'motor_cobranza_validacion_tmp', '-f', candidato, stdout=subprocess.DEVNULL)
        ejecutar([sys.executable, 'scripts/validar_base_demo.py', url.replace('entrega_tmp', 'validacion_tmp'), candidato])
        # Publicar únicamente después de restauración y revisión de seguridad correctas.
        destino = RAIZ / 'db/base-de-datos.sql'
        destino.parent.mkdir(exist_ok=True)
        destino.write_bytes(candidato.read_bytes())
        print(f'Dump validado: db/base-de-datos.sql ({destino.stat().st_size} bytes), fecha base {fecha}.')
    finally:
        if iniciado:
            pg('pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop')
        print(f'Clúster temporal conservado y detenido en {carpeta}; no se tocaron volúmenes operativos.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fecha-base', type=date.fromisoformat, default=date(2026, 10, 6))
    parser.add_argument('--pg-bin', type=Path, default=Path('/usr/lib/postgresql/16/bin'))
    args = parser.parse_args()
    generar(args.fecha_base, args.pg_bin)
