"""Ejecutor de demo para PowerShell: Compose, sin dependencias Python externas.

No interpreta .env como código ni imprime la configuración efectiva. El SQL se
transmite como bytes; evita la recodificación de pipelines de PowerShell 5.1.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validar_config_demo import validar
from scripts.mostrar_error_importacion import diagnosticos

RAIZ = Path(__file__).resolve().parents[1]


class ErrorDemo(Exception):
    """Mensaje fijo o diagnóstico filtrado, sin configuración privada."""


class Demo:
    def __init__(self, raiz=RAIZ):
        self.raiz = raiz
        self.entorno = os.environ.copy()

    def compose(self, *args, entrada=None):
        try:
            return subprocess.run(
                ['docker', 'compose', '--project-directory', str(self.raiz),
                 '--env-file', str(self.raiz / '.env'), '-f', str(self.raiz / 'docker-compose.yml'), *args],
                cwd=self.raiz, env=self.entorno, stdin=entrada,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        except OSError:
            raise ErrorDemo('No se pudo ejecutar Docker Compose. Compruebe Docker Desktop y Compose v2.') from None

    def exigir(self, *args, error):
        r = self.compose(*args)
        if r.returncode:
            raise ErrorDemo(error)
        return r.stdout.decode('utf-8', errors='replace').strip()

    def preflight(self, accion):
        if not (self.raiz / '.env').is_file():
            raise ErrorDemo('Falta .env. Copie .env.example y complete la configuración privada.')
        self.exigir('config', '--quiet', error='Configuración Compose inválida. Revise .env.')
        contenido = self.exigir('config', '--format', 'json', error='No se pudo validar la configuración Compose.')
        try:
            validar(json.loads(contenido), deploy=accion == 'deploy')
        except json.JSONDecodeError:
            raise ErrorDemo('No se pudo interpretar la configuración Compose.') from None
        except ValueError as exc:
            raise ErrorDemo(str(exc)) from None  # El validador solo devuelve nombres, nunca valores.
        except (KeyError, TypeError):
            raise ErrorDemo('Configuración Compose incompleta o incompatible.') from None
        self.entorno['COMMUNICATIONS_REAL_ENABLED'] = 'false'

    def esperar_db(self):
        for _ in range(60):
            salida = self.exigir('ps', '--all', '--format', 'json', 'db',
                                 error='No se pudo consultar el estado de PostgreSQL.')
            try:
                filas = json.loads(salida) if salida.startswith('[') else [json.loads(f) for f in salida.splitlines() if f]
                if not filas or filas[0].get('State') != 'running':
                    raise ErrorDemo('PostgreSQL no está en ejecución.')
                estado = filas[0].get('Health', '')
            except (ValueError, TypeError, AttributeError, KeyError):
                raise ErrorDemo('Estado de PostgreSQL no interpretable.') from None
            if estado == 'healthy':
                return
            if estado == 'unhealthy':
                raise ErrorDemo('PostgreSQL no está saludable. No se continuó.')
            time.sleep(2)
        raise ErrorDemo('Tiempo agotado esperando el healthcheck de PostgreSQL.')

    def restaurar(self):
        sql = self.raiz / 'db/base-de-datos.sql'
        if not sql.is_file():
            raise ErrorDemo('Falta db/base-de-datos.sql.')
        self.preflight('restore')
        self.exigir('pull', 'db', error='No se pudo descargar la imagen PostgreSQL.')
        self.exigir('up', '-d', 'db', error='No se pudo iniciar PostgreSQL.')
        self.esperar_db()
        tablas = self.exigir('exec', '-T', 'db', 'sh', '-c', '''exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"''',
                             error='No se pudo comprobar si public está vacío. No se importó la demo.')
        if tablas != '0':
            raise ErrorDemo('La base no está vacía. Restauración cancelada; use una instalación NUEVA.')
        with sql.open('rb') as entrada:
            r = self.compose('exec', '-T', 'db', 'sh', '-c',
                             'exec psql -X -v ON_ERROR_STOP=1 --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB"', entrada=entrada)
        if r.returncode:
            causas = '\n'.join(diagnosticos(r.stderr.decode('utf-8', errors='replace')))
            raise ErrorDemo(causas + '\nFalló la importación transaccional; no se aplicaron cambios parciales.')
        conteos = self.exigir('exec', '-T', 'db', 'sh', '-c', '''exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 'clientes' AS tabla, count(*) FROM public.clientes
UNION ALL SELECT 'deudas', count(*) FROM public.deudas
UNION ALL SELECT 'pagos', count(*) FROM public.pagos
UNION ALL SELECT 'historial_mensajes', count(*) FROM public.historial_mensajes
UNION ALL SELECT 'comunicaciones', count(*) FROM public.comunicaciones
UNION ALL SELECT 'metricas_snapshots', count(*) FROM public.metricas_snapshots
UNION ALL SELECT 'administradores', count(*) FROM public.administradores"''', error='Demo importada, pero no se pudieron consultar los conteos.')
        print('Demo restaurada. Conteos reales:\n' + conteos)

    def desplegar(self):
        self.preflight('deploy')
        self.exigir('up', '-d', 'db', error='No se pudo iniciar PostgreSQL.')
        self.esperar_db()
        print('Construyendo backend/frontend; espere a que finalice Docker Compose.', flush=True)
        self.exigir('build', 'backend', 'frontend', error='Falló la construcción. No se inició el backend actualizado.')
        self.exigir('stop', 'backend', error='No se pudo detener backend. No se ejecutó la migración.')
        self.exigir('run', '--rm', '--no-deps', 'backend', 'python', '-m', 'app.migrate',
                    error='La migración falló. No se inició el backend actualizado.')
        self.exigir('up', '-d', 'backend', 'frontend', error='No se pudieron iniciar backend/frontend.')
        print('Frontend: http://localhost:8080/\nAPI docs: http://127.0.0.1:8000/docs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion', choices=('restore', 'deploy'))
    args = parser.parse_args()
    try:
        demo = Demo()
        demo.restaurar() if args.accion == 'restore' else demo.desplegar()
    except ErrorDemo as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, KeyboardInterrupt):
        print('Operación interrumpida o error local de lectura. Revise el entorno antes de continuar.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
