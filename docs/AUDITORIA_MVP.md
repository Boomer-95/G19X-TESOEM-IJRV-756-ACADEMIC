# Auditoría técnica y cierre del MVP

## Suite de referencia verificada

La verificación previa a esta revisión aprobó **388 tests backend y 36 tests frontend**. Las cifras inferiores conservadas más abajo corresponden a auditorías históricas, no al total actual. La revisión externa añade tests del diagnóstico de restauración y del ErrorBoundary; el resultado posterior debe consultarse en la ejecución completa de las suites.

Los ajustes acotados incluyen documentación de las diez columnas migrables y `estrategia_id`, retirada de residuos vacíos, pull explícito de PostgreSQL antes de restaurar, diagnóstico técnico sin secretos, ErrorBoundary raíz y distinción entre esquema incompleto y PostgreSQL inaccesible. No se ejecutan migraciones/restauraciones sobre la base operativa ni envíos reales. El ErrorBoundary cubre errores de renderizado del árbol React; los errores de red y handlers asíncronos conservan su manejo existente.

Revisión del 2 de octubre de 2026, sobre `main`, base `8581bc0`. El árbol estaba limpio al iniciar; se revisaron los diez commits más recientes antes de modificar archivos. Cambios locales para revisión, sin commit ni push.

## Alcance y método

Se inspeccionaron FastAPI, React/MSAL, SQLAlchemy/PostgreSQL, Docker/Nginx, migraciones, ML, Groq, Twilio, SendGrid, tests y GitHub Actions. Se diferenciaron código correcto, problemas reproducidos, recomendaciones y validaciones externas pendientes.

Los tests de backend eliminan credenciales del entorno, deshabilitan dotenv, usan SQLite temporal, firman JWT/callbacks con fixtures y bloquean conexiones externas. Frontend usa los componentes y módulos reales con hooks/transporte simulados. No se realizaron envíos ni llamadas reales a Groq, Twilio, SendGrid o Entra.

PostgreSQL solo recibió SELECT sobre filas ficticias construidas con VALUES para demostrar el orden de fechas nulas. No se consultaron ni modificaron tablas de negocio. La configuración de Compose se validó sin imprimir variables sensibles. El escaneo Git examinó 189 blobs textuales históricos con patrones de claves/tokens: sin coincidencias; esto no sustituye un escáner de secretos especializado.

## Clasificación

| Área | Estado | Problema encontrado | Corrección realizada | Evidencia/prueba | Pendiente manual |
|---|---|---|---|---|---|
| Arquitectura/API | LISTO | Sin fallo confirmado de estructura o endpoints | Ninguna | Inspección y suite de API | Ninguno específico |
| Entra | PENDIENTE MANUAL | Sin fallo confirmado de validación; integración depende del tenant | Cobertura crítica adicional de apiFetch, sin modificar autenticación | JWT RSA/JWKS mock, ausencia/invalidez/expiración/scope y rechazo/cambio de cuenta | Login, logout, renovación silenciosa, refresh, BFCache y atrás/adelante con cuenta real |
| Dashboard | LISTO | Cálculos provienen de BD; clientes sin evaluar y estrategias incluyen históricos | Ninguna alteración de fórmulas | Métricas con cartera controlada, pagos y saldo cero | Comparación con dataset propio de demostración |
| Clientes/cartera | CORREGIDO | Filtro Sin calcular/No definido omitía segmentos nulos | Incluir NULL de manera consistente con métricas | Nuevos tests con segmento nulo; búsqueda/folios/filtros/orden existentes | Ninguno específico |
| Pagos | LISTO | Sin fallo confirmado en validación, saldo y rollback | Se conserva lógica monetaria y bloqueos | Pago parcial/total, sobrepago, decimales, fechas y fallo ML | Concurrencia PostgreSQL y recuperación tras respuesta incierta en base aislada |
| Riesgo/ML | LISTO | Modelo sintético; no usa vencimiento actual como feature | Ningún cambio del modelo o umbrales | Seis features verificadas, artefacto compatible, saldo cero sin predicción | Validación estadística con datos reales autorizados, fuera del alcance de la demo |
| Groq | PENDIENTE MANUAL | Modelos y respuestas dependen de cuenta y plan | No se altera configuración funcional | Mocks de timeout, errores, vacío, truncamiento, regeneración y conservación | Disponibilidad de modelos y revisión semántica/financiera de una estrategia |
| Utilidad modelos Groq | CORREGIDO | Consulta al importar y excepción completa en stdout | Guard de ejecución, error genérico, cierre de SDK y timeout sin retries | Mock con secretos sentinela, import sin cliente externo | Consulta manual opcional, no necesaria para tests |
| SendGrid | PENDIENTE MANUAL | HTTP 202 no confirma entrega | Comportamiento correcto conservado | Mock conserva cuerpo completo y muestra aceptación | Remitente verificado y un email controlado; entrega en panel proveedor |
| Twilio SMS | CORREGIDO | E.164 aceptaba dígitos Unicode | Solo dígitos ASCII en validación | SDK mocks, longitud, normalización, rechazo antes de SID y logs permitidos | Un SMS controlado si se requiere demostrar canal real |
| Twilio WhatsApp | PENDIENTE MANUAL | Sandbox/Trial/túnel y destino requieren proveedor | Se conserva alias mexicano sin modificar SMS | Mocks +52/+521 y cuerpo completo | Destinatario unido, origen, lectura/entrega y URL pública |
| Webhook Twilio | CORREGIDO | Ignoraba accepted válido | accepted con rango anterior a queued y etiqueta sin entrega confirmada | Firma válida/inválida, correlación, idempotencia, estados y retrocesos | Callback real por Cloudflare/Twilio |
| Comunicaciones/Llamada | CORREGIDO | API permitía cobranza con saldo cero; Voice simulado por diseño | Rechazo 409 antes de Groq/proveedores cuando no hay deuda activa | Mocks de canales, fallo real sin éxito simulado y doble clic | Solo canales reales autorizados |
| Historial | CORREGIDO | PostgreSQL DESC priorizaba NULL; frontend inventaba fecha 1969/1970 | NULLS LAST y marcador de fecha ausente/inválida | SELECT VALUES PostgreSQL y tests de API/componentes | Ninguno específico |
| Frontend | CORREGIDO | Error de consulta antigua podía sobrescribir estado de la más reciente | Solo la solicitud vigente actualiza el error | Dos regresiones HTTP/red; tests, lint y build | Navegador real con Entra en desktop/tablet/móvil |
| PostgreSQL/Docker | PENDIENTE MANUAL | Sin fallo confirmado de configuración; faltan healthchecks app como mejora | Ningún cambio de infraestructura ni volumen | Compose válido, volumen/puertos/dependencias inspeccionados | Persistencia al recrear servicios, migración y bloqueos en BD aislada |
| Seguridad/dependencias | PENDIENTE TÉCNICO | npm audit: Vite alta y esbuild moderada, herramientas de desarrollo | No realizar actualización mayor forzada; corregir utilidad que imprime errores | Escaneo de Git, logs sentinela, firmas y validación | Actualización compatible y políticas Entra/TLS antes de producción |
| Tests/CI | LISTO | CI ya cubre backend y frontend, lint y build | Ampliar script frontend para nuevas regresiones | Suites locales completas; workflow inspeccionado | Ejecución Actions e imágenes tras decisión del usuario de publicar |
| README/configuración | CORREGIDO | Plantilla referenciada ausente y documentación desactualizada | README acorde a código y .env.example sin secretos | Revisión contra variables, rutas, migración y Compose reales | Completar únicamente configuración local que falte |

