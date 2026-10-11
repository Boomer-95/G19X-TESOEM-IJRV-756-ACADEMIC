#!/usr/bin/env bash
# Compartido por los dos comandos de demo. Nunca cargar .env como código shell.
DEMO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_ROOT"

demo_error() { printf '%s\n' "$*" >&2; exit 1; }
demo_compose() {
    docker compose --project-directory "$DEMO_ROOT" --env-file "$DEMO_ROOT/.env" \
        -f "$DEMO_ROOT/docker-compose.yml" "$@"
}
demo_validar() {
    [[ -f .env ]] || demo_error 'Falta .env. Copie .env.example y complete la configuración privada.'
    command -v docker >/dev/null || demo_error 'Se requiere Docker con Compose.'
    command -v python3 >/dev/null || demo_error 'Se requiere python3 para validar la configuración.'
    demo_compose config --quiet 2>/dev/null || demo_error 'Configuración Compose inválida. Revise .env y las variables PostgreSQL obligatorias.'
    # Solo el validador recibe el JSON, que puede contener secretos. Nunca imprimirlo.
    if ! demo_compose config --format json 2>/dev/null | python3 "$DEMO_ROOT/scripts/validar_config_demo.py" "$1"; then
        demo_error 'Validación de demo fallida; no se inició ningún servicio.'
    fi
    # Preflight comprobó el valor efectivo, incluso overrides del shell.
    export COMMUNICATIONS_REAL_ENABLED=false
}
demo_esperar_db() {
    local estado intento
    for ((intento=0; intento<60; intento++)); do
        if ! estado="$(demo_compose ps --all --format json db 2>/dev/null | python3 -c '
import json,sys
raw=sys.stdin.read().strip()
rows=json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines() if line]
print(rows[0].get("Health", "") if rows and rows[0].get("State")=="running" else "stopped")
' 2>/dev/null)"; then
            demo_error 'No se pudo consultar el estado de PostgreSQL.'
        fi
        case "$estado" in
            healthy) return ;;
            unhealthy|stopped) demo_error 'PostgreSQL no está saludable. Revise el servicio db antes de continuar.' ;;
        esac
        sleep 2
    done
    demo_error 'Tiempo agotado esperando el healthcheck de PostgreSQL.'
}
