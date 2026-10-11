"""Ejecuta los scripts con Docker simulado; jamás accede a la base del usuario."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def demo(tmp_path):
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'db').mkdir()
    (tmp_path / 'db/base-de-datos.sql').write_text('SELECT 1;')
    (tmp_path / '.env').write_text('COMMUNICATIONS_REAL_ENABLED=false\n')
    for nombre in ('restaurar_demo.sh', 'deploy_demo.sh', 'demo_common.sh', 'validar_config_demo.py'):
        shutil.copy2(ROOT / 'scripts' / nombre, tmp_path / 'scripts' / nombre)
    config = {'services': {
        'backend': {'environment': {'COMMUNICATIONS_REAL_ENABLED': 'false',
                                   'ENTRA_CLIENT_ID': 'ficticio-id', 'ENTRA_TENANT_ID': 'ficticio-tenant'}},
        'frontend': {'build': {'args': {'VITE_ENTRA_CLIENT_ID': 'ficticio-id',
                                     'VITE_ENTRA_TENANT_ID': 'ficticio-tenant',
                                     'VITE_ENTRA_API_SCOPE': 'api://ficticio-id/access_as_user',
                                     'VITE_ENTRA_REDIRECT_URI': 'http://localhost:8080/'}}}}}
    config_file = tmp_path / 'config.json'
    log = tmp_path / 'commands.jsonl'
    docker = tmp_path / 'docker'
    docker.write_text(f'#!{sys.executable}\n' + '''import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['DEMO_LOG'],'a') as f:f.write(json.dumps(args)+'\\n')
if 'config' in args:
    if '--quiet' in args:sys.exit(int(os.environ.get('DEMO_BAD_CONFIG','0')))
    print(Path(os.environ['DEMO_CONFIG']).read_text())
elif 'ps' in args and '--format' in args:
    print(json.dumps({'State':'running','Health':os.environ.get('DEMO_HEALTH','healthy')}))
elif 'exec' in args:
    body=args[-1]
    if 'information_schema.tables' in body:print(os.environ.get('DEMO_TABLES','0'))
    elif '--single-transaction' in body:
        sys.stdin.read();sys.exit(int(os.environ.get('DEMO_IMPORT_FAIL','0')))
    else:print('clientes 15; deudas 23; pagos 40; historial_mensajes 24; comunicaciones 24; metricas_snapshots 15')
elif 'run' in args:sys.exit(int(os.environ.get('DEMO_MIGRATE_FAIL','0')))
''')
    docker.chmod(0o755)

    def run(nombre, change=None, **extra):
        if change:
            change(config)
        config_file.write_text(json.dumps(config))
        env = {'PATH': str(tmp_path) + os.pathsep + os.defpath, 'DEMO_LOG': str(log),
               'DEMO_CONFIG': str(config_file), **extra}
        result = subprocess.run(['bash', str(tmp_path / 'scripts' / nombre)],
                                cwd='/tmp', env=env, capture_output=True, text=True, timeout=10)
        commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, commands
    return run


@pytest.mark.parametrize('valor', ['true', '1', 'yes', 'on', 'TRUE', ''])
def test_interruptor_inseguro_no_inicia_servicios(demo, valor):
    r, commands = demo('restaurar_demo.sh', lambda c: c['services']['backend']['environment'].update(COMMUNICATIONS_REAL_ENABLED=valor))
    assert r.returncode != 0
    assert 'COMMUNICATIONS_REAL_ENABLED=false' in r.stderr
    assert not any('up' in c for c in commands)


def test_base_no_vacia_no_importa(demo):
    r, commands = demo('restaurar_demo.sh', DEMO_TABLES='7')
    assert r.returncode != 0
    assert 'La base no está vacía' in r.stderr
    assert not any('--single-transaction' in ' '.join(c) for c in commands)


def test_restauracion_transaccional_y_conteos(demo):
    r, commands = demo('restaurar_demo.sh')
    assert r.returncode == 0, r.stderr
    imports = [c for c in commands if '--single-transaction' in ' '.join(c)]
    assert len(imports) == 1
    assert '-X -v ON_ERROR_STOP=1' in imports[0][-1]
    assert '"$POSTGRES_USER"' in imports[0][-1] and '"$POSTGRES_DB"' in imports[0][-1]
    assert 'POSTGRES_PASSWORD' not in r.stdout + r.stderr
    assert 'metricas_snapshots 15' in r.stdout


@pytest.mark.parametrize('field', ['ENTRA_CLIENT_ID', 'ENTRA_TENANT_ID', 'VITE_ENTRA_CLIENT_ID',
                                 'VITE_ENTRA_TENANT_ID', 'VITE_ENTRA_API_SCOPE', 'VITE_ENTRA_REDIRECT_URI'])
def test_config_invalida_no_compila_ni_muestra_ids(demo, field):
    def change(c):
        values = c['services']['frontend']['build']['args'] if field.startswith('VITE_') else c['services']['backend']['environment']
        values[field] = 'VALOR-PRIVADO-SENTINELA' if field.startswith('VITE_') else ''
    r, commands = demo('deploy_demo.sh', change)
    assert r.returncode != 0
    assert not any('up' in c or 'build' in c for c in commands)
    assert 'VALOR-PRIVADO-SENTINELA' not in r.stdout + r.stderr
    assert 'ficticio-id' not in r.stdout + r.stderr


def test_deploy_migra_antes_del_backend(demo):
    r, commands = demo('deploy_demo.sh')
    assert r.returncode == 0, r.stderr
    build = next(i for i, c in enumerate(commands) if 'build' in c)
    stop = next(i for i, c in enumerate(commands) if 'stop' in c)
    migration = next(i for i, c in enumerate(commands) if 'app.migrate' in c)
    up = next(i for i, c in enumerate(commands) if 'up' in c and 'backend' in c)
    assert build < stop < migration < up
    assert '--rm' in commands[migration] and '--no-deps' in commands[migration]


def test_migracion_fallida_no_inicia_backend(demo):
    r, commands = demo('deploy_demo.sh', DEMO_MIGRATE_FAIL='1')
    assert r.returncode != 0
    assert 'La migración falló' in r.stderr
    assert not any('up' in c and 'backend' in c for c in commands)


@pytest.mark.parametrize('extra', [{'DEMO_IMPORT_FAIL': '1'}, {'DEMO_HEALTH': 'unhealthy'}, {'DEMO_BAD_CONFIG': '1'}])
def test_fallos_de_entorno_detienen_restauracion(demo, extra):
    r, commands = demo('restaurar_demo.sh', **extra)
    assert r.returncode != 0
    assert 'Conteos reales' not in r.stdout
