# Arquitectura

React/Vite conserva sidebar, tablas y paneles empresariales. FastAPI autentica cada endpoint protegido con access tokens Microsoft Entra ID y SQLAlchemy accede a PostgreSQL. Se conservan login, comunicación simulada, historial y cartera priorizada.

Hay tres capas: **IA predictiva** (scikit-learn / RandomForestClassifier), **IA generativa** (Groq) y **Analítica** (consultas PostgreSQL y React/Recharts). La tercera interpreta riesgo, estrategias, comunicaciones, pagos y snapshots; no es un tercer modelo de IA ni prueba causalidad de recuperación.

```text
PostgreSQL (deudas + pagos) → seis features → Random Forest local
  → probabilidad, score y segmento en Cliente
  ├─ Evaluar cartera: termina en el riesgo, sin Groq ni comunicaciones
  └─ Generación individual solicitada: contexto mínimo → Groq → HistorialMensaje
Registros operativos + riesgo + snapshots → Analítica integrada
```

El bosque aprobado usa 12,000 historiales sintéticos y conserva 200 árboles, profundidad 6, mínimo 10 por hoja, clases balanceadas y semilla 42. AUC .8464, accuracy .7558, precision .6118, recall .8208 y F1 .7010 corresponden solo al test sintético, no a cartera empresarial real ni a un modelo calibrado/certificado para producción. La importancia relativa de pagos tardíos (~72.33%) y días de atraso (~22.58%) domina frente al saldo; no es atribución causal. Ver [Modelo ML](MODELO_ML.md) y [Decisiones técnicas](DECISIONES_TECNICAS.md).

GET /api/clientes permite query por nombre (sin distinguir mayúsculas), ID y folio CL-000001, segmento, analizado, estatus_deuda y orden (prioridad/saldo/atraso/vencimiento/nombre). Los folios se derivan del ID, no requieren columna. Las deudas activas tienen saldo positivo. La cartera muestra el vencimiento activo más antiguo, para priorizar vencidas; los días se calculan desde la fecha actual del servidor. El detalle devuelve todas las deudas, pagos, la última estrategia y las comunicaciones del cliente, ordenadas por fecha e ID descendentes. Cada comunicación incluye canal, fecha, mensaje y estado. Los registros históricos marcados exitosos se conservan sin afirmar entrega verificada.

`POST /api/cartera/evaluar` es una acción autenticada manual que obtiene clientes con deuda activa y procesa solo evaluaciones ausentes/incompletas. Reutiliza `recalcular_riesgo`; escribe únicamente `Cliente.probabilidad_pago_a_tiempo`, `score_riesgo` y `segmento`, sin tocar deudas/pagos ni generar estrategias o comunicaciones. No consulta Groq/Twilio/SendGrid ni depende de `COMMUNICATIONS_REAL_ENABLED`. Cada cliente se relee con `FOR UPDATE` y transacción propia: ante fallo se revierte ese cliente y continúa el lote. Los ya evaluados se omiten; no hay caducidad temporal por versión/fecha ni reevaluación forzada. Devuelve conteos y errores seguros; modelo ausente devuelve 503. [Contrato completo](EVALUAR_CARTERA.md).

La acción de Cartera bloquea doble clic, informa carga/resultado y actualiza tabla, métricas y ficha abierta. La tabla muestra score, segmento y prioridad. Esta última sigue siendo `round((score_riesgo or 0) × saldo_pendiente, 2)`: **índice interno de ordenamiento, no dinero**, que combina riesgo estimado e impacto económico. El lote permite resolver prioridad cero por ausencia de evaluación cuando el usuario lo ejecuta y revisa los fallos.

POST /api/deudas/{id}/pagos valida monto decimal positivo de hasta dos decimales, saldo y estado. La fecha es el día del servidor; no se aceptan fechas retroactivas. Bloquea primero Cliente y después Deuda con SELECT FOR UPDATE, registra Pago, actualiza saldo/estatus, hace flush y recalcula ML antes de commit. Todos los pagos de un cliente se serializan en PostgreSQL, aunque correspondan a distintas deudas. Cualquier error hace rollback. No hay reintento automático de pagos; ante una respuesta perdida consultar el historial antes de volver a enviar.

POST /ia/analizar-riesgo/{id} primero comprueba saldo. Sin deuda limpia score/probabilidad a NULL y segmento a Sin deuda, sin ejecutar Random Forest ni Groq. Con deuda y estrategia previa devuelve la última guardada; solamente regenerar=true pide una nueva versión. Sin estrategia calcula ML y solicita Groq (timeout 20 segundos, sin reintentos, temperature 0.5). La huella del contexto se conserva como referencia de generación; ya no dispara regeneraciones automáticas. Errores del proveedor devuelven 502 sin guardar mensajes; si una generación requiere clave y falta, devuelve 503. No hay plantilla local.

Toda la fila selecciona al cliente, llena el ID y desplaza a #operacion. El panel Resultado del análisis consulta únicamente GET /api/clientes/{id}; no calcula ML ni llama Groq. Muestra resumen financiero, fechas, riesgo y estrategia guardada; deudas/pagos/comunicaciones quedan en subsecciones compactas desplegables del mismo panel. No hay ficha debajo de cartera. Los clientes sin estrategia muestran No generada y Sin calcular donde corresponde. Sin deuda se muestra No aplica — sin deuda activa y no hay botones de generación.

