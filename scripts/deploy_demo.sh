#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/demo_common.sh"

demo_validar deploy
demo_compose up -d db
demo_esperar_db
demo_compose build backend frontend
demo_compose stop backend || true
if ! demo_compose run --rm --no-deps backend python -m app.migrate; then
    demo_error 'La migración falló. No se inició el backend actualizado; revise la base antes de continuar.'
fi
demo_compose up -d backend frontend
demo_compose ps
printf '%s\n' 'Frontend: http://localhost:8080/' 'API docs: http://127.0.0.1:8000/docs'
