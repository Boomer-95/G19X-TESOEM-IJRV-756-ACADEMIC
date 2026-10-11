"""Valida configuración efectiva de Compose por stdin, sin mostrar valores."""
import json
import sys


def validar(config, deploy=False):
    backend = config['services']['backend']['environment']
    if str(backend.get('COMMUNICATIONS_REAL_ENABLED', '')).strip().lower() != 'false':
        raise ValueError('La demo exige COMMUNICATIONS_REAL_ENABLED=false.')
    if not deploy:
        return
    frontend = config['services']['frontend']['build']['args']
    for nombre, valores in (
        ('ENTRA_CLIENT_ID', backend), ('ENTRA_TENANT_ID', backend),
        ('VITE_ENTRA_CLIENT_ID', frontend), ('VITE_ENTRA_TENANT_ID', frontend),
        ('VITE_ENTRA_API_SCOPE', frontend),
    ):
        if not isinstance(valores.get(nombre), str) or not valores[nombre].strip():
            raise ValueError(f'Falta configurar {nombre}.')
    for nombre in ('CLIENT_ID', 'TENANT_ID'):
        if frontend[f'VITE_ENTRA_{nombre}'] != backend[f'ENTRA_{nombre}']:
            raise ValueError(f'VITE_ENTRA_{nombre} debe coincidir con ENTRA_{nombre}.')
    if frontend['VITE_ENTRA_API_SCOPE'] != f"api://{backend['ENTRA_CLIENT_ID']}/access_as_user":
        raise ValueError('VITE_ENTRA_API_SCOPE no coincide con el scope esperado.')
    if frontend.get('VITE_ENTRA_REDIRECT_URI') != 'http://localhost:8080/':
        raise ValueError('VITE_ENTRA_REDIRECT_URI debe ser http://localhost:8080/.')


if __name__ == '__main__':
    try:
        validar(json.load(sys.stdin), deploy=sys.argv[1:] == ['deploy'])
    except ValueError as exc:
        # JSONDecodeError incluye fragmentos técnicos, no debe mostrarse.
        mensaje = 'No se pudo interpretar la configuración Compose.' if isinstance(exc, json.JSONDecodeError) else str(exc)
        print(mensaje, file=sys.stderr)
        sys.exit(1)
    except (KeyError, TypeError):
        print('Configuración Compose incompleta o incompatible.', file=sys.stderr)
        sys.exit(1)
