#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/demo_common.sh"

[[ -f db/base-de-datos.sql ]] || demo_error 'Falta db/base-de-datos.sql.'
demo_validar restore
demo_compose pull db
demo_compose up -d db
demo_esperar_db

if ! tablas="$(demo_compose exec -T db sh -c '
    exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = '\''public'\''"
' 2>/dev/null)"; then
    demo_error 'No se pudo comprobar si el esquema public está vacío. No se importó la demo.'
fi
[[ "$tablas" == '0' ]] || demo_error 'La base no está vacía. Restauración cancelada; no se modificaron sus datos. Use una instalación NUEVA.'

umask 077
errores="$(mktemp "${TMPDIR:-/tmp}/motor-demo-import.XXXXXX")"
trap 'rm -f -- "$errores"' EXIT
if ! demo_compose exec -T db sh -c '
    exec psql -X -v ON_ERROR_STOP=1 --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB"
' < db/base-de-datos.sql >/dev/null 2>"$errores"; then
    python3 "$DEMO_ROOT/scripts/mostrar_error_importacion.py" "$errores" || \
        printf '%s\n' 'No se pudo interpretar el diagnóstico técnico de importación.' >&2
    demo_error 'Falló la importación transaccional de la demo; no se aplicaron cambios parciales.'
fi
printf '%s\n' 'Demo restaurada. Conteos reales:'
demo_compose exec -T db sh -c '
    exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT '\''clientes'\'' AS tabla, count(*) FROM public.clientes
     UNION ALL SELECT '\''deudas'\'', count(*) FROM public.deudas
     UNION ALL SELECT '\''pagos'\'', count(*) FROM public.pagos
     UNION ALL SELECT '\''historial_mensajes'\'', count(*) FROM public.historial_mensajes
     UNION ALL SELECT '\''comunicaciones'\'', count(*) FROM public.comunicaciones
     UNION ALL SELECT '\''metricas_snapshots'\'', count(*) FROM public.metricas_snapshots"
'
