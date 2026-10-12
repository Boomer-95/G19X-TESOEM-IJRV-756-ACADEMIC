# QA

## Suite de referencia verificada

La última verificación anterior a los ajustes de auditoría externa aprobó **388 tests backend y 36 tests frontend**. Estos son los resultados de referencia actuales; las cifras de las secciones siguientes describen verificaciones históricas y no deben interpretarse como el total vigente.

Las mejoras de esta revisión añaden cobertura del ErrorBoundary raíz y de diagnóstico seguro de restauración. El total posterior se obtiene ejecutando las suites, sin reutilizar ni inventar cifras. Los tests de backend usan bases aisladas y proveedores mockeados; no se ejecuta la restauración sobre PostgreSQL operativo.

## Status Callback Twilio

319 pruebas Python y 11 de frontend aprobadas (330 total). La suite del callback usa RequestValidator real con token/SID ficticios, TestClient, SDK Twilio mockeado y SQLite en memoria con conexiones externas bloqueadas. Incluye delivered/read/failed/undelivered y estados intermedios, firma válida/inválida/ausente, campos nuevos en la firma, URL pública detrás de proxy, ausencia de JWT, SID desconocido/ausente/ambiguo, formato incorrecto, AccountSid ajeno, repeticiones, conservación de mensaje/cliente/canal, aislamiento de simulados/Email/Voice, eventos atrasados, códigos de error seguros, límite de body y callback temprano que no se sobrescribe al registrar el envío. La migración se ejecuta dos veces sobre datos heredados de prueba y conserva filas, con provider_status inicialmente NULL.

Frontend distingue aceptación, entrega, lectura, fallos e históricos; SendGrid no afirma entrega. Se agregan pruebas de etiquetas y se conservan tests de un POST por clic/solicitud pendiente. npm test, lint y build correctos; compileall app y git diff --check correctos. Una advertencia heredada Starlette/AnyIO. No se ejecutó la migración sobre PostgreSQL existente ni se hicieron llamadas reales, envíos, commit o push. El bloqueo de filas usa PostgreSQL SELECT FOR UPDATE; SQLite no valida su concurrencia real. Prueba local aislada y configuración pública en README, sección Status Callback de Twilio.

## Alias mexicano de destino WhatsApp

`twilio_service.normalizar_destino_whatsapp()` transforma exclusivamente números mexicanos +52 con diez dígitos nacionales al alias +521 observado en el Sandbox. No duplica el 1 de destinos ya +521, conserva otros países y exige sintaxis E.164. Se aplica solo al destino WhatsApp antes de añadir `whatsapp:`; no modifica el remitente ni `Cliente.telefono`. SMS usa exactamente el número original y no invoca esta función. WhatsApp conserva el mensaje largo original; no se modifica Groq, Email, Voice ni la base existente.

Se añaden 14 casos con mocks: transformación mexicana, alias existente, EE.UU., otro país, idempotencia, formato inválido y seis casos integrados por canal/destino. Se comprueba el argumento enviado al SDK mockeado, el cuerpo original de WhatsApp, SMS sin transformación y el teléfono persistido tras recargar el cliente desde SQLite de pruebas.

Validación: 283 pruebas Python y 2 pruebas de componente aprobadas (285 total); compileall app y git diff --check correctos. Una advertencia heredada Starlette/AnyIO. Sin llamadas reales a proveedores ni envíos, commit o push. Frontend sin modificaciones ni reconstrucción.

Para reconstruir y recrear exclusivamente backend desde la raíz:

```bash
docker compose up -d --build --force-recreate --no-deps backend
```

Tras reconstruir, el cambio queda preparado para una única prueba real de WhatsApp con el destinatario incorporado al Sandbox. No se ejecutó esa prueba durante esta actualización; el estado final de entrega deberá comprobarse en Twilio.

Ejecutar desde la raíz con el entorno virtual activado:

