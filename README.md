# Motor Inteligente de Cobranza para PluriOne

MVP para gestionar cartera, priorizar clientes, registrar pagos, generar estrategias y auditar comunicaciones. El código en `app/` y `frontend-react/src/` es la fuente de verdad. `referencias-stitch/` es exclusivamente una referencia visual y no forma parte de la aplicación.

## Inicio rápido de demostración

Para una instalación nueva, siga la [Guía de demo para el asesor](docs/GUIA_DEMO_ASESOR.md): copie `.env.example`, complete la configuración privada y ejecute `scripts/restaurar_demo.sh` y `scripts/deploy_demo.sh`. La demo usa datos ficticios y exige `COMMUNICATIONS_REAL_ENABLED=false`; el despliegue siempre migra antes de arrancar. No restaure sobre una base operativa, no ejecute seeds ni `docker compose down -v`.

## Arquitectura

```text
React 18 + MSAL -> Nginx /backend -> FastAPI -> SQLAlchemy -> PostgreSQL 16
                                     |-> Entra: access tokens RS256 + scope delegado
                                     |-> Random Forest local (joblib)
                                     |-> Groq: estrategias y adaptación SMS
                                     |-> Twilio: SMS/WhatsApp + webhook firmado
                                     |-> SendGrid: email
```

Desarrollo con Python 3.12, React/Vite y npm; frontend Docker con Node 20 durante compilación y Nginx en ejecución; GitHub Actions usa Node 22. La interfaz conserva el diseño empresarial existente. Los datos de negocio persisten en PostgreSQL; las credenciales de proveedores permanecen en el backend.

| Ruta/archivo | Responsabilidad |
|---|---|
| `app/main.py` | Métricas, clientes, pagos, riesgo, estrategias y comunicaciones |
| `app/auth.py` | Discovery/JWKS de Entra y autorización de API |
| `app/models.py`, `app/database.py`, `app/migrate.py` | Modelo, sesiones y migración aditiva |
| `app/ml/` | Seis features, entrenamiento sintético y artefacto existente |
| `app/services/`, `app/twilio_webhook.py` | Adaptadores externos y callbacks |
| `frontend-react/src/` | Dashboard, ficha, pagos, historial y sesión MSAL |
| `tests/`, `frontend-react/tests/` | Tests locales aislados |
| `.github/workflows/ci.yml` | Backend tests/compile/check, frontend tests/lint/build e imágenes Docker |

### Endpoints principales

Las rutas de negocio requieren un access token Microsoft Entra en `Authorization: Bearer <access_token>`. No usar el ID token ni tokens de Microsoft Graph como Bearer de esta API. Las rutas siguientes son las de FastAPI; desde el proxy Docker se antepone `/backend`.

| Método | Ruta | Función |
|---|---|---|
| GET | `/auth/me` | Identidad Microsoft: ID (oid), nombre y email opcional |
| GET | `/api/metricas` | Métricas agregadas de la cartera |
| GET | `/api/clientes` | Búsqueda y filtros: `query`, `segmento`, `analizado`, `solo_con_deuda`, `estatus_deuda`, `orden` |
| GET | `/api/clientes/{cliente_id}` | Ficha, deudas, pagos, última estrategia y comunicaciones |
| GET | `/api/cartera-priorizada` | Clientes con deuda activa, por riesgo × saldo descendente |
| POST | `/api/deudas/{deuda_id}/pagos` | JSON con `monto`; registra pago y actualiza saldo/riesgo |
| POST | `/ia/calcular-riesgo/{cliente_id}` | Calcula y guarda probabilidad, score y segmento |
| POST | `/ia/analizar-riesgo/{cliente_id}` | Genera o reutiliza estrategia; `?regenerar=true` solicita otra |
| GET | `/ia/historial/{cliente_id}` | Estrategias recientes primero; 404 cuando no hay historial |
| GET | `/api/integraciones/estado` | Disponibilidad efectiva booleana de los canales, sin consultar proveedores |
| POST | `/api/comunicaciones` | JSON con `cliente_id`, `canal`, `mensaje`; 201 con modo y estado del registro |
| POST | `/api/webhooks/twilio/status` | Callback de estado; requiere firma Twilio, no token Entra |

Un 201 de comunicaciones significa que se creó el registro: revisar `modo`, `estado` y `provider_status` para conocer el resultado. No acredita envío ni entrega por sí solo. El endpoint rechaza cliente inexistente con 404, datos inválidos con 422 y cliente sin deuda activa con 409. `/auth/login` no existe como método de acceso.

## Configuración

