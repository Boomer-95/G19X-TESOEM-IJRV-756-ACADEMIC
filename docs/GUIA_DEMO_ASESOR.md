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

Para separar los contenedores y el volumen `postgres_data` de cualquier instalación habitual o existente, utilice un `COMPOSE_PROJECT_NAME` independiente, por ejemplo `motor-cobranza-demo`. No cambie el nombre de proyecto ni elimine los volúmenes de una instalación operativa existente. Puede definir `COMPOSE_PROJECT_NAME=motor-cobranza-demo` dentro del archivo `.env` nuevo y/o establecerlo en la sesión de terminal antes de ejecutar los scripts de restauración y despliegue:

- **Linux/macOS:** `export COMPOSE_PROJECT_NAME=motor-cobranza-demo`
- **Windows PowerShell:** `$env:COMPOSE_PROJECT_NAME = 'motor-cobranza-demo'`

Asegúrese de que tanto el comando de restauración como el de despliegue utilicen exactamente el mismo `COMPOSE_PROJECT_NAME`. Los puertos 8000 y 8080 deben estar libres. Docker construye la conexión usando el servicio `db`; no hace falta configurar `DATABASE_URL` para estos comandos.

El revisor utiliza una **cuenta Microsoft dedicada de evaluación**, no la cuenta personal del desarrollador. Las credenciales se comparten únicamente por **TODO Academy → Mis documentos → Técnicos → Accesos de prueba**. Consulte [Acceso del evaluador y checklist de entrega](ACCESO_EVALUADOR.md). No copie IDs, claves o tokens a capturas públicas ni al repositorio.

## Qué trae el documento privado (Accesos de prueba)

El archivo privado `PERFIL.md`, ubicado en TODO Academy → Mis documentos → Técnicos → Accesos de prueba, contiene los siguientes elementos. Se documentan únicamente sus nombres, nunca sus valores:

- Cuenta Microsoft dedicada de evaluación y su contraseña.
- `ENTRA_CLIENT_ID` y `ENTRA_TENANT_ID`.
- `VITE_ENTRA_CLIENT_ID` y `VITE_ENTRA_TENANT_ID`, que utilizan los mismos identificadores correspondientes del backend.
- `VITE_ENTRA_API_SCOPE`.
- `VITE_ENTRA_REDIRECT_URI`.
- `ENTRA_REQUIRED_SCOPE`.
- `GROQ_API_KEY` (opcional: solo para generar estrategias nuevas mediante Groq).

Los identificadores y la configuración de Microsoft Entra son necesarios para configurar correctamente el frontend y el backend y permitir la autenticación del evaluador. `GROQ_API_KEY` es opcional: si falta, se puede iniciar sesión y consultar los datos históricos, pero no generar nuevas estrategias mediante Groq.

## Restauración y despliegue

Linux/macOS:

```bash
export COMPOSE_PROJECT_NAME=motor-cobranza-demo
bash scripts/restaurar_demo.sh
bash scripts/deploy_demo.sh
```

Windows PowerShell, desde la raíz del repositorio (`motor-cobranza-ia`):

```powershell
$env:COMPOSE_PROJECT_NAME = 'motor-cobranza-demo'
.\scripts\restaurar_demo.ps1
.\scripts\deploy_demo.ps1
```

Cierre el editor después de completar `.env` antes de ejecutar la restauración.
Si Windows marca los scripts descargados como bloqueados o la política de ejecución de PowerShell impide ejecutarlos en la sesión, revise su contenido, desbloquee los archivos con `Get-ChildItem .\scripts\*.ps1 | Unblock-File` y habilite una política `Bypass` limitada exclusivamente a la sesión actual (`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`), o bien invóquelos por archivo con `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\restaurar_demo.ps1` (y su equivalente para `deploy_demo.ps1`). No se modifica la política de ejecución permanente del equipo ni del usuario.

Los `.ps1` delegan a `demo_windows.py` (biblioteca estándar Python), que llama a
Docker Compose directamente. PostgreSQL se ejecuta íntegramente mediante Docker (servicio `db`), sin requerir una instalación local independiente de PostgreSQL en Windows. El host Windows no necesita `sh`: el `sh -c` de los
comandos SQL corre dentro del contenedor Linux de PostgreSQL. Compose lee `.env`
y los overrides del entorno; su JSON efectivo solo pasa al validador existente
`validar_config_demo.py`, sin imprimirse. Se exige el valor efectivo
`COMMUNICATIONS_REAL_ENABLED=false` antes de iniciar servicios. El SQL se transmite
como bytes por stdin para preservar UTF-8 y COPY también con PowerShell 5.1.
Los errores de Compose se muestran como fallos de fase sin valores privados; los
errores SQL usan las categorías filtradas de `mostrar_error_importacion.py`.