```bash
pytest
python -m compileall -q app tests
python -m pip check
cd frontend-react
npm test
npm run lint
npm run build
```

Las fixtures deshabilitan dotenv y usan SQLite en memoria, tokens Entra firmados con RSA efímera, discovery/JWKS y Groq mockeados. No leen .env, no acceden a PostgreSQL real ni hacen llamadas al proveedor. Se conserva cobertura de autenticación Entra, comunicación simulada y modelo existente.

Se prueban falta de configuración Groq (503), fallo/respuesta vacía (502, sin historial ni fallback), contexto mínimo, generación, reutilización, regeneración, invalidación tras pago y COUNT DISTINCT. Búsqueda por nombre/ID/folio, filtros, clientes sin evaluar, detalle y fechas pasadas/futuras. Pagos parciales/totales, sobrepago, montos inválidos, deuda inexistente, estatus, saldo, historial, features posteriores al pago, persistencia ML y rollback sin modelo. Migración aditiva repetida y seeds idempotentes, incluyendo cliente heredado.

Docker: `docker compose config --quiet` valida sin imprimir secretos expandidos; `docker compose build backend frontend` construye sin modificar volúmenes. No ejecutar comandos para eliminar volúmenes.

Prueba manual pendiente de navegador: iniciar sesión; buscar dos nombres iguales y distinguir por folio; abrir ficha con ratón/teclado; filtrar y ordenar; procesar/reutilizar/regenerar; registrar pago y verificar actualización de ficha, cartera, métricas y riesgo; comprobar errores visibles; probar móvil y expiración de sesión.

SQLite no reproduce SELECT FOR UPDATE de PostgreSQL. Antes de producción verificar migración sobre una copia del respaldo y pagos concurrentes en PostgreSQL. No se ejecutan pruebas sobre la base existente del usuario. Los builds no sustituyen pruebas E2E. Revisar las limitaciones de dependencias documentadas en SEGURIDAD.md.

## Validación de esta actualización

65 pruebas aprobadas (14.75 s), sin llamadas reales a Groq. Dos advertencias heredadas de deprecación: Starlette/AnyIO y passlib/crypt. La suite se ejecutó fuera del sandbox porque TestClient quedaba bloqueado dentro de él. compileall y pip check correctos; lint sin errores ni advertencias; build Vite correcto. Compose validado con config --quiet sin imprimir secretos. Imágenes backend y frontend construidas correctamente; Docker usó el builder clásico porque no está instalado buildx. No se aplicó la migración ni se ejecutaron seeds sobre la base existente y no se recrearon servicios ni volúmenes.

## Ampliación de ficha y comunicaciones

Se agregaron pruebas de búsqueda parcial por apellido con nombres duplicados y folios distintos; detalle sin comunicaciones; aislamiento de comunicaciones por cliente, orden de fecha/ID, estado simulado y conservación de registros históricos. La ficha contiene ahora acciones de procesar y regenerar, registro editable de comunicación y su historial. El clic en toda la fila o el botón de folio enfoca el detalle; confirmar esta interacción también en navegador.

Validación de la ampliación: 68 pruebas aprobadas en 14.77 s, con las mismas dos advertencias heredadas. Lint sin errores ni advertencias, build Vite, compileall, pip check y Compose config --quiet correctos. No se hizo prueba E2E de navegador ni se operó sobre los datos PostgreSQL existentes.

## Selección y liquidación

La selección consulta detalle sin llamar ML/Groq ni incrementar historial. Se prueban última estrategia, cliente sin estrategia, folios distintos, saldo cero con y sin servicios configurados, score/probabilidad nulos, limpieza al liquidar, exclusión de cartera y deudores activos. Las pruebas existentes de scoring ahora crean deuda positiva. La estrategia previa se conserva incluso después de un pago: una nueva requiere regenerar=true.

