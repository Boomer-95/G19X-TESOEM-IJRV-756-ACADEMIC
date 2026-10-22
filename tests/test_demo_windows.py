"""Camino Windows sin ejecutar PowerShell ni contactar Docker/proveedores."""
import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from scripts import demo_windows as windows

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    raiz = tmp_path / 'demo con espacios'
    (raiz / 'db').mkdir(parents=True)
    (raiz / '.env').write_text('NO_EJECUTAR=texto\n')
    sql = '-- SQL UTF-8 ficticio: revisión\nSELECT 1;\n'.encode()
    (raiz / 'db/base-de-datos.sql').write_bytes(sql)
    config = {'services': {
        'backend': {'environment': {'COMMUNICATIONS_REAL_ENABLED': 'false',
                                   'ENTRA_CLIENT_ID': 'demo-id', 'ENTRA_TENANT_ID': 'demo-tenant'}},
        'frontend': {'build': {'args': {'VITE_ENTRA_CLIENT_ID': 'demo-id',
                                     'VITE_ENTRA_TENANT_ID': 'demo-tenant',
                                     'VITE_ENTRA_API_SCOPE': 'api://demo-id/access_as_user',
                                     'VITE_ENTRA_REDIRECT_URI': 'http://localhost:8080/'}}}}}
    llamadas = []
    opciones = dict(tablas='0', health='healthy', fallo=None, secreto='VALOR-PRIVADO-SENTINELA')
    def ejecutar(args, **kwargs):
        assert args[:2] == ['docker', 'compose']
        assert args[2:8] == ['--project-directory', str(raiz), '--env-file', str(raiz / '.env'), '-f', str(raiz / 'docker-compose.yml')]
        assert kwargs['cwd'] == raiz and not kwargs.get('shell')
        comando = args[8:]
        llamadas.append(comando)
        salida, error, codigo = b'', b'', 0
        if comando == ['config', '--format', 'json']:
            salida = json.dumps(config).encode()
        elif comando[:1] == ['ps']:
            salida = json.dumps([{'State': 'running', 'Health': opciones['health']}]).encode()
        elif 'information_schema.tables' in comando[-1]:
            salida = opciones['tablas'].encode()
        elif '--single-transaction' in comando[-1]:
            assert kwargs['stdin'].read() == sql
            assert kwargs['env']['COMMUNICATIONS_REAL_ENABLED'] == 'false'
        elif 'UNION ALL' in comando[-1]:
            salida = b'clientes 15; pagos 40; administradores 0'
        if opciones['fallo'] and opciones['fallo'] in ' '.join(comando):
            codigo = 1
            error = ('ERROR: relation "' + opciones['secreto'] + '" already exists\nDETAIL: ' + opciones['secreto']).encode()
        return CompletedProcess(args, codigo, salida, error)
    monkeypatch.setattr(windows.subprocess, 'run', ejecutar)
    monkeypatch.setattr(windows.time, 'sleep', lambda _: None)
    return windows.Demo(raiz), config, llamadas, opciones


@pytest.mark.parametrize('valor', ['true', '1', 'yes', '', None])
def test_rechaza_envios_reales_antes_de_iniciar(entorno, valor):
    demo, config, llamadas, _ = entorno
    config['services']['backend']['environment']['COMMUNICATIONS_REAL_ENABLED'] = valor
    with pytest.raises(windows.ErrorDemo, match='COMMUNICATIONS_REAL_ENABLED=false'):
        demo.restaurar()
    assert all(c[0] == 'config' for c in llamadas)


def test_restauracion_bytes_transaccion_y_conteos(entorno, capsys):
    demo, _, llamadas, _ = entorno
    demo.restaurar()
    assert 'clientes 15' in capsys.readouterr().out
    assert llamadas.index(['pull', 'db']) < llamadas.index(['up', '-d', 'db'])
    imports = [c for c in llamadas if '--single-transaction' in c[-1]]
    assert len(imports) == 1
    assert '-X -v ON_ERROR_STOP=1' in imports[0][-1]
    assert '"$POSTGRES_USER"' in imports[0][-1] and '"$POSTGRES_DB"' in imports[0][-1]
    assert not any('DROP' in ' '.join(c) or c[0] == 'down' for c in llamadas)


def test_base_no_vacia_no_importa(entorno):
    demo, _, llamadas, opciones = entorno
    opciones['tablas'] = '7'
    with pytest.raises(windows.ErrorDemo, match='La base no está vacía'):
        demo.restaurar()
    assert not any('--single-transaction' in c[-1] for c in llamadas)