Usar [.env.example](.env.example) como plantilla únicamente si no existe `.env`. No copiar claves a variables `VITE_*`: estas se incorporan al JavaScript público. No compartir `.env` ni incluirlo en imágenes o Git.

| Variables (solo nombres) | Uso |
|---|---|
| `DATABASE_URL` | Conexión PostgreSQL en desarrollo local |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQL en Compose |
| `DB_HOST` | Compose lo establece; tiene prioridad sobre `DATABASE_URL` |
| `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_REQUIRED_SCOPE` | Validación de API |
| `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_API_SCOPE`, `VITE_ENTRA_REDIRECT_URI` | SPA MSAL |
| `VITE_API_URL`, `CORS_ORIGINS` | Acceso a API y orígenes permitidos |
| `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_SMS_MODEL` | Estrategias y modelo independiente de SMS |
| `COMMUNICATIONS_REAL_ENABLED` | Habilitación explícita de envíos reales |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `TWILIO_WHATSAPP_NUMBER`, `TWILIO_STATUS_CALLBACK_URL` | SMS, WhatsApp y validación de callbacks |
| `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, `SENDGRID_FROM_NAME` | Email y remitente verificado |

Las variables opcionales aparecen comentadas en la plantilla para conservar los valores predeterminados del código. Configurar modelos Groq disponibles en la cuenta: la disponibilidad depende del plan. El modelo predeterminado de estrategias heredado puede no estar habilitado para cuentas Free/Developer; configurar `GROQ_MODEL` explícitamente. Esta auditoría no cambia modelos ni secretos existentes.

### Microsoft Entra

Se reutiliza **el único App Registration existente** para SPA y API, single tenant y sin client secret. No cambiar IDs, tenant ni scopes de una instalación funcional. La tabla legacy de administradores se conserva, pero no autentica; no hay login JWT local de respaldo.

Verificar la configuración existente antes de reconstruir:

1. **Registro y redirecciones:** conservar la plataforma SPA y registrar la URI exacta de retorno. Docker usa `http://localhost:8080/`; Vite local necesita también `http://localhost:5173/` en el mismo registro si se utiliza esa dirección. `VITE_ENTRA_REDIRECT_URI` debe coincidir con la URI de ese entorno y también se usa tras logout.
2. **Identificadores:** `ENTRA_CLIENT_ID` y `VITE_ENTRA_CLIENT_ID` corresponden al mismo registro; `ENTRA_TENANT_ID` y `VITE_ENTRA_TENANT_ID`, al mismo tenant. No añadir secretos Microsoft a React.
3. **API y scope:** conservar el Application ID URI `api://<CLIENT_ID>` y el scope delegado habilitado `access_as_user`. El frontend exige `VITE_ENTRA_API_SCOPE` con la forma exacta `api://<CLIENT_ID>/access_as_user`; el backend usa `ENTRA_REQUIRED_SCOPE`. Estos marcadores indican relaciones entre valores, no credenciales que deban copiarse.
4. **Versión y consentimiento:** verificar `api.requestedAccessTokenVersion: 2` en el manifiesto del registro y el consentimiento delegado según la política del tenant. El backend exige issuer v2, audience igual al client ID, firma RS256, expiración, tenant y scope; verifica `nbf` cuando está presente y rechaza tokens v1 o de Graph. La aplicación solicita su scope propio, no `User.Read`.
5. **Usuarios permitidos:** si el acceso debe limitarse al personal de cobranza, configurar asignación requerida y usuarios/grupos autorizados en la aplicación empresarial. El scope no otorga por sí mismo un rol administrativo; el MVP no implementa roles de aplicación.
6. **Aplicar entorno:** las variables `VITE_*` se resuelven al compilar, por lo que cambiar IDs, scope o URI requiere reconstruir frontend. Los cambios de entorno backend requieren recrearlo. En local, exportar las variables frontend o usar `frontend-react/.env.local`; Vite no carga el `.env` de la raíz. Ver el procedimiento Docker más abajo.
7. **Prueba manual sin envíos:** mantener comunicaciones reales deshabilitadas, abrir la SPA e iniciar sesión con Microsoft. Confirmar `/auth/me` y dashboard; recargar, volver a la pestaña y probar atrás/adelante. Cerrar sesión y verificar que no reaparezca cartera sin revalidación. No copiar tokens a logs o herramientas públicas.