Validación manual de interfaz: seleccionar fila y verificar ID automático, desplazamiento a Operación y detalle superior; verificar los cuatro estados del panel y ausencia de ficha bajo cartera. Registrar pago desde la subsección compacta y comprobar que liquidar elimina la fila pero mantiene visible el cliente seleccionado como Sin deuda activa.

Validación del flujo corregido: 79 pruebas aprobadas en 17.94 s; dos advertencias heredadas de deprecación. Lint sin errores ni advertencias; build Vite, compileall y pip check correctos. Groq mockeado y SQLite aislado; sin cambios sobre PostgreSQL. La interacción visual de navegador permanece pendiente de revisión manual.

## Autenticación Microsoft Entra ID

Pruebas automatizadas: token ausente/malformado, firma inválida, exp/nbf, issuer/audience/tid/ver, scope exacto, identidad opcional sin email, rutas protegidas, /auth/login eliminado, configuración ausente, caché/rotación JWKS, discovery restringido y fallos seguros. Los tokens son sintéticos locales; no se consulta Microsoft. Se mantienen las pruebas de negocio y comunicaciones. Los resultados numéricos de secciones anteriores son históricos.

Prueba interactiva pendiente: configurar el único registro según README, iniciar con Microsoft en localhost:8080, aprobar consentimiento para el scope propio, entrar al dashboard y cerrar sesión. Probar atrás/adelante, recarga, cambio de pestaña y BFCache: no debe reaparecer información sin validar la cuenta. Probar selección con varias cuentas y recuperación tras expiración; nunca copiar ni imprimir tokens. Confirmar operaciones con COMMUNICATIONS_REAL_ENABLED=false. Los builds no sustituyen esta prueba interactiva del tenant.

Resultado de esta migración Entra: 142 pruebas aprobadas en 5.03 s; una advertencia heredada de Starlette/AnyIO. compileall, pip check, lint y builds React (sin configuración y con IDs ficticios) correctos. Compose config --quiet y build de backend/frontend correctos usando --env-file /dev/null y variables PostgreSQL ficticias, sin leer el .env real. No se iniciaron servicios ni se modificaron datos. Pendiente exclusivamente la prueba interactiva Microsoft con el tenant del usuario.

## Diagnóstico seguro de adaptación de comunicaciones

El 502 de adaptación ocurre antes de `comunicaciones.registrar()`: no registra comunicación ni contacta Twilio. Los logs posteriores confirmaron dos rechazos por `TokenLimitReached`: la validación exigía `stop` antes de evaluar si el contenido SMS era utilizable. El log no permite determinar qué texto o razonamiento agotó los tokens del proveedor.

Rutas identificadas y reproducidas con mocks:

- Error SDK/proveedor: `GroqGenerationFailed`, con razón fija para timeout, conexión, HTTP 400/401/403/404/429 y otros errores HTTP; una excepción inesperada del cliente se identifica por separado.
- Respuesta sin estructura esperada: `SmsAdaptationFailed reason=MalformedResponse`.
- Para Llamada, `finish_reason=length` mantiene `TokenLimitReached`. Para SMS se acepta `stop` o `length` con contenido utilizable; otros motivos mantienen `UnexpectedFinishReason`.
- Contenido nulo, no textual o vacío: `EmptyContent`.
- Normalización deja solo emojis/caracteres no permitidos, o la primera palabra excede 150 caracteres: `NoUsableSmsWords`.

Un SMS textual utilizable (`stop` o `length`) no se rechaza por el motivo de terminación ni por superar 150 caracteres: `adaptar_sms` extrae únicamente `message.content`, retira adornos Markdown, etiquetas SMS, comillas externas y bloques `<think>` completos o incompletos, normaliza a GSM-7 básico y conserva palabras completas hasta 150 caracteres. Nunca usa el campo separado de razonamiento. Si no queda texto alfanumérico utilizable, aborta antes de registrar. El prompt exige una sola línea de 120–130 caracteres sin razonamiento ni explicaciones. Se mantiene temperatura 0.2 y presupuesto fijo de 256 tokens; no se aumenta para resolver este caso. Llamada conserva su validación anterior, brevedad y simulación. No hay regeneración ni sustitución por mensajes hardcodeados cuando falla Groq.