GET de detalle expone sin_deuda_activa, tiene_estrategia y fecha_ultima_estrategia. En consultas, los clientes sin saldo muestran score/probabilidad nulos aunque tengan valores históricos; GET no modifica la base. Al procesarlos explícitamente o liquidar su última deuda se persiste la limpieza. Si quedan otras deudas positivas, el pago sigue recalculando ML con las seis features. La columna score_riesgo ya era nullable; este ajuste no requiere migración adicional.

La tabla de cobranza usa GET /api/clientes?solo_con_deuda=true más sus filtros. GET /api/clientes sin ese parámetro sigue siendo un listado general. Clientes liquidados se pueden consultar por ID en Operación de Cobranza.


Métricas: saldo vencido positivo por fecha o estatus; clientes con estrategia mediante COUNT DISTINCT; sin evaluar por segmento; deudores activos por saldo. Las claves anteriores se conservan y se agregan total_clientes, clientes_sin_evaluar y saldo_pendiente.

app.migrate agrega columnas anulables sin eliminar registros. Se ejecuta explícitamente antes de desplegar; create_all no sustituye la migración. PostgreSQL usa bloqueo asesor transaccional para evitar dos migraciones simultáneas. Docker conserva el volumen postgres_data; Nginx sirve React y hace proxy /backend.

## Base demo y evidencia

El seed de entrega calcula los scores evaluados con el pipeline/modelo real después de cargar todo el historial ficticio. La base conserva 15 clientes, 23 deudas, 40 pagos, 24 estrategias, 24 comunicaciones simuladas, 15 snapshots y 0 administradores. 13 y 14 parten sin evaluar y 15 sin deuda; estrategias y snapshots son ficticios. No se usan scores manuales para los evaluados.

La restauración PostgreSQL aislada y el backend comprobaron coherencia de scores y prioridad. En otra prueba aislada, Evaluar cartera encontró 14 activos, evaluó 2, omitió 12 y no tuvo fallos; dos solicitudes concurrentes no duplicaron las evaluaciones. Esto no certifica concurrencia de pagos/callbacks, carga empresarial ni entrega real. [QA](QA.md#validación-posterior-a-mejora-del-modelo) distingue estas ejecuciones de auditorías históricas.

## Comunicaciones opcionales

`app/services/configuracion.py` decide disponibilidad efectiva con el interruptor global y las variables del canal. `comunicaciones.py` valida destinatario, persiste la intención y coordina `sendgrid_service.py` o `twilio_service.py`. `main.py` conserva validación del payload y autenticación; no contiene lógica del SDK. Los adaptadores usan timeout de 15 segundos, sin reintentos automáticos. Voice queda reservado y simulado.

POST /api/comunicaciones conserva compatibilidad; GET /api/integraciones/estado es protegido y no realiza consultas externas. React consulta disponibilidad, muestra Real/Simulado y bloquea botón y solicitudes con estado más una referencia síncrona. Si no puede consultar el modo, impide enviar hasta recargar. El historial distingue estados reales, simulados e históricos.

Comunicacion incorpora modo, estado, provider, external_id, error_tecnico y provider_status anulables. Los registros antiguos permanecen sin clasificación nueva para no afirmar entregas desconocidas. Nuevos registros: Simulado con exitoso=false o Pendiente real, seguido de Enviado/Fallido. Enviado inicial representa aceptación, no recepción final. `app/twilio_webhook.py` valida firma oficial sin Entra y delega actualización por SID a `services/twilio_callbacks.py`, con bloqueo de fila PostgreSQL, progresión monotónica y finales protegidos. Una query firmada de correlación permite vincular un callback temprano a la intención ya persistida; el finalizador vuelve a leer la fila para conservar estados confirmados. Se almacenan solo estado del proveedor y código seguro de error. El índice external_id es no único para no romper datos heredados; SID ambiguo se ignora. La ficha muestra estado confirmado al consultar/actualizar el detalle, sin polling del navegador. Una caída sin SID ni callback correlacionado aún puede dejar Pendiente: no existe transacción atómica con el proveedor ni garantía de entrega exactamente una vez. Configuración y pruebas locales en README, sección Status Callback de Twilio.

Random Forest → riesgo → Groq → texto → revisión humana → envío opcional → registro. Ninguna consulta, generación IA o cálculo de riesgo envía comunicaciones automáticamente.

## Autenticación Entra con un solo registro

React → MSAL (PKCE/redirect) → access token para api://CLIENT_ID/access_as_user → apiFetch → HTTPBearer → get_entra_user → operación existente. No se solicita Graph para llamar la API ni se envía idToken. MsalProvider recibe la única PublicClientApplication y gestiona initialize/handleRedirectPromise. Login selecciona cuenta; al restaurar se reutiliza una sola cuenta o la activa previamente elegida, nunca una cuenta arbitraria entre varias.

app/auth.py valida criptográficamente con PyJWT y claves RSA publicadas por Microsoft. Discovery y JWKS tienen caché/rotación, sin certificados hardcodeados. La identidad segura es un diccionario con id/nombre/email; ninguna ruta depende ya del modelo Administrador. El modelo y la tabla permanecen intactos como legado, sin uso para autorizar. POST /auth/login no existe; GET /auth/me valida el mismo token que todas las operaciones.

El guard de sesión impide renderizar datos durante inicialización y redirect, valida /auth/me antes de montar Dashboard y revalida en navegación/BFCache. MSAL renueva tokens; apiFetch obtiene exclusivamente accessToken del scope configurado. Los 401/403 desmontan la sesión visible sin reintentar operaciones de negocio.
