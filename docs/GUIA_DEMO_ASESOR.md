# Guía de demostración para el asesor

Esta guía prepara una **instalación nueva**, con Docker y Compose v2, Git y Python 3.9+ disponibles. En Windows use Docker Desktop iniciado, con contenedores Linux, y Windows PowerShell 5.1 o PowerShell 7. No necesita Bash, WSL ni dependencias pip para los scripts de inicio. Los datos de `db/base-de-datos.sql` son completamente ficticios y las comunicaciones reales permanecen deshabilitadas. No reutilice la carpeta, la base ni el volumen de una instalación operativa.

## Preparación

Sustituya `URL_DEL_REPOSITORIO_ENTREGADA` por la dirección recibida privadamente:

Linux/macOS:

```bash
git clone URL_DEL_REPOSITORIO_ENTREGADA motor-cobranza-ia
cd motor-cobranza-ia
cp -n .env.example .env
```

Windows PowerShell (Python instalado con `py -3`, `python3` o `python` disponible):

```powershell
git clone URL_DEL_REPOSITORIO_ENTREGADA motor-cobranza-ia
if ($LASTEXITCODE -ne 0) { throw 'No se pudo clonar el repositorio.' }
Set-Location motor-cobranza-ia
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Complete `.env` localmente, sin publicar sus valores:

- `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`: valores para la base nueva del servicio `db`.
- `ENTRA_CLIENT_ID` y `ENTRA_TENANT_ID`: configuración Microsoft entregada privadamente, sin client secret.
- `VITE_ENTRA_CLIENT_ID` y `VITE_ENTRA_TENANT_ID`: deben coincidir exactamente con los dos valores de backend.
- `VITE_ENTRA_API_SCOPE`: exactamente `api://<CLIENT_ID>/access_as_user`, sustituyendo `<CLIENT_ID>` por `ENTRA_CLIENT_ID`.
- `VITE_ENTRA_REDIRECT_URI`: exactamente `http://localhost:8080/`. Esta URI debe estar registrada como redirect SPA en Microsoft Entra. El script comprueba el valor local; no consulta el tenant.
- `COMMUNICATIONS_REAL_ENABLED=false`: obligatorio. No configure Twilio ni SendGrid para esta demo.
- `GROQ_API_KEY`: no es necesaria para **Evaluar cartera**; solo si se necesita generar nuevas estrategias o adaptar SMS/llamadas; recibirla privadamente. Sin ella se pueden consultar los datos y estrategias históricas; las operaciones que requieren IA muestran servicio no configurado.

Para separar el volumen de otra instalación, añada a este `.env` nuevo un `COMPOSE_PROJECT_NAME` exclusivo, por ejemplo `motor-cobranza-demo-asesor`. No cambie el nombre de proyecto de una instalación operativa existente. Los puertos 8000 y 8080 deben estar libres. Docker construye la conexión usando el servicio `db`; no hace falta configurar `DATABASE_URL` para estos comandos.

El revisor utiliza una **cuenta Microsoft dedicada de evaluación**, no la cuenta personal del desarrollador. Las credenciales se comparten únicamente por **TODO Academy → Mis documentos → Técnicos → Accesos de prueba**. Consulte [Acceso del evaluador y checklist de entrega](ACCESO_EVALUADOR.md). No copie IDs, claves o tokens a capturas públicas ni al repositorio.

## Restauración y despliegue

Linux/macOS:

```bash
bash scripts/restaurar_demo.sh
bash scripts/deploy_demo.sh
```

Windows PowerShell, desde la raíz del repositorio:

```powershell
.\scripts\restaurar_demo.ps1
.\scripts\deploy_demo.ps1
```

Cierre el editor después de completar `.env` antes de ejecutar la restauración.
Si Windows marca los scripts descargados como bloqueados, revise su contenido y
use `Get-ChildItem .\scripts\*.ps1 | Unblock-File`. Si su política exige scripts
firmados, solicite el procedimiento autorizado por su administrador; no se cambia
la política de equipo desde estos scripts. Puede usar `powershell -NoProfile -File
.\scripts\restaurar_demo.ps1` (o `pwsh`) y su equivalente de deploy.

Los `.ps1` delegan a `demo_windows.py` (biblioteca estándar Python), que llama a
Docker Compose directamente. El host Windows no necesita `sh`: el `sh -c` de los
comandos SQL corre dentro del contenedor Linux de PostgreSQL. Compose lee `.env`
y los overrides del entorno; su JSON efectivo solo pasa al validador existente
`validar_config_demo.py`, sin imprimirse. Se exige el valor efectivo
`COMMUNICATIONS_REAL_ENABLED=false` antes de iniciar servicios. El SQL se transmite
como bytes por stdin para preservar UTF-8 y COPY también con PowerShell 5.1.
Los errores de Compose se muestran como fallos de fase sin valores privados; los
errores SQL usan las categorías filtradas de `mostrar_error_importacion.py`.

Validación local del camino Windows: se prueban el ejecutor Python con Docker
simulado y la estructura estática de las entradas `.ps1`. En el entorno Linux de
esta revisión no está instalado PowerShell; no se ejecutaron los `.ps1` ni Docker
Desktop Windows. Queda pendiente el smoke test en Windows: restauración en
proyecto nuevo, despliegue, acceso Entra y rechazo al repetir la restauración.

`restaurar_demo.sh` y `restaurar_demo.ps1` levantan solo `db`, espera su healthcheck y consulta si el esquema `public` está vacío. Si contiene tablas, se detiene sin importar, borrar ni reemplazar datos. En una base vacía importa el SQL dentro de una única transacción y consulta realmente los conteos:

| Entidad | Cantidad |
|---|---:|
| clientes | 15 |
| deudas | 23 |
| pagos | 40 |
| historial_mensajes | 24 |
| comunicaciones | 24 |
| metricas_snapshots | 15 |
| administradores | 0 |

`deploy_demo.sh` y `deploy_demo.ps1` validan la configuración antes de compilar, espera PostgreSQL, construye backend/frontend, detiene backend y **siempre ejecuta `python -m app.migrate`** antes de arrancar los servicios. Si la migración falla, no continúa al arranque. La migración es aditiva e idempotente. El backend comprueba tablas y columnas antes de aceptar tráfico; ante un esquema incompleto aborta e indica ejecutar la migración.

Abra **http://localhost:8080/** e inicie sesión con la cuenta Microsoft entregada. Documentación de API: http://127.0.0.1:8000/docs; las rutas de negocio requieren autenticación.

## Evaluación predictiva sin proveedores

Los 12 clientes precargados como evaluados tienen scores obtenidos del pipeline local sobre historiales ficticios, sin valores manuales. 13 y 14 quedan inicialmente sin evaluar; 15 está liquidado y sin score.

1. Abra Cartera y revise Sin evaluar.
2. Pulse **Evaluar cartera** y espere la confirmación: en la copia PostgreSQL verificada hubo **14 activos, 2 evaluados, 12 omitidos y 0 fallidos**.
3. Quite el filtro de pendientes para revisar el orden. El 13 pasó a probabilidad .720, score .280, Bajo riesgo y prioridad 5208.00; el 14 a .953, .047, Bajo riesgo y 697.95. El 15 permanece fuera de cartera activa.
4. Confirme que no aumentaron estrategias ni comunicaciones. No se necesita Groq ni credenciales Twilio/SendGrid. Conservar `COMMUNICATIONS_REAL_ENABLED=false` sigue siendo la política de demo para las otras acciones.

Cada cliente se confirma por separado; un fallo revierte ese cliente y el lote continúa. La prioridad score × saldo es un índice interno de ordenamiento, no dinero; combina riesgo estimado e impacto económico. Estas acciones sí cambian los campos de riesgo de la copia conectada: usar únicamente la demo. Los resultados del modelo son sintéticos, no están calibrados ni certificados para producción. [Pasos y contadores](MANUAL_USUARIO.md#8-calcular-riesgo-individual-o-por-cartera).

## Conservación de la demo

- **No usar `docker compose down -v`** durante la operación normal: elimina los volúmenes y sus datos.
- **No ejecutar seeds** después de importar el SQL.
- No repetir la restauración en una base con datos: el script se negará. Para actualizar esta demo use `deploy_demo.sh` o `deploy_demo.ps1`, que conserva los datos y migra antes del arranque.
- Los mensajes simulados no implican envíos. Algunas pruebas aisladas ejercitan proveedores mediante mocks; nunca se necesitan contactos reales para esta guía.

## Ensayo de Instalación Limpia y Registro de Tiempos

Durante el ensayo de instalación desde cero en entorno limpio se registraron los siguientes tiempos reales de ejecución:

| Fase | Comando / Acción | Tiempo medido |
|---|---|---|
| Clonación del repositorio | `git clone URL_DEL_REPOSITORIO_ENTREGADA motor-cobranza-ia` | ~5 a 10 segundos |
| Restauración de datos de prueba | `bash scripts/restaurar_demo.sh` | ~30 segundos |
| Compilación y despliegue de contenedores | `bash scripts/deploy_demo.sh` | ~1 minuto con 10 segundos |

**Nota técnica sobre incidencias menores resueltas (guía para el evaluador):**
- **Liberación preventiva del puerto 8000:** Si el equipo anfitrión mantiene en ejecución otra instancia local del proyecto o servicio en el puerto `8000` (o `8080`), es necesario detenerla preventivamente antes del despliegue para evitar colisiones de puertos.
- **Limpieza previa de volúmenes para nuevas restauraciones:** Dado que `restaurar_demo.sh` protege los datos existentes y aborta si detecta tablas en el esquema `public`, cuando se requiera realizar una nueva restauración limpia desde cero sobre un proyecto previamente inicializado es indispensable eliminar antes el volumen de base de datos con `docker compose down -v` (o definir un `COMPOSE_PROJECT_NAME` nuevo en `.env`).

## Limitación de dependencias de desarrollo

La revisión npm inicial encontró `source-map-js` 1.2.1 (alta), `vite` 5.4.21 (alta) y `esbuild` 0.21.5 (moderada), todos marcados como dependencias de desarrollo en el lockfile. Se actualizó únicamente `source-map-js` a 1.2.2 mediante un patch compatible, eliminando su aviso.

Persisten dos paquetes afectados: Vite y su dependencia esbuild. El registro no ofrece una corrección completa dentro de Vite 5; `npm audit` propone un cambio major. Ese cambio queda aplazado y no se utilizó `--force`. Los avisos incluyen exposición/lectura a través del servidor de desarrollo, manejo de source maps y condiciones específicas de Windows. No exponga Vite en una red pública. La demo Docker sirve el build estático mediante nginx, sin servidor Vite en ejecución; esto limita la exposición, pero no elimina los avisos del entorno de desarrollo.

Detalles originales: [esbuild](https://github.com/advisories/GHSA-67mh-4wv8-2f99), [Vite/source maps](https://github.com/advisories/GHSA-4w7w-66w2-5vf9), [Vite/Windows UNC](https://github.com/advisories/GHSA-v6wh-96g9-6wx3), [Vite/Windows paths](https://github.com/advisories/GHSA-fx2h-pf6j-xcff). Revisar la actualización major en una tarea separada.