Los logs contienen únicamente categorías, razones fijas y canal. No incluyen excepción, stack trace, cuerpo del proveedor, mensajes, destinatarios ni credenciales. Errores inesperados en código local ya no se convierten silenciosamente en un 502 de Groq. Para inspeccionar solo esas categorías tras desplegar (sin generar otro envío):

```bash
docker compose logs --no-color backend | rg 'GroqGenerationFailed|SmsAdaptationFailed|VoiceAdaptationFailed'
```

La regresión mantiene un SMS previo ID 6, provoca cada rechazo y verifica que no se agrega ningún registro ni se llama a proveedores. La suite bloquea conexiones de red y utiliza mocks de Groq, Twilio y SendGrid.

Validación de recuperación SMS con `length`: 207 pruebas aprobadas, con una advertencia heredada Starlette/AnyIO. Se prueba explícitamente entrega al servicio de comunicaciones mockeado, rechazo de contenido vacío/inutilizable sin registro, limpieza de formato/razonamiento y límite GSM-7; se mantienen las pruebas de proveedores, Email/WhatsApp, Voice simulada y fallos de Groq. `compileall app` y `git diff --check` correctos. Sin llamadas reales ni envíos.

## Verificación del commit 234a46c y envíos repetidos

La revisión partió de un árbol limpio y del commit `234a46c`. Este commit ya llama a `extraer_adaptacion(..., permitir_length=True)` para SMS. En ese código, `SmsAdaptationFailed reason=TokenLimitReached` no puede producirse: ese motivo solo puede rechazarse para Voice. Los logs reportados corresponden a una validación SMS anterior o a otro proceso/imagen; no se inspeccionó el contenedor en ejecución. `length` indica agotamiento del presupuesto de generación, pero esos logs no permiten saber si se consumió en contenido, razonamiento o una respuesta más extensa de lo pedido. No se incrementó el presupuesto de 256 tokens.

El componente `Comunicacion` tiene un único handler de envío; `apiFetch` hace un único fetch sin reintentos. El backend no repite la operación y el cliente Groq tiene `max_retries=0`. La ubicación actual del componente está fuera de los formularios de pago y búsqueda. React StrictMode no repite los handlers de clic. Los dos POST históricos no permiten atribuir la causa a un solo clic; podrían ser dos intentos separados o una interfaz anterior. No se agregó idempotencia.

Se conserva el bloqueo síncrono `enCurso` y el botón deshabilitado durante la solicitud. Se añade `type="button"` para impedir un submit accidental si el componente se incorpora a un formulario. Dos pruebas ejecutan el componente real mediante un arnés de hooks y API mockeada: un clic inicia un POST, varios clics antes y después del render no agregan solicitudes mientras está pendiente, se bloquea el selector y al terminar se permite un nuevo intento tanto tras éxito como tras error. Estas pruebas no son E2E de navegador. CI ejecuta `npm test`.

Se añaden pruebas de SMS de 120–130 caracteres para `stop` y `length` y de palabras en 22 longitudes alrededor del máximo de 150. Resultado: 231 pruebas Python y 2 pruebas de componente aprobadas (233 en total); una advertencia heredada Starlette/AnyIO. `python -m compileall app`, `git diff --check`, `npm run lint` y `npm run build` correctos. Sin proveedores reales, commits, push ni cambios a la base existente.

Para reconstruir y recrear backend y frontend desde la raíz, conservando la base:

```bash
docker compose up -d --build --force-recreate --no-deps backend frontend
```

La recreación no se ejecutó durante esta revisión. Es necesaria para que los procesos utilicen el código de la imagen reconstruida; construir una imagen por sí solo no reemplaza un contenedor existente.