@pytest.mark.parametrize('fallo', ['config --quiet', 'pull db', 'information_schema.tables', '--single-transaction'])
def test_fallos_visibles_sin_secretos_ni_continuacion(entorno, fallo, capsys):
    demo, _, llamadas, opciones = entorno
    opciones['fallo'] = fallo
    with pytest.raises(windows.ErrorDemo) as exc:
        demo.restaurar()
    assert opciones['secreto'] not in str(exc.value) + capsys.readouterr().out
    assert not any('UNION ALL' in c[-1] for c in llamadas)
    if fallo == '--single-transaction':
        assert 'La relación ya existe' in str(exc.value)
        assert 'no se aplicaron cambios parciales' in str(exc.value)


def test_despliegue_espera_construye_migra_y_arranca(entorno):
    demo, _, llamadas, _ = entorno
    demo.desplegar()
    db = llamadas.index(['up', '-d', 'db'])
    health = next(i for i, c in enumerate(llamadas) if c[0] == 'ps')
    build = llamadas.index(['build', 'backend', 'frontend'])
    stop = llamadas.index(['stop', 'backend'])
    migracion = llamadas.index(['run', '--rm', '--no-deps', 'backend', 'python', '-m', 'app.migrate'])
    up = llamadas.index(['up', '-d', 'backend', 'frontend'])
    assert db < health < build < stop < migracion < up


@pytest.mark.parametrize('fallo', ['build', 'stop backend', 'app.migrate'])
def test_fallo_deploy_no_arranca_backend(entorno, fallo):
    demo, _, llamadas, opciones = entorno
    opciones['fallo'] = fallo
    with pytest.raises(windows.ErrorDemo):
        demo.desplegar()
    assert ['up', '-d', 'backend', 'frontend'] not in llamadas


@pytest.mark.parametrize('health', ['unhealthy', 'starting'])
def test_health_fallo_o_timeout_no_compila(entorno, health):
    demo, _, llamadas, opciones = entorno
    opciones['health'] = health
    with pytest.raises(windows.ErrorDemo):
        demo.desplegar()
    assert not any(c[0] == 'build' for c in llamadas)


def test_validador_entra_compartido_sin_imprimir_valores(entorno):
    demo, config, llamadas, _ = entorno
    config['services']['frontend']['build']['args']['VITE_ENTRA_CLIENT_ID'] = 'VALOR-SECRETO'
    with pytest.raises(windows.ErrorDemo) as exc:
        demo.desplegar()
    assert 'VALOR-SECRETO' not in str(exc.value)
    assert all(c[0] == 'config' for c in llamadas)


def test_falta_env_o_sql_no_inicia(entorno):
    demo, _, llamadas, _ = entorno
    (demo.raiz / '.env').unlink()
    with pytest.raises(windows.ErrorDemo, match='Falta .env'):
        demo.desplegar()
    (demo.raiz / 'db/base-de-datos.sql').unlink()
    with pytest.raises(windows.ErrorDemo, match='Falta db/base-de-datos.sql'):
        demo.restaurar()
    assert not llamadas


@pytest.mark.parametrize('nombre,accion', [('restaurar_demo.ps1', 'restore'), ('deploy_demo.ps1', 'deploy')])
def test_entradas_powershell_estructura_estatica(nombre, accion):
    # No sustituye un parser PowerShell ni una ejecución Windows.
    texto = (ROOT / 'scripts' / nombre).read_text()
    assert '#Requires -Version 5.1' in texto
    assert ". (Join-Path $PSScriptRoot 'demo_windows.ps1')" in texto
    assert f'Invoke-DemoWindows -Accion {accion}' in texto
    assert 'Invoke-Expression' not in texto
    assert 'Get-Content' not in texto  # No pasar COPY SQL por pipeline de texto.
    comun = (ROOT / 'scripts/demo_windows.ps1').read_text()
    assert "@('py', 'python3', 'python')" in comun
    assert 'exit $LASTEXITCODE' in comun
    assert '$PSScriptRoot' in comun and 'demo_windows.py' in comun
    assert '@prefijo' in comun and '.env' not in comun


def test_readme_corto_con_enlaces_y_referencia_preservada():
    texto = (ROOT / 'README.md').read_text()
    assert len(texto.splitlines()) < 80
    for nombre in ['PRD', 'MVP', 'ARQUITECTURA', 'MANUAL_USUARIO', 'MODELO_ML', 'ANALITICA_IA',
                   'DECISIONES_TECNICAS', 'GUIA_DEMO_ASESOR', 'RECOMENDACION_RECUPERACION', 'CANAL_SUGERIDO', 'QA']:
        assert f'docs/{nombre}.md' in texto
    assert '.\\scripts\\restaurar_demo.ps1' in texto
    assert '.\\scripts\\deploy_demo.ps1' in texto
    assert 'Uso de asistentes de IA durante el desarrollo' in texto
    assert len((ROOT / 'docs/REFERENCIA_TECNICA.md').read_text().splitlines()) > 350