MSAL administra la caché en `sessionStorage`. Antes de cada solicitud se obtiene un access token mediante `acquireTokenSilent`; si Microsoft exige interacción, se utiliza `acquireTokenRedirect`. `/auth/me` confirma la sesión antes de mostrar datos. Logout utiliza `logoutRedirect` y desmonta los datos sensibles; restauración de página y navegación revalidan la sesión. Logout no revoca instantáneamente todos los access tokens ya emitidos: la API continúa verificando su expiración.

Sin configuración frontend válida se muestra un aviso y no se permite login. El backend responde 401 por token ausente/inválido, 403 por scope insuficiente y 503 si la configuración o la obtención de claves falla. Los tests locales simulan claves y tokens; las comprobaciones interactivas están en [AUDITORIA_MVP.md](docs/AUDITORIA_MVP.md#pruebas-externas-para-el-propietario).

## Instalación local

Requisitos: Python 3.12, entorno virtual, PostgreSQL disponible y Node/npm compatibles con las dependencias actuales. Crear una base de desarrollo sin sobrescribir datos existentes. Desde la raíz:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-dev.txt
# Solo cuando todavía no existe .env:
test -e .env || cp .env.example .env
```

Completar las variables de PostgreSQL, Entra y Groq localmente. En una base existente respaldar antes de cualquier migración y detener escrituras concurrentes durante el despliegue:

```bash
python -m app.migrate
uvicorn app.main:app --reload
```

En otra terminal, configurar las variables `VITE_*` en el entorno o en `frontend-react/.env.local`; Vite no carga automáticamente el `.env` de la raíz:

```bash
cd frontend-react
npm ci
npm run dev
```

Frontend: http://localhost:5173. API local: http://127.0.0.1:8000 y documentación en `/docs`. La migración añade columnas faltantes de comunicaciones, vínculo pago/deuda, probabilidad y contexto de estrategias, e índices; no atribuye estados de proveedor ni relaciones a registros históricos desconocidos. `create_all` por sí solo no actualiza tablas existentes.

Solo para una base controlada de demostración, los seeds crean clientes faltantes e historial sintético sin resetear cartera:

```bash
python -m app.seed
python -m app.ml.seed_historial
```

No ejecutar seeds sobre datos reales como parte de una auditoría. El artefacto ML existente se conserva; `python -m app.ml.train_model` lo reemplaza y requiere una decisión explícita.

## Docker y persistencia

Compose incluye PostgreSQL con volumen `postgres_data` y healthcheck; el backend espera a la base saludable. Los puertos backend/frontend se publican solo en localhost; PostgreSQL no publica puerto. El frontend depende del inicio del backend, sin healthcheck adicional. `.env` queda fuera de los contextos de imagen.

Instalación o actualización controlada:

```bash
docker compose config --quiet
docker compose up -d db
docker compose build backend frontend
docker compose stop backend
docker compose run --rm --no-deps backend python -m app.migrate
docker compose up -d backend frontend
```

Abrir http://localhost:8080. Nginx sirve la SPA y proxy `/backend/`. El volumen conserva datos al recrear servicios. **No ejecutar `docker compose down -v`: elimina los volúmenes y puede destruir la BD.** No cambiar el nombre del proyecto Compose ni el volumen existente durante una actualización. Las variables `VITE_*` se aplican al compilar; las de backend se aplican al recrear el contenedor.

Para cambios sin migración, comprobar primero `docker compose config --quiet` y confirmar que PostgreSQL y los servicios dependientes ya están disponibles. Reconstruir y recrear exclusivamente el servicio cambiado:

```bash
# Backend
docker compose up -d --build --force-recreate --no-deps backend
# Frontend
docker compose up -d --build --force-recreate --no-deps frontend
```

Si solo cambian variables backend en `.env`, no hace falta recompilar: `docker compose up -d --force-recreate --no-deps backend` vuelve a aplicarlas. Un simple `docker compose restart backend` no incorpora cambios de entorno. Cambiar variables `VITE_*` sí requiere la reconstrucción frontend indicada arriba. Estos comandos no ejecutan migraciones ni seeds.

### Migración de una base existente

No iniciar el backend nuevo sobre un esquema antiguo sin migrarlo. Primero confirmar la base y el volumen que se conservarán, detener escrituras y hacer un respaldo; proteger el archivo y probar restauración en una base separada. El comando de respaldo está en [MANTENIMIENTO.md — Respaldos](docs/MANTENIMIENTO.md#respaldos). Con PostgreSQL disponible, aplicar esta secuencia desde la raíz:

```bash
docker compose config --quiet
docker compose build backend frontend
docker compose stop backend
# Realizar aquí el respaldo, con el backend detenido.
docker compose run --rm --no-deps backend python -m app.migrate
# Continuar únicamente si la migración terminó correctamente.
docker compose up -d --force-recreate --no-deps backend frontend
```

La migración se ejecuta con la imagen backend recién construida, antes de arrancar el servicio actualizado. Si falla, mantenerlo detenido hasta resolver la causa. En local, detener el backend, respaldar la base configurada y ejecutar `python -m app.migrate` antes de iniciar Uvicorn.

`app.migrate` es aditivo e idempotente. Crea tablas faltantes y añade únicamente columnas que no existan:

| Tabla | Columnas añadidas si faltan |
|---|---|
| `comunicaciones` | `modo`, `estado`, `provider`, `external_id`, `error_tecnico`, `provider_status`, `estrategia_id` (FK a `historial_mensajes`) |
| `pagos` | `deuda_id`, anulable y con FK a `deudas` |
| `clientes` | `probabilidad_pago_a_tiempo` |
| `historial_mensajes` | `contexto_hash` |

Son diez columnas posibles, más índices en `pagos.deuda_id`, `comunicaciones.estrategia_id` y `comunicaciones.external_id`; este último no es único. PostgreSQL aplica la migración dentro de una transacción y con bloqueo asesor para serializar migraciones. No borra datos ni reconstruye tablas; no asocia pagos antiguos por inferencia ni rellena estados de proveedor históricos. El backend valida tablas y columnas al arrancar y aborta ante un esquema incompatible, sin crearlo ni migrarlo automáticamente. No ejecutar seeds ni reentrenamiento como parte de una actualización de esquema.

## Cartera, métricas y pagos

Buscar por ID, folio o nombre parcial; filtrar por riesgo/análisis/estado de deuda y ordenar por prioridad, saldo, atraso, vencimiento o nombre. La prioridad usa score × saldo activo. Seleccionar una fila consulta la ficha y no genera automáticamente una estrategia.

Métricas consultadas en BD:

- Deudores activos: clientes distintos con algún saldo positivo.
- Saldo vencido: obligaciones con saldo positivo y vencimiento pasado o estado almacenado de mora.
- Clientes con estrategia: clientes distintos con historial, incluyendo registros heredados.
- Sin evaluar: segmento `No definido` o nulo; se calcula sobre clientes registrados.
- Recuperación: `(monto original total − saldo pendiente total) / monto original total`, con cero cuando no hay monto original. No suma pagos sintéticos para inflar recuperación.

Los pagos validan monto positivo con dos decimales, no permiten exceder el saldo y bloquean cliente/deuda en la transacción PostgreSQL. Actualizan saldo, historial y riesgo; la liquidación deja deuda pagada y excluye al cliente de cartera activa. Fecha del pago: día actual del servidor. Un fallo revierte toda la operación. No hay claves de idempotencia distribuidas: no reenviar un pago cuyo resultado sea incierto sin consultar primero el historial.

## Riesgo y Groq

Las features exactas son `pct_pagos_tarde`, `promedio_dias_atraso`, `num_pagos_historicos`, `monto_promedio_pago`, `monto_pendiente_actual` y `num_deudas_activas`. Se consideran pagos con `dias_atraso` conocido y obligaciones con saldo positivo. Sin historial se usan supuestos heredados; el modelo no incluye directamente la fecha de vencimiento actual. El contexto enviado a Groq sí incluye vencimientos, pagos recientes, saldo y riesgo; excluye teléfono, email y credenciales.

Random Forest combina 200 árboles para estimar pago a tiempo; `score_riesgo = round(1 - probabilidad_pago_a_tiempo, 3)`. Alto riesgo desde 0.66, riesgo medio desde 0.33 y bajo por debajo de 0.33. El script de entrenamiento genera 2,000 observaciones sintéticas y usa una división estratificada 80%/20%. Sus métricas de precision, recall, F1 y AUC-ROC **no acreditan precisión ni probabilidad calibrada en una cartera real**.

Sin deuda activa no se ejecuta ML ni Groq y riesgo/probabilidad no aplican. No se reentrena ni altera arbitrariamente el modelo. Los valores sin historial son supuestos, no neutralidad demostrada. Antes de uso operativo se requiere evaluación temporal con datos reales autorizados, calibración y revisión de equidad; ver [MODELO_ML.md](docs/MODELO_ML.md). Los pagos sintéticos sirven para demostrar features y no reducen el saldo ni prueban recuperación real.

Procesar reutiliza la estrategia almacenada. Regenerar añade otra sin borrar las anteriores. Falta de configuración devuelve 503; timeout/error o respuesta inválida devuelve 502 sin estrategia ficticia ni registro incompleto. SDK con timeout y sin reintentos automáticos. El prompt prohíbe inventar descuentos o consecuencias financieras; revisar personalmente todo mensaje generado antes de enviarlo.

## Comunicaciones y estados

| Canal | Comportamiento |
|---|---|
| Email | Mensaje completo; SendGrid opcional; HTTP 202 significa aceptación, no entrega ni lectura |
| SMS | Adaptación Groq independiente, limpieza y límite de 150 caracteres; Twilio opcional |
| WhatsApp | Mensaje completo; destino mexicano se normaliza de `+52` a `+521` solo para WhatsApp; no modifica el contacto ni SMS |
| Llamada | Guion adaptado y registro simulado; Voice real no está habilitado |

La API rechaza comunicaciones de cobranza para clientes sin deuda activa antes de adaptar o enviar mensajes. **Llamada sigue simulada**, incluso si otros proveedores están habilitados; no se ejecuta Twilio Voice.

### Interruptor de comunicaciones reales

`COMMUNICATIONS_REAL_ENABLED` ausente, vacío o con un valor distinto de `true` deshabilita todos los envíos, aunque existan credenciales. El código elimina espacios y compara sin distinguir mayúsculas. Con `true`, cada canal sigue necesitando configuración completa: si falta, se registra como simulado. El cliente no puede habilitar envíos mediante el payload.

| Canal real | Configuración necesaria además del interruptor |
|---|---|
| Email | `SENDGRID_API_KEY`, remitente válido `SENDGRID_FROM_EMAIL`; nombre opcional `SENDGRID_FROM_NAME` |
| SMS | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, origen E.164 `TWILIO_PHONE_NUMBER` |
| WhatsApp | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, origen válido `TWILIO_WHATSAPP_NUMBER`, con o sin prefijo `whatsapp:` |

`GET /api/integraciones/estado` requiere Entra y devuelve disponibilidad booleana derivada de la configuración; no comprueba credenciales, permisos o entrega con el proveedor. En un canal real se valida también el contacto del cliente; datos inválidos dan 422 antes de contactar al proveedor. Activar el interruptor habilita todos los canales que estén configurados, no solo el seleccionado.

En simulación no se contacta Twilio/SendGrid, pero SMS y Llamada siguen necesitando Groq para adaptar el mensaje. Un fallo de adaptación cancela el registro y devuelve 502, o 503 si Groq no está configurado. Un fallo de envío real se conserva como real/Fallido; no se convierte en éxito simulado ni se reintenta automáticamente.

Email muestra «Enviado (aceptado; entrega no confirmada)». Twilio conserva únicamente el SID real retornado o correlacionado mediante callback firmado; no se inventa SID cuando falla `messages.create`. `provider_status` no se infiere para registros históricos ni a partir de aceptación de creación. El frontend distingue `accepted`, `queued`, `sending`, `sent`, `delivered`, `read`, `failed` y `undelivered`; `read` solo aplica a WhatsApp.

### Significado de modo, estado y provider_status

| Campo | Significado |
|---|---|
| `modo` | `simulado` o `real`; identifica si se intentó un envío externo |
| `estado` | Etiqueta de la aplicación: intención, aceptación, progreso o fallo |
| `provider_status` | Estado exacto confirmado por callback Twilio; puede ser NULL y no se inventa para históricos |
| `exitoso` | En registros actuales es false para simulación/fallo y true tras aceptación o progreso válido; **no demuestra entrega ni lectura** |
| `external_id` | Identificador del proveedor para conciliación; permanece en BD, no en la respuesta frontend |

| Situación | Estado de aplicación / proveedor | Lo que se puede afirmar |
|---|---|---|
| Simulada | `Simulado`, sin estado de proveedor | Se registró el mensaje; no hubo envío externo |
| Intención real | `Pendiente`, estado de proveedor nulo | Se persistió antes de llamar al proveedor |
| Creación aceptada | Inicialmente `Enviado`, estado de proveedor aún nulo | Proveedor aceptó la solicitud; entrega no confirmada |
| Callback de aceptación | `Aceptado` / `accepted` | Aceptado por Twilio; entrega no confirmada |
| En progreso | `En cola` / `queued`, `Enviando` / `sending`, `Enviado` / `sent` | Todavía no confirma entrega |
| Entregada | `Entregado` / `delivered` | Twilio notificó entrega |
| Leída | `Leído` / `read`, solo WhatsApp | Twilio notificó lectura |
| Fallida | `Fallido` / `failed` o `No entregado` / `undelivered` | Rechazo o fallo de entrega notificado |

Un error antes de crear SID deja Fallido con `ProviderRequestFailed`, sin SID ficticio ni `provider_status` inventado. Un timeout puede ocultar una aceptación: consultar historial y panel del proveedor antes de reenviar. SendGrid no tiene confirmación de entrega/lectura implementada y mantiene la etiqueta de aceptación. Los registros heredados pueden tener campos nulos y no acreditan entrega.

### Adaptación y prueba controlada de un SMS

Email y WhatsApp conservan el mensaje recibido. SMS utiliza su modelo Groq independiente: solicita aproximadamente 120–130 caracteres, limpia formato y razonamiento etiquetado, normaliza espacios, translitera acentos y elimina caracteres fuera del subconjunto GSM-7 admitido. El resultado tiene como máximo 150 caracteres; si excede el límite se conserva un prefijo de palabras completas. Se admite texto utilizable con `finish_reason=stop` o `length`; si no queda texto válido, no se envía. El historial de comunicaciones guarda el texto adaptado y no modifica el historial de estrategias. Revisar fidelidad: el límite puede omitir información final y el prompt no garantiza exactitud financiera.

Para **un único SMS real**, realizar manualmente:

1. Usar un cliente ficticio/controlado con deuda activa, estrategia revisada y teléfono E.164 de un destinatario propio autorizado; en Trial debe cumplir las restricciones de destinatarios y del número emisor de la cuenta.
2. Confirmar Groq y su modelo SMS, las tres variables Twilio SMS de la tabla y, si se quieren estados finales, el callback público descrito abajo. Configurar los valores localmente, sin copiarlos a código, logs o Git.
3. Establecer `COMMUNICATIONS_REAL_ENABLED` en `true` y aplicar el entorno sin reconstruir la imagen:

   ```bash
   docker compose config --quiet
   docker compose up -d --force-recreate --no-deps backend
   ```

4. Iniciar sesión Microsoft, seleccionar ese cliente, revisar el mensaje, elegir **SMS** y confirmar **Modo: Real**. Pulsar **Enviar comunicación una sola vez**.
5. Revisar el registro, texto de hasta 150 caracteres y estado; comprobar en Twilio Console el resultado y segmentos. Si falla o hay timeout, no repetir hasta conciliar historial/proveedor. Un 201 no garantiza aceptación o entrega.
6. Establecer nuevamente `COMMUNICATIONS_REAL_ENABLED` en `false` y recrear backend con el mismo comando para volver a simulación. Durante la prueba no usar otros canales aunque aparezcan habilitados.

Este procedimiento no se ejecuta en tests. Para verificaciones aisladas y el resto de pruebas externas, ver [AUDITORIA_MVP.md](docs/AUDITORIA_MVP.md#pruebas-externas-para-el-propietario).

### Webhook Twilio

`POST /api/webhooks/twilio/status` usa `RequestValidator` y `X-Twilio-Signature`, además de comprobar cuenta, SID y correlación. Usa la URL pública configurada; no confía en Host del proxy. El callback se construye como URL base más `?comunicacion_id=<id>`; la query forma parte de la firma y se conserva. Configurar la variable con la URL base del endpoint sin query.

Callbacks válidos responden 204; firma inválida 403; parámetros inválidos 400; formato distinto al esperado 415; payload excesivo 413; configuración ausente 503. No crean comunicaciones; duplicados y retrocesos no sobrescriben estados posteriores. La correlación temprana admite intenciones reales pendientes sin SID. Si el envío falla sin SID y después llega un callback tardío, no se transforma automáticamente el fallo: conciliar con el proveedor antes de reintentar.

### Procedimiento del Status Callback

1. Publicar únicamente el endpoint mediante HTTPS hasta FastAPI, directamente como `/api/webhooks/twilio/status` o mediante Nginx como `/backend/api/webhooks/twilio/status`. La ruta no debe exigir Entra ni modificar formulario o firma. Mantener protegidas las demás rutas de negocio.
2. Configurar `TWILIO_STATUS_CALLBACK_URL` con esa URL pública exacta, sin query, fragmentos ni credenciales; el código solo admite HTTP para localhost/127.0.0.1 en desarrollo, lo cual no da acceso público a Twilio. Confirmar también token y cuenta Twilio en backend, sin exponerlos.
3. Aplicar primero la migración si la base existente no tiene las columnas actuales. Después de cambiar el entorno, ejecutar:

   ```bash
   docker compose config --quiet
   docker compose up -d --force-recreate --no-deps backend
   ```

4. Cada nuevo SMS/WhatsApp añade `status_callback` al SDK con `?comunicacion_id=<id>`. No es necesario agregar esa query a la variable ni configurar retrospectivamente mensajes históricos. Si la URL queda vacía, el envío se crea sin callback y el endpoint responde 503 cuando no está configurado.
5. Un POST sin firma válida debe devolver 403, sin actualizar comunicaciones. Un callback válido firma la URL pública **incluida la query original** y todos los campos del formulario; omitir campos o cambiar URL rompe la validación. `AccountSid` se compara cuando está configurado. Un POST falso no valida la conectividad desde Twilio ni la entrega real.
6. Para verificar firmas y estados sin proveedores, ejecutar la suite aislada:

   ```bash
   venv/bin/pytest tests/test_twilio_callbacks.py -q
   ```

   Usa SQLite temporal, token ficticio, firmas de la librería oficial y TestClient; no contacta Twilio. Cubre correlación temprana, repeticiones, retrocesos y estados `accepted`, `delivered`, `read`, `failed`, entre otros.
7. La comprobación externa se hace con un solo envío controlado cuando esté autorizado. Verificar la asociación a la misma comunicación y usar **Actualizar estados** en la ficha: el frontend consulta el detalle, sin polling ni WebSocket. Un SID desconocido/ambiguo o estado no soportado devuelve 204 sin cambios; no es prueba de correlación exitosa.

Los fallos de entrega guardan únicamente un código numérico seguro como `TwilioError:<codigo>` o la categoría genérica; no guardan `ErrorMessage` ni el formulario recibido. Twilio/Sandbox requiere destinatario unido, origen configurado, túnel público estable y permisos del Trial. Si cambia la dirección del túnel, actualizar la variable y recrear backend antes de nuevos envíos. El webhook no realiza consultas al proveedor ni envíos. Las verificaciones reales pendientes están detalladas en [AUDITORIA_MVP.md](docs/AUDITORIA_MVP.md#pruebas-externas-para-el-propietario).

Los logs de rechazo Twilio solo muestran canal, HTTP status y código numérico. La BD conserva `ProviderRequestFailed` para errores de envío; el frontend muestra un fallo genérico sin exponer detalles del proveedor. No registrar excepciones completas, request URL, teléfono, body, callback URL, Account SID, token o headers. No activar trazas HTTP de SDK.

## Tests y CI

Desde un entorno con dependencias instaladas:

```bash
source venv/bin/activate
pytest
python -m compileall app
python -m pip check
cd frontend-react
npm test
npm run lint
npm run build
cd ..
git diff --check
```

Backend usa SQLite temporal, tokens RSA de prueba, SDK/JWKS simulados, configuración externa eliminada y conexiones externas bloqueadas. No utiliza la BD de desarrollo ni realiza envíos. Frontend prueba componentes/helpers y el transporte autenticado con mocks. No sustituyen pruebas del navegador, concurrencia PostgreSQL o entrega real.

GitHub Actions ya ejecuta tests/compilación/check de backend, tests/lint/build de frontend y compilación de ambas imágenes. Su ejecución remota queda pendiente hasta que el usuario decida guardar y publicar los cambios.

## Limitaciones y cierre del MVP

Ver [AUDITORIA_MVP.md](docs/AUDITORIA_MVP.md) para evidencia, correcciones y pendientes. Mantener datos ficticios durante demostraciones. El MVP conserva columnas monetarias Float, entrenamiento sintético y ausencia de roles de aplicación/rate limiting/idempotencia distribuida. Restringir asignación de usuarios en Entra y servir mediante TLS antes de uso productivo.

La auditoría npm detecta vulnerabilidades de Vite/esbuild de desarrollo; la actualización compatible queda pendiente. El contenedor final sirve estáticos con Nginx y no incluye el servidor Vite. No publicar el servidor de desarrollo.

### Analítica IA / Impacto de Cobranza

Nueva sección empresarial con cartera actual, evolución por snapshots, pagos registrados,
estrategias y efectividad de Email/SMS/WhatsApp. **Recuperación asociada a IA** representa
una asociación temporal de hasta 7 días tras un envío ligado a una estrategia; no demuestra
causalidad. Excluye simulaciones y pagos del mismo día. El histórico empieza en el primer
snapshot real y registra los días consultados, sin reconstruir el pasado.

Ejecutar `python -m app.migrate` antes del backend actualizado. La migración es aditiva,
idempotente y conserva datos históricos. Consultar [fórmulas, periodos, activación y
limitaciones](docs/ANALITICA_IA.md).

## Base de datos de demostración

[db/base-de-datos.sql](db/base-de-datos.sql) contiene el esquema PostgreSQL actual y un conjunto **completamente ficticio** para la entrega académica: 15 clientes, 23 deudas, 40 pagos, 24 estrategias históricas, 24 comunicaciones simuladas y 15 snapshots de fechas distintas. Incluye constraints, claves foráneas, índices y secuencias; la tabla legacy `administradores` se conserva vacía. No contiene credenciales, datos personales reales, teléfonos, SIDs ni identificadores de proveedores. Los nombres están marcados como ficticios y todos los correos usan `example.invalid`.

Importar **exclusivamente en una base PostgreSQL 16 vacía y separada**. No importar sobre la base operativa ni ejecutar los seeds generales después de restaurar:

```bash
createdb motor_cobranza_demo
psql -X -v ON_ERROR_STOP=1 --single-transaction -d motor_cobranza_demo -f db/base-de-datos.sql
```

Ejemplo Docker aislado, sin Compose ni volúmenes de la instalación actual. `--network none` evita publicar servicios; la autenticación trust es solo para este contenedor local efímero, que no debe exponerse ni usarse en producción:

```bash
docker run -d --name plurione-demo-db --network none \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=motor_cobranza_demo postgres:16-alpine
# Esperar hasta que pg_isready indique que PostgreSQL acepta conexiones:
docker exec plurione-demo-db pg_isready -U postgres -d motor_cobranza_demo
docker exec -i plurione-demo-db psql -U postgres -X -v ON_ERROR_STOP=1 \
  --single-transaction -d motor_cobranza_demo < db/base-de-datos.sql
```

Para usar la demo en el dashboard, configurar el backend de demostración por separado apuntando a la nueva base; no sobrescribir el `.env` ni recrear los servicios operativos. `DB_HOST`, cuando está definido, tiene prioridad sobre `DATABASE_URL`. **`COMMUNICATIONS_REAL_ENABLED=false` debe permanecer así durante toda la demostración.** Los accesos Microsoft se proporcionan por separado: el SQL no crea cuentas Entra ni contiene contraseñas de acceso. Las consultas locales de validación sustituyen Entra únicamente en un TestClient aislado; no prueban el login Microsoft.

Los scores, estrategias y snapshots son datos inventados para ilustrar la interfaz, no resultados de una evaluación real ni llamadas a Groq. Todos los pagos tienen deuda asociada y los saldos concilian con sus importes. Las comunicaciones son exclusivamente simuladas: efectividad por canal muestra simulaciones, pero cero envíos reales, entregas y recuperación atribuida a IA, conforme a las reglas actuales. El dump usa fechas fijas con fecha base **2026-10-06**; con el paso del tiempo los vencimientos y filtros de periodo cambian. `/api/analitica/evolucion` actualiza el snapshot de hoy, únicamente en la base demo conectada.

### Regenerar y verificar la entrega

Los scripts nuevos no cargan `.env` ni usan la conexión operativa. Requieren las dependencias Python del proyecto, los binarios PostgreSQL 16 y ejecutarse como usuario no root. Desde la raíz:

```bash
venv/bin/python scripts/generar_base_demo.py
# Opcional: desplazar todas las fechas para una presentación posterior:
venv/bin/python scripts/generar_base_demo.py --fecha-base AAAA-MM-DD
# Si PostgreSQL está instalado en otro directorio:
venv/bin/python scripts/generar_base_demo.py --pg-bin /ruta/a/postgresql/16/bin
```

El generador inicializa un clúster nuevo en `/tmp/motor-entrega-*`, sin TCP, crea `motor_cobranza_entrega_tmp`, aplica los modelos y las migraciones locales actuales, y ejecuta `scripts/seed_entrega.py`. Este seed rechaza conexiones ajenas al socket temporal y bases que ya tengan tablas. Exporta con `pg_dump --format=plain --no-owner --no-privileges`, importa **solo el SQL** en otra base vacía (`motor_cobranza_validacion_tmp`) y verifica esquema, relaciones, índices, secuencias, conteos, conciliación de saldos y contenido sensible. Después consulta métricas, clientes, cartera y analítica con TestClient, bloqueando conexiones externas. No ejecuta seeds adicionales, envíos ni entrenamiento del modelo. Solo copia el SQL final a `db/base-de-datos.sql` si todas las comprobaciones pasan.

El clúster temporal se detiene al finalizar y su ruta se informa para inspección; no borra bases ni volúmenes existentes. La regeneración reproduce el esquema y los datos para una misma fecha base; cabeceras y marcadores internos de `pg_dump` pueden variar. No ejecutar estos scripts en producción.