## Investigación de EmptyContent

La configuración local `.env` selecciona `openai/gpt-oss-20b`; Compose pasa `GROQ_MODEL` al backend. Esto identifica la configuración del proyecto, no verifica el entorno del contenedor en ejecución. El diagnóstico compara el modelo solicitado con el devuelto. La llamada usa Chat Completions, no Responses ni streaming. Por lo tanto, se espera `choices[0].message.content` como string. En el SDK OpenAI 3.13.0 instalado, `content` es opcional y los campos adicionales de Groq se conservan; una prueba con transporte HTTP mockeado verifica que `message.reasoning` se conserva sin sustituir el contenido final.

Según [Groq Reasoning](https://console.groq.com/docs/reasoning), GPT-OSS entrega el razonamiento en `message.reasoning` por defecto y la respuesta final en `message.content`; no admite `reasoning_format`. [La documentación del modelo](https://console.groq.com/docs/model/openai/gpt-oss-20b) muestra su uso con Chat Completions. No se encontró incompatibilidad documentada en la ruta utilizada. Que los tokens de razonamiento agoten el presupuesto de 256 antes de producir respuesta final es una hipótesis, no una causa demostrada de los logs recibidos. No se modificó el presupuesto, el modelo ni el esfuerzo de razonamiento mientras falta evidencia.

`EmptyContent` solo demuestra que el primer `message.content` no es string o es vacío/solo espacios; no permite distinguir None, ausencia del campo, una estructura no textual, refusal o razonamiento sin respuesta final. `choices` ausente/vacío se clasifica como `MalformedResponse`. Una lista de bloques de texto no corresponde al content string esperado en este endpoint; se diagnostica su tipo y se sigue abortando, sin convertir arbitrariamente otros campos en mensajes al cliente.

Se añade el evento `GroqAdaptationResponse`: WARNING en fallo (con razón fija) e INFO al adaptar correctamente. Registra cantidad de choices y estructura de hasta cinco opciones, motivo de terminación permitido, presencia de message/content, tipo de content, longitud y si está en blanco, presencia/longitud de reasoning/refusal/campos alternativos conocidos, cantidad de tool calls, presencia de audio/function call y contadores de tokens, incluidos reasoning tokens si vienen en usage. Los modelos solo se imprimen si pertenecen a una lista explícita de identificadores conocidos; los demás son `other`, conservando el indicador de coincidencia. No imprime cuerpos, prompts, mensajes, destinatarios, credenciales, argumentos de tools, claves desconocidas ni nombres arbitrarios de tipos. El observador no llama servicios externos.

La siguiente respuesta fallida requiere únicamente el evento `GroqAdaptationResponse canal=SMS reason=EmptyContent structure=...`. En especial: modelo solicitado/devuelto, `finish_reason`, `content_received`, `content_type`, `content_is_none`, `content_length`, `content_blank`, `reasoning_present`, `reasoning_length`, `refusal_present`, `tool_calls_count`, `completion_tokens` y `reasoning_tokens`. Eso permitirá comprobar o descartar la hipótesis de presupuesto consumido en razonamiento. No debe compartirse un volcado completo del SDK ni provocarse un envío SMS para obtener el diagnóstico: la ruta normal contactaría Twilio si la adaptación tiene éxito.

Revisión repetida del frontend: existe un único POST de comunicación por handler y un solo fetch en `apiFetch`, sin reintentos. El componente está fuera de los formularios y conserva `type="button"`, bloqueo síncrono con useRef y controles deshabilitados. Las dos pruebas de componente vuelven a pasar para éxito/error, un clic y clics repetidos pendientes. Cuatro logs POST por sí solos no prueban cuatro clics manuales ni una duplicación automática; se necesitaría una traza del navegador con cantidad y timing de interacciones/solicitudes, sin cuerpos, cabeceras ni datos personales. No se añadió idempotencia ni se modificó frontend en esta investigación.

Resultado: 244 pruebas Python + 2 pruebas de componente = 246 aprobadas. Las pruebas nuevas usan el SDK real con httpx.MockTransport y cubren None, string vacío, espacios, contenido válido stop/length, choices vacío, contenido en lista, campo content ausente y metadatos malformados/sensibles. En los casos inválidos no se invoca comunicaciones. `compileall app`, `git diff --check`, `npm run lint` y `npm run build` correctos; una advertencia heredada Starlette/AnyIO. Sin llamadas reales a Groq/Twilio, envíos, cambios de modelo, commit ni push.

## Control de reasoning SMS GPT-OSS

La prueba aislada inicial confirmó content vacío con finish_reason=length: 256 completion tokens, 254 reasoning tokens. Se implementa `reasoning_effort="low"` exclusivamente para SMS con `openai/gpt-oss-20b` o `openai/gpt-oss-120b`. [La referencia oficial de Groq](https://console.groq.com/docs/api-reference) admite low/medium/high para ambos y define medium como valor por defecto; minimal/none no pertenecen al conjunto soportado por estos modelos. Se conserva max_tokens=256. No se usa reasoning_format ni se intenta desactivar razonamiento con include_reasoning, que solo controla su inclusión en la respuesta.

El script aislado replica el mismo control y emite solo modelo, finish_reason, content_length, reasoning_length, completion_tokens y reasoning_tokens. Continúa sin importar app, con datos ficticios y transporte restringido a una petición POST al endpoint Groq, sin redirects ni reintentos.

Validación: 260 pruebas Python aprobadas (una advertencia heredada Starlette/AnyIO), compileall app/scripts y git diff --check correctos. Las pruebas nuevas verifican la política por modelo/canal, serialización del parámetro por el SDK, política idéntica en el script, salida limitada a metadatos y bloqueo de otros destinos/segunda petición. Frontend no se modificó en esta actualización.

Después de las pruebas se ejecutó exactamente una petición real con el script, reasoning_effort=low, modelo openai/gpt-oss-20b y presupuesto sin cambios. Resultado: finish_reason=length, content_length=0, reasoning_length=616, completion_tokens=256, reasoning_tokens=254. Groq aceptó el parámetro, pero low no dejó presupuesto suficiente para una respuesta final en esta prueba. No se reintentó ni se cambió modelo/presupuesto automáticamente. El flujo sigue sin estar listo para validación mediante /api/comunicaciones: el caso ficticio reprodujo EmptyContent aun con low. No se contactó Twilio, otros proveedores ni la base de datos durante la petición real; sin envíos, commit ni push.

## Modelo SMS separado: Qwen 3.8 instruct

Se incorpora GROQ_SMS_MODEL, con default qwen/qwen3.8-27b y reasoning_effort=none exclusivamente para SMS. La configuración local .env añade ese valor sin modificar GROQ_MODEL=openai/gpt-oss-20b. Compose transmite ambas variables por separado. Estrategias y adaptación de voz siguen usando GROQ_MODEL; Email y WhatsApp conservan el mensaje original. La política previa low se mantiene solo si se configura explícitamente GPT-OSS como GROQ_SMS_MODEL, sin cambiar automáticamente el modelo tras un error. Se mantiene presupuesto SMS de 256 tokens, prompt de 120–130 caracteres y normalización GSM-7 con límite absoluto de 150 por palabras completas.

[La referencia de Groq](https://console.groq.com/docs/api-reference) admite reasoning_effort=none para Qwen 3.8 y lo identifica como modo sin razonamiento. No se cambia facturación ni configuración de cuenta.

Se actualizan primero las pruebas con mocks: separación del modelo de estrategias/voz/SMS, Email/WhatsApp sin generación, petición SDK con modelo Qwen y none, modelo SMS por defecto y script con la misma configuración. El script emite solo modelo solicitado/devuelto, finish_reason, content_length, reasoning_length, completion_tokens y reasoning_tokens. Tras obtener la respuesta ejecuta por ruta únicamente el archivo puro app/services/mensajes.py (sin importar el paquete app) y aplica adaptar_sms/validar_sms; código de salida 0 confirma normalización válida <=150, 2 indica fallo local. No imprime el texto ni accede a comunicaciones, base o proveedores de envío.

Validación: 265 pruebas Python aprobadas, una advertencia heredada Starlette/AnyIO. compileall app/scripts y git diff --check correctos. Frontend no modificado en esta actualización.

Una sola petición real posterior a las pruebas, con datos ficticios: modelo solicitado/devuelto qwen/qwen3.8-27b, finish_reason=stop, content_length=42, reasoning_length ausente, completion_tokens=18, reasoning_tokens ausente. Groq aceptó none y el script terminó con código 0: la respuesta pasó normalización y límite SMS. Los contadores ausentes no se reportan como cero. El mensaje ficticio breve produjo una salida más corta que la meta 120–130; no se rellena artificialmente ni se sustituye por una plantilla. No se realizó una segunda petición.

El resultado permite reconstruir backend y comprobar el flujo en modo simulado (COMMUNICATIONS_REAL_ENABLED=false) sin contactar Twilio. No se reconstruyó ni se llamó /api/comunicaciones real durante esta validación; tampoco se enviaron SMS, se usaron clientes reales ni se hizo commit/push. Una muestra exitosa valida este caso, no garantiza todas las futuras generaciones.

## Fidelidad de la adaptación SMS

Tras observar una consecuencia financiera inventada en una simulación integrada, se refuerza SMS_INSTRUCCION en el archivo puro servicios/mensajes.py. Backend y script comparten exactamente el prompt. Exige usar exclusivamente hechos del original, no deducir consecuencias financieras y omitir cualquier dato/consecuencia no explícito. Enumera recargos, intereses, penalizaciones, descuentos, convenios, reestructuraciones, condiciones financieras, fechas, importes y contactos; prohíbe calcular plazos/importes o inventar firmas. La fidelidad tiene prioridad sobre la meta de longitud: si el original es breve, no se rellena para llegar a 120–130.

No se implementa un filtro semántico basado en palabras: rechazaría datos legítimos cuando el original sí los incluye y no detectaría todas las paráfrasis. El prompt no garantiza ausencia de alucinaciones para todas las salidas; sigue siendo necesaria la revisión de pruebas simuladas. Se conservan modelo Qwen/none, presupuesto, normalización por palabras completas, GSM-7 y límite 150; Email/WhatsApp originales y Voice simulado.

Los mocks de SDK y script verifican igualdad del prompt compartido y todas las restricciones. El modo opcional --revision-ficticia guarda únicamente el SMS generado desde la fixture incorporada en un archivo temporal privado (0600), sin prompts/razonamiento y sin texto en stdout. La CLI no acepta datos de clientes. Los tests comprueban privacidad del archivo, salida de metadatos y una única petición.

Validación: 269 pruebas Python y 2 pruebas de componente aprobadas (271 total), compileall app/scripts y git diff --check correctos, con una advertencia heredada Starlette/AnyIO. Frontend no modificado en esta actualización.

Una sola petición aislada a Groq, sin comunicaciones/base/Twilio: Qwen 3.8, reasoning_effort=none, finish_reason=stop, content_length=42, completion_tokens=18, reasoning_length/reasoning_tokens ausentes. La revisión manual del archivo ficticio comprobó que la salida solo conserva pago MXN 500 y vencimiento 10 de octubre; no agregó recargos, intereses, penalizaciones ni otros hechos. Pasó normalización SMS <=150. Se puede repetir la prueba integrada únicamente en modo simulado, tras reconstruir backend. Sin envíos, commit ni push.