## Problemas reproducidos y alcance de los cambios

1. Clientes con segmento SQL NULL desaparecían de «Sin calcular», pese a contarse como sin evaluar y mostrarse así en la ficha. Se corrigen los dos alias de filtro sin cambiar otros segmentos.
2. Dígitos Unicode pasaban la expresión E.164 porque Python interpreta `\d` ampliamente. Se restringe a `[0-9]`; números ASCII existentes no cambian.
3. `accepted` firmado respondía 204 pero no persistía estado. Se agrega como aceptación anterior a queued, nunca equivalente a delivered/read. Se mantiene el rechazo de retrocesos y duplicados.
4. Fechas nulas se convertían a epoch en React. Se presentan como «—», incluyendo valores inválidos, sin escribir fechas ficticias en BD.
5. En PostgreSQL, `DESC` sin especificación pone NULL primero. La consulta con VALUES lo reprodujo sin datos reales. Se fijó `NULLS LAST` para historial/última estrategia/pagos recientes, con desempate existente por ID.
6. La utilidad `ver_modelos.py` contactaba Groq al importarse y podía revelar texto sensible de excepciones. Solo se ejecuta explícitamente; errores genéricos y SDK cerrado. Tests simulan el proveedor.
7. Una respuesta HTTP fallida o excepción antigua de cartera podía sustituir el estado de una consulta posterior correcta. Los nuevos tests fallaron antes de agregar la comprobación de solicitud vigente y pasan después.
8. El README referenciaba una plantilla de configuración inexistente y tenía información duplicada/inexacta de migración y CI. Se documentó la arquitectura real, instalación conservadora y variables por nombre.

9. Aunque la ficha ocultaba cobranza sin deuda, una llamada directa a `/api/comunicaciones` podía contactar a un cliente liquidado. Los cuatro canales reprodujeron el problema con mocks. La API ahora responde 409 antes de adaptación/proveedor, sin persistir comunicaciones ni llamar Groq. Fixtures de tests de envío ahora incluyen deuda activa controlada.

## Decisiones de no modificación