Validación del camino Windows: además de las pruebas automatizadas del ejecutor Python y de la estructura de las entradas `.ps1`, el `2026-11-10` se ejecutó y confirmó en **Windows 10** la prueba real de clonación, configuración de `.env`, restauración de `db/base-de-datos.sql` con `scripts/restaurar_demo.ps1`, despliegue con `scripts/deploy_demo.ps1`, acceso al frontend (`http://localhost:8080/`), documentación de FastAPI (`http://localhost:8000/docs`) e inicio de sesión con Microsoft Entra ID con acceso al dashboard (véase el detalle en la sección de ensayos más abajo). La comprobación de rechazo al repetir la restauración sobre una base ya poblada está cubierta por la validación automatizada y el ensayo en Linux; no se ejecutó una segunda pasada de `restaurar_demo.ps1` durante la sesión de Windows 10.

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

- **No usar `docker compose down -v`** ni en una instalación normal ni como procedimiento habitual: elimina los volúmenes y sus datos.
- **No eliminar volúmenes de una instalación existente.** Para realizar un ensayo limpio o una instalación de demostración separada, configure un `COMPOSE_PROJECT_NAME` independiente (por ejemplo `motor-cobranza-demo`).
- **No ejecutar seeds** después de importar el SQL.
- No repetir la restauración en una base con datos: el script se negará. Para actualizar esta demo use `deploy_demo.sh` o `deploy_demo.ps1` con el mismo `COMPOSE_PROJECT_NAME`, que conserva los datos y migra antes del arranque.
- Los mensajes simulados no implican envíos. Algunas pruebas aisladas ejercitan proveedores mediante mocks; nunca se necesitan contactos reales para esta guía.

## Ensayo de Instalación Limpia y Registro de Tiempos

### Prueba de instalación en Windows 10 (10 de noviembre de 2026)

Datos del entorno y resultados verificados durante la prueba real de instalación y despliegue en Windows 10:

- **Fecha de la prueba:** `2026-11-10` (10 de noviembre de 2026).
- **Sistema operativo:** `Windows 10`.
- **Docker Desktop:** `4.99.0`.
- **Docker Engine:** `29.9.3`.
- **Docker Compose:** `5.7.0`.
- **Git:** `2.56.1.windows.1`.
- **Python:** `3.14.10`.
- **Terminal / Shell:** `PowerShell`.
- **Base de datos:** PostgreSQL ejecutado mediante Docker (servicio contenedorizado `db`), sin instalación local independiente en el sistema anfitrión.
- **Scripts ejecutados:** `scripts/restaurar_demo.ps1` y `scripts/deploy_demo.ps1`.

Pruebas realizadas y confirmadas (no se cronometraron tiempos individuales por fase en esta ejecución):

1. Clonación exitosa del repositorio desde GitHub.
2. Creación y configuración local del archivo `.env` (sin exponer valores privados).
3. Ejecución exitosa de `scripts/restaurar_demo.ps1`.
4. Restauración de `db/base-de-datos.sql` sobre el contenedor de PostgreSQL en Docker, obteniendo los siguientes conteos verificados:
   - `clientes`: 15
   - `deudas`: 23
   - `pagos`: 40
   - `historial_mensajes`: 24
   - `comunicaciones`: 24
   - `metricas_snapshots`: 15
   - `administradores`: 0
5. Ejecución exitosa de `scripts/deploy_demo.ps1`.
6. Frontend accesible en `http://localhost:8080/`.
7. Documentación interactiva de FastAPI accesible en `http://localhost:8000/docs`.
8. Inicio de sesión con Microsoft Entra ID y acceso al dashboard.

### Ensayo de instalación limpia y tiempos en Linux (29 de octubre de 2026)

Datos del entorno y ejecución registrados durante el ensayo de instalación limpia en Linux:

- **Fecha del ensayo:** `2026-10-29` (29 de octubre de 2026).
- **Sistema operativo utilizado:** `Linux Mint 22.3 (Zena)` *(basado en Ubuntu 24.04 `noble`)*.
- **Versión de Docker:** `Docker version 29.1.3, build 29.1.3-0ubuntu3~24.04.2`.
- **Versión de Docker Compose:** `Docker Compose version v5.5.1`.
- **Scripts utilizados:** `scripts/restaurar_demo.sh` y `scripts/deploy_demo.sh` *(la ejecución equivalente en Windows 10 con `scripts/restaurar_demo.ps1` y `scripts/deploy_demo.ps1` quedó verificada el `2026-11-10`, según se detalla arriba)*.

Durante el ensayo de instalación desde cero en entorno limpio en Linux se registraron los siguientes tiempos y resultados por fase:

| Fase | Comando / Acción | Tiempo medido / Resultado |
|---|---|---|
| Clonación del repositorio | `git clone URL_DEL_REPOSITORIO_ENTREGADA motor-cobranza-ia` | ~5 a 10 segundos |
| Restauración de datos de prueba | `bash scripts/restaurar_demo.sh` | ~30 segundos |
| Compilación y despliegue de contenedores | `bash scripts/deploy_demo.sh` | ~1 minuto con 10 segundos |
| Inicio de sesión y visualización del dashboard | Abrir `http://localhost:8080/` en incógnito, iniciar sesión con la cuenta dedicada y esperar a que cargue el dashboard | ~15 segundos |