- No cambiar IDs, tenant, scopes, secretos, MSAL, api.js ni autenticación backend; se amplían pruebas del transporte sin alterar su código.
- No reentrenar Random Forest ni incorporar features nuevas: se cambiaría un modelo funcional sin validación. Las seis features reales y sus supuestos quedan documentados.
- No sustituir modelos Groq configurados: los valores locales revisados son modelos actuales. Verificar el plan antes de usar el default heredado de estrategias.
- No reducir mensajes de Email/WhatsApp ni presentar aceptación como entrega. No inferir provider_status histórico.
- No cambiar query del callback: se usa en firma y correlación y está cubierta por tests. Twilio documenta URLs con parámetros de query y su validación exige preservarlos.
- No habilitar Voice; no migrar Float a Numeric ni introducir idempotencia distribuida como parte de correcciones pequeñas.
- No rehacer CSS, navegación, login ni componentes desde Stitch. No tocar referencias-stitch.
- No modificar workflows: ya ejecutan todas las etapas solicitadas. No actualizar dependencias con un salto mayor automático.
- No ejecutar seeds, migraciones ni pagos sobre BD de desarrollo; no recrear servicios ni borrar volúmenes.

## Pruebas externas para el propietario

1. **Entra/navegador:** login con cuenta autorizada; recargar; navegación atrás/adelante y retorno a pestaña; logout; volver atrás y comprobar ausencia de cartera; esperar expiración/renovación y confirmar reautorización. Verificar asignación de usuarios en la aplicación empresarial.
2. **PostgreSQL aislado:** respaldo y base de prueba independiente; pago parcial y final, fechas, métricas, dos pagos concurrentes que excederían el saldo; recrear servicios conservando volumen; migración idempotente. No usar cartera real para pruebas destructivas.
3. **Groq:** confirmar modelo de estrategias y de SMS disponibles; generar una estrategia ficticia, regenerar y comprobar conservación de anterior; revisión humana de importes, fechas y ausencia de consecuencias inventadas.
4. **Twilio WhatsApp, una sola prueba:** confirmar destinatario de prueba unido al Sandbox, túnel activo, callback público actualizado y backend recreado. Desde PluriOne hacer un único clic de envío para cliente de prueba con deuda activa. Revisar logs de backend; si falla antes de SID, registrar únicamente `TwilioRequestFailed channel=WhatsApp http_status=<entero> code=<entero>` junto con el error genérico de la aplicación. No reintentar hasta interpretar el código en documentación/panel de Twilio. Si se crea SID, verificar callbacks delivered/read y asociación a la misma comunicación.
5. **SMS/SendGrid:** solo si la demostración exige canales reales, un envío a destinatario propio por canal; revisar panel del proveedor. Email 202 debe seguir apareciendo como aceptación, incluso si el destinatario abre el correo.
6. **Frontend:** con sesión real, escritorio/tablet/móvil, filtros rápidos, selección con teclado, pago, scroll horizontal de tablas y estados del historial. Los mocks no prueban MSAL ni layout real del navegador.
7. **CI/seguridad:** ejecutar Actions cuando se decida guardar/publicar, y planificar actualización Vite/esbuild con pruebas completas. No publicar devserver; asegurar TLS y permisos antes de uso productivo.

## Resultados de verificación local

- Línea base: 330 tests backend y 11 frontend aprobados antes de cambios.
- Final: `pytest`, **342 aprobados**, una advertencia deprecada de Starlette/AnyIO de terceros, sin fallos.
- `npm test`: **29 aprobados** (12 comunicaciones/estados, 6 fechas/historial, 9 transporte autenticado y 2 concurrencia de cartera).
- `npm run lint`: aprobado, sin errores.
- `npm run build`: aprobado con Vite 5.4.21, 199 módulos.
- `python -m compileall app`: aprobado.
- `python -m pip check`: sin dependencias rotas.
- `docker compose config --quiet`: aprobado.
- PostgreSQL SELECT ficticio: orden original NULL primero; con NULLS LAST, fecha válida primero.
- `git diff --check`: aprobado, sin errores de whitespace.
- `npm audit`: pendiente técnico; dos dependencias de desarrollo afectadas, Vite alta/esbuild moderada. No se fuerza cambio mayor.

Se agregaron 12 casos backend y 18 frontend respecto a la línea base. Los fallos de reproducción se observaron antes de las correcciones; las suites finales pasan. Fixtures previos que probaban envío/adaptación ahora agregan deuda activa explícita para conservar el propósito de esas pruebas tras la protección de saldo cero.

No se construyeron/recrearon imágenes o servicios en esta auditoría; no se ejecutó GitHub Actions remoto. No se certifican entrega real, configuración del tenant, layout en navegador ni persistencia/concurrencia PostgreSQL mediante los tests SQLite.

## Referencias de proveedor

- [Twilio Message resource: estados y statusCallback](https://www.twilio.com/docs/messaging/api/message-resource).
- [Twilio: validar firmas y preservar URL/parámetros](https://www.twilio.com/docs/usage/security).
- [SendGrid Mail Send: respuesta de aceptación](https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send).
- [PostgreSQL: ORDER BY y tratamiento de NULL](https://www.postgresql.org/docs/current/queries-order.html).
- [Groq: disponibilidad y deprecaciones por plan](https://console.groq.com/docs/deprecations).

Estimación de cierre técnico: aproximadamente 90% del MVP de demostración. Es una valoración cualitativa, no un porcentaje de cobertura ni una certificación de producción. Las verificaciones externas y las dependencias de desarrollo pendientes impiden declararlo cerrado al 100%.