### Verificación de inicio de sesión con la cuenta de evaluación y visualización del dashboard

Estado de los pasos de la prueba interactiva de Microsoft Entra ID ejecutada el `2026-11-03` en Linux utilizando la cuenta Microsoft dedicada de evaluación (con su propia contraseña, sin usar el correo personal del desarrollador), conforme a [Acceso del evaluador y checklist de entrega](ACCESO_EVALUADOR.md), y complementada el `2026-11-10` en Windows 10 con el inicio de sesión mediante Microsoft Entra ID y acceso al dashboard en `http://localhost:8080/`:

1. **Abrir la aplicación en incógnito (`http://localhost:8080/`):** Verificado (`[X]` en checklist de entrega).
2. **Iniciar sesión con la cuenta Microsoft dedicada de evaluación:** Verificado (`[X]` en checklist de entrega).
3. **Visualizar el dashboard:** Verificado (`[X]` en checklist de entrega).
4. **Confirmar que `/auth/me` (`/backend/auth/me` vía proxy en Docker) responde HTTP 200:** Verificado (`[X]` en checklist de entrega).
5. **Cerrar sesión:** Verificado (`[X]` en checklist de entrega).
6. **Volver a iniciar sesión:** Verificado (`[X]` en checklist de entrega).

### Incidencias encontradas y cómo se resolvieron

- **Política de ejecución de PowerShell y bloqueo de scripts en Windows 10:** Durante la prueba en Windows 10, la política de ejecución de PowerShell y el marcado de archivos impidieron inicialmente ejecutar `scripts/restaurar_demo.ps1` y `scripts/deploy_demo.ps1`. **Resolución:** desbloquear los scripts con `Unblock-File` (`Get-ChildItem .\scripts\*.ps1 | Unblock-File`) y aplicar una política de ejecución `Bypass` limitada exclusivamente a la sesión actual de PowerShell (`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`), sin modificar de forma permanente la política del sistema ni del usuario.
- **Liberación preventiva del puerto 8000 (y 8080):** Si el equipo anfitrión mantiene en ejecución otra instancia local del proyecto o servicio en el puerto `8000` (o `8080`), se produce una colisión de puertos al iniciar los contenedores. **Resolución:** detener preventivamente los contenedores o procesos locales que ocupen esos puertos antes de ejecutar el despliegue, conservando intactos sus volúmenes.
- **Aislamiento de contenedores y volúmenes para ensayos limpios:** Dado que `restaurar_demo.sh` (y `restaurar_demo.ps1`) protege los datos existentes y aborta si detecta tablas en el esquema `public`, no se debe sobrescribir una base ya inicializada ni ejecutar `docker compose down -v` para borrar volúmenes existentes. **Resolución:** definir un `COMPOSE_PROJECT_NAME` independiente (por ejemplo `motor-cobranza-demo`, o un nuevo identificador exclusivo si se requiere otro ensayo limpio) en `.env` y en la sesión de terminal (`export COMPOSE_PROJECT_NAME=motor-cobranza-demo` en Linux/macOS o `$env:COMPOSE_PROJECT_NAME = 'motor-cobranza-demo'` en Windows PowerShell) tanto al restaurar como al desplegar, separando así los contenedores y el volumen de base de datos de cualquier instalación habitual.

## Limitación de dependencias de desarrollo

La revisión npm inicial encontró `source-map-js` 1.2.1 (alta), `vite` 5.4.21 (alta) y `esbuild` 0.21.5 (moderada), todos marcados como dependencias de desarrollo en el lockfile. Se actualizó únicamente `source-map-js` a 1.2.2 mediante un patch compatible, eliminando su aviso.

Persisten dos paquetes afectados: Vite y su dependencia esbuild. El registro no ofrece una corrección completa dentro de Vite 5; `npm audit` propone un cambio major. Ese cambio queda aplazado y no se utilizó `--force`. Los avisos incluyen exposición/lectura a través del servidor de desarrollo, manejo de source maps y condiciones específicas de Windows. No exponga Vite en una red pública. La demo Docker sirve el build estático mediante nginx, sin servidor Vite en ejecución; esto limita la exposición, pero no elimina los avisos del entorno de desarrollo.

Detalles originales: [esbuild](https://github.com/advisories/GHSA-67mh-4wv8-2f99), [Vite/source maps](https://github.com/advisories/GHSA-4w7w-66w2-5vf9), [Vite/Windows UNC](https://github.com/advisories/GHSA-v6wh-96g9-6wx3), [Vite/Windows paths](https://github.com/advisories/GHSA-fx2h-pf6j-xcff). Revisar la actualización major en una tarea separada.
